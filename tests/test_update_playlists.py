import base64
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import update_playlists as u


class ParserTests(unittest.TestCase):
    def test_quoted_comma_directive_and_multiple_entries(self):
        text = '''#EXTM3U x-tvg-url="https://example.org/epg.xml"
#EXTINF:-1 tvg-id="News.us@SD" tvg-logo="https://example.org/a,b.png" group-title="News;Sports",News (720p) [Not 24/7]
https://news.example.org/live.m3u8
#EXTINF:-1 tvg-id="Other.us",Other
#EXTVLCOPT:http-referrer=https://third-party.example/
https://third-party.example/other.m3u8
'''
        entries = list(u.parse_m3u(text))
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0][0]["tvg-logo"], "https://example.org/a,b.png")
        self.assertFalse(entries[0][3])
        self.assertTrue(entries[1][3])
        self.assertEqual(entries[0][0]["group-title"], "News;Sports")
        with self.assertRaises(ValueError):
            list(u.parse_m3u("<html>error</html>"))

    def test_url_validation_rejects_leaks_and_non_hls(self):
        bad = ["http://news.example.org/live.m3u8", "https://127.0.0.1/live.m3u8",
               "https://user:pass@news.example.org/live.m3u8",
               "https://news.example.org:bad/live.m3u8",
               "https://news.example.org/live.m3u8?token=secret",
               "https://news.example.org/live.m3u8?authToken=secret",
               "https://news.example.org/live.m3u8?deviceModel=roku&embedPartner=other",
               "https://news.example.org/live.m3u8\n#EXTINF:-1,Evil",
               "https://news.example.org/index.html", "file:///local.m3u8"]
        for value in bad:
            with self.subTest(value=value):
                self.assertFalse(u.valid_url(value, stream=True))
        self.assertTrue(u.valid_url("https://news.example.org/live.m3u8?ads.xumo_channelId=42", stream=True))

    def test_platform_ids_only_for_flagged_sources(self):
        policy = {"allowed_hosts": [{"host": "cdn.example.org",
                                     "evidence_url": "https://example.org/free"}],
                  "allowed_host_suffixes": [], "approved_channels": [],
                  "excluded_ids": []}
        source = {"name": "fast", "url": "https://example.org/fast.m3u"}
        pluto_id = "62ba60f059624e000781c436"        # 24 hex (Pluto TV)
        roku_id = "98cafb7f4b01848a967fda4bd2225bd7"  # 32 hex (Roku)
        samsung_id = "USBB320000397"                   # Samsung service ID
        for channel_id in (pluto_id, roku_id, samsung_id):
            with self.subTest(channel_id=channel_id):
                channel, why = u.channel_from_entry(
                    {"tvg-id": channel_id}, "FAST Channel",
                    "https://cdn.example.org/live.m3u8", source, policy, False)
                self.assertIsNone(channel)
                self.assertEqual(why, "not_us_or_no_id")
                channel, why = u.channel_from_entry(
                    {"tvg-id": channel_id}, "FAST Channel",
                    "https://cdn.example.org/live.m3u8", source, policy, False,
                    id_style="platform")
                self.assertEqual(why, "accepted")
                self.assertEqual(channel["id"], channel_id)
        channel, _ = u.channel_from_entry(
            {"tvg-id": "Channel.ca"}, "Canadian",
            "https://cdn.example.org/live.m3u8", source, policy, False,
            id_style="platform")
        self.assertIsNone(channel)

    def test_redirect_cache_required_for_flagged_sources(self):
        policy = {"allowed_hosts": [{"host": "cdn.example.org",
                                     "evidence_url": "https://example.org/free"}],
                  "allowed_host_suffixes": [], "approved_channels": [],
                  "excluded_ids": []}
        source = {"name": "fast", "url": "https://example.org/fast.m3u"}
        original = "https://redirector.example/stvp-US1234"
        resolved = "https://cdn.example.org/21_jump/playlist.m3u8?ads.service_id=US1234"
        channel, why = u.channel_from_entry(
            {"tvg-id": "US1234AB"}, "21 Jump Street", original, source, policy, False,
            id_style="platform", redirect_cache={})
        self.assertIsNone(channel)
        self.assertEqual(why, "redirect_unresolved")
        channel, why = u.channel_from_entry(
            {"tvg-id": "US1234AB"}, "21 Jump Street", original, source, policy, False,
            id_style="platform", redirect_cache={original: resolved})
        self.assertEqual(why, "accepted")
        self.assertEqual(channel["url"], resolved)

    def test_group_canonicalization(self):
        cases = {"News + Opinion": "News", "Sports & Outdoors": "Sports",
                 "Nature, History & Science": "Documentary", "En Español": "Spanish",
                 "Latino": "Spanish", "Kids": "Kids", "Movies": "Movies",
                 "TV & Entertainment": "Entertainment", "Weather": "Weather",
                 "Business": "Business", "Government": "Legislative",
                 "Something Odd": "General"}
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(u.canonical_group(raw), expected)

    def test_html_response_uses_github_api_fallback(self):
        source = {"name": "test", "url": "https://example.org/channels.m3u",
                  "github_api_fallback": "https://api.github.com/repos/example/playlist/contents/a.m3u"}
        with patch.object(u, "fetch_bytes", side_effect=[b"<html>temporarily blocked</html>",
                                                        b"#EXTM3U\n"]) as fetch:
            self.assertEqual(u.download_source(source), b"#EXTM3U\n")
            self.assertEqual(fetch.call_count, 2)
            self.assertTrue(fetch.call_args.kwargs["github_api"])

    def test_large_github_file_falls_back_to_blob_api(self):
        git_url = "https://api.github.com/repos/example/playlist/git/blobs/abc123"
        contents = json.dumps({"encoding": "none", "content": "", "git_url": git_url}).encode()
        blob = json.dumps({"encoding": "base64",
                           "content": base64.b64encode(b"#EXTM3U\n").decode()}).encode()

        class _Response:
            def __init__(self, payload):
                self._payload = payload

            def read(self, _n=-1):
                return self._payload

            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

        with patch.object(u, "urlopen", side_effect=[_Response(contents), _Response(blob)]) as opener:
            data = u.fetch_bytes("https://api.github.com/repos/example/playlist/contents/a.m3u",
                                 github_api=True)
        self.assertEqual(data, b"#EXTM3U\n")
        self.assertEqual(opener.call_count, 2)
        self.assertEqual(opener.call_args_list[1].args[0].full_url, git_url)

    def test_only_approved_hosts_and_free_ids(self):
        policy = {
            "allowed_hosts": [{"host": "news.example.org", "evidence_url": "https://news.example.org/free"}],
            "allowed_host_suffixes": [{"suffix": ".cablecast.tv", "evidence_url": "https://cablecast.tv/"}],
            "approved_channels": [{"id": "Sports.us", "hosts": ["cdn.example.org"],
                                   "evidence_url": "https://sports.example.org/free", "category": "Sports"}],
            "excluded_ids": ["Premium.us"],
        }
        source = {"name": "fixture", "url": "https://example.org/test.m3u"}
        def test(channel_id, url, **attrs):
            return u.channel_from_entry({"tvg-id": channel_id, **attrs}, "Channel (720p)",
                                        url, source, policy, False)
        c, why = test("Channel.us@SD", "https://news.example.org/live.m3u8")
        self.assertEqual(why, "accepted")
        self.assertEqual(c["id"], "Channel.us")
        self.assertEqual(c["approval"], "host:news.example.org")
        regional, why = test("Channel.us@KERO", "https://news.example.org/kero.m3u8")
        self.assertEqual(why, "accepted")
        self.assertEqual(regional["id"], "Channel.us@KERO")
        self.assertEqual(regional["base_id"], "Channel.us")
        c, why = test("Sports.us", "https://cdn.example.org/sport.m3u8")
        self.assertEqual(c["group"], "Sports")
        self.assertEqual(why, "accepted")
        c, why = test("Premium.us", "https://news.example.org/premium.m3u8")
        self.assertIsNone(c)
        self.assertEqual(why, "excluded_pay_tv")
        c, why = test("Sports.us", "https://cdn.example.org.evil.test/live.m3u8")
        self.assertIsNone(c)
        self.assertEqual(why, "unreviewed_host")
        c, why = test("Channel.ca", "https://news.example.org/live.m3u8")
        self.assertIsNone(c)
        self.assertEqual(why, "not_us_or_no_id")
        c, why = test("Channel.us", "https://news.example.org/live.m3u8", **{"group-title": "VOD USA"})
        self.assertIsNone(c)
        self.assertEqual(why, "on_demand_not_live")
        c, why = test("Channel.us", "https://news.example.org/live.m3u8", **{"tvg-country": "CA"})
        self.assertIsNone(c)
        self.assertEqual(why, "not_us_or_no_id")
        self.assertIsNone(u.approval("Other.us", "evil.cablecast.tv.example", policy))


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.out = base / "generated"
        self.sources = base / "sources.json"
        self.policy = base / "policy.json"
        self.epg = base / "epg.json"
        self.sources.write_text(json.dumps({"sources": [
            {"name": "fixture", "url": "https://example.org/test.m3u", "required": True}]}))
        self.policy.write_text(json.dumps({
            "allowed_hosts": [{"host": "example.org", "evidence_url": "https://example.org/free"}],
            "allowed_host_suffixes": [], "approved_channels": [], "excluded_ids": ["PayTV.us"]
        }))
        self.epg.write_text(json.dumps({
            "header_url": "https://guide.example.org/us.xml",
            "guides": [{"name": "US", "url": "https://guide.example.org/us.xml"}]
        }))
        self.fixture = '''#EXTM3U
#EXTINF:-1 tvg-id="FreeNews.us@SD" group-title="News" tvg-logo="https://example.org/{}",Free News (1080p) [Not 24/7]
https://example.org/free-news.m3u8
#EXTINF:-1 tvg-id="FreeNews.us@HD" group-title="News",Duplicate
https://example.org/free-news-alt.m3u8
#EXTINF:-1 tvg-id="FreeSport.us" group-title="News;Sports",Free Sport
https://example.org/free-sport.m3u8
#EXTINF:-1 tvg-id="PayTV.us",Premium feed
https://example.org/premium.m3u8
#EXTINF:-1 tvg-id="FreeView.us",Web page is not a stream
https://example.org/watch
#EXTINF:-1 tvg-id="NeedHeaders.us",Requires headers
#EXTVLCOPT:http-user-agent=Custom Agent
https://example.org/headers.m3u8
'''.format("a" * 270 + ".png")

    def build(self, fixture=None, **kwargs):
        raw = (fixture if fixture is not None else self.fixture).encode()
        return u.build(sources_path=self.sources, policy_path=self.policy, epg_path=self.epg,
                       out=self.out, min_channels=1, fetcher=lambda source: raw, **kwargs)

    def test_allowed_host_pattern(self):
        policy = json.loads(self.policy.read_text())
        policy["allowed_host_patterns"] = [
            {"pattern": r"^pb-[a-z0-9]+\.akamaized\.net$", "evidence_url": "e", "reason": "test"}
        ]
        self.assertTrue(u.approval("Ch1.us", "pb-abc123xyz.akamaized.net", policy))
        self.assertFalse(u.approval("Ch1.us", "pb-ABC!invalid.akamaized.net", policy))
        self.assertFalse(u.approval("Ch1.us", "other.akamaized.net", policy))
        # build-level: pattern-approved URL survives while plain suffix does not
        fixture = '#EXTM3U\n#EXTINF:-1 tvg-id="Ch1.us",One\nhttps://pb-abc123xyz.akamaized.net/a/manifest.m3u8\n#EXTINF:-1 tvg-id="Ch2.us",Two\nhttps://wild.akamaized.net/b/manifest.m3u8\n'
        self.policy.write_text(json.dumps(policy))
        with contextlib.redirect_stdout(io.StringIO()):
            manifest = self.build(fixture)
        listed = json.loads((self.out / "channels.json").read_text())
        ids = [c["id"] for c in listed]
        self.assertIn("Ch1.us", ids)
        self.assertNotIn("Ch2.us", ids)
        self.assertGreaterEqual(manifest["skipped"]["unreviewed_host"], 1)

    def test_build_outputs_and_idempotence(self):
        report = self.build()
        self.assertEqual(report["counts"]["usa-all.m3u"], 2)
        self.assertEqual(report["counts"]["usa-news.m3u"], 2)
        self.assertEqual(report["counts"]["usa-sports.m3u"], 1)
        self.assertEqual(report["counts"]["usa-intermittent.m3u"], 1)
        self.assertEqual(report["skipped"]["custom_headers"], 1)
        self.assertEqual(report["skipped"]["excluded_pay_tv"], 1)
        text = (self.out / "playlists/usa-all.m3u").read_text()
        lines = text.splitlines()
        self.assertEqual(len(lines), 5)  # header + 2 EXTINF/URL pairs
        self.assertIn('url-tvg="https://guide.example.org/us.xml"', lines[0])
        self.assertIn('tvg-id="FreeNews.us"', text)
        self.assertNotIn("PayTV.us", text)
        self.assertIn('tvg-logo="https://example.org/' + "a" * 270, text)
        self.assertEqual((self.out / "epg/links.txt").read_text().strip(),
                         "https://guide.example.org/us.xml")
        catalog = json.loads((self.out / "channels.json").read_text())
        self.assertEqual({c["id"] for c in catalog}, {"FreeNews.us", "FreeSport.us"})
        self.assertEqual(catalog[0]["evidence_url"], "https://example.org/free")
        snapshot = {p.relative_to(self.out): p.read_bytes() for p in self.out.rglob("*") if p.is_file()}
        self.assertEqual(report, self.build())
        self.assertEqual(snapshot, {p.relative_to(self.out): p.read_bytes()
                                    for p in self.out.rglob("*") if p.is_file()})

    def test_failure_keeps_published_files_intact(self):
        self.build()
        before = (self.out / "playlists/usa-all.m3u").read_bytes()
        with self.assertRaisesRegex(RuntimeError, "required source failed"):
            u.build(sources_path=self.sources, policy_path=self.policy, epg_path=self.epg,
                    out=self.out, min_channels=1,
                    fetcher=lambda _: (_ for _ in ()).throw(OSError("offline")))
        self.assertEqual(before, (self.out / "playlists/usa-all.m3u").read_bytes())
        smaller = '''#EXTM3U
#EXTINF:-1 tvg-id="FreeSport.us" group-title="Sports",Free Sport
https://example.org/free-sport.m3u8
'''
        with self.assertRaisesRegex(RuntimeError, "would shrink"):
            self.build(fixture=smaller)
        self.assertEqual(before, (self.out / "playlists/usa-all.m3u").read_bytes())
        self.assertEqual(self.build(fixture=smaller, allow_shrink=True)["counts"]["usa-all.m3u"], 1)

    def test_platform_source_redirect_cache_name_dedupe_and_multi_guide(self):
        base = Path(self.tmp.name)
        self.epg.write_text(json.dumps({
            "header_url": "https://guide.example.org/us.xml",
            "guides": [{"name": "US", "url": "https://guide.example.org/us.xml"},
                       {"name": "FAST", "url": "https://guide.example.org/fast.xml.gz"}],
        }))
        self.sources.write_text(json.dumps({"sources": [
            {"name": "iptv", "url": "https://example.org/a.m3u", "required": True},
            {"name": "fast", "url": "https://example.org/b.m3u", "required": True,
             "id_style": "platform", "resolve_redirects": True},
        ]}))
        (base / "redirect_cache.json").write_text(json.dumps({
            "https://redirector.example/stvp-1": "https://example.org/other-news.m3u8",
            "https://redirector.example/stvp-2": "https://example.org/fast-sport.m3u8",
        }))
        iptv = '''#EXTM3U
#EXTINF:-1 tvg-id="FreeNews.us" group-title="News",Free News
https://example.org/free-news.m3u8
'''
        fast = '''#EXTM3U
#EXTINF:-1 tvg-id="62ba60f059624e000781c436" group-title="News + Opinion",Free News
https://redirector.example/stvp-1
#EXTINF:-1 tvg-id="98cafb7f4b01848a967fda4bd2225bd7" group-title="Sports & Outdoors",Only FAST
https://redirector.example/stvp-2
#EXTINF:-1 tvg-id="aaaaaaaaaaaaaaaaaaaaaaaa" group-title="Sports",Unresolved FAST
https://redirector.example/stvp-3
'''

        def fetcher(source):
            return (iptv if source["name"] == "iptv" else fast).encode()

        report = u.build(sources_path=self.sources, policy_path=self.policy, epg_path=self.epg,
                         out=self.out, min_channels=1, fetcher=fetcher,
                         redirect_cache_path=base / "redirect_cache.json")
        # Same-name FAST copy dropped, unresolved redirect dropped.
        self.assertEqual(report["counts"]["usa-all.m3u"], 2)
        self.assertEqual(report["skipped"]["duplicate_name"], 1)
        self.assertEqual(report["skipped"]["redirect_unresolved"], 1)
        self.assertEqual(report["counts"]["usa-news.m3u"], 1)
        self.assertEqual(report["counts"]["usa-sports.m3u"], 1)
        header = (self.out / "playlists/usa-all.m3u").read_text().splitlines()[0]
        self.assertIn("https://guide.example.org/us.xml,https://guide.example.org/fast.xml.gz", header)
        text = (self.out / "playlists/usa-all.m3u").read_text()
        self.assertIn('tvg-id="98cafb7f4b01848a967fda4bd2225bd7"', text)
        self.assertNotIn("stvp-1", text)
        self.assertIn("https://example.org/fast-sport.m3u8", text)


