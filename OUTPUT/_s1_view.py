# -*- coding: utf-8 -*-
"""镜 1 新版 vs 旧版 + 参考图：一张对照图，供基模直接读图判断（README §0）。

版式（2x2）：
   左上 = 参考图 school_gate_wide_v02.png（原图）
   右上 = 旧版生成帧（00001_，乱码版）
   左下 = 新版生成帧（00002_）@1.5s
   右下 = 新版生成帧（00002_）@2.8s
"""
import os
import subprocess

from PIL import Image

ROOT = r"E:\code\stem_fest"
VDIR = os.path.join(ROOT, "OUTPUT", "01_paper_plane", "video")
TMP = os.path.join(ROOT, "OUTPUT", "_s1view")
os.makedirs(TMP, exist_ok=True)
CW, CH = 780, 440


def grab(src, ss, name):
    p = os.path.join(TMP, name)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "%.2f" % ss,
                    "-i", src, "-frames:v", "1", p], capture_output=True)
    return p


def fit(im):
    im = im.convert("RGB")
    k = min(CW / im.width, CH / im.height)
    im = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))),
                   Image.LANCZOS)
    c = Image.new("RGB", (CW, CH), (0, 0, 0))
    c.paste(im, ((CW - im.width) // 2, (CH - im.height) // 2))
    return c


old = os.path.join(VDIR, "01_girl_mother_at_school_gate_00001_.mp4")
new = os.path.join(VDIR, "01_girl_mother_at_school_gate_00002_.mp4")

sheet = Image.new("RGB", (CW * 2 + 10, CH * 2 + 10), (255, 255, 255))
sheet.paste(fit(Image.open(os.path.join(ROOT, "ASSETS", "SCENES",
                                        "01_school_gate",
                                        "school_gate_wide_v02.png"))), (0, 0))
sheet.paste(fit(Image.open(grab(old, 2.8, "o.png"))), (CW + 10, 0))
sheet.paste(fit(Image.open(grab(new, 1.5, "n1.png"))), (0, CH + 10))
sheet.paste(fit(Image.open(grab(new, 2.8, "n2.png"))), (CW + 10, CH + 10))
p = os.path.join(ROOT, "OUTPUT", "_gate_cmp", "S1_NEW_vs_OLD.jpg")
os.makedirs(os.path.dirname(p), exist_ok=True)
sheet.save(p, quality=92)
print("-> %s  %dx%d" % (p, sheet.width, sheet.height))
print("  TL ref / TR OLD 00001_ / BL NEW 00002_@1.5s / BR NEW 00002_@2.8s")
