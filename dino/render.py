"""Render 'Kapa and the dinosaurs' cartoon: composites the Kapa cutout over
scene backgrounds with simple character animation, captions and voiceover."""
import math, subprocess, wave, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1920, 1080, 30
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
SUB_FONT = ImageFont.truetype(FONT, 58)
TITLE_FONT = ImageFont.truetype(FONT, 110)
LEAD, TAIL = 0.6, 0.9  # silence before/after each line

kapa = Image.open("kapa.png").convert("RGBA")
KH = 560
kapa = kapa.resize((int(kapa.width * KH / kapa.height), KH), Image.LANCZOS)
kapa_flip = kapa.transpose(Image.FLIP_LEFT_RIGHT)

def load_bg(path, crop_logo=True):
    im = Image.open(path).convert("RGB")
    if crop_logo:  # trim the generator watermark in the bottom-right corner
        w, h = im.size
        im = im.crop((0, 0, w, int(h * 0.93)))
    # cover-fit to 16:9 at 2x so we can pan/zoom
    w, h = im.size
    s = max(W * 1.25 / w, H * 1.25 / h)
    return im.resize((int(w * s), int(h * s)), Image.LANCZOS)

def wav_env(path):
    w = wave.open(path)
    sr = w.getframerate(); ch = w.getnchannels()
    a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32)
    if ch > 1: a = a.reshape(-1, ch).mean(1)
    hop = sr // FPS
    env = np.array([np.sqrt(np.mean(a[i:i + hop] ** 2)) for i in range(0, len(a), hop)])
    return env / (env.max() + 1e-6)

def ease(t): return t * t * (3 - 2 * t)

SCENES = [
    # key, bg, title, subtitle chunks, kapa mode, camera
    ("s1", "b1.jpg", None, "Привет! Это снова я, Капа!|Знаете, что я люблю больше всего?|Динозавров!|А что если... я отправлюсь прямо к ним?", "talk", "zoomin"),
    ("s2", "b2.jpg", "МАШИНА ВРЕМЕНИ", "Включаю машину времени!|Три... два... один... Поехали!", "portal", "spin"),
    ("s3", "b3.jpg", "100 МЛН ЛЕТ НАЗАД", "Ого! Я в прошлом!|Сто миллионов лет назад!|Тут жарко, и пахнет вулканом.", "popin", "panright"),
    ("s4", "b4.jpg", "БРАХИОЗАВР", "Смотрите! Какие длинные шеи!|Высотой с пятиэтажный дом|и едят только листья.|Привет, великаны!", "talk", "zoomin"),
    ("s5", "b5.jpg", "ТРИЦЕРАТОПС", "А это трицератопс!|У него три рога и огромный воротник.|Выглядит грозно,|но ест только траву.", "talk", "panleft"),
    ("s6", "b6.jpg", "ПТЕРОЗАВР", "А над головой летают птерозавры.|Кстати, это не динозавры,|а летающие ящеры!", "lookup", "panup"),
    ("s7", "trex.png", "ТИРАННОЗАВР!", "Ой... кажется, кто-то проголодался...|Это Ти-Рекс! Бежим!", "flee", "shake"),
    ("s8", "b8.jpg", "АСТЕРОИД", "Фух, оторвался!|Но смотрите! В небе огромный астероид!|66 миллионов лет назад|именно он погубил динозавров.|Пора домой!", "runin", "zoomin"),
    ("s9", "b1.jpg", None, "Я дома! Вот это приключение!|Хотите ещё? Ставьте лайк|и подписывайтесь! Пока!", "jump", "zoomout"),
]

def camera(bg, mode, p, f):
    bw, bh = bg.size
    z = 1.0; cx, cy = 0.5, 0.5; ang = 0
    if mode == "zoomin": z = 1.0 + 0.18 * p
    elif mode == "zoomout": z = 1.18 - 0.18 * p
    elif mode == "panright": cx = 0.4 + 0.2 * p; z = 1.05
    elif mode == "panleft": cx = 0.6 - 0.2 * p; z = 1.05
    elif mode == "panup": cy = 0.6 - 0.2 * p; z = 1.05
    elif mode == "spin": z = 1.0 + 0.35 * p; ang = 25 * p
    elif mode == "shake": z = 1.0 + 0.35 * ease(p); cx = 0.66; cy = 0.45
    vw, vh = bw / 1.25 / z, bh / 1.25 / z
    x0 = cx * bw - vw / 2; y0 = cy * bh - vh / 2
    if mode == "shake" and p > 0.45:
        x0 += 14 * math.sin(f * 2.3); y0 += 10 * math.cos(f * 1.9)
    x0 = max(0, min(bw - vw, x0)); y0 = max(0, min(bh - vh, y0))
    frame = bg.crop((int(x0), int(y0), int(x0 + vw), int(y0 + vh))).resize((W, H), Image.BILINEAR)
    if ang:
        frame = frame.rotate(ang, resample=Image.BILINEAR).crop((0, 0, W, H))
        frame = frame.resize((W, H))
    return frame

