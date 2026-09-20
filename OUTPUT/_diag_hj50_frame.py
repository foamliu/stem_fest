# -*- coding: utf-8 -*-
"""黄继光 50 式改图产物 · **分区结构体检**（2026-09-20）。

`_audit_uniform_redo.py` 只看整图红占比，无法回答"这一版到底哪里不对"。
本脚本按**人物区域**分区量化，用来定位每轮问题：

  · `hat_red`    —— 帽子带（图高 0~10%）的红占比 ⇒ **红五星帽徽**专项判据
  · `hat_w`      —— 帽子的横向宽度 / 人物肩宽 ⇒ 判断"棉帽(宽圆)"还是"解放帽(窄)"
  · `figures`    —— 用"非背景像素的横向投影"数**画面里有几个人**
                    （v04 出了两个人、v05 又崩了，这个判据能一眼看出）
  · `blank_l`    —— 左侧 1/4 是否有一整块灰/棋盘格空洞
  · `hat_top`    —— 人物头顶距画面上沿的像素数 ⇒ 判断构图（是否被裁）

用法：
    py -3.10 OUTPUT/_diag_hj50_frame.py <图片路径> [...]
"""
import os
import sys

import numpy as np
from PIL import Image

RED_HUE_LO, RED_HUE_HI, RED_SAT_MIN, RED_VAL_MIN = 20, 340, 0.42, 40


def red_mask(im):
    hsv = np.asarray(im.convert("HSV")).astype(np.float32)
    h, s, v = hsv[..., 0] * 360 / 255, hsv[..., 1] / 255, hsv[..., 2] / 255
    return ((h < RED_HUE_LO) | (h > RED_HUE_HI)) & (s > RED_SAT_MIN) & (v * 255 > RED_VAL_MIN)


def foreground(a):
    """背景=接近中灰/浅灰的大面积色；前景=明显偏离背景色的像素。"""
    H, W, _ = a.shape
    # 用四角 40×40 的中位数当背景色
    k = 40
    corners = np.concatenate([
        a[:k, :k].reshape(-1, 3), a[:k, -k:].reshape(-1, 3),
        a[-k:, :k].reshape(-1, 3), a[-k:, -k:].reshape(-1, 3)])
    bg = np.median(corners, axis=0)
    dist = np.abs(a.astype(np.float32) - bg).sum(axis=2)
    return dist > 55, bg


def count_figures(fg):
    """按列前景占比切"人形"：前景列占比 > 8% 视为有人在，再数连续段。"""
    H, W = fg.shape
    colfrac = fg.sum(axis=0) / H
    on = colfrac > 0.08
    segs, start = [], None
    for x, v in enumerate(on):
        if v and start is None:
            start = x
        elif not v and start is not None:
            if x - start > W * 0.02:
                segs.append((start, x))
            start = None
    if start is not None:
        segs.append((start, W))
    return segs, colfrac


def main():
    paths = sys.argv[1:]
    if not paths:
        print("用法: py -3.10 OUTPUT/_diag_hj50_frame.py <图片...>")
        return 2
    for p in paths:
        if not os.path.isfile(p):
            print("MISS %s" % p)
            continue
        im = Image.open(p).convert("RGB")
        a = np.asarray(im)
        H, W, _ = a.shape
        rm = red_mask(im)
        fg, bg = foreground(a)
        segs, colfrac = count_figures(fg)

        hat = rm[:int(H * 0.10)]
        hat_red = 100.0 * hat.sum() / max(hat.size, 1)

        # 人物整体 bbox（最大那一"人"）
        if segs:
            x0, x1 = max(segs, key=lambda s: s[1] - s[0])
            sub = fg[:, x0:x1]
            ys = np.nonzero(sub.sum(axis=1) > 0)[0]
            y0, y1 = (ys.min(), ys.max()) if len(ys) else (0, H)
        else:
            x0 = x1 = y0 = y1 = 0
        hat_w = 0.0
        if x1 > x0:
            band = fg[:max(y0 + int((y1 - y0) * 0.12), 1), x0:x1]
            cols = np.nonzero(band.sum(axis=0) > 0)[0]
            body_w = x1 - x0
            if len(cols) and body_w:
                hat_w = 100.0 * (cols.max() - cols.min()) / body_w

        left = fg[:, :W // 4]
        blank_l = 100.0 * (1.0 - left.sum() / left.size)

        print("%s" % p)
        print("   %dx%d  bg=%s" % (W, H, bg.astype(int)))
        print("   帽子带红 %.3f%%  |  人物数 %d 段 %s  |  帽宽/肩宽 %.1f%%  "
              "|  左1/4空白 %.1f%%  |  头顶 y=%d/%d"
              % (hat_red, len(segs), segs, hat_w, blank_l, y0, H))
    return 0


if __name__ == "__main__":
    sys.exit(main())
