# -*- coding: utf-8 -*-
"""列出 `_storyboard_audit.md` 里所有 🔴漂移 明细，便于逐条裁定真伪。"""
import io
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

t = io.open("OUTPUT/_storyboard_audit.md", encoding="utf-8").read()
blocks = re.split(r"### 镜 ", t)[1:]
for b in blocks:
    n = b.split()[0]
    drifts = [l.strip() for l in b.split("\n") if l.strip().startswith("- 🔴")]
    if drifts:
        print("镜 %s" % n)
        for d in drifts:
            print("   " + d[:170])
