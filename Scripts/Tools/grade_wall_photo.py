"""Turn the raw wall-photo capture into the faded print that hangs in Maria's room.

Input:  SourceArt/Photos/raw_MariaEnzo_young.png (viewport capture from shoot_wall_photo.py)
Output: SourceArt/Photos/T_Photo_MariaEnzo.jpg (1024 px wide, cream print border)

The young MetaHumans render with glowing white eyes (an asset issue not yet tracked down), so
the eyes are repainted first: socket shadow, dim sclera, dark brown iris and pupil, drawn at 4x
and blended into the face with a feathered mask. EYES holds the eye centres in raw pixels;
re-measure them if the capture is reshot.

Run: python Scripts/Tools/grade_wall_photo.py
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

PROJECT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SRC = os.path.join(PROJECT, "SourceArt", "Photos", "raw_MariaEnzo_young.png")
DST = os.path.join(PROJECT, "SourceArt", "Photos", "T_Photo_MariaEnzo.jpg")
# eye centre (x, y), half width, half height in raw pixels; skin sample offset below the eye
EYES = [((577, 553), 7.5, 3.0), ((606, 553), 7.5, 3.0),     # Maria
        ((891, 455), 7.5, 3.0), ((922, 454), 7.5, 3.0)]     # Enzo
SS = 4                                   # supersampling for the painted eyes
ASPECT = 1.13                            # picture area of SM_PhotoFrame
CROP_CX, CROP_TOP, CROP_W = 760, 300, 1120


def paint_eye(img, centre, a, b):
    cx, cy = centre
    pad = int(a + 7)
    box = (cx - pad, cy - pad, cx + pad + 1, cy + pad + 1)
    patch = img.crop(box)
    arr = np.asarray(patch).astype(np.float32)
    # skin tone from the cheek just below the eye (median is robust to stray glow)
    skin = np.median(np.asarray(img.crop((cx - 6, cy + 6, cx + 6, cy + 10))).reshape(-1, 3), axis=0)
    n = patch.size[0] * SS
    big = Image.new("RGB", (n, n), tuple(int(v) for v in skin))
    d = ImageDraw.Draw(big)
    c = pad * SS + SS // 2

    def ell(ax, by, dy=0.0):
        return (c - ax * SS, c + (dy - by) * SS, c + ax * SS, c + (dy + by) * SS)

    d.ellipse(ell(a + 3.5, b + 3.0), fill=tuple(int(v * 0.78) for v in skin))   # socket shade
    d.ellipse(ell(a, b), fill=tuple(int(v * 0.30) for v in skin))               # lash line / opening
    sclera = tuple(int(0.55 * v + 0.45 * 150) for v in (skin * 0.85))
    d.ellipse(ell(a - 0.8, b - 0.8, 0.2), fill=sclera)
    mask_open = Image.new("L", (n, n), 0)
    ImageDraw.Draw(mask_open).ellipse(ell(a - 0.8, b - 0.8, 0.2), fill=255)
    iris = Image.new("RGB", (n, n), (0, 0, 0))
    di = ImageDraw.Draw(iris)
    r = b + 0.6
    di.ellipse((c - r * SS, c - r * SS + SS * 0.4, c + r * SS, c + r * SS + SS * 0.4), fill=(62, 42, 30))
    rp = r * 0.45
    di.ellipse((c - rp * SS, c - rp * SS + SS * 0.4, c + rp * SS, c + rp * SS + SS * 0.4), fill=(18, 12, 9))
    di.ellipse((c - 1.6 * SS, c - 1.4 * SS, c - 0.8 * SS, c - 0.6 * SS), fill=(150, 140, 128))  # catchlight
    iris_mask = Image.new("L", (n, n), 0)
    ImageDraw.Draw(iris_mask).ellipse((c - r * SS, c - r * SS + SS * 0.4, c + r * SS, c + r * SS + SS * 0.4), fill=255)
    big.paste(iris, (0, 0), Image.fromarray(np.minimum(np.asarray(iris_mask), np.asarray(mask_open))))
    d.line([(c - a * SS, c - b * SS * 0.2), (c, c - b * SS * 1.05), (c + a * SS, c - b * SS * 0.2)],
           fill=tuple(int(v * 0.22) for v in skin), width=SS)                    # upper lid
    painted = np.asarray(big.resize(patch.size, Image.LANCZOS)).astype(np.float32)
    # feathered blend: full inside the socket, fading out over the glow halo
    yy, xx = np.mgrid[0:patch.size[1], 0:patch.size[0]]
    rr = np.sqrt(((xx - pad) / (a + 5.0)) ** 2 + ((yy - pad) / (b + 4.5)) ** 2)
    w = np.clip((1.25 - rr) / 0.35, 0, 1)[..., None]
    out = arr * (1 - w) + painted * w
    img.paste(Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)), box[:2])


def main():
    img = Image.open(SRC).convert("RGB")
    for centre, a, b in EYES:
        paint_eye(img, centre, a, b)
    h = int(CROP_W / ASPECT)
    img = img.crop((CROP_CX - CROP_W // 2, CROP_TOP, CROP_CX + CROP_W // 2, CROP_TOP + h))
    a = np.asarray(img).astype(np.float32) / 255.0
    # 1970s print: gamma lift (the dome rendered dusky), faded colour, warm cast, soft blacks
    a = np.power(np.clip(a, 0, 1), 0.70)
    lum = (a * [0.3, 0.59, 0.11]).sum(-1, keepdims=True)
    a = lum + (a - lum) * 0.72
    a = a * [1.08, 1.0, 0.86] + [0.04, 0.025, 0.0]
    a = 0.10 + a * 0.82
    hh, ww = a.shape[:2]
    yy, xx = np.mgrid[0:hh, 0:ww]
    r = np.sqrt(((xx - ww / 2) / (ww / 2)) ** 2 + ((yy - hh / 2) / (hh / 2)) ** 2)
    a *= (1 - 0.28 * np.clip(r - 0.55, 0, 1) ** 1.5)[..., None]      # vignette
    a += np.random.default_rng(7).normal(0, 0.018, a.shape[:2])[..., None]   # grain
    img = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))
    img = img.resize((1024, int(1024 / ASPECT)), Image.LANCZOS)
    bw = 36                                                            # cream paper border
    out = Image.new("RGB", (img.width + 2 * bw, img.height + 2 * bw), (236, 228, 210))
    out.paste(img, (bw, bw))
    out = out.resize((1024, int(1024 * out.height / out.width)), Image.LANCZOS)
    out.save(DST, quality=92)
    print(f"wrote {DST} {out.size}")


if __name__ == "__main__":
    main()
