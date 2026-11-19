"""Flat Nyro mark + wordmark PNGs (transparent), drawn to match logo/nyro-mark.svg.

    python3 -I wordmark.py <out_dir>
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "font", "satoshi-700.ttf")
N = [[[10.725, 5.902], [8.266, 5.902], [3.0, 18.098], [5.781, 18.098], [9.842, 8.817], [13.92, 13.159], [14.958, 10.666]], [[13.275, 18.098], [15.734, 18.098], [21.0, 5.902], [18.219, 5.902], [14.158, 15.183], [10.08, 10.841], [9.042, 13.334]]]

def hexc(h): return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], float)

def mark(px):
    s = 4                                   # supersample
    S = px * s; u = S / 28
    yy, xx = np.mgrid[0:S, 0:S] / (S - 1)
    t = np.clip((xx + yy) / 2, 0, 1)[..., None]           # diagonal gradient like the SVG
    c0, c1, c2 = hexc("#f6dc96"), hexc("#d6aa50"), hexc("#8a6420")
    rgb = np.where(t < .55, c0 + (c1 - c0) * (t / .55), c1 + (c2 - c1) * ((t - .55) / .45))
    im = Image.fromarray(np.dstack([rgb, np.full((S, S), 255.0)]).astype(np.uint8), "RGBA")
    a = Image.new("L", (S, S), 0); ImageDraw.Draw(a).ellipse((1 * u, 1 * u, 27 * u, 27 * u), fill=255)
    im.putalpha(a)
    ov = Image.new("RGBA", (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    r0, w = 10.4 * u, 1.1 * u
    d.ellipse((14 * u - r0 - w / 2, 14 * u - r0 - w / 2, 14 * u + r0 + w / 2, 14 * u + r0 + w / 2), outline=(0x5c, 0x42, 0x12, 140), width=round(w))
    for piece in N:
        d.polygon([((4.16 + .82 * x) * u, (4.16 + .82 * y) * u) for x, y in piece], fill=(0x3a, 0x2a, 0x0b, 255))
    im = Image.alpha_composite(im, ov)
    return im.resize((px, px), Image.LANCZOS)

os.makedirs(OUT, exist_ok=True)
for px in (512, 1024):
    mark(px).save(os.path.join(OUT, f"nyro-mark-{px}.png"))

def wordmark(color, name, h=256):
    m = mark(h)
    font = ImageFont.truetype(FONT, round(h * 0.62))
    d0 = ImageDraw.Draw(Image.new("L", (1, 1)))
    x0, y0, x1, y1 = d0.textbbox((0, 0), "nyro", font=font)
    gap = round(h * 0.18)
    _, ny0, _, ny1 = d0.textbbox((0, 0), "nro", font=font)   # x-height box, no descender
    W = h + gap + (x1 - x0) + round(h * 0.04)
    im = Image.new("RGBA", (W, h), (0, 0, 0, 0)); im.alpha_composite(m, (0, 0))
    d = ImageDraw.Draw(im)
    # centre the x-height of "nyro" on the mark
    d.text((h + gap - x0, (h - (ny1 - ny0)) / 2 - ny0), "nyro", font=font, fill=color)
    im.save(os.path.join(OUT, name))

wordmark((244, 244, 244, 255), "nyro-wordmark-on-dark.png")
wordmark((10, 10, 10, 255), "nyro-wordmark-on-light.png")
print("ok", sorted(os.listdir(OUT)))
