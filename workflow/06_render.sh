#!/bin/bash
# Step 06: 渲染 —— LilyPond 出 PDF+MIDI，MuseScore 出 MP3 试听
# 用法: bash workflow/06_render.sh <ly文件> [输出前缀]
set -euo pipefail

LY="${1:?用法: bash workflow/06_render.sh <ly文件>}"
BASE="${2:-${LY%.ly}}"

command -v lilypond >/dev/null 2>&1 || export PATH="/opt/homebrew/bin:$PATH"

echo "== LilyPond: PDF + MIDI =="
lilypond -o "$BASE" "$LY"

MIDI="${BASE}.midi"
if [[ ! -f "$MIDI" ]]; then MIDI="${BASE}.mid"; fi

MSCORE="/System/Volumes/Data/Applications/MuseScore 4.app/Contents/MacOS/mscore"
if [[ ! -x "$MSCORE" ]]; then
  echo "MuseScore 未找到，跳过 MP3 渲染"
  exit 0
fi

echo "== MuseScore: MP3 =="
"$MSCORE" -o "${BASE}.mp3" "$MIDI"
echo "done: ${BASE}.pdf / ${BASE}.mp3"
