# -*- coding: utf-8 -*-
"""系统音频采集：抓取"扬声器正在播放的声音"（Windows WASAPI 环回）。

本文件是本项目唯一的采集胶水层，真正的采集能力来自开源库 soundcard。
输出格式：16kHz / 单声道 / s16le 的 bytes —— 正好是 WhisperLiveKit 期望的输入。
"""
from __future__ import annotations

import numpy as np
import soundcard as sc

TARGET_RATE = 16000
BLOCK_SECONDS = 0.1


def list_loopback_devices() -> list[str]:
    """列出所有支持环回采集（即能抓到系统播放声）的设备名。"""
    out = []
    try:
        for mic in sc.all_microphones(include_loopback=True):
            if getattr(mic, "isloopback", False):
                out.append(mic.name)
    except Exception:
        pass
    return out


def _resample(x: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    """重采样。优先用 soxr（WhisperLiveKit 的依赖），退化时用线性插值。"""
    if src_rate == dst_rate:
        return x
    try:
        import soxr
        return soxr.resample(x, src_rate, dst_rate)
    except Exception:
        n = max(1, int(len(x) * dst_rate / src_rate))
        return np.interp(
            np.linspace(0, len(x) - 1, n), np.arange(len(x)), x
        ).astype(np.float32)


class LoopbackCapture:
    """抓系统声音。

        cap = LoopbackCapture()          # 默认用当前默认播放设备
        for chunk in cap.frames():       # bytes，16k 单声道 s16le
            ...
    """

    def __init__(self, device_name: str | None = None, samplerate: int = TARGET_RATE):
        self.speaker = self._pick_speaker(device_name)
        self.mic = sc.get_microphone(id=str(self.speaker.name), include_loopback=True)
        if self.mic is None:
            raise RuntimeError(
                f"找不到「{self.speaker.name}」的环回采集设备。"
                f"可用设备：{list_loopback_devices()}"
            )
        self.rate = samplerate

    @staticmethod
    def _pick_speaker(device_name: str | None):
        if device_name:
            needle = device_name.lower()
            for spk in sc.all_speakers():
                if needle in spk.name.lower():
                    return spk
            raise RuntimeError(
                f"找不到名称里包含「{device_name}」的播放设备。"
                f"可用设备：{[s.name for s in sc.all_speakers()]}"
            )
        return sc.default_speaker()

    def frames(self):
        """无限生成器：每次产出约 0.1 秒的 16k 单声道 s16le 字节。"""
        native = self.rate
        try:
            recorder = self.mic.recorder(
                samplerate=self.rate, channels=1, blocksize=int(self.rate * BLOCK_SECONDS)
            )
        except Exception:
            # 部分声卡共享模式只接受 48k：按原生采样率录，再重采样到 16k
            native = 48000
            recorder = self.mic.recorder(
                samplerate=native, channels=1, blocksize=int(native * BLOCK_SECONDS)
            )
        per_block = int(native * BLOCK_SECONDS)
        with recorder as rec:
            while True:
                data = rec.record(numframes=per_block)
                mono = np.asarray(data, dtype=np.float32).reshape(-1)
                if native != self.rate:
                    mono = _resample(mono, native, self.rate)
                pcm = np.clip(mono * 32767.0, -32768, 32767).astype(np.int16)
                yield pcm.tobytes()