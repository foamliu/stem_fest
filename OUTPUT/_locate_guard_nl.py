# -*- coding: utf-8 -*-
"""定位：禁令行（★ 全画面不得…）缺 \\n 的具体镜头号。"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = [
    "OUTPUT/_diag_act0_plane.py",
    "OUTPUT/_diag_act1_trench.py",
    "OUTPUT/_diag_act2_startup.py",
    "OUTPUT/_diag_act4_train.py",
    "OUTPUT/_diag_act5_finale.py",
]

BAD = re.compile(r'。\\?"\s*\n\s*"Audio:')

for rel in FILES:
    p = os.path.join(ROOT, rel)
    s = open(p, encoding="utf-8").read()
    lines = s.split("\n")
    # 找 TASKS[n] = dict( 的起止，映射行号 -> 镜头号
    tasks = []
    cur = None
    for i, ln in enumerate(lines):
        m = re.match(r"TASKS\[(\d+)\]\s*=\s*dict\(", ln)
        if m:
            if cur:
                cur["end"] = i
                tasks.append(cur)
            cur = {"shot": int(m.group(1)), "start": i, "end": len(lines)}
    if cur:
        tasks.append(cur)

    def shot_of(lineno):
        for t in tasks:
            if t["start"] <= lineno < t["end"]:
                return t["shot"]
        return None

    hits = []
    for i, ln in enumerate(lines):
        if "★" in ln and "全画面不得" in ln:
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if re.match(r'\s*"Audio:', nxt):
                hits.append((shot_of(i), i + 1, ln.strip()[:60]))
    if hits:
        print("== %s" % os.path.basename(rel))
        for shot, nl, txt in hits:
            print("   镜 %-4s  行 %-5d  %s" % (shot, nl, txt))
