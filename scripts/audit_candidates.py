#!/usr/bin/env python3
"""Audit candidate feeds against the publishing policy, host by host.

`update_playlists.py` answers "what can be published under the current rules".
This script answers the question that comes before it: "what is in each candidate
feed, what did the policy drop, and what would it take to approve more?".

Every entry in every configured source is classified and the blocked ones are
grouped so a human reviewer can work through them:

  structural_rejects  URL fails an invariant that is not negotiable per-entry
                      (plain HTTP, IP-literal host, non-443 port, expiring or
                      credential query string, non-.m3u8 path, web page).
                      These cannot be approved by adding a host rule.
  unreviewed_hosts    URL is direct HTTPS HLS on a shared/CDN host with no
                      evidence on file yet. Each host lists how many entries and
                      distinct channels it would unlock, sample channel names,
                      and whether any sample looks like a pay-TV brand that has
                      no free authorized feed. Host review can approve these.
  other               custom headers, unresolved redirects, dead streams,
                      non-US / missing IDs, exclusions.

Outputs (both regenerated on every run):
  generated/candidate-audit.json   machine-readable per-source report
  generated/candidate-audit.md     reviewer's markdown summary

The report is evidence for host review. It is NOT an approval, and it never
changes policy.json or publishes anything.

Usage:
  python3 scripts/audit_candidates.py                 # all sources
  python3 scripts/audit_candidates.py --source aria   # one source (substring)
  python3 scripts/audit_candidates.py --top 40        # hosts per source
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import sys
from urllib.parse import parse_qsl, urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import update_playlists as u  # noqa: E402

# Brands whose linear networks are sold through pay-TV bundles. A candidate on an
# unreviewed host carrying one of these names is called out in the report so a
# reviewer does not spend time on a restream that can never be published. The
# flag is advisory only: free FAST channels legitimately reuse some brands.
PREMIUM_BRANDS = re.compile(
    r"(?:\b(?:espn(?:\d|u|news|deportes)?|hbo|cinemax|showtime|starz|usa network|fox news|"
    r"fs1|fox sports 1|nba ?tv|nfl network|mlb network|nhl network|big ten network|"
    r"sec network|acc network|longhorn network|disney(?: channel| jr| xd)?|nickelodeon|"
    r"mtv\b|bravo|oxygen|syfy|amc\b|tnt\b|tbs\b|tru ?tv|hln|msnbc|ms now|lifetime|"
    r"food network|hgtv|tlc\b|discovery|history channel|animal planet|paramount network|"
    r"comedy central|\bfx\b|fxx|nat geo|national geographic|\bbet\b|cinemax|epix|"
    r"be ?in sports|dazn|sky sports|viaplay|cbs sports network|golf channel|"
    r"fubo|sling|directv|xfinity|sportsnet|tsn\d?|fox soccer|tudn|universo|telemundo)\b)",
    re.IGNORECASE)

DEAD_CANDIDATE_REASONS = {
    "custom_headers": "stream needs referrer/user-agent overrides",
    "redirect_unresolved": "redirect not in config/redirect_cache.json",
    "dead_stream": "listed in DEFUNCT_STREAMS (known dead)",
    "excluded_pay_tv": "channel ID is on the pay-TV exclusion list",
    "not_us_or_no_id": "no US-style tvg-id (and source is not a platform-ID feed)",
    "on_demand_not_live": "group title marks it as VOD",
    "no_name": "no usable display name",
}


def structural_reason(url: str) -> str | None:
    """Return why a URL fails the direct-HTTPS-HLS invariants, else None.

    Mirrors update_playlists.valid_url(stream=True) but reports the specific
    failing check so the audit can separate fixable host reviews from entries
    that would require weakening a guarantee.
    """
    if not url or len(url) > 2048 or any(c.isspace() or c in '<>"\\' for c in url):
        return "malformed_url"
    if u.CONTROLS.search(url):
        return "malformed_url"
    try:
        parts = urlsplit(url)
        if not parts.hostname or parts.username or parts.password:
            return "malformed_url"
        if parts.port not in (None, 443):
            return f"non_443_port:{parts.port}"
    except ValueError:
        return "malformed_url"
    if parts.scheme != "https":
        return f"scheme:{parts.scheme or 'none'}"
    try:
        ipaddress.ip_address(parts.hostname)
    except ValueError:
        pass
    else:
        return "ip_literal_host"
    if not parts.path.lower().endswith(".m3u8"):
        return "not_hls_path"
    keys = {key.lower() for key, _ in parse_qsl(parts.query)}
    if keys & (u.SECRET_QUERY | u.PARTNER_QUERY):
        # Name the class of query parameter, never its value.
        return "expiring_or_credential_query"
    return None


def entry_attrs(extinf: str) -> tuple[dict, str]:
    """Attributes plus the display name of one #EXTINF line."""
    body = extinf[len("#EXTINF:"):]
    split = u.split_extinf(body)
    if not split:
        return {}, ""
    head, name = split
    return dict(u.ATTRIBUTE.findall(head)), name


