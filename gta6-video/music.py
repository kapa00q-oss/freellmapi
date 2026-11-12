"""Procedural synthwave backing track + whoosh SFX at each fact cut -> music.wav"""
import json
import numpy as np, soundfile as sf

SR = 44100
tim = json.load(open("timings.json"))
DUR = tim["duration"] + 0.5
N = int(DUR * SR)
BPM = 100; beat = 60 / BPM; bar = beat * 4
rng = np.random.default_rng(7)

def midi(m): return 440 * 2 ** ((m - 69) / 12)

def saw(f, t): return 2 * ((t * f) % 1) - 1

def env(n, a=0.01, r=0.2):
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / r)
    return e

out = np.zeros(N, np.float64)
prog = [(57, [57, 60, 64]), (53, [53, 57, 60]), (48, [55, 60, 64]), (55, [55, 59, 62])]   # Am F C G

# pads: one chord per bar, detuned saws, soft attack
bar_n = int(bar * SR)
t_bar = np.arange(bar_n) / SR
pad_env = np.minimum(1, t_bar / 0.4) * np.minimum(1, (bar - t_bar) / 0.3)
pads = {}
for root, notes in prog:
    s = sum(saw(midi(n + 12) * d, t_bar) for n in notes for d in (0.997, 1.003))
    pads[root] = s * pad_env / 6
# smooth pads with simple moving average (cheap lowpass)
k = np.ones(24) / 24
for r in pads: pads[r] = np.convolve(pads[r], k, mode="same")

kick_n = int(0.35 * SR); tk = np.arange(kick_n) / SR
kick = np.sin(2 * np.pi * (45 * tk + 90 * (1 - np.exp(-tk * 30)) / 30)) * np.exp(-tk * 9)
snare_n = int(0.25 * SR)
snare = (rng.standard_normal(snare_n) * 0.6 + np.sin(2 * np.pi * 190 * np.arange(snare_n) / SR) * 0.4) * env(snare_n, 0.001, 0.07)
hat_n = int(0.05 * SR)
hat = np.diff(rng.standard_normal(hat_n + 1)) * env(hat_n, 0.0005, 0.012) * 0.5

def add(sig, start, gain):
    i = int(start * SR)
    if i >= N: return
    j = min(N, i + len(sig)); out[i:j] += sig[: j - i] * gain

t0 = 0.0; bi = 0
while t0 < DUR:
    root, notes = prog[bi % 4]
    add(pads[root], t0, 0.55)
    for b in range(4):
        tb = t0 + b * beat
        add(kick, tb, 0.9)
        if b in (1, 3): add(snare, tb, 0.35)
        for h in range(2): add(hat, tb + h * beat / 2, 0.25)
        for e8 in range(2):                                   # 8th-note bass
            nn = int(beat / 2 * SR); tt = np.arange(nn) / SR
            f = midi(root - 12 + (12 if e8 else 0))
            bs = (saw(f, tt) * 0.6 + np.sin(2 * np.pi * f * tt) * 0.6) * env(nn, 0.005, 0.18)
            add(np.convolve(bs, np.ones(10) / 10, mode="same"), tb + e8 * beat / 2, 0.45)
    # arpeggio 16ths
    arp = notes + [notes[0] + 12]
    for s16 in range(16):
        nn = int(beat / 4 * SR); tt = np.arange(nn) / SR
        f = midi(arp[s16 % 4] + 24)
        sq = np.sign(np.sin(2 * np.pi * f * tt)) * env(nn, 0.002, 0.06)
        add(np.convolve(sq, np.ones(6) / 6, mode="same"), t0 + s16 * beat / 4, 0.07)
    t0 += bar; bi += 1

# whoosh at each segment start (facts + outro)
wn = int(0.5 * SR); tw = np.arange(wn) / SR
noise = rng.standard_normal(wn)
sweep = np.convolve(noise, np.ones(14) / 14, mode="same") * np.sin(np.pi * tw / 0.5) ** 2
for seg in tim["segments"][1:]:
    add(sweep, seg["start"] - 0.45, 0.35)

# fades & normalize
fade = int(2.5 * SR)
out[:int(1.0 * SR)] *= np.linspace(0, 1, int(1.0 * SR))
out[-fade:] *= np.linspace(1, 0, fade)
out = np.tanh(out * 0.9)
out /= np.max(np.abs(out)) + 1e-9
st = np.stack([out * 0.95, np.roll(out, 220) * 0.95], 1)    # tiny stereo width
sf.write("music.wav", st.astype(np.float32), SR)
print("music", round(DUR, 1), "s")
