"""50 式军帽参考图 · **星徽彻底抹平**（2026-09-20）。

v2 的 `red_mask` 只清"高饱和红/紫"，实测 `cap_side_laojunpin` 的星徽
被清成**淡粉色五角星轮廓**（饱和度掉到 0.42 阈值以下就漏网了），
模型仍会照着描一个星 ⇒ 必须用"低饱和也入选"的星徽专用掩膜。

做法：先在**固定 ROI**（星徽所在区域，按图比例给出）里找
  "任一通道显著高于局部布料中位数"的像素（星徽无论红/粉/银都比土黄布亮），
膨胀后按边框填入布料色。ROI 之外一律不动，绝不上牙齿、不碰帽子轮廓。

用法：
    py -3.10 OUTPUT/_fix_cap_star.py
"""
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "OUTPUT", "uniform_50shi", "ref2", "clean2")

# 文件 -> 星徽 ROI（左, 上, 右, 下 比例）
# ★ v1 只盖星尖 ⇒ 留下"星形灰影"。实测星徽含**投影/褪色轮廓**，实际占位
#   比星形本身大一圈（约 0.13W × 0.10H），ROI 必须给足余量。
STAR_ROI = {
    "cap_side_laojunpin.jpg": (0.32, 0.19, 0.68, 0.53),
    "cap_front_laojunpin.jpg": (0.32, 0.19, 0.68, 0.53),
    "cap_front_997788.jpg": (0.26, 0.16, 0.74, 0.58),
}
# 这些图已彻底干净、无星徽（`cap_side_laojunpin2` 是纯侧后视）
SKIP = {"cap_side_laojunpin2.jpg", "uniform_full_laojunpin.jpg",
        "uniform_full_laojunpin2.jpg", "wearer_qq.jpg"}

OUT = os.path.join(IN, "nostar")


def dilate(m, k=3, iters=1):
    img = Image.fromarray((m * 255).astype(np.uint8))
    for _ in range(iters):
        img = img.filter(ImageFilter.MaxFilter(k))
    return np.asarray(img) > 127


def mean_fill(a, m):
    """掩膜区按**邻域已知像素均值**填充（逐行左右 + 逐列上下取最近已知）。"""
    out = a.astype(np.float32).copy()
    H, W, _ = out.shape
    ys, xs = np.nonzero(m)
    if len(ys) == 0:
        return out
    for y, x in zip(ys, xs):
        picks = []
        row = ~m[y]
        left = np.nonzero(row[:x])[0]
        right = np.nonzero(row[x + 1:])[0]
        if len(left):
            picks.append(out[y, left[-1]])
        if len(right):
            picks.append(out[y, x + 1 + right[0]])
        col = ~m[:, x]
        up = np.nonzero(col[:y])[0]
        dn = np.nonzero(col[y + 1:])[0]
        if len(up):
            picks.append(out[up[-1], x])
        if len(dn):
            picks.append(out[y + 1 + dn[0], x])
        if picks:
            out[y, x] = np.mean(picks, axis=0)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    n = 0
    for name in sorted(os.listdir(IN)):
        p = os.path.join(IN, name)
        if not os.path.isfile(p) or not name.lower().endswith(".jpg"):
            continue
        if name in SKIP:
            continue
        roi = STAR_ROI.get(name)
        im = Image.open(p).convert("RGB")
        if not roi:
            print("SKIP %s（未登记 ROI）" % name)
            im.save(os.path.join(OUT, name), quality=95)
            continue
        a = np.asarray(im)
        H, W, _ = a.shape
        l, t, r, b = [int(v * s) for v, s in zip(roi, (W, H, W, H))]
        sub = a[t:b, l:r].astype(np.float32)
        med = np.median(sub.reshape(-1, 3), axis=0)
        lum = sub.mean(axis=2)
        sat = sub.max(axis=2) - sub.min(axis=2)
        # ★ 判据放宽：星徽含褪色描边/投影，亮度略高于布面或略带彩度都算
        star = (lum > np.median(lum) + 8) | (sat > 22) | (sub[..., 0] > med[0] + 8)
        m = np.zeros((H, W), dtype=bool)
        m[t:b, l:r] = star
        # 膨胀到足以盖住描边与投影
        m = dilate(m, 3, 6)
        keep = np.zeros((H, W), dtype=bool)
        keep[max(0, t - 12):min(H, b + 12), max(0, l - 12):min(W, r + 12)] = True
        m &= keep
        out = mean_fill(a, m)
        # 再叠一次轻度中值滤波，让填充区与布面纹理过渡自然
        filled = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
        filled = filled.filter(ImageFilter.MedianFilter(5))
        res = np.array(filled, dtype=np.uint8)
        res[~m] = a[~m]                     # 掩膜外还原原图，绝不碰轮廓
        Image.fromarray(res).save(os.path.join(OUT, name), quality=95)
        print("OK   %-30s 抹星 %d px (%.3f%%)" % (name, m.sum(), 100 * m.sum() / m.size))
        n += 1
    print("\n产物 -> %s  （%d 张）" % (OUT, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
