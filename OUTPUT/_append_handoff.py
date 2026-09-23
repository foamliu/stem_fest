# -*- coding: utf-8 -*-
"""把本次收尾结论追加进 `OUTPUT/_RERUN_HANDOFF.md`（幂等）。"""
from __future__ import annotations

import pathlib

HERE = pathlib.Path(__file__).resolve().parent
HANDOFF = HERE / "_RERUN_HANDOFF.md"
APPEND = HERE / "_handoff_append.md"

MARK = "## 七、收尾结果"


def main() -> int:
    text = HANDOFF.read_text(encoding="utf-8")
    if MARK in text:
        print("已追加过，跳过")
        return 0
    extra = APPEND.read_text(encoding="utf-8")
    HANDOFF.write_text(text.rstrip() + "\n" + extra, encoding="utf-8")
    n = len(HANDOFF.read_text(encoding="utf-8").splitlines())
    print(f"已追加，_RERUN_HANDOFF.md 现共 {n} 行")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
