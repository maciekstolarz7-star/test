#!/usr/bin/env bash
# For every source: 1 frame every 5 s (small JPEGs, filename = absolute seconds)
# and an ffmpeg scene-change list (frames/<stem>/scenes.txt, "seconds score").
# Usage: scripts/frames.sh [files...]
set -euo pipefail
cd "$(dirname "$0")/.."
files=("$@")
[ ${#files[@]} -eq 0 ] && mapfile -t files < <(find sources -maxdepth 1 -type f | sort)
for src in "${files[@]}"; do
  stem=$(basename "${src%.*}")
  dir="frames/$stem"
  [ -f "$dir/.done" ] && { echo "skip $stem"; continue; }
  mkdir -p "$dir"
  ffmpeg -v error -y -i "$src" -vf "fps=1/5,scale=640:-2" -q:v 4 "$dir/f_%05d.jpg"
  # rename f_00001.jpg -> t_000000.jpg (absolute seconds of the frame)
  for f in "$dir"/f_*.jpg; do
    n=$(basename "$f" .jpg); n=$((10#${n#f_}))
    mv "$f" "$dir/$(printf 't_%06d.jpg' $(( (n - 1) * 5 )))"
  done
  ffmpeg -v info -i "$src" -an -vf "scale=320:-2,select='gt(scene,0.3)',metadata=print:file=-" \
    -f null - 2>/dev/null | awk '/pts_time/{split($0,a,"pts_time:"); t=a[2]} /scene_score/{split($0,b,"="); print t, b[2]}' \
    > "$dir/scenes.txt"
  touch "$dir/.done"
  echo "frames $stem: $(ls "$dir"/t_*.jpg | wc -l) frames, $(wc -l < "$dir/scenes.txt") scene cuts"
done
