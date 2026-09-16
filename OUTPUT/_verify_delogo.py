# -*- coding: utf-8 -*-
"""批量核验：8 个泄漏镜 delogo 前后逐帧对比拼图（下部放大，判读用）。

★ 纪律：判读泄漏**必须放大下部 ≥640 宽单帧**（压缩拼图会误判）。

输出：OUTPUT/_delogo_check/S<镜>_before_after.jpg
      每镜上行 = 备份原片（应有字幕），下行 = 擦除后（应干净）。

用法：py -3.10 OUTPUT/_verify_delogo.py [--shots=14,21,...] [--n=6]
"""
import glob
import os
import subprocess
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEAKS = [14, 21, 36, 77, 85, 86, 88, 112]
WIDE = 660


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def dur(p):
    r = sh(["ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "csv=p=0", p])
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 3.0


def find(shot):
    """返回 (备份片, 当前片)。"""
    cur = []
    for pat in (
        os.path.join(ROOT, "OUTPUT", "**", "video", "*_%02d_*.mp4" % shot),
        os.path.join(ROOT, "OUTPUT", "**", "video", "%d_*.mp4" % shot),
    ):
        cur += [f for f in glob.glob(pat, recursive=True)
                if "_bak_" not in os.path.basename(f)
                and "_delogo.mp4" not in f]
    cur = sorted(set(cur), key=os.path.getmtime)
    if not cur:
        return None, None
    c = cur[-1]
    d = os.path.dirname(c)
    base = os.path.basename(c)
    bak = os.path.join(d, "_bak_" + base)
    return (bak if os.path.exists(bak) else None), c


def grab(src, t, dst):
    sh(["ffmpeg", "-y", "-v", "error", "-ss", "%.2f" % t, "-i", src,
        "-frames:v", "1", "-vf",
        "crop=iw:ih*0.36:0:ih*0.62,scale=%d:-1" % WIDE, dst])
    return os.path.exists(dst)


def main():
    shots, n = LEAKS, 6
    for a in sys.argv[1:]:
        if a.startswith("--shots="):
            shots = [int(v) for v in a.split("=", 1)[1].split(",") if v]
        elif a.startswith("--n="):
            n = int(a.split("=", 1)[1])
    out = os.path.join(ROOT, "OUTPUT", "_delogo_check")
    os.makedirs(out, exist_ok=True)
    print("%-6s %-16s %s" % ("镜", "备份片", "当前片"))
    print("-" * 78)
    for s in shots:
        bak, cur = find(s)
        print("%-6d %-16s %s" % (
            s, "有" if bak else "无(!)", os.path.basename(cur) if cur else "-"))
        if not cur:
            continue
        tiles = []
        for tag, p in (("BEFORE", bak), ("AFTER", cur)):
            if not p:
                continue
            d = dur(p)
            for i in range(n):
                f = os.path.join(out, "_%s_%03d_%d.jpg" % (tag, s, i))
                if grab(p, d * (i + 0.5) / n, f):
                    tiles.append((tag, i, f, d))
        if not tiles:
            continue
        w, h = Image.open(tiles[0][2]).size
        cols = n
        rows = 2 if tiles[0][0] == "BEFORE" else 1
        canvas = Image.new("RGB", (w * cols, (h + 20) * rows), (10, 10, 12))
        dr = ImageDraw.Draw(canvas)
        for tag, i, f, d in tiles:
            r = 0 if tag == "BEFORE" else 1
            colr = (255, 190, 80) if tag == "BEFORE" else (120, 230, 140)
            dr.text((i * w + 6, r * (h + 20) + 3),
                    "%s t=%.1fs" % (tag, d * (i + 0.5) / n), fill=colr)
            canvas.paste(Image.open(f).convert("RGB"), (i * w, r * (h + 20) + 20))
        dst = os.path.join(out, "S%03d_before_after.jpg" % s)
        canvas.save(dst, quality=90)
    print("-" * 78)
    print("→ %s\\S<镜>_before_after.jpg（上=BEFORE 下=AFTER）" % out)


if __name__ == "__main__":
    main()
