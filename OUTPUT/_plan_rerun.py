# -*- coding: utf-8 -*-
"""生成「污染重跑清单」：结合①源码修复时间 ②视频生成时间 ③高危镜号，
算出到底哪些镜必须重跑。

判定逻辑（三分支）
    A. 视频 mtime < 修复脚本 mtime  ⇒ 用的是旧 prompt ⇒ 必重跑
    B. 镜号在 _scan_hazard.py 的 R1 高危集内（NO_SPEECH 引用）⇒ 必重跑
    C. 视频不存在 ⇒ 必重跑

第二层：同一镜的多个版本里，只要**最新版**晚于修复时间即可豁免
    （因为 _resume_finalize 已重跑过 4/5/19/39，它们是干净的）

输出
    OUTPUT/_rerun_list.txt    人读清单（按幕分组）
    OUTPUT/_rerun_list.json   {幕: [镜号...]}

用法：
    py -3.10 OUTPUT/_plan_rerun.py
    py -3.10 OUTPUT/_plan_rerun.py --fix-time=2026-09-14T18:11:13
"""
import glob
import json
import os
import re
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")

# 幕目录 → 脚本
# ★ 幕目录 → 脚本（**必须与脚本里的 OUT_ROOT 一致**，勿凭语义猜测）
#   核对来源：各脚本 OUT_ROOT = os.path.join(ROOT, "OUTPUT", "<dir>", "video")
#   注意 act2 输出到 04_classroom_dusk（与 act1 的 06_trench 一样是"命名不直观"的历史遗留）
ACTS = [
    ("01_paper_plane", "_diag_act0_plane.py"),
    ("06_trench", "_diag_act1_trench.py"),
    ("04_classroom_dusk", "_diag_act2_startup.py"),
    ("07_rice_field", "_diag_act3_rice.py"),
    ("08_train_dining", "_diag_act4_train.py"),
    ("05_classroom_night", "_diag_act5_finale.py"),
]

# 09-14 元信息修复的时刻（_fix_prompt_meta.py 落盘时间）
FIX_9_14 = datetime(2026, 9, 14, 18, 11, 13)
# 09-15 NO_SPEECH 修复（本次，全部幕脚本都在 07:05-07:06 改写）
FIX_9_15 = datetime(2026, 9, 15, 7, 6, 30)

# R1 高危（引用了 NO_SPEECH 常量）—— 来自 _scan_hazard.py
R1_SHOTS = {4, 5, 9, 16, 19, 23, 46, 50, 52, 64, 73, 74, 75, 79, 81, 83,
            91, 102, 104, 105, 106, 109, 110, 111, 113, 117, 119, 120, 121,
            122, 123, 124, 125, 126}

# 09-14 元信息修复涉及的镜（_fix_prompt_meta.py）
META_9_14 = {6, 10, 16, 33, 38, 43, 52, 91, 94, 96, 97, 114, 125}

# 09-15 新增修复的镜（否定式残留）
NEW_9_15 = {110, 111, 113, 117, 119, 121}


def latest(shot):
    best, bt = None, None
    for d, _ in ACTS:
        for f in glob.glob(os.path.join(OUT, d, "video", "%02d_*.mp4" % shot)):
            m = os.path.getmtime(f)
            if bt is None or m > bt:
                best, bt = f, m
    return best, (datetime.fromtimestamp(bt) if bt else None)


def script_of(shot):
    for d, s in ACTS:
        if glob.glob(os.path.join(OUT, d, "video", "%02d_*.mp4" % shot)):
            return s
    return "?"


def main():
    fix = FIX_9_14
    for a in sys.argv[1:]:
        if a.startswith("--fix-time="):
            fix = datetime.fromisoformat(a.split("=", 1)[1])
    print("09-14 元信息修复时刻：%s" % fix)
    print("09-15 NO_SPEECH 修复时刻：%s\n" % FIX_9_15)

    rows, by_act = [], {}
    for shot in range(1, 127):
        p, mt = latest(shot)
        tier, reasons = 3, []

        if p is None:
            tier, reasons = 1, ["无视频"]
        else:
            # ── P1 最高优先：今天(09-15)刚修的否定式残留，污染机制已确证 ──
            if shot in NEW_9_15:
                tier, reasons = 1, ["09-15新修：否定式指令残留（已确证机制）"]
            # ── P2：NO_SPEECH 引用的 34 镜，机制已确证（镜5/19 铁证）──
            elif shot in R1_SHOTS:
                tier, reasons = 2, ["R1:引用NO_SPEECH（铁证机制）"]
            # ── P3：09-14 元信息镜，视频早于修复 ⇒ 旧 prompt ──
            elif shot in META_9_14 and mt and mt < FIX_9_14:
                tier, reasons = 3, ["09-14元信息镜且视频早于修复"]
            # ── P4：其余镜，prompt 无实质污染改写 ⇒ 可先不跑，视觉抽检后定 ──
            else:
                tier, reasons = 4, ["无确证污染源"]

        need = tier <= 3
        if p and mt and mt >= FIX_9_15:
            need, reasons = False, ["已含09-15修复版"]
            tier = 0

        s = script_of(shot)
        rows.append((shot, s, need, tier, reasons, mt))
        if need:
            by_act.setdefault(s, []).append(shot)

    tiers = {0: [], 1: [], 2: [], 3: [], 4: []}
    for r in rows:
        tiers[r[3]].append(r[0])
    need_n = sum(1 for r in rows if r[2])
    print("需重跑 %d 镜 / 共 126 镜\n" % need_n)
    print("分级（数字小的优先跑）：")
    names = {0: "已完成(有09-15修复版)", 1: "P1 否定式残留新修",
             2: "P2 NO_SPEECH 引用", 3: "P3 元信息旧视频",
             4: "P4 无确证污染(暂不跑)"}
    for t in sorted(names):
        ns = sorted(tiers[t])
        print("   %-24s %3d 镜  %s" % (names[t], len(ns), ns[:20]))

    with open(os.path.join(OUT, "_rerun_list.txt"), "w", encoding="utf-8") as f:
        f.write("污染重跑清单（2026-09-15）—— 按优先级分级\n" + "=" * 66 + "\n")
        f.write("P1/P2 = 污染机制已视觉确证，必跑\n")
        f.write("P3    = 视频生成于 prompt 修复前，必跑\n")
        f.write("P4    = 无确证污染源，先不跑（省 GPU）\n\n")
        for t in (1, 2, 3):
            ns = sorted(tiers[t])
            if not ns:
                continue
            f.write("\n【%s】共 %d 镜\n  %s\n" % (names[t], len(ns), ns))
            for n in ns:
                r = [x for x in rows if x[0] == n][0]
                f.write("     镜 %-4d %-24s mtime=%s  %s\n" % (
                    n, r[1], r[5].strftime("%m-%d %H:%M:%S") if r[5] else "N/A",
                    "; ".join(r[4])))
        f.write("\n\n【P4 暂不跑】共 %d 镜\n  %s\n" % (
            len(tiers[4]), sorted(tiers[4])))

    with open(os.path.join(OUT, "_rerun_list.json"), "w", encoding="utf-8") as f:
        json.dump({names[t]: sorted(tiers[t]) for t in (1, 2, 3, 4)}, f,
                  ensure_ascii=False, indent=1)

    print("\n输出：OUTPUT/_rerun_list.txt / _rerun_list.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
