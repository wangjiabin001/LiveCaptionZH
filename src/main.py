# -*- coding: utf-8 -*-
"""实时中文字幕 · LiveCaptionZH —— 入口

干什么：把电脑正在播放的外语声音，实时变成中文悬浮字幕。
架构（识别/翻译全部用现成开源项目，本仓库只写"胶水"）：

    系统声音采集   soundcard（WASAPI 环回，10 行调用）
        ↓ 16kHz 单声道 PCM
    实时识别 + 翻译  WhisperLiveKit 11.1k★（内含 faster-whisper + NLLB 翻译）
        ↓ 文字
    悬浮字幕条     tkinter 透明置顶窗（本仓库唯一的自写层）
"""
from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONFIG_PATH = os.path.join(ROOT, "config.json")
EXAMPLE_PATH = os.path.join(ROOT, "config.example.json")

DEFAULTS = {
    "model": "large-v3",          # tiny/base/small/medium/large-v3
    "language": "auto",           # 源语言。"en" 更快更准，"auto" 自动判断
    "target_language": "zh",      # 目标语言（中文）
    "translate": True,            # False = 只转写不翻译
    "device": "",                 # 采集哪个播放设备（留空=系统默认播放设备）
    "font_size": 28,
    "source_font_size": 15,
    "show_source": True,          # 是否同时显示原文
    "max_lines": 2,               # 字幕条上保留几行
    "width_ratio": 0.82,
    "bottom_offset": 90,
    "alpha": 0.85,
    "click_through": True,        # 字幕条不挡鼠标点击
}


def _prepare_env() -> None:
    """必须在 import faster_whisper / whisperlivekit 之前执行。"""
    # 模型源：国内直连 huggingface.co 不通，默认走镜像（可用环境变量覆盖）
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    # 镜像不代理 Xet 存储，关掉它才能正常下载
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    # 本地模型齐全时强制离线：避免运行时再去联网校验模型（国内访问 HF 不稳定）
    if os.path.isdir(os.path.join(ROOT, "models", "faster-whisper-large-v3")) or \
       os.path.isdir(os.path.join(ROOT, "models")):
        _models = os.path.join(ROOT, "models")
        if os.path.isdir(_models) and any(
            os.path.isdir(os.path.join(_models, d)) for d in os.listdir(_models)
        ):
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
    # CUDA 运行时：把 pip 装的 nvidia-cublas/cudnn 的 DLL 目录加进搜索路径
    nv = os.path.join(sys.prefix, "Lib", "site-packages", "nvidia")
    if os.path.isdir(nv):
        for sub in sorted(os.listdir(nv)):
            for cand in ("bin", "lib"):
                d = os.path.join(nv, sub, cand)
                if os.path.isdir(d):
                    try:
                        os.add_dll_directory(d)
                    except Exception:
                        pass
                    os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]


def load_config(path: str) -> dict:
    cfg = dict(DEFAULTS)
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception as e:
            print(f"[警告] 读取配置失败，使用默认值：{e}")
    return cfg


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="实时中文字幕：把电脑播放的外语声音变成中文字幕条",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--config", default=CONFIG_PATH, help="配置文件路径")
    p.add_argument("--model", help="Whisper 模型：tiny/base/small/medium/large-v3")
    p.add_argument("--language", help="源语言，如 en / ja / ko / auto")
    p.add_argument("--target-language", dest="target_language", help="目标语言，默认 zh")
    p.add_argument("--device", help="采集的播放设备名（可用 --list-devices 查看）")
    p.add_argument("--list-devices", action="store_true", help="列出可采集的设备后退出")
    p.add_argument("--no-translate", action="store_true", help="只转写，不翻译")
    p.add_argument("--font-size", type=int, help="中文字号")
    p.add_argument("--alpha", type=float, help="字幕条不透明度 0.3~1.0")
    p.add_argument("--bottom-offset", type=int, help="距屏幕底部像素")
    p.add_argument("--max-lines", type=int, help="字幕条保留行数")
    p.add_argument("--no-source", action="store_true", help="不显示原文，只显示中文")
    p.add_argument("--no-click-through", action="store_true", help="字幕条可被鼠标点到")
    p.add_argument("--console", action="store_true", help="不开字幕窗，只在终端打印（调试用）")
    p.add_argument("--once", type=float, metavar="秒", help="跑指定秒数后自动退出（自测用）")
    return p.parse_args(argv)


