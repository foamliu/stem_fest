# -*- coding: utf-8 -*-
"""全片视频覆盖度体检 —— 逐幕列出「应有镜 / 有视频镜 / 缺失镜 / 多余镜」。

为什么要写它
    2026-09-15 发现 `_shot_refs.json` 的 `script` 归属与实际 mp4 所在目录
    对不上（`06_trench` 报 31 个 mp4，但该幕只应有 28 镜）——
    说明「镜号 → 目录」的映射有历史偏差，必须逐幕核对，
    否则重跑 / 拼接会漏镜或串镜。

输出
    控制台 + `OUTPUT/_coverage.txt`
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")
REFS = os.path.join(OUT, "_shot_refs.json")

# 权威表：幕脚本 → (输出目录, 镜号区间)
ACTS = [
    ("_diag_act0_plane.py",    "01_paper_plane",   (1, 9)),
    ("_diag_act2_startup.py",  "03_classroom_day", (10, 18)),
    ("_diag_act1_trench.py",   "06_trench",        (19, 46)),
    ("_diag_act3_rice.py",     "07_rice_field",    (47, 74)),
    ("_diag_act4_train.py",    "08_train_dining",  (75, 105)),
    ("_diag_act5_finale.py",   "05_classroom_night", (106, 126)),
]


def shots_in(dirname):
    """该目录下所有 mp4 的镜号 → 版本文件列表。"""
    vd = os.path.join(OUT, dirname, "video")
    got = {}
    for f in glob.glob(os.path.join(vd, "*.mp4")):
        m = re.match(r"(\d+)_", os.path.basename(f))
        if m:
            got.setdefault(int(m.group(1)), []).append(f)
    return got


def main():
    refs = json.load(open(REFS, encoding="utf-8"))
    lines = []
    lines.append("%-24s %-20s %6s %6s %6s %s" % (
        "幕脚本", "输出目录", "应有", "有视频", "缺镜", "多余镜(不属于本幕)"))
    lines.append("-" * 100)

    seen = set()
    problems = 0
    for script, dirname, (lo, hi) in ACTS:
        want = set(range(lo, hi + 1))
        got = shots_in(dirname)
        have = set(got)
        miss = sorted(want - have)
        extra = sorted(have - want)
        seen |= have
        lines.append("%-24s %-20s %6d %6d %6d %s" % (
            script, dirname, len(want), len(have), len(miss),
            extra if extra else "-"))
        if miss or extra:
            problems += 1
        if miss:
            lines.append("      缺：%s" % miss)
        if extra:
            lines.append("      多：%s" % extra)

    allwant = set(range(1, 127))
    lines.append("-" * 100)
    lines.append("全片：应有 %d 镜，实际覆盖 %d 镜，缺失 %s" % (
        len(allwant), len(seen & allwant), sorted(allwant - seen) or "无"))
    lines.append("带问题的幕：%d 个" % problems)

    txt = "\n".join(lines)
    print(txt)
    open(os.path.join(OUT, "_coverage.txt"), "w", encoding="utf-8").write(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
