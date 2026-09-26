# m3u-channel-scrape

**Free-viewing US TV playlists, refreshed from public candidate feeds into this GitHub work branch.**

This repository maintains curated, host-reviewed M3U playlists of legal, free-to-air (FTA) and free ad-supported streaming television (FAST) channels in the United States. The catalog currently holds **1,456 host-reviewed US channel listings** and **310 backup stream entries** — encompassing local/public channels, national news, sports, movies, entertainment, music, kids programming, and full US lineups from major FAST platforms (Pluto TV, Roku Channel, Samsung TV Plus). Channel counts change dynamically on refresh runs; consult the live [manifest](generated/manifest.json) for current counts.

---

### Important Disclaimers

> **1. No Content Hosting:** The repository owner and maintainers **do not host, broadcast, archive, or rebroadcast any video or audio content**. This repository contains only plain-text M3U playlist files pointing to publicly accessible third-party streams provided by broadcasters and distribution networks.
>
> **2. No Rapid Fixes for Dead Streams:** Stream availability and uptime are strictly controlled by third-party broadcasters and playout providers. Content owners frequently modify endpoints, cycle token mechanisms, enforce geo-restrictions, or take channels off the air without prior notice. **The repository maintainers cannot quickly fix dead or offline streams.** Stream audits occur periodically, but if a broadcaster discontinues or protects an endpoint, the channel may remain unavailable or be removed.
>
> **3. Strictly Legal, Free-to-Air Streams Only:** Public URL ≠ permission to restream. This project does **not** carry cable subscriptions, DRM keys, pay-TV mirrors, captured credentials, VOD, or proxy bypasses. Streams are direct links to publishers. Host review is a best-effort policy filter, **not a guarantee** of uptime or territorial accessibility in your region.

---

## Download / Play

Open an M3U playlist link in VLC (*Media → Open Network Stream*), mpv, Kodi, TiviMate, or any IPTV player. Direct GitHub RAW URL for the primary US playlist on **this working branch**:

```text
https://raw.githubusercontent.com/cgyegcvcecvoc/m3u-channel-scrape/refs/heads/arena/01a0db0b-m3u-channel-scrape/generated/playlists/usa-all.m3u
```

Replace `usa-all.m3u` with any playlist filename below for specific categories. Files are stored in [generated/playlists/](generated/playlists/):

| Playlist | Contents |
| --- | --- |
| [usa-all.m3u](generated/playlists/usa-all.m3u) | Reviewed US live streams (the root [usa-all.m3u](usa-all.m3u) is kept in sync) |
| [usa-verified.m3u](generated/playlists/usa-verified.m3u) | Catalog subset that **returned a playable media segment** in the latest verification run (see [generated/verification.json](generated/verification.json)) |
| [usa-backups.m3u](generated/playlists/usa-backups.m3u) | **Alternate and backup feeds** for channels with multiple sources; formatted with `group-title="Backups"` and `[Backup]` labels so they appear in a separate category in IPTV players |
| [usa-news.m3u](generated/playlists/usa-news.m3u) | Free national and local news feeds |
| [usa-sports.m3u](generated/playlists/usa-sports.m3u) | Free sports FAST channels, highlights, and talk; **not** paid cable (ESPN/FS1) feeds |
| [usa-local.m3u](generated/playlists/usa-local.m3u) | Local broadcast, public-access, municipal, and regional news streams |
| [usa-entertainment.m3u](generated/playlists/usa-entertainment.m3u) | Free entertainment, classic TV, drama, and comedy feeds |
| [usa-movies.m3u](generated/playlists/usa-movies.m3u) | Free linear movie networks (e.g. Pluto, Roku, Samsung TV Plus cinema channels) |
| [usa-kids.m3u](generated/playlists/usa-kids.m3u) | Family and children's programming |
| [usa-music.m3u](generated/playlists/usa-music.m3u) | Linear music video and audio streams (Vevo, Stingray, XITE) |
| [usa-spanish.m3u](generated/playlists/usa-spanish.m3u) | Spanish-language free live channels |
| [usa-weather.m3u](generated/playlists/usa-weather.m3u) | Weather channels and live forecast loops |
| [usa-business.m3u](generated/playlists/usa-business.m3u) | Free business and financial news (Bloomberg, Cheddar, Yahoo Finance) |
| [usa-intermittent.m3u](generated/playlists/usa-intermittent.m3u) | Sources marked **Not 24/7**; streams that go off air between scheduled live events |

The root [usa-verified.m3u](usa-verified.m3u) is the repository's bulk playlist filtered by verification runs — the probe reads the baseline copy at [generated/bulk_source.m3u](generated/bulk_source.m3u), re-probes every entry, and writes the root file with channels that are direct HTTPS HLS **and** return a media segment. Per-entry `policy_format` flags in the verification report show which survivors pass host review.

### Backup Streams

To prevent clutter in the main category playlists while preserving stream redundancy, alternate feeds for channels available across multiple platforms are grouped into [usa-backups.m3u](generated/playlists/usa-backups.m3u). Each backup entry has:
- `group-title="Backups"` (so your IPTV player isolates them into a separate group)
- A channel name suffixed with `[Backup]` or `[Backup 2]`
- Its own verified direct HTTPS HLS stream URL

---

## Requesting New Channels

We welcome suggestions for new legal, free-to-air channels. Channel requests must be submitted through **GitHub Issues**.

To maintain catalog quality and compliance, **every request must fulfill the following requirements**:

