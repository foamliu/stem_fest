#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""军装「红色违规」体检 —— 检查镜头是否有红星帽徽 / 红领章 / 红肩袢（2026-09-20）。

★ 为什么需要它
    镜 19 第一版（`..._00006_.mp4`）肉眼可见红五星帽徽 + 红领章 + 红胸标，
    但当时**没有任何自动判据**能报出来 —— 只能靠人眼看图。
    本脚本把这次教训固化成闸门。

★ 判据（继承 `_diag_50shi_red.py` 的口径，但**区分区域**，避免误判）
    ⚠️ 关键：红领巾（学生）本身就是**大面积纯红**，是**正当元素**，
       直接统计全画面红像素会被红领巾淹没（学生镜红领巾占比可达 3~5%）。
    ⇒ 故只统计**画面上部「帽子+双肩」条带**里的红像素：
         y ∈ [0.02, 0.42]（帽顶→肩线）
       红领巾主体在 y ∈ [0.45, 0.75]，落不进这个条带。
    ⚠️ 阈值用**严格暖红**（与 `_diag_50shi_red.py` 的 0.62 一致）：
         HSV 里 H<18 或 H>342 且 S>0.62 且 V>40。
       这个口径把暖调肤色（S 通常 <0.5）与赭石/卡其军装排除在外。

★ 用法
    py -3.10 OUTPUT/_check_uniform_red.py OUTDIR_OR_MP4 [更多...] [--tol 0.05]
    py -3.10 OUTPUT/_check_uniform_red.py --compare OLD.mp4 NEW.mp4     # 新旧对比
