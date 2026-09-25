import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import verify_channels as v


class SignatureTests(unittest.TestCase):
    def test_media_signature_accepts_real_containers(self):
        self.assertTrue(v.media_signature(b"\x47" + b"\x00" * 200))          # MPEG-TS
        self.assertTrue(v.media_signature(b"\x00" * 10 + (b"\x47" + b"\x00" * 187) * 3))  # padded TS
        self.assertTrue(v.media_signature(b"\x00\x00\x00\x18ftypisom" + b"\x00" * 64))
        self.assertTrue(v.media_signature(b"\xff\xf1\x50\x80\x01\xcf\xfc"))  # ADTS
        self.assertTrue(v.media_signature(b"\x00\x00\x00\x08moof" + b"\x00" * 32))
        self.assertFalse(v.media_signature(b""))
        self.assertFalse(v.media_signature(b"<html>denied</html>"))
        self.assertFalse(v.media_signature(b"#EXTM3U\n#EXT-X-TARGETDURATION:6\n"))


class ManifestParsingTests(unittest.TestCase):
    def test_variant_urls_skip_media_tags(self):
        manifest = ('#EXTM3U\n'
                    '#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs",URI="subs.m3u8"\n'
                    '#EXT-X-STREAM-INF:BANDWIDTH=1000,RESOLUTION=640x360\n'
                    'low/playlist.m3u8\n'
                    '#EXT-X-STREAM-INF:BANDWIDTH=3000,RESOLUTION=1280x720\n'
                    'https://cdn.example.org/high/playlist.m3u8\n')
        urls = v._variant_urls(manifest, "https://cdn.example.org/master.m3u8")
        self.assertEqual(urls, ["https://cdn.example.org/low/playlist.m3u8",
                                "https://cdn.example.org/high/playlist.m3u8"])

    def test_segment_urls_pick_media_and_relative(self):
        media = ('#EXTM3U\n#EXT-X-TARGETDURATION:6\n#EXTINF:6.0,\n'
                 'seg1.ts\n#EXTINF:6.0,\nhttps://cdn.example.org/seg2.ts\n'
                 '#EXT-X-ENDLIST\n')
        self.assertEqual(v._segment_urls(media, "https://cdn.example.org/live/index.m3u8"),
                         ["https://cdn.example.org/live/seg1.ts",
                          "https://cdn.example.org/seg2.ts"])

    def test_parse_playlist_pairs_preserves_extinf(self):
        text = ('#EXTM3U url-tvg="x"\n'
                '#EXTINF:-1 tvg-id="A.us",Channel A\n'
                'https://a.example/x.m3u8\n'
                '# comment\n'
                '#EXTINF:-1 tvg-id="B.us",Channel B\n'
                'https://b.example/y.m3u8\n')
        pairs = v.parse_playlist_pairs(text)
        self.assertEqual(len(pairs), 2)
        self.assertEqual(pairs[0], ('#EXTINF:-1 tvg-id="A.us",Channel A',
                                    'https://a.example/x.m3u8'))


class ProbeTests(unittest.TestCase):
    def test_master_then_media_then_segment_ok(self):
        master = '#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1\nlow/playlist.m3u8\n'
        media = ('#EXTM3U\n#EXT-X-TARGETDURATION:6\n#EXTINF:6.0,\nseg9.ts\n'
                 '#EXT-X-ENDLIST\n')
        segment = b"\x47" + b"\x00" * 512

        def fake_fetch_text(url, _timeout):
            if url.endswith("master.m3u8"):
                return master, "https://cdn.example.org/master.m3u8"
            if url.endswith("low/playlist.m3u8"):
                return media, "https://cdn.example.org/low/playlist.m3u8"
            raise AssertionError(f"unexpected url {url}")

        with patch.object(v, "fetch_text", side_effect=fake_fetch_text), \
                patch.object(v, "fetch_bytes", return_value=segment):
            self.assertEqual(v.probe("https://cdn.example.org/master.m3u8"),
                             ("segment_ok", "manifest_and_segment"))

    def test_direct_media_without_segments_is_manifest_ok(self):
        media = '#EXTM3U\n#EXT-X-TARGETDURATION:6\n#EXT-X-ENDLIST\n'
        with patch.object(v, "fetch_text", return_value=(media, "https://a.example/live.m3u8")):
            self.assertEqual(v.probe("https://a.example/live.m3u8"),
                             ("manifest_ok", "no_segments_listed"))

    def test_html_body_is_unavailable(self):
        with patch.object(v, "fetch_text",
                          side_effect=v.ProbeFailure("unavailable", "not_hls_body")):
            self.assertEqual(v.probe("https://a.example/gone.m3u8"),
                             ("unavailable", "not_hls_body"))

    def test_network_error_is_inconclusive(self):
        with patch.object(v, "fetch_text",
                          side_effect=v.ProbeFailure("inconclusive", "tls_error")):
            self.assertEqual(v.probe("https://a.example/live.m3u8"),
                             ("inconclusive", "tls_error"))


