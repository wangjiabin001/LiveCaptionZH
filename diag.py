import os, sys, time, logging
os.environ["HF_HUB_OFFLINE"] = "1"
logging.basicConfig(level=logging.INFO, format="%(message)s")
nv = os.path.join(sys.prefix, "Lib", "site-packages", "nvidia")
if os.path.isdir(nv):
    for sub in os.listdir(nv):
        d = os.path.join(nv, sub, "bin")
        if os.path.isdir(d):
            try: os.add_dll_directory(d)
            except Exception: pass
            os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]
from whisperlivekit import TranscriptionEngine
t0 = time.time()
e = TranscriptionEngine(model_dir=r"D:\LiveCaptionZH\models\faster-whisper-large-v3",
                        backend="faster-whisper", backend_policy="localagreement",
                        lan="en", target_language="zh",
                        translation_backend="nllb", nllb_backend="ctranslate2")
print("加载耗时 %.1fs" % (time.time() - t0))
print("engine.args.model_dir =", getattr(e.args, "model_dir", None))
asr = e.asr
print("asr 类型 =", type(asr).__name__)
inner = getattr(asr, "model", None)
for attr in ("model_path", "model_size", "path"):
    if hasattr(inner, attr):
        print(f"  asr.model.{attr} =", getattr(inner, attr))
