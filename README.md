# Piano From Audio

把一首歌（人声 + 伴奏完整音频）自动转成一份**可演奏、听感贴近原曲**的钢琴独奏谱（PDF + 试听 MP3）。

右手承载人声旋律，左手承载伴奏和弦，听者无需听原曲也能还原歌曲全貌。本仓库包含从分离、转录、量化、和弦分析、谱面生成到最终闭环校验的完整可复现管线。

> ⚠️ 本项目是**工具**，不是成品谱。请仅对你拥有合法权利的音频使用；不要将受版权保护的原曲、分离轨或成品谱提交到仓库。

## 原理

```
原曲音频
  │ ① 分离（audio-separator → Vocals + Instrumental）
  ▼
  ├─ Vocals ──► ② basic-pitch 转录 MIDI ──► ③ 按 BPM 网格量化旋律（8 分格）
  │
  └─ Instrumental ──► ④ 低音频谱分析（辅助定和弦，建议与公开和弦资料交叉确认）
  │
  ▼
⑤ 编配（右手=旋律，左手=前八后十六柱式，和弦标记，分段力度）
  │
  ▼
⑥ 渲染（LilyPond → PDF + MIDI，MuseScore → MP3）
  │
  ▼
⑦ 最终闭环：渲染 MP3 与原曲客观比对（时长 / BPM / 拍点），不通过不得交付
```

## 环境要求

- macOS（Apple Silicon 或 Intel）/ Linux，Python 3.10+
- 依赖：`librosa`、`pretty_midi`、`numpy`、`audio-separator`、`basic-pitch`、`ffprobe`
- 渲染：LilyPond 2.26+、MuseScore 4（可选，仅 MP3 试听需要）

```bash
pip install librosa pretty_midi numpy audio-separator basic-pitch
brew install lilypond ffmpeg   # ffmpeg 提供 ffprobe；MuseScore 4 建议从官网安装
```

> 注意：basic-pitch 与较新的 CPython（3.13+）不兼容，建议使用 3.10–3.12 环境。

## 快速开始

```bash
# 1. 复制示例配置并填写你的歌曲信息
cp config.example.json config.json
# 编辑 config.json：input_audio 填原曲绝对路径，song 填歌名/调号/BPM/小节数，
# chords.sections 填段落与和弦进行（Step 04 的分析结果 + 公开资料交叉确认）

# 2. 按阶段执行
python3 workflow/01_separate.py config.json        # 分离两轨
python3 workflow/02_transcribe_vocals.py config.json  # 转录旋律 MIDI
python3 workflow/03_melody_grid.py config.json     # 旋律量化
python3 workflow/04_chord_analyze.py config.json   # 低音/和弦分析（辅助定和弦）
python3 workflow/05_build_ly.py config.json        # 生成 LilyPond 源文件
bash workflow/06_render.sh output/<name>_piano.ly  # 渲染 PDF/MIDI/MP3
python3 workflow/07_compare_original.py config.json output/<name>_piano.mp3  # 最终闭环比对

# 3. 自检（建议每次交付前跑）
python3 selfcheck/selfcheck_workflow.py config.json
```

## 目录结构

```
piano-from-audio/
├── config.example.json    # 示例配置（复制为 config.json 使用）
├── workflow/              # 阶段脚本 01→07
├── selfcheck/             # 管线自检（26 项）
├── docs/workflow.md       # 方法论与踩坑记录
└── examples/              # 示例输出说明
```

## 关键经验（详见 docs/workflow.md）

- 分离：无钢琴专属模型时用 Instrumental 整轨作低音来源（旧 piano 轨低音能量可能低 250 倍）
- 速度：BPM 以含人声整曲的 beat_track 为准（伴奏轨易被 8 分节奏误报）
- 八度漂移：basic-pitch 会把旋律段落放到低八度，统一 `pitch < 阈值 → +12` 修正
- 排版：LilyPond 禁 `\relative`（跨小节累积升八度），用 `\absolute` 写死音高
- 校验：LilyPond 生成的 MIDI 时间戳不可靠，闭环比对必须走音频分析（Step 07）

## License

MIT © AlexYang8096-star

依赖与模型权重许可见 [NOTICE.md](NOTICE.md)。本项目不包含任何受版权保护的音乐素材。
