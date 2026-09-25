#!/usr/bin/env python3
"""Refresh reviewed, free-to-view US HLS playlists. Python 3.10+, stdlib only.

Candidate feeds are NOT an authorization check. Only pre-reviewed publisher/FAST/
public-access hosts (or a specific channel ID + host) can reach generated files.
Unknown feeds are rejected, not automatically promoted by an HTTP 200 response.
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import parse_qsl, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
MAX_DOWNLOAD = 8 * 1024 * 1024
ATTRIBUTE = re.compile(r'(tvg-id|tvg-name|tvg-logo|tvg-country|tvg-chno|group-title)="([^"]*)"')
ID = re.compile(r"^[A-Za-z0-9_.-]+\.us(?:@[A-Za-z0-9_-]+)?$", re.IGNORECASE)
# Country-filtered FAST sources (Pluto TV US, Samsung TV Plus US, Roku) identify
# channels by their own platform IDs: 24-32 hex slugs or Samsung "US"-prefixed
# service IDs. Only accepted for sources flagged id_style=platform, whose EPGs
# (i.mjh.nz) key on the same IDs.
PLATFORM_ID = re.compile(r"^(?:[0-9a-f]{24,32}|US[A-Z0-9]{6,24})$", re.IGNORECASE)
QUALITY_FEEDS = {"sd", "hd", "fhd", "uhd", "4k", "8k", "2160p", "1080p", "720p", "480p", "360p"}
QUALITY = re.compile(r"\s+\((?:\d{3,4}p|4K)\)(?=\s|$)", re.IGNORECASE)
CONTROLS = re.compile(r"[\x00-\x1f\x7f]")
LOCAL_STATIONS = re.compile(r"^(?:ABC|CBS|NBC|FOX)\s+[KW][A-Z0-9-]{2,}", re.IGNORECASE)
SECRET_QUERY = {"token", "auth", "authorization", "password", "pass", "key",
                "api_key", "sig", "signature", "expires", "exp", "access_token", "authtoken"}
PARTNER_QUERY = {"deviceid", "devicemodel", "deviceversion", "devicetype", "devicemake",
                 "advertisingid", "embedpartner", "appname", "appversion"}
CATEGORIES = ("Sports", "News", "Movies", "Entertainment", "Kids", "Music",
              "Documentary", "Education", "Legislative", "Weather", "Business",
              "Spanish", "General")
# FAST platforms ship free-form group titles ("News + Opinion", "Sports &
# Outdoors", "En Español"...). Map them onto the categories above; exact
# category names always pass through unchanged.
GROUP_RULES = (
    (("sport", "motorsport"), "Sports"),
    (("news",), "News"),
    (("movie", "film"), "Movies"),
    (("kid", "family", "children"), "Kids"),
    (("music",), "Music"),
    (("weather",), "Weather"),
    (("business", "finance", "invest"), "Business"),
    (("document", "nature", "history", "science", "animal", "wildlife"), "Documentary"),
    (("español", "espanol", "spanish", "latino"), "Spanish"),
    (("educat", "learning", "school"), "Education"),
    (("legislat", "government", "civic", "council", "city hall", "public access",
      "municipal", "community media"), "Legislative"),
    (("entertain", "comedy", "drama", "reality", "classic", "lifestyle", "game",
      "daytime", "home", "food", "cook", "crime", "reality tv", "tv &"), "Entertainment"),
)


def canonical_group(raw: str) -> str:
    """Translate a source group title into one of CATEGORIES (fallback General)."""
    if raw in CATEGORIES:
        return raw
    lowered = raw.casefold()
    for keys, category in GROUP_RULES:
        if any(key in lowered for key in keys):
            return category
    return "General"


def cleaned(value: str, *, limit: int = 240) -> str:
    """Remove playlist control/quote injection; preserve Unicode channel names."""
    return " ".join(CONTROLS.sub(" ", value.replace('"', "")).split())[:limit]


def valid_url(value: str, *, stream: bool = False) -> bool:
    """No credentials, private/bare IPs, HTTP, expiring signed URLs or web pages."""
    if not value or len(value) > 2048 or any(c.isspace() or c in '<>"\\' for c in value):
        return False
    if CONTROLS.search(value):
        return False
    try:
        parts = urlsplit(value)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
            return False
        if parts.port not in (None, 443):
            return False
    except ValueError:  # malformed port, IPv6 brackets, etc.
        return False
    try:
        ipaddress.ip_address(parts.hostname)  # reject IP literals, even public ones
    except ValueError:
        pass  # a DNS host
    else:
        return False
    if stream:
        if not parts.path.lower().endswith(".m3u8"):
            return False
        if any(key.lower() in SECRET_QUERY | PARTNER_QUERY for key, _ in parse_qsl(parts.query)):
            return False
    return True


def split_extinf(text: str) -> tuple[str, str] | None:
    """Split EXTINF at the first comma outside quotes (logos/UA may contain commas)."""
    quoted = False
    for index, char in enumerate(text):
        if char == '"':
            quoted = not quoted
        if char == "," and not quoted:
            return text[:index], text[index + 1:]
    return None


def parse_m3u(text: str):
    """Yield (attributes, display name, URL, needs_custom_headers).

    A metadata directive between #EXTINF and the URL is not itself a URL. Streams
    needing referrer/user-agent overrides are skipped rather than bypassing gates.
    """
    if not text.lstrip("\ufeff \t\r\n").startswith("#EXTM3U"):
        raise ValueError("upstream is not an extended M3U playlist")
    pending = None
    headers = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#EXTINF:"):
            parts = split_extinf(line[len("#EXTINF:"):])
            pending = (dict(ATTRIBUTE.findall(parts[0])), parts[1]) if parts else None
            headers = False
        elif line.startswith(("#EXTVLCOPT:", "#KODIPROP:", "#EXTHTTP:")):
            headers = True
        elif line.startswith("#") or not line:
            continue
        else:
            if pending:
                attrs, name = pending
                yield attrs, name, line, headers
            pending = None
            headers = False


def fetch_bytes(url: str, *, github_api: bool = False) -> bytes:
    if not valid_url(url):
        raise ValueError("invalid source URL (must be HTTPS to a DNS host)")
    headers = {"User-Agent": "m3u-channel-scrape/1.0 (public playlist updater)",
               "Accept": "application/vnd.github+json" if github_api else "*/*"}
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if github_api and urlsplit(url).hostname == "api.github.com" and token:
        headers["Authorization"] = f"Bearer {token}"
    with urlopen(Request(url, headers=headers), timeout=25) as response:
        data = response.read(MAX_DOWNLOAD + 1)
    if len(data) > MAX_DOWNLOAD:
        raise ValueError("source exceeds 8 MiB limit")
    if github_api:
        blob = json.loads(data)
        if blob.get("encoding") != "base64" or not blob.get("content"):
            # The contents API omits content for large files; use the blob API.
            git_url = blob.get("git_url") if isinstance(blob, dict) else None
            if (not git_url or not valid_url(git_url)
                    or urlsplit(git_url).hostname != "api.github.com"):
                raise ValueError("GitHub contents API did not supply base64 data")
            with urlopen(Request(git_url, headers=headers), timeout=25) as response:
                blob = json.loads(response.read(MAX_DOWNLOAD + 1))
            if blob.get("encoding") != "base64" or not blob.get("content"):
                raise ValueError("GitHub blob API did not supply base64 data")
        data = base64.b64decode(blob["content"])
        if len(data) > MAX_DOWNLOAD:
            raise ValueError("decoded source exceeds 8 MiB limit")
    return data


def download_source(source: dict) -> bytes:
    """GitHub's contents API is a fallback if GitHub Pages/raw CDN is blocked."""
    def checked(data: bytes) -> bytes:
        if not data.decode("utf-8-sig", errors="replace").lstrip().startswith("#EXTM3U"):
            raise ValueError("upstream returned HTML/JSON instead of M3U")
        return data

    try:
        return checked(fetch_bytes(source["url"]))
    except (OSError, ValueError, json.JSONDecodeError) as first:
        if not source.get("github_api_fallback"):
            raise RuntimeError(f"{source['name']}: {first}") from first
        try:
            return checked(fetch_bytes(source["github_api_fallback"], github_api=True))
        except (OSError, ValueError, json.JSONDecodeError) as second:
            raise RuntimeError(f"{source['name']}: primary: {first}; fallback: {second}") from second


