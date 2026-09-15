# -*- coding: utf-8 -*-
"""精确定位每个泄漏镜的字幕框 —— 多时间点抽样 + 自动检测字幕行。

★ 为什么不能用一个统一框（2026-09-15 教训）
    `_delogo.py` 初版用 x=293 y=478 w=470 h=46 套全部 9 镜，核对图显示
    **只有镜 14 是准的**。原因：各镜**景别不同**（近景/中景/双人/群像），
    H3 放字幕的位置随构图浮动，且**同一镜不同时段的字幕位置也可能不同**。

★ 本脚本做法
    1. 每镜抽 8 个时间点（0.15–0.9 时长），每帧裁**下部 45%** 放大保存；
    2. 用 OpenCV 做**形态学检测**（白色/高对比度横排笔画）自动找候选行；
    3. 输出每镜的候选框 + 拼图供人眼最终确认。

用法
    py -3.10 OUTPUT/_locate_subs.py --all
    py -3.10 OUTPUT/_locate_subs.py --shots=77
"""
import os
import subprocess
import sys

try:
    import cv2
    import numpy as np
    HAVE_CV = True
except ImportError:
    HAVE_CV = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")
sys.path.insert(0, OUT)

from _delogo import SHOTS, newest, probe_size  # noqa: E402

FRACS = [0.12, 0.22, 0.32, 0.42, 0.52, 0.62, 0.72, 0.82]


def grab(src, t, dst):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "%.2f" % t, "-i", src,
                    "-frames:v", "1", dst], capture_output=True)
    return os.path.exists(dst)


def detect(img):
    """检测横排字幕笔画：白色高亮 + 横向连通 → 返回候选行 (y, h, x, w, score)。"""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # 字幕 = 亮字（近白）压在较暗背景上；用高阈值取笔画
    _, th = cv2.threshold(g, 200, 255, cv2.THRESH_BINARY)
    # 横向膨胀把字连成行（字幕字距小、行内方向水平）
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 3))
    m = cv2.morphologyEx(th, cv2.MORPH_CLOSE, k)
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    H, W = g.shape
    out = []
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        # 字幕特征：横向长条（宽 >> 高）、位于中下部、宽度占画面 15%–85%
        if h < 12 or h > 70:
            continue
        if w < W * 0.15 or w > W * 0.92:
            continue
        if w / float(h) < 3.5:
            continue
        if y < H * 0.45:
            continue
        # 该框内的“白像素密度”要够高（真笔画），排除亮背景
        roi = th[y:y + h, x:x + w]
        dens = roi.mean() / 255.0
        if dens < 0.10 or dens > 0.75:
            continue
        out.append((y, h, x, w, round(dens, 3)))
    out.sort(key=lambda r: -r[4])
    return out[:3]


def main():
    shots, allf = [], False
    for a in sys.argv[1:]:
        if a.startswith("--shots="):
            shots = [int(x) for x in a.split("=", 1)[1].split(",")]
        elif a == "--all":
            allf = True
    if allf:
        shots = sorted(SHOTS)
    if not shots:
        print("用法：--all 或 --shots=7,14")
        return 1
    if not HAVE_CV:
        print("[X] 需要 opencv-python：py -3.10 -m pip install opencv-python")
        return 1

    tmp = os.path.join(OUT, "_locate")
    os.makedirs(tmp, exist_ok=True)
    from PIL import Image, ImageDraw

    for n in shots:
        act, slug, _ = SHOTS[n]
        src = newest(act, slug)
        d = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration", "-of", "csv=p=0", src],
                           capture_output=True, text=True)
        dur = float(d.stdout.strip())
        W, H = probe_size(src)
        print("=" * 78)
        print("[镜 %-3d] %s  %dx%d  %.2fs" % (n, os.path.basename(src), W, H, dur))

        tiles, hits = [], []
        for fr in FRACS:
            t = dur * fr
            p = os.path.join(tmp, "_f%03d_%02d.png" % (n, int(fr * 100)))
            if not grab(src, t, p):
                continue
            img = cv2.imread(p)
            for cand in detect(img):
                hits.append((fr, cand))
                print("   %.0f%%(%.2fs)  候选 y=%-4d h=%-3d x=%-4d w=%-4d 密度=%.3f"
                      % (fr * 100, t, cand[0], cand[1], cand[2], cand[3], cand[4]))
            tiles.append((fr, t, Image.open(p).convert("RGB")))

        if not hits:
            print("   （无自动候选 —— 可能字幕为暗字/低对比，需人眼定框）")

        # 拼图：2 列 x 4 行，带红色候选框
        tw = 560
        th = int(H * tw / W) + 18
        canvas = Image.new("RGB", (tw * 2, th * 4), (12, 12, 14))
        dr = ImageDraw.Draw(canvas)
        for i, (fr, t, im) in enumerate(tiles[:8]):
            im = im.resize((tw, th - 18))
            x0, y0 = (i % 2) * tw, (i // 2) * th
            dr.text((x0 + 4, y0 + 2), "SHOT %d  %.0f%%  %.2fs" % (n, fr * 100, t),
                    fill=(255, 210, 120))
            # 画该帧的候选框
            for fr2, (y, h, x, w, dn) in hits:
                if abs(fr2 - fr) < 1e-6:
                    sx, sy = tw / float(W), (th - 18) / float(H)
                    dr.rectangle([x0 + x * sx, y0 + 18 + y * sy,
                                  x0 + (x + w) * sx, y0 + 18 + (y + h) * sy],
                                 outline=(255, 0, 0), width=2)
            canvas.paste(im, (x0, y0 + 18))
        pp = os.path.join(tmp, "loc_%03d.jpg" % n)
        canvas.save(pp, quality=86)
        print("   ↳ 拼图：%s" % os.path.relpath(pp, ROOT))

        # 汇总建议框（取所有候选的并集，向下取整）
        if hits:
            ys = [c[0] for _, c in hits]
            ye = [c[0] + c[1] for _, c in hits]
            xs = [c[2] for _, c in hits]
            xe = [c[2] + c[3] for _, c in hits]
            bx = max(0, min(xs) - 14)
            by = max(0, min(ys) - 12)
            bw = min(W - bx, max(xe) - min(xs) + 28)
            bh = min(H - by, max(ye) - min(ys) + 24)
            print("   ★ 建议框（覆盖全部时段）：x=%d y=%d w=%d h=%d" % (bx, by, bw, bh))
    return 0


if __name__ == "__main__":
    sys.exit(main())
