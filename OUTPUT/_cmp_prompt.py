# -*- coding: utf-8 -*-
"""对比「泄漏镜」与「干净镜」的 prompt 写法差异 —— 找可操作的规避规则。

背景（2026-09-15）
    全片扫描出 9 个台词泄漏镜（7/14/21/36/77/85/86/88/112）。
    要把结论变成**可操作规则**，必须回答：**泄漏镜的写法与干净镜有什么不同？**
    本脚本把两者的 `Audio:` 段并排打印，便于人工归纳（也便于以后复用）。

用法
    py -3.10 OUTPUT/_cmp_prompt.py
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")

LEAK = [7, 14, 21, 36, 77, 85, 86, 88, 112]
CLEAN = [5, 15, 20, 30, 40, 47, 60, 100, 113, 118]


def audio_of(n):
    for f in glob.glob(os.path.join(OUT, "_diag_act*.py")):
        src = open(f, encoding="utf-8").read()
        m = re.search(r"TASKS\[%d\]" % n, src)
        if not m:
            continue
        seg = src[m.end():m.end() + 2200]
        a = re.findall(r'Audio:[^"]{0,220}', seg)
        return os.path.basename(f), (a[0] if a else "（无 Audio 段）")
    return "?", "（未找到该镜）"


def main():
    L = ["# 泄漏镜 vs 干净镜 —— Audio 段写法对照", "",
         "## 一、泄漏镜（%d 个）" % len(LEAK), "",
         "| 镜 | 幕脚本 | Audio 段 |", "|:-:|---|---|"]
    for n in LEAK:
        f, a = audio_of(n)
        L.append("| %d | `%s` | %s |" % (n, f, a.replace("|", "/")))
    L += ["", "## 二、干净镜（对照，%d 个）" % len(CLEAN), "",
          "| 镜 | 幕脚本 | Audio 段 |", "|:-:|---|---|"]
    for n in CLEAN:
        f, a = audio_of(n)
        L.append("| %d | `%s` | %s |" % (n, f, a.replace("|", "/")))
    L += ["", "## 三、观察要点（人工填）", "",
          "- 泄漏镜是否都写了**台词原文**？（`说：xxx`）",
          "- 干净镜是否多用**「说了一句」而不给原文**？",
          "- 是否与**镜时长/画面复杂度**相关？", ""]
    txt = "\n".join(L)
    print(txt)
    open(os.path.join(OUT, "_cmp_prompt.md"), "w",
         encoding="utf-8").write(txt)
    print("\n→ OUTPUT/_cmp_prompt.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
