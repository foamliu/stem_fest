# -*- coding: utf-8 -*-
"""核查 6 个幕级脚本的镜号覆盖：是否有缺口 / 重叠。"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = [
    ("序幕一 1-9", "_diag_act0_plane.py"),
    ("序幕二 10-18", "_diag_act2_startup.py"),
    ("第一幕 19-46", "_diag_act1_trench.py"),
    ("第二幕 47-74", "_diag_act3_rice.py"),
    ("第三幕 75-105", "_diag_act4_train.py"),
    ("尾声 106-126", "_diag_act5_finale.py"),
]

seen = {}
for label, f in SCRIPTS:
    p = os.path.join(ROOT, "OUTPUT", f)
    src = io.open(p, encoding="utf-8").read()
    nums = sorted(int(m.group(1)) for m in re.finditer(r"^TASKS\[(\d+)\] = dict\(", src, re.M))
    want = label.split()[1]
    lo, hi = (int(x) for x in want.split("-"))
    expect = set(range(lo, hi + 1))
    got = set(nums)
    print("%-16s 脚本镜号 %d-%d（%d 个）  期望 %d-%d（%d 个）" % (
        label, nums[0] if nums else 0, nums[-1] if nums else 0, len(nums),
        lo, hi, len(expect)))
    if got != expect:
        miss = sorted(expect - got)
        extra = sorted(got - expect)
        if miss:
            print("    [X] 缺号: %s" % miss)
        if extra:
            print("    [X] 越界: %s" % extra)
    for n in nums:
        seen.setdefault(n, []).append(label)

dups = {n: v for n, v in seen.items() if len(v) > 1}
print()
alln = set(seen)
full = set(range(1, 127))
print("合计覆盖 %d 个镜号" % len(alln))
if dups:
    print("[X] 重叠镜号：")
    for n, v in sorted(dups.items()):
        print("   %d -> %s" % (n, v))
print("[X] 全片缺号: %s" % sorted(full - alln) if full - alln else "[OK] 1-126 无缺口")
