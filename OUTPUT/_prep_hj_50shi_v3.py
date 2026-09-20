# -*- coding: utf-8 -*-
"""黄继光 50 式冬装 · 拼版 v3「**无缝融合**」（2026-09-20）。

★ 三轮实测的核心教训（必须记录）：
  只要拼版里存在**白色边框 / 标签 / 分隔灰缝**，模型就会把这些结构
  当成"要生成的目标版面"一起画出来：
    · v03 → 出图仍是三块拼版，人缩成小点；
    · v04 → 出了两个全身人 + 左侧棋盘格残块；
    · v05 → 整图崩成棋盘格；
    · cap01 → 帽子编辑**原地保留拼版**，红五星纹丝未动。
  ⇒ **不能再给模型任何"版面线索"。**

v3 做法：把参考图当作**背景参考**，用大面积羽化渐变融进人像两侧，
  全图**没有边框、没有标签、没有分隔线**，读起来就是"一张照片里
  左边是服装图鉴、中间是本人"。模型只看到一个连续画面，
  没有"多格版面"可复制，才可能输出单张照片。

产出：
  in/fused_full.png  —— [人物三视图] ←渐隐→ [50 式棉服实物] 的无缝长图
  in/fused_cap.png   —— [人物头肩]   ←渐隐→ [50 式棉帽实物]  的无缝长图
"""
import os

import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "OUTPUT", "uniform_50shi", "in")
CL = os.path.join(ROOT, "OUTPUT", "uniform_50shi", "ref2", "clean2")
NS = os.path.join(CL, "nostar")

BG = (236, 236, 234)
FEATHER = 0.16       # 渐隐带宽（占总宽比例）


def load(p):
    return Image.open(p).convert("RGB")


def cover(im, w, h):
    """等比缩放**填满** w×h（裁掉多余），不做留白 —— 避免出现空白块。"""
    s = max(w / im.width, h / im.height)
    r = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
    l = (r.width - w) // 2
    t = (r.height - h) // 2
    return r.crop((l, t, l + w, t + h))


def hstack_feathered(left, right, feather=FEATHER):
    """左右并排，接缝处用**余弦羽化**互相溶图（无硬边、无线条）。"""
    h = max(left.height, right.height)
    W = left.width + right.width
    canvas = Image.new("RGB", (W, h), BG)
    canvas.paste(left.resize((left.width, h), Image.LANCZOS), (0, 0))
    canvas.paste(right.resize((right.width, h), Image.LANCZOS), (left.width, 0))

    a = np.asarray(canvas).astype(np.float32)
    fw = max(8, int(W * feather))
    x0 = left.width - fw // 2
    x1 = left.width + fw // 2
    x0 = max(0, x0)
    x1 = min(W, max(x0 + 1, x1))
    # 接缝处：把左右两侧各自往中间做线性交叉淡化（视觉上像同一张照片）
    blend = np.zeros((h, W), dtype=np.float32)
    ramp = np.linspace(0.0, 1.0, x1 - x0, dtype=np.float32)
    blend[:, x0:x1] = ramp
    # 用水平方向的均值色做"雾化过渡"，彻底抹掉缝
    blur = np.asarray(
        Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
        .filter(ImageFilter.GaussianBlur(fw / 2.2))
    ).astype(np.float32)
    alpha = np.zeros((h, W, 1), dtype=np.float32)
    ramp = np.sin(np.linspace(0, np.pi, x1 - x0)).astype(np.float32) * 0.85
    alpha[:, x0:x1, 0] = ramp[None, :]
    a = a * (1 - alpha) + blur * alpha
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def main():
    hj = load(os.path.join(IN, "hj_crop.png"))
    head = load(os.path.join(IN, "hj_head.png"))

    # ── fused_full：人物(左) + 棉服(中) + 棉帽(右)，高度统一 ──
    H = 900
    man = cover(hj, int(H * hj.width / hj.height), H)
    coat = cover(load(os.path.join(CL, "uniform_full_laojunpin.jpg")), 430, H)
    cap = cover(load(os.path.join(NS, "cap_side_laojunpin.jpg")), 430, H)
    fused = hstack_feathered(hstack_feathered(man, cap), coat)
    p1 = os.path.join(IN, "fused_full.png")
    fused.save(p1)
    print("写成 %s  %dx%d" % (p1, fused.width, fused.height))

    # ── fused_cap：人物头肩(左) + 棉帽(右) ──
    H2 = 820
    hd = cover(head, int(H2 * head.width / head.height), H2)
    cp = cover(load(os.path.join(NS, "cap_front_laojunpin.jpg")), 520, H2)
    fused2 = hstack_feathered(hd, cp, feather=0.12)
    p2 = os.path.join(IN, "fused_cap.png")
    fused2.save(p2)
    print("写成 %s  %dx%d" % (p2, fused2.width, fused2.height))


if __name__ == "__main__":
    main()
