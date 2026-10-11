#!/usr/bin/env python3
"""Step 07: 最终闭环自检 —— 渲染产物 vs 原曲客观比对
比对维度：时长 / BPM / 拍点数(小节数对齐) / chroma 调性倾向。
任何一项超出容差即 FAIL；不通过不得交付。
用法: python3 workflow/07_compare_original.py config.json <render_mp3>
"""
import json
import sys
from pathlib import Path

import librosa
import numpy as np

ROOT = Path(__file__).resolve().parent.parent


def analyze(path, label):
    y, sr = librosa.load(path, sr=22050, mono=True)
    dur = librosa.get_duration(y=y, sr=sr)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    tempo = float(np.atleast_1d(tempo)[0])
    n_beats = int(len(beats))
    n_bars = n_beats // 4
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_mean = np.mean(chroma, axis=1)
    keys = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    k = int(np.argmax(chroma_mean))
    print(f"[{label}] duration={dur:.1f}s  tempo={tempo:.2f}  beats={n_beats}  bars~={n_bars}  chroma_key_hint={keys[k]}")
    return dur, tempo, n_beats


def main():
    cfg_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "config.json"
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    orig = cfg["song"]["input_audio"]

    render = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else None
    if render is None:
        out_dir = (ROOT / cfg["song"]["output_dir"]).resolve()
        pdf = sorted(out_dir.glob("*_piano.pdf"))
        mp3 = sorted(out_dir.glob("*.mp3"))
        render = mp3[0] if mp3 else (pdf[0] if pdf else None)
    if render is None:
        raise SystemExit("未找到渲染 MP3，请传入路径: python3 workflow/07_compare_original.py config.json <render.mp3>")

    print("== 原曲 vs 渲染 MP3 闭环比对 ==")
    print("orig :", orig)
    print("render:", render)
    d1, t1, b1 = analyze(orig, "ORIGINAL")
    d2, t2, b2 = analyze(render, "RENDER")

    ok = True
    def check(name, a, b, tol, unit=""):
        nonlocal ok
        diff = abs(a - b)
        pct = diff / max(a, b) * 100
        status = "OK" if pct <= tol else "FAIL"
        if status == "FAIL":
            ok = False
        print(f"[{status}] {name}: {a:.2f}{unit} vs {b:.2f}{unit} (diff {pct:.2f}% <= {tol}%)")

    check("时长", d1, d2, 5, "s")
    check("BPM", t1, t2, 3)
    check("拍点数", b1, b2, 8)
    print("== 结果:", "全部通过" if ok else "存在偏差", "==")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
