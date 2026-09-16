# -*- coding: utf-8 -*-
"""OpenCV 字幕检测：给每个泄漏镜自动定框（delogo 兜底用）。

原理：硬字幕 = 画面下部一横条内、高亮度/高饱和边缘、逐帧位置固定。
做法：每镜抽 N 帧 → 逐帧算 Sobel 边缘 → 求"帧间稳定"的边缘（字幕特征）
     → 取最大连通带 → 输出建议框 (x, y, w, h)。

用法：
    py -3.10 OUTPUT/_locate_subs.py --shots=14,21,36   # 指定镜
    py -3.10 OUTPUT/_locate_subs.py --all              # 全部泄漏镜
"""
import glob
import os
import subprocess
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEAKS = [14, 21, 36, 77, 85, 86, 88, 112]
NFR = 8            # 每镜抽帧数
BAND_TOP = 0.55    # 只在下部 45% 里找（字幕区）


def newest(shot):
    cand = []
    for pat in (
        os.path.join(ROOT, "OUTPUT", "**", "video", "*_%02d_*.mp4" % shot),
        os.path.join(ROOT, "OUTPUT", "**", "video", "%d_*.mp4" % shot),
    ):
        cand += [f for f in glob.glob(pat, recursive=True)
                 if "_bak_" not in os.path.basename(f)]
    cand = sorted(set(cand), key=os.path.getmtime)
    return cand[-1] if cand else None


def frames(path, n=NFR):
    cap = cv2.VideoCapture(path)
    tot = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    out = []
    for i in range(n):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(tot * (i + 0.5) / n))
        ok, fr = cap.read()
        if ok:
            out.append(fr)
    cap.release()
    return out


def locate(shot):
    p = newest(shot)
    if not p:
        return None
    frs = frames(p)
    if len(frs) < 3:
        return None
    h, w = frs[0].shape[:2]
    y0 = int(h * BAND_TOP)
    grays = [cv2.cvtColor(f[y0:, :], cv2.COLOR_BGR2GRAY) for f in frs]
    # 逐帧 Sobel 边缘 → 二值
    bins = []
    for g in grays:
        sx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
        sy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
        m = cv2.magnitude(sx, sy)
        bins.append((m > np.percentile(m, 96)).astype(np.uint8))
    stack = np.stack(bins, 0)
    # 帧间稳定：≥70% 的帧在此处有边缘
    stable = (stack.mean(0) >= 0.7).astype(np.uint8)
    stable = cv2.morphologyEx(stable, cv2.MORPH_CLOSE,
                              np.ones((5, 25), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(stable, 8)
    best = None
    for i in range(1, n):
        x, y, ww, hh, area = stats[i]
        if area < 300:
            continue
        if ww < w * 0.06:
            continue
        if best is None or area > best[4]:
            best = (x, y, ww, hh, area)
    if best is None:
        return None
    x, y, ww, hh, _ = best
    # 转回全图坐标 + 留边（字幕描边）
    pad_x, pad_y = 8, 6
    X = max(0, x - pad_x)
    Y = max(0, y0 + y - pad_y)
    W = min(w - X, ww + 2 * pad_x)
    H = min(h - Y, hh + 2 * pad_y)
    return {"shot": shot, "src": p, "box": (X, Y, W, H),
            "size": (w, h), "frames": len(frs)}


def main():
    want = LEAKS
    for a in sys.argv[1:]:
        if a.startswith("--shots="):
            want = [int(v) for v in a.split("=", 1)[1].split(",") if v]
    out = os.path.join(ROOT, "OUTPUT", "_subbox")
    os.makedirs(out, exist_ok=True)
    print("%-6s %-22s %s" % ("镜", "建议框 (x,y,w,h)", "来源"))
    print("-" * 70)
    for s in want:
        r = locate(s)
        if not r:
            print("%-6d (未检出)" % s)
            continue
        X, Y, W, H = r["box"]
        print("%-6d (%4d,%4d,%4d,%4d)  %s" % (
            s, X, Y, W, H, os.path.basename(r["src"])))
        # 出核对图：框出字幕
        p = r["src"]
        img = frames(p, 1)[0]
        cv2.rectangle(img, (X, Y), (X + W, Y + H), (0, 0, 255), 2)
        cv2.imwrite(os.path.join(out, "box_%03d.jpg" % s), img)
    print("-" * 70)
    print("核对图：%s\\box_<镜>.jpg" % out)


if __name__ == "__main__":
    main()
