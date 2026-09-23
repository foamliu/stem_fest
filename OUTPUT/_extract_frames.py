# -*- coding: utf-8 -*-
"""全片抽帧器 —— 为每一镜从**最新版** mp4 抽 1 张代表帧到 `<幕>/frames/`。

为什么需要它（2026-09-15）
    §1 `OUTPUT/_face_identity.py ledger` 依赖 `<幕>/frames/*.png`，
       而 05/06/07/08 四个幕的 `frames/` **是空的** ⇒ 人脸一致性审计无法覆盖全片。
    §2 抽帧必须来自**最新版** mp4（重跑后旧帧会误导审计，见 LESSONS #2 教训）。

命名（`_face_identity.py` 的 `SHOT_RE` 认得两种）
    `<镜号>_<slug>_<版本>.png`（如 `05_zhang_shuyang_catches_plane_00003_.png`）
    ⇒ 保留原 mp4 名，仅换扩展名，最省事且不含糊。

抽帧位置
    默认 **时长中点**（0.5）—— 人物最稳定、不在起势/收势。
    可 `--at=0.35` 改；一次多抽用 `--at=0.35,0.5,0.65`（文件名加 `_f1` 后缀）。

用法
    py -3.10 OUTPUT/_extract_frames.py --act=05_classroom_night
    py -3.10 OUTPUT/_extract_frames.py --all
    py -3.10 OUTPUT/_extract_frames.py --all --shots=110,111 --at=0.5 --force
"""
import glob
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")

ACTS = {
    "01_paper_plane": (1, 9),
    "03_classroom_day": (10, 18),
    "06_trench": (19, 46),
    "07_rice_field": (47, 74),
    "08_train_dining": (75, 105),
    "05_classroom_night": (106, 126),
}


def dur_of(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def latest_mp4(act, shot):
    """该镜**最新版** mp4（mtime 最大）。"""
    fs = glob.glob(os.path.join(OUT, act, "video", "%d_*.mp4" % shot))
    if not fs:
        fs = glob.glob(os.path.join(OUT, act, "video", "%02d_*.mp4" % shot))
    if not fs:
        return None
    return max(fs, key=os.path.getmtime)


def main():
    acts = []
    ats = [0.5]
    shots_filter = None
    force = False
    for a in sys.argv[1:]:
        if a.startswith("--act="):
            acts = [a.split("=", 1)[1]]
        elif a == "--all":
            acts = list(ACTS)
        elif a.startswith("--shots="):
            shots_filter = set(int(x) for x in
                               a.split("=", 1)[1].split(",") if x.strip())
        elif a.startswith("--at="):
            ats = [float(x) for x in a.split("=", 1)[1].split(",") if x.strip()]
        elif a == "--force":
            force = True
    if not acts:
        print("!! 请用 --act=<幕目录> 或 --all")
        return 1

    total, made, skipped, failed = 0, 0, 0, []
    for act in acts:
        lo, hi = ACTS.get(act, (0, 0))
        fd = os.path.join(OUT, act, "frames")
        os.makedirs(fd, exist_ok=True)
        for n in range(lo, hi + 1):
            if shots_filter and n not in shots_filter:
                continue
            total += 1
            mp4 = latest_mp4(act, n)
            if not mp4:
                failed.append((act, n, "无 mp4"))
                continue
            d = dur_of(mp4)
            if d <= 0:
                failed.append((act, n, "时长读不到"))
                continue
            stem = os.path.splitext(os.path.basename(mp4))[0]
            for k, fr in enumerate(ats):
                tag = "" if len(ats) == 1 else "_f%d" % (k + 1)
                dst = os.path.join(fd, "%s%s.png" % (stem, tag))
                if os.path.exists(dst) and not force:
                    skipped += 1
                    continue
                subprocess.run(["ffmpeg", "-y", "-v", "error",
                                "-ss", "%.3f" % (d * fr), "-i", mp4,
                                "-frames:v", "1", dst],
                               capture_output=True)
                if os.path.exists(dst) and os.path.getsize(dst) > 0:
                    made += 1
                else:
                    failed.append((act, n, "ffmpeg 失败"))
        print("  %-22s 已处理（累计 新抽=%d 跳过=%d）" % (act, made, skipped))

    print("\n共 %d 镜；新抽 %d 张，跳过 %d 张" % (total, made, skipped))
    if failed:
        print("失败 %d 项：" % len(failed))
        for a, n, why in failed[:20]:
            print("   %s 镜 %d —— %s" % (a, n, why))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
