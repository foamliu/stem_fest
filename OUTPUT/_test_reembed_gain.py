#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证「小脸裁切重提特征」对可比性的改善（离线，不需要 ComfyUI 服务）。

做法：从既有 _face_ledger_*.json 里取出「脸很小、原判 DIFFERENT」的镜，
对同一帧分别用 reembed_px=0（整帧提特征，= 旧口径）与 reembed_px=512（裁切重提）
算出与参考图的余弦相似度，看是否更接近主参考（同人应更高）。

用法（必须用 ComfyUI venv 解释器）：
  E:\\code\\ComfyUI\\venv\\Scripts\\python.exe OUTPUT/_test_reembed_gain.py
"""
from __future__ import annotations

import glob
import json
import math
import os
import sys
import types

COMFY = r"E:\code\ComfyUI"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, COMFY)
fp = types.ModuleType("folder_paths")
fp.get_input_directory = lambda: os.path.join(COMFY, "input")
fp.get_output_directory = lambda: os.path.join(COMFY, "output")
sys.modules["folder_paths"] = fp
sys.path.insert(0, os.path.join(COMFY, "custom_nodes"))
from comfyui_media_audit.nodes import InsightFaceFeature  # noqa: E402


def cos(a, b):
    s = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return s / (na * nb) if na and nb else 0.0


def first_emb(node, path, reembed):
    out, _ = node.extract(path, "buffalo_l", "CPU", 640, 0.3, True, reembed, 4)
    d = json.loads(out)
    if not d.get("ok"):
        return None, None
    img = d["images"][0]
    if not img["face_count"]:
        return None, img
    return img["faces"][0], img


def main():
    node = InsightFaceFeature()
    picks = []
    for lf in sorted(glob.glob(os.path.join(ROOT, "OUTPUT", "_face_ledger_*.json"))):
        for row in json.load(open(lf, encoding="utf-8")).get("rows", []):
            frame = os.path.join(ROOT, row.get("frame", ""))
            if row.get("frame_face_h", 999) < 250 and os.path.exists(frame):
                row["_frame_abs"] = frame
                picks.append(row)
    picks.sort(key=lambda r: r.get("frame_face_h", 999))
    print(f"候选（脸高 < 250 px **且帧文件仍在**）共 {len(picks)} 个，取最小的 8 个做对照\n")
    print(f"{'镜':>4} {'脸高px':>7} {'旧cos':>7} {'新cos':>7} {'变化':>7}  {'参考图':<38}")
    gains = []
    for row in picks[:8]:
        frame = row["_frame_abs"]
        ref = None
        for pat in (f"ASSETS/CHARACTERS/**/{row['ref']}", f"ASSETS/**/{row['ref']}"):
            hit = glob.glob(os.path.join(ROOT, pat), recursive=True)
            if hit:
                ref = hit[0]
                break
        if not (os.path.exists(frame) and ref):
            continue
        rf, _ = first_emb(node, ref, 512)
        f0, _ = first_emb(node, frame, 0)
        f1, info = first_emb(node, frame, 512)
        if not (rf and f0 and f1):
            print(f"{row['shot']:>4} {'-':>7}  （无法提特征，跳过）")
            continue
        c0, c1 = cos(rf["embedding"], f0["embedding"]), cos(rf["embedding"], f1["embedding"])
        gains.append(c1 - c0)
        tag = "↑" if c1 > c0 else "↓"
        print(f"{row['shot']:>4} {row.get('frame_face_h', 0):>7.0f} {c0:>7.3f} {c1:>7.3f} "
              f"{tag}{abs(c1 - c0):>6.3f}  {row['ref'][:36]:<38}")
    if gains:
        print(f"\n平均变化 {sum(gains) / len(gains):+.3f}"
              f"（正 = 裁切重提后与参考更接近；样本 {len(gains)}）")
        print("注意：本对照只验证『方法是否改善可比性』，"
              "不代表小脸就能判定同一人 —— 仍需按 README §6.5 用相对排名 + 硬特征。")


if __name__ == "__main__":
    main()
