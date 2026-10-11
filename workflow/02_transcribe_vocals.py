#!/usr/bin/env python3
"""Step 02: 人声旋律转录
用 basic-pitch 将 Vocals 轨转录为 MIDI（nmp.onnx 后端，规避 ValueError）。
用法: python3 workflow/02_transcribe_vocals.py config.json
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    cfg_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "config.json"
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    song, sep, mel = cfg["song"], cfg["separation"], cfg["melody"]

    sep_dir = (ROOT / sep["output_dir"]).resolve()
    vocals = sorted(sep_dir.glob("*_(Vocals)_*.wav"))
    if not vocals:
        raise SystemExit("未找到 Vocals 分离轨，请先运行 Step 01")
    src = vocals[0]

    midi_out = (ROOT / mel["midi_path"]).resolve()
    midi_out.parent.mkdir(parents=True, exist_ok=True)

    print("== Step 02 转录 ==")
    print("src :", src)
    print("out :", midi_out)

    cmd = [
        "basic-pitch",
        "--save-midi", "--sonify-midi",
        "--model-serialization", "onnx",
        "--onset-threshold", "0.5",
        "--frame-threshold", "0.3",
        "--minimum-note-length", "127.7",
        str(midi_out.parent), str(src),
    ]
    print("cmd:", " ".join(cmd))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise SystemExit("basic-pitch 转录失败")

    # 新版 basic-pitch 以 <音频名>_basic_pitch.mid 写入 output_dir，移动为约定文件名
    produced = sorted(midi_out.parent.glob("*_basic_pitch.mid"))
    if not produced:
        raise SystemExit("未找到 basic-pitch 生成的 MIDI 文件")
    produced[0].replace(midi_out)
    print("done:", midi_out)


if __name__ == "__main__":
    main()
