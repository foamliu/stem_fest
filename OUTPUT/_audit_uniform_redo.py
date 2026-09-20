# -*- coding: utf-8 -*-
"""军装体检 —— 定妆照/改图产物的「红色标识」与「军装色相」量化判据。

★ 2026-09-20 重建（原同名脚本在隔离清理中一并删除）。
  用途（README §6.10.17 / §6.10.16）：R2V 是**参考图锁形**的，
  prompt 里写「没有领章/没有红帽徽」压不住参考图上画出来的红色
  ⇒ 修图后**必须以像素验收**，不能只看"感觉没了"。

判据（三条，全部基于 HSV / RGB 直接计算，不依赖任何外部模型）：
  ① `upper_red_ratio` —— 上半身高饱和红像素占比（%）
     · 帽徽 / 领章 / 肩章 / 臂章 的通用判据
     · 阈值：**< 0.05%** 视为干净；> 0.5% 视为有红色标识
     · 旧 `08_young_soldier` 实测 领口红 7.196% ⇒ 严重污染
  ② `collar_red_ratio` —— **领口带**（图高 40%–52%）的高饱和红占比（%）
     · 专抓**红领章**：把「嘴唇的红」排除在外（嘴唇在脸带 22%–40%）
     · 阈值：**< 0.05%**
  ③ `uniform_hue` / `uniform_sat` —— 军装区（暖度 R−B > 18 的像素）的
     色相中位数与饱和度中位数
     · 50 式冬装实测 色相 ≈ 38°（褪色土黄）、饱和 ≈ 30
     · 65 式鲜绿实测 色相 ≈ 78°（鲜绿）、饱和 ≈ 45+
     · 判据：色相落在 **25°–55°** 为土黄褪色系（合格）；
             落在 **60°–100°** 为鲜绿系（不合格）

用法：
    py -3.10 OUTPUT/_audit_uniform_redo.py <图片路径> [<图片路径> ...]
    py -3.10 OUTPUT/_audit_uniform_redo.py --glob "OUTPUT/uniform_50shi/*.png"

输出：逐图一行，`OK` / `WARN` / `FAIL` 三态；退出码 = FAIL 的图片数。
"""
import argparse
import glob as globmod
import os
import sys

import numpy as np
from PIL import Image

# 高饱和红判据
RED_HUE_LO = 20      # 色相 < 20° 或 > 340° 视为红区
RED_HUE_HI = 340
RED_SAT_MIN = 0.45   # HSV 饱和度下限（0-1），排除灰粉/肤色反光
RED_LUM_MIN = 40     # 亮度下限，排除暗部噪点

# 分区（按图高比例）
ZONE_CAP_TOP = 0.22
ZONE_FACE_TOP = 0.40
ZONE_COLLAR_TOP = 0.52
ZONE_UPPER_BOT = 0.55

# 军装区（暖度分割）
WARM_RB = 18
HUE_OK = (25.0, 55.0)    # 土黄/褪色橄榄 = 合格
HUE_BAD = (60.0, 100.0)  # 鲜绿 = 不合格

RATIO_CLEAN = 0.05
RATIO_DIRTY = 0.50


def hsv_arrays(im):
    """返回 (hue_deg, sat01, val01) —— 全部用 PIL 的 HSV 转换保证与肉眼一致。"""
    hsv = np.asarray(im.convert("HSV")).astype(np.float32)
    return hsv[..., 0] * 360.0 / 255.0, hsv[..., 1] / 255.0, hsv[..., 2] / 255.0


def red_mask(hue, sat, val):
    red = (hue < RED_HUE_LO) | (hue > RED_HUE_HI)
    return red & (sat > RED_SAT_MIN) & (val * 255.0 > RED_LUM_MIN)


def band_mask(shape, h0, h1):
    """按图高比例 [h0, h1) 生成行带布尔掩膜。"""
    m = np.zeros(shape, dtype=bool)
    H = shape[0]
    m[int(H * h0):int(H * h1)] = True
    return m


