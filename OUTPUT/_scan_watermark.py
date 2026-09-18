# -*- coding: utf-8 -*-
"""★ 扫「豆包AI生成」类**模型水印**（烧进画面的实体字，不在字幕带）。

为什么单独立一个扫描器
    字幕泄漏检测器（`_scan_text_rows.py`）只盯 0.76–0.96H 的**字幕带**，
    而模型水印可能出现在**画面任意位置**（镜 18 出现在投影仪机身、约 0.72H），
    且常常是**水平小块**，笔画少、nseg 低 —— 恰好被字幕检测器的连通块阈值滤掉。
    因此必须**独立全画面扫描**：找"横向排列的深色小笔画组"。

判据（与字幕检测器同源，但全画面 + 更宽松的 nseg）
    1. 灰度中位数作中性基准，找**比基准暗 20/255** 的像素；
    2. 横向滚动膨胀，把同一行的笔画连成块；
    3. 块内连通块数 nseg >= 6（水印通常 4-8 个字，比字幕行少）；
    4. 块的宽高比 >= 2.2（横向排布）且宽度 <= 0.45W（不是整条字幕）。

用法：
    py -3.10 OUTPUT/_scan_watermark.py --shots=1-126      # 全片
    py -3.10 OUTPUT/_scan_watermark.py --shots=18 --dump  # 裁出候选块待读图
输出：OUTPUT/_wm_result.tsv  + 可选 OUTPUT/_wm_crops/*.jpg
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
CROPS = os.path.join(HERE, "_wm_crops")
TSV = os.path.join(HERE, "_wm_result.tsv")
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
            if not m:
                continue
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


def blobs(mask, min_px=6):
    """4-连通标记 -> [(像素数, x0, y0, x1, y1)]。栈式，纯 numpy+python。"""
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


def frames(src, n=8):
    d = dur(src)
    got = []
    for i in range(n):
        t = d * (i + 1) / (n + 1)
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", "%.3f" % t, "-i", src,
                            "-vframes", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
                           capture_output=True)
        if r.stdout:
            got.append((t, Image.open(io.BytesIO(r.stdout)).convert("L")))
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


def scan_one(src, n, dump):
    """返回 (rows, best)：rows 为 TSV 行，best 为最强候选（用于打印与存档）。"""
    rows, best = [], None
    for t, im in frames(src, 8):
        a = np.asarray(im, dtype=np.float32)
        h, w = a.shape
        med = float(np.median(a))
        dark = a < (med - 20)
        dil = dark.copy()
        for dx in (-6, -3, 3, 6):
            dil |= np.roll(dark, dx, axis=1)
        for npx, x0, y0, x1, y1 in blobs(dil, min_px=25):
            bw, bh = x1 - x0 + 1, y1 - y0 + 1
            if bh < 8 or bh > h * 0.28:
                continue
            asp = bw / float(bh)
            if asp < 2.2 or bw > w * 0.45:
                continue
            sub = dark[y0:y1 + 1, x0:x1 + 1]
            nseg = len(blobs(sub, min_px=3))
            if nseg < 6:
                continue
            rows.append("%s\t%d\t%.2f\t%d\t%d\t%d\t%d\t%d\t%.2f"
                        % (os.path.basename(src), n, t, x0, y0, x1, y1, nseg, asp))
            if best is None or nseg > best[0]:
                best = (nseg, t, x0, y0, x1, y1, asp, npx)
            if dump:
                pad = 14
                cx0, cy0 = max(0, x0 - pad), max(0, y0 - pad)
                cx1, cy1 = min(w, x1 + pad), min(h, y1 + pad)
                sub2 = np.asarray(im)[cy0:cy1, cx0:cx1]
                Image.fromarray(sub2).resize(
                    (max(1, (cx1 - cx0) * 4), max(1, (cy1 - cy0) * 4)),
                    Image.LANCZOS).save(
                    os.path.join(CROPS, "s%03d_t%.2f.jpg" % (n, t)), quality=92)
    return rows, best


def main():
    shots, dump = None, False
    for a in sys.argv[1:]:
        if a.startswith("--shots="):
            shots = parse_shots(a.split("=", 1)[1])
        elif a == "--dump":
            dump = True
    best_map = newest_by_shot()
    shots = shots or sorted(best_map)
    if dump:
        os.makedirs(CROPS, exist_ok=True)

    allrows = ["file\tshot\tt\tx0\ty0\tx1\ty1\tnseg\taspect"]
    for n in shots:
        src = best_map.get(n)
        if not src:
            continue
        rows, best = scan_one(src, n, dump)
        allrows += rows
        if best:
            print("  镜 %-4d %2d帧  max nseg=%-3d  t=%.2fs  (%d,%d)-(%d,%d)  asp=%.2f"
                  % (n, len(rows), best[0], best[1], best[2], best[3], best[4], best[5], best[6]))
    with io.open(TSV, "w", encoding="utf-8") as f:
        f.write("\n".join(allrows) + "\n")
    print("\n候选 %d 条 -> %s" % (len(allrows) - 1, TSV))
    if dump:
        print("裁剪块 -> %s" % CROPS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
