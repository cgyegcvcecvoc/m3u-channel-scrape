# m3u-channel-scrape

Report issues in #issues and be as detailed as possible about the issue. Full description of the issue, and give it a moment to be resolved; it will be resolved ASAP 





**Free-viewing US TV playlists, refreshed from public candidate feeds into this GitHub work branch.**

This checkout originally contained only a README; the earlier M3U Forge dataset described in chat was **not in this repository**. These are generated files, not a copy of a claimed 10,000+ channel database. The catalog now holds **1,059 host-reviewed US listings** — local/public channels, free news, free sports, and full US lineups from FAST platforms (Pluto TV, Roku Channel, Samsung TV Plus); counts change on every refresh, so trust the live [manifest](generated/manifest.json) over any fixed number.

> Public URL ≠ permission to restream. This project does **not** carry cable subscriptions, DRM keys, pay-TV mirrors, captured credentials, VOD, or proxy bypasses. Streams are links to other publishers, not video hosted here. Publisher terms, regional restrictions, and playback can change; the host review is a best-effort filter, **not a guarantee** that every link is authorized or works in your location.

## Download/play

Open an M3U link in VLC (Media → Open Network Stream) or import it in an IPTV player. Direct GitHub RAW URL for the US playlist on **this working branch**:

```text
https://raw.githubusercontent.com/cgyegcvcecvoc/m3u-channel-scrape/refs/heads/arena/01a0da43-m3u-channel-scrape/generated/playlists/usa-all.m3u
```

Replace `usa-all.m3u` with a filename below for smaller playlists. Files are also available in [generated/playlists/](generated/playlists/):

| Playlist | Contents |
| --- | --- |
| [usa-all.m3u](generated/playlists/usa-all.m3u) | Reviewed US live streams (the root [usa-all.m3u](usa-all.m3u) is the same file, kept in sync) |
| [usa-verified.m3u](generated/playlists/usa-verified.m3u) | Catalog subset that **returned a playable media segment** in the last verification run (see [generated/verification.json](generated/verification.json)) |
| [usa-news.m3u](generated/playlists/usa-news.m3u) | Free news / local news |
| [usa-sports.m3u](generated/playlists/usa-sports.m3u) | Free sports FAST/talk/highlights; **not** paid ESPN/FS1 feeds |
| [usa-local.m3u](generated/playlists/usa-local.m3u) | Local/public-access/municipal/free local news |
| [usa-spanish.m3u](generated/playlists/usa-spanish.m3u) | Spanish-language free channels |
| [usa-weather.m3u](generated/playlists/usa-weather.m3u) · [usa-business.m3u](generated/playlists/usa-business.m3u) | Weather and business/free finance |
| [usa-intermittent.m3u](generated/playlists/usa-intermittent.m3u) | Sources marked **Not 24/7**; a stream may be off air between events |
| [usa-movies.m3u](generated/playlists/usa-movies.m3u) · [usa-entertainment.m3u](generated/playlists/usa-entertainment.m3u) · [usa-kids.m3u](generated/playlists/usa-kids.m3u) · [usa-music.m3u](generated/playlists/usa-music.m3u) | Other free-viewing categories |

The root [usa-verified.m3u](usa-verified.m3u) is the repository's original bulk playlist filtered by each verification run — the run reads the pristine copy at [generated/bulk_source.m3u](generated/bulk_source.m3u) (all 4,021 uploaded entries), re-probes every one of them, and rewrites the root file with those that are still direct HTTPS HLS **and** returned a media segment; re-probing the pristine copy (instead of the previous filtered output) means a channel that hiccuped in one run can come back. Per-entry `policy_format` flags in the verification report show which survivors also pass host review.

Each UTF-8 file starts with `#EXTM3U` and XMLTV guide URL(s), then pairs `#EXTINF:-1 tvg-id="…" tvg-name="…" tvg-logo="…" group-title="…",Name` with one HTTPS `.m3u8` stream URL. `tvg-id` drops quality-only suffixes (such as `@SD`) but keeps regional feed IDs (such as `@KEROTV`) rather than assigning the wrong local TV schedule; FAST platform entries keep their platform channel ID so the matching i.mjh.nz guide applies. **Building does not probe streams** — playback evidence comes from `scripts/verify_channels.py`, whose point-in-time results are recorded in [generated/verification.json](generated/verification.json). Channel totals and the UTC generation timestamp are in [generated/manifest.json](generated/manifest.json); per-channel source and approval evidence is in [generated/channels.json](generated/channels.json). Do not assume thousands of US pay-cable networks have authorized free HLS streams.

## EPG / XMLTV

The playlists' first guide (and `url-tvg` header) is the **external** US guide (plain XML):

```text
https://epg.pw/xmltv/epg_US.xml
```

