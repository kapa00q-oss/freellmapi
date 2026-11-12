"""Render the 1920x1080 '35 Quick Facts About GTA 6' video frames -> mp4 (no audio).
usage: python render.py [preview_seconds]"""
import json, math, os, subprocess, sys
from functools import lru_cache
from multiprocessing import Pool
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1920, 1080, 30
HZ = 640                     # horizon y
SUN_C, SUN_R = (1380, HZ - 10), 250
F = "/usr/share/fonts/opentype/inter/"
def font(name, size): return ImageFont.truetype(F + name, size)
BLACK_I = "InterDisplay-BlackItalic.otf" if os.path.exists(F + "InterDisplay-BlackItalic.otf") else "Inter-BoldItalic.otf"
BOLD = "Inter-Bold.otf"; SEMI = "Inter-SemiBold.otf" if os.path.exists(F + "Inter-SemiBold.otf") else BOLD
PINK, CYAN, YELLOW, WHITE = (255, 60, 172), (60, 230, 255), (255, 214, 64), (255, 255, 255)

script = json.load(open("script.json"))
tim = json.load(open("timings.json"))
SEGS = tim["segments"]; DUR = tim["duration"]

# ---------------------------------------------------------------- background
def lerp(a, b, t): return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

def sky():
    stops = [(0, (14, 2, 40)), (0.35, (58, 12, 92)), (0.7, (190, 40, 120)), (0.92, (255, 110, 90)), (1.0, (255, 170, 90))]
    arr = np.zeros((HZ, W, 3), np.uint8)
    for y in range(HZ):
        t = y / (HZ - 1)
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                arr[y, :] = lerp(c0, c1, (t - t0) / (t1 - t0)); break
    img = Image.new("RGBA", (W, H), (16, 0, 34, 255)); img.paste(Image.fromarray(arr), (0, 0))
    rng = np.random.default_rng(3)                       # stars
    d = ImageDraw.Draw(img)
    for _ in range(140):
        x, y = rng.integers(0, W), rng.integers(0, int(HZ * 0.55))
        b = int(rng.integers(120, 255)); r = rng.choice([1, 1, 1, 2])
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, b))
    return img

def sun_layer(phase):
    cx, cy = SUN_C; r = SUN_R
    size = r * 2 + 1
    yy, xx = np.mgrid[0:size, 0:size]
    dist = np.hypot(xx - r, yy - r)
    t = (yy / size)[..., None]
    col = (np.array([255, 236, 120]) * (1 - t) + np.array([255, 40, 150]) * t).astype(np.uint8)
    alpha = (dist <= r).astype(np.uint8) * 255
    # retro cut stripes on lower half, drifting downward
    rel = yy - r * 0.15
    period = 34
    stripe_h = np.clip((rel / r) * 16, 0, 16)
    m = ((rel + phase * period) % period) < stripe_h
    alpha[(rel > 0) & m] = 0
    rgba = np.dstack([col, alpha]).astype(np.uint8)
    sun = Image.fromarray(rgba, "RGBA")
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([cx - r - 60, cy - r - 60, cx + r + 60, cy + r + 60], fill=(255, 80, 160, 110))
    layer = Image.alpha_composite(layer, glow.filter(ImageFilter.GaussianBlur(70)))
    layer.alpha_composite(sun, (cx - r, cy - r))
    return layer

def ground_layer(phase):
    g = Image.new("RGBA", (W, H - HZ), (16, 0, 34, 255))
    arr = np.array(g)
    for y in range(H - HZ):                            # haze near horizon
        k = max(0, 1 - y / 160)
        arr[y, :, :3] = np.clip(arr[y, :, :3] + np.array([120, 20, 90]) * k, 0, 255)
    g = Image.fromarray(arr)
    lines = Image.new("RGBA", g.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lines)
    vx = W // 2
    for i in range(-30, 31):                           # converging verticals
        x_bottom = vx + i * 150
        d.line([(vx + i * 6, 0), (x_bottom, H - HZ)], fill=(255, 60, 200, 200), width=2)
    for k in range(18):                                # moving horizontals (perspective)
        z = (k + phase) / 18
        y = (H - HZ) * (z ** 2.4)
        d.line([(0, y), (W, y)], fill=(255, 60, 200, int(80 + 175 * z)), width=2 if z < .5 else 3)
    glow = lines.filter(ImageFilter.GaussianBlur(4))
    g = Image.alpha_composite(g, glow); g = Image.alpha_composite(g, lines)
    full = Image.new("RGBA", (W, H), (0, 0, 0, 0)); full.paste(g, (0, HZ))
    return full

