# -*- coding: utf-8 -*-
"""★ 水印 A/B 对比：同一镜的两版（旧/新）在同一**归一化区域**上做笔画带比对。

为什么要"归一化区域 + 稳定带"
    镜 18 的水印「豆包AI生成」是**水平排列的六字实体笔画**，位置固定在
    投影仪机身侧面（约 0.70–0.78H、0.12–0.50W）。
    ⇒ 判据 = 该区域内**存在一条水平笔画带**：
        · 带内每行的"笔画像素数"呈**连续数十行非零**；
        · 带的**水平跨度** >= 0.15W（六个字连排）；
        · 这个结构在**多帧同一位置**重复（水印不随镜头动）。

为什么不做 A/B 差图
    两版 seed 不同 ⇒ 画面本身不同，差图会全屏噪声。
    只有"**带结构的有无**"才是可比的量。

用法：
    py -3.10 OUTPUT/_wm_ab.py OLD.mp4 NEW.mp4 --box=0.12,0.68,0.50,0.80
    py -3.10 OUTPUT/_wm_ab.py OLD.mp4 NEW.mp4          # 默认扫下半画面找最强带
"""
from __future__ import annotations
import io
import subprocess
import sys

import numpy as np
from PIL import Image


def dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", p], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def grab(p, t):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", "%.3f" % t, "-i", p,
                        "-vframes", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
                       capture_output=True)
    return Image.open(io.BytesIO(r.stdout)).convert("L") if r.stdout else None


def stroke_band(im, box):
    """在 box 内找"水平笔画带"，返回 (行跨度, 最大水平跨度, 笔画px)。"""
    a = np.asarray(im, dtype=np.float32)
    H, W = a.shape
    if box:
        x0, y0, x1, y1 = (int(box[0] * W), int(box[1] * H),
                          int(box[2] * W), int(box[3] * H))
    else:
        x0, y0, x1, y1 = int(W * 0.03), int(H * 0.35), int(W * 0.97), int(H * 0.95)
    reg = a[y0:y1, x0:x1]
    if reg.size == 0:
        return 0, 0, 0
    k = 9
    bg = reg.copy()
    for axis in (0, 1):
        pad = np.pad(bg, [(k // 2, k // 2) if i == axis else (0, 0) for i in range(2)],
                     mode="edge")
        sw = np.lib.stride_tricks.sliding_window_view(pad, k, axis=axis)
        bg = sw.max(axis=-1)
    ink = (bg - reg) > 26
    rows = ink.sum(1)
    if rows.sum() == 0:
        return 0, 0, 0
    thr = max(3, int(rows.max() * 0.18))
    on = rows >= thr
    # 最长连续非零段
    best = cur = 0
    bw = 0
    run_start = None
    for i, v in enumerate(on):
        if v:
            if cur == 0:
                run_start = i
            cur += 1
            if cur > best:
                best = cur
            if run_start is not None:
                cols = ink[run_start:i + 1].any(0)
                idx = np.where(cols)[0]
                if len(idx):
                    bw = max(bw, int(idx.max() - idx.min() + 1))
        else:
            cur = 0
            run_start = None
    return best, bw, int(ink.sum())


def main():
    old, new = sys.argv[1], sys.argv[2]
    box = None
    for a in sys.argv[3:]:
        if a.startswith("--box="):
            box = tuple(float(x) for x in a.split("=", 1)[1].split(","))
    print("框选区域：%s" % (str(box) if box else "下半画面（自动）"))
    print("文件                       最长行段  最大水平跨度  ink_px   判定")
    print("-" * 74)
    for tag, p in (("旧", old), ("新", new)):
        d = dur(p)
        bands = []
        for i in range(6):
            im = grab(p, d * (i + 0.5) / 6)
            if im is None:
                continue
            bands.append(stroke_band(im, box))
        if not bands:
            print("%-26s 抽帧失败" % tag)
            continue
        rs = [b[0] for b in bands]
        ws = [b[1] for b in bands]
        ins = [b[2] for b in bands]
        H = 608
        med_r, mx_w, med_i = int(np.median(rs)), int(np.median(ws)), int(np.median(ins))
        # 六字水印 ≈ 一行 20-40px 高的笔画带，水平跨度 >= 0.15W 且多帧稳定
        verdict = "★ 疑似烧字带" if (med_r >= 12 and mx_w >= 0.15 * 1056) else "无带状结构"
        print("%-26s %-9d %-12d %-8d %s（6帧行段=%s）"
              % (tag, med_r, mx_w, med_i, verdict, rs))
    print("-" * 74)
    print("★ 判据：`最长行段 >= 12` 且 `水平跨度 >= 158px(0.15W)` 才是字带；"
          "纹理/渐变不会有长行段。**仍需读图终判**。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
