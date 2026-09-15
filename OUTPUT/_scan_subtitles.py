# -*- coding: utf-8 -*-
"""全片「画面字幕」批量排查 —— 用**画面中央带**（不是底部带）扫台词泄漏。

★ 为什么要扫"中央带"而不是底部带（2026-09-15）
    `_probe.py --type=T1` 只裁画面**底部**，因为最初的污染（`NO_SPEECH` 常量）
    恰好落在底部。但**台词被渲染成字幕**时，H3 习惯放在**画面中央偏下**
    （实测镜 14：「我上次竞选科技之星」在中央）—— 底部带**扫不到**。
    ⇒ 本脚本裁**中央 40% 高度**横带，专扫台词类字幕。

用法
    py -3.10 OUTPUT/_scan_subtitles.py --shots=14,15,20     # 指定镜
    py -3.10 OUTPUT/_scan_subtitles.py --all                # 全片（分批出图）
    py -3.10 OUTPUT/_scan_subtitles.py --all --batch=16     # 每批 16 镜一张图
"""
import glob
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")

DIRS = ["01_paper_plane", "04_classroom_dusk", "06_trench",
        "07_rice_field", "08_train_dining", "05_classroom_night"]


def collect():
    found = {}
    for d in DIRS:
        for f in glob.glob(os.path.join(OUT, d, "video", "*.mp4")):
            m = re.match(r"(\d+)_", os.path.basename(f))
            if not m:
                continue
            n = int(m.group(1))
            if n not in found or os.path.getmtime(f) > os.path.getmtime(found[n]):
                found[n] = f
    return found


def dur_of(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def main():
    only, allf, batch = None, False, 16
    for a in sys.argv[1:]:
        if a.startswith("--shots="):
            only = [int(x) for x in a.split("=", 1)[1].split(",")]
        elif a == "--all":
            allf = True
        elif a.startswith("--batch="):
            batch = int(a.split("=", 1)[1])

    found = collect()
    shots = sorted(found) if allf else (only or [])
    if not shots:
        print("!! 用 --shots=… 或 --all")
        return 1

    od = os.path.join(OUT, "_subscan")
    os.makedirs(od, exist_ok=True)
    from PIL import Image, ImageDraw

    made = 0
    for bi in range(0, len(shots), batch):
        grp = shots[bi:bi + batch]
        cols, tw = 2, 560
        tiles = []
        for n in grp:
            p = found[n]
            d = dur_of(p)
            for k, fr in enumerate((0.35, 0.6)):
                t = d * fr
                q = os.path.join(od, "_s%03d_%d.jpg" % (n, k))
                # ★ 裁**下部 1/3**（画面 62%–100% 高度）：
                #   实测台词泄漏位置在 78–85% 高度（镜 14），比 `_probe.py --type=T1`
                #   的"最底 1/4"更高，比"中央 40%"更低 ⇒ 单扫这条带最有效。
                subprocess.run(["ffmpeg", "-y", "-v", "error",
                                "-ss", "%.2f" % t, "-i", p, "-frames:v", "1",
                                "-vf", "crop=iw:ih*0.38:0:ih*0.62,scale=%d:-1" % tw,
                                q], capture_output=True)
                if os.path.exists(q):
                    tiles.append((n, t, Image.open(q).convert("RGB")))
        if not tiles:
            continue
        th = tiles[0][2].height + 18
        rows = (len(tiles) + cols - 1) // cols
        canvas = Image.new("RGB", (tw * cols, th * rows), (12, 12, 14))
        dr = ImageDraw.Draw(canvas)
        for i, (n, t, im) in enumerate(tiles):
            x = (i % cols) * tw
            y = (i // cols) * th
            dr.text((x + 4, y + 2), "SHOT %d  %.1fs" % (n, t),
                    fill=(255, 210, 120))
            canvas.paste(im, (x, y + 18))
        pp = os.path.join(od, "scan_%02d_%03d.jpg" % (bi // batch + 1,
                                                       grp[-1]))
        canvas.save(pp, quality=86)
        made += 1
        print("  %s  （镜 %d–%d）" % (os.path.relpath(pp, ROOT),
                                    grp[0], grp[-1]))
    print("\n共 %d 张拼图，输出目录 %s" % (made, os.path.relpath(od, ROOT)))
    print("⚠️ 需人眼读图：找**成行的中文句子**（台词泄漏）；")
    print("   一两个字（牌子/屏幕 UI）不算。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
