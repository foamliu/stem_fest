# -*- coding: utf-8 -*-
"""★ 成片终检：在 `full_cut.mp4` 里按章节对轴表的**绝对时间**抽帧，
核验 8 个泄漏镜在成品里是否干净。

为什么不能只看单镜文件：拼接顺序/时间轴若错位，单镜干净但成片仍可能串镜。

依据：`OUTPUT/_concat_chapters.txt`（镜号 → 起点/终点）。

用法：py -3.10 OUTPUT/_verify_fullcut.py [--shots=14,21,...] [--n=4]
"""
import os
import subprocess
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEAKS = [14, 21, 36, 77, 85, 86, 88, 112]
WIDE = 680
CROP = "crop=iw:110:0:ih-125"


def chapters():
    p = os.path.join(ROOT, "OUTPUT", "_concat_chapters.txt")
    out = {}
    for line in open(p, encoding="utf-8"):
        if line.startswith("#"):
            continue
        parts = line.rstrip("\n").split("\t")
        if len(parts) >= 3:
            try:
                out[int(parts[0])] = (float(parts[2]), float(parts[3]))
            except ValueError:
                pass
    return out


def grab(src, t, dst):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "%.2f" % t,
                    "-i", src, "-frames:v", "1", "-vf",
                    "%s,scale=%d:-1" % (CROP, WIDE), dst],
                   capture_output=True)
    return os.path.exists(dst)


def main():
    shots, n = LEAKS, 4
    for a in sys.argv[1:]:
        if a.startswith("--shots="):
            shots = [int(v) for v in a.split("=", 1)[1].split(",") if v]
        elif a.startswith("--n="):
            n = int(a.split("=", 1)[1])
    src = os.path.join(ROOT, "OUTPUT", "full_cut.mp4")
    if not os.path.exists(src):
        print("找不到 %s" % src)
        return 1
    ch = chapters()
    out = os.path.join(ROOT, "OUTPUT", "_fullcut_check")
    os.makedirs(out, exist_ok=True)

    rows = []
    for s in shots:
        if s not in ch:
            print("镜 %d 不在章节表" % s)
            continue
        t0, t1 = ch[s]
        for i in range(n):
            t = t0 + (t1 - t0) * (i + 1) / (n + 1)
            f = os.path.join(out, "s%03d_%d.jpg" % (s, i))
            if grab(src, t, f):
                rows.append((s, i, t, f))
    if not rows:
        print("抽帧失败")
        return 1
    w, h = Image.open(rows[0][3]).size
    per = n
    nrow = (len(rows) + per - 1) // per
    canvas = Image.new("RGB", (w * per, (h + 18) * nrow), (10, 10, 12))
    dr = ImageDraw.Draw(canvas)
    for k, (s, i, t, f) in enumerate(rows):
        r, c = k // per, k % per
        dr.text((c * w + 6, r * (h + 18) + 3), "镜 %d  t=%.2fs" % (s, t),
                fill=(120, 230, 140))
        canvas.paste(Image.open(f).convert("RGB"), (c * w, r * (h + 18) + 18))
    dst = os.path.join(out, "FULLCUT_8SHOTS.jpg")
    canvas.save(dst, quality=90)
    print("→ %s" % dst)
    print("（每格标注镜号与成片绝对时间；底部条带放大 %d 宽）" % WIDE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
