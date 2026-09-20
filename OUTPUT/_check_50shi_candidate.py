# -*- coding: utf-8 -*-
"""50 式候选图 · 红色残留 + 人脸年龄 体检（2026-09-20）。

★ 为什么要这个脚本
    肉眼判断「还有没有红」在本项目**反复出错**（README §6.10.17）：
      · 我第一次看 `young_soldier_50shi_v02` 觉得「明显年轻了」，
        但 InsightFace 读出 **29 岁**，和 v01 的 28 岁几乎一样 ⇒ 肉眼不可靠。
    所以本脚本把两件事都变成**数值**：
      ① 高饱和红像素占比（沿用 `_diag_ref50_red.py` 的阈值口径）
      ② 人脸年龄估计（调 `_face_identity.py`，它自带 ComfyUI venv 切换）

★ 判据（红）
    `red_ratio` < **0.05%**   → ✅ 干净
    0.05% ~ 0.30%            → ⚠️ 有零星暖色被误计（需看图）
    > 0.30%                  → ❌ 存在成片红布（领章/帽徽/肩袢）

用法
    py -3.10 OUTPUT/_check_50shi_candidate.py OUTPUT/uniform_50shi/frames_*/f020.png
    py -3.10 OUTPUT/_check_50shi_candidate.py --no-age FILE [FILE...]
"""
from __future__ import annotations

import argparse
import glob as globmod
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACE_TOOL = os.path.join(ROOT, "OUTPUT", "_face_identity.py")

# 与 _diag_ref50_red.py 保持同一口径，便于跨脚本对比
RED_HUE_HI = 20        # 色相 < 20° 视为红侧
RED_HUE_LO = 300       # 色相 > 300° 视为红侧
# ★ 2026-09-20 实测修正：0.42 会把**暖调光照下的肤色**误计为红
#   （`_diag_50shi_red.py` 实测：宽口径红像素里 **34.9%** 同时落在暖肤色带内）。
#   「实心红布」（领章/帽徽/肩袢）的饱和显著更高 ⇒ 用 **0.62** 作判据，
#   与 `_diag_50shi_red.py` 的 `strong` 指标一致。
RED_SAT_MIN = 0.62
RED_VAL_MIN = 40

OK_RATIO = 0.05        # < 0.05% 判干净
WARN_RATIO = 0.30      # > 0.30% 判存在成片红布


def red_stats(path: str) -> dict:
    im = Image.open(path).convert("RGB")
    hsv = np.asarray(im.convert("HSV")).astype(np.float32)
    h = hsv[..., 0] * 360 / 255.0
    s = hsv[..., 1] / 255.0
    v = hsv[..., 2] / 255.0
    m = ((h < RED_HUE_HI) | (h > RED_HUE_LO)) & (s > RED_SAT_MIN) & (v * 255 > RED_VAL_MIN)
    n = int(m.sum())
    ratio = 100.0 * n / m.size
    out = {
        "file": os.path.relpath(path, ROOT),
        "size": "%dx%d" % im.size,
        "red_px": n,
        "red_ratio_pct": round(ratio, 4),
    }
    if ratio > WARN_RATIO:
        out["red_verdict"] = "FAIL"
    elif ratio > OK_RATIO:
        out["red_verdict"] = "WARN"
    else:
        out["red_verdict"] = "OK"
    return out


def ages(paths: list[str]) -> dict:
    """调 `_face_identity.py audit` 拿年龄（它自己会切到 ComfyUI venv）。"""
    if not os.path.exists(FACE_TOOL):
        return {}
    tmp = os.path.join(ROOT, "OUTPUT", "_check_50shi_age.json")
    cmd = [sys.executable, FACE_TOOL, "audit"]
    for p in paths:
        cmd += ["--glob", os.path.relpath(p, ROOT).replace("\\", "/")]
    cmd += ["--json", tmp]
    try:
        subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=900)
        if not os.path.exists(tmp):
            return {}
        d = json.load(open(tmp, encoding="utf-8"))
        rows = d if isinstance(d, list) else d.get("rows", d.get("images", []))
        return {os.path.basename(r.get("file", "")): r.get("age_max") for r in rows}
    except Exception as e:  # noqa: BLE001
        print("[warn] 年龄检测失败: %s" % e)
        return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", help="图片路径或通配符")
    ap.add_argument("--no-age", action="store_true", help="跳过年龄检测（快）")
    ap.add_argument("--age", type=int, default=None, help="年龄上限告警阈值（默认 26）")
    args = ap.parse_args()

    paths = []
    for p in (args.paths or ["OUTPUT/uniform_50shi/frames_*/f020.png"]):
        hits = globmod.glob(p)
        paths.extend(hits if hits else ([p] if os.path.exists(p) else []))
    paths = sorted({os.path.abspath(p) for p in paths})
    if not paths:
        print("没有匹配到图片")
        return 1

    amap = {} if args.no_age else ages(paths)
    age_cap = 26 if args.age is None else args.age

    print("=" * 78)
    print("%-52s %9s  %5s  %s" % ("文件", "红占比", "年龄", "判定"))
    print("-" * 78)
    bad = 0
    for p in paths:
        r = red_stats(p)
        age = amap.get(os.path.basename(p))
        flags = []
        if r["red_verdict"] != "OK":
            flags.append("红=%s" % r["red_verdict"])
        if age is not None and age > age_cap:
            flags.append("年龄>%d" % age_cap)
        if flags:
            bad += 1
        print("%-52s %8.4f%%  %5s  %s"
              % (r["file"][-52:], r["red_ratio_pct"],
                 "-" if age is None else age,
                 "✅ OK" if not flags else "⚠️ " + " ".join(flags)))
    print("-" * 78)
    print("合计 %d 张，需关注 %d 张" % (len(paths), bad))
    print("（红判据：<%.2f%% 干净 / >%.2f%% 有成片红布；年龄上限 %d）"
          % (OK_RATIO, WARN_RATIO, age_cap))
    return 0


if __name__ == "__main__":
    sys.exit(main())
