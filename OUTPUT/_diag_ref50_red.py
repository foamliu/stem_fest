# -*- coding: utf-8 -*-
"""诊断：`cap_side_laojunpin.jpg` 里的高饱和红到底在哪（2026-09-20）。

目的：v2 清洗脚本"越清越红"（1.75% → 2.47%），必须查清是
  (a) 红色像素本身没被掩膜覆盖 → 膨胀后仍漏，还是
  (b) `inpaint` 把邻近的暖色布纹推进了掩膜区，反而造出新红像素。
本脚本把红色像素的 bbox、行/列直方图、以及"掩膜 vs 实际红像素"的重叠率打出来。
"""
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "OUTPUT", "uniform_50shi", "ref2", "cap_side_laojunpin.jpg")


def red_mask(im, hue_hi=20, hue_lo=300, sat_min=0.42, val_min=40):
    hsv = np.asarray(im.convert("HSV")).astype(np.float32)
    h, s, v = hsv[..., 0] * 360 / 255, hsv[..., 1] / 255, hsv[..., 2] / 255
    return ((h < hue_hi) | (h > hue_lo)) & (s > sat_min) & (v * 255 > val_min)


def main():
    im = Image.open(P).convert("RGB")
    a = np.asarray(im)
    H, W, _ = a.shape
    m = red_mask(im)
    ys, xs = np.nonzero(m)
    print("图 %dx%d  红像素 %d (%.4f%%)" % (W, H, m.sum(), 100 * m.sum() / m.size))
    print("bbox  x[%d,%d] y[%d,%d]" % (xs.min(), xs.max(), ys.min(), ys.max()))
    print("红像素占比最高的 5 行：")
    rows = m.sum(axis=1)
    for i in np.argsort(rows)[-5:][::-1]:
        print("   y=%4d  %5d px  (%.1f%% 行宽)" % (i, rows[i], 100 * rows[i] / W))
    print("红像素占比最高的 5 列：")
    cols = m.sum(axis=0)
    for i in np.argsort(cols)[-5:][::-1]:
        print("   x=%4d  %5d px" % (i, cols[i]))

    # 掩膜膨胀后与实际红像素的重叠率
    for k, it in ((3, 1), (3, 2), (5, 2), (5, 3)):
        img = Image.fromarray((m * 255).astype(np.uint8))
        for _ in range(it):
            img = img.filter(ImageFilter.MaxFilter(k))
        d = np.asarray(img) > 127
        cover = 100.0 * (m & d).sum() / max(m.sum(), 1)
        print("MaxFilter(k=%d,it=%d): 覆盖红 %.2f%%  面积 %.4f%%"
              % (k, it, cover, 100 * d.sum() / d.size))

    # 掩膜区周围布料的色相（判断 inpaint 抽邻居会不会抽到红）
    print("\n掩膜区外扩 12px 环带内，红像素比例：")
    img = Image.fromarray((m * 255).astype(np.uint8))
    ring = np.asarray(img.filter(ImageFilter.MaxFilter(25))) > 127
    ring &= ~m
    print("   环带 %d px，其中红 %d px (%.2f%%)"
          % (ring.sum(), (m & ring).sum(), 100.0 * (m & ring).sum() / max(ring.sum(), 1)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
