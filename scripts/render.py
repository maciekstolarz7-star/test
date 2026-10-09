#!/usr/bin/env python3
"""Render one raw horizontal clip from a list of segments.

Spec (JSON file):
  {"out": "clips/tjr_01_slug.mp4",
   "segments": [{"src": "sources/stream.mp4", "start": 3721.40, "end": 3729.10}, ...]}

- Cut points are snapped to word boundaries from transcripts/<stem>.json, so
  no cut lands mid-word (start moves back to a word's start, end forward to
  its end, then each edge gets up to 60 ms of the surrounding gap).
- Video: hard cuts. Audio: true crossfade of XF_FRAMES frames at each join.
  Each non-final segment's audio runs XF seconds past its video cut and
  overlaps the next one, so the audio stays exactly as long as the video
  (no A/V drift across joins).
- 16:9, 1920x1080 or the source's height if lower, H.264 CRF 18 + AAC 192k.

Usage: python3 scripts/render.py spec.json [--no-snap]
"""
import argparse, json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
XF_FRAMES = 3
PAD = 0.06


def probe(src):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,r_frame_rate", "-of", "json", str(src)],
                       capture_output=True, text=True, check=True)
    s = json.loads(r.stdout)["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    return s["width"], s["height"], float(num) / float(den)


def words_for(src):
    p = ROOT / "transcripts" / f"{Path(src).stem}.json"
    if not p.exists():
        return []
    return [w for s in json.loads(p.read_text())["segments"] for w in s["words"]]


def snap(start, end, words):
    if not words:
        return start, end
    for w in words:  # start inside a word -> back to its start
        if w["s"] < start < w["e"]:
            start = w["s"]; break
    for w in words:  # end inside a word -> forward to its end
        if w["s"] < end < w["e"]:
            end = w["e"]; break
    prev_e = max((w["e"] for w in words if w["e"] <= start + 1e-3), default=start - PAD)
    next_s = min((w["s"] for w in words if w["s"] >= end - 1e-3), default=end + PAD)
    start = max(start - PAD, (prev_e + start) / 2, 0)
    end = min(end + PAD, (end + next_s) / 2)
    return round(start, 3), round(end, 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec"); ap.add_argument("--no-snap", action="store_true")
    a = ap.parse_args()
    spec = json.loads(Path(a.spec).read_text())
    segs = spec["segments"]

    w0, h0, fps = probe(ROOT / segs[0]["src"])
    H = min(1080, h0); H -= H % 2
    W = round(H * 16 / 9); W -= W % 2
    xf = XF_FRAMES / fps

    cache, args, fv, fa = {}, [], [], []
    for i, s in enumerate(segs):
        src = ROOT / s["src"]
        if src not in cache:
            cache[src] = words_for(src)
        st, en = (s["start"], s["end"]) if a.no_snap else snap(s["start"], s["end"], cache[src])
        s["_cut"] = (st, en)
        dur = en - st
        last = i == len(segs) - 1
        args += ["-ss", f"{st:.3f}", "-t", f"{dur + (0 if last else xf):.3f}", "-i", str(src)]
        fv.append(f"[{i}:v]trim=duration={dur:.3f},setpts=PTS-STARTPTS,fps={fps:.4f},"
                  f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
                  f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1[v{i}]")
        fa.append(f"[{i}:a]asetpts=PTS-STARTPTS,aresample=48000,"
                  f"aformat=channel_layouts=stereo[a{i}]")

    n = len(segs)
    graph = fv + fa
    graph.append("".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vout]")
    prev = "a0"
    for i in range(1, n):
        graph.append(f"[{prev}][a{i}]acrossfade=d={xf:.4f}:c1=tri:c2=tri[ax{i}]")
        prev = f"ax{i}"

    out = ROOT / spec["out"]
    out.parent.mkdir(exist_ok=True)
    cmd = ["ffmpeg", "-y", "-v", "error", *args, "-filter_complex", ";".join(graph),
           "-map", "[vout]", "-map", f"[{prev}]", "-c:v", "libx264", "-preset", "slow",
           "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)
    total = sum(s["_cut"][1] - s["_cut"][0] for s in segs)
    print(f"{spec['out']}: {total:.1f}s, {n} segment(s) "
          + ", ".join(f"{Path(s['src']).name}@{s['_cut'][0]:.2f}-{s['_cut'][1]:.2f}" for s in segs))


if __name__ == "__main__":
    main()
