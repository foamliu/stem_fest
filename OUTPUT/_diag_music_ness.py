# -*- coding: utf-8 -*-
"""判断一段音频"有多像音乐"：算 12 音平均律的色度（chroma）能量分布。

原理：音乐 → 音高集中在少数 12 个音级上（色度分布尖、熵低）；
      噪音型音效（风/雨/群杂）→ 能量平铺在所有频段（色度分布平、熵高）。
用法： py -3.10 OUTPUT/_diag_music_ness.py
"""
import io
import math
import os
import struct
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
D = r"E:\code\stem_fest\OUTPUT\bgm"
N = 4096
SR = 16000


def chroma_entropy(path):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR),
         "-f", "s16le", "-"], capture_output=True).stdout
    n = len(raw) // 2
    s = [x / 32768.0 for x in struct.unpack("<%dh" % n, raw)]

    # Goertzel：对每个 12 音级的目标频率测能量（覆盖 4 个八度）
    # 音级 A4=440，半音比 2^(1/12)
    import cmath
    win = [0.5 - 0.5 * math.cos(2 * math.pi * i / (N - 1)) for i in range(N)]
    acc = [0.0] * 12
    frames = 0
    for st in range(0, n - N, N * 4):
        seg = [s[st + i] * win[i] for i in range(N)]
        for deg in range(12):
            e = 0.0
            for octv in (1, 2, 3, 4):
                f = 220.0 * (2 ** (deg / 12.0)) * octv
                if f > SR / 2.2:
                    continue
                w = 2 * math.pi * f / SR
                c = cmath.exp(-1j * w)
                z1 = 0j
                for x in seg:
                    z1 = x + z1 * c
                e += abs(z1) ** 2
            acc[deg] += e
        frames += 1
    tot = sum(acc) or 1.0
    p = [a / tot for a in acc]
    ent = -sum(x * math.log(x + 1e-12) for x in p) / math.log(12)
    return ent, [round(x, 3) for x in p]


print("| 文件 | 色度熵(0=纯音乐,1=纯噪音) | 判读 |")
print("|---|---|---|")
for f in sorted(os.listdir(D)):
    if not f.endswith(".mp3"):
        continue
    ent, p = chroma_entropy(os.path.join(D, f))
    verdict = ("✅ 噪音型（像音效）" if ent > 0.93 else
               ("⚠️ 偏音乐" if ent > 0.86 else "❌ 明显音乐化"))
    print("| `%s` | %.4f | %s |" % (f, ent, verdict))
