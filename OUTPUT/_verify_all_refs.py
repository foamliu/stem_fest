# -*- coding: utf-8 -*-
"""开跑前总校验：6 个幕级脚本的每个 TASKS 项，参考图是否都存在。

做法：把脚本当模块运行到 TASKS 构建完成（不触发网络），逐个 TASKS 检查 ref1/ref2。
"""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = [
    "_diag_act0_plane.py", "_diag_act2_startup.py", "_diag_act1_trench.py",
    "_diag_act3_rice.py", "_diag_act4_train.py", "_diag_act5_finale.py",
]

bad, tot_refs, tot_shots = [], 0, 0
for f in SCRIPTS:
    path = os.path.join(ROOT, "OUTPUT", f)
    # 只执行到 TASKS 定义完；main() 不会跑（__name__ != "__main__"）
    spec = importlib.util.spec_from_file_location("m_" + f[:-3], path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    shots = sorted(mod.TASKS)
    tot_shots += len(shots)
    for n in shots:
        t = mod.TASKS[n]
        for key in ("ref1", "ref2"):
            p = t.get(key)
            if p is None:
                continue
            tot_refs += 1
            if not os.path.isfile(p):
                bad.append((f, n, key, os.path.relpath(p, ROOT)))
    print("%-24s %2d 镜  %s" % (f, len(shots), "OK" if shots else "空"))

print()
print("合计 %d 镜 / %d 处参考图引用" % (tot_shots, tot_refs))
if bad:
    print("缺失 %d 处：" % len(bad))
    for f, n, k, p in bad:
        print("   %-24s 镜%-3d %s  %s" % (f, n, k, p))
else:
    print("全部参考图存在 [OK]")