class EmitTests(unittest.TestCase):
    def test_catalog_verified_only_alive(self):
        channels = [
            {"id": "Alive.us", "name": "Alive", "url": "https://a.example/alive.m3u8",
             "logo": "", "group": "News"},
            {"id": "Dead.us", "name": "Dead", "url": "https://a.example/dead.m3u8",
             "logo": "", "group": "News"},
        ]
        body = v.emit_catalog_verified(channels, {"Alive.us"},
                                       ["https://guide.example/us.xml"], "2026-09-25T00:00:00Z")
        text = body.decode()
        self.assertTrue(text.startswith("#EXTM3U"))
        self.assertIn("Alive", text)
        self.assertNotIn("Dead", text)
        self.assertIn("1 of 2", text)

    def test_root_verified_filters_invalid_and_dead(self):
        original = ('#EXTM3U x-tvg-url="https://guide.example/us.xml" url-tvg="https://guide.example/us.xml"\n'
                    '#EXTINF:-1 tvg-id="Ok.us",Ok Channel\n'
                    'https://ok.example/live.m3u8\n'
                    '#EXTINF:-1 tvg-id="Dead.us",Dead Channel\n'
                    'https://dead.example/live.m3u8\n'
                    '#EXTINF:-1 tvg-id="Insecure.us",Insecure Channel\n'
                    'http://insecure.example/live.m3u8\n')
        results = {"https://ok.example/live.m3u8": ("segment_ok", "manifest_and_segment"),
                   "https://dead.example/live.m3u8": ("unavailable", "http_404")}
        body = v.emit_root_verified(original, results, "2026-09-25T00:00:00Z")
        text = body.decode()
        self.assertIn("https://ok.example/live.m3u8", text)
        self.assertNotIn("dead.example", text)
        self.assertNotIn("insecure.example", text)
        self.assertIn("1 of 3", text)


class RunWiringTests(unittest.TestCase):
    def test_run_writes_outputs_from_fixtures(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            catalog = base / "channels.json"
            catalog.write_text(json.dumps([
                {"id": "Alive.us", "name": "Alive", "url": "https://a.example/alive.m3u8",
                 "logo": "", "group": "News"},
            ]))
            root = base / "usa-verified.m3u"
            root.write_text('#EXTM3U x-tvg-url="" url-tvg=""\n'
                            '#EXTINF:-1 tvg-id="Ok.us",Ok Channel\n'
                            'https://ok.example/live.m3u8\n')
            out_json = base / "verification.json"
            verified = base / "verified.m3u"
            root_out = base / "root-out.m3u"

            def fake_probe(url, _timeout=10.0):
                return ("segment_ok", "manifest_and_segment")

            with patch.object(v, "probe", side_effect=fake_probe):
                report = v.run(catalog, root, out_json, verified, root_out,
                               workers=2, timeout=1.0, skip_root=False, skip_catalog=False)
            self.assertEqual(report["catalog"]["counts"], {"segment_ok": 1})
            self.assertTrue(out_json.is_file())
            self.assertIn("Alive", verified.read_text())
            self.assertIn("Ok Channel", root_out.read_text())


if __name__ == "__main__":
    unittest.main()
