# -*- coding: utf-8 -*-
"""临时：把候选底图拼一张看（用完即删）。py -3.10 OUTPUT/_dbg_bases.py 9 121"""
import os
import sys
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
shots = [int(x) for x in sys.argv[1:]] or [9, 121]
tiles = []
for n in shots:
    p = os.path.join(ROOT, "OUTPUT", "comic", "frames", "%03d.png" % n)
    im = Image.open(p).convert("RGB")
    k = 1400.0 / im.width
    im = im.resize((1400, int(im.height * k)), Image.LANCZOS)
    t = Image.new("RGB", (1400, im.height + 34), (255, 255, 255))
    t.paste(im, (0, 34))
    ImageDraw.Draw(t).text((6, 8), "shot %d" % n, fill=(0, 0, 0))
    tiles.append(t)
out = Image.new("RGB", (1400, sum(t.height for t in tiles)), (255, 255, 255))
y = 0
for t in tiles:
    out.paste(t, (0, y))
    y += t.height
dst = os.path.join(ROOT, "OUTPUT", "_view_out", "bases.jpg")
os.makedirs(os.path.dirname(dst), exist_ok=True)
out.save(dst, "JPEG", quality=88)
print(dst, out.size)
