# -*- coding: utf-8 -*-
"""打印指定镜最终提交给 H3 的 prompt 全文（含 strip_late_audio 处理）。

用法：py -3.10 OUTPUT/_dump_prompt.py 14
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACT = {
    14: "_diag_act2_startup.py",
    21: "_diag_act1_trench.py", 36: "_diag_act1_trench.py",
    77: "_diag_act4_train.py", 85: "_diag_act4_train.py",
    86: "_diag_act4_train.py", 88: "_diag_act4_train.py",
    112: "_diag_act5_finale.py",
}


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 14
    f = ACT.get(n)
    if not f:
        print("未登记镜号 %d" % n)
        return 1
    ns = {"__name__": "_dump"}
    src = open(os.path.join(ROOT, "OUTPUT", f), encoding="utf-8").read()
    old, sys.argv = sys.argv, ["x"]
    try:
        exec(compile(src, f, "exec"), ns)
    finally:
        sys.argv = old
    raw = ns["TASKS"][n]["prompt"]
    real = ns["strip_late_audio"](raw)
    print("=" * 68)
    print("镜 %d  |  %s  |  seed=%s  dur=%ss" % (
        n, ns["TASKS"][n]["slug"], ns["TASKS"][n]["seed"], ns["TASKS"][n]["dur"]))
    print("=" * 68)
    print("【原始 TASKS[n]['prompt']】")
    print(raw)
    print("-" * 68)
    print("【strip_late_audio 之后 —— 真正提交给 H3 的文本】")
    print(real)
    print("-" * 68)
    for i, L in enumerate(real.split("\n")):
        print("  行%d: %s" % (i + 1, L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