class PublishedFileTests(unittest.TestCase):
    def test_committed_playlists_are_well_formed_and_match_manifest(self):
        out = u.ROOT / "generated"
        report = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        catalog = json.loads((out / "channels.json").read_text(encoding="utf-8"))
        self.assertEqual(report["counts"]["usa-all.m3u"], len(catalog))
        guide = report["epg_url"]
        for file, count in report["counts"].items():
            with self.subTest(file=file):
                text = (out / "playlists" / file).read_text(encoding="utf-8")
                lines = text.splitlines()
                self.assertEqual(len(lines), 1 + 2 * count)
                self.assertIn(guide, lines[0])
                entries = list(u.parse_m3u(text))
                self.assertEqual(len(entries), count)
                self.assertEqual(len({url for _, _, url, _ in entries}), count)
                for attrs, name, url, needs_headers in entries:
                    self.assertTrue(u.ID.fullmatch(attrs["tvg-id"])
                                    or u.PLATFORM_ID.fullmatch(attrs["tvg-id"]))
                    self.assertTrue(name)
                    self.assertFalse(needs_headers)
                    self.assertTrue(u.valid_url(url, stream=True))
        links = (out / "epg/links.txt").read_text().splitlines()
        self.assertIn(guide, links)
        self.assertTrue(all(u.valid_url(link) for link in links))


if __name__ == "__main__":
    unittest.main()
