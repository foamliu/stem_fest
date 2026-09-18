# -*- coding: utf-8 -*-
"""★ 量化「高铁 LED 信息屏」出现情况：找出**有发光屏**的镜 + 屏上是否有笔画。

为什么用"量化"而不是"读图"
    读图是最终判据，但当读图通道受限时，先用**像素统计**把范围锁定到
    「确实点亮的 LED 屏」那几镜，读图只需看这几镜即可。
    这也符合"扫描器只筛候选"的纪律 —— 它只负责把 126 镜缩到 3-5 镜。

判据（LED 屏的特征）
    · 位置：上半画面（< 0.20H），通常是车厢端墙上方的一条横屏；
    · 颜色：**高饱和红/绿发光点阵**（S>110, V>130），这是 LED 屏独有特征；
    · 与"行李架金属格栅"的区别：格栅是**低饱和灰白**，不会命中。

输出每镜：发光像素数 + 红/绿占比 + 是否有"笔画感"（细密连通块）
用法：
    py -3.10 OUTPUT/_led_probe.py --shots=74-108
    py -3.10 OUTPUT/_led_probe.py --shots=100-108 --dump
"""
from __future__ import annotations
import io
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
DIRS = ["01_paper_plane", "04_classroom_dusk", "05_classroom_night",
        "06_trench", "07_rice_field", "08_train_dining", "02_campus"]
CROPS = os.path.join(HERE, "_led_crops")
SKIP = ("_mid_", "_bak_", "_v2bak_", "_rejected")


def newest_by_shot():
    best = {}
    for d in DIRS:
        vd = os.path.join(HERE, d, "video")
        if not os.path.isdir(vd):
            continue
        for f in os.listdir(vd):
            if not f.endswith(".mp4") or f.startswith(SKIP):
                continue
            m = re.match(r"(\d+)_", f)
            if m:
                n = int(m.group(1))
                p = os.path.join(vd, f)
                if n not in best or os.path.getmtime(p) > os.path.getmtime(best[n]):
                    best[n] = p
    return best


def dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", p], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def nblobs(mask, min_px=4):
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    c = 0
    for sy, sx in np.argwhere(mask):
        if seen[sy, sx]:
            continue
        c += 1
        stack = [(int(sy), int(sx))]
        seen[sy, sx] = True
        n = 0
        while stack:
            y, x = stack.pop()
            n += 1
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        if n < min_px:
            c -= 1
    return c


def parse_shots(spec):
    out = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            x, y = part.split("-", 1)
            out += list(range(int(x), int(y) + 1))
        elif part:
            out.append(int(part))
    return out


def main():
    shots, dump = None, False
    for a in sys.argv[1:]:
        if a.startswith("--shots="):
            shots = parse_shots(a.split("=", 1)[1])
        elif a == "--dump":
            dump = True
    best = newest_by_shot()
    shots = shots or sorted(best)
    if dump:
        os.makedirs(CROPS, exist_ok=True)

    print("镜   T  发光px  红%   绿%   细碎块  箱位(box)")
    print("-" * 72)
    for n in shots:
        src = best.get(n)
        if not src:
            continue
        d = dur(src)
        t = d * 0.55
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", "%.3f" % t, "-i", src,
                            "-vframes", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
                           capture_output=True)
        if not r.stdout:
            continue
        im = Image.open(io.BytesIO(r.stdout)).convert("RGB")
        W, H = im.size
        a = np.asarray(im, dtype=np.int16)
        R, G, B = a[:, :, 0], a[:, :, 1], a[:, :, 2]
        mx = a.max(axis=2)
        mn = a.min(axis=2)
        sat = np.where(mx > 0, (mx - mn) * 255 // np.maximum(mx, 1), 0)
        red = (R > 110) & (R - np.maximum(G, B) > 55)
        grn = (G > 110) & (G - np.maximum(R, B) > 55)
        # ★ 高铁 LED 屏 = 深色底 + 亮红/绿点阵，整体**亮度不高但局部高饱和**。
        #   不要用全局 sat>110（红领巾会更亮），而是找"**深色矩形区域里的高饱和点**"。
        bright = (mx > 120) & (sat > 90)
        m = bright & (red | grn)
        ys, xs = np.where(m)
        if len(ys) < 60:
            continue
        # LED 屏是**一条横带**
        bh = ys.max() - ys.min() + 1
        bw = xs.max() - xs.min() + 1
        if bh > H * 0.09 or bw < W * 0.04:
            continue
        # 且必须在上半画面（车厢端墙上方）
        if ys.mean() > H * 0.35:
            continue
        # ★ 关键区分：LED 屏所在区域**整体是暗的**（黑底），
        #   而红领巾/校徽所在区域整体是亮的（白衫）。用邻域中位亮度区分。
        box = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
        pad = 6
        gx0, gy0 = max(0, box[0] - pad), max(0, box[1] - pad)
        gx1, gy1 = min(W, box[2] + pad), min(H, box[3] + pad)
        g = np.asarray(im.convert("L"))[gy0:gy1, gx0:gx1]
        if float(np.median(g)) > 130:          # 亮底 => 白衫/红领巾，不是 LED 屏
            continue
        sub = m[box[1]:box[3] + 1, box[0]:box[2] + 1]
        frag = nblobs(sub, min_px=4)
        rp = 100.0 * red[m].sum() / max(1, m.sum())
        gp = 100.0 * grn[m].sum() / max(1, m.sum())
        print("%-4d%.1f %-7d %-5.0f %-5.0f %-7d %s bgmed=%d"
              % (n, t, int(m.sum()), rp, gp, frag, box, int(np.median(g))))
        if dump:
            pad = 20
            x0, y0 = max(0, box[0] - pad), max(0, box[1] - pad)
            x1, y1 = min(W, box[2] + pad), min(H, box[3] + pad)
            Image.fromarray(np.asarray(im)[y0:y1, x0:x1]).resize(
                (max(1, (x1 - x0) * 6), max(1, (y1 - y0) * 6)),
                Image.LANCZOS).save(
                os.path.join(CROPS, "s%03d.jpg" % n), quality=92)
    if dump:
        print("裁剪 -> %s" % CROPS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
