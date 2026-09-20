#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第一幕措辞：从「深秋有太阳」改为「风雪阴冷」（2026-09-20，幂等可重跑）。

★ 为什么改（史料为据，推翻 09-19 的旧稿）
    用户指出旧稿与史实不符，核实两条硬史料确认旧稿错：
      · 「爆尘、浓烟**遮天蔽日**，以至他走访过的许多老兵们都以为那一天是个**阴天**」（张嵩山）
        —— 中国网络电视台《上甘岭战役：世界现代战争史上坚守防御的典范》
      · 「即便在**零下二三十摄氏度**的冬天，战士们也不畏寒冷，凿筑着新的坑道与战壕」
        —— 新华网《揭秘上甘岭战役中坚不可摧的「地下长城」》2022-11-25
    ⇒ 战役 43 天跨 10-11 月，11 月的朝鲜已冰天雪地；坑道内积水/泥水亦有据。
    ⇒ 用户 2026-09-20 重生成 `trench_wide_v01~v04` 为**风雪阴冷版**（R-B −18~−20）。

★ 改什么
    `_diag_act1_trench.py` 里 24+ 处镜头的「深秋的战前交通壕」「深秋干冷」
    以及「枯黄发干/干硬黄褐/枝条光秃」这类**与风雪冷调冲突**的措辞。
    （`LIGHT` / `LIGHT_TONE` / `SCENE` 三个常量已在前一步手工改好，本脚本不动它们。）

★ 不动的
    `LIGHT` 常量本体、`SCENE` 常量、`GUARD_SOLDIER_WINTER` 服装护栏
    —— 前两者已单独修正；服装与本议题无关（50 式冬服在深秋/隆冬都成立）。

★ 用法
    py -3.10 OUTPUT/_fix_act1_winter_scene.py            # dry-run，只打印
    py -3.10 OUTPUT/_fix_act1_winter_scene.py --apply    # 真正写入（带 .winter.bak 备份）
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "OUTPUT", "_diag_act1_trench.py")

# (旧串, 新串, 说明)  —— 顺序有意义：长串必须先替换，否则短串会啃掉长串的一部分
RULES = [
    # ── 环境串：深秋 → 风雪初冬 ────────────────────────────────
    ("那条深秋的战前交通壕", "那条风雪阴冷的战前交通壕", "环境：季节口径"),
    ("深秋的战前交通壕", "风雪阴冷的战前交通壕", "环境：季节口径"),
    ("深秋干冷的战壕色调", "风雪阴冷的战壕色调", "转场：季节口径"),
    ("1952-10 朝鲜战场交通壕，深秋干冷", "1952-10~11 朝鲜战场交通壕，风雪阴冷", "文件头注释"),

    # ── 植被/地面：枯黄干硬 → 焦土薄雪泥水 ──────────────────────
    ("壕壁上的野草全部枯黄发干、枝条光秃、地面是干硬的黄褐色焦土",
     "壕壁上是原木与沙袋垛、地面是炮火翻搅过的焦土与薄雪、低处积着泥水",
     "镜 19：地面与工事"),
    ("土壁上只长着稀稀拉拉、枯黄发干的野草",
     "土壁上是原木加固的痕迹、堆叠的沙袋、地面浮土里落着一层薄雪",
     "镜 21：地面与工事"),
    ("壕壁上枯草发黄、枝条光秃", "壕壁上是原木与堆叠的沙袋、低处有积水", "环境：工事"),
    ("壕壁上枯草发黄", "壕壁上是原木与沙袋、低处有积水", "环境：工事"),
    ("土壁与枯黄发干的野草", "土壁与堆叠的沙袋、地面的薄雪", "环境：工事"),
    ("壕壁上只有枯黄发干的野草",
     "壕壁上是原木与沙袋、地面浮土里落着一层薄雪", "镜 41：地面与工事"),
    ("稀稀拉拉的野草", "低处积着泥水", "环境：植被→泥水"),
    ("那丛野菜叶片发干、边缘卷起、颜色暗绿发黄，是深秋霜冻前最后一点野菜",
     "那丛野菜叶片发干、边缘卷起、上面压着薄雪，是从焦土里冒出来的最后一点野菜",
     "镜 21：野菜（保留枯干质感，去掉\"深秋霜冻前\"）"),
    ("土壁、沙袋、弹坑、稀稀拉拉的野草", "土壁、沙袋、弹坑、低处的泥水洼", "镜 19：环境枚举"),
]

# 冲突词自检：改完后这些词**不应该**再出现在镜头措辞里
FORBIDDEN = ["白天有太阳", "暖金色", "暖调为主", "暖亮", "无积雪", "地面上没有积雪"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正写入（默认 dry-run）")
    args = ap.parse_args()

    if not os.path.exists(SRC):
        print("找不到 %s" % SRC)
        return 1
    text = open(SRC, encoding="utf-8").read()
    orig = text

    total = 0
    for old, new, why in RULES:
        n = text.count(old)
        if n:
            text = text.replace(old, new)
            total += n
            print("  %-38s ×%-3d  → %s" % (why, n, new[:34]))
        else:
            print("  %-38s ×0    （已改过或未出现）" % why)

    print("-" * 70)
    print("合计替换 %d 处" % total)

    # 冲突词自检
    left = [w for w in FORBIDDEN if w in text]
    if left:
        print("⚠️ 仍存在冲突词：%s" % left)
    else:
        print("✅ 无冲突词（白天有太阳/暖金色/暖调为主/暖亮/无积雪）")

    if total == 0:
        print("（无改动，幂等）")
        return 0

    if args.apply:
        bak = SRC + ".winter.bak"
        if not os.path.exists(bak):
            open(bak, "w", encoding="utf-8").write(orig)
            print("已备份 → %s" % os.path.basename(bak))
        open(SRC, "w", encoding="utf-8").write(text)
        print("✅ 已写入 %s" % os.path.basename(SRC))
    else:
        print("（dry-run，未写入；加 --apply 生效）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
