# -*- coding: utf-8 -*-
"""汇总 `_scan_text_rows.py` 的输出：按"命中帧数"排序，找出**最可能是真字幕**的镜。

★ 为什么要排序而不是只看"命中/未命中"
    新版检测器（v2 字形判据）敏感度大幅提高 —— 从 0/126 升到能抓到镜 36，
    但也会把**白校服高光、桌面反光、屏幕 UI** 误报进来。
    ⇒ 真字幕的指纹是：**同一镜内多帧连续命中** + **y 位置稳定** + **列段数稳定**。
      偶发 1–2 帧命中的多半是误报。

用法：
    py -3.10 OUTPUT/_scan_text_rows.py --every=0.35 > OUTPUT/_scan.txt 2>&1
    py -3.10 OUTPUT/_scan_summary.py
"""
from __future__ import annotations
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def read_any(path):
    """读文件，自动识别 UTF-16 / UTF-8（PowerShell `>` 重定向默认产出 UTF-16LE）。"""
    raw = open(path, "rb").read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", errors="replace")
    for enc in ("utf-8", "gbk", "utf-16"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="replace")


def main():
    p = os.path.join(HERE, "_scan.txt")
    if not os.path.exists(p):
        print("先跑：py -3.10 OUTPUT/_scan_text_rows.py --every=0.35 | Tee-Object OUTPUT\\_scan.txt")
        return 1
    txt = read_any(p)
    # 形如：`036_xxx.mp4   3.04s  🔴 疑似   4 处`（emoji 在不同 locale 下会被转义）
    # ⇒ 用"文件名 + 时长s + <任意> + N 处"的宽松式匹配，不依赖 emoji 本身。
    rows = []
    for m in re.finditer(r"^([0-9]{2,3}_\S+\.mp4)\s+([\d.]+)s\s+[^\n]*?(\d+)\s+处\s*$", txt, re.M):
        rows.append((m.group(1), float(m.group(2)), int(m.group(3))))
    rows.sort(key=lambda r: -r[2])
    print("疑似命中 %d 镜（按命中帧数降序）" % len(rows))
    print("-" * 74)
    for f, dur, n in rows:
        tag = "★★ 高置信" if n >= max(3, dur * 1.5) else ("★ 中等" if n >= 3 else "  低（多半误报）")
        print("%-56s %5.2fs  %3d 帧  %s" % (f, dur, n, tag))
    return 0


if __name__ == "__main__":
    sys.exit(main())
