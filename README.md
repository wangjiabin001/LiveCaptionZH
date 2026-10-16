# LiveCaptionZH · 实时中文字幕

把**电脑正在播放的任何外语声音**（浏览器、播放器、直播软件都行）实时变成**中文字幕条**，悬浮在屏幕下方，不吃鼠标点击、不看播放器脸色。

> 适用场景：看外语电影/剧集没有中文字幕、看国外直播、看 YouTube/TED、开英文会议……
> 只要声音从你电脑的扬声器出来，它就能听。

## 实测效果

播放一段英文音频，屏幕上底部的字幕条：

```
I am watching a foreign movie right now, and I really want to see Chinese subtitles.
我现在正在看一部外语电影，而且我特别想要中文字幕。
```

字幕延迟约 **1~2 秒**（本地 GPU 推理），可点击穿透、可调字号/位置/透明度。

## 它是怎么工作的

```
系统正在播放的声音
      │  soundcard（WASAPI 环回采集，无需虚拟声卡）
      ▼
16kHz 单声道 PCM
      │  WhisperLiveKit（11.1k★）· faster-whisper 流式识别
      ▼
外语文字
      │  NLLB-200 翻译（200 语言 → 中文，本地离线）
      ▼
中文字幕条
      │  tkinter 透明置顶窗（点击穿透）
      ▼
屏幕下方
```

**本项目只写了「胶水」，不造轮子**：

| 能力 | 用谁 |
| --- | --- |
| 实时流式识别 | [WhisperLiveKit](https://github.com/QuentinFuxa/WhisperLiveKit) 11.1k★ |
| 识别模型 | [faster-whisper](https://github.com/SYSTRAN/faster-whisper)（CTranslate2）large-v3 |
| 翻译 | [NLLB-200-distilled-600M](https://huggingface.co/facebook/nllb-200-distilled-600M) + [nllw](https://github.com/QuentinFuxa/NoLanguageLeftWaiting) |
| 系统声音采集 | [soundcard](https://github.com/bastibe/SoundCard)（WASAPI loopback） |
| 悬浮字幕窗 | Python 标准库 tkinter（**本项目唯一的自写层**） |

源码总共约 400 行，其中真正"自己写的逻辑"就是一个采集循环 + 一个字幕窗口。

## 快速开始

### 1. 装依赖

双击 **`install.cmd`**（需要 Python 3.10+）

### 2. 下模型

双击 **`下载模型.cmd`**（约 5.5GB，会自动优先走国内源）

- 识别模型 large-v3（3.0GB）→ 从 **ModelScope** 拉，比 HuggingFace 镜像快十几倍
- 翻译模型 NLLB（2.35GB）→ 从 hf-mirror 拉

> 不想等 / 磁盘紧张？可以改 `config.json` 里的 `"model"` 为 `small` 或 `medium`，
> 翻译也能关掉（`"translate": false`，只看外语原文）。

### 3. 开始用

双击 **`start.cmd`**，然后随便播个外语视频 —— 字幕自己就出来了。
**关掉那个黑窗口就是退出。**

## 配置

首次运行会生成 `config.json`：

| 字段 | 说明 | 默认 |
| --- | --- | --- |
| `model` | 识别模型：tiny/base/small/medium/large-v3 | `large-v3` |
| `language` | 源语言。`en` 更快更准，`auto` 自动判断 | `auto` |
| `target_language` | 目标语言 | `zh` |
| `translate` | 是否翻译（关掉=只显示原文） | `true` |
| `device` | 采集哪个播放设备，留空=系统默认 | `""` |
| `font_size` / `source_font_size` | 中文字号 / 原文字号 | `28` / `15` |
| `show_source` | 是否同时显示原文 | `true` |
| `max_lines` | 字幕条保留几行 | `2` |
| `bottom_offset` | 距屏幕底部像素 | `90` |
| `alpha` | 不透明度 | `0.85` |
| `click_through` | 点击穿透（不挡鼠标） | `true` |

也可以命令行临时覆盖：

```bat
start.cmd --model medium --language en --font-size 34 --no-source
start.cmd --list-devices          :: 列出可采集的播放设备
start.cmd --console               :: 不开字幕窗，只在终端打印（调试用）
```

## 硬件要求

| | 最低 | 推荐 |
| --- | --- | --- |
| 显卡 | 无（CPU 跑 `small` 模型） | NVIDIA 显卡 + 8GB 显存（实测 RTX 3070 跑 large-v3 int8） |
| 内存 | 8GB | 16GB |
| 磁盘 | ~7GB（模型） | ~10GB |

CPU 也能跑，但要用小模型（`small` 及以下），字幕延迟会到 3~5 秒。

## 常见问题

**Q：为什么不直接做个播放器插件？**
很多播放器确实有字幕功能，但它们只能显示"片子里已经有的字幕轨"。你这个需求是片子**根本没有字幕**，那就必须先做语音识别，这已经超出播放器插件的范围了。本项目直接抓系统声音，好处是**跟任何播放器/浏览器都解耦**。

**Q：为什么没直接用 GitHub 上现成的"实时字幕"项目？**
搜过了：识别+翻译的**引擎**很成熟（WhisperLiveKit 等），但"抓系统声音 → 悬浮中文字幕"这一层的现成项目**全是 0~45 星的新坑**（多数没有 README、只支持 macOS、或不翻译中文）。所以选择用成熟引擎 + 自己写这层胶水。

**Q：延迟为什么消不掉？**
识别要等一句话说出一部分才敢下判断，加上翻译时间，1~2 秒是本地推理的物理下限。**电影对白效果明显好于直播**（直播有口音、背景音、抢话）。

**Q：模型下载太慢？**
识别模型走 ModelScope（国内很快）；翻译模型走 hf-mirror（时快时慢，脚本会自动断点续传）。实在不行就先只用识别（`"translate": false`）。

**Q：字幕挡住视频了？**
默认在屏幕底部 90px、点击穿透，不挡鼠标。位置/字号在 `config.json` 里调。

## 许可证

MIT

## 致谢

本项目站在这些项目肩上：WhisperLiveKit、faster-whisper、CTranslate2、OpenAI Whisper、NLLB / NoLanguageLeftWaiting、SoundCard。
识别模型来自 ModelScope 镜像仓库 `pengzhendong/faster-whisper-large-v3`。

---

## English

**LiveCaptionZH** — real-time Chinese subtitles for *anything playing on your PC*.
It captures system audio via WASAPI loopback (no virtual cable needed), streams it through
[WhisperLiveKit](https://github.com/QuentinFuxa/WhisperLiveKit) (faster-whisper + NLLB translation),
and renders a click-through always-on-top subtitle bar with tkinter.

Works with any player, browser, or live stream. ~1-2s latency on a local GPU.
Only ~400 lines of glue code — the heavy lifting is done by mature upstream projects.

License: MIT