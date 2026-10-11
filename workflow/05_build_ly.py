#!/usr/bin/env python3
"""Step 05: 生成 LilyPond 谱面源文件
右手=人声旋律（含八度修正），左手=前八后十六柱式，和弦标记=config 中真实进行。
用法: python3 workflow/05_build_ly.py config.json
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def pitch_name(p):
    names = ['c', 'cis', 'd', 'dis', 'e', 'f', 'fis', 'g', 'gis', 'a', 'ais', 'b']
    octave = p // 12 - 1
    return names[p % 12] + "'" * max(0, octave - 3) + "," * max(0, 3 - octave)


def build_chord_seq(sections, n_bars):
    """按段落展开为逐小节和弦列表，并校验总数。"""
    seq = []
    for sec in sections:
        loop = sec.get("chords")
        start, end = int(sec["start"]), int(sec["end"])
        for b in range(start - 1, end):
            seq.append(loop[b % len(loop)])
    if len(seq) != n_bars:
        raise SystemExit(f"chord sequence length {len(seq)} != n_bars {n_bars}; 请检查 sections 配置")
    return seq


def melody_bar(bars, bar_idx, fix_threshold):
    b = bars[bar_idx]
    slots = {s["s"]: s for s in b["slots"]}
    out = []
    for s8 in range(8):
        if s8 in slots:
            p = slots[s8]["p"]
            if p < fix_threshold:
                p += 12
            out.append(pitch_name(p) + "8")
        else:
            out.append("r8")
    return " ".join(out) + " |"


def lh_bar(chord, chord_map):
    low, upper = chord_map[chord]["low"], chord_map[chord]["upper"]
    pat = f"{low}8( {upper}16 {upper}16) "
    return pat * 4 + "|"


def main():
    cfg_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "config.json"
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    song, chords_cfg = cfg["song"], cfg["chords"]
    mel = cfg["melody"]

    work = (ROOT / song["work_dir"]).resolve()
    out_dir = (ROOT / song["output_dir"]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    grid = json.load(open(work / "melody_grid.json", encoding="utf-8"))
    bars = grid["bars"]
    n_bars = int(song["n_bars"])
    bpm = float(song["bpm"])
    key = song["key"]

    chord_seq = build_chord_seq(chords_cfg["sections"], n_bars)
    chord_map = chords_cfg["chord_map"]

    ly_path = out_dir / f"{Path(cfg_path).stem}_piano.ly"

    lines = []
    lines.append('\\version "2.26.0"')
    lines.append('\\header {')
    lines.append(f'  title = "{song["title"]} (Piano Solo)"')
    lines.append(f'  subtitle = "{song["subtitle"]}"')
    lines.append('  tagline = ""')
    lines.append('}')
    lines.append('')
    lines.append('\\paper {')
    lines.append('  #(set-paper-size "a4")')
    lines.append('  top-margin = 14\\mm')
    lines.append('  bottom-margin = 14\\mm')
    lines.append('  left-margin = 15\\mm')
    lines.append('  right-margin = 15\\mm')
    lines.append('  ragged-last = ##f')
    lines.append('}')
    lines.append('')
    lines.append('\\layout {')
    lines.append('  \\context { \\Score')
    lines.append('    \\override SpacingSpanner.base-shortest-duration = #(ly:make-moment 1/16)')
    lines.append('  }')
    lines.append('}')
    lines.append('')

    lines.append('harmonies = \\chordmode {')
    lines.append('  \\set chordChanges = ##t')
    lines.append('  \\set majorSevenSymbol = \\markup { maj7 }')
    for ch in chord_seq:
        lines.append(f"  {chord_map[ch]['chordsym']} |")
    lines.append('}')
    lines.append('')

    lines.append('rh = {')
    lines.append(f'  \\key {key} \\major')
    lines.append(f'  \\time {song["time_signature"]}')
    lines.append(f'  \\tempo 4 = {int(bpm)}')
    lines.append('  \\absolute {')
    for sec in chords_cfg["sections"]:
        lines.append(f"  % {sec['name']} (bars {sec['start']}-{sec['end']})")
        for b in range(int(sec["start"]) - 1, int(sec["end"])):
            dyn = sec["dyn"] if b == int(sec["start"]) - 1 else ""
            lines.append("  " + (dyn + " " if dyn else "") + melody_bar(bars, b, mel["octave_fix_threshold"]))
        lines.append("  \\break")
    lines.append('  \\bar "|."')
    lines.append('  }')
    lines.append('}')
    lines.append('')

    lines.append('lh = {')
    lines.append(f'  \\key {key} \\major')
    lines.append(f'  \\time {song["time_signature"]}')
    lines.append('  \\absolute {')
    for sec in chords_cfg["sections"]:
        lines.append(f"  % {sec['name']} (bars {sec['start']}-{sec['end']})")
        for b in range(int(sec["start"]) - 1, int(sec["end"])):
            dyn = sec["dyn"] if b == int(sec["start"]) - 1 else ""
            lines.append("  " + (dyn + " " if dyn else "") + lh_bar(chord_seq[b], chord_map))
        lines.append("  \\break")
    lines.append('  \\bar "|."')
    lines.append('  }')
    lines.append('}')
    lines.append('')

    lines.append('\\score {')
    lines.append('  <<')
    lines.append('    \\new ChordNames { \\harmonies }')
    lines.append('    \\new PianoStaff <<')
    lines.append('      \\new Staff = "right" { \\rh }')
    lines.append('      \\new Staff = "left" { \\clef bass \\lh }')
    lines.append('    >>')
    lines.append('  >>')
    lines.append('  \\layout { }')
    lines.append(f'  \\midi {{ \\tempo 4 = {int(bpm)} }}')
    lines.append('}')
    lines.append('')

    with open(ly_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("written:", ly_path, "lines:", len(lines))

    # 校验：以 | 结尾的小节行数 = rh + lh + harmonies 三组各 n_bars 行
    n_endpipe = sum(1 for l in lines if l.rstrip().endswith("|"))
    print("pipe-terminated bar lines:", n_endpipe, "expected:", 3 * n_bars)


if __name__ == "__main__":
    main()
