# -*- coding: utf-8 -*-
"""定位「红像素」到底在哪 —— 排除暖调肤色/布料被误计（2026-09-20）。

背景：`_check_50shi_candidate.py` 对 4 张 50 式候选图都报红占比 0.34%~0.56%
      （>0.30% FAIL）。但那些图肉眼看不到红领章 —— 必须查清是
      ① 真有成片红布，还是 ② 暖调光照下的**肤色/土黄布料**落进了红侧色相阈值。

做法：把红像素按**位置**聚类（行/列直方图 + bbox），并额外输出
      **只看领口附近的一条带**，把「脸/手肤色」与「领口区域」分开统计。

用法
    py -3.10 OUTPUT/_diag_50shi_red.py OUTPUT/uniform_50shi/frames_young_soldier_v03/f020.png
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RED_HUE_HI = 20
RED_HUE_LO = 300
RED_SAT_MIN = 0.42
RED_VAL_MIN = 40


def masks(im):
    hsv = np.asarray(im.convert("HSV")).astype(np.float32)
    h = hsv[..., 0] * 360 / 255.0
    s = hsv[..., 1] / 255.0
    v = hsv[..., 2] / 255.0
    red = ((h < RED_HUE_HI) | (h > RED_HUE_LO)) & (s > RED_SAT_MIN) & (v * 255 > RED_VAL_MIN)
    # 「皮肤候选」：色相 5~45°（暖橙）、中低饱和、较亮 —— 白种/黄种肤色典型区间
    skin = (h > 5) & (h < 45) & (s > 0.25) & (s < 0.62) & (v * 255 > 90)
    # 「深红布」：更严的饱和阈值，用来区分「实心红布」与「暖色偏移」
    strong = ((h < RED_HUE_HI) | (h > RED_HUE_LO)) & (s > 0.62) & (v * 255 > 40)
    return h, s, v, red, skin, strong


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    args = ap.parse_args()
    paths = args.paths or ["OUTPUT/uniform_50shi/frames_young_soldier_v03/f020.png"]

    for p in paths:
        p = p if os.path.isabs(p) else os.path.join(ROOT, p)
        if not os.path.exists(p):
            print("跳过（不存在）: %s" % p)
            continue
        im = Image.open(p).convert("RGB")
        W, H = im.size
        h, s, v, red, skin, strong = masks(im)
        print("=" * 78)
        print("%s   %dx%d" % (os.path.relpath(p, ROOT), W, H))
        print("  红(sat>%.2f) %6d px  %.4f%%" % (RED_SAT_MIN, red.sum(), 100 * red.sum() / red.size))
        print("  强红(sat>0.62) %6d px  %.4f%%   ← 「成片红布」更可信的指标"
              % (strong.sum(), 100 * strong.sum() / strong.size))
        print("  暖肤色带       %6d px  %.4f%%" % (skin.sum(), 100 * skin.sum() / skin.size))

        if red.sum() == 0:
            print("  → 无红像素")
            continue
        ys, xs = np.nonzero(red)
        print("  bbox  x[%d,%d] y[%d,%d]" % (xs.min(), xs.max(), ys.min(), ys.max()))

        rows, cols = red.sum(axis=1), red.sum(axis=0)
        print("  红最多的 6 行：")
        for i in np.argsort(rows)[-6:][::-1]:
            if rows[i] == 0:
                break
            print("     y=%4d  %5d px  (%.1f%% 行宽)  该行皮肤像素 %d"
                  % (i, rows[i], 100 * rows[i] / W, skin[i].sum()))
        print("  红最多的 6 列：")
        for i in np.argsort(cols)[-6:][::-1]:
            if cols[i] == 0:
                break
            print("     x=%4d  %5d px" % (i, cols[i]))

        # 肤色重叠：红像素里有多少同时落在"暖肤色带"内 → 说明是误计
        both = red & skin
        print("  红 ∩ 暖肤色带 = %d px  (占红像素 %.1f%%)  ← 越高越像「肤色被误计」"
              % (both.sum(), 100.0 * both.sum() / max(red.sum(), 1)))
        # 领口带：人脸下方到胸口，粗略 0.45H ~ 0.62H，水平居中 0.30W~0.70W
        band = np.zeros_like(red)
        band[int(0.45 * H):int(0.62 * H), int(0.30 * W):int(0.70 * W)] = True
        print("  领口带内：红 %d px / 强红 %d px  (占全图 %.4f%%)"
              % ((red & band).sum(), (strong & band).sum(),
                 100.0 * (red & band).sum() / red.size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