def place_kapa(frame, mode, p, t, dur, amp, f):
    img = kapa; scale = 1.0; x = 120; y = H - KH + 40; rot = 0; alpha = 1.0
    talk = 1.0 + 0.06 * amp           # squash/stretch with voice loudness
    sway = 4 * math.sin(f / 7)
    if mode == "talk":
        rot = sway
    elif mode == "portal":
        if p > 0.55:
            q = ease((p - 0.55) / 0.45)
            scale = 1 - 0.95 * q; rot = 720 * q
            x = int(120 + (W / 2 - 120 - kapa.width / 2) * q); y = int(y - (H / 2 - KH / 2 - 40) * q * 0.4 - 200 * q)
            alpha = 1 - q * 0.5
    elif mode == "popin":
        q = min(1, t / 0.6); y = int(H - (H - y) * (1 - (1 - q) ** 3) - 30 * math.sin(q * math.pi)) if q < 1 else y
        rot = sway
    elif mode == "lookup":
        rot = -6 + sway
    elif mode == "flee":
        if t < dur * 0.55:
            x += int(8 * math.sin(f * 2.7))  # trembling
        else:
            img = kapa_flip
            q = ease((t - dur * 0.55) / (dur * 0.45))
            x = int(120 - (kapa.width + 160) * q * 1.6) if False else int(120 + (W + 200) * q)
            y += int(-25 * abs(math.sin(f / 2)))
    elif mode == "runin":
        q = min(1, t / 0.9); x = int(-kapa.width + (120 + kapa.width) * ease(q))
        if q < 1: y += int(-25 * abs(math.sin(f / 2)))
        rot = sway
    elif mode == "jump":
        y -= int(70 * abs(math.sin(t * 3.2))) if t < dur * 0.45 else 0
        rot = sway
    sx = int(img.width * scale * (2 - talk) ** 0.5); sy = int(img.height * scale * talk)
    if sx < 4 or sy < 4: return
    k = img.resize((sx, sy), Image.BILINEAR)
    if rot: k = k.rotate(rot, resample=Image.BILINEAR, expand=True)
    if alpha < 1:
        a = k.getchannel("A").point(lambda v: int(v * alpha)); k.putalpha(a)
    frame.paste(k, (x - (k.width - sx) // 2, y + (img.height - sy) - (k.height - sy) // 2), k)

def text_box(draw, txt, font, cx, cy, fill, stroke, sw):
    bb = draw.textbbox((0, 0), txt, font=font, stroke_width=sw)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    draw.text((cx - tw / 2, cy - th / 2), txt, font=font, fill=fill, stroke_width=sw, stroke_fill=stroke)

def main():
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "19",
                           "-preset", "medium", "-pix_fmt", "yuv420p", "video_only.mp4"], stdin=subprocess.PIPE)
    audio_parts = []; gf = 0
    for key, bgp, title, subs, kmode, cam in SCENES:
        voice = f"vo/{key}.wav"
        env = wav_env(voice)
        vdur = len(env) / FPS
        dur = LEAD + vdur + TAIL
        n = int(round(dur * FPS))
        bg = load_bg(bgp, crop_logo=bgp.endswith(".jpg"))
        chunks = subs.split("|")
        weights = np.array([len(c) for c in chunks], float); bounds = np.cumsum(weights) / weights.sum()
        audio_parts.append((voice, dur))
        for i in range(n):
            t = i / FPS; p = i / max(1, n - 1)
            frame = camera(bg, cam, p, gf)
            vi = int((t - LEAD) * FPS)
            amp = float(env[vi]) if 0 <= vi < len(env) else 0.0
            place_kapa(frame, kmode, p, t, dur, amp, gf)
            d = ImageDraw.Draw(frame)
            if title and t > 0.15:
                q = min(1, (t - 0.15) / 0.3)
                f2 = ImageFont.truetype(FONT, int(110 * (0.6 + 0.4 * q)))
                text_box(d, title, f2, W / 2 + 160, 120, (255, 214, 0), (0, 0, 0), 9)
            ts = (t - LEAD) / vdur
            if 0 <= ts <= 1.0:
                ci = int(np.searchsorted(bounds, ts))
                text_box(d, chunks[min(ci, len(chunks) - 1)], SUB_FONT, W / 2 + 200, H - 110, (255, 255, 255), (0, 0, 0), 7)
            # quick fade between scenes
            fa = min(1, t / 0.25, (dur - t) / 0.25)
            if fa < 1:
                frame = Image.blend(Image.new("RGB", (W, H)), frame, max(0, fa))
            ff.stdin.write(frame.tobytes()); gf += 1
        print(key, round(dur, 2), flush=True)
    ff.stdin.close(); ff.wait()
    # audio: each line delayed by LEAD and padded to its scene length
    inputs = []; filt = []
    for i, (v, dur) in enumerate(audio_parts):
        inputs += ["-i", v]
        filt.append(f"[{i}:a]aresample=44100,adelay={int(LEAD*1000)}|{int(LEAD*1000)},apad,atrim=0:{dur:.3f}[a{i}]")
    filt.append("".join(f"[a{i}]" for i in range(len(audio_parts))) + f"concat=n={len(audio_parts)}:v=0:a=1[voice]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filt),
                    "-map", "[voice]", "-ac", "2", "voice_full.wav"], check=True)

if __name__ == "__main__":
    main()
