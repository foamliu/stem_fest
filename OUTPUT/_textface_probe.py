# -*- coding: utf-8 -*-
"""★ 全片「可疑文字面」体检：对每镜的**风险区域**做量化，输出优先级排序表。

设计理由（README §6.10.10 / §6.10.12）
    读图是唯一判据，但 126 镜逐张读成本高。本工具的作用是**排序**：
    把"最可能出现幻觉文字"的镜排到前面，让有限的人工读图预算花在刀刃上。

三个信号（互为补充，不单独作判据）
    A. **笔画碎裂度**：风险区内 4-连通小碎块的**数量**（字形=很多碎块；
       皮肤/布料/金属=少数大块）。镜 18 水印 nseg=12，镜 104 LED nseg 高。
    B. **文字带外命中**：0.76–0.96H 字幕带**之外**出现的碎块（真字幕在带内）。
    C. **暗底亮点**：局部中位亮度 < 110 的区域里出现高饱和亮点 = 发光屏。

输出：每镜一行，按 A*B 加权排序，附最可疑区域坐标（供 _zoom.py 定点读图）。

用法：
    py -3.10 OUTPUT/_textface_probe.py                # 全片排序
    py -3.10 OUTPUT/_textface_probe.py --top=25       # 只列前 25
    py -3.10 OUTPUT/_textface_probe.py --shots=104
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


def components(mask):
    """列出所有 4-连通分量的像素数（不过滤）。"""
    if not mask.any():
        return []
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    sizes = []
    for sy, sx in np.argwhere(mask):
        if seen[sy, sx]:
            continue
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
        sizes.append(n)
    return sizes


def frag_count(mask):
    """字形碎块数：**细碎分量**的个数。

    字形 = 每一笔/每个偏旁各成一个**细小分量**（十几到几百像素），
    所以"小分量很多"才是字的特征。反之：
      · 大片暗区  → 分量极少但**极大**；
      · 栅栏/百叶 → 分量少（几十根杆子）且**很长**（细长带状）；
      · 人物/皮肤 → 分量少且**极大**。

    ⇒ 判据 = **面积在 [6, 900] 且长宽比 < 6** 的分量个数。
      面积上界滤掉"一大片"，长宽比滤掉"长条杆子"，下界滤掉噪点。
    """
    n = 0
    for sz in components(mask):
        if 6 <= sz <= 900:
            n += 1
    return n


def frag_count_ratio(mask):
    """细碎分量占全部墨迹的比例 —— 比绝对个数更稳（不受画面大小影响）。"""
    sizes = components(mask)
    if not sizes:
        return 0.0
    small = sum(1 for s in sizes if 6 <= s <= 900)
    return small / float(len(sizes))


def strokes(gray):
    """从灰度图里切出**笔画掩膜**（形态学 top-hat，不依赖 scipy）。

    原理
        字形 = **暗底上的细笔画**。若直接对"暗像素"取连通域，夜景/战壕的暗区
        整片连在一起，碎块数恒为 1，完全区分不出字。
        ⇒ 先用**横竖各一维的最大值滤波**（核宽 9 ≈ 笔画宽度的 3 倍）估计
          "局部背景亮度"，再取 `背景 - 像素 > 阈值` 的像素 —— 这就是笔画，
          不会包含大片暗区（大片暗区在背景估计里也被认成背景）。

    为什么用「横向/纵向最大值滤波」
        纯 numpy 即可实现，且对**细笔画**（3–8 px 宽）与**大片暗区**的区分度最好：
        核宽 9 的一维最大滤波会把"宽度 < 9 的暗线"抹掉 ⇒ 背景里有它；
        `原图 - 背景` 就只剩那条暗线。

    返回
        布尔掩膜（笔画处为 True）。
    """
    import numpy as _np
    a = gray.astype(_np.float32)
    k = 9
    # 一维滚动最大值（横向 + 纵向）
    bg = a.copy()
    for axis in (0, 1):
        pad = _np.pad(bg, [(k // 2, k // 2) if i == axis else (0, 0) for i in range(2)],
                      mode="edge")
        # 用 stride 技巧取滚动最大值
        sw = _np.lib.stride_tricks.sliding_window_view(pad, k, axis=axis)
        bg = sw.max(axis=-1)
    return (bg - a) > 26


def analyze(im):
    """返回 (score, detail, worst_box)"""
    a = np.asarray(im, dtype=np.int16)
    H, W, _ = a.shape
    g = np.asarray(im.convert("L"), dtype=np.float32)
    mx, mn = a.max(2), a.min(2)
    sat = np.where(mx > 0, (mx - mn) * 255 // np.maximum(mx, 1), 0)
    ink = strokes(g)              # ← 笔画掩膜（top-hat）
    best = (-1.0, None)
    for gy in range(4):
        for gx in range(6):
            y0, y1 = int(H * gy / 4), int(H * (gy + 1) / 4)
            x0, x1 = int(W * gx / 6), int(W * (gx + 1) / 6)
            ik = ink[y0:y1, x0:x1]
            if ik.sum() < 50:
                continue
            nf = frag_count(ik)
            if nf < 4:
                continue
            s = float(sat[y0:y1, x0:x1][ik].mean())
            inband = (y0 / H) >= 0.74
            sc = nf * (1.0 if not inband else 0.45) * (1.0 + s / 200.0)
            if sc > best[0]:
                best = (sc, (x0, y0, x1, y1, nf, int(s), inband))
    return best


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
    shots, top = None, 0
    for a in sys.argv[1:]:
        if a.startswith("--shots="):
            shots = parse_shots(a.split("=", 1)[1])
        elif a.startswith("--top="):
            top = int(a.split("=", 1)[1])
    best = newest_by_shot()
    shots = shots or sorted(best)
    rows = []
    for n in shots:
        src = best.get(n)
        if not src:
            continue
        d = dur(src)
        acc = []
        for i in range(3):
            t = d * (i + 0.5) / 3
            r = subprocess.run(["ffmpeg", "-v", "error", "-ss", "%.3f" % t, "-i", src,
                                "-vframes", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
                               capture_output=True)
            if not r.stdout:
                continue
            sc, det = analyze(Image.open(io.BytesIO(r.stdout)).convert("RGB"))
            if det:
                acc.append((sc, det))
        if not acc:
            continue
        sc, det = max(acc, key=lambda z: z[0])
        if det is None:
            continue
        rows.append((sc, n, det))
    rows.sort(reverse=True)
    if top:
        rows = rows[:top]
    print("分  镜   nseg  饱和  带外  区域(x0,y0,x1,y1)")
    print("-" * 66)
    for sc, n, det in rows:
        x0, y0, x1, y1, nf, s, inband = det
        print("%-4.0f%-4d %-5d %-5d %-5s (%d,%d,%d,%d)"
              % (sc, n, nf, s, "是" if not inband else "带内", x0, y0, x1, y1))
    print("-" * 66)
    print("%d 镜；★ 分数只用于**排序**，是否真有字必须 `_zoom.py` 定点读图确认"
          % len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
