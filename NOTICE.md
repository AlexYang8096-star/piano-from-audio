# NOTICE

本仓库的代码采用 MIT License 发布（见 LICENSE）。以下为运行时依赖与模型权重的许可说明，使用前请逐一确认：

| 组件 | 用途 | 许可 |
|---|---|---|
| [basic-pitch](https://github.com/spotify/basic-pitch) | 旋律转录（ICASSP 2022 模型） | Apache-2.0 |
| [librosa](https://github.com/librosa/librosa) | 音频分析 | ISC |
| [pretty_midi](https://github.com/craffel/pretty_midi) | MIDI 处理 | MIT |
| [numpy](https://numpy.org) | 数值计算 | BSD-3-Clause |
| [audio-separator](https://github.com/nice1it/audio-separator) | 人声/伴奏分离 | MIT |
| [LilyPond](https://lilypond.org) | 乐谱排版 | GPL-3.0+ |
| [MuseScore 4](https://musescore.org) | MIDI→MP3 渲染 | GPL-3.0 |

## 模型权重

- `melband_roformer_instvox_duality_v2` 来自 UVR（Ultimate Vocal Remover）社区，由 audio-separator 下载。UVR 模型权重通常以社区条款分发（非商用/署名要求），请以实际下载页的许可声明为准。
- basic-pitch 的 ICASSP 2022 转录模型权重随 Python 包分发，遵循 Apache-2.0。

## 免责声明

本项目仅用于音乐学习与研究。请仅对你拥有合法权利的音频运行本工具；因扒谱/改编产生的音乐作品版权问题由使用者自行负责。不要将受版权保护的原曲音频、分离轨或成品谱提交到本仓库。