def approval(channel_id: str, host: str, policy: dict) -> tuple[str, str] | None:
    for rule in policy["allowed_hosts"]:
        if host == rule["host"]:
            return ("host:" + host, rule["evidence_url"])
    for rule in policy.get("allowed_host_patterns", ()):
        if re.fullmatch(rule["pattern"], host):
            return ("pattern:" + rule["pattern"], rule["evidence_url"])
    for rule in policy["allowed_host_suffixes"]:
        if host.endswith(rule["suffix"]):
            return ("suffix:" + rule["suffix"], rule["evidence_url"])
    for rule in policy["approved_channels"]:
        if channel_id.casefold() == rule["id"].casefold() and host in rule["hosts"]:
            return ("id+host:" + rule["id"], rule["evidence_url"])
    return None


def channel_from_entry(attrs: dict, raw_name: str, url: str, source: dict, policy: dict,
                       requires_headers: bool, *, id_style: str = "us",
                       redirect_cache: dict | None = None) -> tuple[dict | None, str]:
    if requires_headers:
        return None, "custom_headers"
    raw_id = attrs.get("tvg-id", "")
    valid_id = ID.fullmatch(raw_id)
    if id_style == "platform" and not valid_id:
        valid_id = PLATFORM_ID.fullmatch(raw_id)
    if len(raw_id) > 128 or not valid_id:
        return None, "not_us_or_no_id"
    channel_id, _, feed_id = raw_id.partition("@")
    # Discard only quality labels and the nationwide @US marker. @KERO/@East
    # are distinct regional feeds; replacing them with ABC.us could assign
    # the WRONG EPG schedule. @US is the no-region feed used for generic
    # FAST/series ids (DogtheBountyHunter.us@US -> DogtheBountyHunter.us).
    tvg_id = channel_id if (feed_id.lower() in QUALITY_FEEDS
                            or feed_id.lower() == "us") else raw_id
    country = attrs.get("tvg-country", "")
    if country and "US" not in re.split(r"[,;/ ]+", country.upper()):
        return None, "not_us_or_no_id"
    if channel_id.casefold() in {x.casefold() for x in policy["excluded_ids"]}:
        return None, "excluded_pay_tv"
    if redirect_cache is not None:
        # Sources flagged resolve_redirects publish redirector URLs (e.g.
        # jmp2.uk/stvp-...) that are only usable after one-time resolution;
        # an unresolved entry is skipped rather than shipped broken.
        url = redirect_cache.get(url, "")
        if not url:
            return None, "redirect_unresolved"
    if not valid_url(url, stream=True):
        return None, "not_direct_https_hls"
    host = urlsplit(url).hostname or ""
    approved = approval(channel_id, host, policy)
    if not approved:
        return None, "unreviewed_host"
    name = cleaned(raw_name)
    name = QUALITY.sub("", name).strip()
    geo = "[Geo-blocked]" in name or "Ⓖ" in name
    intermittent = "[Not 24/7]" in name
    name = re.sub(r"\s*[ⓈⓉⓎⒼ]\s*", " ", name).strip()
    if geo and "[Geo-blocked]" not in name:
        name += " [Geo-restricted]"
    if not name:
        return None, "no_name"
    groups = [cleaned(g) for g in re.split(r"[;,]", attrs.get("group-title", ""))]
    if any("vod" in g.casefold() for g in groups):
        return None, "on_demand_not_live"
    groups = [canonical_group(g) for g in groups
              if g and g.casefold() not in ("usa", "us", "united states")]
    groups = list(dict.fromkeys(groups))
    for rule in policy["approved_channels"]:
        if channel_id.casefold() == rule["id"].casefold() and host in rule["hosts"]:
            groups = list(dict.fromkeys([rule["category"], *groups]))
            break
    if not groups:
        groups = (["News"] if "News" in name or "Reuters" in name else
                  ["Sports"] if "Sports" in name else ["General"])
    category = next((c for c in CATEGORIES if c in groups), "General")
    logo = attrs.get("tvg-logo", "")
    logo = logo if valid_url(logo) and len(logo) <= 1000 else ""
    local = (host.endswith(".cablecast.tv") or host in
             {"livestream.telvue.com", "edge-f.swagit.com", "stream.swagit.com",
              "video.oct.dc.gov", "video.ct-n.com"} or
             bool(LOCAL_STATIONS.match(name)) or
             (name.startswith("CBS News ") and name != "CBS News 24/7"))
    return {
        "id": tvg_id, "base_id": channel_id, "name": name, "url": url, "logo": logo,
        "group": category, "categories": groups, "country": "US", "local": local,
        "not_24_7": intermittent, "geo_restricted": geo,
        "source": source["name"], "source_url": source["url"],
        "approval": approved[0], "evidence_url": approved[1]
    }, "accepted"


