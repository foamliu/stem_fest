# -*- coding: utf-8 -*-
"""★ 闸门：校验**拼接后的真 prompt**（经 strip_late_audio）结构与禁令隔离。

为什么需要：`strip_late_audio()` 会在提交前处理 prompt。若它把 `\n` 吃掉，
禁令句就与台词粘连 → H3 把台词渲染成画面字幕（镜 14 实测 8/8 帧泄漏）。

本脚本对 8 个泄漏镜逐一：导入 act 脚本 → 取 TASKS[n]["prompt"] →
跑该脚本自己的 strip_late_audio() → 检查：
  1. 是否存在换行（多段结构）
  2. 禁令句（★ 全画面不得…）是否独占一行
  3. 禁令行与台词行是否已分离
  4. `**` 残留数

用法：py -3.10 OUTPUT/_verify_prompt_lines.py [--shots=14,21,...]
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEAKS = [14, 21, 36, 77, 85, 86, 88, 112]
ACT = {
    14: "_diag_act2_startup.py",
    21: "_diag_act1_trench.py", 36: "_diag_act1_trench.py",
    77: "_diag_act4_train.py", 85: "_diag_act4_train.py",
    86: "_diag_act4_train.py", 88: "_diag_act4_train.py",
    112: "_diag_act5_finale.py",
}
GUARD = "★ 全画面不得出现任何可读的文字、字幕或符号。"


def load(mod_file):
    ns = {"__name__": "_mod_%s" % mod_file.replace(".", "_")}
    src = open(os.path.join(ROOT, "OUTPUT", mod_file), encoding="utf-8").read()
    old = sys.argv
    sys.argv = ["x"]                       # 防止模块级 argparse 读我们的参数
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
    cache = {}
    bad = 0
    print("%-6s %-8s %-8s %-9s %-9s %s" % ("镜", "有换行", "禁令独行", "禁令行OK",
                                           "** 残留", "判定"))
    print("-" * 62)
    for n in shots:
        f = ACT[n]
        if f not in cache:
            cache[f] = load(f)
        ns = cache[f]
        raw = ns["TASKS"][n]["prompt"]
        real = ns["strip_late_audio"](raw)
        lines = real.split("\n")
        multi = len(lines) > 1
        guard_lines = [i for i, L in enumerate(lines) if GUARD in L]
        # 禁令行必须"独占"：整行只有禁令（允许前后空白）
        solo = bool(guard_lines) and all(
            lines[i].strip() == GUARD for i in guard_lines)
        # 禁令所在行不得含台词关键词（"说：" 之类）
        clean = bool(guard_lines) and all(
            ("说：" not in lines[i]) and ("Audio:" not in lines[i].replace(GUARD, ""))
            for i in guard_lines)
        stars = real.count("**")
        ok = multi and solo and clean and stars == 0
        if not ok:
            bad += 1
        print("%-6d %-8s %-8s %-9s %-9d %s" % (
            n, "是" if multi else "否", "是" if solo else "否",
            "是" if clean else "否", stars, "OK" if ok else "!! 需修"))
    print("-" * 62)
    print("通过 %d/%d" % (len(shots) - bad, len(shots)))
    if bad:
        print("\n--- 失败样例（镜 14 处理后尾部）---")
        ns = cache.get(ACT[14]) or load(ACT[14])
        print(repr(ns["strip_late_audio"](ns["TASKS"][14]["prompt"])[-320:]))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
