#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""50 式战士定妆照入库（2026-09-20）。

背景与决策链（★ 改前必读）
    `_extras/08_young_soldier` 与 `_extras/11_volunteer_soldiers` 的
    历史 `v01` 定妆照**在磁盘上从来不存在**（README §6.10.17 记录了
    「双红领章 7.196%」「红肩袢」等读数，但当前工作区里找不到对应文件）。
    因此本轮**从零重建**，不再受旧图污染。

★ 路线（这是本轮唯一走通的路线，别再退回拼版）
    ❌ 拼版图 → LongCat image edit：模型会**复刻拼版结构**
       （v03 三格、v04 双人+棋盘格、v05 整图崩坏、cap01 原地保留拼版）。
    ✅ **两张独立参考图 → minimax H3 R2V**：模型分别理解「服装从哪来、
       脸从哪来」，没有版面可抄 ⇒ 稳定输出单张全身正视图。

★ 本轮角色（全员成年，视觉年龄 18+）
    young_soldier  年轻战士  18-20 岁视觉，队列里最年轻
    volunteer_a    战友 A    二十七八岁，方脸硬汉
    volunteer_b    战友 B    三十出头，圆脸敦厚

  三者 + 黄继光都由 R2V `<Picture 1>` 锁「50 式冬装」
  （= `in/ref_trench.png`，用户提供的上甘岭实景截图，**无红五星**）。

用法
    py -3.10 OUTPUT/_import_50shi_extras.py --dry     # 只打印不落盘
    py -3.10 OUTPUT/_import_50shi_extras.py --apply   # 真正入库（带备份）
"""
from __future__ import annotations

import argparse
import glob
import os
import shutil

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "OUTPUT", "uniform_50shi")
EXTRAS = os.path.join(ROOT, "ASSETS", "CHARACTERS", "_extras")

# (帧目录 tag, 目标子目录, 目标文件名, 说明)
JOBS = [
    # ★ 2026-09-20 重抽定版：`ys_r1` 是「年轻脸 + 深绿 50 式冬装」两个条件
    #   同时成立的唯一一版。
    #   被淘汰的：`young_soldier_v03`（脸对但**棕色毛帽 + 卡其黄棉服** ——
    #   因为它的 <Picture 2> 那张 T2I 参考图本身穿卡其黄，H3 把服装也继承了）；
    #   `young_soldier_50shi_v01`（有小胡子，显老）；
    #   `young_soldier_50shi_v02`（年龄读数与 v01 无差，脸未变年轻）。
    ("ys_r1", "08_young_soldier",
     "young_soldier_50shi_hero_v01.png", "年轻战士（18-20 岁视觉）"),
    ("soldier_a_50shi_v01", "11_volunteer_soldiers",
     "volunteer_a_50shi_hero_v01.png", "战友 A"),
    ("soldier_b_50shi_v01", "11_volunteer_soldiers",
     "volunteer_b_50shi_hero_v01.png", "战友 B"),
    ("hj_r2v_fuse01", "05_huang_jiguang",
     "huang_jiguang_50shi_hero_v01.png", "黄继光 · 50 式冬装全身"),
]

# 裁切参数（视频 864x480，人物居中全身）
CROP = dict(left=0.24, right=0.76, top=0.00, bottom=1.00)
OUT_H = 960          # 裁后统一缩到该高度（README：脸高 ≥250px 口径尽量接近）


def pick_cleanest_frame(tag: str) -> str:
    """选「成片红布」像素最少的帧 —— 避开暖色最强的背光帧。"""
    import numpy as np

    fs = sorted(glob.glob(os.path.join(BASE, "frames_%s" % tag, "*.png")))
    if not fs:
        raise SystemExit("缺帧目录 frames_%s，先跑 ffmpeg 抽帧" % tag)
    best, best_n = fs[0], None
    for f in fs:
        a = np.asarray(Image.open(f).convert("HSV")).astype(np.float32)
        h, s, v = a[..., 0] * 360 / 255, a[..., 1] / 255, a[..., 2] / 255
        n = int((((h < 20) | (h > 300)) & (s > 0.62) & (v * 255 > 40)).sum())
        if best_n is None or n < best_n:
            best, best_n = f, n
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正落盘（默认 dry-run）")
    args = ap.parse_args()

    for tag, sub, name, desc in JOBS:
        src = pick_cleanest_frame(tag)
        im = Image.open(src).convert("RGB")
        w, h = im.size
        box = (int(w * CROP["left"]), int(h * CROP["top"]),
               int(w * CROP["right"]), int(h * CROP["bottom"]))
        crop = im.crop(box)
        nh = OUT_H
        nw = max(1, int(crop.width * nh / crop.height))
        out = crop.resize((nw, nh), Image.LANCZOS)

        dst_dir = os.path.join(EXTRAS, sub) if sub != "05_huang_jiguang" else \
            os.path.join(ROOT, "ASSETS", "CHARACTERS", "05_huang_jiguang")
        dst = os.path.join(dst_dir, name)
        print("%-14s %-26s ← %s" % (desc, os.path.relpath(dst, ROOT),
                                    os.path.relpath(src, ROOT)))
        print("   裁 %s → %dx%d" % (box, nw, nh))
        if args.apply:
            os.makedirs(dst_dir, exist_ok=True)
            if os.path.exists(dst):
                shutil.copy2(dst, dst + ".bak")
                print("   已备份 → %s.bak" % name)
            out.save(dst)
            print("   ✅ 已写入 %.1f KB" % (os.path.getsize(dst) / 1024))
        else:
            print("   （dry-run，未写入）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
