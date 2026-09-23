# -*- coding: utf-8 -*-
"""对照实验：用 ffmpeg 原生 `-f concat`（conat demuxer）「纯接」行不行？

同时测两件事（7 镜，含镜 55-61）：
  1) 音画是否漂移（源片段音频在成片里的实际位置）
  2) 镜头切换处有没有**重复帧**（画面停一帧 = 微卡顿）

对照三份产物：
  A  现状旧逻辑（视频/音频分开 concat 滤镜）
  C  本次修法（每段音频 apad/atrim 钉到本镜时长）
  D  `-f concat` demuxer 纯接 + 重编码（可烧镜号）
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
SHOTS = [
    (55, "55_yuan_pulls_normal_rice_00008_.mp4"),
    (56, "56_yuan_points_marked_ear_00003_.mp4"),
    (57, "57_zhang_shuyang_leans_in_00008_.mp4"),
    (58, "58_yuan_asks_if_they_ate_00003_.mp4"),
    (59, "59_liu_siqi_answers_quietly_00003_.mp4"),
    (60, "60_yuan_talks_about_hungry_people_00007_.mp4"),
    (61, "61_liu_sicheng_blurts_out_00009_.mp4"),
]
FILES = [os.path.join(OUT, "07_rice_field", "video", fn) for _, fn in SHOTS]


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


def pcm(path, ss=None, t=None, ch=1):
    cmd = ["ffmpeg", "-v", "error"]
    if ss is not None:
        cmd += ["-ss", "%.4f" % ss]
    cmd += ["-i", path]
    if t is not None:
        cmd += ["-t", "%.4f" % t]
    cmd += ["-vn", "-ac", str(ch), "-ar", str(SR), "-f", "f32le", "-"]
    r = subprocess.run(cmd, capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.float32)


def env(x, win=320):
    n = len(x) // win * win
    return np.abs(x[:n]).reshape(-1, win).mean(axis=1) if n else np.zeros(0, np.float32)


def dup_frames(path, w=96, h=54):
    """数「与前一帧几乎相同」的帧（=画面停住/重复帧）。"""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path,
                        "-vf", "scale=%d:%d,format=gray" % (w, h),
                        "-f", "rawvideo", "-"], capture_output=True)
    fr = np.frombuffer(r.stdout, dtype=np.uint8)
    n = w * h
    cnt = fr.size // n
    f = fr[:cnt * n].reshape(cnt, n).astype(np.int16)
    if cnt < 2:
        return []
    d = np.abs(np.diff(f, axis=0)).mean(axis=1)
    return [i + 1 for i in range(len(d)) if d[i] < 0.5]


def build_d():
    lst = os.path.join(TMP, "list_d.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for p in FILES:
            f.write("file '%s'\n" % p.replace("\\", "/"))
    out = os.path.join(TMP, "out_D.mp4")
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst,
           "-vf", "scale=1056:608,setsar=1,drawtext=fontfile='C\\:/Windows/Fonts/msyhbd.ttc'"
                  ":text='SHOT 000':fontsize=34:fontcolor=white:borderw=3:"
                  "bordercolor=black@0.85:x=w-text_w-24:y=24:fix_bounds=1",
           "-c:v", "libx264", "-crf", "28", "-preset", "ultrafast",
           "-c:a", "aac", "-ar", "32000", "-ac", "2", out]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode:
        print("  !! D 失败：%s" % (r.stderr or "")[:400])
        return None
    return out


def drift(path, t0_of):
    mv = env(pcm(path))
    print("  %-34s 成片 %.3fs" % (os.path.basename(path), len(mv) * 0.01))
    for s, fn in SHOTS:
        src = os.path.join(OUT, "07_rice_field", "video", fn)
        a = env(pcm(src))
        L = len(a)
        base = int(round(t0_of[s] / 0.01))
        best = (None, -9.0)
        for off in range(-150, 451):
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


def main():
    # 各镜帧数 → 两种时间轴
    t0_frames, acc = {}, 0.0
    for s, fn in SHOTS:
        t0_frames[s] = acc
        acc += probe(FILES[SHOTS.index((s, fn))])["vf"] / 24.0
    print("按帧数累加的章节起点：%.4f s" % acc)

    print("\n=== D：ffmpeg -f concat demuxer 纯接 + 重编码 ===")
    d = build_d()
    if d:
        info = probe(d)
        print("  产物：视频 %.4fs (%d 帧) / 音频 %.4fs  →  音轨−画面 %+.4fs"
              % (info["vdur"], info["vf"], info["adur"],
                 info["adur"] - info["vf"] / 24.0))
        dups = dup_frames(d)
        print("  重复帧（画面停住）：%d 个，位置(帧号) %s" % (len(dups), dups))
        print("  期望：纯接不漂移，但每刀多推 ~容器余量 ⇒ 卡顿")
        drift(d, t0_frames)

    for tag, f in [("A（旧：v/a 分开 concat）", "out_A.mp4"),
                   ("C（修法：音频钉到本镜时长）", "out_C.mp4")]:
        p = os.path.join(TMP, f)
        if not os.path.exists(p):
            print("\n（缺 %s，先跑 _diag_concat_ab.py）" % f)
            continue
        info = probe(p)
        dups = dup_frames(p)
        print("\n=== %s ===" % tag)
        print("  视频 %.4fs (%d 帧) / 音频 %.4fs → 差 %+.4fs；重复帧 %d 个"
              % (info["vdur"], info["vf"], info["adur"],
                 info["adur"] - info["vf"] / 24.0, len(dups)))


if __name__ == "__main__":
    main()
