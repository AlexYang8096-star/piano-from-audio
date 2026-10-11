#!/usr/bin/env python3
"""工作流自检：检查各环节输入输出衔接、工具可用性、脚本可重放性、最终闭环比对。
用法: python3 selfcheck/selfcheck_workflow.py config.json
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PC = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

ok, fail = [], []


def check(name, cond, detail=""):
    (ok if cond else fail).append(f"{name}: {detail if not cond else '通过'}")


def have(t):
    if shutil.which(t):
        return True
    return os.path.exists(f"/opt/homebrew/bin/{t}")


def main():
    cfg_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "config.json"
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    song, sep, mel = cfg["song"], cfg["separation"], cfg["melody"]
    work = (ROOT / song["work_dir"]).resolve()
    out = (ROOT / song["output_dir"]).resolve()

    # 1. 输入资源
    check("原曲音频", os.path.exists(song["input_audio"]))
    sep_dir = (ROOT / sep["output_dir"]).resolve()
    check("Instrumental 分离轨", bool(list(sep_dir.glob("*_(Instrumental)_*.wav"))))
    check("Vocals 分离轨", bool(list(sep_dir.glob("*_(Vocals)_*.wav"))))
    midi = (ROOT / mel["midi_path"]).resolve()
    check("人声转录 MIDI", os.path.exists(midi))

    # 2. 中间产物
    check("旋律网格 JSON", os.path.exists(work / "melody_grid.json"))
    check("和弦分析 JSON", os.path.exists(work / "chord_analysis.json"))

    # 3. 脚本可重放
    for s in ["01_separate.py", "02_transcribe_vocals.py", "03_melody_grid.py",
              "04_chord_analyze.py", "05_build_ly.py", "06_render.sh", "07_compare_original.py"]:
        check(f"脚本 {s}", os.path.exists(ROOT / "workflow" / s))

    # 4. 谱面源文件：和弦数 = n_bars 且与 config 段落序列一致
    ly = sorted(out.glob("*_piano.ly"))
    n_bars = int(song["n_bars"])
    if ly:
        txt = ly[0].read_text(encoding="utf-8")
        m = re.search(r"harmonies\s*=\s*\\chordmode\s*\{(.*?)\n\}", txt, re.S)
        chords = re.findall(r"([a-g](?:is|es)?1(?::maj7|:m|:7|:maj|:min|/)?(?:/[a-g](?:is|es)?)?)",
                            m.group(1) if m else "")
        check("ly 和弦数=n_bars", len(chords) == n_bars, f"实际 {len(chords)}")
        seq = []
        for sec in cfg["chords"]["sections"]:
            loop = sec["chords"]
            for b in range(int(sec["start"]) - 1, int(sec["end"])):
                seq.append(cfg["chords"]["chord_map"][loop[b % len(loop)]]["chordsym"])
        check("和弦序列与 config 一致", chords == seq,
              f"差异 {sum(1 for a, b in zip(chords, seq) if a != b)} 处")
    else:
        check("ly 谱面存在", False, "缺 *_piano.ly")

    # 5. 渲染产物
    check("渲染 PDF", bool(list(out.glob("*_piano.pdf"))))
    check("渲染 MP3", bool(list(out.glob("*.mp3"))))

    # 6. 最终闭环：渲染产物 vs 原曲
    mp3 = sorted(out.glob("*.mp3"))
    if mp3:
        r = subprocess.run([sys.executable, str(ROOT / "workflow" / "07_compare_original.py"),
                            str(cfg_path), str(mp3[0])], capture_output=True, text=True)
        tail = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
        check("原曲闭环比对(时长/BPM/拍点)", r.returncode == 0,
              tail[-1] if tail else "运行失败")
    else:
        check("原曲闭环比对", False, "缺渲染 MP3")

    # 7. 工具链
    for t in ["lilypond", "mscore", "demucs", "audio-separator", "basic-pitch", "ffprobe"]:
        check(f"工具 {t}", have(t) or (t == "mscore" and os.path.exists(
            "/System/Volumes/Data/Applications/MuseScore 4.app/Contents/MacOS/mscore")))

    # 8. 旋律网格小节数与音域
    if os.path.exists(work / "melody_grid.json"):
        g = json.load(open(work / "melody_grid.json", encoding="utf-8"))
        check("旋律网格=n_bars", len(g["bars"]) == n_bars, f"实际 {len(g['bars'])}")
        ps = [s["p"] + (12 if s["p"] < mel["octave_fix_threshold"] else 0)
              for b in g["bars"] for s in b["slots"]]
        if ps:
            check("旋律音域 G4-C6", 66 <= min(ps) and max(ps) <= 84, f"范围 {min(ps)}-{max(ps)}")

    print("== 通过 ==")
    for x in ok:
        print("  [OK]", x)
    print("== 失败/待人工 ==")
    for x in fail:
        print("  [!!]", x)
    print(f"\n总计 {len(ok)} 通过, {len(fail)} 未通过")


if __name__ == "__main__":
    main()
