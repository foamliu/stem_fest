# -*- coding: utf-8 -*-
"""列出所有 Audio 段里的「…地(说|问|喊|答)：」，用于核对归一化结果。"""
from __future__ import annotations
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
MODS = ["_diag_act0_plane", "_diag_act1_trench", "_diag_act2_startup",
        "_diag_act3_rice", "_diag_act4_train", "_diag_act5_finale"]
PAT = re.compile(r"([\u4e00-\u9fa5\u3001\uff0c]{0,14})\u5730(\u8bf4|\u95ee|\u558a|\u7b54|\u5631\u5490)([\uff1a:])")


def main():
    dest = os.path.join(HERE, "_stage_dir_check.txt")
    out = []
    n_hit = 0
    for mn in MODS:
        m = __import__(mn)
        for n, t in sorted(m.TASKS.items()):
            p = t["prompt"]
            i = p.find("Audio:")
            aud = p[i:] if i >= 0 else ""
            for mm in PAT.finditer(aud):
                n_hit += 1
                out.append("镜 %-4d (%s)  %r" % (n, mn, mm.group()))
    out.insert(0, "Audio 段里残留的「…地说：」= %d 处" % n_hit)
    out.insert(1, "-" * 70)
    txt = "\n".join(out)
    io.open(dest, "w", encoding="utf-8").write(txt + "\n")
    print(txt[:3000])
    print("\n-> %s" % dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
