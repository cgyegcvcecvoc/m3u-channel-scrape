#!/usr/bin/env python3
"""Probe playlists and record point-in-time playback evidence.

For every channel URL the probe:
  1. downloads the HLS master/media manifest (following redirects),
  2. picks a variant rendition and downloads its media playlist,
  3. downloads one complete media segment and checks container bytes
     (MPEG-TS sync, MP4 ftyp/moof, or ADTS audio).

Statuses written to generated/verification.json:
  segment_ok    manifest + one full media segment fetched (strongest signal)
  manifest_ok   HLS playlists fetched; media segment not confirmed
  geo_blocked   HTTP 451 (legally restricted in probe region)
  unavailable   definitive miss: HTTP 404/410/400, DNS failure, non-HLS body
  inconclusive  network/TLS/timeout/5xx/403/401 — NOT evidence a channel is dead

Outputs:
  generated/verification.json            full per-channel results + method notes
  generated/playlists/usa-verified.m3u   catalog entries with segment_ok
  usa-verified.m3u (repository root)     root bulk playlist filtered to
                                         segment_ok, https, direct-HLS entries

A probe only proves that ONE segment loaded from ONE runner location at ONE
moment. It says nothing about rights, terms, continuity, or your location.
"""
from __future__ import annotations

import argparse
import concurrent.futures
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import ssl
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import update_playlists as u  # noqa: E402

USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 "
              "Firefox/128.0 m3u-channel-scrape/1.0 (+verification probe)")
MANIFEST_CAP = 768 * 1024
SEGMENT_CAP = 1024 * 1024
MAX_RENDITIONS = 3


class ProbeFailure(Exception):
    def __init__(self, status: str, reason: str):
        super().__init__(f"{status}:{reason}")
        self.status = status
        self.reason = reason


def media_signature(chunk: bytes) -> bool:
    """True when bytes look like MPEG-TS, fMP4/MP4, or ADTS audio media."""
    if not chunk:
        return False
    head = chunk[:512]
    if head[:4] == b"#EXT" or head[:1] in (b"<", b"{"):
        return False                      # another playlist / JSON / HTML error body
    if b"ftyp" in head or b"moof" in head or b"styp" in head:
        return True                       # ISO-BMFF / fMP4
    if chunk[0] == 0xFF and (chunk[1] & 0xF0) == 0xF0:
        return True                       # ADTS AAC frame
    if b"ID3" in chunk[:3]:
        return True                       # MP3 with ID3 tag
    if chunk[0] == 0x47:
        return True                       # MPEG-TS sync byte at packet start
    # Tolerate short leading padding: sync byte inside the first packet that
    # repeats at the fixed 188-byte TS packet size.
    idx = head.find(b"\x47", 1, 188)
    while idx != -1:
        if idx + 188 < len(chunk) and chunk[idx + 188] == 0x47:
            return True
        idx = head.find(b"\x47", idx + 1, 188)
    return False


def _classify(exc: BaseException) -> ProbeFailure:
    if isinstance(exc, HTTPError):
        code = exc.code
        if code == 451:
            return ProbeFailure("geo_blocked", "http_451")
        if code in (404, 410):
            return ProbeFailure("unavailable", f"http_{code}")
        if code in (400, 402):
            return ProbeFailure("unavailable", f"http_{code}")
        return ProbeFailure("inconclusive", f"http_{code}")
    reason = getattr(exc, "reason", exc)
    if isinstance(reason, socket.gaierror):
        return ProbeFailure("unavailable", "dns_failure")
    if isinstance(reason, (ssl.SSLError, ssl.SSLZeroReturnError)):
        return ProbeFailure("inconclusive", "tls_error")
    if isinstance(reason, (socket.timeout, TimeoutError)):
        return ProbeFailure("inconclusive", "timeout")
    if isinstance(exc, URLError) and isinstance(reason, str) and "timed out" in reason:
        return ProbeFailure("inconclusive", "timeout")
    return ProbeFailure("inconclusive", type(reason).__name__[:60])


