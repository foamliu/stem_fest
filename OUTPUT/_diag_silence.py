# -*- coding: utf-8 -*-
"""精确定位：concat 产物里的**数字静音**（全 0 采样）落在哪、有多长。

若 concat 滤镜把每段音频「补齐」到某个长度，就会在段边界插入一段纯 0 采样。
AAC 是有损编码，但纯 0 输入解出来仍是极小的值 ⇒ 用阈值检测。
"""
import os
import subprocess
import sys

import numpy as np

for _s in ("stdout", "stderr"):
    try:
        getattr(sys, _s).reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(ROOT, "OUTPUT", "_diag_concat")
SR = 32000


def pcm(path):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1",
                        "-ar", str(SR), "-f", "f32le", "-"],
                       capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.float32)


def scan(tag, path):
    x = pcm(path)
    print("\n== %s ==  解码 %.4f s（%d 采样）" % (tag, len(x) / SR, len(x)))
    thr = 1e-5
    q = np.abs(x) < thr
    # 找 < 5ms 的连续静音/极低电平段（补静音的指纹；真实环境底噪不会这么整齐）
    idx = np.flatnonzero(q)
    if len(idx) == 0:
        print("  未发现静音")
        return
    runs = []
    st = idx[0]
    prev = idx[0]
    for i in idx[1:]:
        if i != prev + 1:
            runs.append((st, prev))
            st = i
        prev = i
    runs.append((st, prev))
    # 只报 20ms 以上 的（低于此多半是语音间隙）
    big = [(a, b) for a, b in runs if (b - a + 1) >= int(0.010 * SR)]
    print("  ≥10ms 的近静音段 %d 个（总静音 %.3fs）" % (
        len(big), sum(b - a + 1 for a, b in big) / SR))
    for a, b in big[:40]:
        print("    %8.4fs — %8.4fs   长 %6.1f ms" %
              (a / SR, (b + 1) / SR, (b - a + 1) / SR * 1000))


def main():
    for tag, f in [("A（现状：v/a 分开 concat）", "out_A.mp4"),
                   ("B（v=1:a=1 一起 concat）", "out_B.mp4")]:
        p = os.path.join(TMP, f)
        if os.path.exists(p):
            scan(tag, p)
        else:
            print("缺 %s" % p)
    print("\n源片段边界（章节起点）应为：0.0000 / 4.4583 / 8.9167 / 13.3750 / "
          "16.4167 / 18.7500 / 26.7500 s")


if __name__ == "__main__":
    main()
