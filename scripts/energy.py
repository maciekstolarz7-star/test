#!/usr/bin/env python3
"""Find loud / high-energy moments (screaming, celebrating, rage) per source.

Reads the 16 kHz wav made by transcribe.py, computes loudness per second, and
lists the peaks that stand far above the source's own baseline. Each peak is
printed with the transcript text around it.

Usage: python3 scripts/energy.py <stem> [--top 40]
"""
import argparse, json, wave
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent


def hms(t):
    t = int(t); return f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stem"); ap.add_argument("--top", type=int, default=40)
    a = ap.parse_args()
    wav = ROOT / "transcripts" / f".work_{a.stem}" / "audio.wav"
    with wave.open(str(wav)) as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    n = len(x) // sr
    rms = np.sqrt((x[: n * sr].reshape(n, sr) ** 2).mean(1) + 1e-10)
    db = 20 * np.log10(rms)
    # 3 s smoothing, compared with the median of the surrounding 5 minutes
    sm = np.convolve(db, np.ones(3) / 3, mode="same")
    base = np.array([np.median(db[max(0, i - 150): i + 150]) for i in range(n)])
    score = sm - base
    order, picked = np.argsort(-score), []
    for i in order:
        if all(abs(i - j) > 20 for j in picked):
            picked.append(i)
        if len(picked) >= a.top:
            break
    tr = json.loads((ROOT / "transcripts" / f"{a.stem}.json").read_text())["segments"]
    for i in sorted(picked):
        text = " ".join(s["text"] for s in tr if s["end"] > i - 8 and s["start"] < i + 8)
        print(f"{hms(i)} ({i}s) +{score[i]:.1f}dB | {text[:220]}")


if __name__ == "__main__":
    main()
