# -*- coding: utf-8 -*-
"""镜 1 prompt 清理：去掉 Markdown `**`（会被 H3 当画面文字画出来）。

★ 依据 README §6.6 / §6.6b：`**` 是**给 Agent 自己看**的语义强调标记，
   H3 不需要；实测「镜 7 出了 `** 也不抬`」⇒ `**` 只增泄漏面，必须删。

★ 为什么镜 1 还有 `**`：它在 2026-09-19「校名方向反转」时被重写，
   新写的正向要求里带了 `**` 强调（`**金色校名立体字**` 等）。
   旧版去泄漏化（§6.6b）只覆盖了当时已存在的镜，漏了这次新写的。

★ 做法：只删 `**` 标记符本身，**保留加粗文字**（语义不变）。
   ⚠️ 注意 §6.6b 的 R2 规则：`**头也不抬**` 要改写成自然陈述句，
      而不是简单删星号。但镜 1 这些 `**` 只是**名词短语**（`金色校名立体字`、
      `红色圆形校徽`），删星号后读起来仍是通顺的陈述 ⇒ 直接删星号即可。

用法：py -3.10 OUTPUT/_fix_shot1_stars.py [--check]
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "OUTPUT", "_diag_act0_plane.py")
GATE = os.path.join(ROOT, "OUTPUT", "_fix_shot1_stars_gate.txt")

text = io.open(SRC, encoding="utf-8").read()
orig_stars = text.count("**")

# 只改 TASKS[1] 的 prompt 块
start = text.find("TASKS[1] = dict(")
end = text.find("TASKS[2] = dict(")
assert start > 0 and end > start, "TASKS[1] block not found"
block = text[start:end]
new_block = block.replace("**", "")
text = text[:start] + new_block + text[end:]

syn_ok, syn_err = True, ""
try:
    compile(text, SRC, "exec")
except SyntaxError as e:
    syn_ok, syn_err = False, "%s (line %s)" % (e.msg, e.lineno)

after = text[start:start + len(new_block)].count("**")
report = ["stars in file before: %d" % orig_stars,
          "stars in TASKS[1] after: %d" % after,
          "syntax: %s %s" % ("OK" if syn_ok else "FAIL", syn_err)]
ok = syn_ok and after == 0
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