def m3u(channels: list[dict], guides: list[str]) -> bytes:
    joined = ",".join(guides)
    header = f'#EXTM3U url-tvg="{joined}" x-tvg-url="{joined}"'
    lines = [header]
    for c in channels:
        lines.extend([
            '#EXTINF:-1 tvg-id="{}" tvg-name="{}" tvg-logo="{}" group-title="{}",{}'.format(
                cleaned(c["id"]), cleaned(c["name"]), cleaned(c["logo"], limit=1000),
                cleaned(c["group"]), cleaned(c["name"])),
            c["url"],
        ])
    return ("\n".join(lines) + "\n").encode("utf-8")


def json_bytes(obj) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".update-", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(content)
        os.replace(tmp_path, path)
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def build(*, sources_path: Path = ROOT / "config/sources.json",
          policy_path: Path = ROOT / "config/policy.json",
          epg_path: Path = ROOT / "config/epg.json",
          out: Path = ROOT / "generated", min_channels: int = 50,
          allow_shrink: bool = False, fetcher=download_source,
          redirect_cache_path: Path = ROOT / "config/redirect_cache.json") -> dict:
    sources = json.loads(sources_path.read_text(encoding="utf-8"))["sources"]
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    epg = json.loads(epg_path.read_text(encoding="utf-8"))
    guide = epg["header_url"]
    if not valid_url(guide) or not guide.endswith((".xml", ".xml.gz")):
        raise ValueError("EPG header URL must be an HTTPS XMLTV link")
    if (not epg.get("guides") or guide not in [item["url"] for item in epg["guides"]] or
            any(not valid_url(item["url"]) or not item["url"].endswith((".xml", ".xml.gz"))
                for item in epg["guides"])):
        raise ValueError("EPG guides must be HTTPS XMLTV URLs and include the header link")
    if not sources:
        raise ValueError("no configured playlist sources")
    try:
        redirect_cache = json.loads(redirect_cache_path.read_text(encoding="utf-8"))
        if not isinstance(redirect_cache, dict):
            raise ValueError("redirect cache must be a JSON object")
    except FileNotFoundError:
        redirect_cache = {}
    except (OSError, ValueError):
        redirect_cache = {}
    candidates: list[dict] = []
    skipped: Counter[str] = Counter()
    source_results = []
    for source in sources:
        try:
            raw = fetcher(source)
            entries = list(parse_m3u(raw.decode("utf-8-sig", errors="replace")))
        except (OSError, ValueError, RuntimeError, UnicodeError) as exc:
            if source.get("required", True):
                raise RuntimeError(f"required source failed ({source['name']}): {exc}") from exc
            source_results.append({"name": source["name"], "error": str(exc)[:160]})
            continue
        accepted = 0
        cache = redirect_cache if source.get("resolve_redirects") else None
        for attrs, name, url, needs_headers in entries:
            channel, reason = channel_from_entry(
                attrs, name, url, source, policy, needs_headers,
                id_style=source.get("id_style", "us"), redirect_cache=cache)
            if channel:
                candidates.append(channel)
                accepted += 1
            else:
                skipped[reason] += 1
        source_results.append({"name": source["name"], "url": source["url"],
                               "sha256": hashlib.sha256(raw).hexdigest(),
                               "candidates": len(entries), "approved_candidates": accepted})
    # Prefer earlier (US-specific) sources; one stream/EPG ID, one URL, one
    # listing per channel name (FAST platforms repeat the same channel names).
    by_id = {}
    seen_urls = set()
    seen_names = set()
    for c in candidates:
        name_key = " ".join(c["name"].casefold().split())
        if c["id"].casefold() in by_id or c["url"] in seen_urls:
            skipped["duplicate"] += 1
            continue
        if name_key in seen_names:
            skipped["duplicate_name"] += 1
            continue
        by_id[c["id"].casefold()] = c
        seen_urls.add(c["url"])
        seen_names.add(name_key)
    channels = sorted(by_id.values(), key=lambda c: (c["name"].casefold(), c["id"].casefold()))
    if len(channels) < min_channels:
        raise RuntimeError(f"only {len(channels)} channels approved (minimum {min_channels}); previous files untouched")
    previous = {}
    try:
        previous = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    old_count = previous.get("counts", {}).get("usa-all.m3u", 0)
    if old_count and len(channels) < math.ceil(old_count * 0.6) and not allow_shrink:
        raise RuntimeError(f"would shrink playlist from {old_count} to {len(channels)}; "
                           "investigate the source/policy or explicitly use --allow-shrink")
    files = {
        "usa-all.m3u": channels,
        "usa-news.m3u": [c for c in channels if "News" in c["categories"]],
        "usa-sports.m3u": [c for c in channels if "Sports" in c["categories"]],
        "usa-local.m3u": [c for c in channels if c["local"]],
        "usa-movies.m3u": [c for c in channels if "Movies" in c["categories"]],
        "usa-entertainment.m3u": [c for c in channels if "Entertainment" in c["categories"]],
        "usa-kids.m3u": [c for c in channels if "Kids" in c["categories"]],
        "usa-music.m3u": [c for c in channels if "Music" in c["categories"]],
        "usa-weather.m3u": [c for c in channels if "Weather" in c["categories"]],
        "usa-business.m3u": [c for c in channels if "Business" in c["categories"]],
        "usa-spanish.m3u": [c for c in channels if "Spanish" in c["categories"]],
        "usa-intermittent.m3u": [c for c in channels if c["not_24_7"]],
    }
    guide_urls = [guide] + [g["url"] for g in epg["guides"] if g["url"] != guide]
    payloads = {"playlists/" + name: m3u(items, guide_urls) for name, items in files.items()}
    payloads["channels.json"] = json_bytes(channels)  # provenance for every listed URL
    payloads["epg/links.json"] = json_bytes(epg)
    payloads["epg/links.txt"] = ("\n".join(g["url"] for g in epg["guides"]) + "\n").encode()
    counts = {name: len(items) for name, items in files.items()}
    manifest_without_date = {
        "counts": counts, "sources": source_results, "skipped": dict(sorted(skipped.items())),
        "epg_url": guide, "epg_urls": guide_urls,
        "stream_probe": "not performed at build time; run scripts/verify_channels.py "
                        "(Verify workflow) for point-in-time playback evidence in "
                        "generated/verification.json",
    }
    prev_without_date = {k: v for k, v in previous.items() if k != "generated_utc"}
    unchanged_files = all((out / name).is_file() and (out / name).read_bytes() == body
                          for name, body in payloads.items())
    if unchanged_files and prev_without_date == manifest_without_date:
        generated = previous["generated_utc"]
    else:
        generated = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    manifest = {"generated_utc": generated, **manifest_without_date}
    payloads["manifest.json"] = json_bytes(manifest)
    # All network/parsing/policy/size checks above finish before touching published files.
    for name, body in payloads.items():
        destination = out / name
        if not destination.exists() or destination.read_bytes() != body:
            atomic_write(destination, body)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "generated")
    parser.add_argument("--min-channels", type=int, default=50)
    parser.add_argument("--allow-shrink", action="store_true",
                        help="allow a >40% decline after investigating upstream or policy changes")
    args = parser.parse_args()
    try:
        report = build(out=args.out, min_channels=args.min_channels, allow_shrink=args.allow_shrink)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Update failed: {exc}", file=sys.stderr)
        return 1
    print("Generated:", report["generated_utc"])
    for name, count in report["counts"].items():
        print(f"  {name}: {count}")
    # Keep the root convenience copy (the file opened most often on GitHub)
    # byte-identical with the reviewed catalog playlist.
    root_copy = ROOT / "usa-all.m3u"
    generated_copy = args.out / "playlists" / "usa-all.m3u"
    if generated_copy.is_file():
        body = generated_copy.read_bytes()
        if not root_copy.is_file() or root_copy.read_bytes() != body:
            atomic_write(root_copy, body)
            print("  synced root usa-all.m3u")
    print("Playlist URLs have NOT been live-probed here; only reviewed/free-viewing "
          "host rules were applied. generated/verification.json carries any "
          "point-in-time probe results from the Verify workflow.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
