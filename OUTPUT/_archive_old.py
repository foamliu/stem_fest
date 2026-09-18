# -*- coding: utf-8 -*-
"""归档被取代的中间版本 —— 每个镜号只保留 mtime 最新的一个 mp4，其余移到 `_mid_` 前缀。

★ 为什么需要
    重跑会产生 `_00003_` / `_00004_` / `_00005_` … 多版并存。
    `_concat_video.py` 按 **mtime 最新** 选片，所以只要留下最新版就不会拼错；
    但目录里堆着几十个旧版会让人工复核（抽帧、ASR、对轴）看错文件。
    ⇒ 统一归档：旧版改名 `_mid_<原名>`，concat 的 glob `^(\d+)_` 不会匹配到它们。

用法：
    py -3.10 OUTPUT/_archive_old.py            # 预览
    py -3.10 OUTPUT/_archive_old.py --apply    # 落盘
    py -3.10 OUTPUT/_archive_old.py --keep=10  # 每镜保留最新 10 版（默认 1）
"""
from __future__ import annotations
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DIRS = ["01_paper_plane", "04_classroom_dusk", "06_trench",
        "07_rice_field", "08_train_dining", "05_classroom_night"]


def main():
    apply_ = "--apply" in sys.argv
    keep = 1
    for a in sys.argv[1:]:
        if a.startswith("--keep="):
            keep = int(a.split("=", 1)[1])

    total = 0
    for d in DIRS:
        p = os.path.join(HERE, d, "video")
        if not os.path.isdir(p):
            continue
        by = {}
        for f in os.listdir(p):
            if f.startswith("_mid_") or not f.endswith(".mp4"):
                continue
            m = re.match(r"^(\d{1,3})_", f)
            if not m:
                continue
            by.setdefault(int(m.group(1)), []).append(f)
        for n, files in sorted(by.items()):
            files.sort(key=lambda x: os.path.getmtime(os.path.join(p, x)), reverse=True)
            for f in files[keep:]:
                total += 1
                if apply_:
                    os.rename(os.path.join(p, f), os.path.join(p, "_mid_" + f))
                else:
                    print("  [%s] %s" % (d, f))
    print("\n%s %d 个中间版本" % ("已归档" if apply_ else "待归档（预览）", total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
