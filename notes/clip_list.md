# TJR clips: clip list

Source: `sources/tjr_yt1.mkv`, the TJR vlog "taking delivery of my vintage Rolls-Royce Corniche" (34:02, 1920×1080, 23.976 fps).
All three clips come from the sit-down speech he gives to camera inside the car, in the garage (18:13–34:00).
Raw horizontal 1920×1080, H.264 CRF 18 + AAC 192k, original audio only, hard video cuts, 3-frame audio crossfade at each join.
Cut lists: `notes/specs/tjr_0N.json` (re-render: `python3 scripts/render.py notes/specs/tjr_0N.json`).

**Vertical captioned versions:** `clips/vertical/tjr_0N_<slug>_v.mp4`, 1080×1920
(`python3 scripts/render.py notes/specs/tjr_0N.json --vertical --captions`).
- 9:16 crop centred on TJR (face detected at x≈945 px in all three clips, steady ±40 px, so the crop is fixed with no jitter).
- Captions: one line at a time, white Inter SemiBold 64 px, soft blurred dark shadow, ~70 % down the frame (clear of TikTok/Reels bottom UI). Lines are hand-phrased in each spec (`caption_lines`); the renderer verifies they match the spoken words 1:1 and times them from word timestamps.
- Swear words are starred in captions only (f*ck, sh*t) for reach; audio is untouched. `--uncensored` prints them in full.

Ranked best → worst.

---

## 1. `clips/tjr_01_winners-lost-more.mp4`: 19.6 s
- **Source / timestamps:** tjr_yt1 33:25.7–33:41.7 → 33:46.0–33:49.5 (2 segments; skipped "you're going to make mistakes, you guys, you're going to lose")
- **Hook (first 2 s):** "Winners have lost more than losers ever have in their entire lives…"; TJR straight to camera, serious face.
- **Full text:** "Winners have lost more than losers ever have in their entire lives, because winners have fallen on their face so many times to understand what it takes to be a winner. You guys are going to fall, it's going to fucking hurt. But the only way that you truly lose is when you quit."
- **Why it should go viral:** it opens on a statement that sounds backwards, so people stop scrolling to hear the explanation. Then it pays off with a clean, quotable closing line. Works for anyone (trading, gym, business) and is highly shareable/saveable.
- **Hook text options:**
  1. Winners have lost MORE than losers
  2. Why winners fail more than you
  3. The only way you actually lose
- **Caption:** If you've been losing lately, you might be closer than you think. #TJR #trading #mindset #motivation #daytrading
- **Flags:** No logos/sponsors. Slight lighting shift (warmer) at the join at ~0:16, because the sun changed over the 5 s that were cut. Contains one f-word (unbleeped).

## 2. `clips/tjr_02_boss-you-hate.mp4`: 15.2 s
- **Source / timestamps:** tjr_yt1 28:53.6–29:05.0 → 28:49.1–28:52.8 (2 segments; the "imagine waking up…" line, said just before, is moved to the end as the payoff)
- **Hook (first 2 s):** "There's a small portion of time where you're going to have to work for a boss that you absolutely hate."
- **Full text:** "There's a small portion of time where you're going to have to work for a boss that you absolutely hate. But once you can break out of that and pursue something that you love, find a way to monetize it, that's when your life is going to change. Imagine just waking up and saying, hey, I get to do whatever the fuck I want to do today."
- **Why it should go viral:** It's about the 9–5, the campaign audience's #1 topic, and "boss you absolutely hate" is relatable and gets people commenting. It ends on an aspirational line instead of a lecture. Short, so it'll rewatch well.
- **Hook text options:**
  1. If you hate your boss, watch this
  2. How long you should stay at your 9–5
  3. The day your life actually changes
- **Caption:** Everyone starts somewhere. Not everyone leaves. #TJR #9to5 #money #entrepreneur #daytrading
- **Flags:** No logos/sponsors. The two sentences are in reverse order from how he said them (he said the "imagine" line ~1 s before); meaning unchanged. One f-word.

