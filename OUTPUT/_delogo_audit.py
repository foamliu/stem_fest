# -*- coding: utf-8 -*-
"""擦除效果量化体检：比对「擦前（备份）vs 擦后」的字幕带高亮像素量。

原理：硬字幕 = 白字，底部条带的白像素量会显著高于无字幕的底噪。
擦除成功后该值应**大幅下降**（经验阈值：降到擦前的 55% 以下）。

用法：py -3.10 OUTPUT/_delogo_audit.py [--shots=21,36,...]
"""
import glob
import os
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEAKS = [14, 21, 36, 77, 85, 86, 88, 112]
NFR = 6
CROP = "crop=iw:140:0:ih-155"


def newest(shot):
    cand = []
    for pat in (
        os.path.join(ROOT, "OUTPUT", "**", "video", "*_%02d_*.mp4" % shot),
        os.path.join(ROOT, "OUTPUT", "**", "video", "%d_*.mp4" % shot),
    ):
        cand += [f for f in glob.glob(pat, recursive=True)
                 if "_bak_" not in os.path.basename(f)
                 and "_delogo" not in f and "_temporal" not in f]
    cand = sorted(set(cand), key=os.path.getmtime)
    return cand[-1] if cand else None


def brightness(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True)
    try:
        d = float(r.stdout.strip())
    except ValueError:
        d = 3.0
    tot = 0
    for i in range(NFR):
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss",
                            "%.2f" % (d * (i + 0.5) / NFR), "-i", p,
                            "-frames:v", "1", "-f", "rawvideo",
                            "-pix_fmt", "gray", "-vf", CROP, "-"],
                           capture_output=True)
        if r.stdout:
            tot += int((np.frombuffer(r.stdout, dtype=np.uint8) > 210).sum())
    return tot


def main():
    shots = LEAKS
    for a in sys.argv[1:]:
        if a.startswith("--shots="):
            shots = [int(v) for v in a.split("=", 1)[1].split(",") if v]
    print("%-6s %-10s %-10s %-8s %s" % ("镜", "擦前", "擦后", "保留率", "判定"))
    print("-" * 56)
    for s in shots:
        cur = newest(s)
        if not cur:
            print("%-6d (无片)" % s)
            continue
        bak = os.path.join(os.path.dirname(cur),
                           "_bak_" + os.path.basename(cur))
        if not os.path.exists(bak):
            print("%-6d (无备份)" % s)
            continue
        b, c = brightness(bak), brightness(cur)
        rate = c / b if b else 0
        print("%-6d %-10d %-10d %-8.0f%% %s" % (
            s, b, c, rate * 100,
            "OK" if rate < 0.55 else "!! 需复查"))
    print("-" * 56)
    print("保留率 < 55% 视为擦除成功；否则需改用 delogo 或重跑")


if __name__ == "__main__":
    main()
