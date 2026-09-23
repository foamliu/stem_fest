# -*- coding: utf-8 -*-
"""诊断：full_cut_scene_v2 的音画漂移是否由 `_concat_video.py` 的
「视频轨与音频轨分别 concat」造成。

原理
----
`_concat_video.py` 的烧号路径里 filtergraph 是：

    [v0][v1]...[vN]concat=n=126:v=1:a=0[v];
    [a0][a1]...[aN]concat=n=126:v=0:a=1[a]

即**视频段**与**音频段**各自独立拼接：
  · 视频段时间轴 = Σ(各段解码帧数) / 24
  · 音频段时间轴 = Σ(各段音频采样数) / 32000
只要某段的「音频时长 ≠ 视频时长」，两者的累计时间轴就会分叉 ⇒
后段人声相对画面**整体平移**（越往后越明显）。

本脚本对章节表里实际用到的 126 个源片段逐个探测
（视频帧数 / 音频采样数），模拟两条时间轴，算出每个镜号处的漂移量。
"""

import json
import os
import re
import subprocess
import sys

for _s in ("stdout", "stderr"):
    try:
        getattr(sys, _s).reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")
CHAP = os.path.join(OUT, "_concat_chapters.txt")
DIRS = ["01_paper_plane", "03_classroom_day", "06_trench",
        "07_rice_field", "08_train_dining", "05_classroom_night"]
RANGES = {
    "01_paper_plane": (1, 9),
    "03_classroom_day": (10, 18),
    "06_trench": (19, 46),
    "07_rice_field": (47, 74),
    "08_train_dining": (75, 105),
    "05_classroom_night": (106, 126),
}
INTEREST = [59, 60, 61]


def probe(p):
    """返回 (视频帧数, 视频时长, 音频时长, 音频采样率, 音频start_time)"""
    cmd = ["ffprobe", "-v", "error", "-of", "json", "-show_streams",
           "-show_format", "-count_frames", p]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    d = json.loads(r.stdout or "{}")
    vf = vd = ad = sr = ast = None
    for s in d.get("streams", []):
        if s.get("codec_type") == "video":
            vf = int(s.get("nb_read_frames") or 0)
            vd = float(s.get("duration") or 0)
        elif s.get("codec_type") == "audio":
            ad = float(s.get("duration") or 0)
            sr = int(s.get("sample_rate") or 0)
            ast = float(s.get("start_time") or 0)
    return vf, vd, ad, sr, ast


def find(shot, fname):
    for d in DIRS:
        lo, hi = RANGES[d]
        if not (lo <= shot <= hi):
            continue
        p = os.path.join(OUT, d, "video", fname)
        if os.path.exists(p):
            return p
    return None


def main():
    rows = []
    for line in open(CHAP, encoding="utf-8"):
        if line.startswith("#"):
            continue
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 5:
            continue
        rows.append((int(parts[0]), float(parts[1]), float(parts[2]),
                     float(parts[3]), parts[4]))

    print("源片段逐个探测（%d 镜）…" % len(rows))
    vt = at = 0.0
    drift_pts = {}
    worst = []
    for shot, dur, t0, t1, fname in rows:
        p = find(shot, fname)
        if p is None:
            print("  !! 镜 %d 找不到 %s" % (shot, fname))
            continue
        vf, vd, ad, sr, ast = probe(p)
        v_dur = vf / 24.0 if vf else (vd or 0.0)
        a_dur = ad or 0.0
        vt += v_dur
        at += a_dur
        drift_pts[shot] = (vt, at, at - vt, v_dur - a_dur, vf, a_dur, fname)
        worst.append((abs(v_dur - a_dur), shot, v_dur, a_dur, sr, ast))

    print("\n%-5s %10s %10s %10s %10s  %s"
          % ("镜号", "视频累计", "音频累计", "漂移(s)", "本镜音视差", "文件"))
    for shot in sorted(drift_pts):
        vt_, at_, dr, dd, vf, adur, fname = drift_pts[shot]
        flag = "  <<<" if shot in INTEREST else ""
        if shot <= 5 or shot in INTEREST or shot in (74, 105, 126) \
                or abs(dd) > 0.1:
            print("%-5d %10.3f %10.3f %+10.3f %+10.3f  %s%s"
                  % (shot, vt_, at_, dr, dd, fname, flag))

    print("\n—— 每镜「视频时长 − 音频时长」偏差最大的 15 个 ——")
    worst.sort(reverse=True)
    for dd, shot, vd, ad, sr, ast in worst[:15]:
        print("  镜 %-4d 视频 %7.4fs  音频 %7.4fs  差 %+7.4fs  sr=%s start=%s"
              % (shot, vd, ad, vd - ad, sr, ast))

    if INTEREST:
        print("\n—— 关注镜号 ——")
        for shot in INTEREST:
            if shot in drift_pts:
                _, _, dr, dd, vf, adur, fname = drift_pts[shot]
                print("  镜 %-4d 累计漂移(音频领先) = %+.3f s   本镜差 %+.4f s  %s"
                      % (shot, dr, dd, fname))

    tot_drift = max(d[2] for d in drift_pts.values())
    print("\n全片最大累计漂移：%+.3f s" % tot_drift)
    print("（正 = 音频轨在成片里相对画面**提前**；负 = 滞后）")


if __name__ == "__main__":
    main()
