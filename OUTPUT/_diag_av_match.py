# -*- coding: utf-8 -*-
"""实测 v4：把源片段音频包络在成片音频包络上**大范围**搜索最佳对齐点。

输出每镜：最佳位移 s*、该处归一化相关、以及成片窗口 RMS（判断是否静音）。
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
MOVIE = (sys.argv[1] if len(sys.argv) > 1
         else os.path.join(OUT, "full_cut_scene_v2.mp4"))
if not os.path.isabs(MOVIE):
    MOVIE = os.path.join(ROOT, MOVIE)
CHAP = os.path.join(OUT, "_concat_chapters.txt")
SR = 32000
WIN = 320          # 10 ms
DIRS = ["01_paper_plane", "03_classroom_day", "06_trench",
        "07_rice_field", "08_train_dining", "05_classroom_night"]
RANGES = {
    "01_paper_plane": (1, 9), "03_classroom_day": (10, 18), "06_trench": (19, 46),
    "07_rice_field": (47, 74), "08_train_dining": (75, 105),
    "05_classroom_night": (106, 126),
}


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
    if n == 0:
        return np.zeros(0, np.float32)
    e = np.abs(x[:n]).reshape(-1, WIN).mean(axis=1)
    return e


def norm_corr(x, y):
    x = x - x.mean()
    y = y - y.mean()
    den = np.sqrt((x * x).sum() * (y * y).sum())
    return float((x * y).sum() / den) if den > 0 else 0.0


def main():
    rows = []
    for line in open(CHAP, encoding="utf-8"):
        if line.startswith("#"):
            continue
        p = line.rstrip("\n").split("\t")
        if len(p) >= 5:
            rows.append((int(p[0]), float(p[2]), float(p[3]), p[4]))

    print("解成片音轨包络 …")
    mv = env(pcm(MOVIE))
    print("  成片音频 %.3f s（%d 格）" % (len(mv) * 0.01, len(mv)))

    print("\n%-5s %9s %8s %8s %9s  %s"
          % ("镜号", "最佳位移", "相关", "s=0相关", "窗口RMS", "文件"))
    bad = []
    for shot, t0, t1, fname in rows:
        d = next(k for k, (lo, hi) in RANGES.items() if lo <= shot <= hi)
        src = os.path.join(OUT, d, "video", fname)
        if not os.path.exists(src):
            continue
        a = env(pcm(src))
        L = len(a)
        if L < 5:
            continue
        base = int(round(t0 / 0.01))
        # 搜索 -1.5s .. +4.5s
        best = (None, -9.0)
        c0 = None
        for off in range(-150, 451):          # 单位 10ms
            st = base + off
            if st < 0 or st + L > len(mv):
                continue
            c = norm_corr(mv[st:st + L], a)
            if off == 0:
                c0 = c
            if c > best[1]:
                best = (off * 10, c)
        win = mv[base:base + L] if base + L <= len(mv) else mv[base:]
        rms = 20 * np.log10(win.mean() + 1e-12)
        flag = ""
        if best[0] is not None and abs(best[0]) > 60:
            flag = "  <<<"
            bad.append((shot, best[0], best[1], rms))
        print("%-5d %8s ms %8.2f %8.2f %8.1f dB  %s%s"
              % (shot, "" if best[0] is None else "%+d" % best[0],
                 best[1], -9 if c0 is None else c0, rms, fname, flag))

    print("\n—— 偏移 > 60 ms 的镜（共 %d 个）——" % len(bad))
    for s, o, c, r in bad:
        print("  镜 %-4d 位移 %+5d ms  相关 %.2f  RMS %.1f dB" % (s, o, c, r))


if __name__ == "__main__":
    main()
