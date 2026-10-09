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

Vertical (--vertical): 1080x1920, a full-height 9:16 crop centred on the
spec's "center_x" (source pixels; default: frame centre), written to
clips/vertical/<name>_v.mp4.
Captions (--captions): one line at a time, white Inter SemiBold with a soft
dark shadow, timed from the transcript's word timestamps mapped through the
cuts. Swear words are lightly starred for reach (CENSOR); --uncensored keeps
them as spoken.

Usage: python3 scripts/render.py spec.json [--no-snap] [--vertical] [--captions] [--uncensored]
"""
import argparse, json, re, subprocess, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
XF_FRAMES = 3
PAD = 0.06
CENSOR = {"fuck": "f*ck", "fucking": "f*cking", "shit": "sh*t", "bitch": "b*tch"}
LINE_CHARS = 24   # max characters per caption line (vertical, font 64)
LINE_GAP = 0.6    # a pause this long may start a new line


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


def caption_words(segs, cache, uncensored):
    """Words of the final clip with output-timeline timestamps."""
    out, offset = [], 0.0
    for s in segs:
        first = True
        st, en = s["_cut"]
        for w in cache[ROOT / s["src"]]:
            if st <= (w["s"] + w["e"]) / 2 <= en:
                text = w["w"].strip()
                if not uncensored:
                    core = re.sub(r"[^\w']", "", text).lower()
                    if core in CENSOR:
                        text = text.lower().replace(core, CENSOR[core])
                out.append({"s": max(w["s"], st) - st + offset,
                            "e": min(w["e"], en) - st + offset, "w": text, "cut": first})
                first = False
        offset += en - st
    return out, offset


WEAK_END = {"a", "an", "the", "to", "of", "and", "but", "or", "so", "i", "you", "your",
            "my", "that", "it", "is", "are", "was", "were", "has", "have", "had", "be",
            "can", "will", "when", "where", "in", "on", "at", "for", "with", "from",
            "by", "as", "if", "than", "their", "his", "her", "our", "this", "what",
            "because", "going", "we", "they", "he", "she", "it's", "there's", "very"}
# good words to START a line with
BREAK_BEFORE = {"because", "but", "and", "so", "when", "where", "that", "than", "what",
                "once", "if", "to", "you", "it's", "i"}


def _bare(w):
    return re.sub(r"[^\w']", "", w["w"]).lower()


def _split_phrase(ph):
    """Split one phrase into balanced lines (DP over break points)."""
    lens = [len(w["w"]) for w in ph]
    total = sum(lens) + len(ph) - 1
    k = max(1, -(-total // LINE_CHARS))
    target = total / k
    n = len(ph)

    def cost(i, j):  # line = ph[i:j]
        ln = sum(lens[i:j]) + (j - i - 1)
        c = (ln - target) ** 2
        if ln > LINE_CHARS:
            c += 1000 + 50 * (ln - LINE_CHARS)
        if j < n:
            if _bare(ph[j - 1]) in WEAK_END:
                c += 60
            if ph[j - 1]["w"].endswith(","):
                c -= 40
            if ph[j]["s"] - ph[j - 1]["e"] > LINE_GAP:
                c -= 30
            if _bare(ph[j]) in BREAK_BEFORE:
                c -= 20
        if j - i == 1 and n > 1:
            c += 80
        return c

    best = {0: (0, [])}
    for j in range(1, n + 1):
        cands = [(best[i][0] + cost(i, j), best[i][1] + [(i, j)]) for i in best if i < j]
        best[j] = min(cands, key=lambda x: x[0])
    return [ph[i:j] for i, j in best[n][1]]


def caption_lines(words):
    """Phrases end at a cut, a sentence end or a capitalised sentence start;
    each phrase is split into balanced lines of <= LINE_CHARS that avoid
    ending on weak words and prefer commas/pauses as break points."""
    phrases, cur = [], []
    for w in words:
        if cur and (w.get("cut") or re.search(r"[.?!]$", cur[-1]["w"])
                    or (w["w"][:1].isupper() and _bare(w) not in {"i", "i'm", "i'll", "i've"})):
            phrases.append(cur); cur = []
        cur.append(w)
    if cur:
        phrases.append(cur)
    return [ln for ph in phrases for ln in _split_phrase(ph)]


def ass_time(t):
    t = max(t, 0); cs = round(t * 100)
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def manual_lines(words, texts, uncensored):
    """Hand-written caption lines from the spec. They must contain exactly the
    clip's words in order (punctuation/case may differ), so wording stays 1:1
    with what is said; timing comes from the word timestamps."""
    norm = lambda t: re.sub(r"[^\w']", "", t.replace("*", "")).lower()
    toks = [t for line in texts for t in line.split()]
    got = [norm(w["w"]) for w in words]
    want = [norm(t) for t in toks]
    censored = [norm(c) for c in CENSOR.values()]
    if len(got) != len(want) or any(g != x and g not in censored for g, x in zip(got, want)):
        raise SystemExit(f"caption_lines don't match the clip's words:\n  clip: {' '.join(got)}\n  spec: {' '.join(want)}")
    out, k = [], 0
    for line in texts:
        n = len(line.split())
        ln = [dict(w) for w in words[k:k + n]]
        for w, t in zip(ln, line.split()):
            if not uncensored:
                core = norm(t)
                t = t.replace(core, CENSOR[core]) if core in CENSOR else t
            w["w"] = t
        out.append(ln); k += n
    return out


def write_ass(path, words, total, W, H, texts=None, uncensored=False):
    lines = manual_lines(words, texts, uncensored) if texts else caption_lines(words)
    ev = []
    for i, ln in enumerate(lines):
        start = ln[0]["s"]
        end = min(lines[i + 1][0]["s"] if i + 1 < len(lines) else total, ln[-1]["e"] + 0.5)
        text = " ".join(w["w"] for w in ln)
        text = re.sub(r"[,.;:]+(?=\s|$)", "", text)  # clean look: keep ? ! and apostrophes
        if i == 0:
            text = text[0].upper() + text[1:]
        ev.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Cap,,0,0,0,,{text}")
    path.write_text(f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Inter SemiBold,{round(H * 0.0335)},&H00FFFFFF,&H00FFFFFF,&H8C000000,&H8C000000,0,0,0,0,100,100,0,0,1,{H * 0.0016:.1f},{H * 0.0012:.1f},2,60,60,{round(H * 0.30)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "\n".join(e.replace(",,0,0,0,,", ",,0,0,0,,{\\blur3}", 1) for e in ev) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec"); ap.add_argument("--no-snap", action="store_true")
    ap.add_argument("--vertical", action="store_true")
    ap.add_argument("--captions", action="store_true")
    ap.add_argument("--uncensored", action="store_true")
    a = ap.parse_args()
    spec = json.loads(Path(a.spec).read_text())
    segs = spec["segments"]

    w0, h0, fps = probe(ROOT / segs[0]["src"])
    H = min(1080, h0); H -= H % 2
    W = round(H * 16 / 9); W -= W % 2
    if a.vertical:
        cw = round(h0 * 9 / 16); cw -= cw % 2
        cx = min(max(spec.get("center_x", w0 / 2) - cw / 2, 0), w0 - cw)
        frame = f"crop={cw}:{h0}:{cx:.0f}:0,scale=1080:1920:flags=lanczos,setsar=1"
        W, H = 1080, 1920
    else:
        frame = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
                 f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1")
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
                  f"{frame}[v{i}]")
        fa.append(f"[{i}:a]asetpts=PTS-STARTPTS,aresample=48000,"
                  f"aformat=channel_layouts=stereo[a{i}]")

    n = len(segs)
    graph = fv + fa
    graph.append("".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vcat]")
    vlast = "null"
    if a.captions:
        words, total = caption_words(segs, cache, a.uncensored)
        ass = Path(tempfile.mkdtemp()) / "captions.ass"
        write_ass(ass, words, total, W, H, spec.get("caption_lines"), a.uncensored)
        vlast = f"ass={ass}"
    graph.append(f"[vcat]{vlast}[vout]")
    prev = "a0"
    for i in range(1, n):
        graph.append(f"[{prev}][a{i}]acrossfade=d={xf:.4f}:c1=tri:c2=tri[ax{i}]")
        prev = f"ax{i}"

    out = ROOT / spec["out"]
    if a.vertical:
        out = out.parent / "vertical" / f"{out.stem}_v{out.suffix}"
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-v", "error", *args, "-filter_complex", ";".join(graph),
           "-map", "[vout]", "-map", f"[{prev}]", "-c:v", "libx264", "-preset", "slow",
           "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)
    total = sum(s["_cut"][1] - s["_cut"][0] for s in segs)
    print(f"{out.relative_to(ROOT)}: {total:.1f}s, {n} segment(s) "
          + ", ".join(f"{Path(s['src']).name}@{s['_cut'][0]:.2f}-{s['_cut'][1]:.2f}" for s in segs))


if __name__ == "__main__":
    main()