def fetch_text(url: str, timeout: float) -> tuple[str, str]:
    request = Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.apple.mpegurl, application/x-mpegURL, */*;q=0.8",
    })
    try:
        with urlopen(request, timeout=timeout) as response:
            data = response.read(MANIFEST_CAP + 1)
            final_url = response.geturl()
    except (HTTPError, URLError, OSError, ValueError) as exc:
        raise _classify(exc) from exc
    if len(data) > MANIFEST_CAP:
        data = data[:MANIFEST_CAP]
    text = data.decode("utf-8-sig", errors="replace")
    if not text.lstrip().startswith("#EXTM3U"):
        raise ProbeFailure("unavailable", "not_hls_body")
    return text, final_url  # type: ignore[return-value]


def fetch_bytes(url: str, timeout: float) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read(SEGMENT_CAP + 1)
    except (HTTPError, URLError, OSError, ValueError) as exc:
        raise _classify(exc) from exc


def _variant_urls(manifest: str, base_url: str) -> list[str]:
    """Rendition URIs after each #EXT-X-STREAM-INF (audio/subtitle media tags skipped)."""
    urls: list[str] = []
    expecting = False
    for line in manifest.splitlines():
        line = line.strip()
        if line.startswith("#EXT-X-STREAM-INF"):
            expecting = True
        elif not line or line.startswith("#"):
            continue
        elif expecting:
            urls.append(urljoin(base_url, line))
            expecting = False
    return urls


def _segment_urls(media: str, base_url: str) -> list[str]:
    urls: list[str] = []
    for line in media.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().endswith(".m3u8"):
            continue
        urls.append(urljoin(base_url, line))
    return urls


def probe(url: str, timeout: float = 10.0) -> tuple[str, str]:
    """Return (status, reason) for one channel URL."""
    try:
        manifest, media_url = fetch_text(url, timeout)
        for _ in range(MAX_RENDITIONS):
            if "#EXT-X-STREAM-INF" not in manifest:
                break
            variants = _variant_urls(manifest, media_url)
            if not variants:
                raise ProbeFailure("unavailable", "no_renditions")
            failure: ProbeFailure | None = None
            for variant in variants[:MAX_RENDITIONS]:
                try:
                    manifest, media_url = fetch_text(variant, timeout)
                    failure = None
                    break
                except ProbeFailure as exc:
                    failure = exc
            if failure is not None:
                raise failure
        else:
            raise ProbeFailure("unavailable", "renditions_too_deep")
        if "#EXTINF" not in manifest and "#EXT-X-TARGETDURATION" not in manifest:
            raise ProbeFailure("unavailable", "not_media_playlist")
        segments = _segment_urls(manifest, media_url)
        if not segments:
            return "manifest_ok", "no_segments_listed"
        last_failure: ProbeFailure | None = None
        for segment_url in segments[-2:]:
            try:
                chunk = fetch_bytes(segment_url, timeout)
            except ProbeFailure as exc:
                last_failure = exc
                continue
            if media_signature(chunk[:SEGMENT_CAP]):
                return "segment_ok", "manifest_and_segment"
            last_failure = ProbeFailure("manifest_ok", "segment_signature_mismatch")
        if last_failure is not None and last_failure.status == "manifest_ok":
            return "manifest_ok", last_failure.reason
        raise last_failure or ProbeFailure("manifest_ok", "segment_fetch_failed")
    except ProbeFailure as exc:
        return exc.status, exc.reason


def parse_playlist_pairs(text: str) -> list[tuple[str, str]]:
    """Return (extinf_line, url) pairs, preserving original EXTINF text."""
    pairs: list[tuple[str, str]] = []
    pending: str | None = None
    for raw in text.splitlines():
        line = raw.rstrip("\r")
        if line.startswith("#EXTINF"):
            pending = line
        elif line.startswith("#") or not line.strip():
            continue
        elif pending is not None:
            pairs.append((pending, line.strip()))
            pending = None
    return pairs


def _probe_all(targets: list[tuple[str, str]], workers: int, timeout: float) -> dict[str, tuple[str, str]]:
    results: dict[str, tuple[str, str]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(probe, url, timeout): (key, url)
                   for key, url in targets}
        for future in concurrent.futures.as_completed(futures):
            key, _url = futures[future]
            try:
                results[key] = future.result()
            except Exception as exc:  # noqa: BLE001 - never lose one channel
                results[key] = ("inconclusive", f"probe_error:{type(exc).__name__}")
    return results


def _counts(results: dict[str, tuple[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for status, _ in results.values():
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def emit_catalog_verified(channels: list[dict], alive_ids: set[str], guide_urls: list[str],
                          checked: str) -> bytes:
    joined = ",".join(guide_urls)
    lines = [f'#EXTM3U url-tvg="{joined}" x-tvg-url="{joined}"',
             f"# Verified working: {len(alive_ids)} of {len(channels)} catalog channels "
             f"returned a playable media segment from the probe runner at {checked}.",
             "# Point-in-time result from scripts/verify_channels.py; availability in "
             "your location and over time is not guaranteed."]
    for c in channels:
        if c["id"] not in alive_ids:
            continue
        lines.extend([
            '#EXTINF:-1 tvg-id="{}" tvg-name="{}" tvg-logo="{}" group-title="{}",{}'.format(
                u.cleaned(c["id"]), u.cleaned(c["name"]), u.cleaned(c["logo"], limit=1000),
                u.cleaned(c["group"]), u.cleaned(c["name"])),
            c["url"],
        ])
    return ("\n".join(lines) + "\n").encode("utf-8")


def emit_root_verified(original: str, results: dict[str, tuple[str, str]], checked: str) -> bytes:
    lines_in = original.splitlines()
    header = next((line for line in lines_in if line.startswith("#EXTM3U")),
                  "#EXTM3U x-tvg-url=\"\" url-tvg=\"\"")
    pairs = parse_playlist_pairs(original)
    alive = [(extinf, url) for extinf, url in pairs
             if u.valid_url(url, stream=True)
             and results.get(url, ("", ""))[0] == "segment_ok"]
    total_https = sum(1 for _, url in pairs if u.valid_url(url, stream=True))
    out = [header,
           f"# Verified working: {len(alive)} of {len(pairs)} entries "
           f"({total_https} policy-format https/HLS) returned a playable media "
           f"segment at {checked}.",
           "# Original bulk playlist filtered by scripts/verify_channels.py; "
           "point-in-time probe, not a rights review."]
    for extinf, url in alive:
        out.extend([extinf, url])
    return ("\n".join(out) + "\n").encode("utf-8")


def run(catalog_path: Path, root_playlist: Path, out_json: Path,
        verified_playlist: Path, root_out: Path, workers: int, timeout: float,
        skip_root: bool, skip_catalog: bool) -> dict:
    checked = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    runner = "github-actions" if os.environ.get("GITHUB_ACTIONS") == "true" else "local"
    report: dict = {
        "checked_utc": checked,
        "runner": runner,
        "method": "HLS master/media playlists plus one complete media segment; "
                  "container signature checked (TS/MP4/ADTS), not decoded and "
                  "not a continuous-playback test",
        "limitations": "One probe, one runner location, one moment in time. "
                       "inconclusive = network/TLS/timeout/server error and is NOT "
                       "evidence the channel is dead. segment_ok does not guarantee "
                       "playback in your location, continuity, or any distribution "
                       "right. geo restrictions and terms are out of scope.",
    }
    # -- catalog ----------------------------------------------------------
    channels: list[dict] = []
    if not skip_catalog and catalog_path.is_file():
        channels = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog_targets = [(c["id"], c["url"]) for c in channels]
    catalog_results = _probe_all(catalog_targets, workers, timeout)
    alive_ids = {key for key, (status, _) in catalog_results.items() if status == "segment_ok"}
    report["catalog"] = {
        "total": len(channels),
        "counts": _counts(catalog_results),
        "results": [
            {"id": c["id"], "name": c["name"], "url": c["url"],
             "status": catalog_results.get(c["id"], ("inconclusive", "not_probed"))[0],
             "reason": catalog_results.get(c["id"], ("", ""))[1]}
            for c in sorted(channels, key=lambda x: (x["name"].casefold(), x["id"].casefold()))
        ],
    }
    # -- root bulk playlist ----------------------------------------------
    root_pairs: list[tuple[str, str]] = []
    if not skip_root and root_playlist.is_file() and root_playlist.stat().st_size:
        original = root_playlist.read_text(encoding="utf-8", errors="replace")
        root_pairs = parse_playlist_pairs(original)
        root_targets = [(url, url) for _, url in root_pairs]
        root_results = _probe_all(root_targets, workers, timeout)
        report[root_playlist.name] = {
            "total": len(root_pairs),
            "counts": _counts(root_results),
            "results": [
                {"name": parse_playlist_pairs_name(extinf), "url": url,
                 "status": root_results.get(url, ("inconclusive", "not_probed"))[0],
                 "reason": root_results.get(url, ("", ""))[1],
                 "policy_format": u.valid_url(url, stream=True)}
                for extinf, url in root_pairs
            ],
        }
        root_out.write_bytes(emit_root_verified(original, root_results, checked))
        print(f"  {root_out}: filtered to {report[root_playlist.name]['counts'].get('segment_ok', 0)} "
              f"working of {len(root_pairs)}")
    # -- outputs ----------------------------------------------------------
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                        encoding="utf-8")
    if channels:
        epg = json.loads((ROOT / "config/epg.json").read_text(encoding="utf-8"))
        guide = epg["header_url"]
        guide_urls = [guide] + [g["url"] for g in epg["guides"] if g["url"] != guide]
        verified_playlist.write_bytes(
            emit_catalog_verified(channels, alive_ids, guide_urls, checked))
        print(f"  {verified_playlist}: {len(alive_ids)} of {len(channels)} catalog channels segment_ok")
    print(f"  {out_json}: written (runner={runner})")
    return report


def parse_playlist_pairs_name(extinf: str) -> str:
    return extinf.rsplit(",", 1)[-1].strip()[:120]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=ROOT / "generated/channels.json")
    parser.add_argument("--root-playlist", type=Path, default=ROOT / "usa-verified.m3u")
    parser.add_argument("--out", type=Path, default=ROOT / "generated/verification.json")
    parser.add_argument("--verified-out", type=Path,
                        default=ROOT / "generated/playlists/usa-verified.m3u")
    parser.add_argument("--root-out", type=Path, default=ROOT / "usa-verified.m3u")
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--skip-root", action="store_true")
    parser.add_argument("--skip-catalog", action="store_true")
    args = parser.parse_args()
    try:
        run(args.catalog, args.root_playlist, args.out, args.verified_out,
            args.root_out, args.workers, args.timeout, args.skip_root, args.skip_catalog)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Verify failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
