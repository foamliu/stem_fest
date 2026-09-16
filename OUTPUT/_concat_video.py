# -*- coding: utf-8 -*-
"""把已生成的镜头按镜号顺序拼成一个完整视频（增量可用）。

★ 设计要点
  1. **按镜号**从 6 个幕目录里收集产物，自动排序 —— 镜号 ≠ 目录顺序，
     不能靠目录名拼（第二幕在 07_rice_field、第三幕在 08_train_dining）。
  2. **优先无损拼接**：所有片段都是同一套 H3 输出规格
     （1056×608 h264 / aac 32kHz 2ch / 24fps），用 concat demuxer + `-c copy`，
     不重编码 ⇒ 快（分钟级）且零画质损失。
  3. **自动检测规格一致性**：若片段规格不同（例如将来超分过），
     自动回退到「统一转码后拼接」并给出提示。
  4. **镜号缺口检测**：缺号明确列出，但不阻止拼接（按现有镜号顺序拼）。
  5. 顺带生成**章节对轴表**（镜号 / 时长 / 起止时间点），便于剪辑对轴。

用法：
    py -3.10 OUTPUT/_concat_video.py                 # 拼到最后一镜（默认 OUTPUT/full_cut.mp4）
    py -3.10 OUTPUT/_concat_video.py --upto=50        # 只拼 1-50
    py -3.10 OUTPUT/_concat_video.py --out=OUTPUT/xx.mp4
    py -3.10 OUTPUT/_concat_video.py --list           # 只列将要拼的片段，不合并
"""
import glob
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRS = ["01_paper_plane", "04_classroom_dusk", "06_trench",
        "07_rice_field", "08_train_dining", "05_classroom_night"]
TMP = os.path.join(ROOT, "OUTPUT", "_concat")
CHAP = os.path.join(ROOT, "OUTPUT", "_concat_chapters.txt")


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


def probe(p):
    out = run(["ffprobe", "-v", "error", "-show_entries",
               "format=duration:stream=codec_type,codec_name,width,height,"
               "sample_rate,channels,r_frame_rate",
               "-of", "json", p])
    try:
        d = json.loads(out.stdout)
    except Exception:
        return None
    info = {"dur": float(d["format"]["duration"])}
    for s in d["streams"]:
        if s.get("codec_type") == "video":
            info.update(w=s.get("width"), h=s.get("height"),
                        vc=s.get("codec_name"), fps=s.get("r_frame_rate"))
        elif s.get("codec_type") == "audio":
            info.update(ac=s.get("codec_name"), sr=s.get("sample_rate"),
                        ch=s.get("channels"))
    return info


def collect(upto=None):
    """按镜号收集产物：{镜号: 路径}（同号取 mtime 最新的）

    ⚠️ 必须排除：
      · `_bak_*`（擦除/重跑前的备份）
      · `_rejected/` 子目录（镜 14 多 seed 择优后的落选版本）
      · `*_delogo.mp4` / `*_temporal.mp4` / `*_split.mp4`（失败的临时文件）
    """
    found = {}
    for d in DIRS:
        for f in glob.glob(os.path.join(ROOT, "OUTPUT", d, "video", "*.mp4")):
            base = os.path.basename(f)
            if base.startswith("_bak_"):
                continue
            if re.search(r"_(delogo|temporal|split)\.mp4$", base):
                continue
            m = re.match(r"(\d+)_", base)
            if not m:
                continue
            n = int(m.group(1))
            if upto and n > upto:
                continue
            if n not in found or os.path.getmtime(f) > os.path.getmtime(found[n]):
                found[n] = f
    return found


