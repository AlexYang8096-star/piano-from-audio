# 方法论与踩坑记录

本文档沉淀自《Gracie Abrams - us.》完整项目的实战经验，是本管线 7 个阶段背后的设计依据。

## 目标定义

把原曲的**人声 + 伴奏统一转成一份钢琴独奏谱**，用钢琴演奏出来的效果**无限接近听原曲**：
- 右手 = 人声主旋律（8 分音符量化）
- 左手 = 伴奏和弦（前八后十六柱式）
- 和弦标记 + 分段力度 + 速度标注齐全，可直接演奏

## 各阶段要点

### 01 分离

- 模型选择：`melband_roformer_instvox_duality_v2`（UVR 社区）。无钢琴专属模型时，**用 Instrumental 整轨作低音来源**——实测 demucs 旧 piano 轨低音能量仅为 Instrumental 轨的 1/250，不能用作低音。
- 必须校验：分离轨与原曲时长一致（ffprobe），防截断。

### 02 转录

- basic-pitch 转录 Vocals 轨。若报 `ValueError`（onnx 后端问题），确认使用包内 nmp.onnx 后端。
- 产物检查：音符数量 800+、按 30 秒分段密度均匀、音高集中在主旋律区。

### 03 旋律量化

- 按 BPM 4/4 网格：每小节 `60/BPM*4` 秒，8 分格 = 小节/8。
- 过滤：音高超出主旋律带（默认 55–88）与短于 0.09s 的杂音；同一 8 分格取 velocity 大的音符。
- 输出 `melody_grid.json`（逐小节 8 分格，空位 = 休止）。

### 04 和弦分析（辅助，非最终）

- 对 Instrumental 轨做 beat_track，4 拍一组切小节；30–250Hz 低频段能量峰取低音根音候选；全频 chroma top5 作和弦内音参考。
- **公开资料裁决**：低音频谱受泛音干扰只能作参考，最终和弦进行应以公开和弦集（如 ChordZone/Klangio）交叉确认后，写入 `config.json` 的 `chords.sections`。
- 案例：《us.》最终裁决 Intro/Verse = Em-D-C-G，Chorus = G-C-D-G，Bridge = Em-G-C-D。

### 05 谱面生成

- 右手旋律：八度修正规则 `pitch < 64 → +12`（basic-pitch 会把同一旋律线段落放到低八度）。
- 左手：前八后十六柱式 `低音8( 柱式16 柱式16)` ×4/小节，如 `g8( <b d'>16 <b d'>16)`。
- 和弦标记：`\chordmode` 每小节一个，`\set chordChanges = ##t` 省略重复，**必须写时长**（`e1:m` 而非 `e:m`）。
- 段落：每段独立力度（Intro mp → Verse mf → Chorus f → Bridge mp → Final ff），段末 `\break`。

### 06 渲染

- **禁 `\relative`，用 `\absolute` 写死音高**：`\relative` 连续解析会跨小节累积升八度。
- 排版偏好：每行 2 小节、每页 7 行；超过 3 条加线用 8va/8vb；左手 ≥ B2、右手 ≤ G5 为宜。

### 07 最终闭环（必须做）

- 渲染 MP3 与原曲音频客观比对：时长（容差 5%）、BPM（容差 3%）、拍点数（容差 8%）、chroma 调性倾向。
- **不通过不得交付**。速度/时值对得上只代表"速度一致"，最终还要人工双盲试听：先听渲染 MP3 再听原曲，核对主旋律走向、和弦色彩、段落衔接。
- MIDI 校验不可用：LilyPond 生成 MIDI 的 note_on 时间戳不可靠，闭环比对必须走音频分析。

## 踩坑清单（复用时直接规避）

| # | 坑 | 规避 |
|---|---|---|
| 1 | 钢琴专属轨低音能量不足 | 用 Instrumental 整轨作低音来源 |
| 2 | 伴奏轨 beat_track 误报 BPM | 速度以含人声整曲为准 |
| 3 | `\relative` 跨小节累积升八度 | 全曲 `\absolute` |
| 4 | basic-pitch 八度漂移（段落性低八度） | `pitch < 阈值` 统一 +12 |
| 5 | LilyPond MIDI 时间戳不可靠 | 校验走音频分析，不走 MIDI |
| 6 | 视觉模型读谱幻觉 | 以源 .ly + 音高计算为准，视觉只做粗查 |
| 7 | chordmode 不写时长报错 | `e1:m` 而非 `e:m` |
| 8 | 新版 CPython 装不了 basic-pitch | 使用 Python 3.10–3.12 |
| 9 | 谱面和弦进行写错（听感差根源） | 用公开资料裁决，勿只信频谱估计 |

## 新歌复用清单（换歌时改什么）

1. `config.json`：输入音频路径、歌名、调号、BPM、小节数。
2. 重新跑 01→04，用 04 结果 + 公开资料更新 `chords.sections` 与 `chord_map`。
3. `03_melody_grid.py` 无需改代码（全参数化）；如旋律音域特殊，调整 `pitch_min/max` 与 `octave_fix_threshold`。
4. 渲染后务必跑 Step 07 闭环比对与人工试听。
