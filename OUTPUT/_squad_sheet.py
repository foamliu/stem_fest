# -*- coding: utf-8 -*-
"""战友群像 · 抽帧拼版预览（2026-09-20）。

把 OUTPUT/uniform_50shi/frames_<tag>/ 里每条视频的**首帧/中帧/末帧**
排成一张对照表，方便一次读图比对：

    行 = 一条视频（一个角色）
    列 = 首帧 / 中帧 / 末帧

用法：
    python OUTPUT/_squad_sheet.py                      # 用默认 tag 列表
    python OUTPUT/_squad_sheet.py --tags=a,b --out=x.jpg
"""
import argparse
import glob
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "OUTPUT", "uniform_50shi")

DEFAULT_TAGS = [
    "hj_r2v_fuse01",
    "young_soldier_50shi_v01",
    "soldier_a_50shi_v01",
    "soldier_b_50shi_v01",
]


def row_frames(tag):
    fs = sorted(glob.glob(os.path.join(BASE, "frames_%s" % tag, "*.png")))
    if not fs:
        return None
    return [fs[0], fs[len(fs) // 2], fs[-1]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", default=",".join(DEFAULT_TAGS))
    ap.add_argument("--out", default=os.path.join(ROOT, "OUTPUT", "_tmp_squad.jpg"))
    ap.add_argument("--col-w", type=int, default=430)
    args = ap.parse_args()

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    rows = []
    for t in tags:
        fr = row_frames(t)
        if fr:
            rows.append((t, fr))

    if not rows:
        raise SystemExit("没有可用帧，先跑 ffmpeg 抽帧")

    W = args.col_w
    probe = Image.open(rows[0][1][0])
    H = int(probe.height * W / probe.width)
    sheet = Image.new("RGB", (W * 3, H * len(rows)), (18, 18, 18))
    for r, (t, fr) in enumerate(rows):
        for c, f in enumerate(fr):
            im = Image.open(f).convert("RGB").resize((W, H), Image.LANCZOS)
            sheet.paste(im, (c * W, r * H))
    sheet.save(args.out, quality=72)
    print("写成 %s  %dx%d  行=%s" % (args.out, sheet.width, sheet.height, [t for t, _ in rows]))


if __name__ == "__main__":
    main()
