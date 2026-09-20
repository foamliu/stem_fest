#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""替换拼版原料裁图：旧 55 式 → 新 50 式（2026-09-20）。

★ 为什么必须做（这是镜 23/34/35/36/39 出红领章/红肩袢的**真正根源**）
    `_make_group.py` 的拼版原料在 `OUTPUT/group_ref/crops/<角色名>.png`。
    2026-09-20 读图实测确认，其中 3 张是**旧 55 式**：
      · `小战士.png`   → **红五星帽徽 + 红领章 + 翻领**，且是**儿童**（约 8-10 岁）
      · `战士群演.png` → **红五星帽徽 + 红肩袢**（两人合影，55 式）
      · `黄继光.png`   → **红五星帽徽 + 大檐帽**（不是冬装栽绒棉帽）
    这三张被 `_make_group.py` 拼进合影 → 喂 R2V → 镜 23/34/35/36/39 全部带红。
    ★ **改下游不如改源头**（README §6.10.17 F3）—— 追到 crops/ 层才是对的。

★ 新原料来自哪
    2026-09-20 新生成的 50 式定妆照（`R2V` + 独立参考图路线，无红五星）：
      ASSETS/CHARACTERS/_extras/08_young_soldier/young_soldier_50shi_hero_v01.png
      ASSETS/CHARACTERS/_extras/11_volunteer_soldiers/volunteer_a_50shi_hero_v01.png
      ASSETS/CHARACTERS/_extras/11_volunteer_soldiers/volunteer_b_50shi_hero_v01.png
      ASSETS/CHARACTERS/05_huang_jiguang/huang_jiguang_50shi_hero_v01.png
    这些图是 898×960 的**全身正视图**，肩宽占比小 ⇒ 拼版后人物会偏小。
    故本脚本**裁到"头肩+半身"**再入库，与旧裁图的取景比例对齐。

★ 命名对应（crops 用中文名，`_make_group.py` 的 COMBOS 按中文名取图）
    「小战士」   → 年轻战士（成年！18-20 岁视觉）
    「战士群演」 → 战友 A（成年，方脸硬汉）
    「黄继光」   → 黄继光 50 式冬装版

★ 用法
    py -3.10 OUTPUT/_swap_group_crops.py            # dry-run
    py -3.10 OUTPUT/_swap_group_crops.py --apply    # 写入（旧的自动 .bak55 备份）
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

from PIL import Image
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CROPS = os.path.join(ROOT, "OUTPUT", "group_ref", "crops")
CH = os.path.join(ROOT, "ASSETS", "CHARACTERS")
EX = os.path.join(CH, "_extras")

# (目标裁图名, 源视频帧目录 tag, 说明)
# ★ 改为**从源视频的帧目录挑帧**（而不是用已裁好的定妆照）——
#   定妆照是「红最少」那一帧做的，可能落在暗帧上；从帧目录重挑可以同时保证
#   「红少 + 曝光正常」，且裁法可与定妆照一致。
JOBS = [
    ("小战士", "ys_r1", "年轻战士（成年 18-20 岁视觉）"),
    ("战士群演", "soldier_a_50shi_v01", "战友 A（成年）"),
    ("黄继光", "hj_r2v_fuse01", "黄继光 · 50 式冬装"),
]

VIDEO_FRAMES = os.path.join(ROOT, "OUTPUT", "uniform_50shi")


def _red_px(im: Image.Image) -> int:
    import numpy as np
    a = np.asarray(im.convert("HSV")).astype(np.float32)
    h, s, v = a[..., 0] * 360 / 255, a[..., 1] / 255, a[..., 2] / 255
    return int((((h < 20) | (h > 300)) & (s > 0.62) & (v * 255 > 40)).sum())


