# -*- coding: utf-8 -*-
"""★ 把候选裁剪块拼成一张审图板（读图铁律的批量执行器）。

用法：
    py -3.10 OUTPUT/_wm_sheet.py _wm_read            # 拼某目录下所有 jpg
    py -3.10 OUTPUT/_wm_sheet.py _wm_read out.jpg    # 指定输出名
"""
from __future__ import annotations
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
PER = 3
CW = 700
LAB = 20


def main():
    d = os.path.join(HERE, sys.argv[1] if len(sys.argv) > 1 else "_wm_read")
    out = os.path.join(d, sys.argv[2] if len(sys.argv) > 2 else "SHEET.jpg")
    fs = sorted(f for f in os.listdir(d) if f.lower().endswith(".jpg") and f != os.path.basename(out))
    if not fs:
        print("无图")
        return 1
    cells = []
    for f in fs:
        im = Image.open(os.path.join(d, f)).convert("RGB")
        w, h = im.size
        ch = max(40, int(h * CW / w))
        cells.append((f, im.resize((CW, min(ch, 320)), Image.LANCZOS)))
    nrow = (len(cells) + PER - 1) // PER
    chh = max(c[1].size[1] for c in cells)
    canvas = Image.new("RGB", (CW * PER, (chh + LAB) * nrow), (12, 12, 14))
    dr = ImageDraw.Draw(canvas)
    for k, (f, im) in enumerate(cells):
        r_, c_ = k // PER, k % PER
        dr.text((c_ * CW + 6, r_ * (chh + LAB) + 4), f.replace(".jpg", ""), fill=(140, 240, 160))
        canvas.paste(im, (c_ * CW, r_ * (chh + LAB) + LAB))
    canvas.save(out, quality=90)
    print("%d 块 -> %s" % (len(cells), out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
