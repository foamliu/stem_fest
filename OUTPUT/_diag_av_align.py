# -*- coding: utf-8 -*-
"""实测 v3：打印「源片段音频 ↔ 成片同一镜窗口」的对齐曲线（不看单一峰）。

对每一镜：
  窗口 = 成片 [t0-0.5s, t0+L+0.5s]
  对位移 s ∈ [-500ms, +500ms]（25ms 步）：
      源包络 vs 窗口包络（起点 500ms + s）算归一化相关
  打印 s 与相关值 ⇒ 直接看真实峰在哪一格。

若音频与画面同步，峰应在 s = 0。
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
OUT = os.path.join(ROOT, "OUTPUT")
MOVIE = os.path.join(OUT, "full_cut_scene_v2.mp4")
SR = 32000
WIN = 320          # 10 ms


def pcm(path, ss=None, t=None):
    cmd = ["ffmpeg", "-v", "error"]
    if ss is not None:
        cmd += ["-ss", "%.4f" % ss]
    cmd += ["-i", path]
    if t is not None:
        cmd += ["-t", "%.4f" % t]
    cmd += ["-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    r = subprocess.run(cmd, capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.float32)


def env(x):
    n = len(x) // WIN * WIN
    e = np.abs(x[:n]).reshape(-1, WIN).mean(axis=1)
    return e


def hp(e, k=5):
    """去掉慢变底噪：env - 移动平均 ⇒ 突出语音起落"""
    ker = np.ones(k) / k
    return e - np.convolve(e, ker, mode="same")


def table(shot, t0, d, fname):
    src = os.path.join(OUT, d, "video", fname)
    if not os.path.exists(src):
        print("镜 %d：缺 %s" % (shot, src))
        return
    a = env(pcm(src))
    L = len(a)
    b = env(pcm(MOVIE, ss=t0 - 0.5, t=L * 0.01 + 1.0))
    ah, bh = hp(a), hp(b)
    off_center = 50          # 500ms = 50 格
    print("镜 %-4d 源 %.3fs  窗口 %.3fs" % (shot, L * 0.01, len(b) * 0.01))
    line = []
    best = (None, -9)
    for step in range(-20, 21):          # -500ms .. +500ms，25ms 步
        s = step * 2                     # 2 格 = 20ms? → 下面用 0.025s 步进
    for ms in range(-500, 501, 25):
        g = int(round(ms / 10.0))
        st = off_center + g
        if st < 0 or st + L > len(bh):
            continue
        x, y = bh[st:st + L], ah
        x, y = x - x.mean(), y - y.mean()
        den = np.sqrt((x * x).sum() * (y * y).sum())
        c = float((x * y).sum() / den) if den > 0 else 0.0
        line.append((ms, c))
        if c > best[1]:
            best = (ms, c)
    print("  位移(ms): " + " ".join("%5d" % m for m, _ in line))
    print("  相关    : " + " ".join("%5.2f" % c for _, c in line))
    print("  ⇒ 最佳对齐 %+d ms（相关 %.2f）；s=0 处相关 %.2f"
          % (best[0], best[1], dict(line).get(0, float("nan"))))
    print()


SHOTS = [
    (2, 3.0417, "01_paper_plane", "02_mother_looking_at_girl_00001_.mp4"),
    (59, 223.1667, "07_rice_field", "59_liu_siqi_answers_quietly_00003_.mp4"),
    (60, 225.5000, "07_rice_field", "60_yuan_talks_about_hungry_people_00007_.mp4"),
    (61, 233.5000, "07_rice_field", "61_liu_sicheng_blurts_out_00009_.mp4"),
    (120, None, "05_classroom_night", None),
]


def main():
    for shot, t0, d, fname in SHOTS:
        if fname is None:
            continue
        table(shot, t0, d, fname)


if __name__ == "__main__":
    main()
