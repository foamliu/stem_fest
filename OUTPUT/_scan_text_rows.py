# -*- coding: utf-8 -*-
"""★ 字幕泄漏的**程序化**终检（读图失效时的替代方案）。

原理
    H3 泄漏出来的字幕是**高亮白字 + 深色描边**，在画面下部形成一条
    「细笔画、高局部对比、横向成行」的带状结构。用三个条件联合判定：

      A. 位于画面下方 38%（本项目泄漏位置实测在 62%–90% 高度，README §6.6）
      B. 存在**极亮像素**（>= 235）且其**紧邻四周有极暗像素**（<= 60）
         —— 白字描边的特征；纯白校服/白墙没有这种"亮-暗-亮"夹层
      C. 这些像素在**水平方向成行**（同一行内跨度 >= 画面宽的 25%）
         且**垂直方向很薄**（连续行数 <= 画高的 12%）

    三个都满足 ⇒ 判为「疑似字幕」，输出坐标供人工/读图复核。

⚠️ 这是**筛查器不是判官**：白校服上的深色领口、屏幕 UI 可能触发。
   命中后必须用 `_probe.py --type=T1` 放大那一条自己看（README §6.4 读图铁律）。

用法：
    py -3.10 OUTPUT/_scan_text_rows.py --shots=7,14,21,36,77,85,86,88,112
    py -3.10 OUTPUT/_scan_text_rows.py --video=OUTPUT/full_cut.mp4 --every=4
"""
import os
import subprocess
import sys

import numpy as np
from PIL import Image

ROOT = r"E:\code\stem_fest"
OUT = os.path.join(ROOT, "OUTPUT")
TMP = os.path.join(OUT, "_textrows")
os.makedirs(TMP, exist_ok=True)


def probe_dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def scan_frame(a):
    """→ (命中?, 行带 y, 跨度比, 厚度比, 相邻率)。

    ⚠️ 判据必须是**「亮像素紧贴暗像素」的比例**，不能只看"跨度 + 厚度"。
    误报案例（2026-09-16 镜 14）：旧判据只看"横向成行 + 竖向很薄"，
    把**课桌阴影造成的横向暗带**误判成字幕。
    真正的白字黑边结构里，亮像素**必然 100% 与暗像素相邻**；
    阴影暗带则相邻率接近 0。
    """
    H, W, _ = a.shape
    y0 = int(H * 0.62)                      # 泄漏位置实测下界
    sub = a[y0:, :, :]
    mx = sub.max(axis=2)
    mn = sub.min(axis=2)
    bright = mx >= 235
    dark = mn <= 60
    try:
        halo = binary_dilation(dark, iterations=2)
    except Exception:
        halo = dark
    cand = bright & halo
    # ★ 相邻率：亮像素里有多少是"紧贴暗像素"的 —— 字幕 ≈ 1.0，阴影 ≈ 0
    if bright.sum() < 200:
        return False, 0, 0.0, 0.0, 0.0
    adj = float(cand.sum()) / float(bright.sum())
    if adj < 0.55 or cand.sum() < 200:
        return False, 0, 0.0, 0.0, adj
    rows = np.where(cand.any(axis=1))[0]
    if rows.size == 0:
        return False, 0, 0.0, 0.0, adj
    segs, s, p = [], rows[0], rows[0]
    for r in rows[1:]:
        if r - p > 3:
            segs.append((s, p))
            s = r
        p = r
    segs.append((s, p))
    best = max(segs, key=lambda x: x[1] - x[0])
    a0, b0 = best
    cols = np.where(cand[a0:b0 + 1].any(axis=0))[0]
    if cols.size < 4:
        return False, 0, 0.0, 0.0, adj
    span = (cols.max() - cols.min() + 1) / float(W)
    thick = (b0 - a0 + 1) / float(H)
    hit = (span >= 0.25) and (thick <= 0.12) and (adj >= 0.55)
    return hit, a0 + y0, span, thick, adj


def check_video(p, every=0.35):
    dur = probe_dur(p)
    hits = []
    t = 0.15
    while t < dur:
        fp = os.path.join(TMP, "_tr.jpg")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "%.3f" % t,
                        "-i", p, "-frames:v", "1", "-q:v", "2", fp],
                       capture_output=True)
        if os.path.exists(fp):
            a = np.asarray(Image.open(fp).convert("RGB"), dtype=np.float32)
            h, y, sp, th, adj = scan_frame(a)
            if h:
                hits.append((round(t, 2), int(y), round(sp, 2), round(th, 3), round(adj, 2)))
        t += every
    return dur, hits


def main():
    shots, video, every = None, None, 0.35
    for a in sys.argv[1:]:
        if a.startswith("--shots="):
            shots = [int(x) for x in a.split("=", 1)[1].split(",") if x.strip()]
        elif a.startswith("--video="):
            video = a.split("=", 1)[1]
        elif a.startswith("--every="):
            every = float(a.split("=", 1)[1])

    import glob
    DIRS = ["01_paper_plane", "04_classroom_dusk", "06_trench",
            "07_rice_field", "08_train_dining", "05_classroom_night"]
    targets = []
    if video:
        targets = [(os.path.basename(video), os.path.join(OUT, video) if not os.path.isabs(video) else video)]
    else:
        best = {}
        import re
        for d in DIRS:
            for f in glob.glob(os.path.join(OUT, d, "video", "*.mp4")):
                m = re.match(r"(\d+)_", os.path.basename(f))
                if not m:
                    continue
                n = int(m.group(1))
                if shots and n not in shots:
                    continue
                if n not in best or os.path.getmtime(f) > os.path.getmtime(best[n]):
                    best[n] = f
        targets = [(os.path.basename(best[n]), best[n]) for n in sorted(best)]

    print("扫描 %d 个片段（每 %.2fs 抽 1 帧）" % (len(targets), every))
    bad = 0
    for name, p in targets:
        dur, hits = check_video(p, every)
        tag = "🔴 疑似" if hits else "✅ 干净"
        print("%-52s %5.2fs  %s  %d 处" % (name, dur, tag, len(hits)))
        for t, y, sp, th, adj in hits[:4]:
            print("      t=%.2fs  y=%d  横向跨度=%.0f%%  厚度=%.1f%%  相邻率=%.2f"
                  % (t, y, sp * 100, th * 100, adj))
        bad += 1 if hits else 0
    print("\n合计 %d/%d 片段命中" % (bad, len(targets)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
