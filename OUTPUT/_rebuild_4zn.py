# -*- coding: utf-8 -*-
"""重拼 `four_students_zhong_nanshan`：用**你现用的写实四人合影**裁出四小强，
再与新写实钟南山并排拼版。

为什么要这样拼（而不是用 crop 目录的单人图）：
  · `four_students_hero_v02.png` 是你提供的**宽幅**真人合影，四人比例/光线/背景天然一致
  · 用 crop 目录的单人图会得到竖版人像，拼出来比例和这张宽幅不一致
  · 旧 `four_students_zhong_nanshan` 里的钟南山是**插画风带蓝底 + 姓名标签 + 豆包水印**，
    且四小强与现用版不是同一批照片 ⇒ 整张弃用

输出：`ASSETS/CHARACTERS/_group/four_students_zhong_nanshan_hero_v01.png`
"""
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GROUP = os.path.join(ROOT, "ASSETS", "CHARACTERS", "_group")
SRC4 = os.path.join(GROUP, "four_students_hero_v02.png")
ZN = os.path.join(ROOT, "ASSETS", "CHARACTERS", "07_zhong_nanshan",
                  "zhong_nanshan_hero_v01.png")
DST = os.path.join(GROUP, "four_students_zhong_nanshan_hero_v01.png")

# 目标人像高度：与 four_students 的主体高度对齐（原图人物约占 1062 高的 ~72%）
TARGET_H = 765

four = Image.open(SRC4).convert("RGBA")
# 四小强那张是"白底 + 四人"的宽幅；裁到人物下沿之上，保持画面干净
four = four.crop((0, 0, four.width, int(four.height * 0.92)))
four = four.resize((int(four.width * TARGET_H / four.height), TARGET_H), Image.LANCZOS)

zn = Image.open(ZN).convert("RGBA")
zn = zn.resize((int(zn.width * TARGET_H / zn.height), TARGET_H), Image.LANCZOS)

GAP, MARGIN = 8, 24
W = four.width + GAP + zn.width + MARGIN * 2
H = TARGET_H + MARGIN * 2
canvas = Image.new("RGB", (W, H), (24, 26, 30))
canvas.paste(four, (MARGIN, MARGIN), four)
canvas.paste(zn, (MARGIN + four.width + GAP, MARGIN), zn)
canvas.save(DST, "PNG", optimize=True)

print("四人段 %dx%d（源 %s）" % (four.width, four.height, os.path.basename(SRC4)))
print("钟南山 %dx%d（源 %s）" % (zn.width, zn.height, os.path.basename(ZN)))
print("输出  %dx%d  %.2f MB" % (canvas.width, canvas.height,
                              os.path.getsize(DST) / 1024.0 / 1024.0))
