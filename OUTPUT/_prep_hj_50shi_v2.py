# -*- coding: utf-8 -*-
"""黄继光 50 式冬装改图 · 输入素材准备 v2（2026-09-20）。

v1 拼版的三个致命问题（v03 出图实测）：
  ① 参考图用的是**黑白战地照**（战士裹白伪装披风）⇒ 模型画成"白披风 + 大檐帽"；
  ② 定妆照是**胸像裁切**，模型把"胸像"当整图重绘 ⇒ 人物被缩成画面中央的小点；
  ③ 拼版里参考块比人像块好看，模型把参考图当主体 ⇒ 人像被当成"拼版的一部分"。

v2 对策：
  ① 参考图换成 `ref2/clean2/`（已像素级清掉红水印/红五角星，**彩色实物**）；
  ② 把人像块放大加白边，并在其周围留出**宽灰边**（暗示"这是主体"）；
  ③ 参考块只排 3 张、尺寸缩小，避免喧宾夺主；
  ④ prompt 里明确说"人像在图 1 左侧区块内"。

产出：
  in/hj_crop.png     —— 裁掉水印后的干净三视图
  in/plate_v2.png    —— 主拼版：[左侧·人物三视图] + [中·交角棉帽实物(前/侧)] + [右·志愿军棉服实物]
  in/plate_cap.png   —— 帽子细节板（人物头肩特写 + 2 张 50 式棉帽实物）
  in/hj_head.png     —— 人物头肩特写（独立的帽型编辑基底）

用法：
    py -3.10 OUTPUT/_prep_hj_50shi_v2.py
"""
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "ASSETS", "CHARACTERS", "05_huang_jiguang",
                   "huang_jiguang_closeup_v01.png")
CLEAN = os.path.join(ROOT, "OUTPUT", "uniform_50shi", "ref2", "clean2")
OUT = os.path.join(ROOT, "OUTPUT", "uniform_50shi", "in")

BG = (238, 238, 236)
GAP = 14
BORDER = 4


def load(p):
    return Image.open(p).convert("RGB")


def crop_watermark(im):
    """裁掉定妆照右侧约 12% 画幅（那里压着「豆包AI生成」水印）。"""
    w, h = im.size
    return im.crop((0, 0, int(w * 0.88), h))


def pad(im, ratio=0.06):
    """四周补白边 —— 让主体不贴边，避免模型把它当"可裁掉的部分"。"""
    w, h = im.size
    nw, nh = int(w * (1 + 2 * ratio)), int(h * (1 + 2 * ratio))
    canvas = Image.new("RGB", (nw, nh), BG)
    canvas.paste(im, ((nw - w) // 2, (nh - h) // 2))
    return canvas


def fit(im, bw, bh):
    """等比缩放进 bw×bh，用 BG 补满整块。"""
    s = min(bw / im.width, bh / im.height)
    nw, nh = max(1, int(im.width * s)), max(1, int(im.height * s))
    r = im.resize((nw, nh), Image.LANCZOS)
    cell = Image.new("RGB", (bw, bh), BG)
    cell.paste(r, ((bw - nw) // 2, (bh - nh) // 2))
    return cell


def tile(cell, label):
    """给单元加白边框 + 左上角序号标签，帮模型区分"这是第几块"。"""
    w, h = cell.size
    out = Image.new("RGB", (w + 2 * BORDER, h + 2 * BORDER), (255, 255, 255))
    out.paste(cell, (BORDER, BORDER))
    if label:
        d = ImageDraw.Draw(out)
        d.rectangle([6, 6, 6 + 26 * len(label), 34], fill=(255, 255, 255))
        d.text((12, 11), label, fill=(60, 60, 60))
    return out


def main():
    os.makedirs(OUT, exist_ok=True)

    hj_full = crop_watermark(load(SRC))
    p_crop = os.path.join(OUT, "hj_crop.png")
    hj_full.save(p_crop)
    print("写成 %s  %dx%d" % (p_crop, hj_full.width, hj_full.height))

    # 头肩特写（供"只修帽子"用）
    hh = int(hj_full.height * 0.72)
    head = hj_full.crop((0, 0, int(hj_full.width * 0.42), hh))
    p_head = os.path.join(OUT, "hj_head.png")
    head.save(p_head)
    print("写成 %s  %dx%d" % (p_head, head.width, head.height))

    # ── 主拼版 v2：人物块最大 + 3 张彩色实物参考（星徽已抹除） ──
    HJ_W, HJ_H = 900, 760
    RW, RH = 520, 760
    NS = os.path.join(CLEAN, "nostar")
    cells = [
        tile(fit(pad(hj_full), HJ_W, HJ_H), "1 MAN"),
        tile(fit(load(os.path.join(NS, "cap_front_laojunpin.jpg")), RW, RH), "2 CAP"),
        tile(fit(load(os.path.join(NS, "cap_side_laojunpin.jpg")), RW, RH), "3 CAP"),
        tile(fit(load(os.path.join(CLEAN, "uniform_full_laojunpin.jpg")), RW, RH), "4 COAT"),
    ]
    widths = [HJ_W + 2 * BORDER, RW + 2 * BORDER, RW + 2 * BORDER, RW + 2 * BORDER]
    H = max(c.height for c in cells)
    W = sum(widths) + GAP * (len(cells) + 1)
    plate = Image.new("RGB", (W, H + 2 * GAP), BG)
    x = GAP
    for c, w in zip(cells, widths):
        plate.paste(c, (x, GAP + (H - c.height) // 2))
        x += w + GAP
    p2 = os.path.join(OUT, "plate_v2.png")
    plate.save(p2)
    print("写成 %s  %dx%d" % (p2, plate.width, plate.height))

    # ── 帽子细节板 ──
    CW, CH = 620, 720
    cells2 = [
        tile(fit(pad(head, 0.05), CW, CH), "1 MAN"),
        tile(fit(load(os.path.join(NS, "cap_front_laojunpin.jpg")), CW, CH), "2 CAP"),
        tile(fit(load(os.path.join(NS, "cap_side_laojunpin.jpg")), CW, CH), "3 CAP"),
    ]
    H2 = max(c.height for c in cells2)
    W2 = sum(c.width for c in cells2) + GAP * (len(cells2) + 1)
    plate2 = Image.new("RGB", (W2, H2 + 2 * GAP), BG)
    x = GAP
    for c in cells2:
        plate2.paste(c, (x, GAP))
        x += c.width + GAP
    p3 = os.path.join(OUT, "plate_cap.png")
    plate2.save(p3)
    print("写成 %s  %dx%d" % (p3, plate2.width, plate2.height))


if __name__ == "__main__":
    main()
