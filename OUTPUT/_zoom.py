# -*- coding: utf-8 -*-
"""★ 定点放大工具：把成片/单镜里**指定区域**裁出来放大，用于读图核实小字。

为什么需要
    "到底有没有字"只有看见才算数，而小字在联系表里只有几十像素高、
    根本读不出来。本工具把**归一化坐标框**（相对画面宽高的比例）裁出来
    放大到可读尺寸，一次可裁多处，直接拼成一张读图板。

用法：
    # 单一区域
    py -3.10 OUTPUT/_zoom.py --shot=104 --t=3.0 --box=0.28,0.04,0.62,0.16
    # 同一镜多个区域（用 ; 分隔）
    py -3.10 OUTPUT/_zoom.py --shot=104 --t=3.0 --box=0.28,0.04,0.62,0.16;0.0,0.0,1.0,0.3
    # 从成片按绝对秒
    py -3.10 OUTPUT/_zoom.py --full --t=418.0 --box=0.3,0.05,0.6,0.15
    # 批量（每行 镜号 时间 box），拼一张板
    py -3.10 OUTPUT/_zoom.py --batch=OUTPUT/_zoomspec.txt

box = x0,y0,x1,y1（0-1 归一化，左上为原点）
输出：OUTPUT/_zoom/Z_<标记>.jpg  +  拼板 OUTPUT/_zoom/SHEET.jpg
"""
from __future__ import annotations
import io
import os
import re
import subprocess
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ZOOM = os.path.join(HERE, "_zoom")
FULL = os.path.join(HERE, "full_cut.mp4")
DIRS = ["01_paper_plane", "03_classroom_day", "05_classroom_night",
        "06_trench", "07_rice_field", "08_train_dining", "02_campus"]


def newest_by_shot():
    best = {}
    for d in DIRS:
        vd = os.path.join(HERE, d, "video")
        if not os.path.isdir(vd):
            continue
        for f in os.listdir(vd):
            if not f.endswith(".mp4") or f.startswith(("_mid_", "_bak_", "_v2bak_", "_rejected")):
                continue
            m = re.match(r"(\d+)_", f)
            if m:
                n = int(m.group(1))
                p = os.path.join(vd, f)
                if n not in best or os.path.getmtime(p) > os.path.getmtime(best[n]):
                    best[n] = p
    return best


def grab(src, t):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", "%.3f" % t, "-i", src,
                        "-vframes", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
                       capture_output=True)
    return Image.open(io.BytesIO(r.stdout)).convert("RGB") if r.stdout else None


def crop_zoom(im, box, out, scale=5):
    W, H = im.size
    x0, y0, x1, y1 = box
    c = im.crop((int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H)))
    cw, chh = c.size
    c = c.resize((max(1, cw * scale), max(1, chh * scale)), Image.LANCZOS)
    c.save(out, quality=94)
    return c


def get_arg(name, default=None):
    for a in sys.argv[1:]:
        if a.startswith("--%s=" % name):
            return a.split("=", 1)[1]
    return default


def main():
    os.makedirs(ZOOM, exist_ok=True)
    batch = get_arg("batch")
    jobs = []
    if batch:
        for l in io.open(batch, encoding="utf-8"):
            l = l.strip()
            if not l or l.startswith("#"):
                continue
            p = l.split()
            jobs.append((int(p[0]), float(p[1]), tuple(float(x) for x in p[2].split(","))))
    else:
        shot = get_arg("shot")
        t = float(get_arg("t", "2.0"))
        boxes = [tuple(float(x) for x in b.split(","))
                 for b in get_arg("box", "0.0,0.0,1.0,1.0").split(";")]
        if shot:
            jobs = [(int(shot), t, b) for b in boxes]
        else:
            jobs = [(0, t, b) for b in boxes]

    best = newest_by_shot()
    cells = []
    for n, t, box in jobs:
        src = FULL if n == 0 else best.get(n)
        if not src:
            print("  跳过 镜 %s（无源）" % n)
            continue
        im = grab(src, t)
        if im is None:
            continue
        name = ("FULL" if n == 0 else "s%03d" % n) + "_t%.2f_%s" % (t, ",".join("%.2f" % v for v in box))
        out = os.path.join(ZOOM, name.replace(",", "_") + ".jpg")
        c = crop_zoom(im, box, out)
        cells.append((name, c))
        print("  %s  -> %s  (%dx%d)" % (name, os.path.basename(out), *c.size))

    if len(cells) > 1:
        CW = 1100
        cells2 = []
        for name, c in cells:
            w, h = c.size
            chh = max(40, int(h * CW / w))
            cells2.append((name, c.resize((CW, min(chh, 340)), Image.LANCZOS)))
        chh = max(c[1].size[1] for c in cells2)
        cv = Image.new("RGB", (CW, (chh + 18) * len(cells2)), (10, 10, 12))
        dr = ImageDraw.Draw(cv)
        for k, (name, c) in enumerate(cells2):
            dr.text((6, k * (chh + 18) + 3), name, fill=(130, 235, 150))
            cv.paste(c, (0, k * (chh + 18) + 18))
        dst = os.path.join(ZOOM, "SHEET.jpg")
        cv.save(dst, quality=92)
        print("拼板 -> %s" % dst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
