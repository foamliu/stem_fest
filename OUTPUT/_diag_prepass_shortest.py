# -*- coding: utf-8 -*-
"""路线 E：**先把每个片段修干净，再接**。

E1 预处理：`ffmpeg -i clip -c copy -shortest` —— 无损丢掉音频尾巴（不重编码）
E2 拼接：`ffmpeg -f concat -i list -vf drawtext ... -c:v libx264 -c:a aac`
测：预处理后片段「音轨是否变回 = 画面长度」；接完是否还漂移、有没有重复帧。
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
NORMD = os.path.join(TMP, "norm")
os.makedirs(NORMD, exist_ok=True)
SR = 32000
SHOTS = [
    (55, "55_yuan_pulls_normal_rice_00008_.mp4"),
    (56, "56_yuan_points_marked_ear_00003_.mp4"),
    (57, "57_zhang_shuyang_leans_in_00008_.mp4"),
    (58, "58_yuan_asks_if_they_ate_00003_.mp4"),
    (59, "59_liu_siqi_answers_quietly_00003_.mp4"),
    (60, "60_yuan_talks_about_hungry_people_00007_.mp4"),
    (61, "61_liu_sicheng_blurts_out_00009_.mp4"),
]
SRC = [os.path.join(OUT, "07_rice_field", "video", fn) for _, fn in SHOTS]


def probe(path):
    import json
    r = subprocess.run(["ffprobe", "-v", "error", "-of", "json", "-show_streams",
                        "-show_format", "-count_frames", path],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    d = json.loads(r.stdout or "{}")
    o = {"dur": float(d.get("format", {}).get("duration") or 0)}
    for s in d.get("streams", []):
        if s.get("codec_type") == "video":
            o["vf"] = int(s.get("nb_read_frames") or 0)
            o["vdur"] = float(s.get("duration") or 0)
        elif s.get("codec_type") == "audio":
            o["adur"] = float(s.get("duration") or 0)
    return o


def pcm_len(path):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1",
                        "-ar", str(SR), "-f", "f32le", "-"], capture_output=True)
    return len(r.stdout) // 4 / SR


def pcm(path, ss=None, t=None):
    cmd = ["ffmpeg", "-v", "error"]
    if ss is not None:
        cmd += ["-ss", "%.4f" % ss]
    cmd += ["-i", path]
    if t is not None:
        cmd += ["-t", "%.4f" % t]
    cmd += ["-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True).stdout,
                         dtype=np.float32)


def env(x, win=320):
    n = len(x) // win * win
    return np.abs(x[:n]).reshape(-1, win).mean(axis=1) if n else np.zeros(0, np.float32)


def dup_frames(path, w=96, h=54):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path,
                        "-vf", "scale=%d:%d,format=gray" % (w, h),
                        "-f", "rawvideo", "-"], capture_output=True)
    fr = np.frombuffer(r.stdout, dtype=np.uint8)
    n = w * h
    cnt = fr.size // n
    f = fr[:cnt * n].reshape(cnt, n).astype(np.int16)
    d = np.abs(np.diff(f, axis=0)).mean(axis=1) if cnt > 1 else []
    return [i + 1 for i in range(len(d)) if d[i] < 0.5]


def main():
    print("=== E1 预处理：-c copy -shortest（无损削尾巴）===")
    norms = []
    for (s, fn), src in zip(SHOTS, SRC):
        dst = os.path.join(NORMD, fn)
        r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src,
                            "-c", "copy", "-shortest", "-movflags", "+faststart",
                            dst], capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        if r.returncode:
            print("  镜 %d 失败：%s" % (s, (r.stderr or "")[:200]))
            norms.append(src)
            continue
        o0, o1 = probe(src), probe(dst)
        print("  镜 %-3d  前: 画面 %.4fs 音轨 %.4fs(%+.1fms) → 后: 画面 %.4fs 音轨 %.4fs(%+.1fms)"
              % (s, o0["vf"] / 24.0, pcm_len(src),
                 (pcm_len(src) - o0["vf"] / 24.0) * 1000,
                 o1["vf"] / 24.0, pcm_len(dst),
                 (pcm_len(dst) - o1["vf"] / 24.0) * 1000))
        norms.append(dst)

    print("\n=== E2 纯接：-f concat + 重编码（烧镜号）===")
    lst = os.path.join(TMP, "list_e.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for p in norms:
            f.write("file '%s'\n" % p.replace("\\", "/"))
    out = os.path.join(TMP, "out_E.mp4")
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst,
           "-vf", "scale=1056:608,setsar=1", "-c:v", "libx264", "-crf", "28",
           "-preset", "ultrafast", "-c:a", "aac", "-ar", "32000", "-ac", "2", out]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode:
        print("  失败：%s" % (r.stderr or "")[:400])
        return
    o = probe(out)
    print("  产物：画面 %.4fs (%d 帧) / 音轨 %.4fs → 差 %+.4fs；重复帧 %d 个"
          % (o["vf"] / 24.0, o["vf"], pcm_len(out),
             pcm_len(out) - o["vf"] / 24.0, len(dup_frames(out))))

    mv = env(pcm(out))
    t0 = 0.0
    print("  逐镜实测（章节起点按帧数累加）：")
    for s, fn in SHOTS:
        a = env(pcm(os.path.join(NORMD, fn)))
        L = len(a)
        nf = probe(os.path.join(NORMD, fn))["vf"]
        base = int(round(t0 / 0.01))
        best = (None, -9.0)
        for off in range(-150, 151):
            st = base + off
            if st < 0 or st + L > len(mv):
                continue
            x = mv[st:st + L] - mv[st:st + L].mean()
            y = a - a.mean()
            den = np.sqrt((x * x).sum() * (y * y).sum())
            c = float((x * y).sum() / den) if den > 0 else 0.0
            if c > best[1]:
                best = (off * 10, c)
        print("     镜 %-3d → 音频在 %+5d ms  相关 %.2f" % (s, best[0], best[1]))
        t0 += nf / 24.0


if __name__ == "__main__":
    main()
