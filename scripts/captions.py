#!/usr/bin/env python3
"""Caption styles drawn with PIL straight onto the frame (used by edit.py).

draw(img, words, active, style, age) -> img
  img     PIL RGB image 1080x1920 (modified copy returned)
  words   list of display strings for the current chunk
  active  index of the word being spoken
  age     seconds since the chunk appeared (drives the pop-in)

Styles:
  boxed    Poppins ExtraBold caps, white w/ black stroke; the spoken word sits
           on a rounded green box (Submagic/Hormozi look). 2-3 words.
  single   One word at a time, huge Anton caps, thick stroke; keywords yellow.
  podcast  Clean lowercase Montserrat with soft shadow; keywords swap to a
           large Playfair Display italic serif; words appear as spoken (layout fixed).
  native   TikTok-native: black Poppins Bold on a white rounded pill.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS = Path(__file__).resolve().parent.parent / "fonts"
W, H = 1080, 1920
# TikTok/Reels safe area: the right ~140 px hold the like/comment/share buttons
# and the bottom ~25 % the username/description, so captions stay inside a
# centred SAFE_W box (140 px margin each side) and above y = 0.75 H.
SAFE_W = 800
MIN_FIT = 0.8   # shrink down to 80 %, beyond that wrap onto two lines
_cache = {}


def font(name, size, weight=None):
    key = (name, size, weight)
    if key not in _cache:
        f = ImageFont.truetype(str(FONTS / name), size)
        if weight:
            f.set_variation_by_axes([weight])
        _cache[key] = f
    return _cache[key]


STYLES = {
    "boxed":   dict(chunk=3, chars=16, upper=True, y=0.66),
    "single":  dict(chunk=1, chars=99, upper=True, y=0.64),
    "podcast": dict(chunk=6, chars=27, upper=False, y=0.68),
    "native":  dict(chunk=4, chars=20, upper=False, y=0.70),
}
GREEN, YELLOW = (34, 197, 94), (255, 225, 77)


def _pop(age, dur=0.12, start=0.82):
    u = min(max(age / dur, 0), 1)
    return start + (1 - start) * (1 - (1 - u) ** 3)


def _shadow(img, draw_fn, blur=8, alpha=150, offset=(0, 5)):
    """Draw a soft drop shadow of whatever draw_fn draws (in black)."""
    m = Image.new("L", img.size, 0)
    draw_fn(ImageDraw.Draw(m), 255)
    m = m.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: v * alpha // 255)
    sh = Image.new("RGB", img.size, (0, 0, 0))
    img.paste(sh, offset, m)


def _layout(parts, gap):
    """parts: list of (text, font). Returns total width and per-part x offsets."""
    ws = [f.getbbox(t)[2] - f.getbbox(t)[0] for t, f in parts]
    xs, x = [], 0
    for w in ws:
        xs.append(x); x += w + gap
    return x - gap, xs, ws


def draw(img, words, active, style, age=1.0, keywords=()):
    img = img.copy()
    st = STYLES[style]
    s = _pop(age)
    cy = int(H * st["y"])
    kw = {k.lower() for k in keywords}
    bare = lambda t: "".join(c for c in t.lower() if c.isalnum() or c == "'")

    if style == "boxed":
        f = font("Poppins-ExtraBold.ttf", int(78 * s))
        parts = [(w.upper(), f) for w in words]
        tw, xs, ws = _layout(parts, int(20 * s))
        if tw > SAFE_W:
            f = font("Poppins-ExtraBold.ttf", int(78 * s * SAFE_W / tw))
            parts = [(w.upper(), f) for w in words]
            tw, xs, ws = _layout(parts, int(20 * s * SAFE_W / tw))
        x0 = (W - tw) // 2
        asc = f.getbbox("H")
        d = ImageDraw.Draw(img)
        bx = x0 + xs[active]
        d.rounded_rectangle([bx - 18, cy + asc[1] - 16, bx + ws[active] + 18, cy + asc[3] + 18],
                            radius=18, fill=GREEN)
        for (t, f_), x in zip(parts, xs):
            d.text((x0 + x, cy), t, font=f_, fill="white", stroke_width=6, stroke_fill="black")
        return img

    if style == "single":
        t = words[active].upper()
        f = font("Anton-Regular.ttf", int(150 * s))
        if f.getbbox(t)[2] - f.getbbox(t)[0] > SAFE_W:
            f = font("Anton-Regular.ttf", int(150 * s * SAFE_W / (f.getbbox(t)[2] - f.getbbox(t)[0])))
        col = YELLOW if bare(t) in kw else (255, 255, 255)
        bb = f.getbbox(t)
        x = (W - (bb[2] - bb[0])) // 2 - bb[0]
        _shadow(img, lambda d, v: d.text((x, cy), t, font=f, fill=v, stroke_width=10, stroke_fill=v),
                blur=10, alpha=170, offset=(0, 8))
        ImageDraw.Draw(img).text((x, cy), t, font=f, fill=col, stroke_width=9, stroke_fill="black")
        return img

    if style == "podcast":
        def build(ws, k):
            parts = []
            for w in ws:
                t = w.lower().strip(",.")
                if bare(w) in kw:
                    parts.append((t, font("PlayfairDisplay-Italic[wght].ttf", int(96 * k), 600)))
                else:
                    parts.append((t, font("Montserrat[wght].ttf", int(64 * k), 700)))
            return parts, _layout(parts, int(18 * k))

        def fit(ws):
            parts, (tw, xs, _) = build(ws, s)
            if tw > SAFE_W:
                parts, (tw, xs, _) = build(ws, s * SAFE_W / tw)
            return parts, tw, xs

        _, (tw, _, _) = build(words, s)
        if tw <= SAFE_W / MIN_FIT or len(words) < 2:
            rows = [(words, 0)]
        else:  # two balanced lines
            cut = min(range(1, len(words)),
                      key=lambda k: abs(build(words[:k], s)[1][0] - build(words[k:], s)[1][0]))
            rows = [(words[:cut], 0), (words[cut:], cut)]
        laid = []
        for r, (ws, first) in enumerate(rows):
            parts, tw, xs = fit(ws)
            base = cy + 70 + (r - (len(rows) - 1)) * int(88 * s)
            laid += [(parts[k], ((W - tw) // 2 + xs[k], base), first + k) for k in range(len(ws))]
        shown = [(pt, ps) for pt, ps, idx in laid if idx <= active]  # appear as spoken

        def txt(d, v):
            for (t, f_), (x, y) in shown:
                d.text((x, y), t, font=f_, fill=v, anchor="ls")
        _shadow(img, txt, blur=9, alpha=205, offset=(0, 4))
        txt(ImageDraw.Draw(img), (255, 255, 255))
        return img

    if style == "native":
        f = font("Poppins-Bold.ttf", int(60 * s))
        t = " ".join(words)
        if f.getbbox(t)[2] - f.getbbox(t)[0] > SAFE_W - 56:
            f = font("Poppins-Bold.ttf", int(60 * s * (SAFE_W - 56) / (f.getbbox(t)[2] - f.getbbox(t)[0])))
        bb = f.getbbox(t)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        x = (W - tw) // 2
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([x - 28, cy + bb[1] - 20, x + tw + 28, cy + bb[3] + 22], radius=22,
                            fill=(255, 255, 255))
        d.text((x - bb[0], cy), t, font=f, fill=(15, 15, 15))
        return img
    raise ValueError(style)