1. **Mandatory Stream Link:** You **must provide a direct stream link (HTTPS `.m3u8` URL)** or an official publisher web page where the live stream is publicly viewable. **Channel requests submitted without a working stream link will not be considered and will be closed.**
2. **Channel Information:**
   - Channel Name
   - Category / Genre (e.g., News, Sports, Entertainment)
   - Country / Target Region (must be US or US-accessible free-to-view)
3. **Proof of Free-to-Air Status:** Provide evidence (such as the official website) showing that the stream is free to the public without subscription, paywall, or authentication.
4. **No Piracy or Pay-TV:** Requests for subscription cable or premium channels (e.g., ESPN, HBO, CNN, Fox News, Disney Channel, regional sports networks) will be immediately rejected and closed.

To submit a request, navigate to the [Issues tab](https://github.com/cgyegcvcecvoc/m3u-channel-scrape/issues), click **New Issue**, and provide the details above.

---

## Reporting Broken or Malfunctioning Streams

If you find a stream that has stopped working, buffering indefinitely, or returning an error:

1. **Verify Locally First:** Ensure the issue is not caused by your local internet connection, media player cache, or a temporary broadcaster outage. Some streams may also be geo-restricted to the United States.
2. **Open a GitHub Issue:** Go to the [Issues tab](https://github.com/cgyegcvcecvoc/m3u-channel-scrape/issues) and select **New Issue**.
3. **Include the Following Details in Your Report:**
   - **Channel Name** and (if known) `tvg-id`
   - **Playlist File** where you encountered the issue (e.g., `usa-all.m3u`, `usa-news.m3u`)
   - **Stream URL** from the M3U file
   - **Error Description & Behavior:** (e.g., HTTP 404 Not Found, 403 Forbidden, SSL handshake failure, audio without video, black screen)
   - **Media Player & Operating System:** (e.g., VLC 3.0 on Windows 11, TiviMate on Android TV)
   - **Replacement Stream Link (Optional but Encouraged):** If you know of an updated official stream URL, please share it.

*Please note:* As stated in the disclaimers, the repository maintainer does not control external stream servers and **cannot provide immediate turnaround for dead streams**. Reported streams will be audited and either updated with a working replacement or removed in the next scheduled catalog refresh.

---

## EPG / XMLTV Guides

The playlists specify XMLTV electronic program guides via standard header tags. The primary US guide is:

```text
https://epg.pw/xmltv/epg_US.xml
```

The header additionally includes [i.mjh.nz](https://github.com/matthuisman/i.mjh.nz) XMLTV links for major FAST platforms (`PlutoTV/us.xml.gz`, `SamsungTVPlus/us.xml.gz`, `Roku/all.xml.gz`) in a comma-separated `x-tvg-url` list. IPTV players automatically match channels based on `tvg-id` (`*.us` IDs match epg.pw; platform-specific IDs match i.mjh.nz).

Refer to [generated/epg/links.txt](generated/epg/links.txt) and [generated/epg/links.json](generated/epg/links.json) for provider references and caveats. Upstream providers generate these XMLTV files independently; we do not host or alter schedule data. XMLTV `<channel id>` must match the playlist `tvg-id` for EPG integration.

---

## Refreshing Playlists Locally

Requirements: **Python 3.10+** (standard library only, no external pip dependencies needed).

```bash
# Run unit test suite
python3 -m unittest discover -s tests -v

# Regenerate playlists
python3 scripts/update_playlists.py
```

The updater reads [config/sources.json](config/sources.json), fetches upstream candidate sources ([iptv-org](https://github.com/iptv-org/iptv), [Free-TV](https://github.com/Free-TV/IPTV), and FAST platforms), and applies [config/policy.json](config/policy.json):
- Direct HTTPS HLS (`.m3u8` paths, no raw IP addresses, port 443 only)
- Strict host allowlist, verified CDN patterns, or reviewed ID+host pairs with documented evidence
- Exclusion of pay-TV channels, expiring tokens, custom auth headers, and VOD
- Multi-feed deduplication with secondary feeds routed to `usa-backups.m3u`

For Samsung TV Plus redirector feeds:
```bash
python3 scripts/resolve_redirects.py   # updates config/redirect_cache.json
python3 scripts/update_playlists.py
```

Host review standards and historical documentation are tracked in [RESEARCH.md](RESEARCH.md).

---

## Verifying Playback

To probe stream availability directly:

```bash
python3 scripts/verify_channels.py
```

The verifier contacts each stream URL, downloads the master manifest, parses a rendition media playlist, and downloads **one complete media segment** to verify valid container bytes (MPEG-TS, ISO-BMFF / MP4, ADTS). Results are written to [generated/verification.json](generated/verification.json) with verified channels output to [generated/playlists/usa-verified.m3u](generated/playlists/usa-verified.m3u).

---

## GitHub Automation

- [.github/workflows/refresh.yml](.github/workflows/refresh.yml): Runs on pushes to `arena/01a0db0b-m3u-channel-scrape`, daily at 06:17 UTC, and on manual dispatch. Resolves redirects, updates playlists, runs tests, and commits updated files.
- [.github/workflows/verify.yml](.github/workflows/verify.yml): Probes channel streams daily at 08:43 UTC and commits probe results.
- [.github/workflows/tests.yml](.github/workflows/tests.yml): Runs test suites on pushes and pull requests.

---

## Upstream Acknowledgments

- Upstream playlist feeds: [iptv-org](https://github.com/iptv-org/iptv), [Free-TV/IPTV](https://github.com/Free-TV/IPTV), and [BuddyChewChew/app-m3u-generator](https://github.com/BuddyChewChew/app-m3u-generator).
- XMLTV guide providers: [epg.pw](https://epg.pw/) and [matthuisman/i.mjh.nz](https://github.com/matthuisman/i.mjh.nz).
