# m3u-channel-scrape

**Free-viewing US TV playlists, refreshed from public candidate feeds into this GitHub work branch.**

This checkout originally contained only a README; the earlier M3U Forge dataset described in chat was **not in this repository**. These are newly generated files, not a copy of a claimed 10,000+ channel database. As of the first build there are **248 host-allowlisted US listings** (8 sports, 35 news, 6 marked intermittent); counts can change on refresh. See the live [manifest](generated/manifest.json) rather than relying on a fixed count.

> Public URL ≠ permission to restream. This project does **not** carry cable subscriptions, DRM keys, pay-TV mirrors, captured credentials, VOD, or proxy bypasses. Streams are links to other publishers, not video hosted here. Publisher terms, regional restrictions and playback can change; the host review is a best-effort filter, **not a guarantee** that every link is authorized or works in your location.

## Download / play

Open an M3U link in VLC (Media → Open Network Stream) or import it in an IPTV player. Direct GitHub RAW URL for the US playlist on **this work branch**:

```text
https://raw.githubusercontent.com/cgyegcvcecvoc/m3u-channel-scrape/refs/heads/arena/01a0da01-m3u-channel-scrape/generated/playlists/usa-all.m3u
```

Replace `usa-all.m3u` with a filename below for smaller playlists. Files are also available in [generated/playlists/](generated/playlists/):

| Playlist | Contents |
| --- | --- |
| [usa-all.m3u](generated/playlists/usa-all.m3u) | Reviewed US live streams |
| [usa-news.m3u](generated/playlists/usa-news.m3u) | Free news / local news |
| [usa-sports.m3u](generated/playlists/usa-sports.m3u) | Free sports FAST/talk/highlights; **not** paid ESPN/FS1 feeds |
| [usa-local.m3u](generated/playlists/usa-local.m3u) | Local/public-access/municipal/free local news |
| [usa-intermittent.m3u](generated/playlists/usa-intermittent.m3u) | Sources marked **Not 24/7**; a stream may be off air between events |
| [usa-movies.m3u](generated/playlists/usa-movies.m3u) · [usa-entertainment.m3u](generated/playlists/usa-entertainment.m3u) · [usa-kids.m3u](generated/playlists/usa-kids.m3u) · [usa-music.m3u](generated/playlists/usa-music.m3u) | Other free-viewing categories |

Each UTF-8 file starts with `#EXTM3U` and an XMLTV guide URL, then pairs `#EXTINF:-1 tvg-id="…" tvg-name="…" tvg-logo="…" group-title="…",Name` with one HTTPS `.m3u8` stream URL. `tvg-id` drops quality-only suffixes (such as `@SD`) but keeps regional feed IDs (such as `@KEROTV`) rather than assigning the wrong local TV schedule. **An HTTP link check is not proof of playback or rights; no streams were live-probed here.** Actual channel totals and the UTC generation timestamp are in [generated/manifest.json](generated/manifest.json); individual source and approval evidence is in [generated/channels.json](generated/channels.json). Do not assume thousands of US pay-cable networks have authorized free HLS streams.

## EPG / XMLTV

The playlists reference this **external** US guide (plain XML):

```text
https://epg.pw/xmltv/epg_US.xml
```

[generated/epg/links.txt](generated/epg/links.txt) also has the `.xml.gz` option; [generated/epg/links.json](generated/epg/links.json) records the provider and caveats. The provider [publishes these XMLTV links](https://epg.pw/xmltv.html?lang=en) and updates its own guide. We do **not** copy its schedule into GitHub or claim redistribution rights. XMLTV `<channel id>` must equal a playlist's `tvg-id` for automatic schedule matching; this third-party guide may use different IDs. If your player shows an empty guide, map IDs in your player or select a guide with matching IDs. The often-copied `iptv-org.github.io/epg/guides/us.xml` link is **404**, so it is not used here. An EPG link is not a channel stream.

## Refresh locally

Python **3.10+**, standard library only:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/update_playlists.py
```

The updater reads [config/sources.json](config/sources.json), fetches the [iptv-org US playlist](https://github.com/iptv-org/iptv) and [Free-TV's US playlist](https://github.com/Free-TV/IPTV), and falls back to GitHub's public contents API if raw/GitHub Pages is unavailable. These are **candidate** sources, not a legal clearance. It applies [config/policy.json](config/policy.json): US XMLTV ID, reviewed exact DNS host/host suffix or reviewed ID+host with a publisher/free-service page, HTTPS direct HLS, no credentials/signed-token or partner/device-impersonation URLs, no custom-header workarounds, no VOD, and an explicit exclusion list for pay-TV IDs. Unknown new domains are **not** silently accepted. It deduplicates on channel ID and stream URL, normalizes metadata, and writes the files in `generated/` only after all required sources succeed. Large unexplained drops are refused so a bad download cannot replace good playlists.

To add a genuinely free channel, find the publisher's own free-viewing page and a direct HLS feed it permits viewers to access; add a candidate M3U source in `config/sources.json` and a **narrow**, reviewed host or exact channel ID+host with `evidence_url` in `config/policy.json`. Check publisher terms and territory. Do **not** approve a generic CDN, an unauthorized cable restream, a proxy to defeat service restrictions, or a pay-TV channel just because it returns 200. Changes to the policy and EPG provider [config/epg.json](config/epg.json) are reviewed by people rather than automatically discovered from random web pages. `--allow-shrink` overrides the 40% shrink guard **only after** investigating it. Scheduled runs do not use this override.

## GitHub automatic updates

[.github/workflows/refresh.yml](.github/workflows/refresh.yml) runs **daily around 06:17 UTC** and on manual dispatch, runs tests, regenerates playlists/EPG-link files, and commits **only changed `generated/` files to `arena/01a0da01-m3u-channel-scrape`**. No extra secret/PAT is needed: it uses `GITHUB_TOKEN` (repository Actions setting must allow `contents: write`). [tests.yml](.github/workflows/tests.yml) checks code on work-branch pushes and pull requests. GitHub may delay or disable scheduled jobs; this is daily refresh, not real-time monitoring.

**Activation:** GitHub `schedule` and `workflow_dispatch` require the workflow file on the repository's **default branch**. This work-branch copy will not self-schedule until its workflow is merged into `main` (or installed on the default branch by the maintainer). After that, its checkout and push still target **only the Arena work branch**, not `main`; you can merge subsequent updates when ready. If a bot push is denied by branch protection or Actions token permissions, check repository Settings → Actions → General / branch rules. Until activation, run the local command to update manually and push this branch.

Upstream playlist maintainers: [iptv-org](https://github.com/iptv-org/iptv) and [Free-TV/IPTV](https://github.com/Free-TV/IPTV). Guide provider: [epg.pw](https://epg.pw/xmltv.html?lang=en). Please report any stream that is subscription-only, misattributed or not intended for direct access; it should be removed from the allowlist.
