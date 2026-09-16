# -*- coding: utf-8 -*-
"""★ 闸门（镜 7 式）：校验「strip 之后」真 prompt 是否满足去泄漏配方。

配方（2026-09-16 实证，镜 7 唯一成功形态）：
  行1 = 画面段（含禁令，且禁令后仍有画面语作为缓冲）
  行2 = 台词行（独立一行，不含禁令）
判定：
  · 恰好 2 行
  · 禁令在第 1 行内
  · 禁令不是第 1 行的结尾（后面还有缓冲画面语）
  · 第 2 行不含禁令、含中文台词
  · `**` 残留 = 0

用法：py -3.10 OUTPUT/_verify_prompt_lines.py [--shots=14,21,...]
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEAKS = [7, 14, 21, 36, 77, 85, 86, 88, 112]
ACT = {
    7: "_diag_act0_plane.py",
    14: "_diag_act2_startup.py",
    21: "_diag_act1_trench.py", 36: "_diag_act1_trench.py",
    77: "_diag_act4_train.py", 85: "_diag_act4_train.py",
    86: "_diag_act4_train.py", 88: "_diag_act4_train.py",
    112: "_diag_act5_finale.py",
}
GUARD = "★ 全画面不得"


def load(mod_file):
    ns = {"__name__": "_m_%s" % mod_file.replace(".", "_")}
    src = open(os.path.join(ROOT, "OUTPUT", mod_file), encoding="utf-8").read()
    old, sys.argv = sys.argv, ["x"]
    try:
        exec(compile(src, mod_file, "exec"), ns)
    finally:
        sys.argv = old
    return ns


def main():
    shots = LEAKS
    for a in sys.argv[1:]:
        if a.startswith("--shots="):
            shots = [int(x) for x in a.split("=", 1)[1].split(",") if x]
    cache, bad = {}, 0
    print("%-6s %-6s %-9s %-10s %-6s %s" % (
        "镜", "行数", "禁令在行1", "行1非禁令结尾", "**残留", "判定"))
    print("-" * 64)
    for n in shots:
        f = ACT[n]
        if f not in cache:
            cache[f] = load(f)
        ns = cache[f]
        real = ns["strip_late_audio"](ns["TASKS"][n]["prompt"])
        lines = [L for L in real.split("\n")]
        nline = len(lines)
        l1, l2 = lines[0], (lines[1] if nline > 1 else "")
        g_in_l1 = GUARD in l1
        # 禁令后仍有画面语？（镜 7 的关键特征）
        tail = l1.split(GUARD)[-1] if g_in_l1 else ""
        buffered = len(tail.strip()) >= 6
        l2_clean = GUARD not in l2
        stars = real.count("**")
        ok = (nline == 2 and g_in_l1 and buffered and l2_clean and stars == 0)
        if not ok:
            bad += 1
        print("%-6d %-6d %-9s %-10s %-6d %s" % (
            n, nline, "是" if g_in_l1 else "否",
            "是" if buffered else "否", stars, "OK" if ok else "!! 需修"))
    print("-" * 64)
    print("通过 %d/%d" % (len(shots) - bad, len(shots)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
