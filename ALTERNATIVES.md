# Free Alternatives to Requested Pay-TV Channels

**Session date:** 2026-09-26 (branch `arena/01a0ddf7-m3u-channel-scrape`)

This repository publishes **only** legal, free-to-air (FTA) and free
ad-supported streaming TV (FAST) channels. A request was made to add the
following channels. **None of them can be added as a free stream** — each is a
premium / subscription cable network with no authorized free-to-air feed. Adding
a "working link" for them would mean publishing an unauthorized rebroadcast,
which this project explicitly does not carry (see the
[README disclaimers](README.md#important-disclaimers) and
[`config/policy.json`](config/policy.json), where `ESPN.us`, `ESPN2.us` and
`ESPNU.us` are already on the exclusion list).

Instead of the pay-TV feeds, this file lists the **free, legal alternatives
already in the catalog** that cover the same genres.

---

## Requested channels and their status

| Requested channel | Type | Why it can't be a free stream | Free alternative genre |
| --- | --- | --- | --- |
| **ESPN** | Premium cable sports | Requires a TV/cable package; no FTA broadcast | Free sports FAST (below) |
| **ESPNU** | Premium cable sports (college) | Subscription only; already in `excluded_ids` | Free college/conference sports (below) |
| **Big Ten Network** | Subscription sports network | TV-provider login required; no free feed | Free college/conference sports (below) |
| **Disney Channel** | Premium cable (kids/family) | Subscription only; README rejects it explicitly | Free kids/family FAST (below) |
| **Disney XD** | Premium cable (kids/animation) | Subscription only (and winding down) | Free kids/animation FAST (below) |

---

## Free sports alternatives — for ESPN / ESPNU / Big Ten Network

Open **[`generated/playlists/usa-sports.m3u`](generated/playlists/usa-sports.m3u)**
(112 free sports channels). Closest substitutes:

**National sports news / talk / highlights**
- SportsGrid
- CBS Sports HQ
- Yahoo! Sports Network
- Roku Sports Channel
- NBC Sports NOW
- The Jim Rome Show
- FOX Sports (the free Pluto TV sports channel, *not* pay cable FS1)
- ESPN8: The Ocho (free Pluto TV homage channel)

**College / conference sports** (closest to ESPNU & Big Ten Network)
- Pac-12 Insider
- ACC Digital Network
- Big 12 Studios
- Scripps Sports Network
- NESN Nation
- PHLY Sports
- CHGO Sports

**Combat sports** (ESPN holds UFC/boxing rights; free alternatives)
- Bellator MMA, PFL, One Championship TV
- DAZN Ringside, Top Rank Classics, Zuffa Boxing Prelims, TVS Boxing

**Other free sports**
- NASCAR Channel, Formula 1 Channel, MotoGP Channel, Red Bull TV
- MLB Channel, MiLB, NFL Channel, NHL Network, The NBA Channel
- Tennis Channel, PGA TOUR, GolfPass, FIFA+, UEFA Champions League

---

## Free kids / family alternatives — for Disney Channel / Disney XD

Open **[`generated/playlists/usa-kids.m3u`](generated/playlists/usa-kids.m3u)**
(73 free kids channels). Closest substitutes:

**General kids / animation networks**
- Nickelodeon Pluto TV, Nick Jr. Pluto TV
- ToonGoggles, Kartoon Channel!, Moonbug
- PBS Kids (+ PBS Kids Alaska / Hawaii / Mountain / Pacific)

**Franchise / series channels** (Disney-style animation & action)
- Pokémon, Yu-Gi-Oh, Power Rangers, Transformers
- My Little Pony, Barbie and Friends, Hot Wheels Action
- LEGO Kids TV, The LEGO Channel
- Peppa Pig, Teletubbies, Strawberry Shortcake

**Preschool / younger**
- Baby Shark TV, Blippi, Super Simple Songs, Baby Einstein, Barney and Friends

**Retro / classic kids**
- 90's Kids, 90s Kids TV 2, Garfield and Friends, Johnny Test

---

## How to watch

Open any playlist in VLC (*Media → Open Network Stream*), mpv, Kodi, TiviMate,
or any IPTV player using the raw GitHub URL for **this branch**:

```text
https://raw.githubusercontent.com/cgyegcvcecvoc/m3u-channel-scrape/refs/heads/arena/01a0ddf7-m3u-channel-scrape/generated/playlists/usa-sports.m3u
https://raw.githubusercontent.com/cgyegcvcecvoc/m3u-channel-scrape/refs/heads/arena/01a0ddf7-m3u-channel-scrape/generated/playlists/usa-kids.m3u
```

Or browse them on GitHub:
[generated/playlists/usa-sports.m3u](generated/playlists/usa-sports.m3u) ·
[generated/playlists/usa-kids.m3u](generated/playlists/usa-kids.m3u) ·
[generated/playlists/usa-all.m3u](generated/playlists/usa-all.m3u)

---

## Verification note

Every URL in these playlists comes from a reviewed free publisher / FAST
platform (Pluto TV, Roku Channel, Samsung TV Plus, and other allow-listed hosts
in [`config/policy.json`](config/policy.json)) — never from a pay-TV restream.
The most recent automated playback probe
([`generated/verification.json`](generated/verification.json)) recorded
**1,322 of 1,409** catalog channels returning a real media segment
(`segment_ok`); the rest were `inconclusive` (transient network/geo) or a small
number `unavailable`. Streams are re-probed daily by the repo's *Verify* GitHub
Action, which runs from a runner that can reach the stream CDNs.
