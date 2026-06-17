#!/usr/bin/env bash
# fetch_fonts.sh — download the v1 book fonts (all free / OFL, embeddable) into
# this folder so the Dockerfile's `COPY fonts/` bundles them into the image.
#
# Run this ONCE on the machine that builds the image (your PC or the VPS), from
# inside the fonts/ folder, BEFORE `docker compose up -d --build`:
#
#     cd book-formatter-worker/fonts && bash fetch_fonts.sh
#
# Fonts pulled from the official google/fonts repo (OFL licensed).
set -euo pipefail
cd "$(dirname "$0")"
RAW="https://raw.githubusercontent.com/google/fonts/main/ofl"

# family-subpath : output filename  (regular weights; add more weights if desired)
files=(
  "ebgaramond/EBGaramond%5Bwght%5D.ttf:EBGaramond.ttf"
  "lora/Lora%5Bwght%5D.ttf:Lora.ttf"
  "merriweather/Merriweather%5Bopsz,wdth,wght%5D.ttf:Merriweather.ttf"
  "librebaskerville/LibreBaskerville%5Bwght%5D.ttf:LibreBaskerville.ttf"
  "librebaskerville/LibreBaskerville-Italic%5Bwght%5D.ttf:LibreBaskerville-Italic.ttf"
  "sourceserif4/SourceSerif4%5Bopsz,wght%5D.ttf:SourceSerif4.ttf"
  "sourceserif4/SourceSerif4-Italic%5Bopsz,wght%5D.ttf:SourceSerif4-Italic.ttf"
  "montserrat/Montserrat%5Bwght%5D.ttf:Montserrat.ttf"
  "montserrat/Montserrat-Italic%5Bwght%5D.ttf:Montserrat-Italic.ttf"
  "lato/Lato-Regular.ttf:Lato-Regular.ttf"
  "lato/Lato-Bold.ttf:Lato-Bold.ttf"
  "lato/Lato-Italic.ttf:Lato-Italic.ttf"
)

for entry in "${files[@]}"; do
  url="${RAW}/${entry%%:*}"
  out="${entry##*:}"
  echo "→ $out"
  curl -fsSL "$url" -o "$out" || echo "  (skip: $url not found — check the path in the google/fonts repo)"
done

echo "done. fonts present:"
ls -1 *.ttf 2>/dev/null || echo "  (no .ttf downloaded — the image will fall back to system serif/sans)"
