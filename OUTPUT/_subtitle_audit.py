# -*- coding: utf-8 -*-
"""字幕污染专项抽检：把指定镜头的「画面底部字幕带」截出来拼成一张大图。

为什么只看底部条带
    H3 的字幕/字样污染 99% 出现在画面底部或中央水平带。
    把每镜裁出「下 1/4」并横向压缩成一条，一张图能塞 30+ 镜 ⇒ 最省 token 的抽检。
    同时对每镜抽 2 个时间点（中段 + 尾段），因为字幕可能只在某一段出现。

输出
    OUTPUT/_subtitle_audit/band_XX.jpg   每条带含 N 镜

用法：
    py -3.10 OUTPUT/_subtitle_audit.py --shots=4,5,9,16,19
    py -3.10 OUTPUT/_subtitle_audit.py                  # 默认扫 R1 高危 34 镜
    py -3.10 OUTPUT/_subtitle_audit.py --full            # 全片 126 镜
"""
import glob
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")
DIR = os.path.join(OUT, "_subtitle_audit")

# ★ 必须与各幕脚本的 OUT_ROOT 一致（act2→04_classroom_dusk 是历史命名，勿猜）
ACTS = ["01_paper_plane", "04_classroom_dusk", "06_trench",
        "07_rice_field", "08_train_dining", "05_classroom_night"]

# R1 命中（NO_SPEECH 指令块）—— 本次抽检重点
R1_SHOTS = [4, 5, 9, 16, 19, 23, 46, 50, 52, 64, 73, 74, 75, 79, 81, 83,
            91, 102, 104, 105, 106, 109, 110, 111, 113, 117, 119, 120, 121,
            122, 123, 124, 125, 126]


def latest(shot):
    best, bt = None, 0
    for d in ACTS:
        for f in glob.glob(os.path.join(OUT, d, "video", "%02d_*.mp4" % shot)):
            if os.path.getmtime(f) > bt:
                best, bt = f, os.path.getmtime(f)
    return best


def dur_of(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def bands(shot, per=2):
    """抽 per 个时间点的「下 1/4」条带，返回文件列表。"""
    p = latest(shot)
    if not p:
        return []
    d = dur_of(p)
    if d <= 0:
        return []
    got = []
    for i in range(per):
        t = d * (0.45 + 0.45 * i / max(1, per - 1)) if per > 1 else d * 0.6
        fp = os.path.join(DIR, "_b%03d_%d.jpg" % (shot, i))
        # 裁下 1/4：高 608/4=152，从 y=456 起；再放大约 2 倍便于辨字
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "%.3f" % t,
                        "-i", p, "-frames:v", "1",
                        "-vf", "crop=1056:160:0:448,scale=1400:212",
                        "-q:v", "2", fp], capture_output=True)
        if os.path.exists(fp) and os.path.getsize(fp) > 0:
            got.append(fp)
    return got


def main():
    per, cols, per_sheet = 2, 1, 14
    only = R1_SHOTS
    for a in sys.argv[1:]:
        if a.startswith("--shots="):
            only = [int(x) for x in a.split("=", 1)[1].split(",") if x.strip()]
        elif a.startswith("--full"):
            only = list(range(1, 127))
        elif a.startswith("--per="):
            per = int(a.split("=", 1)[1])
        elif a.startswith("--sheet="):
            per_sheet = int(a.split("=", 1)[1])

    os.makedirs(DIR, exist_ok=True)
    for f in glob.glob(os.path.join(DIR, "_b*.jpg")):
        os.remove(f)

    from PIL import Image, ImageDraw

    print("字幕抽检：%d 镜，每镜 %d 个时间点" % (len(only), per))
    band_h = 212
    lab_h = 18
    sheets = []
    for si in range(0, len(only), per_sheet):
        chunk = only[si:si + per_sheet]
        W = 1400 * per + 12
        H = 4 + len(chunk) * (band_h + lab_h + 3)
        canvas = Image.new("RGB", (W, H), (12, 12, 14))
        dr = ImageDraw.Draw(canvas)
        for ri, n in enumerate(chunk):
            y = 4 + ri * (band_h + lab_h + 3)
            p = latest(n)
            ver = re.search(r"_(\d{5})_\.mp4$", os.path.basename(p)) if p else None
            dr.text((6, y), "SHOT %d  v%s   %s" % (
                n, ver.group(1) if ver else "?",
                os.path.basename(p)[:56] if p else "NO VIDEO"),
                fill=(255, 225, 130))
            fs = bands(n, per)
            for j, fp in enumerate(fs):
                try:
                    im = Image.open(fp).convert("RGB")
                    canvas.paste(im, (6 + j * (1400 + 4), y + lab_h))
                except Exception:
                    pass
        sp = os.path.join(DIR, "band_%02d.jpg" % (len(sheets) + 1))
        canvas.save(sp, quality=86)
        sheets.append(sp)
        print("  %s  (%s)" % (os.path.basename(sp),
                              ",".join(str(x) for x in chunk)))
    print("\n输出：%s" % DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
