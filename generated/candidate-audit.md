# Candidate source audit

Generated: `2026-09-26T15:52:59Z`

Entries are classified with the same policy code the updater uses (scripts/update_playlists.py). This report is evidence for host review, not an approval: nothing here publishes or changes policy.json.

> structural_rejects cannot be fixed by a host rule (plain HTTP, IP-literal host, non-443 port, expiring/credential query, non-HLS path). unreviewed_hosts can be approved after a host review with evidence.

**Totals:** 3938 candidate entries; 1979 publishable under the current policy; 488 blocked only by an unreviewed host; 1015 fail URL invariants; 456 blocked for other reasons.

## iptv-org US (community-submitted candidates)

- entries: **1464** (sha256 `5e0387fd41e4d09e…`)
- publishable now: **747**
- blocked only by host review: **472**
- URL invariant failures: **176** `{"non_443_port:8080": 44, "scheme:http": 32, "non_443_port:1935": 16, "non_443_port:8420": 11, "non_443_port:8989": 10, "non_443_port:1936": 10, "non_443_port:5000": 7, "non_443_port:8000": 6, "non_443_port:9997": 4, "non_443_port:444": 3, "non_443_port:9998": 3, "not_hls_path": 3, "non_443_port:5001": 3, "non_443_port:9953": 3, "non_443_port:8081": 2, "non_443_port:9002": 2, "non_443_port:9590": 2, "non_443_port:9060": 1, "non_443_port:2082": 1, "non_443_port:40000": 1, "non_443_port:3667": 1, "non_443_port:1943": 1, "non_443_port:8815": 1, "non_443_port:8298": 1, "non_443_port:4430": 1, "non_443_port:3238": 1, "non_443_port:5443": 1, "non_443_port:3000": 1, "non_443_port:3504": 1, "non_443_port:19360": 1, "non_443_port:8001": 1, "non_443_port:3943": 1}`
- other reasons: `{"not_us_or_no_id": 50, "custom_headers": 7, "dead_stream": 6, "not_direct_https_hls": 4, "duplicate_of_accepted_channel": 1, "excluded_pay_tv": 1}`
- entries whose name matches a pay-TV brand: 82
- entries that ask for spoofed `#EXTVLCOPT`/`#KODIPROP` headers: 10

### Unreviewed hosts (iptv-org US (community-submitted candidates))