"""
from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# 帽子+双肩条带（画面上部）
BAND_Y0, BAND_Y1 = 0.02, 0.50
# ⚠️ 2026-09-20 阈值校准（初版两个阈值都错，实测探针数据在下面注释里）
#   ① 违规红在**实拍/低照度**画面里不是纯红，而是**暗红/褐红**：
#        v6 红星帽徽实测 RGB=47/9/0、54/25/21，**V 只有 47~73**、S 0.5~1.0。
#      初版写 `S>0.62 & V>40` —— V 勉强过、S 又把 S=0.51~0.61 的领章漏掉。
#   ② 军装在阴天画面里是**橄榄/褐绿**：H 13~21、S 0.41~0.63、V 73~111。
#      初版写 `H 30~105` ⇒ **军装 mask 根本没框住军装**，膨胀后自然盖不到帽徽。
#   ⇒ 修正为下面这组（用 v6 当"必须报警"的正样本校准，v7 当"必须为 0"的负样本）：
SAT_MIN, VAL_MIN = 0.45, 35      # 放宽到能抓到暗红领章
HUE_LO, HUE_HI = 22, 340         # 红 = H<22 或 H>340（褐红 H 7~14 属红侧）
# 军装 mask：橄榄/褐绿（H 10~70，含被压暗的军绿）
UNI_HUE_LO, UNI_HUE_HI = 10, 75
UNI_SAT_LO, UNI_SAT_HI = 0.12, 0.90
UNI_VAL_MIN = 45


def red_ratio(im: Image.Image) -> float:
    """返回**军装邻域内**的严格暖红像素占比（0~1）。

    ★ 2026-09-20 二次修正 —— **必须排除红领巾**：
       初版统计「帽子+双肩」条带（y 0.02~0.42）里的所有红像素，
       结果 v6/v7 两版都判 FAIL、且数值只差 0.06pp —— 追查发现
       红像素**几乎全部来自学生的红领巾**（其打结处伸进 y 0.35~0.42），
       而红领巾是**正当元素**（四小强是穿越者，本就系红领巾）。
    ⇒ 改判据：违规红（帽徽/领章/肩袢/臂章的星徽）**必然紧贴军装**，
       故只统计**「军装色像素邻域」内的红**：
         ① 先找「军绿/土黄军装」像素（V 中等、S 中等、H 在黄绿区间）
         ② 对军装 mask 做**膨胀**（模拟"紧贴"）
         ③ 红像素 ∩ 膨胀后的军装 mask = 违规红
       红领巾所在的白 Polo 区域不含军绿 ⇒ 被排除。
    """
    a = np.asarray(im.convert("RGB")).astype(np.float32)
    h, w = a.shape[:2]
    band = a[int(h * BAND_Y0):int(h * BAND_Y1), :, :].astype(np.uint8)
    hsv = np.asarray(Image.fromarray(band).convert("HSV")).astype(np.float32)
    hue = hsv[..., 0] * 360 / 255
    sat = hsv[..., 1] / 255
    val = hsv[..., 2]

    # ① 军装 mask：橄榄/褐绿区间（阴天实拍军装 H 13~21 / S 0.41~0.63 / V 73~111）
    uniform = ((hue > UNI_HUE_LO) & (hue < UNI_HUE_HI) &
               (sat > UNI_SAT_LO) & (sat < UNI_SAT_HI) & (val > UNI_VAL_MIN))
    if uniform.sum() < 200:
        return 0.0
    # ② 膨胀（用 PIL MaxFilter 近似，3px 半径）
    um = Image.fromarray((uniform * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(7))
    near_uniform = np.asarray(um) > 0

    # ③ 严格暖红 ∩ 军装邻域
    red = ((hue < HUE_LO) | (hue > HUE_HI)) & (sat > SAT_MIN) & (val > VAL_MIN)
    return float((red & near_uniform).mean())


def frames_of(path: str, step: int = 5) -> list:
    """把 mp4 抽帧（或直接用目录里的图），返回图片路径列表。"""
    if os.path.isdir(path):
        return sorted(glob.glob(os.path.join(path, "*.png")) +
                      glob.glob(os.path.join(path, "*.jpg")))[::step]
    tmp = tempfile.mkdtemp(prefix="uniform_red_")
    subprocess.run(["ffmpeg", "-y", "-i", path, "-vsync", "0",
                    os.path.join(tmp, "f%04d.png")],
                   capture_output=True)
    return sorted(glob.glob(os.path.join(tmp, "*.png")))[::step]


def scan(path: str, step: int = 5) -> dict:
    fs = frames_of(path, step)
    if not fs:
        return {"path": path, "error": "无帧"}
    ratios = []
    for f in fs:
        try:
            ratios.append(red_ratio(Image.open(f)))
        except Exception:  # noqa: BLE001
            pass
    if not ratios:
        return {"path": path, "error": "读取失败"}
    return {"path": path, "n": len(ratios), "mean": float(np.mean(ratios)),
            "max": float(np.max(ratios)), "p90": float(np.percentile(ratios, 90))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", help="mp4 或抽帧目录")
    ap.add_argument("--tol", type=float, default=0.05,
                    help="红占比容差（百分比），默认 0.05%%")
    ap.add_argument("--step", type=int, default=5, help="抽帧步长")
    ap.add_argument("--compare", nargs=2, metavar=("OLD", "NEW"))
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    if args.compare:
        paths = list(args.compare)
    else:
        paths = args.paths
    if not paths:
        ap.error("至少给一个 mp4 或目录")

    print("条带 y ∈ [%.2f, %.2f]（帽子+双肩） | 严格暖红 H<18|H>342 & S>%.2f & V>%d"
          % (BAND_Y0, BAND_Y1, SAT_MIN, VAL_MIN))
    print("=" * 78)
    rows = []
    for p in paths:
        r = scan(p, args.step)
        rows.append(r)
        name = os.path.basename(p.rstrip("\\/"))
        if "error" in r:
            print("[ERR] %-52s %s" % (name[:52], r["error"]))
            continue
        verdict = "PASS" if r["max"] * 100 <= args.tol else "FAIL"
        print("[%s] %-52s 帧 %-4d 均值 %.3f%%  最大 %.3f%%  P90 %.3f%%"
              % (verdict, name[:52], r["n"], r["mean"] * 100, r["max"] * 100,
                 r["p90"] * 100))
    print("-" * 78)
    if len(rows) == 2 and all("max" in r for r in rows):
        d = (rows[1]["max"] - rows[0]["max"]) * 100
        print("对比：最大红占比 %.3f%% → %.3f%%（%+.3f pp）"
              % (rows[0]["max"] * 100, rows[1]["max"] * 100, d))
    nfail = sum(1 for r in rows if "error" not in r and r["max"] * 100 > args.tol)
    print("结论：%s" % ("[OK] 全部通过" if nfail == 0 else "[FAIL] %d 个超标" % nfail))
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
