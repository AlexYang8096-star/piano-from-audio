#!/usr/bin/env python3
"""Step 05: 生成 LilyPond 谱面源文件（支持谱面微调 tune）
右手=人声旋律（含八度修正），左手=前八后十六柱式，和弦标记=config 中真实进行。
用法: python3 workflow/05_build_ly.py config.json [--tune lh_vel=+2,rh_density=-2,tempo=+1]

tune 微调字段（config 顶层 "tune" 或 --tune 覆盖，每项取值 -3..+3，0=原始）：
  lh_vel     左手强度档（在 LH_DYN_OFFSET 弱化后基础上再偏移，clamp 到 \\pppp..\\fff）
  rh_vel     右手强度档（在段落 dyn 基础上偏移，clamp 到 \\pppp..\\fff）
  lh_density 左手疏密档（负=简化：前八后十六→前八后八→四分柱式→低音长音；正=加密：十六分分解/密集柱式）
  rh_density 右手疏密档（负=去弱位保留强拍骨干；正=休止/长音槽补和弦音至16分）
  tempo      速度档（每档 ±20 BPM，基准 song.bpm：-3→76/-2→96/-1→116/0→136/+1→156/+2→176/+3→196）
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ------------------------------------------------------------
# 力度档位阶梯（clamp 范围 \\pppp .. \\fff）
# ------------------------------------------------------------
DYN_LADDER = ["\\pppp", "\\ppp", "\\pp", "\\p", "\\mp", "\\mf", "\\f", "\\ff", "\\fff"]


def shift_dyn(dyn, k):
    """在力度阶梯上平移 k 档并 clamp 到 \\pppp..\\fff；不在阶梯内则原样返回。"""
    if dyn in DYN_LADDER:
        idx = max(0, min(len(DYN_LADDER) - 1, DYN_LADDER.index(dyn) + k))
        return DYN_LADDER[idx]
    return dyn


# 左手伴奏整体比右手弱一档（钢琴编配惯例：旋律突出、伴奏衬底）
LH_DYN_OFFSET = {
    "\\ppp": "\\ppp",
    "\\pp": "\\ppp",
    "\\p": "\\pp",
    "\\mp": "\\p",
    "\\mf": "\\mp",
    "\\f": "\\mf",
    "\\ff": "\\f",
}


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


# ============================================================
# 休止符固定规范（固化为固定代码，禁止手写绕过）
# ------------------------------------------------------------
# 1. 整小节静默：一律输出全音符休止符 r1（4/4 拍恰好占满一小节），
#    严禁输出 8 个八分休止符 r8 堆叠 —— 谱面臃肿且不符合记谱惯例。
# 2. 小节内连续休止：按「全 > 二分 > 四分 > 八分」贪心合并，
#    如 7 个 r8 → r2 + r4 + r8；仅孤立单拍空隙保留 r8。
# 3. 适用范围：melody_bar 整小节无音符时即整小节静默；
#    未来新增任何声部（左手/内声部）若出现整小节静默，
#    必须复用 rest_bar()，禁止手写 r8 堆叠。
# ============================================================
def rest_bar():
    """整小节静默 → 全音符休止 r1（4/4 拍占满一小节）。"""
    return "r1 |"


def _emit_rests(run):
    """把 run 个八分休止贪心拆成规范时值序列（不跨小节）。"""
    parts = []
    for val, dur in ((8, "r1"), (4, "r2"), (2, "r4"), (1, "r8")):
        while run >= val:
            parts.append(dur)
            run -= val
    return parts


def merge_rests(tokens):
    """合并连续 r8 休止符为更长时值（r1/r2/r4），保持音符顺序不变。"""
    out = []
    run = 0
    for t in tokens:
        if t == "r8":
            run += 1
            continue
        if run:
            out.extend(_emit_rests(run))
            run = 0
        out.append(t)
    if run:
        out.extend(_emit_rests(run))
    return out


def _emit_rests_16(run):
    """把 run 个十六分休止贪心拆成规范时值序列（不跨小节）。"""
    parts = []
    for val, dur in ((16, "r1"), (8, "r2"), (4, "r4"), (2, "r8"), (1, "r16")):
        while run >= val:
            parts.append(dur)
            run -= val
    return parts


def merge_rests_16(tokens):
    """合并连续 r16 休止符为更长时值（r1/r2/r4/r8），保持音符顺序不变。"""
    out = []
    run = 0
    for t in tokens:
        if t == "r16":
            run += 1
            continue
        if run:
            out.extend(_emit_rests_16(run))
            run = 0
        out.append(t)
    if run:
        out.extend(_emit_rests_16(run))
    return out


# ============================================================
# 右手旋律小节：基础 / 减疏 / 加密
# ------------------------------------------------------------
RH_SPARSE_KEEP = {
    -1: {0, 2, 4, 6},   # 去弱位（1/3/5/7 槽装饰音）
    -2: {0, 2, 4},      # 进一步去 6 槽
    -3: {0, 4},         # 只保留两拍强拍主干
}


def _slots_of(b):
    return {s["s"]: s for s in b.get("slots", [])}


def _mel_tokens_8(slots, fix_threshold, keep=None):
    """8 分槽 → token 序列；keep 为 None 表示全部保留（原始）。"""
    tokens = []
    for s8 in range(8):
        if s8 in slots and (keep is None or s8 in keep):
            p = slots[s8]["p"]
            if p < fix_threshold:
                p += 12
            tokens.append(pitch_name(p) + "8")
        else:
            tokens.append("r8")
    return tokens


def _chord_pitch_tokens(chord_map, chord, count, low_then_upper=False):
    """从当前小节和弦取 count 个补音音名序列（含八度撇号格式）。
    low_then_upper=True 时优先低音参与（更饱满的 16 分填充）。"""
    cm = chord_map[chord]
    low = cm["low"]
    upper = re.sub(r"[<>]", "", cm["upper"]).split()
    pool = ([low] + upper) if low_then_upper else upper
    if not pool:
        pool = [low]
    return [pool[i % len(pool)] for i in range(count)]


def _dense_16_slots(slots, fix_threshold, fill):
    """构造 16 分粒度小节：fill 是 16 个槽位列表，None=休止。
    返回 (tokens, has_note)。原 8 分音占两个 16 槽（输出 pitch8）。"""
    tokens = []
    for s16 in range(16):
        t = fill[s16]
        if t is None:
            tokens.append("r16")
        else:
            tokens.append(t)
    return tokens


def melody_bar(bars, bar_idx, fix_threshold, chord, chord_map, tune):
    """右手小节：按 rh_density 档位生成（0=原始；负=减疏；正=加密）。"""
    b = bars[bar_idx]
    slots = _slots_of(b)
    rh_density = tune.get("rh_density", 0)

    # 加密：在休止/长音槽补和弦音（16 分粒度）
    if rh_density > 0:
        # 16 个 16 分槽：原 8 分音占 [2s, 2s+1]
        fill = [None] * 16
        has_note = False
        for s8 in range(8):
            if s8 in slots:
                p = slots[s8]["p"]
                if p < fix_threshold:
                    p += 12
                fill[2 * s8] = pitch_name(p) + "16"
                fill[2 * s8 + 1] = pitch_name(p) + "16"
                has_note = True
        # 对空 8 分槽补和弦音（level 1: 8分粒度 → level 2/3: 16分分解）
        level = rh_density
        for s8 in range(8):
            if s8 in slots:
                continue
            if level == 1:
                # 空槽补 8 分和弦音（用第一个补音）
                p = _chord_pitch_tokens(chord_map, chord, 1, low_then_upper=False)[0]
                fill[2 * s8] = p + "8"
                fill[2 * s8 + 1] = p + "8"
                has_note = True
            else:
                # level 2：upper 两音分解；level 3：低音+upper 更饱满
                p2 = _chord_pitch_tokens(chord_map, chord, 2, low_then_upper=(level >= 3))
                fill[2 * s8] = p2[0] + "16"
                fill[2 * s8 + 1] = p2[1] + "16"
                has_note = True
        if not has_note:
            return rest_bar()
        return " ".join(merge_rests_16(_dense_16_slots(slots, fix_threshold, fill))) + " |"

    # 减疏：只保留强拍/主干槽，移除处 r8 占位后合并
    if rh_density < 0:
        if not slots:
            return rest_bar()
        keep = RH_SPARSE_KEEP.get(rh_density, {0, 2, 4, 6})
        tokens = merge_rests(_mel_tokens_8(slots, fix_threshold, keep))
        return " ".join(tokens) + " |"

    # 原始：8 分粒度 + 休止合并
    if not slots:
        return rest_bar()
    return " ".join(merge_rests(_mel_tokens_8(slots, fix_threshold, None))) + " |"


# ============================================================
# 左手小节：前八后十六柱式 / 减疏 / 加密
# ------------------------------------------------------------
def _strip_angle(upper):
    return re.sub(r"[<>]", "", upper)


def lh_bar(chord, chord_map, density):
    """左手小节：按 lh_density 档位生成（0=原始前八后十六；负=简化；正=加密）。"""
    low, upper = chord_map[chord]["low"], chord_map[chord]["upper"]
    up = _strip_angle(upper)

    if density == -1:
        # 前八后八：每拍 low8 upper8
        return " ".join([f"{low}8 {up}8"] * 4) + " |"
    if density == -2:
        # 四分柱式：每拍一个低音+和弦柱式
        return " ".join([f"<{low} {up}>4"] * 4) + " |"
    if density == -3:
        # 低音长音：整小节低音全音符
        return f"{low}1 |"
    if density == +1:
        # 十六分分解（低音 16 + 和弦 16×3）
        return " ".join([f"{low}16( {upper}16 {upper}16 {upper}16)"] * 4) + " |"
    if density == +2:
        # 十六分分解交替（低-和-低-和）
        return " ".join([f"{low}16 {upper}16 {low}16 {upper}16"] * 4) + " |"
    if density == +3:
        # 密集柱式：每 8 分一个低音+和弦柱式
        return " ".join([f"<{low} {up}>8"] * 8) + " |"

    # 原始：前八后十六柱式
    return f"{low}8( {upper}16 {upper}16) " * 4 + "|"


def parse_tune_overrides(text):
    """解析 --tune "lh_vel=+2,rh_density=-2,tempo=+1" 形式的覆盖参数。"""
    out = {}
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^(\w+)\s*=\s*([+-]?\d+)$", part)
        if not m:
            raise SystemExit(f"无法解析 tune 覆盖: {part!r}，应为 name=±N")
        out[m.group(1)] = int(m.group(2))
    return out


def load_tune(cfg, cli_overrides):
    """合并 config["tune"] 与 CLI 覆盖；缺省字段默认 0（原始）。"""
    defaults = {"lh_vel": 0, "rh_vel": 0, "lh_density": 0, "rh_density": 0, "tempo": 0}
    tune = dict(defaults)
    tune.update(cfg.get("tune", {}) or {})
    tune.update(cli_overrides)
    for k in defaults:
        v = tune[k]
        if not isinstance(v, int) or not (-3 <= v <= 3):
            raise SystemExit(f"tune.{k} 必须为 -3..+3 的整数，当前: {v!r}")
    return tune


def main():
    argv = sys.argv[1:]
    cfg_path = Path(argv[0]) if argv and not argv[0].startswith("--") else ROOT / "config.json"
    cli_overrides = {}
    for a in argv:
        if a.startswith("--tune"):
            idx = argv.index(a)
            if idx + 1 < len(argv):
                cli_overrides = parse_tune_overrides(argv[idx + 1])

    cfg = json.load(open(cfg_path, encoding="utf-8"))
    song, chords_cfg = cfg["song"], cfg["chords"]
    mel = cfg["melody"]
    tune = load_tune(cfg, cli_overrides)

    work = (ROOT / song["work_dir"]).resolve()
    out_dir = (ROOT / song["output_dir"]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    grid = json.load(open(work / "melody_grid.json", encoding="utf-8"))
    bars = grid["bars"]
    n_bars = int(song["n_bars"])
    bpm = float(song["bpm"]) + tune["tempo"] * 20  # 速度每档 ±20 BPM（-1→116/-2→96/-3→76/+1→156/+2→176/+3→196）
    key = song["key"]

    chord_seq = build_chord_seq(chords_cfg["sections"], n_bars)
    chord_map = chords_cfg["chord_map"]

    # 非全 0 时输出文件名带档位后缀，避免覆盖原始谱面
    suffix = ""
    if any(tune[k] != 0 for k in tune):
        tags = [f"{k}{tune[k]:+d}" for k in ("lh_vel", "rh_vel", "lh_density", "rh_density", "tempo")]
        suffix = "_tune_" + "_".join(tags)
    ly_path = out_dir / f"{Path(cfg_path).stem}_piano{suffix}.ly"

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
            dyn = shift_dyn(sec["dyn"], tune["rh_vel"]) if b == int(sec["start"]) - 1 else ""
            lines.append("  " + (dyn + " " if dyn else "") + melody_bar(bars, b, mel["octave_fix_threshold"], chord_seq[b], chord_map, tune))
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
            base = LH_DYN_OFFSET.get(sec["dyn"], sec["dyn"])
            dyn = shift_dyn(base, tune["lh_vel"]) if b == int(sec["start"]) - 1 else ""
            lines.append("  " + (dyn + " " if dyn else "") + lh_bar(chord_seq[b], chord_map, tune["lh_density"]))
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
    print("written:", ly_path, "lines:", len(lines), "tune:", tune)

    # 校验：以 | 结尾的小节行数 = rh + lh + harmonies 三组各 n_bars 行
    n_endpipe = sum(1 for l in lines if l.rstrip().endswith("|"))
    print("pipe-terminated bar lines:", n_endpipe, "expected:", 3 * n_bars)
    ok = n_endpipe == 3 * n_bars
    print("pipe-check:", "OK" if ok else "FAIL")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
