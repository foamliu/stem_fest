# -*- coding: utf-8 -*-
"""诊断：禁令行（★ 全画面不得…）后面是否缺少 \n 换行，导致与 Audio: 拼成同一行。

背景：镜 14 重跑后字幕仍在 —— prompt 里 `★ 全画面不得…。` 与 `Audio: …`
被拼成同一行（`符号。Audio:`），而非分成两段。本脚本扫描全部 5 个 act 脚本。
"""
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

# 禁令行模板：以 。" 结束（引号前无 \n 转义）
GUARD_END_NO_NL = re.compile(r'。\\?"\s*\n\s*"Audio:')
GUARD_END_WITH_NL = re.compile(r'。\\n\\?"\s*\n\s*"Audio:')

print("act 脚本                     含★行  ★后缺\\n接Audio  ★后有\\n(正常)")
print("-" * 74)
total_bad = 0
for rel in FILES:
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        print("%-28s  (缺失)" % os.path.basename(rel))
        continue
    s = open(p, encoding="utf-8").read()
    n_star = len(re.findall(r"★", s))
    bad = len(GUARD_END_NO_NL.findall(s))
    good = len(GUARD_END_WITH_NL.findall(s))
    total_bad += bad
    print("%-28s %4d  %10d  %10d" % (os.path.basename(rel), n_star, bad, good))
print("-" * 74)

if total_bad:
    print("!! 发现 %d 处禁令行缺 \\n —— 需修复后重跑受影响镜头。" % total_bad)
else:
    print("OK: 所有禁令行均有 \\n 隔离。")