class CaptionPipeline:
    """系统声音 → WhisperLiveKit 实时识别+翻译 → 字幕条"""

    def __init__(self, cfg: dict, overlay=None, console: bool = False):
        self.cfg = cfg
        self.overlay = overlay
        self.console = console
        self.running = True
        self._capture = None
        self._last_pairs: list[tuple[str, str]] = []
        self.translator = None
        self._mt_warned = False
        self._t0 = time.time()

    # ---------- 引擎参数 ----------
    def _engine_kwargs(self) -> dict:
        from whisperlivekit.config import WhisperLiveKitConfig

        model = self.cfg["model"]
        model_args = {}
        # 本地已有模型（由 下载模型.cmd 预先下好）→ 走官方 model_dir 入口，完全不联网
        local = model if os.path.isdir(model) else os.path.join(ROOT, "models", f"faster-whisper-{model}")
        if os.path.isdir(local):
            model_args["model_dir"] = local
        else:
            model_args["model_size"] = model

        wanted = {
            **model_args,
            # 用纯 CTranslate2 的 LocalAgreement 通路：不依赖 PyTorch/CUDA，
            # 稳定性最好（SimulStreaming 需要 CUDA 版 torch 才能跑 AlignAtt 解码）
            "backend": "faster-whisper",
            "backend_policy": "localagreement",
            "lan": self.cfg["language"],
            "target_language": "",   # 上游内置流式翻译实测不产出译文，改由本项目 translate.py 直接翻已提交句子
            "translation_backend": "nllb",
            "nllb_backend": "ctranslate2",   # 用 CTranslate2 版 NLLB：快且省内存
            "pcm_input": True,               # 我们直接喂 PCM，不需要 ffmpeg 解码
            "vad": True,
            "diarization": False,
            "beams": 1,
            "log_level": "warning",
        }
        valid = {f.name for f in dataclasses.fields(WhisperLiveKitConfig)}
        return {k: v for k, v in wanted.items() if k in valid}

    # ---------- 线程入口 ----------
    def start(self) -> threading.Thread:
        th = threading.Thread(target=self._thread_main, daemon=True, name="caption-pipeline")
        th.start()
        return th

    def _thread_main(self) -> None:
        try:
            asyncio.run(self._run())
        except Exception as e:
            print(f"[错误] 管线异常退出：{type(e).__name__}: {e}", flush=True)
        finally:
            self.running = False

    async def _run(self) -> None:
        from whisperlivekit import AudioProcessor, TranscriptionEngine
        from capture import LoopbackCapture      # 同目录

        print("[1/3] 打开系统声音采集 …", flush=True)
        self._capture = LoopbackCapture(device_name=self.cfg.get("device") or None)
        print(f"      设备：{self._capture.speaker.name}", flush=True)

        kwargs = self._engine_kwargs()
        shown = kwargs.get("model_dir") or kwargs.get("model_size")
        print(f"[2/3] 加载识别模型 {shown} …", flush=True)
        if self.cfg["translate"]:
            from translate import NllbTranslator
            mt_dir = os.path.join(ROOT, "nllb-200-distilled-600M-ctranslate2")
            if not os.path.isdir(mt_dir):
                print(f"      [警告] 没找到翻译模型 {mt_dir}，先跑 下载模型.cmd；本次只出原文", flush=True)
            else:
                print("      加载翻译模型 NLLB …", flush=True)
                self.translator = NllbTranslator(
                    mt_dir, src_lang=self.cfg["language"] if self.cfg["language"] != "auto" else "en",
                    tgt_lang=self.cfg["target_language"],
                )
                print("      翻译就绪", flush=True)
        # 注意：target_language 必须交给 TranscriptionEngine（引擎级），
        # 直接塞给 AudioProcessor 会被当成"会话参数"丢弃 → 翻译不生效
        engine = TranscriptionEngine(**kwargs)
        processor = AudioProcessor(transcription_engine=engine, pcm_input=True)
        gen = await processor.create_tasks()
        consumer = asyncio.create_task(self._consume(gen))
        print("[3/3] 开始出字幕 —— 播放任意外语音视频即可\n", flush=True)

        loop = asyncio.get_running_loop()
        it = iter(self._capture.frames())
        deadline = self._t0 + self.cfg["once"] if self.cfg.get("once") else None

        while self.running:
            if deadline and time.time() > deadline:
                break
            try:
                chunk = await loop.run_in_executor(None, next, it)
            except (StopIteration, RuntimeError):
                break
            await processor.process_audio(chunk)

        self.running = False
        try:
            await processor.process_audio(None)   # 通知引擎收尾
        except Exception:
            pass
        consumer.cancel()
        print("\n已停止。", flush=True)

    async def _consume(self, gen) -> None:
        try:
            async for data in gen:
                pairs = self._extract(data)
                if not pairs or pairs == self._last_pairs:
                    continue
                self._last_pairs = pairs
                src = " ".join(p[0] for p in pairs).strip()
                dst = " ".join(p[1] for p in pairs if p[1]).strip()
                if not dst and self.translator is not None and src:
                    try:
                        dst = self.translator.translate_incremental(src)
                    except Exception as e:
                        dst = ""
                        if not self._mt_warned:
                            self._mt_warned = True
                            print(f"[警告] 翻译失败：{type(e).__name__}: {e}", flush=True)
                if self.console or not self.overlay:
                    print(f"[原文] {src}\n[中文] {dst}\n", flush=True)
                if self.overlay:
                    self.overlay.push(src, dst)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[警告] 结果流结束：{type(e).__name__}: {e}", flush=True)

    def _extract(self, data) -> list[tuple[str, str]]:
        """从 WhisperLiveKit 的输出里取出最后 N 行「原文 + 译文」。"""
        lines = getattr(data, "lines", None)
        if lines is None and isinstance(data, dict):
            lines = data.get("lines", [])
        out: list[tuple[str, str]] = []
        for ln in lines or []:
            if isinstance(ln, dict):
                text = str(ln.get("text") or "").strip()
                tr = ln.get("translation")
            else:
                text = str(getattr(ln, "text", "") or "").strip()
                tr = getattr(ln, "translation", None)
            if tr is not None and not isinstance(tr, str):
                tr = getattr(tr, "text", "") or ""
            tr = str(tr or "").strip()
            if text or tr:
                out.append((text, tr))
        n = max(1, int(self.cfg.get("max_lines", 2)))
        return out[-n:]


