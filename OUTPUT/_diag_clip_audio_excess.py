# -*- coding: utf-8 -*-
"""定性：v2 的音画漂移是「片段本身的问题（哪天生成的）」还是「脚本的问题」。

对章节表里实际用到的 126 个片段，逐个量：
    画面长度 D = 帧数 / 24
    音轨解码长度 A（= concat 会用它推进时间轴的那个长度）
    余量 = A − D   （正 ⇒ 该段把音频时间轴往后推）
并按 **文件 mtime（生成批次）** 分组统计。
"""
import glob
import json
import os
import re
import subprocess
import sys
from collections import defaultdict

for _s in ("stdout", "stderr"):
    try:
        getattr(sys, _s).reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")
CHAP = os.path.join(OUT, "_concat_chapters.txt")
SR = 32000
DIRS = ["01_paper_plane", "03_classroom_day", "06_trench",
        "07_rice_field", "08_train_dining", "05_classroom_night"]
RANGES = {
    "01_paper_plane": (1, 9), "03_classroom_day": (10, 18), "06_trench": (19, 46),
    "07_rice_field": (47, 74), "08_train_dining": (75, 105),
    "05_classroom_night": (106, 126),
}


def nframes(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-count_frames", "-show_entries", "stream=nb_read_frames",
                        "-of", "csv=p=0", p], capture_output=True, text=True)
    try:
        return int(r.stdout.strip())
    except ValueError:
        return 0


def alias(p):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-vn", "-ac", "1",
                        "-ar", str(SR), "-f", "s16le", "-"], capture_output=True)
    return len(r.stdout) / 2 / SR


def main():
    rows = []
    for line in open(CHAP, encoding="utf-8"):
        if line.startswith("#"):
            continue
        p = line.rstrip("\n").split("\t")
        if len(p) >= 5:
            rows.append((int(p[0]), p[4]))
    print("逐段量「音轨解码长度 − 画面长度」（共 %d 段）\n" % len(rows))

    by_day = defaultdict(list)
    out = []
    for shot, fname in rows:
        d = next(k for k, (lo, hi) in RANGES.items() if lo <= shot <= hi)
        path = os.path.join(OUT, d, "video", fname)
        if not os.path.exists(path):
            continue
        D = nframes(path) / 24.0
        A = alias(path)
        ex = (A - D) * 1000
        mt = os.path.getmtime(path)
        import time
        day = time.strftime("%Y-%m-%d", time.localtime(mt))
        by_day[day].append(ex)
        out.append((shot, ex, day, fname))
        print("  镜 %-4d 画面 %7.4fs 音轨 %7.4fs 余量 %+7.1f ms  %s  %s"
              % (shot, D, A, ex, day, fname[:34]))

    print("\n按生成日期分组：")
    tot = 0.0
    for day in sorted(by_day):
        v = by_day[day]
        s = sum(v)
        tot += s
        print("  %s  段数 %3d   平均余量 %+7.1f ms   合计 %+8.1f ms  (= 若按此拼接的累计漂移)"
              % (day, len(v), s / len(v), s))
    print("\n全部片段余量合计 = %+.1f ms  ← 应≈ v2 的 +2631 ms" % tot)

    print("\n余量为 0 的段（画面/音轨等长）：%d / %d"
          % (sum(1 for x in out if abs(x[1]) < 0.5), len(out)))
    print("余量 > 0 的段：%d ；余量 < 0 的段：%d"
          % (sum(1 for x in out if x[1] > 0.5), sum(1 for x in out if x[1] < -0.5)))


if __name__ == "__main__":
    main()
