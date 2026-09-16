# -*- coding: utf-8 -*-
"""字幕条带图：把每镜下部按网格铺开并标尺，供人工精确读框。

输出：OUTPUT/_subbox/strip_<镜>.jpg
  · 裁下部 45%（约 y=335..608）
  · 放大 2×，叠加 50px 网格 + 坐标数字
  · 一次看多个时间点（字幕位置逐帧固定，任一张足够）

用法：py -3.10 OUTPUT/_substrip.py --shots=14,21,36
"""
import glob
import os
import subprocess
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEAKS = [14, 21, 36, 77, 85, 86, 88, 112]
Y0_FRAC = 0.50          # 从半高处开始裁
SCALE = 2
GRID = 50


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


def grab(src, t, dst, y0frac=Y0_FRAC):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "%.2f" % t,
                    "-i", src, "-frames:v", "1", "-vf",
                    "crop=iw:ih*(1-%f):0:ih*%f" % (y0frac, y0frac), dst],
                   capture_output=True, text=True)
    return os.path.exists(dst)


def main():
    want = LEAKS
    for a in sys.argv[1:]:
        if a.startswith("--shots="):
            want = [int(v) for v in a.split("=", 1)[1].split(",") if v]
    out = os.path.join(ROOT, "OUTPUT", "_subbox")
    os.makedirs(out, exist_ok=True)
    for s in want:
        p = newest(s)
        if not p:
            print("镜 %d 无视频" % s)
            continue
        tmp = os.path.join(out, "_tmp.jpg")
        if not grab(p, 2.0, tmp):
            print("镜 %d 抓帧失败" % s)
            continue
        im = Image.open(tmp).convert("RGB")
        # 若时长 < 2s，退回 0.5s
        if im.width == 0:
            grab(p, 0.5, tmp)
            im = Image.open(tmp).convert("RGB")
        w, h = im.size
        im = im.resize((w * SCALE, h * SCALE), Image.LANCZOS)
        W, H = im.size
        d = ImageDraw.Draw(im)
        y0px = int(608 * Y0_FRAC)            # 全图坐标 y0
        for gx in range(0, 608 + 1, GRID):
            X = gx * SCALE
            if X < W:
                d.line([(X, 0), (X, H)], fill=(0, 255, 255), width=1)
                d.text((X + 3, 3), str(gx), fill=(0, 255, 255))
        for gy in range(y0px, 609, GRID):
            Y = (gy - y0px) * SCALE
            if Y < H:
                d.line([(0, Y), (W, Y)], fill=(255, 255, 0), width=1)
                d.text((3, Y + 3), "y=%d" % gy, fill=(255, 255, 0))
        dst = os.path.join(out, "strip_%03d.jpg" % s)
        im.save(dst, quality=92)
        print("镜 %-4d → %s  (原图 1056x608，裁自 y=%d，2× 放大，网格 %d)"
              % (s, dst, y0px, GRID))


if __name__ == "__main__":
    main()
