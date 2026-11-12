"""Synthesize narration per segment with Kokoro (ONNX), align words with Whisper,
write voice.wav + timings.json.  usage: python tts.py <model_dir> [voice]"""
import json, sys
import numpy as np, soundfile as sf
from kokoro_onnx import Kokoro
from faster_whisper import WhisperModel

MD = sys.argv[1]; VOICE = sys.argv[2] if len(sys.argv) > 2 else "am_michael"
SR = 24000; GAP = 0.55

d = json.load(open("script.json"))
segs = [("intro", d["intro"])] + [(f"fact{i+1}", f"Number {i+1}. {f['say']}") for i, f in enumerate(d["facts"])] + [("outro", d["outro"])]

k = Kokoro(f"{MD}/model.onnx", f"{MD}/voices-v1.0.bin")
wm = WhisperModel("base.en", device="cpu", compute_type="int8")

audio = [np.zeros(int(SR * 0.6), np.float32)]; t = 0.6; out = []
for key, text in segs:
    a, sr = k.create(text, voice=VOICE, speed=1.08, lang="en-us")
    a = a.astype(np.float32)
    # trim leading/trailing silence
    nz = np.where(np.abs(a) > 0.01)[0]
    if len(nz): a = a[max(0, nz[0] - 600): nz[-1] + 1800]
    a16 = np.interp(np.arange(0, len(a), SR / 16000), np.arange(len(a)), a).astype(np.float32)
    words = []
    res, _ = wm.transcribe(a16, word_timestamps=True, language="en", initial_prompt=text)
    for s in res:
        for w in s.words or []:
            words.append({"w": w.word.strip(), "s": t + w.start, "e": t + w.end})
    out.append({"key": key, "text": text, "start": t, "end": t + len(a) / SR, "words": words})
    audio.append(a); t += len(a) / SR
    g = 0.8 if key == "intro" else GAP
    audio.append(np.zeros(int(SR * g), np.float32)); t += g
    print(key, round(t, 2), len(words), "/", len(text.split()), flush=True)
audio.append(np.zeros(int(SR * 2.0), np.float32)); t += 2.0
sf.write("voice.wav", np.concatenate(audio), SR)
json.dump({"duration": t, "segments": out}, open("timings.json", "w"), indent=1)
print("total", round(t, 1))
