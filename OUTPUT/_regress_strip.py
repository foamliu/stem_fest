# -*- coding: utf-8 -*-
"""回归：strip_late_audio 改动前后，全片 prompt 差异审计。

目的：确认「保留换行」的修复**只**恢复 `\n` 结构，不改变任何镜的
文案内容（台词/环境音剔除结果必须完全一致）。

做法：用旧实现（吃掉 \n）与新实现分别处理每个 TASKS[n]["prompt"]，
把两边都压成「无空白单行」后比较 —— 内容应当逐字相同；
若不同，说明改动意外改动了文案（真 bug）。

用法：py -3.10 OUTPUT/_regress_strip.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACTS = [
    "_diag_act0_plane.py", "_diag_act1_trench.py", "_diag_act2_startup.py",
    "_diag_act3_rice.py", "_diag_act4_train.py", "_diag_act5_finale.py",
]


def load(mod_file):
    ns = {"__name__": "_reg_%s" % mod_file.replace(".", "_")}
    src = open(os.path.join(ROOT, "OUTPUT", mod_file), encoding="utf-8").read()
    old, sys.argv = sys.argv, ["x"]
    try:
        exec(compile(src, mod_file, "exec"), ns)
    finally:
        sys.argv = old
    return ns


def old_impl(text, mark):
    """旧实现（吞 \n，作为对照）。"""
    out = []
    for sent in re.split(r"(?<=[；。])|\n", text):
        if mark in sent:
            continue
        out.append(sent)
    return "".join(out).strip()


def squash(s):
    return re.sub(r"\s+", "", s)


def main():
    total = same = diff = 0
    problems = []
    per_act = []
    for f in ACTS:
        ns = load(f)
        new_impl = ns["strip_late_audio"]
        mark = ns["LATE_MARK"]
        tasks = ns.get("TASKS") or {}
        n_act = n_diff = 0
        for n in sorted(tasks):
            raw = tasks[n].get("prompt")
            if not raw:
                continue
            a = old_impl(raw, mark)
            b = new_impl(raw)
            total += 1
            n_act += 1
            if squash(a) == squash(b):
                same += 1
            else:
                diff += 1
                n_diff += 1
                problems.append((f, n, a, b))
        per_act.append((os.path.basename(f), n_act, n_diff))
    for name, n_act, n_diff in per_act:
        print("%-28s 镜数 %3d  内容一致 %3d  不一致 %d" % (
            name, n_act, n_act - n_diff, n_diff))
    print("-" * 66)
    print("总计 %d 镜：内容一致 %d，不一致 %d" % (total, same, diff))
    if problems:
        print("\n!! 以下镜文案被改动（需人工核对）：")
        for f, n, a, b in problems[:8]:
            print("  %s 镜 %s" % (os.path.basename(f), n))
            print("    旧: %s" % a[-150:])
            print("    新: %s" % b[-150:])
        return 1
    print("✅ 修复仅恢复换行结构，未改动任何镜的文案。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