## 3. `clips/tjr_03_five-years.mp4`: 20.9 s
- **Source / timestamps:** tjr_yt1 28:23.6–28:26.2 (cold open) → 27:55.8–27:59.7 → 28:02.5–28:04.5 → 28:05.8–28:15.0 → 28:31.0–28:34.2 (5 segments)
- **Hook (first 2 s):** "Five years, man, I thought this was going to take a year." (Here he's voicing the viewer's reaction.)
- **Full text:** "Five years, man, I thought this was going to take a year. I was very interested in a hobby called day trading. I was absolutely obsessed with it. I fell on my face over and over and over again, lost a shit ton of money, but then I finally was able to make it work. And from there, it has taken me around five years. The journey is actually the most fun part about it."
- **Why it should go viral:** An honest timeline in a niche full of "overnight success" claims. Every trader recognizes "lost a ton of money". It's a mini story arc (obsession → failure → it works → 5 years) and invites "how long did it take you?" comments.
- **Hook text options:**
  1. How long trading REALLY took me
  2. It took me 5 years, not 1
  3. Before trading made me money…
- **Caption:** Nobody talks about how long it actually takes. #TJR #daytrading #trading #trader #money
- **Flags:** No logos/sponsors. Visible jump cuts at the joins (same shot, he moves between them), standard for talking-head content. "I was very interested in…" → "I was absolutely obsessed…": removed "and this was a side hustle hobby at the time, but" plus "I pursued it with a passion"; meaning unchanged.

---

### Why these three
1. **Winners lost more** is the best hook of the video: a counterintuitive one-liner with its own payoff. It needs zero context about TJR, so it travels outside his audience.
2. **Boss you hate** hits the audience's most-argued topic (9–5 vs. freedom) in 15 s, and the ending gives people something to want.
3. **Five years** is the strongest story beat; slightly less punchy than 1–2, but the most credible and comment-driving for a trading audience.

### Deliberately skipped from this source
- 24:44: mention of a suicide attempt; too sensitive to clip out of context.
- "Puerto Ricans aren't the best drivers" (3:50), "drink and drive" joke (6:27): risk making TJR look bad.
- "TJR bootcamp" mention (29:30): promo.
- Car-delivery section: Rolls-Royce badge visible in many shots (logo rule), and copyrighted music plays around 2:06.

### Backup ideas (not rendered)
- School hot take, 21:24–21:31 + 22:35–22:37: "Why am I learning this, I'm never going to use this in the real world… I wanna be a full-time day trader and I don't wanna go to college."
- "You need to be selfish in order to be selfless", 31:41–31:58.
- Car comedy, 13:59: "This is the equivalent of an 80-year-old trying to run a marathon" (check for logos).

---

## Edited vertical versions (`clips/edited/*_edit.mp4`)

`python3 scripts/edit.py notes/specs/tjr_0N.json`: built on top of the horizontal render (identical cuts/audio), 1080×1920.
- **Punch-in zooms** (pace matched to clip 02: a change every ~1–1.5 s, quick pull-outs, a hard punch on the final word) on emphasis lines (1.0 → 1.12–1.35×) with a small overshoot so each one lands; slow drift while held; a slow push-in on every closing line. The crop follows TJR's face (smoothed face tracking), so he stays framed at every zoom level.
- **B-roll cutaways** (video only; his voice keeps playing), all real TJR footage from the same vlog, him driving the convertible under palm trees, no Rolls-Royce badge in frame:
  - 01: 0:04.2–0:05.6 ("in their entire lives"), vlog 4:40; 0:08.4–0:10.0 ("so many times"), vlog 17:30
  - 02: 0:11.4–0:14.3 ("Imagine just waking up… I get to do"), vlog 16:05 + 4:30, then back on TJR for "I want to do today"
  - 03: 0:14.2–0:17.7 ("And from there… around five years"), vlog 9:55 + 17:30
  - In the B-roll shots he's talking to the camera, so his lips don't match the voice-over (normal for cutaways).
- **Captions (v4, "podcast" style, picked from `notes/caption_styles.jpg`):** clean lowercase Montserrat Bold with a soft shadow; one keyword per phrase swaps to a large Playfair Display italic serif; words appear as they're spoken (layout fixed, no shifting). Phrases = the hand-written `caption_lines`; keywords per clip in the spec (`keywords`). Drawn per frame by `scripts/captions.py` (styles `boxed`, `single`, `podcast`, `native` available via `caption_style`).
- Zoomed shots are upscaled up to ~2.3× from the 1080p source, slightly softer than the wide shots but fine on a phone.
- Other TJR videos as B-roll: YouTube blocks downloads from this server; upload them to Drive (like the first source) to use them.
