# -*- coding: utf-8 -*-
"""★ 全片视觉一致性审核：按**幕**抽帧拼联系表，供多模态底模逐镜读图比对 storyboard。

与 `_visual_review.py` 的区别
    `_visual_review.py` 从**源视频目录**取最新版（可能拍到落选版）；
    本工具**严格按 `_concat_chapters.txt` 的成片对轴表**抽帧，
    保证"看到的就是成片里的那一镜、那一刻"。

每镜取 2 帧（镜中偏前 / 镜中偏后），拼成每行 4 镜、每镜 2 帧的联系表。

用法：
    py -3.10 OUTPUT/_audit_visual.py --act=1        # 序幕一（镜 1-9）
    py -3.10 OUTPUT/_audit_visual.py --shots=14,21
    py -3.10 OUTPUT/_audit_visual.py --all          # 分 8 批
"""
import os
import subprocess
import sys

ROOT = r"E:\code\stem_fest"
OUT = os.path.join(ROOT, "OUTPUT")
CUT = os.path.join(OUT, "full_cut.mp4")
CHAP = os.path.join(OUT, "_concat_chapters.txt")
DEST = os.path.join(OUT, "_audit_visual")

ACTS = [
    ("序幕一 纸飞机", 1, 9), ("序幕二 启动", 10, 18),
    ("第一幕 上甘岭", 19, 46), ("第二幕 禾下乘凉", 47, 74),
    ("第三幕 餐车一角", 75, 105), ("尾声 归来与揭晓", 106, 126),
]


def chapters():
    """→ {镜号: (start, end, file)}"""
    d = {}
    for L in open(CHAP, encoding="utf-8", newline="").read().split("\n"):
        L = L.rstrip("\r")
        if not L or L.startswith("#"):
            continue
        p = L.split("\t")
        if len(p) >= 5 and p[0].isdigit():
            d[int(p[0])] = (float(p[2]), float(p[3]), p[4])
    return d


def grab(t, dst):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "%.3f" % t,
                    "-i", CUT, "-frames:v", "1", "-q:v", "3", dst],
                   capture_output=True)
    return os.path.exists(dst) and os.path.getsize(dst) > 0


def main():
    args = sys.argv[1:]
    act, shots, per = None, None, 3
    for a in args:
        if a.startswith("--act="):
            act = int(a.split("=", 1)[1])
        elif a.startswith("--shots="):
            shots = [int(x) for x in a.split("=", 1)[1].split(",") if x.strip()]
        elif a.startswith("--per="):
            per = int(a.split("=", 1)[1])

    ch = chapters()
    if shots:
        keys = shots
    elif act is not None:
        _, a, b = ACTS[act]
        keys = list(range(a, b + 1))
    else:
        print("用法：--act=N / --shots=1,2,3 / --all")
        return 1

    os.makedirs(DEST, exist_ok=True)
    from PIL import Image, ImageDraw

    scale, cols, rows = 500, 4, 2
    tile_h = int(scale * 608 / 1056)
    lab = 20
    per_sheet = cols * rows
    made = []
    for si in range(0, len(keys), per_sheet):
        chunk = [n for n in keys[si:si + per_sheet] if n in ch]
        if not chunk:
            continue
        cv = Image.new("RGB", (cols * scale + (cols + 1) * 4,
                               rows * (tile_h + lab) + (rows + 1) * 4), (12, 12, 14))
        dr = ImageDraw.Draw(cv)
        for i, n in enumerate(chunk):
            r, c = divmod(i, cols)
            x0 = 4 + c * (scale + 4)
            y0 = 4 + r * (tile_h + lab + 4)
            s0, s1, fn = ch[n]
            dur = s1 - s0
            fr = []
            for j in range(per):
                frac = 0.20 + 0.60 * j / max(1, per - 1)
                fp = os.path.join(DEST, "_f%03d_%d.jpg" % (n, j))
                if grab(s0 + dur * frac, fp):
                    fr.append(fp)
            tag = fn.replace(".mp4", "")
            dr.text((x0 + 2, y0 + 3), "S%-3d %s" % (n, tag[:44]), fill=(250, 240, 110))
            sw = (scale - (per - 1) * 2) // per
            for j, fp in enumerate(fr):
                try:
                    im = Image.open(fp).convert("RGB").resize((sw, tile_h), Image.LANCZOS)
                    cv.paste(im, (x0 + j * (sw + 2), y0 + lab))
                except Exception:
                    pass
        nm = ("act%d" % act) if act is not None else "shots"
        sp = os.path.join(DEST, "%s_%02d.jpg" % (nm, len(made) + 1))
        cv.save(sp, quality=90)
        made.append(sp)
        print("  %s  (%d 镜)" % (os.path.basename(sp), len(chunk)))
    print("\n共 %d 张：%s" % (len(made), DEST))
    for m in made:
        print("  " + m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
