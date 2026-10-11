#!/usr/bin/env python3
"""Step 01: 人声/伴奏分离
调用 audio-separator 将原曲分离为 Vocals 与 Instrumental 两轨，并用 ffprobe 校验时长一致。
用法: python3 workflow/01_separate.py config.json
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    cfg_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "config.json"
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    song, sep = cfg["song"], cfg["separation"]

    src = song["input_audio"]
    out_dir = (ROOT / sep["output_dir"]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    print("== Step 01 分离 ==")
    print(f"model: {sep['model']}")
    print(f"src  : {src}")
    print(f"out  : {out_dir}")

    cmd = [
        "audio-separator", str(src),
        "--model_filename", sep["model"],
        "--output_dir", str(out_dir),
    ]
    print("cmd:", " ".join(cmd))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise SystemExit("audio-separator 分离失败")

    # 校验：分离轨时长与原曲一致（防止截断）
    def dur(p):
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                              "format=duration", "-of", "default=nw=1:nk=1", str(p)],
                             capture_output=True, text=True)
        return float(out.stdout.strip()) if out.stdout.strip() else -1.0

    d_src = dur(src)
    print(f"original duration: {d_src:.2f}s")
    for wav in sorted(out_dir.glob("*.wav")):
        d = dur(wav)
        diff = abs(d - d_src) / d_src * 100
        status = "OK" if diff < 1.0 else "WARN"
        print(f"[{status}] {wav.name}: {d:.2f}s (diff {diff:.2f}%)")


if __name__ == "__main__":
    main()