def rgb_hue(rgb):
    """RGB -> 色相（度），用于军装区色相统计。"""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx = rgb.max(axis=-1)
    mn = rgb.min(axis=-1)
    d = np.maximum(mx - mn, 1e-6)
    hue = np.where(mx == r, ((g - b) / d) % 6,
          np.where(mx == g, (b - r) / d + 2,
                            (r - g) / d + 4)) * 60.0
    return hue


def audit(path):
    """对单张图做三项体检，返回 dict。"""
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(np.float32)
    H, W, _ = a.shape

    hue, sat, val = hsv_arrays(im)
    rm = red_mask(hue, sat, val)

    up = band_mask(a.shape[:2], 0.0, ZONE_UPPER_BOT)
    collar = band_mask(a.shape[:2], ZONE_FACE_TOP, ZONE_COLLAR_TOP)
    face = band_mask(a.shape[:2], ZONE_CAP_TOP, ZONE_FACE_TOP)

    upper_red = 100.0 * (rm & up).sum() / max(up.sum(), 1)
    collar_red = 100.0 * (rm & collar).sum() / max(collar.sum(), 1)
    face_red = 100.0 * (rm & face).sum() / max(face.sum(), 1)

    # 军装区：上半身里 R−B > 18 的暖色像素（躲开冷调摄影棚灰背景）
    warm = up & ((a[..., 0] - a[..., 2]) > WARM_RB)
    n_warm = int(warm.sum())
    if n_warm > 500:
        px = a[warm]
        uh = rgb_hue(px)
        usat = 100.0 * (1.0 - px.min(axis=1) / np.maximum(px.max(axis=1), 1e-6))
        u_hue = float(np.median(uh))
        u_sat = float(np.median(usat))
    else:
        u_hue = u_sat = float("nan")

    # 判定
    problems = []
    if upper_red > RATIO_DIRTY:
        problems.append("upper红%.3f%%" % upper_red)
    if collar_red > RATIO_DIRTY:
        problems.append("领口红%.3f%%" % collar_red)
    if not np.isnan(u_hue) and HUE_BAD[0] <= u_hue <= HUE_BAD[1]:
        problems.append("鲜绿hue%.0f" % u_hue)

    if problems:
        verdict = "FAIL"
    elif (upper_red > RATIO_CLEAN or collar_red > RATIO_CLEAN
          or (not np.isnan(u_hue) and not (HUE_OK[0] <= u_hue <= HUE_OK[1]))):
        verdict = "WARN"
    else:
        verdict = "OK"

    return {
        "path": path, "size": im.size, "mean": float(a.mean()),
        "upper_red": upper_red, "collar_red": collar_red, "face_red": face_red,
        "u_hue": u_hue, "u_sat": u_sat, "warm_px": n_warm, "verdict": verdict,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--glob", dest="g")
    args = ap.parse_args()

    paths = list(args.paths)
    if args.g:
        paths += sorted(globmod.glob(args.g))
    if not paths:
        ap.error("至少给一张图，或用 --glob")

    n_fail = 0
    for p in paths:
        if not os.path.isfile(p):
            print("MISSING  %s" % p)
            continue
        r = audit(p)
        if r["verdict"] == "FAIL":
            n_fail += 1
        print("%-6s %s" % (r["verdict"], r["path"]))
        print("       %dx%d mean=%.1f | 上半身红 %.3f%% | 领口红 %.3f%% | 脸部红 %.3f%% "
              "| 军装 hue=%.1f sat=%.1f (n=%d)"
              % (r["size"][0], r["size"][1], r["mean"],
                 r["upper_red"], r["collar_red"], r["face_red"],
                 r["u_hue"], r["u_sat"], r["warm_px"]))
    print("\nFAIL=%d / %d" % (n_fail, len(paths)))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
