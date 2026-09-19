# -*- coding: utf-8 -*-
"""把 `full_cut.mp4` 每镜的**右上角镜号**拼成紧凑联系表，供一次读图完成全片验收。

为什么这样做：
  · 读图通道对**大文件**不稳（`media omitted: invalid or exceeds size limit`），
    但对 5 KB / 300×80 的灰度小图稳定。
  · 逐镜点开 126 次成本太高 ⇒ 拼成 2 张图，一次看完。

产物：`OUTPUT/_burn_check/CORNERS_A.jpg`（镜 1-63）、`CORNERS_B.jpg`（镜 64-126）
      每格标「序号 + 期望镜号」，方便一眼扫出跳号/错号。
用法：py -3.10 OUTPUT/_sheet_corners.py
"""
import os
import re
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHAP = os.path.join(ROOT, "OUTPUT", "_concat_chapters.txt")
OUT = os.path.join(ROOT, "OUTPUT", "_burn_check")
FULL = os.path.join(ROOT, "OUTPUT", "full_cut.mp4")

W, H = 1056, 608
# 只取右上角文字带；宽 300 覆盖「SHOT NNN」全部笔画（实测 x≈752..1024）
CW, CH, CX, CY = 300, 80, W - 304, 0
# ★ 通道限制实测：单图 >~5 KB 就会被拒（media omitted: invalid or exceeds size limit）。
#   ⇒ 为「能读」优先：大幅缩小 + 灰度 + 低质量，单张压到 ~5 KB 量级。
OUT_W = 132
CELL_W, CELL_H = OUT_W, 36
LABEL_H = 12
COLS = 4
JPEG_Q = 38
PER_SHEET = 16          # 4 列 × 4 行 = 16 格/张 ⇒ ~2 KB，稳过通道

font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 8)


def build(shots, path):
    rows = (len(shots) + COLS - 1) // COLS
    sheet = Image.new("L", (COLS * CELL_W, rows * (CELL_H + LABEL_H)), 40)
    d = ImageDraw.Draw(sheet)
    for i, (n, t) in enumerate(shots):
        r, c = divmod(i, COLS)
        fp = os.path.join(TMP, "c%03d.png" % n)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "%.3f" % t,
                        "-i", FULL, "-frames:v", "1", "-vf",
                        "crop=%d:%d:%d:%d,scale=%d:-1" % (CW, CH, CX, CY, OUT_W),
                        fp], check=False)
        y = r * (CELL_H + LABEL_H)
        if os.path.exists(fp):
            sheet.paste(Image.open(fp).convert("L"), (c * CELL_W, y))
        d.rectangle([c * CELL_W, y, (c + 1) * CELL_W - 1, y + CELL_H - 1],
                    outline=90)
        d.text((c * CELL_W + 2, y + CELL_H + 1),
               "#%03d=SHOT %03d" % (n, n), fill=215, font=font)
    sheet.save(path, quality=JPEG_Q, optimize=True)
    return os.path.getsize(path)


rows = []
with open(CHAP, encoding="utf-8") as f:
    for ln in f:
        m = re.match(r"^(\d+)\t([\d.]+)\t([\d.]+)\t([\d.]+)\t", ln)
        if m:
            rows.append((int(m.group(1)), (float(m.group(3)) + float(m.group(4))) / 2))

TMP = tempfile.mkdtemp(prefix="corners_")
os.makedirs(OUT, exist_ok=True)

# 分块：每 32 镜一张（4 列 × 8 行），共 4 张 —— 单张体积稳在 ~120 KB
chunks = [rows[i:i + PER_SHEET] for i in range(0, len(rows), PER_SHEET)]
for k, ch in enumerate(chunks, 1):
    p = os.path.join(OUT, "CORNERS_%d.jpg" % k)
    lo, hi = ch[0][0], ch[-1][0]
    print("第 %d 张（镜 %d-%d）：%d 格  %.0f KB"
          % (k, lo, hi, len(ch), build(ch, p) / 1024.0))
    print("   %s" % p)
