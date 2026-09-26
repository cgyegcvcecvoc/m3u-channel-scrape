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
              "Spanish", "General", "Backups")
# FAST platforms ship free-form group titles ("News + Opinion", "Sports &
# Outdoors", "En Español"...). Map them onto the categories above; exact
# category names always pass through unchanged.
GROUP_RULES = (
    (("backup", "backups", "alternate"), "Backups"),
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

# Known dead / 404 / DNS-failed streams mapped directly to verified working live feeds
DEAD_STREAM_REPLACEMENTS: dict[str, str] = {
    # CBS News national and regional feeds (old akamaized / cbsnstream 404 -> working Pluto TV feeds)
    "https://cbsnews.akamaized.net/hls/live/2020607/cbsnlineup_8/master.m3u8": "https://jmp2.uk/plu-5a6b92f6e22a617379789618.m3u8",
    "https://cbsn-sf.cbsnstream.cbsnews.com/out/v1/dac63c1abb3f4a2dac9f508f44bb072a/master.m3u8": "https://jmp2.uk/plu-5eb1afb21486df0007abc57c.m3u8",
    "https://cbsn-bos.cbsnstream.cbsnews.com/out/v1/589d66ec6eb8434c96c28de0370d1326/master.m3u8": "https://jmp2.uk/plu-5eb1af2ad345340008fccd1e.m3u8",
    "https://cbsn-chi.cbsnstream.cbsnews.com/out/v1/b2fc0d5715d54908adf07f97d2616646/master.m3u8": "https://jmp2.uk/plu-5eb1aeb2fd4b8a00076c2047.m3u8",
    "https://cbsn-den.cbsnstream.cbsnews.com/out/v1/2e49baf2906244ecb01b07d9885fbe7a/master.m3u8": "https://jmp2.uk/plu-5eb1b12146cba40007aa7e5d.m3u8",
    "https://cbsn-det.cbsnstream.cbsnews.com/out/v1/169f5c001bc74fa7a179b19c20fea069/master.m3u8": "https://jmp2.uk/plu-634f2610d5023700078f7dee.m3u8",
    "https://cbsn-la.cbsnstream.cbsnews.com/out/v1/57b6c4534a164accb6b1872b501e0028/master.m3u8": "https://jmp2.uk/plu-5dc481cda1d430000948a1b4.m3u8",
    "https://cbsn-min.cbsnstream.cbsnews.com/out/v1/76518f06941246ba810c8d175600bf74/master.m3u8": "https://jmp2.uk/plu-5eb1b0bf2240d8000732a09c.m3u8",
    "https://cbsn-ny.cbsnstream.cbsnews.com/out/v1/ec3897d58a9b45129a77d67aa247d136/master.m3u8": "https://jmp2.uk/plu-5dc48170e280c80009a861ab.m3u8",
    "https://cbsn-phi.cbsnstream.cbsnews.com/out/v1/5c9ad3e215984b0e9ad845b335216b72/master.m3u8": "https://jmp2.uk/plu-5eb1b03cd345340008fccd28.m3u8",
    "https://cbsn-pit.cbsnstream.cbsnews.com/out/v1/6966dabf8150405ab26f854e3cd6a2b8/master.m3u8": "https://jmp2.uk/plu-5eb1b199042b3100076fe931.m3u8",
    # The Bob Ross Channel (dead tubi.video 404 -> working Pluto TV embed)
    "https://aegis-cloudfront-1.tubi.video/45301c94-0d40-4cbb-b342-f5dc7949d76c/playlist.m3u8": "https://jmp2.uk/plu-5f36d726234ce10007784f2a.m3u8",
    # Baywatch (dead AU amagi dns failure -> working Roku Channel embed)
    "https://amg00145-fremantlemedian-baywatch-samsungau-gtsd6.amagi.tv/playlist/amg00145-fremantlemedian-baywatch-samsungau/playlist.m3u8": "https://jmp2.uk/rok-ab47c5037be851e6a929a4d09daafeac.m3u8",
    # Vevo channels (dead AU / stale regional CDNs -> verified US Pluto TV feeds)
    "https://d1s6jz7jeei17.cloudfront.net/playlist/amg00056-vevotv-vevo2kau-samsungau/playlist.m3u8": "https://jmp2.uk/plu-5fd7bca3e0a4ee0007a38e8c.m3u8",
    "https://d128y56w6v2kax.cloudfront.net/playlist/amg00056-vevotv-vevopopau-samsungau/playlist.m3u8": "https://jmp2.uk/plu-5d93b635b43dd1a399b39eee.m3u8",
    "https://amg00056-vevotv-vevo70saunz-samsungau-xzszd.amagi.tv/playlist/amg00056-vevotv-vevo70saunz-samsungau/playlist.m3u8": "https://jmp2.uk/plu-5f32f26bcd8aea00071240e5.m3u8",
    "https://amg00056-vevotv-vevo80saunz-samsungau-rp5e3.amagi.tv/playlist/amg00056-vevotv-vevo80saunz-samsungau/playlist.m3u8": "https://jmp2.uk/plu-5fd7b8bf927e090007685853.m3u8",
    "https://amg00056-vevotv-vevo90saunz-samsungau-n6a0d.amagi.tv/playlist/amg00056-vevotv-vevo90saunz-samsungau/playlist.m3u8": "https://jmp2.uk/plu-5fd7bb1f86d94a000796e2c2.m3u8",
    "https://amg00056-vevotv-vevocountryau-samsungau-ktmqm.amagi.tv/playlist/amg00056-vevotv-vevocountryau-samsungau/playlist.m3u8": "https://jmp2.uk/plu-5da0d75e84830900098a1ea0.m3u8",
    # The Hill TV (dead amagi dns failure -> working Samsung TV Plus embed)
    "https://amg01312-cw-amg01312c15-firetv-us-3444.playouts.now.amagi.tv/playlist.m3u8": "https://jmp2.uk/stvp-US3300008FX",
    # Transformers TV (dead Pluto slug 404 -> working Samsung TV Plus embed)
    "https://jmp2.uk/plu-60fb053712f22a0007ff14d2.m3u8": "https://jmp2.uk/stvp-US29000168D",
    # ABC News Live obsolete regional feeds (404 -> working Pluto TV ABC News Live)
    "https://abcnews-streams.akamaized.net/hls/live/2023560/abcnewshudson1/master.m3u8": "https://jmp2.uk/plu-6508be683a0d700008c534e4.m3u8",
    "https://abcnews-streams.akamaized.net/hls/live/2023561/abcnewshudson2/master.m3u8": "https://jmp2.uk/plu-6508be683a0d700008c534e4.m3u8",
    "https://abcnews-streams.akamaized.net/hls/live/2023562/abcnewshudson3/master.m3u8": "https://jmp2.uk/plu-6508be683a0d700008c534e4.m3u8",
    "https://abcnews-streams.akamaized.net/hls/live/2023563/abcnewshudson4/master.m3u8": "https://jmp2.uk/plu-6508be683a0d700008c534e4.m3u8",
    "https://abcnews-streams.akamaized.net/hls/live/2023564/abcnewshudson5/master.m3u8": "https://jmp2.uk/plu-6508be683a0d700008c534e4.m3u8",
    "https://abcnews-streams.akamaized.net/hls/live/2023565/abcnewshudson6/master.m3u8": "https://jmp2.uk/plu-6508be683a0d700008c534e4.m3u8",
    "https://abcnews-streams.akamaized.net/hls/live/2023566/abcnewshudson7/master.m3u8": "https://jmp2.uk/plu-6508be683a0d700008c534e4.m3u8",
    "https://abcnews-streams.akamaized.net/hls/live/2023567/abcnewshudson8/master.m3u8": "https://jmp2.uk/plu-6508be683a0d700008c534e4.m3u8",
    "https://abcnews-streams.akamaized.net/hls/live/2023568/abcnewshudson9/master.m3u8": "https://jmp2.uk/plu-6508be683a0d700008c534e4.m3u8",
    "https://abcnews-streams.akamaized.net/hls/live/2023569/abcnewshudson10/master.m3u8": "https://jmp2.uk/plu-6508be683a0d700008c534e4.m3u8",
    # AMC en Español (dead wurl -> working Samsung TV Plus embed)
    "https://amc-amcespanol-1-us.lg.wurl.tv/playlist.m3u8": "https://jmp2.uk/stvp-USBA300020W4",
    # Ninja Kidz TV (dead roku 404 -> working cloudfront CDN stream)
    "https://jmp2.uk/rok-9dd23031622757d1944e4782b2a192ef.m3u8": "https://d3868b4ny0rgdf.cloudfront.net/playlist.m3u8",
    # Cinevault 80s (dead tubi 404 -> working Wurl / GSN linear stream)
    "https://aegis-cloudfront-1.tubi.video/ea1ab5d1-f554-4f6b-b03f-2611fcd94257/playlist.m3u8": "https://wurlgameshownetwork.global.transmit.live/hls/68d16f229e868efab9c34b16/v1/gsn_cinevault_80s_1/lg_us/latest/main/hls/playlist.m3u8",
    # Canela TV (dead cloudfront -> working Samsung TV Plus embed)
    "https://d3cx6yargdnl7q.cloudfront.net/canelatv.m3u8": "https://jmp2.uk/stvp-USBC39000080S",
}

# Defunct publisher endpoints with no viable replacement stream
DEFUNCT_STREAMS: set[str] = {
    "https://30a-tv.com/ln.m3u8",
    "https://30a-tv.com/loomer.m3u8",
    "https://ntv1.akamaized.net/hls/live/2014075/NASA-NTV1-HLS/master_2000.m3u8",
    "https://ntv2.akamaized.net/hls/live/2013923/NASA-NTV2-HLS/master.m3u8",
    "https://fast-channels.sinclairstoryline.com/TBD/index.m3u8",
    "https://rpn.bozztv.com/trn01/gusa-TVSFilmNoir/index.m3u8",
    "https://dai.google.com/linear/hls/event/HZ3JdLVcQ463l3b1BLXmmQ/master.m3u8",
    "https://d3svnrf3rmq619.cloudfront.net/krgv-live/smil:krgv-somos.smil/playlist.m3u8",
}


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


def approval(channel_id: str, host: str, policy: dict, *, source: dict | None = None,
             redirect_source_url: str = "") -> tuple[str, str] | None:
    """Approve a publisher host, or a narrow ID+host/source+redirect combination.

    CloudFront, Akamai `pb-*`, Samsung TV Plus, and AWS MediaTailor are shared
    delivery infrastructure, not evidence of distribution rights on their own.
    Rules for those hosts therefore require the entry to come from the reviewed
    Samsung TV Plus US feed and its stable jmp2.uk `/stvp-` redirect, unless a
    separate exact channel-ID+host rule exists.
    """
    if host in policy.get("excluded_hosts", ()):
        return None
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
    if source and source.get("resolve_redirects") and redirect_source_url:
        origin = urlsplit(redirect_source_url)
        for rule in policy.get("allowed_source_host_patterns", ()):
            if source.get("name") != rule["source_name"]:
                continue
            if origin.hostname != rule["redirect_host"]:
                continue
            if not origin.path.startswith(rule["redirect_path_prefix"]):
                continue
            if "pattern" in rule and re.fullmatch(rule["pattern"], host):
                return ("source-pattern:" + rule["pattern"], rule["evidence_url"])
            if host in rule.get("hosts", ()):
                return ("source-host:" + host, rule["evidence_url"])
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
    redirect_source_url = ""
    if redirect_cache is not None:
        # Sources flagged resolve_redirects publish redirector URLs (e.g.
        # jmp2.uk/stvp-...) that are only usable after one-time resolution;
        # retain the original URL so shared CDN hosts can be allowed only for
        # this reviewed source and redirect path.
        redirect_source_url = url
        url = redirect_cache.get(url, "")
        if not url:
            return None, "redirect_unresolved"
    if url in DEAD_STREAM_REPLACEMENTS:
        url = DEAD_STREAM_REPLACEMENTS[url]
    if url in DEFUNCT_STREAMS:
        return None, "dead_stream"
    if not valid_url(url, stream=True):
        return None, "not_direct_https_hls"
    host = urlsplit(url).hostname or ""
    approved = approval(channel_id, host, policy, source=source,
                         redirect_source_url=redirect_source_url)
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
    # Alternate working streams are captured and formatted as backups with
    # category "Backups" for seamless M3U player grouping.
    by_id = {}
    by_name = {}
    seen_urls = set()
    backups = []
    backup_counts = Counter()

    for c in candidates:
        name_key = " ".join(c["name"].casefold().split())
        url = c["url"]
        cid = c["id"].casefold()

        if url in seen_urls:
            skipped["duplicate"] += 1
            continue

        if cid in by_id or name_key in by_name:
            primary = by_id.get(cid) or by_name.get(name_key)
            if primary and backup_counts[primary["id"]] < 2 and url != primary["url"]:
                backup_counts[primary["id"]] += 1
                b_num = backup_counts[primary["id"]]
                b_suffix = " [Backup]" if b_num == 1 else f" [Backup {b_num}]"
                backup_item = dict(c)
                backup_item["name"] = f"{primary['name']}{b_suffix}"
                backup_item["group"] = "Backups"
                backup_item["categories"] = ["Backups"]
                backup_item["is_backup"] = True
                backup_item["backup_of"] = primary["id"]
                backups.append(backup_item)
                seen_urls.add(url)
            skipped["duplicate_name" if name_key in by_name else "duplicate"] += 1
            continue

        by_id[cid] = c
        by_name[name_key] = c
        seen_urls.add(url)

    channels = sorted(by_id.values(), key=lambda c: (c["name"].casefold(), c["id"].casefold()))
    backups = sorted(backups, key=lambda c: (c["name"].casefold(), c["id"].casefold()))
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
        "usa-backups.m3u": backups,
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
                        help="allow a decline greater than 40 percent after investigating upstream or policy changes")
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
