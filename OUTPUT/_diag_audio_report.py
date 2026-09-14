# -*- coding: utf-8 -*-
"""对 OUTPUT/bgm/*.mp3 做客观体检：时长 / 整体RMS / peak / 逐段RMS / 过零率。

判读：ZCR 高（>0.02）＝宽频噪音状（风声、群杂、蝉鸣）；ZCR 很低（<0.01）＝单一音调。
RMS 变异大 ＝ 有自然起伏；变异极小 ＝ 可能是持续性嗡鸣。

用法： py -3.10 OUTPUT/_diag_audio_report.py
"""
import io
import math
import os
import re
import struct
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
D = r"E:\code\stem_fest\OUTPUT\bgm"
COMFY = r"E:\code\ComfyUI\output\audio"

files = sorted(f for f in os.listdir(D) if f.endswith(".mp3"))

out = []
w = out.append
w("# ACE-Step 环境音体检报告")
w("")
w("| 文件 | 时长 | 整体RMS | peak | 段RMS变异 | 平均ZCR | 判读 |")
w("|---|---|---|---|---|---|---|")

for f in files:
    p = os.path.join(D, f)
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", p, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
        capture_output=True).stdout
    n = len(raw) // 2
    if n == 0:
        w("| %s | 解码失败 | | | | | |" % f)
        continue
    s = struct.unpack("<%dh" % n, raw)
    HOP = 8000

    def rms(seg):
        return math.sqrt(sum((x / 32768.0) ** 2 for x in seg) / max(1, len(seg)))

    def zcr(seg):
        c = sum(1 for i in range(1, len(seg)) if (seg[i - 1] < 0) != (seg[i] < 0))
        return c / float(len(seg))

    segs = [s[i:i + HOP] for i in range(0, n - HOP + 1, HOP)]
    rs = [rms(x) for x in segs]
    zs = [zcr(x) for x in segs]
    mean_r = sum(rs) / len(rs)
    var = (max(rs) - min(rs)) / mean_r if mean_r else 0
    z = sum(zs) / len(zs)
    peak = max(abs(x) for x in s) / 32768.0

    tone = "宽频噪音状" if z > 0.02 else ("偏低·疑似音调" if z < 0.01 else "中等")
    dyn = "有起伏" if var > 1.0 else ("偏平" if var < 0.3 else "中等")
    w("| `%s` | %.1fs | %.4f | %.3f | %.2f (%s) | %.4f | %s |" % (
        f, n / 16000.0, mean_r, peak, var, dyn, z, tone))

w("")
w("> 判读口径：**ZCR 高 = 宽频噪音**（风声/群杂/蝉鸣等真实环境声该有的样子）；")
w("> **ZCR 极低 = 单一音调**（可能被生成成音乐而非氛围）。")
w("> **段RMS变异大 = 有自然呼吸起伏**；极小 = 像持续嗡鸣/循环旋钮。")

txt = "\n".join(out)
io.open(r"E:\code\stem_fest\OUTPUT\_audio_report.md", "w", encoding="utf-8").write(txt + "\n")
print(txt)
