# -*- coding: utf-8 -*-
"""按 `_scan_result.tsv` 的命中帧，裁出**字幕带**并放大，供人工读图复核。

★ 为什么必须裁带 + 放大
    `_scan_text_rows.py` 是筛查器，候选里混着"白校服高光"等误报（实测 7 候选里 5 个是误报）。
    复核时必须**只看字幕所在的那条横带**并放大 2× ——
    整帧缩略图里那点字根本看不清，容易被当成"没有字"。
    这是 §6.4「读图铁律」在字幕问题上的具体落实。

用法：
    py -3.10 OUTPUT/_scan_text_rows.py --every=0.35   # 先产出 _scan_result.tsv
    py -3.10 OUTPUT/_crop_candidates.py               # 再裁带
    # 然后逐个看 OUTPUT/_chk7/crop*.jpg 并更新 _textrows_verdict.py
"""
from __future__ import annotations
import csv
import glob
import io
import os
import re
import subprocess
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
TSV = os.path.join(HERE, "_scan_result.tsv")
DST = os.path.join(HERE, "_chk7")
DIRS = ["01_paper_plane", "04_classroom_dusk", "06_trench",
        "07_rice_field", "08_train_dining", "05_classroom_night"]


def newest_by_shot():
    best = {}
    for d in DIRS:
        for f in glob.glob(os.path.join(HERE, d, "video", "*.mp4")):
            b = os.path.basename(f)
            if b.startswith("_mid_"):
                continue
            m = re.match(r"(\d+)_", b)
            if not m:
                continue
            n = int(m.group(1))
            if n not in best or os.path.getmtime(f) > os.path.getmtime(best[n]):
                best[n] = f
    return best


def main():
    if not os.path.exists(TSV):
        print("先跑：py -3.10 OUTPUT/_scan_text_rows.py --every=0.35")
        return 1
    os.makedirs(DST, exist_ok=True)
    best = newest_by_shot()
    first = {}
    for row in csv.DictReader(io.open(TSV, encoding="utf-8"), delimiter="\t"):
        n = int(row["file"].split("_")[0])
        first.setdefault(n, (row["file"], float(row["t"]), int(row["y"]), int(row["hits"])))
    for n, (fn, t, y, hits) in sorted(first.items()):
        src = best.get(n)
        if not src:
            print("  镜 %-4d 找不到源文件" % n)
            continue
        raw = os.path.join(DST, "f%03d.jpg" % n)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "%.2f" % t, "-i", src,
                        "-vframes", "1", "-q:v", "2", raw], capture_output=True)
        if not os.path.exists(raw):
            print("  镜 %-4d 抽帧失败" % n)
            continue
        im = Image.open(raw)
        W, H = im.size
        band = im.crop((0, int(H * 0.76), W, int(H * 0.97)))
        band = band.resize((W, band.size[1] * 2), Image.LANCZOS)
        out = os.path.join(DST, "crop%03d.jpg" % n)
        band.save(out)
        print("  镜 %-4d 命中 %d 帧 · 取 t=%.2fs · 字幕带 -> %s" % (n, hits, t, os.path.basename(out)))
    print("\n请逐个读图复核，并把结论写进 OUTPUT/_textrows_verdict.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
