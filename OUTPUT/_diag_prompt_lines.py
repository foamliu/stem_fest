# -*- coding: utf-8 -*-
"""查：真 prompt 的「行结构」是否被 strip_late_audio 破坏。

用途：镜 31 场景漂移（应出交通壕、实际出教室）的根因排查 ——
若某镜的音频行与画面行被合并，H3 会把整段当"一段话"，场景描述被稀释。

用法：py -3.10 OUTPUT/_diag_prompt_lines.py 31 61 59 66 72
"""
import importlib.util
import os
import sys

OUT = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = ["_diag_act0_plane.py", "_diag_act2_startup.py", "_diag_act1_trench.py",
           "_diag_act3_rice.py", "_diag_act4_train.py", "_diag_act5_finale.py"]
LIGHT_KEYS = ["光线", "色调", "盛夏", "朝鲜战场", "教室", "稻", "餐车", "校门"]


def main():
    want = [int(x) for x in sys.argv[1:] if x.strip().isdigit()]
    rows = []
    for fn in SCRIPTS:
        p = os.path.join(OUT, fn)
        spec = importlib.util.spec_from_file_location(fn[:-3], p)
        m = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(m)
        except SystemExit:
            pass
        T = getattr(m, "TASKS", {})
        strip = getattr(m, "strip_late_audio", lambda x: x)
        for n in sorted(T):
            if want and n not in want:
                continue
            t = strip(T[n]["prompt"])
            ls = t.split("\n")
            # 判定：第 1 行是否"超长"（画面段 + 音频段被合并的特征）
            long_first = len(ls) > 0 and len(ls[0]) > 260
            rows.append((n, len(ls), [len(x) for x in ls], long_first,
                         ls[-1][:46] if ls else ""))
    print("%-5s %-4s %-22s %-8s %s" % ("镜号", "行数", "各行长度", "首页超长", "末行前 46 字"))
    for n, k, lens, lf, tail in rows:
        flag = "  🔴合并" if (k < 2 or lf) else ""
        print("%-5d %-4d %-22s %-8s %s%s" % (n, k, lens, str(lf), tail, flag))
    return 0


if __name__ == "__main__":
    sys.exit(main())
