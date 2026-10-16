# -*- coding: utf-8 -*-
"""下载本项目需要的两个模型（带断点续传与卡死重连）。

  识别模型 faster-whisper-large-v3  -> ModelScope（国内快）
  翻译模型 NLLB-200-distilled-600M  -> hf-mirror（HuggingFace 国内镜像）

用法：
    python tools/fetch_models.py              # 全下
    python tools/fetch_models.py --asr small  # 只下小号识别模型
    python tools/fetch_models.py --no-mt      # 只下识别模型
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = os.path.join(ROOT, "models")
MT_DIR = os.path.join(ROOT, "nllb-200-distilled-600M-ctranslate2")

# ModelScope 上的 faster-whisper 镜像仓库
MS_REPO = {
    "large-v3": "pengzhendong/faster-whisper-large-v3",
    "medium": "pengzhendong/faster-whisper-medium",
    "small": "pengzhendong/faster-whisper-small",
}
ASR_FILES = ["config.json", "tokenizer.json", "vocabulary.json", "preprocessor_config.json", "model.bin"]

MT_REPO = "entai2965/nllb-200-distilled-600M-ctranslate2"
MT_FILES = [
    "config.json", "model.bin", "sentencepiece.bpe.model", "shared_vocabulary.json",
    "special_tokens_map.json", "tokenizer.json", "tokenizer_config.json",
]


def size_of(path: str) -> int:
    return os.path.getsize(path) if os.path.isfile(path) else 0


def remote_size(url: str) -> int:
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return int(r.headers.get("Content-Length") or 0)
    except Exception:
        return 0


def download(url: str, dest: str, rounds: int = 80) -> bool:
    """断点续传下载；传输卡住(20 秒无数据)就断开重连。"""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    expected = remote_size(url)
    for i in range(1, rounds + 1):
        have = size_of(dest)
        if expected and have >= expected:
            print(f"    ✓ {os.path.basename(dest)}  {have/1048576:.0f} MB")
            return True
        if i > 1:
            print(f"    续传第 {i} 轮 … 已有 {have/1048576:.0f} MB")
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0",
                "Range": f"bytes={have}-" if have else "bytes=0-",
            })
            with urllib.request.urlopen(req, timeout=30) as r, open(dest, "ab") as f:
                if have and r.status == 200:      # 服务端不支持续传 → 重头来
                    f.close()
                    open(dest, "wb").close()
                    f = open(dest, "ab")
                last = time.time()
                while True:
                    chunk = r.read(1 << 16)
                    if not chunk:
                        break
                    f.write(chunk)
                    last = time.time()
                    if time.time() - last > 20:   # 卡死保护
                        break
        except Exception as e:
            print(f"    连接中断（{type(e).__name__}），20 秒后重试 …")
            time.sleep(20)
    ok = size_of(dest) >= expected > 0
    print(("    ✓ " if ok else "    ✗ 未完成 ") + os.path.basename(dest))
    return ok


def fetch_asr(name: str) -> bool:
    repo = MS_REPO.get(name)
    if not repo:
        print(f"[识别模型] 不支持的型号 {name}，可用：{', '.join(MS_REPO)}")
        return False
    dst = os.path.join(MODELS, f"faster-whisper-{name}")
    print(f"[1/2] 识别模型 faster-whisper-{name}（ModelScope）→ {dst}")
    base = f"https://www.modelscope.cn/api/v1/models/{repo}/repo?Revision=master&FilePath="
    ok = True
    for f in ASR_FILES:
        if size_of(os.path.join(dst, f)) > 0 and f != "model.bin":
            continue
        ok &= download(base + f, os.path.join(dst, f))
    return ok


def fetch_mt() -> bool:
    print(f"[2/2] 翻译模型 NLLB → {MT_DIR}")
    base = f"https://hf-mirror.com/{MT_REPO}/resolve/main/"
    os.makedirs(MT_DIR, exist_ok=True)
    ok = True
    for f in MT_FILES:
        if f != "model.bin" and size_of(os.path.join(MT_DIR, f)) > 0:
            continue
        ok &= download(base + f, os.path.join(MT_DIR, f))
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description="下载 LiveCaptionZH 需要的模型")
    ap.add_argument("--asr", default="large-v3", help="识别模型：large-v3 / medium / small")
    ap.add_argument("--no-mt", action="store_true", help="跳过翻译模型")
    args = ap.parse_args()

    ok = fetch_asr(args.asr)
    if not args.no_mt:
        ok &= fetch_mt()
    print("\n完成。" if ok else "\n有文件没下完，重新运行本脚本会自动续传。")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())