def pick_frame(tag: str) -> str:
    """选帧优先级：**亮度贴近全片中位** > 红像素少。

    ⚠️ 顺序很重要（2026-09-20 实测教训）：
       初版按「红最少」优先、亮度只作过滤器，结果 `ys_r1` 选了 f013
       （亮度 80.4 / 中位 87.8）—— 数值在容差内，**但视觉上仍明显偏暗**，
       因为"红最少"的帧恰好落在曝光偏低的段上。
       ⇒ 改为**亮度优先**：先按 |亮度−中位| 排序，取最接近的一批里红最少的。
    """
    import glob
    import numpy as np

    fs = sorted(glob.glob(os.path.join(VIDEO_FRAMES, "frames_%s" % tag, "*.png")))
    if not fs:
        raise SystemExit("缺帧目录 frames_%s" % tag)
    metas = []
    for f in fs:
        im = Image.open(f).convert("RGB")
        a = np.asarray(im).astype(np.float32)
        metas.append({"f": f, "red": _red_px(im), "luma": float(a.mean())})
    med = float(np.median([m["luma"] for m in metas]))
    # ① 先按「亮度贴近中位」取最接近的 1/3 帧
    metas.sort(key=lambda m: abs(m["luma"] - med))
    pool = metas[: max(3, len(metas) // 3)]
    # ② 再在池里挑红最少的
    best = min(pool, key=lambda m: m["red"])
    print("           选帧 %s  亮度 %.1f（全片中位 %.1f）红 %d px"
          % (os.path.basename(best["f"]), best["luma"], med, best["red"]))
    return best["f"]


TOP_KEEP = 0.62      # 保留上部比例（头顶→腰）
OUT_H = 1340         # 与旧裁图高度量级对齐（旧图 820~1566）

# ⚠️ 2026-09-20 修正 —— **取景必须与四小强对齐，否则拼版后战士显小**：
#   四小强的裁图（`刘思齐.png` 等）是「**头肩特写**」：脸几乎占满画框高度。
#   而战士源帧是「**全身正视图**」，若也取上部 62%（头顶→腰），
#   在同样 OUT_H 下人物占比就小得多 ⇒ 拼版实测战士明显比学生矮一截。
#   ⇒ 战士类改用 **HEAD_KEEP = 0.34**（头顶→胸/领口），与"头肩特写"对齐。
#   这是**逐角色**参数：学生类沿用 0.62，战士类用 0.34。
HEAD_KEEP = 0.34     # 战士类源帧的取景比例（头顶 → 胸/领口）

# ★ 2026-09-20 补丁：选帧不能只看「红最少」，还要看**曝光正常**。
#   实测教训：`ys_r1` 全片亮度从 **60.6 渐增到 98.7**（镜头缓拉 + 曝光上行），
#   只按「红像素最少」选会落到 f006 这类**早期暗帧** ⇒ 拼版后该角色明显偏暗、
#   与其他人物不在一个曝光上。故选帧改为**双条件**：
#     ① 红占比 < 阈值（干净）
#     ② 全图亮度落在「本片亮度中位数 ± 容差」内（曝光正常）
TARGET_LUMA_TOL = 8.0    # 允许偏离全片中位亮度的幅度

# 人物横向固定裁切比例（源帧 864×480，人物居中占宽约 34%）
PERSON_X0 = 0.30
PERSON_X1 = 0.70


def normalize_luma(im: Image.Image, target: float = 112.0) -> Image.Image:
    """把裁图的整体亮度归一化到 target（默认 112），保证拼版里各人曝光一致。

    ★ 为什么要这一步（2026-09-20）
      四个源视频的**基准曝光各不相同**（实测全片中位亮度）：
        ys_r1 87.8 / soldier_a 114.8 / soldier_b ~117 / hj_r2v 117.4
      `ys_r1` 明显偏暗 ⇒ 直接拼版会出现「一个人暗、三个人亮」。
      选帧只能选**相对该片**最亮的帧，解决不了**跨片**差异，
      所以必须再做一层数值归一化。用**线性增益**（不换伽马），
      保持对比关系、不引入色偏。
    """
    import numpy as np

    a = np.asarray(im).astype(np.float32)
    cur = float(a.mean())
    if cur <= 1.0:
        return im
    gain = target / cur
    gain = max(0.75, min(1.60, gain))      # 限幅，避免过曝/压死
    out = np.clip(a * gain, 0, 255).astype(np.uint8)
    return Image.fromarray(out)


def crop_half(src: str) -> Image.Image:
    """从横构图帧里裁出**人物区域**（头肩到腰）。

    ⚠️ 踩过两次坑，记录在此：
      ① 直接 crop((0,0,w,h*0.62)) → 3898×1340 **过宽**；
         因为源帧 864×480 横构图，人物只占中间约 1/3，两侧全是空背景。
      ② 改用「与四角背景色差异 > 45」自动找人物 bbox → **也失败**：
         源图是**深灰渐变背景**，渐变本身与角落色差异就超阈值，
         整图被判成"人物"（战士群演/黄继光实测 bbox x 占比 **100%**）。
    ⇒ 结论：**自动检测在渐变背景上不可靠**，改用**固定比例裁**。
       源帧构图是 R2V 的固定输出（全身正视图、人物居中、头顶贴边），
       实测人物约占画面宽 34%、居中对齐 ⇒ 取中央 40% 宽 + 上部 62% 高，
       这个比例对 ys_r1 / soldier_a / soldier_b / hj_r2v 四个源都成立。
    """
    im = Image.open(src).convert("RGB")
    w, h = im.size
    cx0 = int(w * PERSON_X0)
    cx1 = int(w * PERSON_X1)
    return im.crop((cx0, 0, cx1, int(h * HEAD_KEEP)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正写入（默认 dry-run）")
    ap.add_argument("--no-norm", action="store_true", help="跳过亮度归一化")
    args = ap.parse_args()

    for name, tag, desc in JOBS:
        src = pick_frame(tag)
        dst = os.path.join(CROPS, name + ".png")
        old = os.path.getsize(dst) if os.path.exists(dst) else 0
        im = crop_half(src)
        nh = OUT_H
        nw = int(im.width * nh / im.height)
        out = im.resize((nw, nh), Image.LANCZOS)
        prev = out
        if not args.no_norm:
            out = normalize_luma(out)
        print("%-10s %-22s ← %s" % (name, desc, os.path.relpath(src, ROOT)))
        print("           %s  %s → %dx%d"
              % (os.path.relpath(dst, ROOT), "旧 %d B" % old if old else "（不存在）",
                 nw, nh))
        if not args.no_norm:
            print("           亮度 %.1f → %.1f（归一化）"
                  % (float(np.asarray(prev).mean()), float(np.asarray(out).mean())))
        if args.apply:
            os.makedirs(CROPS, exist_ok=True)
            if os.path.exists(dst):
                shutil.copy2(dst, dst + ".bak55")
                print("           已备份 → %s.bak55" % name)
            out.save(dst)
            print("           ✅ 已写入 %.1f KB" % (os.path.getsize(dst) / 1024))
        else:
            print("           （dry-run）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
