# -*- coding: utf-8 -*-
"""第一幕（上甘岭）文字一致性清理：去掉与新史实基调冲突的旧措辞。

★ 背景：`_patch_act1_winter.py` 已把 LIGHT 改为「10 月深秋、白天有太阳」，
   并给 21 个含战士的镜挂了 `GUARD_SOLDIER_WINTER`（50 式冬装）。
   但正文里仍残留**与新闻冲突**的旧词：
     · 「灰蒙蒙的」战前交通壕  → 与「白天有太阳」冲突（且史实上 10 月不阴霾）
     · 「穿军绿色立领军装」的志愿军战士 → 单层军装，与「冬季棉装」冲突
   必须一并清掉，否则 H3 收到自相矛盾的描述（README §6.10.3 镜 31 同源教训：
   锚点冲突时模型会任选其一）。

★ 替换（幂等，可重复运行）
   A) `那条灰蒙蒙的战前交通壕`  → `那条深秋的战前交通壕`
   B) `穿军绿色立领军装的志愿军战士` → `穿军绿色冬季棉装的志愿军战士`
   C) 独立的 `灰蒙蒙的`（其他地方）→ 视上下文，统一改 `深秋干冷的`

★ 注意：`GUARD_HUANG` 里的「军绿色立领军装」**保留** —— 那是黄继光的
   外形护栏，与 `huang_jiguang_hero_v02.png` 定妆照一致（README §6.1 #1：
   定妆照 = 外形唯一权威）。只改**正文叙述里的战士**，不动护栏常量。

用法：py -3.10 OUTPUT/_fix_act1_wording.py [--check]
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "OUTPUT", "_diag_act1_trench.py")
GATE = os.path.join(ROOT, "OUTPUT", "_fix_act1_wording_gate.txt")

text = io.open(SRC, encoding="utf-8").read()
orig = text
counts = {}

# 只替换**正文叙述**里的措辞；护栏常量（GUARD_HUANG 定义块）单独保护。
# 记录 GUARD_HUANG 定义块的位置以便跳过
guard_start = text.find("GUARD_HUANG = (")
guard_end = text.find(")", guard_start) + 1
head, guard_block, tail = text[:guard_start], text[guard_start:guard_end], text[guard_end:]

RULES = [
    ("那条灰蒙蒙的战前交通壕", "那条深秋的战前交通壕"),
    ("穿军绿色立领军装的志愿军战士", "穿军绿色冬季棉装的志愿军战士"),
    ("灰蒙蒙的战前交通壕", "深秋的战前交通壕"),
    ("天灰蒙蒙的", "天色偏冷的"),
    ("灰蒙蒙", "深秋干冷"),
]

for a, b in RULES:
    n = head.count(a) + tail.count(a)
    if n:
        head = head.replace(a, b)
        tail = tail.replace(a, b)
    counts[a] = n

text = head + guard_block + tail

syn_ok, syn_err = True, ""
try:
    compile(text, SRC, "exec")
except SyntaxError as e:
    syn_ok, syn_err = False, "%s (line %s)" % (e.msg, e.lineno)

report = ["replacements: %s" % counts,
          "remaining 灰蒙蒙 in file: %d" % text.count("灰蒙蒙"),
          "remaining in guard block: %d" % guard_block.count("灰蒙蒙"),
          "syntax: %s %s" % ("OK" if syn_ok else "FAIL", syn_err)]
ok = syn_ok and (text.count("灰蒙蒙") == 0)
report.append("GATE: %s" % ("PASS" if ok else "FAIL"))
io.open(GATE, "w", encoding="utf-8", newline="\n").write("\n".join(report) + "\n")

if not ok:
    print("gate failed; not written")
    sys.exit(2)
if "--check" in sys.argv:
    print("check mode; not written")
    sys.exit(0)
io.open(SRC, "w", encoding="utf-8", newline="\n").write(text)
print("written")
