# -*- coding: utf-8 -*-
"""★ 按 storyboard 自动校正 `TASKS[n]["dur"]`。

为什么要脚本做
    全片 126 镜里有一批 `dur` 与 `storyboard.md` 的「时长」列不一致
    （早期生成时按「够念完台词」临时加长，后续 storyboard 压缩后未回改）。
    storyboard 是**唯一权威** ⇒ 以它为准批量校正。

安全设计
    · 默认 **--dry**，只打印 diff，不改文件；
    · `--apply` 才真写；写前自动备份 `.dur.bak`；
    · 不碰 prompt，只改 `dur=...` 这一处。

用法：
    py -3.10 OUTPUT/_fix_dur_drift.py            # 只看 diff
    py -3.10 OUTPUT/_fix_dur_drift.py --apply    # 真改
"""
import os
import re
import sys

ROOT = r"E:\code\stem_fest"
OUT = os.path.join(ROOT, "OUTPUT")
SB = os.path.join(ROOT, "storyboard.md")
SCRIPTS = ["_diag_act0_plane.py", "_diag_act2_startup.py", "_diag_act1_trench.py",
           "_diag_act3_rice.py", "_diag_act4_train.py", "_diag_act5_finale.py"]


def sb_dur():
    d = {}
    raw = open(SB, encoding="utf-8", newline="").read()
    for L in raw.split("\n"):
        L = L.rstrip("\r")
        if not L.startswith("| "):
            continue
        c = [x.strip() for x in L.strip().strip("|").split("|")]
        if len(c) >= 2 and re.fullmatch(r"\d+", c[0]) and re.fullmatch(r"\d+s", c[1]):
            d[int(c[0])] = int(c[1][:-1])
    return d


def main():
    apply = "--apply" in sys.argv
    want = sb_dur()
    total = 0
    for fn in SCRIPTS:
        p = os.path.join(OUT, fn)
        src = open(p, encoding="utf-8", newline="").read()
        lines = src.split("\n")
        hits = []
        cur = None
        for i, L in enumerate(lines):
            m = re.match(r"TASKS\[(\d+)\]\s*=\s*dict\(", L)
            if m:
                cur = int(m.group(1))
                continue
            if cur is None:
                continue
            m = re.match(r"^(\s*ref\d=.*?,\s*)?dur=([0-9.]+),\s*$", L)
            if m and "dur=" in L:
                got = float(m.group(2))
                exp = float(want.get(cur, got))
                if abs(got - exp) > 0.01:
                    new = L.replace("dur=%.1f," % got, "dur=%.1f," % exp)
                    lines[i] = new
                    hits.append((cur, got, exp))
        if hits:
            print("\n%s：" % fn)
            for n, g, e in hits:
                print("  镜 %d  %ss -> %ss" % (n, g, e))
            total += len(hits)
            if apply:
                open(p + ".dur.bak", "w", encoding="utf-8", newline="").write(src)
                open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
                print("  ✅ 已写回（备份 %s.dur.bak）" % os.path.basename(fn))
    print("\n合计需校正 %d 镜%s" % (total, "" if apply else "（--dry，未写回）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