The header additionally carries [i.mjh.nz](https://github.com/matthuisman/i.mjh.nz) XMLTV links for the FAST platforms (`PlutoTV/us.xml.gz`, `SamsungTVPlus/us.xml.gz`, `Roku/all.xml.gz`) — one comma-separated `x-tvg-url` list, so each player picks the guide whose IDs match a given entry (`*.us` IDs → epg.pw; platform IDs → i.mjh.nz). [generated/epg/links.txt](generated/epg/links.txt) lists every guide; [generated/epg/links.json](generated/epg/links.json) records providers and caveats. The providers publish and update these XMLTV files themselves; we do **not** copy schedules into GitHub or claim redistribution rights. XMLTV `<channel id>` must equal a playlist's `tvg-id` for automatic schedule matching. The often-copied `iptv-org.github.io/epg/guides/us.xml` link is **404**, so it is not used here. An EPG link is not a channel stream.

## Refresh locally

Python **3.10+**, standard library only:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/update_playlists.py
```

The updater reads [config/sources.json](config/sources.json), fetches the [iptv-org US playlist](https://github.com/iptv-org/iptv), [Free-TV's US playlist](https://github.com/Free-TV/IPTV), and the FAST platform lineups above, falling back to GitHub's public contents/blob API if raw/GitHub Pages is unavailable. These are **candidate** sources, not a legal clearance. It applies [config/policy.json](config/policy.json): US XMLTV ID (or a platform ID for country-filtered FAST sources), reviewed exact DNS host/host suffix or reviewed ID+host with a publisher/free-service page, HTTPS direct HLS, no credentials/signed-token or partner/device-impersonation URLs, no custom-header workarounds, no VOD, and an explicit exclusion list for pay-TV IDs. Unknown new domains are **not** silently accepted — every rejected host and the reason is recorded in the policy file's `_rejected_hosts`. It deduplicates on channel ID, stream URL **and channel name** (FAST platforms repeat the same names), normalizes group titles into the published categories, and writes the files in `generated/` only after all required sources succeed. Large unexplained drops are refused so a bad download cannot replace good playlists.

Samsung TV Plus entries are published through redirector URLs that need one-time resolution:

```bash
python3 scripts/resolve_redirects.py   # writes config/redirect_cache.json (needs network)
python3 scripts/update_playlists.py
```

To add a genuinely free channel, find the publisher's own free-viewing page and a direct HLS feed it permits viewers to access; add a candidate M3U source in `config/sources.json` and a **narrow**, reviewed host or exact channel ID+host with `evidence_url` in `config/policy.json`. Check publisher terms and territory. Do **not** approve a generic CDN, an unauthorized cable restream, a proxy to defeat service restrictions, or a pay-TV channel just because it returns 200. Changes to the policy and EPG provider [config/epg.json](config/epg.json) are reviewed by people rather than automatically discovered from random web pages. `--allow-shrink` overrides the 40% shrink guard **only after** investigating it. Scheduled runs do not use this override. The research trail for the current host list lives in [RESEARCH.md](RESEARCH.md).

## Verify playback

```bash
python3 scripts/verify_channels.py            # probes catalog + root bulk playlist
```

For each URL it downloads the master manifest, a rendition media playlist, and **one complete media segment**, then checks container bytes (MPEG-TS/MP4/ADTS). Results are written to [generated/verification.json](generated/verification.json) with honest statuses: `segment_ok`, `manifest_ok`, `geo_blocked`, `unavailable` (definitive miss), `inconclusive` (network/TLS/timeout — not evidence of death). Two playlists are kept in sync with the results: [generated/playlists/usa-verified.m3u](generated/playlists/usa-verified.m3u) (reviewed catalog that played) and the root [usa-verified.m3u](usa-verified.m3u) (the uploaded bulk list, filtered to working policy-format entries). A probe proves only that a segment loaded from one runner location at one moment — not rights, not continuity, not your location.

## GitHub automatic updates

[.github/workflows/refresh.yml](.github/workflows/refresh.yml) runs **on every push to `arena/01a0da43-m3u-channel-scrape`**, daily around 06:17 UTC, and on manual dispatch: tests → redirect resolution → playlist regeneration → tests again, then commits changed `generated/` files, `config/redirect_cache.json` and the synced root `usa-all.m3u` **to this work branch only**. [.github/workflows/verify.yml](.github/workflows/verify.yml) probes every channel the same way plus daily at 08:43 UTC and commits `generated/verification.json` and the two verified playlists; both workflows skip the `github-actions[bot]`'s own commits so they cannot loop. [tests.yml](.github/workflows/tests.yml) checks code on work-branch pushes and pull requests. No extra secret/PAT is needed: they use `GITHUB_TOKEN` (repository Actions setting must allow `contents: write`). GitHub may delay or disable scheduled jobs; this is daily refresh, not real-time monitoring.

**Activation:** GitHub `schedule` and `workflow_dispatch` require the workflow file on the repository's **default branch**. Push triggers (above) work today from this branch; the schedules activate once these workflow files are merged into `main`. After that, checkouts and pushes still target **only the Arena work branch**, not `main`; you can merge subsequent updates when ready. If a bot push is denied by branch protection or Actions token permissions, check repository Settings → Actions → General / branch rules. Until activation, run the local commands above and push this branch.

Upstream playlist maintainers: [iptv-org](https://github.com/iptv-org/iptv), [Free-TV/IPTV](https://github.com/Free-TV/IPTV) and [BuddyChewChew/app-m3u-generator](https://github.com/BuddyChewChew/app-m3u-generator). Guide providers: [epg.pw](https://epg.pw/xmltv.html?lang=en) and [matthuisman/i.mjh.nz](https://github.com/matthuisman/i.mjh.nz). Please report any stream that is subscription-only, misattributed or not intended for direct access; it should be removed from the allowlist.
