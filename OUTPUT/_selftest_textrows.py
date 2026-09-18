# -*- coding: utf-8 -*-
"""字幕泄漏检测器（`_scan_text_rows.py::scan_frame`）的自测 —— 正例 + 负例。

★ 为什么必须自测
    镜 36 事故：字幕「继光哥」「你听见没」**明明在画面里**，
    但扫描器报「0/126 干净」——**漏检**。
    根因：旧判据用"亮像素紧贴暗像素的比例"，而镜 36 是**夜间暗场**，
    暗掩膜近乎全屏 ⇒ 比例被稀释（0.30 < 0.55 阈值）⇒ 漏。
    ⇒ 检测器的判据必须用**正例 + 负例**双重自测锁住，不能只靠"跑一遍没报错"。

正例（应命中）：镜 36 泄漏帧（暗场 + 短字幕）、镜 60/61 等含烧字的帧
负例（不该命中）：白校服特写、纯白/纯黑转场卡、稻田空镜、屏幕 UI

用法：
    py -3.10 OUTPUT/_selftest_textrows.py
"""
from __future__ import annotations
import importlib.util
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.argv = ["x"]

spec = importlib.util.spec_from_file_location("strw", os.path.join(HERE, "_scan_text_rows.py"))
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


def load(p):
    return np.asarray(Image.open(p).convert("RGB"), dtype=np.float32)


POSITIVE = [
    ("OUTPUT/_chk36/f0.jpg", "镜 36 暗场短字幕「继光哥」"),
    ("OUTPUT/_chk36/f2.jpg", "镜 36 暗场短字幕「你听见没」"),
    ("OUTPUT/_chk36/f3.jpg", "镜 36 暗场短字幕"),
]
# ★ f1 是**淡出中间帧**（字幕半透明，每行仅 ~23 px ≥205）——
#   单帧允许漏；扫描器按镜**多时间点采样**，只要有一帧命中即判该镜有字幕。
OPTIONAL = [
    ("OUTPUT/_chk36/f1.jpg", "镜 36 淡出中帧（允许漏）"),
]
NEGATIVE = [
    ("OUTPUT/_fullcut_check/s112_0.jpg", "镜 112 教室（无字）"),
    ("OUTPUT/_fullcut_check/s085_0.jpg", "镜85 底部条带 110px（无字，验证分辨率无关）"),
    ("OUTPUT/_fullcut_check/s036_0.jpg", "镜 36 底部带（旧抽样，可能无字）"),
    # ★ v2 的误报源（2026-09-17 实锤：这两帧**无字但被判命中**）—— 必须常驻回归
    ("OUTPUT/_chk_fp/s02_2.0.jpg", "镜 02 妈妈明亮的脸（v2 误报源）"),
    ("OUTPUT/_chk_fp/s60_2.0.jpg", "镜 60 人脸暖色高光（v2 误报源）"),
]


def main():
    root = os.path.dirname(HERE)
    ok = bad = 0
    print("=== 正例（应命中 True）===")
    for rel, why in POSITIVE:
        p = os.path.join(root, rel)
        if not os.path.exists(p):
            print("  [skip] %s 不存在" % rel)
            continue
        hit = bool(M.scan_frame(load(p))[0])
        print("  %-6s %-40s %s" % ("HIT" if hit else "MISS", why, rel))
        if hit:
            ok += 1
        else:
            bad += 1
    print("\n=== 可选正例（淡出中帧，允许漏）===")
    for rel, why in OPTIONAL:
        p = os.path.join(root, rel)
        if not os.path.exists(p):
            print("  [skip] %s 不存在" % rel)
            continue
        hit = bool(M.scan_frame(load(p))[0])
        print("  %-6s %-40s %s" % ("HIT" if hit else "miss", why, rel))
    print("\n=== 负例（应不命中 False）===")
    for rel, why in NEGATIVE:
        p = os.path.join(root, rel)
        if not os.path.exists(p):
            print("  [skip] %s 不存在" % rel)
            continue
        hit = bool(M.scan_frame(load(p))[0])
        print("  %-6s %-40s %s" % ("FALSE+" if hit else "ok", why, rel))
        if not hit:
            ok += 1
        else:
            bad += 1
    print("\n结果：%d 通过 / %d 不通过" % (ok, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