def palm(x0, base_y, height, lean, scale=1.0, flip=False):
    """Procedural palm silhouette."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
    col = (10, 0, 22, 255)
    pts = []
    n = 24
    for i in range(n + 1):
        t = i / n
        x = x0 + lean * (t ** 1.6); y = base_y - height * t
        pts.append((x, y))
    for i in range(n):
        w = (26 - 14 * i / n) * scale
        (xa, ya), (xb, yb) = pts[i], pts[i + 1]
        d.polygon([(xa - w / 2, ya), (xa + w / 2, ya), (xb + w / 2 - 1, yb), (xb - w / 2 + 1, yb)], fill=col)
    tx, ty = pts[-1]
    for ang, ln, droop in [(-170, 260, 90), (-140, 240, 120), (-100, 160, 60), (-60, 200, 110), (-20, 270, 120),
                           (10, 230, 140), (160, 200, 150), (200, 190, 160), (-200, 230, 160)]:
        a = math.radians(ang); L = ln * scale
        leaf = []
        for i in range(13):
            t = i / 12
            x = tx + math.cos(a) * L * t
            y = ty + math.sin(a) * L * t + droop * scale * t * t
            leaf.append((x, y))
        top = [(x, y - 14 * scale * math.sin(math.pi * (i / 12))) for i, (x, y) in enumerate(leaf)]
        bot = [(x, y + 6 * scale * math.sin(math.pi * (i / 12))) for i, (x, y) in enumerate(leaf)]
        d.polygon(top + bot[::-1], fill=col)
    d.ellipse([tx - 18 * scale, ty - 12 * scale, tx + 18 * scale, ty + 18 * scale], fill=col)
    return layer

ART = Image.open("art.jpg").convert("RGB")
PX, PY, PW, PH = 1330, 40, 500, 1000          # right-side art panel

def build_bg_loop(n=1):
    big = ART.resize((W, int(ART.height * W / ART.width)), Image.LANCZOS).filter(ImageFilter.GaussianBlur(28))
    arr = np.asarray(big).astype(np.float32) * 0.55
    arr[..., 0] *= 1.08; arr[..., 2] *= 1.12                      # purple-ish grade
    big = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    shade = np.zeros((H, W, 4), np.uint8)
    xs = np.linspace(1, 0, W)
    shade[..., 3] = (np.clip(xs * 1.3 - 0.1, 0, 1) * 150).astype(np.uint8)[None, :]
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle([PX - 6, PY - 6, PX + PW + 6, PY + PH + 6], radius=34, fill=PINK + (230,))
    glow = glow.filter(ImageFilter.GaussianBlur(26))
    return {"big": big, "shade": Image.fromarray(shade, "RGBA"), "glow": glow}

PANEL_MASK = Image.new("L", (PW, PH), 0)
ImageDraw.Draw(PANEL_MASK).rounded_rectangle([0, 0, PW - 1, PH - 1], radius=28, fill=255)

def base_frame(t, seg_since):
    big = BG["big"]
    span = big.height - H
    y = int(span * (0.5 + 0.5 * math.sin(t / DUR * 2 * math.pi - math.pi / 2)))   # slow pan down and back
    frame = big.crop((0, y, W, y + H)).convert("RGBA")
    frame.alpha_composite(BG["shade"]); frame.alpha_composite(BG["glow"])
    z = 1.0 + 0.07 * min(1.0, seg_since / 8.0)                                  # Ken Burns per segment
    cw, ch = ART.width / z, ART.height / z
    cx, cy = ART.width / 2, ART.height * 0.52
    crop = ART.crop((int(cx - cw / 2), int(cy - ch / 2), int(cx + cw / 2), int(cy + ch / 2)))
    crop = crop.resize((PW, PH), Image.BILINEAR)
    frame.paste(crop, (PX, PY), PANEL_MASK)
    ImageDraw.Draw(frame).rounded_rectangle([PX, PY, PX + PW - 1, PY + PH - 1], radius=28, outline=PINK, width=4)
    return frame

# ---------------------------------------------------------------- text helpers
def glow_text(size, draw_fn, glow_col, radius=14, strength=2):
    layer = Image.new("RGBA", size, (0, 0, 0, 0)); draw_fn(ImageDraw.Draw(layer), None)
    g = Image.new("RGBA", size, (0, 0, 0, 0)); draw_fn(ImageDraw.Draw(g), glow_col)
    g = g.filter(ImageFilter.GaussianBlur(radius))
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    for _ in range(strength): out = Image.alpha_composite(out, g)
    return Image.alpha_composite(out, layer)

def wrap(text, fnt, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if fnt.getlength(t) <= maxw or not cur: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

@lru_cache(maxsize=8)
def fact_card(n):
    f = script["facts"][n - 1]
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # number
    fn_num = font(BLACK_I, 230); fn_small = font(BOLD, 34); fn_tag = font(BOLD, 30)
    num = f"#{n}"
    def dn(d, gc):
        d.text((110, 70), num, font=fn_num, fill=gc or WHITE, stroke_width=0)
    layer = Image.alpha_composite(layer, glow_text((W, H), dn, PINK + (255,), 22, 3))
    nw = fn_num.getlength(num)
    d = ImageDraw.Draw(layer)
    d.text((130 + nw, 230), "/ 35", font=fn_small, fill=(255, 255, 255, 170))
    # tag chip
    tag = f["tag"]; tw = fn_tag.getlength(tag)
    d.rounded_rectangle([118, 345, 118 + tw + 44, 397], radius=26, outline=CYAN, width=3, fill=(10, 30, 50, 150))
    d.text((140, 351), tag, font=fn_tag, fill=CYAN)
    # headline
    size = 120
    while True:
        fh = font(BLACK_I, size); lines = wrap(f["head"].upper(), fh, 1120)
        if len(lines) <= 2 or size <= 80: break
        size -= 8
    y = 425
    def dh(dd, gc):
        yy = y
        for ln in lines:
            dd.text((112, yy), ln, font=fh, fill=gc or WHITE); yy += int(size * 1.08)
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(shadow)
    yy = y
    for ln in lines:
        sd.text((112 + 7, yy + 7), ln, font=fh, fill=PINK); yy += int(size * 1.08)
    layer = Image.alpha_composite(layer, shadow)
    layer = Image.alpha_composite(layer, glow_text((W, H), dh, (255, 120, 220, 200), 18, 1))
    return layer

@lru_cache(maxsize=4)
def title_card(kind):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if kind == "intro":
        rows = [("35 QUICK FACTS", font(BLACK_I, 170), WHITE, PINK), ("ABOUT GTA 6", font(BLACK_I, 210), YELLOW, PINK)]
        sub = "ONE WEEK TO LAUNCH  •  NOV 19, 2026"
    else:
        rows = [("WHICH FACT", font(BLACK_I, 150), WHITE, PINK), ("SURPRISED YOU?", font(BLACK_I, 150), YELLOW, PINK)]
        sub = "COMMENT  •  LIKE  •  SUBSCRIBE"
    y = 230
    for text, fn, col, gcol in rows:
        while fn.getlength(text) > 1150: fn = font(BLACK_I, fn.size - 6)
        x = 110
        def dr(d, gc, text=text, fn=fn, col=col, x=x, y=y): d.text((x, y), text, font=fn, fill=gc or col)
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(sh).text((x + 8, y + 8), text, font=fn, fill=gcol)
        layer = Image.alpha_composite(layer, sh)
        layer = Image.alpha_composite(layer, glow_text((W, H), dr, gcol + (255,), 20, 2))
        y += int(fn.size * 1.1)
    fs = font(BOLD, 40); d = ImageDraw.Draw(layer)
    sw = fs.getlength(sub)
    d.rounded_rectangle([110, y + 30, 110 + sw + 60, y + 100], radius=35, outline=CYAN, width=3, fill=(10, 30, 50, 170))
    d.text((140, y + 42), sub, font=fs, fill=CYAN)
    return layer

FN_CAP = font(BOLD, 46)
CX = 700
@lru_cache(maxsize=64)
def caption(seg_i, hi):
    seg = SEGS[seg_i]
    words = seg["text"].split()
    lines = wrap(seg["text"], FN_CAP, 1080)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
    lh = 62; total_h = lh * len(lines)
    y0 = H - 95 - total_h
    maxw = max(FN_CAP.getlength(l) for l in lines)
    d.rounded_rectangle([CX - maxw / 2 - 34, y0 - 20, CX + maxw / 2 + 34, y0 + total_h + 14], radius=22, fill=(8, 0, 20, 185))
    idx = 0
    for li, ln in enumerate(lines):
        x = CX - FN_CAP.getlength(ln) / 2; y = y0 + li * lh
        for w in ln.split():
            col = YELLOW if idx == hi else (WHITE if idx < hi or hi < 0 else (205, 195, 220))
            if idx == hi:
                d.text((x, y), w, font=FN_CAP, fill=col, stroke_width=2, stroke_fill=(120, 30, 90))
            else:
                d.text((x, y), w, font=FN_CAP, fill=col)
            x += FN_CAP.getlength(w + " "); idx += 1
    return layer

def word_index(seg, t):
    words = seg["text"].split()
    ws = seg.get("words") or []
    if len(ws) >= max(1, len(words) // 2):
        # map kokoro tokens (punctuation-free words) to caption words by order
        toks = [w for w in ws if any(c.isalnum() for c in w["w"])]
        k = sum(1 for w in toks if w["s"] <= t) - 1
        return min(max(k, 0), len(words) - 1) if toks else 0
    frac = (t - seg["start"]) / max(0.01, seg["end"] - seg["start"])
    lens = np.cumsum([len(w) + 1 for w in words]); lens = lens / lens[-1]
    return int(np.searchsorted(lens, frac))

PB_Y = H - 26
def progress(layer_d, n_done, cur):
    x0, x1 = 110, W - 110; gap = 6; n = 35
    w = (x1 - x0 - gap * (n - 1)) / n
    for i in range(n):
        xa = x0 + i * (w + gap)
        col = PINK + (255,) if i < n_done else ((255, 255, 255, 230) if i == cur else (255, 255, 255, 60))
        layer_d.rounded_rectangle([xa, PB_Y, xa + w, PB_Y + 8], radius=4, fill=col)

def ease(x): x = min(max(x, 0), 1); return 1 - (1 - x) ** 3

# ---------------------------------------------------------------- frame
BG = None
def seg_at(t):
    cur = 0
    for i, s in enumerate(SEGS):
        if t >= s["start"] - 0.25: cur = i
    return cur

def render_frame(fi):
    t = fi / FPS
    si = seg_at(t); seg = SEGS[si]
    since = t - (seg["start"] - 0.25)
    frame = base_frame(t, since)
    key = seg["key"]
    card = title_card(key) if key in ("intro", "outro") else fact_card(int(key[4:]))
    e = ease(since / 0.35)
    if e < 1:
        card = card.copy(); a = np.array(card); a[..., 3] = (a[..., 3] * e).astype(np.uint8)
        card = Image.fromarray(a); frame.alpha_composite(card, (int(-90 * (1 - e)), 0))
    else:
        frame.alpha_composite(card)
    if seg["start"] - 0.05 <= t <= seg["end"] + 0.5 and key != "intro":
        frame.alpha_composite(caption(si, word_index(seg, t) if t <= seg["end"] else -1))
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    n_done = 0 if key == "intro" else (35 if key == "outro" else int(key[4:]) - 1)
    progress(d, n_done, n_done if key.startswith("fact") else -1)
    frame.alpha_composite(ov)
    if since < 0.12 and si > 0:                         # flash on cut
        fl = Image.new("RGBA", (W, H), (255, 255, 255, int(110 * (1 - since / 0.12)))); frame.alpha_composite(fl)
    return frame.convert("RGB").tobytes()

def render_chunk(args):
    global BG
    idx, a, b, out = args
    BG = build_bg_loop()
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                          "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    for fi in range(a, b):
        p.stdin.write(render_frame(fi))
        if (fi - a) % 300 == 0: print(f"chunk{idx}: {fi - a}/{b - a}", flush=True)
    p.stdin.close(); p.wait()
    return out

if __name__ == "__main__":
    total = int(DUR * FPS)
    if len(sys.argv) > 1 and sys.argv[1] == "stills":
        BG = build_bg_loop()
        for t in map(float, sys.argv[2:]):
            Image.frombytes("RGB", (W, H), render_frame(int(t * FPS))).save(f"still_{t:g}.png")
        sys.exit()
    nproc = 4
    os.makedirs("parts", exist_ok=True)
    step = math.ceil(total / nproc)
    jobs = [(i, i * step, min(total, (i + 1) * step), f"parts/p{i}.mp4") for i in range(nproc)]
    with Pool(nproc) as pool: outs = pool.map(render_chunk, jobs)
    open("parts/list.txt", "w").write("".join(f"file '{os.path.basename(o)}'\n" for o in outs))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "parts/list.txt", "-c", "copy", "video_noaudio.mp4"], check=True)
    print("done", total, "frames")
