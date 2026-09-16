# -*- coding: utf-8 -*-
"""dump 指定镜的「真 prompt」（strip_late_audio 之后）到 OUTPUT/_dump/<n>.txt。

用法：
    py -3.10 OUTPUT/_dump_shot.py 1 14 106
"""
import importlib.util
import os
import sys

ROOT = r"E:\code\stem_fest"
OUT = os.path.join(ROOT, "OUTPUT")
DEST = os.path.join(OUT, "_dump")

SCRIPTS = [
    "_diag_act0_plane.py", "_diag_act2_startup.py", "_diag_act1_trench.py",
    "_diag_act3_rice.py", "_diag_act4_train.py", "_diag_act5_finale.py",
]


def main():
    want = [int(x) for x in sys.argv[1:] if x.strip().isdigit()]
    os.makedirs(DEST, exist_ok=True)
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
        for n, t in T.items():
            if want and n not in want:
                continue
            txt = strip(t.get("prompt", ""))
            dst = os.path.join(DEST, "%03d.txt" % n)
            with open(dst, "w", encoding="utf-8", newline="\n") as f:
                f.write("### 镜 %d ｜ slug=%s ｜ dur=%ss\n" % (n, t.get("slug"), t.get("dur")))
                f.write("### ref1=%s\n### ref2=%s\n" % (t.get("ref1"), t.get("ref2")))
                f.write("### 以下为真 prompt（strip_late_audio 之后）\n")
                f.write("----- 8< -----\n")
                f.write(txt)
                f.write("\n")
            print("  -> %s" % dst)
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
