# -*- coding: utf-8 -*-
"""翻译层：NLLB-200（CTranslate2 版）外语 → 中文。

只用现成组件，本文件只是把它们串起来：
    Meta NLLB-200-distilled-600M 模型
    CTranslate2                 推理引擎
    transformers NllbTokenizer  分词

为什么不用 WhisperLiveKit 内置的实时翻译：它的"流式翻译"通路依赖一串
token 对齐状态机，实测在 LocalAgreement 策略下不产出译文。改成对
「已提交的句子」直接翻译，简单、稳定、可缓存，效果一样好。
"""
from __future__ import annotations

import re
import threading

# 常用语言 → NLLB 语言码（NLLB 用自己的 BCP-47 风格代码）
NLLB_CODE = {
    "en": "eng_Latn", "zh": "zho_Hans", "ja": "jpn_Jpan", "ko": "kor_Hang",
    "fr": "fra_Latn", "de": "deu_Latn", "es": "spa_Latn", "ru": "rus_Cyrl",
    "it": "ita_Latn", "pt": "por_Latn", "ar": "arb_Arab", "th": "tha_Thai",
    "vi": "vie_Latn", "id": "ind_Latn", "hi": "hin_Deva", "tr": "tur_Latn",
}
SENT_SPLIT = re.compile(r"(?<=[.!?。！？])\s+|\n+")


class NllbTranslator:
    """线程安全的 NLLB 翻译器，带整句缓存（同一句只翻一次）。"""

    def __init__(self, model_dir: str, src_lang: str = "en", tgt_lang: str = "zh",
                 device: str = "cpu", compute_type: str = "int8"):
        import ctranslate2
        from transformers import AutoTokenizer

        self.src_code = NLLB_CODE.get(src_lang, "eng_Latn")
        self.tgt_code = NLLB_CODE.get(tgt_lang, "zho_Hans")
        # tokenizer 文件就在 ct2 模型目录里，本地加载，不联网
        self.tok = AutoTokenizer.from_pretrained(model_dir, src_lang=self.src_code)
        self.engine = ctranslate2.Translator(model_dir, device=device, compute_type=compute_type)
        self._cache: dict[str, str] = {}
        self._lock = threading.Lock()

    def translate(self, text: str) -> str:
        text = (text or "").strip()
        if not text:
            return ""
        with self._lock:
            hit = self._cache.get(text)
        if hit is not None:
            return hit
        tokens = self.tok.convert_ids_to_tokens(self.tok.encode(text))
        res = self.engine.translate_batch(
            [tokens], target_prefix=[[self.tgt_code]], beam_size=1,
            max_batch_size=1, max_decoding_length=256,
        )
        ids = self.tok.convert_tokens_to_ids(res[0].hypotheses[0][1:])
        out = self.tok.decode(ids, skip_special_tokens=True).strip()
        with self._lock:
            self._cache[text] = out
            if len(self._cache) > 4000:
                self._cache.clear()
        return out

    def translate_incremental(self, full_text: str, keep: int = 2) -> str:
        """把一段（会不断变长的）识别文本翻译成中文，只翻新出现的句子。"""
        parts = [p.strip() for p in SENT_SPLIT.split(full_text.strip()) if p.strip()]
        if not parts:
            return ""
        parts = parts[-keep:]
        return " ".join(self.translate(p) for p in parts)