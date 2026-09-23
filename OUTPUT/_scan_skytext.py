# -*- coding: utf-8 -*-
"""★ 扫**天区文字**（高铁 LED 信息屏 / 告示牌 / 招牌这类"高空小字"）。

为什么需要它
    已有两个扫描器都覆盖不到：
      · `_scan_text_rows.py`  —— 只扫 0.76–0.96H（底部字幕带）
      · `_scan_watermark.py`  —— 全画面但阈值偏重在道具表面
    而**高铁车厢 LED 信息屏**在画面 0.04–0.14H、是**红绿高饱和发光点阵**，
    与"深色小笔画"的判据方向相反（它是**亮**的）。镜 104 实测确有假字。
    ⇒ 本扫描器专扫**上半画面（0–0.40H）**的**高饱和发光小字块**。

判据
    1. 上半画面；
    2. HSV 饱和度 > 90 且 明度 > 110（发光点阵）；
    3. 形态学闭运算成块，块宽 0.03–0.45W、高 0.015–0.10H（一条屏）；
    4. 块内连通块数 >= 5（多个字/字缝）；
    5. 输出裁剪块供读图 —— **必须读图确认**（车窗反光也会高饱和）。

用法：
    py -3.10 OUTPUT/_scan_skytext.py --shots=74-108 --dump
输出：OUTPUT/_sky_result.tsv + OUTPUT/_sky_crops/
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
DIRS = ["01_paper_plane", "03_classroom_day", "05_classroom_night",
        "06_trench", "07_rice_field", "08_train_dining", "02_campus"]
CROPS = os.path.join(HERE, "_sky_crops")
TSV = os.path.join(HERE, "_sky_result.tsv")
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


def blobs(mask, min_px=8):
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    out = []
    for sy, sx in np.argwhere(mask):
        if seen[sy, sx]:
            continue
        stack = [(int(sy), int(sx))]
        seen[sy, sx] = True
        n = 0
        x0 = x1 = int(sx)
        y0 = y1 = int(sy)
        while stack:
            y, x = stack.pop()
            n += 1
            x0, x1 = min(x0, x), max(x1, x)
            y0, y1 = min(y0, y), max(y1, y)
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        if n >= min_px:
            out.append((n, x0, y0, x1, y1))
    return out


def frames(src, n=6):
    d = dur(src)
    got = []
    for i in range(n):
        t = d * (i + 1) / (n + 1)
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", "%.3f" % t, "-i", src,
                            "-vframes", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
                           capture_output=True)
        if r.stdout:
            got.append((t, Image.open(io.BytesIO(r.stdout))))
    return got


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

    rows = ["file\tshot\tt\tx0\ty0\tx1\ty1\tnseg\tsat"]
    for n in shots:
        src = best.get(n)
        if not src:
            continue
        hits = 0
        for t, im in frames(src, 6):
            W, H = im.size
            top = im.crop((0, 0, W, int(H * 0.40)))
            hsv = np.asarray(top.convert("HSV"), dtype=np.int16)
            S, V = hsv[:, :, 1], hsv[:, :, 2]
            m = (S > 90) & (V > 110)
            if m.sum() < 60:
                continue
            dil = m.copy()
            for dx in (-4, -2, 2, 4):
                dil |= np.roll(m, dx, axis=1)
            for npx, x0, y0, x1, y1 in blobs(dil, min_px=30):
                bw, bh = x1 - x0 + 1, y1 - y0 + 1
                if not (W * 0.03 <= bw <= W * 0.45):
                    continue
                if not (H * 0.015 <= bh <= H * 0.10):
                    continue
                nseg = len(blobs(m[y0:y1 + 1, x0:x1 + 1], min_px=3))
                if nseg < 5:
                    continue
                sat = float(S[y0:y1 + 1, x0:x1 + 1][m[y0:y1 + 1, x0:x1 + 1]].mean()) if m[y0:y1+1, x0:x1+1].any() else 0
                rows.append("%s\t%d\t%.2f\t%d\t%d\t%d\t%d\t%d\t%.0f"
                            % (os.path.basename(src), n, t, x0, y0, x1, y1, nseg, sat))
                hits += 1
                if dump:
                    pad = 16
                    cx0, cy0 = max(0, x0 - pad), max(0, y0 - pad)
                    cx1, cy1 = min(W, x1 + pad), min(int(H * 0.4), y1 + pad)
                    sub = np.asarray(im)[cy0:cy1, cx0:cx1]
                    Image.fromarray(sub).resize(
                        (max(1, (cx1 - cx0) * 4), max(1, (cy1 - cy0) * 4)),
                        Image.LANCZOS).save(
                        os.path.join(CROPS, "s%03d_t%.2f.jpg" % (n, t)), quality=92)
        if hits:
            print("  镜 %-4d  %d 个天区文字候选" % (n, hits))
    with io.open(TSV, "w", encoding="utf-8") as f:
        f.write("\n".join(rows) + "\n")
    print("\n候选 %d 条 -> %s" % (len(rows) - 1, TSV))
    return 0


if __name__ == "__main__":
    sys.exit(main())
