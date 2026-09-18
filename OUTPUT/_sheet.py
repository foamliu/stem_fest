# -*- coding: utf-8 -*-
"""★ 逐镜读图工具：把成片按镜号抽帧，排成**联系表（contact sheet）**批量审图。

为什么必须这样做（README §6.4 读图铁律）
    程序化闸门只能给"候选"，**"画面对不对"只有看见才算数**。
    全片 126 镜，逐张打开要 126 次读图 —— 排成联系表后每次能看 12 格，
    既省往返，又能**横向对比同一场内的一致性**（校服/光影/人脸）。

用法：
    py -3.10 OUTPUT/_sheet.py                       # 1-126 全部，每 12 镜一张
    py -3.10 OUTPUT/_sheet.py --shots=1-60          # 只做前 60 镜
    py -3.10 OUTPUT/_sheet.py --shots=36,61,97      # 指定镜
    py -3.10 OUTPUT/_sheet.py --n=2                 # 每镜抽 2 帧（默认 1，取 40% 处）
    py -3.10 OUTPUT/_sheet.py --from=full           # 从成片抽（默认从**单镜文件**抽，更清晰）
输出：OUTPUT/_sheets/SHEET_<起>-<止>.jpg  与  _sheets/p<镜号>.jpg（单镜帧）
"""
from __future__ import annotations
import io
import os
import re
import subprocess
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "_sheets")
DIRS = ["01_paper_plane", "04_classroom_dusk", "06_trench",
        "07_rice_field", "08_train_dining", "05_classroom_night"]
PER = 3          # 每行格数
CELL = 620       # 单格宽
LABEL = 16
FULL = os.path.join(HERE, "full_cut.mp4")
CHAP = os.path.join(HERE, "_concat_chapters.txt")


def newest_by_shot():
    best = {}
    for d in DIRS:
        for f in os.listdir(os.path.join(HERE, d, "video")) if os.path.isdir(os.path.join(HERE, d, "video")) else []:
            if not f.endswith(".mp4") or f.startswith("_mid_"):
                continue
            m = re.match(r"(\d+)_", f)
            if not m:
                continue
            n = int(m.group(1))
            p = os.path.join(HERE, d, "video", f)
            if n not in best or os.path.getmtime(p) > os.path.getmtime(best[n]):
                best[n] = p
    return best


def chapters():
    out = {}
    for l in io.open(CHAP, encoding="utf-8"):
        p = l.split()
        if len(p) >= 5 and p[0].isdigit():
            out[int(p[0])] = (float(p[2]), float(p[3]))
    return out


def dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", p], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def parse(spec):
    out = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            out += list(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return out


def grab(src, t, dst):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "%.3f" % t, "-i", src,
                    "-vframes", "1", "-q:v", "2", dst], capture_output=True)
    return os.path.exists(dst)


def main():
    shots, nframe, src_mode = None, 1, "shot"
    for a in sys.argv[1:]:
        if a.startswith("--shots="):
            shots = parse(a.split("=", 1)[1])
        elif a.startswith("--n="):
            nframe = int(a.split("=", 1)[1])
        elif a.startswith("--from="):
            src_mode = a.split("=", 1)[1]
    if shots is None:
        shots = list(range(1, 127))

    os.makedirs(OUT, exist_ok=True)
    best = newest_by_shot()
    ch = chapters()

    imgs = []
    for n in shots:
        src = FULL if src_mode == "full" else best.get(n)
        if not src or not os.path.exists(src):
            print("  镜 %-4d 找不到源" % n)
            continue
        if src_mode == "full" and n in ch:
            t0, t1 = ch[n]
            span, base = t1 - t0, t0
        else:
            span, base = dur(src), 0.0
        for i in range(nframe):
            t = base + span * (i + 1) / (nframe + 1)
            dst = os.path.join(OUT, "p%03d_%d.jpg" % (n, i))
            if grab(src, t, dst):
                imgs.append((n, dst))

    if not imgs:
        print("没抽到帧")
        return 1

    # 分块出联系表
    idx = 0
    while idx < len(imgs):
        chunk = imgs[idx:idx + 12]
        idx += 12
        w, h = Image.open(chunk[0][1]).size
        cw = CELL
        chh = int(h * cw / w)
        nrow = (len(chunk) + PER - 1) // PER
        canvas = Image.new("RGB", (cw * PER, (chh + LABEL) * nrow), (8, 8, 10))
        dr = ImageDraw.Draw(canvas)
        for k, (nn, f) in enumerate(chunk):
            r_, c_ = k // PER, k % PER
            dr.text((c_ * cw + 6, r_ * (chh + LABEL) + 2), "SHOT %d" % nn, fill=(120, 235, 145))
            canvas.paste(Image.open(f).convert("RGB").resize((cw, chh), Image.LANCZOS),
                         (c_ * cw, r_ * (chh + LABEL) + LABEL))
        lo, hi = chunk[0][0], chunk[-1][0]
        dst = os.path.join(OUT, "SHEET_%03d-%03d.jpg" % (lo, hi))
        canvas.save(dst, quality=88)
        print("  %s   (%d 镜)" % (os.path.basename(dst), len(chunk)))
    print("\n联系表 -> %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
