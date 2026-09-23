# -*- coding: utf-8 -*-
"""受控复现：验证 `_concat_video.py` 的「视频轨 / 音频轨分开 concat」是否造成音画漂移，
并验证修法（单条 concat 用 v=1:a=1，音视频一起拼）。

对同一组源片段跑两种 filtergraph：
  A（现状）：[v..]concat=v=1:a=0[v] ; [a..]concat=v=0:a=1[a]
  B（修法）：[v0][a0][v1][a1]...concat=n=N:v=1:a=1[v][a]
测量产物：视频时长 / 音频时长 /（音频 − 视频）。
"""
import os
import subprocess
import sys

for _s in ("stdout", "stderr"):
    try:
        getattr(sys, _s).reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")
TMP = os.path.join(OUT, "_diag_concat")
os.makedirs(TMP, exist_ok=True)

SHOTS = [
    (55, "07_rice_field", "55_yuan_pulls_normal_rice_00008_.mp4"),
    (56, "07_rice_field", "56_yuan_points_marked_ear_00003_.mp4"),
    (57, "07_rice_field", "57_zhang_shuyang_leans_in_00008_.mp4"),
    (58, "07_rice_field", "58_yuan_asks_if_they_ate_00003_.mp4"),
    (59, "07_rice_field", "59_liu_siqi_answers_quietly_00003_.mp4"),
    (60, "07_rice_field", "60_yuan_talks_about_hungry_people_00007_.mp4"),
    (61, "07_rice_field", "61_liu_sicheng_blurts_out_00009_.mp4"),
]


