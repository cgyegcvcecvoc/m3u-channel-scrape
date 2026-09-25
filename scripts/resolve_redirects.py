#!/usr/bin/env python3
"""Resolve redirector URLs for FAST sources into direct HLS manifest URLs.

Sources flagged `resolve_redirects` in config/sources.json publish entries such
as https://jmp2.uk/stvp-XXXX that (a) redirect to the platform's real manifest
and (b) lack a .m3u8 path, which the channel validator requires. This script
follows each redirect once, keeps only direct HTTPS .m3u8 results without
credential/expiry query parameters, and stores the mapping in
config/redirect_cache.json for scripts/update_playlists.py.

Requires outbound network access (run in the refresh workflow or anywhere the
redirector is reachable). Existing cache entries are kept when a re-resolution
fails, so a transient error never drops channels from the next build.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import sys
import tempfile
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import update_playlists as u  # noqa: E402

USER_AGENT = "m3u-channel-scrape/1.0 (redirect resolver)"


def resolve(url: str) -> tuple[str, str] | None:
    """Return (original, final_manifest_url) when the redirect resolves cleanly."""
    if not u.valid_url(url):
        return None
    try:
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
        with urlopen(request, timeout=15) as response:
            head = response.read(4096)
            final = response.geturl()
    except (OSError, ValueError):
        return None
    if not head.lstrip(b"\xef\xbb\xbf \t\r\n").startswith(b"#EXTM3U"):
        return None
    if final == url or not u.valid_url(final, stream=True):
        return None
    return url, final


def collect_urls(sources: list[dict], fetcher=u.download_source) -> list[str]:
    urls: list[str] = []
    for source in sources:
        if not source.get("resolve_redirects"):
            continue
        raw = fetcher(source)
        for _, _, url, needs_headers in u.parse_m3u(raw.decode("utf-8-sig", errors="replace")):
            if not needs_headers:
                urls.append(url)
    return list(dict.fromkeys(urls))


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".redirect-", delete=False,
                                         mode="w", encoding="utf-8") as tmp:
            tmp_path = Path(tmp.name)
            json.dump(payload, tmp, indent=2, sort_keys=True, ensure_ascii=False)
            tmp.write("\n")
        os.replace(tmp_path, path)
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=ROOT / "config/redirect_cache.json")
    parser.add_argument("--sources", type=Path, default=ROOT / "config/sources.json")
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()
    sources = json.loads(args.sources.read_text(encoding="utf-8"))["sources"]
    try:
        urls = collect_urls(sources)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Resolve failed reading sources: {exc}", file=sys.stderr)
        return 1
    try:
        cache = json.loads(args.cache.read_text(encoding="utf-8"))
        if not isinstance(cache, dict):
            cache = {}
    except (OSError, ValueError):
        cache = {}
    todo = [url for url in urls if url not in cache]
    resolved = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for result in pool.map(resolve, todo):
            if result:
                cache[result[0]] = result[1]
                resolved += 1
    atomic_json(args.cache, cache)
    print(f"Redirect cache: {resolved} newly resolved, {len(todo) - resolved} failed/skipped, "
          f"{len(cache)} total entries ({len(urls)} URLs needed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
