# -*- coding: utf-8 -*-
"""快速核实：每镜「音频比画面长出来的那段」是编码器补零（静音）还是真声音？

对每个片段：
  D = 帧数 / 24（画面长度）
  a = 解码整条音轨（32 kHz 单声道）
  tail = a[D*32000 : ]    ← 就是 concat 会多推出去的那一段
打印 tail 的 RMS 与整条 RMS 的差；差值很大（如 < −40 dB）⇒ 是补零静音。
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
SR = 32000
SAMP = [
    ("07_rice_field", "55_yuan_pulls_normal_rice_00008_.mp4"),
    ("07_rice_field", "57_zhang_shuyang_leans_in_00008_.mp4"),
    ("07_rice_field", "59_liu_siqi_answers_quietly_00003_.mp4"),
    ("07_rice_field", "60_yuan_talks_about_hungry_people_00007_.mp4"),
    ("07_rice_field", "61_liu_sicheng_blurts_out_00009_.mp4"),
    ("07_rice_field", "74_white_out_diary_card_act2_00004_.mp4"),
    ("01_paper_plane", "02_mother_looking_at_girl_00001_.mp4"),
    ("05_classroom_night", "126_final_freeze_four_backs_00003_.mp4"),
]


def nframes_and_pcm(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-count_frames", "-show_entries",
                        "stream=nb_read_frames", "-of", "csv=p=0", p],
                       capture_output=True, text=True)
    try:
        nf = int(r.stdout.strip())
    except ValueError:
        nf = 0
    r2 = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-vn", "-ac", "1",
                         "-ar", str(SR), "-f", "f32le", "-"], capture_output=True)
    return nf, np.frombuffer(r2.stdout, dtype=np.float32)


def db(x):
    return 20 * np.log10(float(np.sqrt(np.mean(x * x))) + 1e-12)


print("%-4s %10s %10s %8s %9s %9s %9s  %s"
      % ("镜", "画面(s)", "音轨(s)", "多出ms", "整体RMS", "尾部RMS", "尾部峰值", "判定"))
for d, fn in SAMP:
    p = os.path.join(OUT, d, "video", fn)
    if not os.path.exists(p):
        print("缺 %s" % p)
        continue
    nf, a = nframes_and_pcm(p)
    D = nf / 24.0
    cut = int(round(D * SR))
    tail = a[cut:]
    ex_ms = len(tail) / SR * 1000
    body_db = db(a)
    tail_db = db(tail) if len(tail) else -999
    peak = float(np.abs(tail).max()) if len(tail) else 0.0
    verdict = ("静音（编码器补零）" if (len(tail) == 0 or tail_db < body_db - 40)
               else "!! 有声音")
    print("%-4s %10.4f %10.4f %8.1f %9.1f %9.1f %9.5f  %s"
          % (fn.split("_")[0], D, len(a) / SR, ex_ms, body_db, tail_db, peak,
             verdict))
