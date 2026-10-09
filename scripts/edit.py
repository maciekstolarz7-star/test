#!/usr/bin/env python3
"""Vertical "edited" version of a clip: punch-in zooms, B-roll cutaways,
captions with emphasis words.

Takes the horizontal clip made by render.py (spec["out"]) as the A-roll, so
cuts, audio and crossfades are identical; this only re-frames the picture.

Spec additions (all optional):
  "zoom":  [{"t": 0.0, "z": 1.25}, {"t": 1.86, "z": 1.0},
            {"t": 16.1, "z": 1.3, "ease": 3.4}, ...]
           t = output seconds. Without "ease" the change is a hard punch with a
           small overshoot; with "ease" it glides there over that many seconds.
  "broll": [{"at": 11.38, "dur": 1.6, "src": "sources/x.mkv", "t": 965.0,
             "cx": 820, "z": 1.0, "z2": 1.08}]
           Cutaway (video only, voice keeps playing) from src at time t,
           9:16 crop centred on source x = cx, slow push from z to z2.

Usage: python3 scripts/edit.py notes/specs/tjr_01.json [--uncensored]
Output: clips/edited/<name>_edit.mp4 (1080x1920)
"""
import argparse, json, subprocess, sys, tempfile
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render  # noqa: E402

ROOT = render.ROOT
OW, OH = 1080, 1920
FACE_AT = 0.40          # face height in the frame (fraction from top) when zoomed
OVERSHOOT, SETTLE = 0.05, 0.18
DRIFT = 0.010           # slow push per second while a zoom level is held
ACCENT = "&H4DE1FF&"    # emphasis colour (BGR) = #FFE14D


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,r_frame_rate,nb_frames", "-of", "json", str(path)],
                       capture_output=True, text=True, check=True)
    s = json.loads(r.stdout)["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    return s["width"], s["height"], float(num) / float(den)


def reader(path, w, h, ss=None, dur=None):
    cmd = ["ffmpeg", "-v", "error"]
    if ss is not None:
        cmd += ["-ss", f"{ss:.3f}"]
    cmd += ["-i", str(path)]
    if dur is not None:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    try:
        while True:
            buf = p.stdout.read(w * h * 3)
            if len(buf) < w * h * 3:
                break
            yield np.frombuffer(buf, np.uint8).reshape(h, w, 3)
    finally:  # closed early (B-roll window over): stop ffmpeg quietly
        p.kill(); p.wait()


def face_track(path, w, h, fps, default_x):
    """Face centre per frame (smoothed); falls back to default_x / mid-height."""
    casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    pts = []
    for i, fr in enumerate(reader(path, w // 2, h // 2)):
        if i % 4:
            continue
        fs = casc.detectMultiScale(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY), 1.1, 5, minSize=(50, 50))
        if len(fs):
            x, y, fw, fh = max(fs, key=lambda r: r[2] * r[3])
            pts.append((i, (x + fw / 2) * 2, (y + fh / 2) * 2))
    n = i + 1
    if not pts:
        return np.full(n, default_x), np.full(n, h * 0.4)
    idx, xs, ys = map(np.array, zip(*pts))
    fx, fy = np.interp(np.arange(n), idx, xs), np.interp(np.arange(n), idx, ys)
    k = max(1, int(fps * 0.8))  # ~0.8 s smoothing: follows him without jitter
    ker = np.ones(k) / k
    pad = lambda a: np.pad(a, (k, k), mode="edge")
    return (np.convolve(pad(fx), ker, "same")[k:-k], np.convolve(pad(fy), ker, "same")[k:-k])


def ease(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def zoom_at(t, keys):
    """Zoom factor at output time t from the keyframe list."""
    z, last_t = 1.0, 0.0
    prev = 1.0
    for k in keys:
        if k["t"] > t:
            break
        prev, last_t = z, k["t"]
        if k.get("ease"):
            z = prev + (k["z"] - prev) * ease((t - k["t"]) / k["ease"])
        else:
            u = (t - k["t"]) / SETTLE
            z = k["z"] * (1 + OVERSHOOT * (1 - ease(u))) if k["z"] > prev + 0.02 else k["z"]
    held = t - last_t
    return z * (1 + min(DRIFT * held, 0.04))


def frame_crop(img, cx, cy, z):
    """9:16 window of the frame, zoom z (1 = full height), face at FACE_AT."""
    h, w = img.shape[:2]
    wh = h / z
    ww = wh * 9 / 16
    x0 = min(max(cx - ww / 2, 0), w - ww)
    y0 = min(max(cy - FACE_AT * wh, 0), h - wh) if z > 1.001 else 0
    s = OH / wh
    m = np.float32([[s, 0, -x0 * s], [0, s, -y0 * s]])
    return cv2.warpAffine(img, m, (OW, OH), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


CHUNK_CHARS = 17        # max characters per caption chunk (uppercase, 76 px)


def chunks_of(lines):
    """Chunk the whole clip's words (DP): chunks of <= 3 words (4 if short) / CHUNK_CHARS,
    never across a sentence end or a cut, preferring caption-line boundaries,
    avoiding lone short words and uneven sizes."""
    words, line_end, hard = [], [], []
    for ln in lines:
        for k, w in enumerate(ln):
            words.append(w)
            line_end.append(k == len(ln) - 1)
            hard.append(bool(render.re.search(r"[.?!]$", w["w"])))
    for i in range(len(words) - 1):  # a cut right after word i is a hard break
        if words[i + 1].get("cut"):
            hard[i] = True
    n = len(words)

    def cost(i, j):  # chunk = words[i:j]
        ws = words[i:j]
        ln = len(" ".join(w["w"] for w in ws))
        if len(ws) > (4 if ln <= 15 else 3) or (ln > CHUNK_CHARS and len(ws) > 1) or any(hard[i:j - 1]):
            return None
        c = (ln - 11) ** 2 * 0.3
        if len(ws) == 1 and len(ws[0]["w"]) <= 5:
            c += 60
        if j < n and not line_end[j - 1]:
            c += 25
        return c

    best = [(0, [])] + [None] * n
    for j in range(1, n + 1):
        for i in range(max(0, j - 4), j):
            c = cost(i, j)
            if c is not None and best[i] is not None:
                cand = (best[i][0] + c, best[i][1] + [(i, j)])
                if best[j] is None or cand[0] < best[j][0]:
                    best[j] = cand
    return [words[i:j] for i, j in best[n][1]]


def captions(spec, ass_path, uncensored):
    """Bold short-form captions: 2-3 words at a time, uppercase, black outline;
    the word being spoken turns yellow and grows slightly; each chunk pops in."""
    segs = spec["segments"]
    cache = {}
    for s in segs:
        src = ROOT / s["src"]
        cache.setdefault(src, render.words_for(src))
        s["_cut"] = render.snap(s["start"], s["end"], cache[src])
    words, total = render.caption_words(segs, cache, uncensored)
    lines = (render.manual_lines(words, spec["caption_lines"], uncensored)
             if spec.get("caption_lines") else render.caption_lines(words))
    clean = lambda t: render.re.sub(r"[,.;:]+$", "", t).upper()
    chunks = chunks_of(lines)
    ev = []
    for ci, ch in enumerate(chunks):
        c_start = ch[0]["s"]
        nxt = chunks[ci + 1][0]["s"] if ci + 1 < len(chunks) else total
        c_end = min(nxt, ch[-1]["e"] + 0.35)
        for k, w in enumerate(ch):
            st = c_start if k == 0 else w["s"]
            en = ch[k + 1]["s"] if k + 1 < len(ch) else c_end
            if en - st < 0.02:
                continue
            toks = [f"{{\\c{ACCENT}\\fscx106\\fscy106}}{clean(x['w'])}{{\\c&HFFFFFF&\\fscx100\\fscy100}}"
                    if j == k else clean(x["w"]) for j, x in enumerate(ch)]
            pop = "{\\fscx82\\fscy82\\t(0,110,\\fscx100\\fscy100)}" if k == 0 else ""
            ev.append(f"Dialogue: 0,{render.ass_time(st)},{render.ass_time(en)},Cap,,0,0,0,,{pop}{' '.join(toks)}")
    ass_path.write_text(f"""[Script Info]
ScriptType: v4.00+
PlayResX: {OW}
PlayResY: {OH}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Inter Black,76,&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,0,0,0,0,100,100,2,0,1,5.5,4,2,40,40,{round(OH * 0.33)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "\n".join(ev) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec"); ap.add_argument("--uncensored", action="store_true")
    a = ap.parse_args()
    spec = json.loads(Path(a.spec).read_text())
    base = ROOT / spec["out"]
    w, h, fps = probe(base)
    keys = sorted(spec.get("zoom", []), key=lambda k: k["t"])
    brolls = sorted(spec.get("broll", []), key=lambda b: b["at"])

    print("tracking face…", flush=True)
    fxs, fys = face_track(base, w, h, fps, spec.get("center_x", w / 2) * w / 1920)

    tmp = Path(tempfile.mkdtemp())
    ass = tmp / "captions.ass"
    captions(spec, ass, a.uncensored)

    out = ROOT / "clips" / "edited" / f"{Path(spec['out']).stem}_edit.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{OW}x{OH}",
         "-r", f"{fps:.6f}", "-i", "-", "-i", str(base), "-filter_complex", f"[0:v]ass={ass}[v]",
         "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "slow", "-crf", "18",
         "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(out)],
        stdin=subprocess.PIPE)

    active, bgen = None, None
    for i, fr in enumerate(reader(base, w, h)):
        t = i / fps
        b = next((b for b in brolls if b["at"] <= t < b["at"] + b["dur"]), None)
        if b is not active:
            if bgen:
                bgen.close()
            active = b
            if b:
                bw, bh, _ = probe(ROOT / b["src"])
                bgen = reader(ROOT / b["src"], bw, bh, ss=b["t"], dur=b["dur"] + 1)
        if active:
            bf = next(bgen, None)
            if bf is not None:
                u = (t - active["at"]) / active["dur"]
                z = active.get("z", 1.0) + (active.get("z2", 1.08) - active.get("z", 1.0)) * u
                bh_ = bf.shape[0]
                img = frame_crop(bf, active.get("cx", bf.shape[1] / 2), active.get("cy", bh_ * 0.4), z)
                enc.stdin.write(img.tobytes())
                continue
        img = frame_crop(fr, fxs[min(i, len(fxs) - 1)], fys[min(i, len(fys) - 1)], zoom_at(t, keys))
        enc.stdin.write(img.tobytes())
    enc.stdin.close()
    enc.wait()
    print(f"{out.relative_to(ROOT)}", flush=True)


if __name__ == "__main__":
    main()