| host | entries | distinct names | pay-TV-brand samples | samples |
| --- | ---: | ---: | ---: | --- |
| `2-fss-2.streamhoster.com` | 14 | 14 | 0 | AMG TV (1080p)<br>GoodLife 45 (720p) [Not 24/7]<br>Heartland (720p)<br>KSCE 38.1 (360p) |
| `mdc.ott.alticeusa.net` | 12 | 12 | 0 | News12 Bronx [Geo-blocked]<br>News12 Brooklyn [Geo-blocked]<br>News12 Conneticut [Geo-blocked]<br>News12 Hudson Valley [Geo-blocked] |
| `a-cdn.klowdtv.com` | 11 | 11 | 0 | AWE (720p)<br>AWE International (720p)<br>Cine Sony (720p)<br>Game Show Network (720p) [Not 24/7] |
| `dlttx48mxf9m3.cloudfront.net` | 9 | 9 | 0 | AMP 1 (720p)<br>AMP 2 (720p)<br>CVC Education (480p)<br>CVC Government (480p) |
| `2-fss-1.streamhoster.com` | 8 | 8 | 0 | Ace TV KCKS-LD (720p)<br>Biz TV (1080p)<br>Create WMPT<br>Genesis Science Network (720p) |
| `d368vp0qqzvkid.cloudfront.net` | 7 | 7 | 2 | NBC KNTV (1080p)<br>NBC KXAS-TV (1080p)<br>NBC WBTS-CD (1080p)<br>NBC WMAQ-TV (1080p) |
| `streaming-live-fcdn.api.prd.univisionnow.com` | 7 | 7 | 0 | Galavision East HD (1080p) [Geo-blocked]<br>Galavision West HD (1080p) [Geo-blocked]<br>UniMas KFTR-DT [Geo-blocked]<br>UniMas KUVN-DT |
| `cdn.vegasplus.us` | 6 | 6 | 0 | Asian Culture TV (1080p)<br>FilAmTV Network (1080p)<br>Las Vegas Tonight with Dale Davidson (1080p)<br>Latino Channel TV (1080p) |
| `mediaserver.abnvideos.com` | 6 | 6 | 0 | ABN Afghanistan (540p)<br>ABN Africa (480p)<br>ABN Bible Movies Channel (720p)<br>ABN China (720p) |
| `townnews.g-mana.live` | 6 | 6 | 0 | ABC WTVQ-DT (720p)<br>ABC WWAY<br>CBS WCBI-TV (720p)<br>CBS WDEF-TV (720p) |
| `vodcdn.bamboo-cloud.com` | 6 | 6 | 0 | S Corby TV (480p)<br>S Free! (360p)<br>S KPop! (480p)<br>S Metro TV (360p) |
| `5c2974786200d.streamlock.net` | 5 | 5 | 0 | Midpen Media Center Channel 26 (720p)<br>Midpen Media Center Channel 28 (720p)<br>Midpen Media Center Channel 29 (720p)<br>Midpen Media Center Channel 30 (720p) |
| `castus-vod-dev.s3.amazonaws.com` | 5 | 5 | 0 | ACTV (United States)<br>Akaku 53 (1080p)<br>Akaku 54 (1080p)<br>Akaku 55 (1080p) |
| `cdn.whiplash.cc` | 5 | 5 | 0 | Atlas (480p)<br>Whiplash (720p)<br>Whiplash Cinema (480p)<br>Whiplash II (480p) |
| `securestream11.champds.com` | 5 | 5 | 0 | ATL 26<br>FGTV (United States)<br>Gillette Public Access Television Channel 189<br>Gillette Public Access Television Channel 190 |
| `58cc65c534c67.streamlock.net` | 4 | 4 | 0 | Alkarma TV Family (1080p) [Not 24/7]<br>Alkarma TV Middle East (1080p) [Not 24/7]<br>Alkarma TV Praise (720p) [Not 24/7]<br>Alkarma TV Talmaza Discipleship (1080p) [Not 24/ |
| `59d39900ebfb8.streamlock.net` | 4 | 4 | 0 | Dega TV (720p) [Not 24/7]<br>Radio Tele Kajou (480p) [Not 24/7]<br>Radio Tele Sentinel<br>Radio Tele Wisdom (360p) [Not 24/7] |
| `5aafcc5de91f1.streamlock.net` | 4 | 4 | 0 | Alkarma TV North America & Canada (1080p) [Not 2<br>Alkarma TV Youth & English (1080p) [Not 24/7]<br>Almagd TV North America (1080p)<br>Logos TV English (1080p) [Not 24/7] |
| `cantv.streamguys1.com` | 4 | 4 | 0 | CAN TV19 (1080p)<br>CAN TV21 (1080p)<br>CAN TV27 (1080p)<br>CAN TV36 (1080p) |
| `fuel-streaming-prod01.fuelmedia.io` | 4 | 4 | 0 | ABC KITV (720p)<br>CBS KWTV-DT (720p) [Not 24/7]<br>TLN Media Chicago (720p)<br>TLN Media San Francisco (720p) |
| `jstre.am` | 4 | 4 | 0 | Hope Channel Inter-America<br>Hope Channel Inter-America English (1080p)<br>Hope Channel International (1080p)<br>Hope Channel North America (1080p) |
| `shd-gcp-live.edgenextcdn.net` | 4 | 4 | 0 | MBC 1 USA (1080p) [Geo-blocked]<br>MBC 3 USA (1080p) [Geo-blocked]<br>MBC Drama USA (1080p)<br>MBC Masr USA (1080p) |
| `sra72yz.s.gy` | 4 | 4 | 2 | Cinemax Action East HD (1080p)<br>HBO Drama (1080p)<br>Nick Jr. (United States) East HD (1080p)<br>Nicktoons (United States) (1080p) |
| `stream.ads.ottera.tv` | 4 | 4 | 0 | Camp Spoopy (576p)<br>El Rey<br>Novelisima<br>Smurf TV (480p) |
| `streamer1.connectto.com` | 4 | 4 | 0 | AMGA TV (720p) [Not 24/7]<br>ARTN TV (1080p) [Not 24/7]<br>High Vision TV (1080p) [Not 24/7]<br>KIIO-LD 10.4 (480p) |

Other blocker explanations:

- `dead_stream` — listed in DEFUNCT_STREAMS (known dead)
- `not_us_or_no_id` — no US-style tvg-id (and source is not a platform-ID feed)
- `custom_headers` — stream needs referrer/user-agent overrides
- `excluded_pay_tv` — channel ID is on the pay-TV exclusion list

## Free-TV US (curated candidates, not a rights guarantee)

- entries: **28** (sha256 `c82e07f39c8c6597…`)
- publishable now: **9**
- blocked only by host review: **11**
- URL invariant failures: **5** `{"expiring_or_credential_query": 2, "non_443_port:8080": 1, "not_hls_path": 1, "scheme:http": 1}`
- other reasons: `{"dead_stream": 2, "excluded_pay_tv": 1}`
- entries whose name matches a pay-TV brand: 0
- entries that ask for spoofed `#EXTVLCOPT`/`#KODIPROP` headers: 0

### Unreviewed hosts (Free-TV US (curated candidates, not a rights guarantee))

| host | entries | distinct names | pay-TV-brand samples | samples |
| --- | ---: | ---: | ---: | --- |
| `lukentvlive.vgcdn.net` | 3 | 3 | 0 | Heartland<br>Retro TV<br>Rev'n |
| `2-fss-1.streamhoster.com` | 1 | 1 | 0 | Biz TV |
| `bcovlive-a.akamaihd.net` | 1 | 1 | 0 | Stadium |
| `cinedigm.vo.llnwd.net` | 1 | 1 | 0 | Docurama |
| `d1bl6tskrpq9ze.cloudfront.net` | 1 | 1 | 0 | NBC News |
| `fffffff110156200.tvustream.com` | 1 | 1 | 0 | Stryk TV |
| `hls.livecdn.io` | 1 | 1 | 0 | Cheddar |
| `live.gideo.video` | 1 | 1 | 0 | America TeVe |
| `nmxlive.akamaized.net` | 1 | 1 | 0 | Newsmax TV |

Other blocker explanations:

- `excluded_pay_tv` — channel ID is on the pay-TV exclusion list
- `dead_stream` — listed in DEFUNCT_STREAMS (known dead)

## Pluto TV US (FAST platform lineup via jmp2.uk to Pluto's official embed manifests)

- entries: **431** (sha256 `f633936b4c1efb04…`)
- publishable now: **428**
- blocked only by host review: **0**
- URL invariant failures: **0** `{}`
- other reasons: `{"duplicate_of_accepted_channel": 3}`
- entries whose name matches a pay-TV brand: 31
- entries that ask for spoofed `#EXTVLCOPT`/`#KODIPROP` headers: 0

## Roku Channel lineup (FAST platform via jmp2.uk to Roku's CDN manifests)

- entries: **232** (sha256 `4842986a075e6f6f…`)
- publishable now: **231**
- blocked only by host review: **1**
- URL invariant failures: **0** `{}`
- other reasons: `{}`
- entries whose name matches a pay-TV brand: 4
- entries that ask for spoofed `#EXTVLCOPT`/`#KODIPROP` headers: 0

### Unreviewed hosts (Roku Channel lineup (FAST platform via jmp2.uk to Roku's CDN manifests))

| host | entries | distinct names | pay-TV-brand samples | samples |
| --- | ---: | ---: | ---: | --- |
| `d3868b4ny0rgdf.cloudfront.net` | 1 | 1 | 0 | Ninja Kidz TV |

## Samsung TV Plus US (FAST platform; jmp2.uk URLs resolved via redirect cache)

- entries: **581** (sha256 `588f48574748df5b…`)
- publishable now: **539**
- blocked only by host review: **3**
- URL invariant failures: **39** `{"not_hls_path": 39}`
- other reasons: `{}`
- entries whose name matches a pay-TV brand: 21
- entries that ask for spoofed `#EXTVLCOPT`/`#KODIPROP` headers: 0

### Unreviewed hosts (Samsung TV Plus US (FAST platform; jmp2.uk URLs resolved via redirect cache))

| host | entries | distinct names | pay-TV-brand samples | samples |
| --- | ---: | ---: | ---: | --- |
| `dai.google.com` | 3 | 3 | 0 | CBS News 24/7<br>CBS Sports HQ<br>ET |

## aria-tv/aria (user-suggested candidates; reviewed entries only)

- entries: **418** (sha256 `85879c7de4cd152a…`)
- publishable now: **12**
- blocked only by host review: **0**
- URL invariant failures: **263** `{"scheme:http": 46, "non_443_port:9981": 35, "non_443_port:9000": 33, "non_443_port:9091": 27, "non_443_port:8000": 22, "non_443_port:1234": 21, "non_443_port:81": 18, "non_443_port:8080": 16, "not_hls_path": 13, "non_443_port:8888": 7, "non_443_port:8420": 4, "non_443_port:8089": 3, "non_443_port:9700": 3, "non_443_port:9998": 3, "non_443_port:9002": 2, "non_443_port:4200": 2, "non_443_port:1936": 2, "non_443_port:1935": 2, "non_443_port:8083": 1, "non_443_port:10205": 1, "non_443_port:10206": 1, "non_443_port:9590": 1}`
- other reasons: `{"not_us_or_no_id": 143}`
- entries whose name matches a pay-TV brand: 53
- entries that ask for spoofed `#EXTVLCOPT`/`#KODIPROP` headers: 0

Other blocker explanations:

- `not_us_or_no_id` — no US-style tvg-id (and source is not a platform-ID feed)

## doms9/iptv (user-suggested candidates; reviewed entries only)

- entries: **784** (sha256 `53d26cc1430d86e2…`)
- publishable now: **13**
- blocked only by host review: **1**
- URL invariant failures: **532** `{"expiring_or_credential_query": 205, "expiring_or_credential_query(pay_tv_brand)": 189, "scheme:http": 78, "non_443_port:8080": 46, "non_443_port:8989": 4, "not_hls_path": 4, "non_443_port:9590": 2, "non_443_port:4430": 1, "non_443_port:4004": 1, "non_443_port:4007": 1, "non_443_port:80": 1}`
- other reasons: `{"custom_headers": 203, "not_us_or_no_id": 35}`
- entries whose name matches a pay-TV brand: 254
- entries that ask for spoofed `#EXTVLCOPT`/`#KODIPROP` headers: 671

### Unreviewed hosts (doms9/iptv (user-suggested candidates; reviewed entries only))

| host | entries | distinct names | pay-TV-brand samples | samples |
| --- | ---: | ---: | ---: | --- |
| `d3ehq1uaxory6w.cloudfront.net` | 1 | 1 | 0 | FanDuel Racing |

Other blocker explanations:

- `not_us_or_no_id` — no US-style tvg-id (and source is not a platform-ID feed)
- `custom_headers` — stream needs referrer/user-agent overrides
