# -*- coding: utf-8 -*-
"""配乐体检：这次要看「有多音乐」。

与 _diag_music_ness.py 相反 —— BGM 该**熵低**（音高集中在调内）。
另测：调性稳定性（前后半段色度是否一致）+ 动态（有无人声包络段）。

用法： py -3.10 OUTPUT/_diag_bgm_report.py
"""
import cmath
import io
import math
import os
import struct
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
D = r"E:\code\stem_fest\OUTPUT\bgm"
SR = 16000
N = 4096
WIN = [0.5 - 0.5 * math.cos(2 * math.pi * i / (N - 1)) for i in range(N)]


def decode(p):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", p, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
        capture_output=True).stdout
    return [x / 32768.0 for x in struct.unpack("<%dh" % (len(raw) // 2), raw)]


def chroma(s, st):
    seg = [s[st + i] * WIN[i] for i in range(N)]
    acc = [0.0] * 12
    for deg in range(12):
        for octv in (1, 2, 3, 4):
            f = 220.0 * (2 ** (deg / 12.0)) * octv
            if f > SR / 2.2:
                continue
            c = cmath.exp(-1j * 2 * math.pi * f / SR)
            z = 0j
            for x in seg:
                z = x + z * c
            acc[deg] += abs(z) ** 2
    return acc


def entropy(p):
    tot = sum(p) or 1.0
    p = [a / tot for a in p]
    return -sum(x * math.log(x + 1e-12) for x in p) / math.log(12)


def keyname(p):
    """最可能的调（大调音阶模板相关）。"""
    MAJ = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    best, bi = -1e9, 0
    for r in range(12):
        v = sum(p[(r + i) % 12] * MAJ[i] for i in range(12))
        if v > best:
            best, bi = v, r
    return names[bi] + " major"


print("| 文件 | 时长 | 色度熵(越低越音乐) | 推定调性 | 前后段调性一致 | 段RMS变异 |")
print("|---|---|---|---|---|---|")
for f in sorted(os.listdir(D)):
    if not f.endswith(".mp3"):
        continue
    p = os.path.join(D, f)
    s = decode(p)
    n = len(s)
    if n < N * 8:
        continue
    half = n // 2
    a1, a2 = [0.0] * 12, [0.0] * 12
    for st in range(0, n - N, N * 8):
        c = chroma(s, st)
        tgt = a1 if st < half else a2
        for i in range(12):
            tgt[i] += c[i]
    tot = [a1[i] + a2[i] for i in range(12)]
    ent = entropy(tot)
    k_all = keyname(tot)
    k1, k2 = keyname(a1), keyname(a2)
    HOP = 8000
    rs = [math.sqrt(sum((s[i + j] ** 2) for j in range(HOP)) / HOP)
          for i in range(0, n - HOP, HOP)]
    mean_r = sum(rs) / len(rs)
    var = (max(rs) - min(rs)) / mean_r if mean_r else 0
    print("| `%s` | %.0fs | %.4f | %s | %s | %.2f |" % (
        f, n / SR, ent, k_all, "✅" if k1 == k2 else "⚠️ %s→%s" % (k1, k2), var))
