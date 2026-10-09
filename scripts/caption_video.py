#!/usr/bin/env python3
"""Add captions to a finished vertical video (no cutting or reframing).

Spec (JSON):
  {"video": "side/side_01.mp4",
   "transcript": "transcripts/side_01.json",      # word timestamps; made automatically if missing
   "out": "side/side_01_captioned.mp4",
   "style": "podcast",          # see scripts/captions.py
   "y": 0.47,                   # caption height as a fraction of the frame (0.5 = middle)
   "safe_w": 680,               # max caption width in px (1080 - 2 x side padding)
   "caption_lines": ["All day I wanted to get *home*.", ...]}
Words wrapped in *asterisks* are keywords (accent font). caption_lines must
contain exactly the spoken words, in order (checked).

Usage: python3 scripts/caption_video.py spec.json
"""
import json, subprocess, sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import captions  # noqa: E402
import edit  # noqa: E402
import render  # noqa: E402

ROOT = render.ROOT


def transcribe(video, path):
    """Word-timestamped transcript of a short video (faster-whisper medium)."""
    from faster_whisper import WhisperModel
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-ac", "1", "-ar", "16000",
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
    segs, _ = WhisperModel("medium", device="cpu", compute_type="int8").transcribe(
        audio, language="en", word_timestamps=True, beam_size=5)
    out = [{"start": s.start, "end": s.end, "text": s.text.strip(),
            "words": [{"s": round(w.start, 2), "e": round(w.end, 2), "w": w.word,
                       "p": round(w.probability, 2)} for w in s.words]} for s in segs]
    path.write_text(json.dumps({"source": video.name, "segments": out}))
    print("\n".join(s["text"] for s in out))


def main():
    spec = json.loads(Path(sys.argv[1]).read_text())
    video = ROOT / spec["video"]
    w, h, fps = edit.probe(video)
    style = spec.get("style", "podcast")

    if not (ROOT / spec["transcript"]).exists():
        transcribe(video, ROOT / spec["transcript"])
    tr = json.loads((ROOT / spec["transcript"]).read_text())
    words = [{"s": x["s"], "e": x["e"], "w": x["w"].strip()} for s in tr["segments"] for x in s["words"]]
    total = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                  "-of", "csv=p=0", str(video)], capture_output=True, text=True).stdout)
    lines = (render.manual_lines(words, spec["caption_lines"], spec.get("uncensored", False))
             if spec.get("caption_lines") else render.caption_lines(words))
    st = captions.STYLES[style]
    # narrower safe box -> shorter phrases, so they stay on one line
    chars = int(st["chars"] * min(1.0, spec.get("safe_w", captions.SAFE_W) / captions.SAFE_W))
    chunks = edit.chunks_of(lines, st["chunk"], chars)
    track = []
    for ci, ch in enumerate(chunks):
        nxt = chunks[ci + 1][0]["s"] if ci + 1 < len(chunks) else total
        track.append({"start": ch[0]["s"], "end": min(nxt, ch[-1]["e"] + 0.5),
                      "words": [x["w"] for x in ch], "starts": [x["s"] for x in ch]})

    out = ROOT / spec["out"]
    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}",
         "-r", f"{fps:.6f}", "-i", "-", "-i", str(video), "-map", "0:v", "-map", "1:a?",
         "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "copy", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    for i, fr in enumerate(edit.reader(video, w, h)):
        t = i / fps
        ch = next((c for c in track if c["start"] <= t < c["end"]), None)
        if ch:
            active = max(k for k, s0 in enumerate(ch["starts"]) if s0 <= t or k == 0)
            pil = Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB))
            pil = captions.draw(pil, ch["words"], active, style, t - ch["start"],
                                spec.get("keywords", []), y=spec.get("y"), safe_w=spec.get("safe_w"))
            fr = cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR)
        enc.stdin.write(fr.tobytes())
    enc.stdin.close()
    enc.wait()
    print(out.relative_to(ROOT))


if __name__ == "__main__":
    main()
