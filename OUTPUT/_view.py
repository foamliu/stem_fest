#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""省图片额度看图：把大图缩到 ≤1024 px 后再交给主模型读。

用法： py -3.10 OUTPUT/_view.py <图片路径> [更多路径...] [--max 1024]
输出：缩好的副本写到 OUTPUT/_view_out/ ，路径打印到 stdout。
"""
import os
import sys

from PIL import Image

ROOT = r"E:\code\stem_fest"
OUTDIR = os.path.join(ROOT, "OUTPUT", "_view_out")

MAXPX = 1024
args = [a for a in sys.argv[1:] if not a.startswith("--")]
for a in sys.argv[1:]:
    if a.startswith("--max="):
        MAXPX = int(a.split("=", 1)[1])

os.makedirs(OUTDIR, exist_ok=True)
for p in args:
    if not os.path.exists(p):
        print("[X] 不存在：%s" % p)
        continue
    im = Image.open(p)
    w, h = im.size
    if max(w, h) > MAXPX:
        k = MAXPX / float(max(w, h))
        im = im.resize((max(1, int(w * k)), max(1, int(h * k))), Image.LANCZOS)
    dst = os.path.join(OUTDIR, os.path.splitext(os.path.basename(p))[0] + ".jpg")
    im.convert("RGB").save(dst, "JPEG", quality=88)
    print("%s -> %s  %sx%s %.0fKB" % (
        p, dst, im.width, im.height, os.path.getsize(dst) / 1024.0))
