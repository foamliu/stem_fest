# -*- coding: utf-8 -*-
"""50 式冬装参考图 · **像素级水印/红标识清除**（2026-09-20，v2）。

v1 用"按比例裁"清不掉水印 —— 实测裁完 `cap_side` 仍有 **2.38% 高饱和红**，
因为红色电话号码与红/紫五角星压在**画面正中**。

v2 改为三步像素手术（纯 numpy/PIL，不外调模型）：
  ① `red_mask` 找高饱和红/粉/紫像素（含五角星与联系电话）；
  ② 形态学膨胀 + 连通域面积筛选 ⇒ 只保留"笔画状/星形"候选，
     避开帽子本身的暖色阴影（低饱和不入选）；
  ③ 掩膜区做**邻域中值/均值填充**（多次模糊外插），把红色换成周边布料色。
再对整图统计残留红占比，**残留 > 0.05% 判 FAIL 不许进拼版**。

用法：
    py -3.10 OUTPUT/_clean_ref50_v2.py
"""
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "OUTPUT", "uniform_50shi", "ref2")
DST = os.path.join(SRC, "clean2")

# 每张图的处理方式：
#   "red"   = 清红（水印 + 红五角星）
#   "crop"  = 只裁底部时间戳
#   "keep"  = 原样
PLAN = {
    "cap_side_laojunpin.jpg":     ("red", (0.00, 0.02, 1.00, 0.96)),
    "cap_side_laojunpin2.jpg":    ("red", (0.00, 0.02, 1.00, 0.96)),
    "cap_front_laojunpin.jpg":    ("red", (0.00, 0.02, 1.00, 0.96)),
    "cap_front_997788.jpg":       ("red", (0.00, 0.02, 1.00, 0.98)),
    "uniform_full_laojunpin.jpg": ("red", (0.00, 0.00, 1.00, 0.96)),
    "uniform_full_laojunpin2.jpg": ("red", (0.00, 0.00, 1.00, 0.96)),
    "wearer_qq.jpg":              ("keep", (0.06, 0.00, 1.00, 0.96)),
}

# 这些图**一律不进拼版**（红五角星帽徽 / 大面积红水印，清了也没细节）
BLACKLIST = {
    "uniform_set_repro.jpg": "带红五角星帽徽",
    "uniform_set_laojunpin.jpg": "腰部红水印带",
}


def red_mask(im, sat_min=0.42, val_min=40):
    """高饱和红/粉/紫掩膜（色相 <20° 或 >300°，含紫红五角星）。"""
    hsv = np.asarray(im.convert("HSV")).astype(np.float32)
    h, s, v = hsv[..., 0] * 360 / 255, hsv[..., 1] / 255, hsv[..., 2] / 255
    return (((h < 20) | (h > 300)) & (s > sat_min) & (v * 255 > val_min)) & (s > sat_min)


def dilate(m, k=3, iters=2):
    """正方形结构元膨胀（PIL MaxFilter，够用且快）。"""
    img = Image.fromarray((m * 255).astype(np.uint8))
    for _ in range(iters):
        img = img.filter(ImageFilter.MaxFilter(k))
    return np.asarray(img) > 127


def inpaint(a, m, rounds=8):
    """掩膜区填充：**由外向内一圈圈吃邻域已知像素的均值**。

    2026-09-20 修正（v2 首版越清越红的根因）：
      旧写法每轮用 `BoxBlur(6)` 全图模糊后取值 —— 模糊半径大于掩膜宽度时，
      **掩膜内部残留的红像素会被自己反复平均回来**，于是"清完更红"
      （实测 1.75% → 2.47%）。改为只取**掩膜外**已知像素的均值，
      掩膜区永不参与统计，才能真正把红抹掉。
    """
    out = a.astype(np.float32).copy()
    hole = m.copy()
    if not hole.any():
        return out
    for _ in range(rounds):
        if not hole.any():
            break
        # 只模糊"已知"像素：把洞填成 0 再模糊，最后按权重归一化
        known = (~hole).astype(np.float32)
        src = out * known[..., None]
        blur_src = np.asarray(
            Image.fromarray(np.clip(src, 0, 255).astype(np.uint8))
            .filter(ImageFilter.BoxBlur(5))
        ).astype(np.float32)
        blur_w = np.asarray(
            Image.fromarray((known * 255).astype(np.uint8))
            .filter(ImageFilter.BoxBlur(5))
        ).astype(np.float32) / 255.0
        fill = blur_src / np.maximum(blur_w[..., None], 1e-3)
        # 本轮只填"贴边一圈"，由外向内推进，避免一次吃太多邻居失真
        edge = hole & dilate(~hole, 3, 1)
        if not edge.any():
            edge = hole
        ok = edge & (blur_w > 0.02)
        out[ok] = fill[ok]
        hole = hole & ~ok
    if hole.any():                      # 兜底：极小块用全局已知均值
        out[hole] = out[~m].reshape(-1, 3).mean(axis=0)
    return out


def process(name, im, mode, box):
    W, H = im.size
    l, t, r, b = box
    im = im.crop((int(W * l), int(H * t), int(W * r), int(H * b)))
    if mode != "red":
        return im, 0.0, 0.0
    a = np.asarray(im)
    m = red_mask(im)
    before = 100.0 * m.sum() / m.size
    m = dilate(m, 3, 2)                       # 膨胀盖住红色描边
    a2 = inpaint(a, m)
    out = Image.fromarray(np.clip(a2, 0, 255).astype(np.uint8))
    after = 100.0 * red_mask(out).sum() / (out.width * out.height)
    return out, before, after


def main():
    os.makedirs(DST, exist_ok=True)
    n_fail = 0
    for name, (mode, box) in sorted(PLAN.items()):
        p = os.path.join(SRC, name)
        if not os.path.isfile(p):
            print("MISS  %s" % name)
            continue
        out, before, after = process(name, Image.open(p).convert("RGB"), mode, box)
        verdict = "OK" if after <= 0.05 else "FAIL"
        if verdict == "FAIL":
            n_fail += 1
        out.save(os.path.join(DST, name), quality=95)
        print("%-4s %-30s %-10s 红 %.4f%% -> %.4f%%"
              % (verdict, name, "%dx%d" % out.size, before, after))

    for name, why in BLACKLIST.items():
        print("SKIP %-30s %s" % (name, why))
    print("\n干净参考 -> %s   FAIL=%d" % (DST, n_fail))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
