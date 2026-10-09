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
  "emphasis": ["lost", "quit"]   words highlighted in the captions.

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


def captions(spec, ass_path, uncensored):
    segs = spec["segments"]
    cache = {}
    for s in segs:
        src = ROOT / s["src"]
        cache.setdefault(src, render.words_for(src))
        s["_cut"] = render.snap(s["start"], s["end"], cache[src])
    words, total = render.caption_words(segs, cache, uncensored)
    render.write_ass(ass_path, words, total, OW, OH, spec.get("caption_lines"), uncensored)
    # emphasis colour + a subtle pop-in on every line
    emph = {e.lower() for e in spec.get("emphasis", [])}
    out = []
    for line in ass_path.read_text().splitlines():
        if line.startswith("Dialogue:"):
            head, text = line.split(",,0,0,0,,", 1)
            text = text.replace("{\\blur3}", "")
            toks = [f"{{\\c{ACCENT}}}{t}{{\\c&HFFFFFF&}}"
                    if render.re.sub(r"[^\w']", "", t).lower().replace("*", "") in emph else t
                    for t in text.split(" ")]
            line = (head + ",,0,0,0,,{\\blur3\\fscx106\\fscy106\\t(0,90,\\fscx100\\fscy100)}"
                    + " ".join(toks))
        out.append(line)
    ass_path.write_text("\n".join(out) + "\n")


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
