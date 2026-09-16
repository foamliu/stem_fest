# -*- coding: utf-8 -*-
"""字幕框定位 v2：白字 + 描边特征，专抓硬字幕。

改进点（vs v1）：
  · 用「高亮白像素 + 邻近暗描边」做主特征（硬字幕 = 白字 + 黑描边）
  · 要求横条宽高比 ≥ 2.0（字幕是横排）
  · 只在下部 42% 搜索；取最靠下的候选（字幕贴底）
  · 支持 --box=N:x,y,w,h 手动覆盖（自动失败时）
  · 出核对图（红框）供人工确认

用法：
    py -3.10 OUTPUT/_locate_subs.py --shots=14,21,36
    py -3.10 OUTPUT/_locate_subs.py --all
    py -3.10 OUTPUT/_locate_subs.py --shots=85 --box=85:200,540,660,60
"""
import glob
import os
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEAKS = [14, 21, 36, 77, 85, 86, 88, 112]
NFR = 10
BAND_TOP = 0.58          # 下部 42%


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


def read_frames(path, n=NFR):
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


def sub_mask(fr, y0):
    """下部区域的「字幕候选」掩膜：亮白像素 + 邻近暗描边。"""
    band = fr[y0:, :]
    g = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
    bright = (g > 200).astype(np.uint8)
    dark = (g < 95).astype(np.uint8)
    dk = cv2.dilate(dark, np.ones((9, 9), np.uint8))
    cand = cv2.bitwise_and(bright, dk)
    cand = cv2.bitwise_or(cand, bright)
    return cv2.morphologyEx(cand, cv2.MORPH_CLOSE, np.ones((3, 17), np.uint8))


def locate(shot, manual=None):
    p = newest(shot)
    if not p:
        return None
    frs = read_frames(p)
    if len(frs) < 3:
        return None
    h, w = frs[0].shape[:2]
    if manual:
        return {"shot": shot, "src": p, "box": manual, "size": (w, h),
                "auto": False}

    y0 = int(h * BAND_TOP)
    masks = np.stack([sub_mask(f, y0) for f in frs], 0)
    stable = (masks.mean(0) >= 0.6).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(stable, 8)
    cands = []
    for i in range(1, n):
        x, y, ww, hh, area = stats[i]
        if area < 250 or ww < w * 0.05:
            continue
        if ww / max(1, hh) < 2.0:          # 字幕横排 → 扁
            continue
        if hh > h * 0.18:                  # 太高 → 不是字幕
            continue
        cands.append((area, x, y, ww, hh))
    if not cands:
        return {"shot": shot, "src": p, "box": None, "size": (w, h),
                "auto": True, "n_cands": 0}
    cands.sort(key=lambda c: (-(c[2] + c[4]), -c[0]))   # 最靠下 + 面积大
    area, x, y, ww, hh = cands[0]
    pad_x, pad_y = 10, 8
    X = max(0, x - pad_x)
    Y = max(0, y0 + y - pad_y)
    W = min(w - X, ww + 2 * pad_x)
    H = min(h - Y, hh + 2 * pad_y)
    return {"shot": shot, "src": p, "box": (X, Y, W, H), "size": (w, h),
            "auto": True, "n_cands": len(cands)}


def main():
    want = LEAKS
    manual = {}
    for a in sys.argv[1:]:
        if a.startswith("--shots="):
            want = [int(v) for v in a.split("=", 1)[1].split(",") if v]
        elif a.startswith("--box="):
            k, v = a.split("=", 1)[1].split(":", 1)
            manual[int(k)] = tuple(int(t) for t in v.split(","))
    out = os.path.join(ROOT, "OUTPUT", "_subbox")
    os.makedirs(out, exist_ok=True)
    print("%-6s %-24s %-8s %s" % ("镜", "框 (x,y,w,h)", "候选数", "来源"))
    print("-" * 76)
    for s in want:
        r = locate(s, manual.get(s))
        fn = os.path.basename(r["src"]) if r else "-"
        if not r or not r["box"]:
            print("%-6d %-24s %-8s %s" % (s, "(未检出)", "-", fn))
            continue
        X, Y, W, H = r["box"]
        print("%-6d (%4d,%4d,%4d,%4d) %-8s %s" % (
            s, X, Y, W, H, r.get("n_cands", "手动"), fn))
        img = read_frames(r["src"], 1)[0]
        cv2.rectangle(img, (X, Y), (X + W, Y + H), (0, 0, 255), 2)
        cv2.imwrite(os.path.join(out, "box_%03d.jpg" % s), img)
    print("-" * 76)
    print("核对图：%s\\box_<镜>.jpg" % out)


if __name__ == "__main__":
    main()
