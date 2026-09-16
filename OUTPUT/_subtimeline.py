# -*- coding: utf-8 -*-
"""多时段条带拼图：检查字幕出现在哪些时段（逐帧位置是否固定）。

用途：delogo 的框必须覆盖「字幕出现的所有时段」的区域。
若各时段位置不同（如镜 85 可能换行/换位），需按时间段分别定框。

用法：py -3.10 OUTPUT/_subtimeline.py --shot=85 --n=8
"""
import glob
import os
import subprocess
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Y0_FRAC = 0.72          # 只看最底部 28%（字幕带）


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


def dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def main():
    shot = 85
    n = 8
    for a in sys.argv[1:]:
        if a.startswith("--shot="):
            shot = int(a.split("=", 1)[1])
        elif a.startswith("--n="):
            n = int(a.split("=", 1)[1])
    p = newest(shot)
    if not p:
        print("镜 %d 无视频" % shot)
        return 1
    d = dur(p)
    out = os.path.join(ROOT, "OUTPUT", "_subbox")
    os.makedirs(out, exist_ok=True)
    tiles = []
    for i in range(n):
        t = d * (i + 0.5) / n
        f = os.path.join(out, "_tl_%02d.jpg" % i)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "%.2f" % t,
                        "-i", p, "-frames:v", "1", "-vf",
                        "crop=iw:ih*(1-%f):0:ih*%f,scale=1056:-1"
                        % (Y0_FRAC, Y0_FRAC), f],
                       capture_output=True, text=True)
        if os.path.exists(f):
            tiles.append((t, f))
    if not tiles:
        print("抓帧失败")
        return 1
    w, h = Image.open(tiles[0][1]).size
    band = 24
    canvas = Image.new("RGB", (w, (h + band) * len(tiles)), (10, 10, 12))
    dr = ImageDraw.Draw(canvas)
    for k, (t, f) in enumerate(tiles):
        y = k * (h + band)
        dr.text((6, y + 5), "t=%.2fs" % t, fill=(255, 220, 100))
        canvas.paste(Image.open(f).convert("RGB"), (0, y + band))
    dst = os.path.join(out, "timeline_%03d.jpg" % shot)
    canvas.save(dst, quality=92)
    print("镜 %d  时长 %.2fs  → %s" % (shot, d, dst))
    print("（每行 = 一个时间点的底部 %d%% 条带）" % int((1 - Y0_FRAC) * 100))
    return 0


if __name__ == "__main__":
    sys.exit(main())