def probe(path):
    import json as _json
    r = subprocess.run(["ffprobe", "-v", "error", "-of", "json",
                        "-show_streams", "-show_format", "-count_frames", path],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    d = _json.loads(r.stdout or "{}")
    v = a = None
    for s in d.get("streams", []):
        if s.get("codec_type") == "video" and v is None:
            v = (float(s.get("duration") or 0),
                 int(s.get("nb_read_frames") or s.get("nb_frames") or 0))
        elif s.get("codec_type") == "audio" and a is None:
            a = (float(s.get("duration") or 0),
                 int(s.get("nb_read_frames") or s.get("nb_frames") or 0))
    return v, a


def graph_a(files, n):
    fin = []
    for f in files:
        fin += ["-i", f]
    ch = "".join("[%d:v]copy[v%d];" % (i, i) for i in range(n))
    ch2 = "".join("[%d:a]anull[a%d];" % (i, i) for i in range(n))
    fc = (ch + "".join("[v%d]" % i for i in range(n)) + "concat=n=%d:v=1:a=0[v];" % n
          + ch2 + "".join("[a%d]" % i for i in range(n)) + "concat=n=%d:v=0:a=1[a]" % n)
    return fin, fc


def graph_b(files, n):
    fin = []
    for f in files:
        fin += ["-i", f]
    fc = (";".join("[%d:v]copy[v%d];[%d:a]anull[a%d]" % (i, i, i, i)
                   for i in range(n)) + ";"
          + "".join("[v%d][a%d]" % (i, i) for i in range(n))
          + "concat=n=%d:v=1:a=1[v][a]" % n)
    return fin, fc


def run(name, fin, fc, n):
    fb = os.path.join(TMP, "fg_%s.txt" % name)
    with open(fb, "w", encoding="utf-8") as f:
        f.write(fc)
    out = os.path.join(TMP, "out_%s.mp4" % name)
    cmd = (["ffmpeg", "-y", "-v", "error"] + fin +
           ["-filter_complex_script", fb, "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-crf", "28", "-preset", "ultrafast",
            "-c:a", "aac", "-ar", "32000", "-ac", "2", out])
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode != 0:
        print("  !! %s 失败：%s" % (name, (r.stderr or "")[:400]))
        return None
    v, a = probe(out)
    print("  %-4s 视频 %8.4fs (%d 帧)   音频 %8.4fs   音频−视频 %+8.4fs"
          % (name, v[0], v[1], a[0], a[0] - v[0]))
    return a[0] - v[0], a[0], v[0]


def env(x, win=320):
    import numpy as _np
    n = len(x) // win * win
    if n == 0:
        return _np.zeros(0, "float32")
    return _np.abs(x[:n]).reshape(-1, win).mean(axis=1)


def pcm(path, ss=None, t=None):
    import numpy as _np
    cmd = ["ffmpeg", "-v", "error"]
    if ss is not None:
        cmd += ["-ss", "%.4f" % ss]
    cmd += ["-i", path]
    if t is not None:
        cmd += ["-t", "%.4f" % t]
    cmd += ["-vn", "-ac", "1", "-ar", "32000", "-f", "f32le", "-"]
    r = subprocess.run(cmd, capture_output=True)
    return _np.frombuffer(r.stdout, dtype="float32")


def drift_report(tag, movie):
    """在成片里逐镜找源音频的实际位置，报告累计漂移（章节起点按帧数累加）。"""
    import numpy as _np
    mv = env(pcm(movie))
    t0 = 0.0
    print("  %s 逐镜实测（章节起点 = Σ帧数/24）：" % tag)
    for s, d, fn in SHOTS:
        src = os.path.join(OUT, d, "video", fn)
        a = env(pcm(src))
        L = len(a)
        v, _ = probe(src)
        base = int(round(t0 / 0.01))
        best = (None, -9.0)
        for off in range(-100, 231):
            st = base + off
            if st < 0 or st + L > len(mv):
                continue
            x = mv[st:st + L]
            x = x - x.mean()
            y = a - a.mean()
            den = _np.sqrt((x * x).sum() * (y * y).sum())
            c = float((x * y).sum() / den) if den > 0 else 0.0
            if c > best[1]:
                best = (off * 10, c)
        print("    镜 %-3d 章节起点 %7.3fs → 音频实际在 %+5d ms  相关 %.2f"
              % (s, t0, best[0], best[1]))
        t0 += v[0]
    print()


def graph_c(files, n, durs):
    """修法候选 C：每段音频先 aresample，再 apad 后 atrim 到**本镜精确时长**，
    然后 v/a 一起 concat ⇒ 音频段长度恒等于视频段长度，不再累积漂移。"""
    fin = []
    for f in files:
        fin += ["-i", f]
    ch = []
    for i in range(n):
        ch.append("[%d:v]copy[v%d]" % (i, i))
        ch.append("[%d:a]aresample=32000,aformat=channel_layouts=stereo,apad,"
                  "atrim=0:%.6f,asetpts=N/SR/TB[a%d]" % (i, durs[i], i))
    fc = (";".join(ch) + ";"
          + "".join("[v%d][a%d]" % (i, i) for i in range(n))
          + "concat=n=%d:v=1:a=1[v][a]" % n)
    return fin, fc


def main():
    files = []
    for s, d, fn in SHOTS:
        p = os.path.join(OUT, d, "video", fn)
        assert os.path.exists(p), p
        files.append(p)
    n = len(files)
    print("源片段（%d 个）：" % n)
    sv = sa = 0.0
    for s, d, fn in SHOTS:
        v, a = probe(os.path.join(OUT, d, "video", fn))
        sv += v[0]
        sa += a[0]
        print("  镜 %-3d 视频 %7.4fs (%3d 帧)  音频 %7.4fs  差 %+7.4fs  %s"
              % (s, v[0], v[1], a[0], a[0] - v[0], fn))
    print("  合计：视频 %.4fs  音频 %.4fs  差 %+.4fs"
          % (sv, sa, sa - sv))

    fin, fc = graph_a(files, n)
    da = run("A", fin, fc, n)
    fin, fc = graph_b(files, n)
    db = run("B", fin, fc, n)
    durs = [probe(os.path.join(OUT, d, "video", fn))[0][0] for s, d, fn in SHOTS]
    fin, fc = graph_c(files, n, durs)
    dc = run("C", fin, fc, n)
    print("\nA（现状）音频偏长 %.4fs   B（一起 concat）%.4fs   C（apad+atrim 钉长）%.4fs\n"
          % (da[0], db[0], dc[0]))
    drift_report("A（现状 · 音视频分开 concat）",
                 os.path.join(TMP, "out_A.mp4"))
    drift_report("B（v=1:a=1 一起 concat）",
                 os.path.join(TMP, "out_B.mp4"))
    drift_report("C（每段 apad+atrim 钉到本镜时长）",
                 os.path.join(TMP, "out_C.mp4"))


if __name__ == "__main__":
    main()
