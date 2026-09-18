# -*- coding: utf-8 -*-
"""列出 storyboard 一致性报告里的 🔴 漂移镜（精简版，便于逐条看）。"""
from __future__ import annotations
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    L = io.open(os.path.join(HERE, "_storyboard_audit.md"), encoding="utf-8").read()
    n = 0
    for m in re.finditer(r"### 镜 (\d+)(.{0,1200}?)(?=\n### |\Z)", L, re.S):
        body = m.group(2)
        if "\U0001f534" in body:
            n += 1
            print("镜 %s" % m.group(1))
            for l in body.split("\n"):
                if "\U0001f534" in l:
                    print("   ", l.strip()[:140])
    print("\n🔴 共 %d 镜" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
