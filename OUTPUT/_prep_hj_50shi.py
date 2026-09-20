# -*- coding: utf-8 -*-
"""黄继光 50 式冬装改图 · 输入素材准备（2026-09-20）。

背景：`image_edit_longcat` 是**单图输入**，模型只能靠文字想象军装
⇒ 前两轮改图都"关了帽徽又画出帽徽"。本脚本产出一张**参考拼版**
（左：黄继光三视图定妆照；右：50 式冬装实拍参考），由 `_run_hj_50shi.py`
喂给多图工作流，让模型**直接看到要复制的服装**。

产出：
  1. `OUTPUT/uniform_50shi/in/hj_crop.png`   —— 定妆照去掉最右侧带"豆包AI生成"
     水印的画幅后剩下的干净三视图（2048×1152 → 裁掉右 ~12%）。
  2. `OUTPUT/uniform_50shi/in/plate.png`     —— 合成参考板：左黄继光定妆照，
     右 2 张 50 式冬装实拍参考，每块带灰底与细白边分隔。模型一次看到
     "脸" 与 "要穿的服装"。
  3. `OUTPUT/uniform_50shi/in/plate_cap.png` —— 帽子细节专板（左：定妆照头肩，
     右：50 式栽绒帽实拍 ×2），用于第二轮"只修帽子"。

用法：
    py -3.10 OUTPUT/_prep_hj_50shi.py
"""
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "ASSETS", "CHARACTERS", "05_huang_jiguang",
                   "huang_jiguang_closeup_v01.png")
REF = os.path.join(ROOT, "OUTPUT", "uniform_50shi", "ref")
OUT = os.path.join(ROOT, "OUTPUT", "uniform_50shi", "in")

BG = (232, 232, 230)   # 浅灰底，与定妆照影棚背景接近
GAP = 12               # 板间距
BORDER = 3             # 每块白边


def load(path):
    return Image.open(path).convert("RGB")


def crop_watermark(im):
    """裁掉定妆照右侧约 12% 画幅（那里压着「豆包AI生成」水印）。"""
    w, h = im.size
    return im.crop((0, 0, int(w * 0.88), h))


def fit(im, box_w, box_h):
    """等比缩放到完全装进 box_w×box_h，再用 BG 底色补成整块。"""
    s = min(box_w / im.width, box_h / im.height)
    nw, nh = max(1, int(im.width * s)), max(1, int(im.height * s))
    im = im.resize((nw, nh), Image.LANCZOS)
    cell = Image.new("RGB", (box_w, box_h), BG)
    cell.paste(im, ((box_w - nw) // 2, (box_h - nh) // 2))
    return cell


def board(cells, cols, cell_w, cell_h):
    """把若干等大单元拼成 cols 列的板，块间留 GAP 灰缝 + 白边。"""
    rows = (len(cells) + cols - 1) // cols
    W = cols * cell_w + (cols + 1) * GAP
    H = rows * cell_h + (rows + 1) * GAP
    canvas = Image.new("RGB", (W, H), BG)
    for i, c in enumerate(cells):
        r, col = divmod(i, cols)
        x = GAP + col * (cell_w + GAP)
        y = GAP + r * (cell_h + GAP)
        canvas.paste(c, (x, y))
        # 白细边：把每个单元框出来，避免模型把两图当一张连续画面
        frame = Image.new("RGB", (cell_w + 2 * BORDER, cell_h + 2 * BORDER), (255, 255, 255))
        frame.paste(c, (BORDER, BORDER))
        canvas.paste(frame, (x - BORDER, y - BORDER))
    return canvas


def main():
    os.makedirs(OUT, exist_ok=True)

    hj = crop_watermark(load(SRC))
    p_hj = os.path.join(OUT, "hj_crop.png")
    hj.save(p_hj)
    print("写成 %s  %dx%d" % (p_hj, hj.width, hj.height))

    # ── 板 1：全身/服装参考板（定妆照 + 50 式实拍 ×2） ──
    CW, CH = 720, 760
    cells = [
        fit(hj, CW, CH),
        fit(load(os.path.join(REF, "mod1.jpg")), CW, CH),
        fit(load(os.path.join(REF, "mod2.jpg")), CW, CH),
    ]
    b = board(cells, 3, CW, CH)
    p1 = os.path.join(OUT, "plate.png")
    b.save(p1)
    print("写成 %s  %dx%d" % (p1, b.width, b.height))

    # ── 板 2：帽子细节板（定妆照头肩 + 50 式栽绒帽实拍 ×2） ──
    cw2, ch2 = 560, 760
    hh = int(hj.height * 0.62)
    head = hj.crop((0, 0, int(hj.width * 0.40), hh))
    cells2 = [
        fit(head, cw2, ch2),
        fit(load(os.path.join(REF, "cap50.jpg")), cw2, ch2),
        fit(load(os.path.join(REF, "us_cap.jpg")), cw2, ch2),
    ]
    b2 = board(cells2, 3, cw2, ch2)
    p2 = os.path.join(OUT, "plate_cap.png")
    b2.save(p2)
    print("写成 %s  %dx%d" % (p2, b2.width, b2.height))


if __name__ == "__main__":
    main()
