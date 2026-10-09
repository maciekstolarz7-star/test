#!/usr/bin/env python3
"""Transcribe every video in ./sources with word-level timestamps.

Long streams are split into chunks; timestamps stay absolute (seconds from
the start of the source). Finished chunks are cached, so a crashed or
interrupted run resumes where it stopped.

Usage: python3 scripts/transcribe.py [--model medium|small] [--chunk 1800] [files...]
Output per source: transcripts/<stem>.json (segments + words) and
                   transcripts/<stem>.txt  ([HH:MM:SS] line per segment)
"""
import argparse, json, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC, OUT = ROOT / "sources", ROOT / "transcripts"
VIDEO_EXT = {".mp4", ".mkv", ".webm", ".mov", ".m4v", ".ts", ".flv", ".avi"}


def hms(t):
    t = int(t)
    return f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}"


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return float(r.stdout.strip())


def extract_wav(src, wav):
    if wav.exists():
        return
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vn", "-ac", "1",
                    "-ar", "16000", "-c:a", "pcm_s16le", str(wav)], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="medium")
    ap.add_argument("--chunk", type=float, default=1800, help="chunk length in seconds")
    ap.add_argument("files", nargs="*")
    a = ap.parse_args()

    from faster_whisper import WhisperModel
    model = WhisperModel(a.model, device="cpu", compute_type="int8")

    files = [Path(f) for f in a.files] or sorted(p for p in SRC.iterdir() if p.suffix.lower() in VIDEO_EXT)
    OUT.mkdir(exist_ok=True)
    for src in files:
        stem = src.stem
        if (OUT / f"{stem}.json").exists():
            print(f"skip {stem} (done)"); continue
        work = OUT / f".work_{stem}"
        work.mkdir(exist_ok=True)
        wav = work / "audio.wav"
        extract_wav(src, wav)
        dur = duration(wav)
        segments = []
        start = 0.0
        while start < dur:
            length = min(a.chunk, dur - start)
            cache = work / f"chunk_{int(start):06d}.json"
            if cache.exists():
                segs = json.loads(cache.read_text())
            else:
                t0 = time.time()
                piece = work / "piece.wav"
                subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(start), "-t", str(length),
                                "-i", str(wav), "-c", "copy", str(piece)], check=True)
                it, _ = model.transcribe(str(piece), language="en", word_timestamps=True,
                                         vad_filter=True, beam_size=5,
                                         condition_on_previous_text=False)
                segs = [{"start": round(s.start + start, 2), "end": round(s.end + start, 2),
                         "text": s.text.strip(),
                         "words": [{"s": round(w.start + start, 2), "e": round(w.end + start, 2),
                                    "w": w.word, "p": round(w.probability, 2)} for w in s.words]}
                        for s in it]
                cache.write_text(json.dumps(segs))
                print(f"{stem} {hms(start)}-{hms(start + length)} done in {time.time() - t0:.0f}s", flush=True)
            segments += segs
            start += length
        (OUT / f"{stem}.json").write_text(json.dumps({"source": src.name, "duration": dur,
                                                      "model": a.model, "segments": segments}))
        (OUT / f"{stem}.txt").write_text("".join(f"[{hms(s['start'])}] {s['text']}\n" for s in segments))
        print(f"wrote transcripts/{stem}.json", flush=True)


if __name__ == "__main__":
    sys.exit(main())