def classify(attrs: dict, name: str, url: str, source: dict, policy: dict,
             redirect_cache: dict | None, seen_ids: set[str],
             seen_names: set[str], seen_urls: set[str],
             needs_headers: bool = False) -> tuple[str, str, bool]:
    """Return (bucket, reason, premium_brand) for one entry.

    URL facts are reported before per-entry header requirements: a URL carrying
    an expiring token is a stronger statement about a feed than the fact that
    the entry also asks for a spoofed referrer.
    """
    channel_id = attrs.get("tvg-id", "").partition("@")[0]
    premium = bool(PREMIUM_BRANDS.search(name))
    if url in seen_urls:
        return "other", "duplicate_url", premium
    structural = structural_reason(url)
    if structural and not (redirect_cache and url in redirect_cache):
        if structural == "expiring_or_credential_query" and premium:
            return "structural_rejects", "expiring_or_credential_query(pay_tv_brand)", premium
        return "structural_rejects", structural, premium
    if needs_headers:
        return "other", "custom_headers", premium
    if url in u.DEFUNCT_STREAMS:
        return "other", "dead_stream", premium
    channel, reason = u.channel_from_entry(
        attrs, name, url, source, policy, False,
        id_style=source.get("id_style", "us"), redirect_cache=redirect_cache)
    if channel:
        key = channel["id"].casefold()
        name_key = " ".join(channel["name"].casefold().split())
        if key in seen_ids or name_key in seen_names:
            return "other", "duplicate_of_accepted_channel", premium
        seen_ids.add(key)
        seen_names.add(name_key)
        seen_urls.add(url)
        return "accepted", channel["approval"].split(":")[0], premium
    if reason == "unreviewed_host":
        # Distinguish an entry that would otherwise be publishable from one that
        # only fails on the host rule, so the host review list is honest. Report
        # the host that actually blocks the entry: the updater rewrites known
        # dead URLs first, and a redirect-cache source is resolved before review.
        resolved = u.DEAD_STREAM_REPLACEMENTS.get(url, (redirect_cache or {}).get(url, url))
        host = urlsplit(resolved).hostname or ""
        if source.get("resolve_redirects") and not (redirect_cache or {}).get(url):
            return "other", "redirect_unresolved", premium
        if not channel_id:
            return "other", "not_us_or_no_id", premium
        return "unreviewed_hosts", host, premium
    return "other", reason, premium


