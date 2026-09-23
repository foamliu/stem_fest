# -*- coding: utf-8 -*-
"""校验四个幕脚本的 SCENE 常量是否指向真实存在的场景图（2026-09-21）。

背景：`04_classroom_dusk` 目录删除后，`_diag_act2_startup.py` 等脚本的 `SCENE`
曾指向不存在的文件 —— 那种错误在 `--dry` 里也会静默过去（dry 不校验文件存在性），
直到真跑提交时才炸。本脚本把这一步显式化。

用法：
    py -3.10 OUTPUT/_check_scene_refs.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(ROOT, "OUTPUT")

# (脚本文件, [常量名...])
TARGETS = [
    ("_diag_act0_plane.py", ["SCENE_GATE", "SCENE_CAMPUS", "SCENE_CLASS"]),
    ("_diag_act1_trench.py", ["SCENE"]),
    ("_diag_act2_startup.py", ["SCENE"]),
    ("_diag_act3_rice.py", ["SCENE_RICE"]),
    ("_diag_act4_train.py", ["SCENE"]),
    ("_diag_act5_finale.py", ["SCENE"]),
]

# os.path.join(SCENES, "dir", "file")
PAT = re.compile(
    r'^\s*%s\s*=\s*os\.path\.join\(\s*SCENES\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\)',
    re.M,
)

ok_all = True
for fname, vars_ in TARGETS:
    path = os.path.join(OUTPUT, fname)
    if not os.path.exists(path):
        print("[跳过] 脚本不存在：%s" % fname)
        continue
    src = open(path, encoding="utf-8").read()
    for var in vars_:
        # 定位 `var =` 那一行（取首次出现）
        line = None
        for ln in src.splitlines():
            if re.match(r"\s*%s\s*=" % re.escape(var), ln):
                line = ln
                break
        if line is None:
            print("[?] %-22s 未找到 `%s =`" % (fname, var))
            ok_all = False
            continue
        m = re.search(r'os\.path\.join\(\s*SCENES\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\)', line)
        if not m:
            print("[?] %-22s `%s` 写法非常规，请手工确认：%s" % (fname, var, line.strip()))
            ok_all = False
            continue
        d, f = m.group(1), m.group(2)
        full = os.path.join(ROOT, "ASSETS", "SCENES", d, f)
        exist = os.path.exists(full)
        if not exist:
            ok_all = False
        print("%-22s %-11s %-52s %s" % (
            fname, var, "SCENES/%s/%s" % (d, f), "OK" if exist else "*** 文件不存在 ***"))

print("-" * 72)
print("结论：%s" % ("四个幕脚本的场景图引用全部有效。" if ok_all
                 else "有引用失效，请修复后再跑生成。"))
sys.exit(0 if ok_all else 1)
