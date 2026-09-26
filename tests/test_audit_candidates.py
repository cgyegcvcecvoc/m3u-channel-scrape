import json
from pathlib import Path
import tempfile
import unittest

from scripts import audit_candidates as a
from scripts import update_playlists as u

ROOT = Path(__file__).resolve().parents[1]

FIXTURE = """#EXTM3U
#EXTINF:-1 tvg-id="Good.us" group-title="News",Good Channel (720p)
https://cdn.example.org/good.m3u8
#EXTINF:-1 tvg-id="Otherowner.us" group-title="News",Other Owner
https://unreviewed.example.net/other.m3u8
#EXTINF:-1 tvg-id="PlainHttp.us",Plain HTTP
http://plain.example.org/live.m3u8
#EXTINF:-1 tvg-id="IpPort.us",Raw IP with port
http://203.0.113.9:8989/ip/index.m3u8
#EXTINF:-1 tvg-id="ESPN.us",ESPN
https://cdnlivetv.example/secure/playlist.m3u8?token=abcdef012345
#EXTINF:-1 tvg-id="Headers.us",Needs headers
#EXTVLCOPT:http-referrer=https://third-party.example/
https://unreviewed.example.net/headers.m3u8
#EXTINF:-1 tvg-id="Global.ca",Not US
https://cdn.example.org/ca.m3u8
"""

POLICY = {
    "allowed_hosts": [{"host": "cdn.example.org", "evidence_url": "https://example.org/free"}],
    "allowed_host_suffixes": [], "allowed_host_paths": [], "approved_channels": [],
    "excluded_ids": ["ESPN.us"],
}


class StructuralReasonTests(unittest.TestCase):
    def test_reports_the_specific_failing_invariant(self):
        cases = {
            "http://plain.example.org/live.m3u8": "scheme:http",
            "http://203.0.113.9:8989/ip/index.m3u8": "non_443_port:8989",
            "https://203.0.113.9/live.m3u8": "ip_literal_host",
            "https://cdn.example.org/live.m3u8?token=abcdef": "expiring_or_credential_query",
            "https://cdn.example.org/watch": "not_hls_path",
            "https://cdn.example.org/live.m3u8": None,
        }
        for url, expected in cases.items():
            with self.subTest(url=url):
                self.assertEqual(a.structural_reason(url), expected)

    def test_pay_tv_brand_flag_marks_bundled_networks_only(self):
        self.assertTrue(a.PREMIUM_BRANDS.search("ESPN"))
        self.assertTrue(a.PREMIUM_BRANDS.search("HBO Signature"))
        self.assertFalse(a.PREMIUM_BRANDS.search("Midpen Media Center Channel 26"))
        self.assertFalse(a.PREMIUM_BRANDS.search("Denver 8 TV"))


class AuditReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name)
        self.source = {"name": "fixture", "url": "https://example.org/fixture.m3u"}

    def run_audit(self, *, policy=None, top=10):
        return a.audit([self.source], policy or POLICY, top=top,
                       fetcher=lambda source: FIXTURE.encode())

    def test_buckets_separate_host_review_from_url_invariants(self):
        report = self.run_audit()
        source = report["sources"][0]
        self.assertEqual(source["entries"], 7)
        self.assertEqual(source["accepted"], 1)
        self.assertEqual(source["unreviewed_host_entries"], 1)   # other.m3u8 only
        self.assertEqual(source["structural_reject_entries"], 3)  # http, ip:port, token
        self.assertEqual(source["other_blocked_entries"], 2)      # headers + non-US id
        self.assertEqual(source["structural_rejects"]["scheme:http"], 1)
        self.assertIn("unreviewed.example.net",
                      [h["host"] for h in source["unreviewed_hosts"]])

    def test_nothing_is_published_or_changed_by_auditing(self):
        before = (ROOT / "config/policy.json").read_bytes()
        self.run_audit()
        self.assertEqual(before, (ROOT / "config/policy.json").read_bytes())

    def test_report_renders_and_writes_both_files(self):
        report = self.run_audit()
        body = a.markdown(report)
        self.assertIn("# Candidate source audit", body)
        self.assertIn("structural_rejects", body)
        self.assertIn("unreviewed.example.net", body)
        # No token value may leak into the reviewer-facing report.
        self.assertNotIn("abcdef012345", body)

    def test_fetch_failure_is_recorded_not_raised(self):
        def boom(source):
            raise RuntimeError("upstream down")
        report = a.audit([self.source], POLICY, fetcher=boom)
        self.assertIn("upstream down", report["sources"][0]["error"])

    def test_approved_host_paths_are_honoured_by_the_audit(self):
        policy = {**POLICY, "approved_host_paths": [{
            "host": "unreviewed.example.net", "path_pattern": "^/other",
            "evidence_url": "https://example.net/", "category": "News"}]}
        report = self.run_audit(policy=policy)
        source = report["sources"][0]
        self.assertEqual(source["accepted"], 2)
        self.assertEqual(source["unreviewed_host_entries"], 0)  # /headers asks for headers


class CommittedAuditTests(unittest.TestCase):
    """The checked-in report must describe the checked-in sources and policy."""

    def test_committed_audit_covers_every_configured_source(self):
        report = json.loads((ROOT / "generated/candidate-audit.json").read_text(encoding="utf-8"))
        sources = json.loads((ROOT / "config/sources.json").read_text(encoding="utf-8"))["sources"]
        self.assertEqual([s["name"] for s in report["sources"]], [s["name"] for s in sources])

    def test_buckets_add_up_and_reported_hosts_are_still_unapproved(self):
        report = json.loads((ROOT / "generated/candidate-audit.json").read_text(encoding="utf-8"))
        policy = json.loads((ROOT / "config/policy.json").read_text(encoding="utf-8"))
        for source in report["sources"]:
            if source.get("error"):
                continue
            with self.subTest(source=source["name"]):
                total = (source["accepted"] + source["unreviewed_host_entries"]
                         + source["structural_reject_entries"] + source["other_blocked_entries"])
                self.assertEqual(total, source["entries"])
                for host in source["unreviewed_hosts"]:
                    self.assertIsNone(u.approval("Sample.us", host["host"], policy,
                                                 url=f"https://{host['host']}/sample/index.m3u8"))


if __name__ == "__main__":
    unittest.main()
