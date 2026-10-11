#!/usr/bin/env python3
"""Step 04: 伴奏轨低音/和弦分析（辅助人工定和弦）
按 beat_track 真实拍点 4 拍一组切小节，输出逐小节低音根音候选 + 全频 chroma top5，
与公开和弦资料交叉后填入 config.json 的 sections。
用法: python3 workflow/04_chord_analyze.py config.json
"""
import json
import sys
from pathlib import Path

import librosa
import numpy as np

ROOT = Path(__file__).resolve().parent.parent

PC = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def pc_name(m):
    return PC[m % 12]


def low_root_candidates(y, sr, t0, t1):
    seg = y[int(t0 * sr):int(t1 * sr)]
    if len(seg) < sr // 8:
        return []
    S = np.abs(librosa.stft(seg, n_fft=2048, hop_length=512))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    band = (freqs >= 30) & (freqs <= 250)
    e = S[band].sum(axis=1)
    f = freqs[band]
    if e.max() == 0:
        return []
    idx = np.argsort(e)[::-1][:3]
    out = []
    for i in idx:
        midi = 12 * np.log2(f[i] / 440.0) + 69
        out.append({"pc": pc_name(round(midi)), "energy": round(float(e[i] / e.max()), 2)})
    return out


def main():
    cfg_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "config.json"
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    song, sep = cfg["song"], cfg["separation"]

    sep_dir = (ROOT / sep["output_dir"]).resolve()
    inst = sorted(sep_dir.glob("*_(Instrumental)_*.wav"))
    if not inst:
        raise SystemExit("未找到 Instrumental 分离轨，请先运行 Step 01")
    src = inst[0]

    print("loading:", src, flush=True)
    y, sr = librosa.load(src, sr=22050, mono=True)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time", trim=False)
    beats = np.asarray(beats)
    print(f"bpm={float(np.atleast_1d(tempo)[0]):.2f} beats={len(beats)}", flush=True)

    bar_starts = beats[::4] if len(beats) > 4 else []
    hop = 512
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop)
    times = librosa.times_like(chroma, sr=sr, hop_length=hop)

    rows = []
    for i, t0 in enumerate(bar_starts):
        t1 = bar_starts[i + 1] if i + 1 < len(bar_starts) else min(t0 + 2.321, len(y) / sr)
        lows = low_root_candidates(y, sr, t0, t1)
        mask = (times >= t0) & (times < t1)
        seg = chroma[:, mask]
        mean = seg.mean(axis=1) if mask.sum() > 0 else np.zeros(12)
        top5 = np.argsort(mean)[::-1][:5]
        rows.append({
            "bar": i + 1,
            "t0": round(float(t0), 2),
            "low": lows,
            "top": ",".join(pc_name(int(p)) for p in top5),
            "energy": round(float(mean.max()), 2) if mean.max() > 0 else 0.0,
        })

    out_path = (ROOT / song["work_dir"] / "chord_analysis.json").resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"n_bars": len(rows), "rows": rows}, f, ensure_ascii=False, indent=1)
    print("written:", out_path)
    for r in rows[:20]:
        print(f"bar {r['bar']:>3} t0={r['t0']:>7} low={r['low']} top={r['top']}")


if __name__ == "__main__":
    main()
