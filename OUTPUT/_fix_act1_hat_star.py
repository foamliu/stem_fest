#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第一幕军装措辞：去掉「红星军帽」等 55 式特征（2026-09-20，幂等可重跑）。

★ 为什么改
    镜 19 重跑后读图实测：战士**仍有红五星帽徽 + 红领章 + 红胸标**。
    排查出**两个来源**，都在 prompt 文字里：
      ① 常量 `GUARD_SOLDIER_WINTER` 写着「帽徽是红色五角星」
         （上一轮为压「青天白日旗臂章」而加）→ 已手工改掉。
      ② **17 处镜头 prompt 里硬编码「戴红星军帽」/「军帽上的红色五角星帽徽」**
         → 本脚本负责清掉。
    ⚠️ 根因是**文字与参考图打架**（README §6.10.3 锚点冲突）：
       用户实景参考图（`ref_trench.png`）与新建定妆照里，栽绒棉帽**都是素帽无星**，
       而 prompt 反着写「红星」⇒ H3 按文字补出红星。
    ⚠️ 史实：1952 年志愿军**栽绒棉帽不佩戴星徽**；戴星的是大檐帽/解放帽等常服帽，
       与冬装棉帽不是一回事。

★ 改什么（全部为「正向可画的替代物」，不用否定式）
    · 「戴红星军帽的年轻战士」   → 「戴栽绒棉帽的年轻战士」
    · 「军帽上的红色五角星帽徽必须保留」 → 「帽子前脸是素净的同色棉布、无星徽」
    · 「军绿色立领军装」         → 「军绿色冬季棉装」（与 GUARD 的"棉装"口径统一）

★ 用法
    py -3.10 OUTPUT/_fix_act1_hat_star.py            # dry-run
    py -3.10 OUTPUT/_fix_act1_hat_star.py --apply    # 写入（带 .hatstar.bak 备份）
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "OUTPUT", "_diag_act1_trench.py")

# 顺序有意义：长串先替换
RULES = [
    # ── 帽徽：直接删掉"星"的表述 ─────────────────────────────
    ("（军绿色立领军装与军帽上的红色五角星帽徽必须保留，不可改成其他军装、不可摘下军帽）",
     "（军绿色冬季棉装与栽绒棉帽，帽子前脸是素净的同色棉布、没有星徽，不可改成其他军装、不可摘下棉帽）",
     "帽徽：删除红星要求"),
    ("穿军绿色立领军装戴红星军帽的年轻战士", "穿军绿色冬季棉装戴栽绒棉帽的年轻战士", "身份串"),
    ("穿军绿色立领军装、戴红星军帽的年轻战士", "穿军绿色冬季棉装、戴栽绒棉帽的年轻战士", "身份串"),
    ("穿军绿色立领军装、戴红星军帽的志愿军战士", "穿军绿色冬季棉装、戴栽绒棉帽的志愿军战士", "身份串"),
    ("穿军绿色立领军装、戴红星军帽", "穿军绿色冬季棉装、戴栽绒棉帽", "身份串"),
    ("戴红星军帽的年轻战士", "戴栽绒棉帽的年轻战士", "身份串"),
    ("戴红星军帽的志愿军战士", "戴栽绒棉帽的志愿军战士", "身份串"),
    ("戴红星军帽", "戴栽绒棉帽", "帽型"),
    # ── 军装：立领军装 → 冬季棉装（与 GUARD 口径统一）─────────
    ("穿军绿色立领军装的年轻战士", "穿军绿色冬季棉装的年轻战士", "军装型制"),
    ("穿军绿色立领军装的志愿军战士", "穿军绿色冬季棉装的志愿军战士", "军装型制"),
    ("穿军绿色立领军装", "穿军绿色冬季棉装", "军装型制"),
    ("与军绿色立领军装", "与军绿色冬季棉装", "军装型制"),
    # ── 第二轮补漏（第一轮跑完自检报出的 6 处残留）──────────────
    # 变体一：GUARD_HUANG 里的括号串（措辞与 GUARD_SOLDIER_WINTER 不同）
    ("（军绿色立领军装与军帽上的红色五角星帽徽必须保留，",
     "（军绿色冬季棉装与栽绒棉帽，帽子前脸是素净的同色棉布、没有星徽，",
     "GUARD_HUANG 帽徽"),
    # 变体二：带「穿着偏大的」定语 + 小战士（旧称呼残留）
    ("一位穿着偏大的军绿色立领军装的年轻小战士", "一位穿着偏大的军绿色冬季棉装的年轻战士",
     "小战士→年轻战士"),
    ("一位穿着偏大军绿色立领军装的年轻小战士", "一位穿着偏大军绿色冬季棉装的年轻战士",
     "小战士→年轻战士"),
    ("与一位穿着偏大军绿色立领军装的年轻小战士", "与一位穿着偏大军绿色冬季棉装的年轻战士",
     "小战士→年轻战士"),
    ("一位穿着偏大军绿色立领军装的年轻战士", "一位穿着偏大军绿色冬季棉装的年轻战士", "军装型制"),
]

# 改完后**不应**再出现在镜头措辞里的词
FORBIDDEN = ["红星军帽", "红色五角星帽徽", "戴红星", "立领军装"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    text = open(SRC, encoding="utf-8").read()
    orig = text
    total = 0
    for old, new, why in RULES:
        n = text.count(old)
        if n:
            text = text.replace(old, new)
            total += n
            print("  %-22s ×%-3d → %s" % (why, n, new[:40]))
        else:
            print("  %-22s ×0  （已改过或未出现）" % why)
    print("-" * 70)
    print("合计替换 %d 处" % total)

    # 自检：只剩注释里可以留
    code_hits = []
    for i, l in enumerate(text.split("\n"), 1):
        if l.lstrip().startswith("#"):
            continue
        for w in FORBIDDEN:
            if w in l:
                code_hits.append((i, w))
    if code_hits:
        print("⚠️ 代码行仍残留：")
        for i, w in code_hits:
            print("   L%-4d 「%s」" % (i, w))
    else:
        print("✅ 代码行已清空（红星军帽/红色五角星帽徽/戴红星/立领军装）")

    if total == 0:
        print("（无改动，幂等）")
        return 0
    if args.apply:
        bak = SRC + ".hatstar.bak"
        if not os.path.exists(bak):
            open(bak, "w", encoding="utf-8").write(orig)
            print("已备份 → %s" % os.path.basename(bak))
        open(SRC, "w", encoding="utf-8").write(text)
        print("✅ 已写入 %s" % os.path.basename(SRC))
    else:
        print("（dry-run；加 --apply 生效）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