def main():
    args = sys.argv[1:]
    upto = None
    out = os.path.join(ROOT, "OUTPUT", "full_cut.mp4")
    list_only = "--list" in args
    for a in args:
        if a.startswith("--upto="):
            upto = int(a.split("=", 1)[1])
        elif a.startswith("--out="):
            v = a.split("=", 1)[1]
            out = v if os.path.isabs(v) else os.path.join(ROOT, v)

    found = collect(upto)
    if not found:
        print("没有找到任何产物")
        return 1
    shots = sorted(found)
    last = shots[-1]
    missing = [n for n in range(1, last + 1) if n not in found]

    print("=" * 70)
    print("镜号范围：1 - %d（%d 个片段）" % (last, len(shots)))
    print("区间内缺号：%s" % (missing if missing else "无 [OK]"))

    specs, rows, total = {}, [], 0.0
    for n in shots:
        info = probe(found[n])
        if not info:
            print("!! 镜 %d 探测失败：%s" % (n, found[n]))
            continue
        key = (info.get("w"), info.get("h"), info.get("vc"),
               info.get("ac"), info.get("sr"), info.get("ch"), info.get("fps"))
        specs.setdefault(key, []).append(n)
        total += info["dur"]
        rows.append((n, info["dur"], os.path.basename(found[n])))

    print("片段总时长：%.1f s（%.2f 分）" % (total, total / 60.0))
    print("规格分布：")
    for k, v in specs.items():
        print("   %sx%s %s / %s %sHz %sch @%s  -> %d 个镜 %s" % (
            k[0], k[1], k[2], k[3], k[4], k[5], k[6], len(v),
            (str(v[:8]) + "...") if len(v) > 8 else str(v)))
    uniform = len(specs) == 1

    if list_only:
        print("\n将要拼接（镜号 / 时长 / 文件）：")
        for n, d, fn in rows:
            print("  %3d  %5.2fs  %s" % (n, d, fn))
        return 0

    os.makedirs(TMP, exist_ok=True)
    os.makedirs(os.path.dirname(out), exist_ok=True)

    if uniform:
        lst = os.path.join(TMP, "list.txt")
        with open(lst, "w", encoding="utf-8") as f:
            for n in shots:
                f.write("file '%s'\n" % found[n].replace("\\", "/"))
        print("\n[无损拼接] ffmpeg -f concat -c copy  ->  %s" % os.path.relpath(out, ROOT))
        r = run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                 "-i", lst, "-c", "copy", "-movflags", "+faststart", out])
        if r.returncode != 0:
            print("拼接失败：\n%s" % (r.stderr or "")[:1500])
            return 1
    else:
        print("\n!! 片段规格不一致，回退到「统一转码后拼接」（较慢、会轻微损失画质）")
        parts = []
        for n in shots:
            seg = os.path.join(TMP, "seg_%03d.mp4" % n)
            r = run(["ffmpeg", "-y", "-v", "error", "-i", found[n],
                     "-vf", "scale=1056:608,fps=24,setsar=1",
                     "-c:v", "libx264", "-crf", "16", "-preset", "medium",
                     "-c:a", "aac", "-ar", "32000", "-ac", "2", seg])
            if r.returncode != 0:
                print("转码失败 镜 %d：%s" % (n, (r.stderr or "")[:400]))
                return 1
            parts.append(seg)
        lst = os.path.join(TMP, "list_norm.txt")
        with open(lst, "w", encoding="utf-8") as f:
            for s in parts:
                f.write("file '%s'\n" % s.replace("\\", "/"))
        r = run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                 "-i", lst, "-c", "copy", "-movflags", "+faststart", out])
        if r.returncode != 0:
            print("拼接失败：\n%s" % (r.stderr or "")[:1500])
            return 1

    t = 0.0
    with open(CHAP, "w", encoding="utf-8") as f:
        f.write("# 合成片章节对轴表（%s）\n" % os.path.basename(out))
        f.write("# 镜号\t片长(s)\t起点\t终点\t文件\n")
        for n, d, fn in rows:
            f.write("%d\t%.2f\t%.2f\t%.2f\t%s\n" % (n, d, t, t + d, fn))
            t += d

    info = probe(out)
    print("-" * 70)
    if info:
        print("产物：%s" % os.path.relpath(out, ROOT))
        print("      %sx%s %s / %s %sHz %sch @%s" % (
            info.get("w"), info.get("h"), info.get("vc"), info.get("ac"),
            info.get("sr"), info.get("ch"), info.get("fps")))
        print("      时长 %.1f s（%.2f 分）  大小 %.1f MB  %d 个镜（1-%d）" % (
            info["dur"], info["dur"] / 60.0,
            os.path.getsize(out) / 1048576.0, len(shots), last))
    print("章节对轴表：%s" % os.path.relpath(CHAP, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
