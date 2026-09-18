# -*- coding: utf-8 -*-
"""把 _asr_audit.txt 里**仍未通过**的镜汇总成可读清单（只列缺陷 + 当前 ASR 实得）。"""
from __future__ import annotations
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def main():
    p = os.path.join(HERE, "_asr_audit.txt")
    lines = io.open(p, encoding="utf-8").read().splitlines()
    out = []
    for l in lines:
        parts = l.split(None, 2)
        if len(parts) >= 3 and parts[1] in ("miss", "extra", "silent"):
            out.append(l)
    print("\n".join(out) if out else "（无未通过镜）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