def audit(source_files: list[dict], policy: dict, *, top: int = 25,
          fetcher=u.download_source, redirect_cache: dict | None = None,
          sources_path: Path | None = None) -> dict:
    redirect_cache = redirect_cache or {}
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "sources_file": str(sources_path or ROOT / "config/sources.json"),
        "method": "Entries are classified with the same policy code the updater uses "
                  "(scripts/update_playlists.py). This report is evidence for host review, "
                  "not an approval: nothing here publishes or changes policy.json.",
        "note": "structural_rejects cannot be fixed by a host rule (plain HTTP, IP-literal "
                "host, non-443 port, expiring/credential query, non-HLS path). "
                "unreviewed_hosts can be approved after a host review with evidence.",
        "sources": [],
    }
    totals: Counter[str] = Counter()
    for source in source_files:
        result = {"name": source["name"], "url": source["url"]}
        try:
            raw = fetcher(source)
            entries = list(u.parse_m3u(raw.decode("utf-8-sig", errors="replace")))
        except (OSError, ValueError, RuntimeError, UnicodeError) as exc:
            result["error"] = str(exc)[:200]
            report["sources"].append(result)
            continue
        cache = redirect_cache if source.get("resolve_redirects") else None
        buckets: Counter[str] = Counter()
        hosts: dict[str, dict] = defaultdict(lambda: {"entries": 0, "channels": set(),
                                                      "samples": [], "premium": 0})
        structural: Counter[str] = Counter()
        other: Counter[str] = Counter()
        accepted_ids: set[str] = set()
        seen_names: set[str] = set()
        seen_urls: set[str] = set()
        premium_total = 0
        header_entries = 0
        for attrs, name, url, needs_headers in entries:
            name = u.cleaned(name)
            header_entries += bool(needs_headers)
            bucket, reason, premium = classify(attrs, name, url, source, policy, cache,
                                               accepted_ids, seen_names, seen_urls,
                                               needs_headers=needs_headers)
            premium_total += premium
            buckets[bucket] += 1
            if bucket == "unreviewed_hosts":
                info = hosts[reason]
                info["entries"] += 1
                info["channels"].add(name or attrs.get("tvg-id", ""))
                if premium:
                    info["premium"] += 1
                if len(info["samples"]) < 6 and name:
                    info["samples"].append(name)
            elif bucket == "structural_rejects":
                structural[reason] += 1
            elif bucket == "other":
                other[reason] += 1
        result.update({
            "sha256": hashlib.sha256(raw).hexdigest(),
            "entries": len(entries),
            "accepted": buckets["accepted"],
            "unreviewed_host_entries": buckets["unreviewed_hosts"],
            "structural_reject_entries": buckets["structural_rejects"],
            "other_blocked_entries": buckets["other"],
            "entries_with_pay_tv_brand_name": premium_total,
            "entries_needing_custom_headers": header_entries,
            "structural_rejects": dict(structural.most_common()),
            "other_reasons": {k: v for k, v in other.most_common()},
            "other_reason_notes": {k: DEAD_CANDIDATE_REASONS[k]
                                   for k in other if k in DEAD_CANDIDATE_REASONS},
            "unreviewed_hosts": [
                {"host": host, "entries": info["entries"],
                 "distinct_channel_names": len(info["channels"]),
                 "pay_tv_brand_samples": info["premium"],
                 "samples": sorted(info["channels"])[:6]}
                for host, info in sorted(hosts.items(),
                                         key=lambda kv: (-kv[1]["entries"], kv[0]))[:top]
            ],
        })
        result["review_checklist"] = [
            f"confirm {h['host']} is a publisher/CDN used by the named channels "
            f"(evidence URL required) before adding a host rule"
            for h in result["unreviewed_hosts"] if not h["pay_tv_brand_samples"]
        ][:top]
        totals["sources"] += 1
        totals["entries"] += len(entries)
        totals["accepted"] += result["accepted"]
        totals["unreviewed_host_entries"] += result["unreviewed_host_entries"]
        totals["structural_reject_entries"] += result["structural_reject_entries"]
        totals["other_blocked_entries"] += result["other_blocked_entries"]
        report["sources"].append(result)
    report["totals"] = dict(totals)
    return report