def main(argv=None) -> int:
    args = parse_args(argv)
    # 翻译库(nllw)把模型存在"当前目录"的相对路径下，所以固定工作目录到项目根
    sys.path.insert(0, HERE)
    try:
        os.chdir(ROOT)
    except Exception:
        pass
    _prepare_env()

    if args.list_devices:
        from capture import list_loopback_devices
        print("可采集的播放设备（把名字填进 config.json 的 device）：")
        for name in list_loopback_devices():
            print("  -", name)
        return 0

    cfg = load_config(args.config)
    for key in ("model", "language", "target_language", "device", "font_size",
                "alpha", "bottom_offset", "max_lines"):
        v = getattr(args, key, None)
        if v is not None:
            cfg[key] = v
    if args.no_translate:
        cfg["translate"] = False
    if args.no_source:
        cfg["show_source"] = False
    if args.no_click_through:
        cfg["click_through"] = False
    if args.once:
        cfg["once"] = args.once

    print("=" * 62)
    print("  实时中文字幕 LiveCaptionZH")
    print(f"  源语言 {cfg['language']} → 目标 {cfg['target_language']}  模型 {cfg['model']}"
          f"  翻译 {'开' if cfg['translate'] else '关'}")
    print("=" * 62)

    if not os.path.isfile(args.config):
        try:
            with open(args.config, "w", encoding="utf-8") as f:
                json.dump(DEFAULTS, f, ensure_ascii=False, indent=2)
            print(f"[提示] 首次运行，已生成配置文件：{args.config}")
        except Exception as e:
            print(f"[警告] 写配置文件失败：{e}")

    overlay = None
    if not args.console:
        from overlay import SubtitleOverlay
        overlay = SubtitleOverlay(
            font_size=cfg["font_size"],
            source_font_size=cfg["source_font_size"],
            width_ratio=cfg["width_ratio"],
            bottom_offset=cfg["bottom_offset"],
            alpha=cfg["alpha"],
            show_source=cfg["show_source"],
            click_through=cfg["click_through"],
            max_lines=cfg["max_lines"],
        )

    pipe = CaptionPipeline(cfg, overlay=overlay, console=args.console)
    pipe.start()

    if overlay is None:
        try:
            while pipe.running:
                time.sleep(0.3)
        except KeyboardInterrupt:
            pipe.running = False
        return 0

    try:
        overlay.run()          # 主线程跑界面
    finally:
        pipe.running = False
    return 0


if __name__ == "__main__":
    sys.exit(main())