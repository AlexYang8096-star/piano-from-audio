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
echo ""
echo "== 试听完成，可以启动谱面微调 =="
echo "用法: python3 workflow/05_build_ly.py config.json --tune \"lh_vel=+1,rh_vel=-1,lh_density=0,rh_density=-2,tempo=+1\""
echo "参数: lh_vel/rh_vel(强弱) lh_density/rh_density(疏密) tempo(速度)，各取 -3..+3，0=原始"
echo "速度档: -3→76/-2→96/-1→116/0→136/+1→156/+2→176/+3→196 (基准 song.bpm)"
echo "然后重新运行: bash workflow/06_render.sh <新ly文件> <输出前缀>"
