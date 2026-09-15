# -*- coding: utf-8 -*-
"""A/B 对照验证：同一镜的「旧版（污染）」vs「新版（修复后）」并排出图。

为什么需要 A/B
    "改写 prompt 后字幕消失了吗" 是**相对判断**：
    单看新版图"没有字幕"，无法排除"这镜本来就没字幕"。
    必须把**同一镜的旧版抽帧**与**新版抽帧**并排 ⇒ 才证明因果。

布局（每镜两行）
    ┌──────────────┬──────────────┬──────────────┐
    │ OLD v0000N   │ 3 帧（下1/4放大）           │
    ├──────────────┼──────────────┼──────────────┤
    │ NEW v0000M   │ 3 帧（同位置、同手法）        │
    └──────────────┴──────────────┴──────────────┘
    两行抽帧的**时间点相同**（0.35/0.60/0.85 时长），保证可比性。

用法：
    py -3.10 OUTPUT/_ab_check.py --shots=5,19,91
    py -3.10 OUTPUT/_ab_check.py --shots=5 --mode=full   # 全帧而非底部带
"""
import glob
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")
DIR = os.path.join(OUT, "_ab")

ACTS = ["01_paper_plane", "04_classroom_dusk", "06_trench",
        "07_rice_field", "08_train_dining", "05_classroom_night"]


def versions(shot):
    """该镜所有版本，按 (mtime, 版本号) 升序。"""
    got = []
    for d in ACTS:
        for f in glob.glob(os.path.join(OUT, d, "video", "%02d_*.mp4" % shot)):
            m = re.search(r"_(\d{5})_\.mp4$", os.path.basename(f))
            got.append((os.path.getmtime(f), int(m.group(1)) if m else 0, f))
    got.sort()
    return got


def dur_of(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0


FRACS = (0.35, 0.60, 0.85)


def frames(shot, path, tag, mode):
    d = dur_of(path)
    if d <= 0:
        return []
    vf = ("scale=1500:-1" if mode == "full"
          else "crop=1056:190:0:418,scale=1500:270")
    got = []
    for i, fr in enumerate(FRACS):
        fp = os.path.join(DIR, "_%s_%03d_%d.jpg" % (tag, shot, i))
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "%.3f" % (d * fr),
                        "-i", path, "-frames:v", "1", "-vf", vf, "-q:v", "2", fp],
                       capture_output=True)
        if os.path.exists(fp) and os.path.getsize(fp) > 0:
            got.append(fp)
    return got


def main():
    shots, mode, scale = [], "band", None
    for a in sys.argv[1:]:
        if a.startswith("--shots="):
            shots = [int(x) for x in a.split("=", 1)[1].split(",") if x.strip()]
        elif a.startswith("--mode="):
            mode = a.split("=", 1)[1].lower()
    if not shots:
        print("!! 请用 --shots=5,19,91")
        return 1

    os.makedirs(DIR, exist_ok=True)
    for f in glob.glob(os.path.join(DIR, "_*.jpg")):
        os.remove(f)

    from PIL import Image, ImageDraw
    tw, th = (1500, 863) if mode == "full" else (1500, 270)
    lab_h, rowgap = 20, 4
    W = 3 * (tw + 4) + 14
    H = 4 + len(shots) * (2 * (th + lab_h) + rowgap * 2 + 8)
    canvas = Image.new("RGB", (W, H), (12, 12, 14))
    dr = ImageDraw.Draw(canvas)
    dr.text((6, 2), "A/B 对照 —— 上行 OLD（修复前 prompt 产出）/ 下行 NEW（修复后）"
                    "  抽帧点=%s" % (FRACS,), fill=(255, 225, 130))

    y = 18
    for n in shots:
        vs = versions(n)
        if not vs:
            dr.text((6, y), "SHOT %d  NO VIDEO" % n, fill=(255, 90, 90))
            y += 40
            continue
        old, new = vs[0], vs[-1]
        for label, (mt, ver, path), col in (("OLD", old, (255, 150, 120)),
                                           ("NEW", new, (140, 240, 160))):
            dr.text((6, y), "SHOT %d  %s v%05d  %s" % (
                n, label, ver, os.path.basename(path)[:60]), fill=col)
            for j, fp in enumerate(frames(n, path, label, mode)):
                try:
                    im = Image.open(fp).convert("RGB").resize((tw, th),
                                                              Image.LANCZOS)
                    canvas.paste(im, (6 + j * (tw + 4), y + lab_h))
                except Exception:
                    pass
            y += th + lab_h + rowgap
        y += 8

    sp = os.path.join(DIR, "AB.jpg")
    canvas.save(sp, quality=86)
    print("输出：%s" % sp)
    for n in shots:
        vs = versions(n)
        print("   镜 %-4d 版本数=%d  %s" % (
            n, len(vs), [os.path.basename(v[2]) for v in vs]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
