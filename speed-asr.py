import os, sys, time
nv = os.path.join(sys.prefix, "Lib", "site-packages", "nvidia")
if os.path.isdir(nv):
    for sub in os.listdir(nv):
        d = os.path.join(nv, sub, "bin")
        if os.path.isdir(d):
            try: os.add_dll_directory(d)
            except Exception: pass
            os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]
from faster_whisper import WhisperModel
import soundfile as sf, soxr, numpy as np
a, sr = sf.read("test-en.wav", dtype="float32")
if sr != 16000: a = soxr.resample(a, sr, 16000)
a = a.astype(np.float32)
print("音频时长 %.1f 秒" % (len(a)/16000))
for ct in ("auto", "int8_float16", "float16"):
    try:
        t0 = time.time(); m = WhisperModel(r"D:\LiveCaptionZH\models\faster-whisper-large-v3", device="cuda", compute_type=ct); tl = time.time()-t0
        t0 = time.time(); segs, info = m.transcribe(a, language="en", beam_size=1); txt = " ".join(s.text for s in segs).strip(); tt = time.time()-t0
        print(f"  {ct:14s} 加载 {tl:5.1f}s  识别 {tt:5.1f}s  ({len(a)/16000/tt:.1f}x 实时)")
        if ct == "auto": print("     转写:", txt[:90])
        del m
    except Exception as e:
        print(f"  {ct}: 失败 {type(e).__name__} {str(e)[:80]}")