def markdown(report: dict) -> str:
    lines = [
        "# Candidate source audit",
        "",
        f"Generated: `{report['generated_utc']}`",
        "",
        report["method"],
        "",
        "> " + report["note"],
        "",
        f"**Totals:** {report['totals'].get('entries', 0)} candidate entries; "
        f"{report['totals'].get('accepted', 0)} publishable under the current policy; "
        f"{report['totals'].get('unreviewed_host_entries', 0)} blocked only by an unreviewed host; "
        f"{report['totals'].get('structural_reject_entries', 0)} fail URL invariants; "
        f"{report['totals'].get('other_blocked_entries', 0)} blocked for other reasons.",
        "",
    ]
    for source in report["sources"]:
        lines += [f"## {source['name']}", ""]
        if source.get("error"):
            lines += [f"Fetch failed: `{source['error']}`", ""]
            continue
        lines += [
            f"- entries: **{source['entries']}** (sha256 `{source['sha256'][:16]}…`)",
            f"- publishable now: **{source['accepted']}**",
            f"- blocked only by host review: **{source['unreviewed_host_entries']}**",
            f"- URL invariant failures: **{source['structural_reject_entries']}** "
            f"`{json.dumps(source['structural_rejects'])}`",
            f"- other reasons: `{json.dumps(source['other_reasons'])}`",
            f"- entries whose name matches a pay-TV brand: {source['entries_with_pay_tv_brand_name']}",
            f"- entries that ask for spoofed `#EXTVLCOPT`/`#KODIPROP` headers: "
            f"{source.get('entries_needing_custom_headers', 0)}",
            "",
        ]
        if source["unreviewed_hosts"]:
            lines += [f"### Unreviewed hosts ({source['name']})", "",
                      "| host | entries | distinct names | pay-TV-brand samples | samples |",
                      "| --- | ---: | ---: | ---: | --- |"]
            for host in source["unreviewed_hosts"]:
                samples = "<br>".join(u.cleaned(s)[:48] for s in host["samples"][:4])
                lines.append(f"| `{host['host']}` | {host['entries']} | "
                             f"{host['distinct_channel_names']} | {host['pay_tv_brand_samples']} | "
                             f"{samples} |")
            lines.append("")
        if source["other_reason_notes"]:
            lines += ["Other blocker explanations:", ""]
            lines += [f"- `{k}` — {v}" for k, v in source["other_reason_notes"].items()]
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sources", type=Path, default=ROOT / "config/sources.json")
    parser.add_argument("--policy", type=Path, default=ROOT / "config/policy.json")
    parser.add_argument("--out", type=Path, default=ROOT / "generated")
    parser.add_argument("--source", default="",
                        help="only audit sources whose name contains this text")
    parser.add_argument("--top", type=int, default=25, help="hosts to report per source")
    parser.add_argument("--stdout", action="store_true", help="print the report, write nothing")
    args = parser.parse_args()
    sources = json.loads(args.sources.read_text(encoding="utf-8"))["sources"]
    if args.source:
        needle = args.source.casefold()
        sources = [s for s in sources if needle in s["name"].casefold()]
        if not sources:
            print(f"No configured source matches {args.source!r}", file=sys.stderr)
            return 1
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    try:
        redirect_cache = json.loads(
            (ROOT / "config/redirect_cache.json").read_text(encoding="utf-8"))
        if not isinstance(redirect_cache, dict):
            redirect_cache = {}
    except (OSError, ValueError):
        redirect_cache = {}
    report = audit(sources, policy, top=args.top, redirect_cache=redirect_cache,
                   sources_path=args.sources)
    body = markdown(report)
    if args.stdout:
        print(body)
        return 0
    u.atomic_write(args.out / "candidate-audit.json",
                   u.json_bytes(report))
    u.atomic_write(args.out / "candidate-audit.md", body.encode("utf-8"))
    print(f"Audited {report['totals'].get('entries', 0)} entries from "
          f"{report['totals'].get('sources', 0)} sources")
    for source in report["sources"]:
        if source.get("error"):
            print(f"  {source['name']}: FETCH FAILED ({source['error'][:80]})")
            continue
        print(f"  {source['name']}: {source['entries']} entries, "
              f"{source['accepted']} publishable, "
              f"{source['unreviewed_host_entries']} host-review candidates, "
              f"{source['structural_reject_entries']} URL rejects")
    print(f"Wrote {args.out / 'candidate-audit.json'} and {args.out / 'candidate-audit.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
