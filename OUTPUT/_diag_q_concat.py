# -*- coding: utf-8 -*-
"""定位机制：漂移是出在 **concat 滤镜** 还是 **AAC 编码/封装**？

做法：把同一条片段重复 N 次（内容完全相同 ⇒ 每一份的音频都应落在
「Σ前面各段帧数 / 24」处），分别输出
  · out_pcm.wav  （-c:a pcm_s16le，采样域精确，无编码器干扰）
  · out_aac.m4a  （-c:a aac 32k）
对两者查「第 k 份的音频实际开始于何处」，即可分离两层贡献。
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
TMP = os.path.join(OUT, "_diag_concat")
os.makedirs(TMP, exist_ok=True)
SR = 32000

SRC = os.path.join(OUT, "07_rice_field", "video",
                   "59_liu_siqi_answers_quietly_00003_.mp4")
CLIPS = [SRC, SRC, SRC]
GROUPS = {
    "A_pcm": None,      # 填下面
}


def pcm(path):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1",
                        "-ar", str(SR), "-f", "f32le", "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.float32)


def build(tag, acodec):
    fc = (";".join("[%d:v]copy[v%d];[%d:a]anull[a%d]" % (i, i, i, i)
                   for i in range(len(CLIPS))) + ";"
          + "".join("[v%d]" % i for i in range(len(CLIPS)))
          + "concat=n=%d:v=1:a=0[v];" % len(CLIPS)
          + "".join("[a%d]" % i for i in range(len(CLIPS)))
          + "concat=n=%d:v=0:a=1[a]" % len(CLIPS))
    fb = os.path.join(TMP, "fg_q_%s.txt" % tag)
    open(fb, "w", encoding="utf-8").write(fc)
    ext = ".wav" if acodec == "pcm_s16le" else ".m4a"
    out = os.path.join(TMP, "out_q_%s%s" % (tag, ext))
    fin = []
    for c in CLIPS:
        fin += ["-i", c]
    cmd = (["ffmpeg", "-y", "-v", "error"] + fin +
           ["-filter_complex_script", fb, "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-crf", "30", "-preset", "ultrafast",
            "-c:a", acodec] + (["-ar", "32000"] if acodec == "aac" else []) + [out])
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode:
        print("!! %s 失败 %s" % (tag, r.stderr[:300]))
        return None
    return out


def content_offset(mixed, ref, base_s, span=0.3):
    """在 mixed 里找 ref 的内容出现在 base_s 附近±span 的精确位置（采样级）。"""
    b = int((base_s - span) * SR)
    e = int((base_s + span) * SR)
    seg = mixed[b:e].copy()
    n = len(ref)
    if len(seg) < n:
        return None
    best = (0, -1e18)
    # 用 1ms 步粗搜 + 包络，再用波形精搜
    for lag in range(0, len(seg) - n + 1, 32):
        x = seg[lag:lag + n]
        c = float(np.dot(x, ref))
        if c > best[1]:
            best = (lag, c)
    l0 = max(0, best[0] - 64)
    l1 = min(len(seg) - n, best[0] + 64)
    best2 = (0, -1e18)
    for lag in range(l0, l1 + 1):
        x = seg[lag:lag + n]
        c = float(np.dot(x, ref))
        if c > best2[1]:
            best2 = (lag, c)
    lag = best2[0]
    abs_s = (b + lag) / SR
    return abs_s - base_s, best2[1] / (np.linalg.norm(seg[l0:l0 + n]) * np.linalg.norm(ref) + 1e-9)


def main():
    ref = pcm(SRC)
    # 源片段帧数 → 每段在成片里的时长
    r = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams",
                        "v:0", "-show_entries", "stream=nb_read_frames",
                        "-of", "csv=p=0", SRC], capture_output=True, text=True)
    nf = int(r.stdout.strip())
    seg = nf / 24.0
    print("源片段 %d 帧 ⇒ 每段 %.4f s；片段音频 %.4f s"
          % (nf, seg, len(ref) / SR))

    for tag, ac in [("pcm", "pcm_s16le"), ("aac", "aac")]:
        out = build(tag, ac)
        if not out:
            continue
        m = pcm(out)
        print("\n== %s ==  解码 %.4f s（%d 采样；期望内容 %.4f s）"
              % (tag, len(m) / SR, len(m), seg * 3))
        for k in range(3):
            res = content_offset(m, ref, k * seg)
            if res is None:
                print("  第 %d 份：窗口不足" % (k + 1))
            else:
                off, c = res
                print("  第 %d 份  应落在 %7.4fs → 实际 %+7.1f ms  相关 %.3f"
                      % (k + 1, k * seg, off * 1000, c))


if __name__ == "__main__":
    main()
