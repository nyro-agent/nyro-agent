"""Finish a raw banner render: soft bloom, gentle vignette, then the domain bottom-right.

    python3 -I post.py og-raw.png og.jpg 1200 630
"""
import sys, os
from PIL import Image, ImageFilter, ImageChops, ImageDraw, ImageFont

src, dst, W, H = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
HERE = os.path.dirname(os.path.abspath(__file__))
im = Image.open(src).convert("RGB")

# bloom: bright pass, blurred twice, screened on top
bright = im.point(lambda v: max(0, v - 170) * 3)
glow = ImageChops.add(bright.filter(ImageFilter.GaussianBlur(im.width / 180)),
                      bright.filter(ImageFilter.GaussianBlur(im.width / 45)), scale=1.6)
im = ImageChops.screen(im, glow)

# vignette: darken the corners a little
mask = Image.new("L", (im.width // 8, im.height // 8), 0)
ImageDraw.Draw(mask).ellipse((-mask.width * 0.15, -mask.height * 0.25, mask.width * 1.15, mask.height * 1.25), fill=255)
mask = mask.filter(ImageFilter.GaussianBlur(mask.width / 10)).resize(im.size, Image.LANCZOS)
im = Image.composite(im, ImageChops.multiply(im, Image.new("RGB", im.size, (110, 110, 115))), mask)

im = im.resize((W, H), Image.LANCZOS)

# domain, bottom-right
d = ImageDraw.Draw(im)
size = round(H * 0.046)
font = ImageFont.truetype(os.path.join(HERE, "font", "satoshi-700.ttf"), size)
text = "nyro.run"
pad = round(H * 0.06)
x0, y0, x1, y1 = d.textbbox((0, 0), text, font=font)
pos = (W - pad - x1, H - pad - y1)
# soft dark shadow so the domain stays readable over busy parts of the image
sh = Image.new("L", im.size, 0); ImageDraw.Draw(sh).text(pos, text, font=font, fill=255)
sh = sh.filter(ImageFilter.GaussianBlur(size * 0.35)).point(lambda v: min(255, v * 2))
im = Image.composite(Image.new("RGB", im.size, (0, 0, 0)), im, sh.point(lambda v: v * 0.75))
d = ImageDraw.Draw(im)
d.text(pos, text, font=font, fill=(238, 232, 220))
im.save(dst, quality=90, optimize=True, progressive=True)
print(dst, im.size, os.path.getsize(dst) // 1024, "KB")
