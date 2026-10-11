#!/usr/bin/env python3
"""Step 03: 旋律量化
将 basic-pitch 转录的人声 MIDI 按 BPM/拍号网格量化到 8 分格，输出 melody_grid.json。
用法: python3 workflow/03_melody_grid.py config.json
"""
import json
import sys
from pathlib import Path

import numpy as np
import pretty_midi

ROOT = Path(__file__).resolve().parent.parent


def midi2name(p):
    names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    return names[p % 12] + str(p // 12 - 1)


def main():
    cfg_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "config.json"
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    song = cfg["song"]
    mel = cfg["melody"]

    midi_path = (ROOT / mel["midi_path"]).resolve() if not Path(mel["midi_path"]).is_absolute() else Path(mel["midi_path"])
    grid_out = (ROOT / song["work_dir"] / "melody_grid.json").resolve()

    bpm = float(song["bpm"])
    bar = 60.0 / bpm * 4
    eighth = bar / 8
    n_bars = int(song["n_bars"])

    m = pretty_midi.PrettyMIDI(str(midi_path))
    notes = []
    for ins in m.instruments:
        notes.extend(ins.notes)
    print(f"raw notes: {len(notes)}", flush=True)

    # 清理：主旋律音域 + 过滤超短杂音
    keep = [n for n in notes
            if mel["pitch_min"] <= n.pitch <= mel["pitch_max"]
            and (n.end - n.start) >= mel["min_note_len"]]
    keep.sort(key=lambda n: (n.start, -n.velocity))
    merged = []
    for n in keep:
        if merged and n.start - merged[-1].start < 0.05:
            if n.velocity > merged[-1].velocity:
                merged[-1] = n
        else:
            merged.append(n)
    print(f"cleaned notes: {len(merged)}", flush=True)

    # 量化到 8 分格
    grid = {}
    for n in merged:
        slot = int(round(n.start / eighth))
        bar_idx, s8 = slot // 8, slot % 8
        if bar_idx < 0 or bar_idx >= n_bars:
            continue
        key = (bar_idx, s8)
        if key not in grid or n.velocity > grid[key][1]:
            grid[key] = (n.pitch, n.velocity)

    out = []
    for b in range(n_bars):
        slots = []
        for s8 in range(8):
            if (b, s8) in grid:
                p, v = grid[(b, s8)]
                slots.append({"s": s8, "note": midi2name(p), "p": p, "v": v})
        out.append({"bar": b + 1, "slots": slots})

    grid_out.parent.mkdir(parents=True, exist_ok=True)
    with open(grid_out, "w", encoding="utf-8") as f:
        json.dump({"bar_len": bar, "eighth": eighth, "bars": out}, f, ensure_ascii=False)
    print("bars with notes:", sum(1 for x in out if x["slots"]))
    print("written:", grid_out)
    for x in out[:16]:
        print(x["bar"], " ".join(f"{s['note']}@{s['s']}" for s in x["slots"]))


if __name__ == "__main__":
    main()
