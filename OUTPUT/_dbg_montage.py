# -*- coding: utf-8 -*-
"""临时：把任意几张图拼成联系表看图（用完即删）。py -3.10 OUTPUT/_dbg_montage.py a.png b.png"""
import os
import sys
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = 1300
tiles = []
for p in sys.argv[1:]:
    im = Image.open(p).convert("RGB")
    k = W / float(im.width)
    im = im.resize((W, int(im.height * k)), Image.LANCZOS)
    t = Image.new("RGB", (W, im.height + 30), (255, 255, 255))
    t.paste(im, (0, 30))
    ImageDraw.Draw(t).text((6, 6), os.path.basename(p), fill=(0, 0, 0))
    tiles.append(t)
out = Image.new("RGB", (W, sum(t.height for t in tiles)), (255, 255, 255))
y = 0
for t in tiles:
    out.paste(t, (0, y))
    y += t.height
dst = os.path.join(ROOT, "OUTPUT", "_view_out", "montage.jpg")
os.makedirs(os.path.dirname(dst), exist_ok=True)
out.save(dst, "JPEG", quality=86)
print(dst, out.size)
