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

import io

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


def _blobs(mask):
    """4-邻域连通块统计（纯 numpy 手写，避免依赖 scipy）→ (块数, 最大块像素数)。

    ★ 为什么要数"块"而不是只看列投影段数
      列投影（横向有没有亮像素）对**大色块**与**字形**是一样的；
      但连通块拓扑完全不同：字形是"很多小岛"，脸颊/额头是"一片大陆"。
    """
    h, w = mask.shape
    seen = np.zeros((h, w), dtype=bool)
    nblob = 0
    maxblob = 0
    for i in range(h):
        for j in range(w):
            if not mask[i, j] or seen[i, j]:
                continue
            nblob += 1
            stack = [(i, j)]
            seen[i, j] = True
            cnt = 0
            while stack:
                y, x = stack.pop()
                cnt += 1
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            if cnt > maxblob:
                maxblob = cnt
    return nblob, maxblob


def scan_frame(a):
    """判定一帧里是否含**烧入字幕**。

    ★★ 2026-09-17 演进史（三轮，每轮都被实测打脸 —— 记下来别再走弯路）

    v1（原始）判据 = 「亮像素里"紧贴暗像素"的比例 adj ≥ 0.55」
      ⛔ **漏检镜 36**：那是**夜间暗场**，dark 像素 19.8 万、暗掩膜近乎全屏，
         dilation 后 halo 也全屏 ⇒ 分母被稀释，adj 掉到 0.30，
         而字幕明明在（bright≥235 有 441 px）。⇒ 该判据在暗场必然失效。

    v2 判据 = 「滑动窗 + 列投影离散段数 ≥4 + 平均字宽 ≤6%」
      ⛔ **误报 96/126**：把**人脸高光、牙齿、白领口、桌面反光**全算进去了
         （实测镜 02/60 抽帧无字却判命中）。
         根因：这些结构同样是"多个窄亮块横向排列"，与字形**在列投影上不可分**。

    v3（当前）⇒ **加上字幕独有的三条硬特征**，缺一不可：
      H1 **纯白 + 硬边**：字幕是渲染上去的矢量白字（RGB 三通道同时 ≥240），
         而人脸高光/牙齿是**暖色**（R>G>B，蓝通道明显低）⇒ 用 B 通道阈值即可分开。
      H2 **单行、位于下方固定带**：字幕基线稳定在 0.78–0.94H，且**只有一行**；
         人脸高光会跨多行连续出现（脸颊到下巴）。
      H3 **带内垂直投影是"一峰"**：字幕的亮像素在所选窗内**上下留白**
         （字上下各有 ≥2 行无亮像素）；人脸高光是连续的。

    这三条让镜 36（真字幕）命中、镜 02/60（人脸）不再命中。
    """
    H, W, _ = a.shape
    # H2：只查字幕实际落位带
    ys, ye = int(H * 0.76), int(H * 0.96)
    if ye - ys < 20:
        return False, 0, 0.0, 0.0, 0.0
    band_area = a[ys:ye]
    bh, bw, _ = band_area.shape

    # H1 ★ 字幕是**渲染上去的近中性白**（实测 |R−B| ≈ 5–7）；
    #    人脸高光/牙齿是**暖色**（|R−B| 36–75）。
    #    ⚠️ 只用 `|R−B| <= 12` 这一条会漏掉"明亮但偏黄"的字幕，
    #       但配合 H4（连通块拓扑）已足够区分 —— 见下方 `_blobs`。
    R, G, B = band_area[:, :, 0], band_area[:, :, 1], band_area[:, :, 2]
    white = (np.minimum(np.minimum(R, G), B) >= 205) & (np.abs(R - B) <= 14)

    if int(white.sum()) < 120:
        return False, 0, 0.0, 0.0, 0.0

    for mask in (white,):
        # H3：找行带（字幕行的上下留白）
        rowsum = mask.sum(axis=1)
        thr = max(3, int(W * 0.004))
        on = rowsum >= thr
        segs, s = [], None
        for i, v in enumerate(on):
            if v and s is None:
                s = i
            elif not v and s is not None:
                segs.append((s, i - 1))
                s = None
        if s is not None:
            segs.append((s, len(on) - 1))
        # ★ 字幕的"行带"可能被字内间隙切成多段（实测 f0 断成 6 段、每段仅 1–3 行）
        #   ⇒ 先把**间隔 ≤3 行**的相邻段合并，还原成"一整行字"。
        merged = []
        for a0, b0 in segs:
            if merged and a0 - merged[-1][1] <= 3:
                merged[-1] = (merged[-1][0], b0)
            else:
                merged.append((a0, b0))
        for a0, b0 in merged:
            thick = (b0 - a0 + 1) / float(H)
            if not (0.008 <= thick <= 0.10):
                continue
            band = mask[a0:b0 + 1]
            cols = np.where(band.any(axis=0))[0]
            if cols.size < 4:
                continue
            span = (cols.max() - cols.min() + 1) / float(W)
            if span < 0.06:
                continue
            # ★★★ H4 **连通块拓扑**（本轮真正的判别器）
            #   字形 = 很多小岛（≥8 块，最大块 < 40% 总面积）
            #   人脸高光/白领口 = 一片大陆（1–3 块，最大块 > 60%）
            nblob, maxblob = _blobs(band)
            tot = float(band.sum())
            if nblob < 8 or maxblob > 0.40 * tot:
                continue
            dens = tot / float(band.size)
            if not (0.01 <= dens <= 0.60):
                continue
            return True, ys + a0, span, thick, float(nblob)

    return False, 0, 0.0, 0.0, 0.0
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
    DIRS = ["01_paper_plane", "03_classroom_day", "06_trench",
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
    # ★ 2026-09-17：结构化结果**自己写 UTF-8 文件**，不依赖 shell 重定向
    #   （PowerShell `>` 会产出 UTF-16 + 控制台代码页双重编码，中文全乱）。
    tsv = io.open(os.path.join(OUT, "_scan_result.tsv"), "w", encoding="utf-8")
    tsv.write("file\tdur\thits\tt\ty\tspan\tthick\tnseg\n")
    bad = 0
    for name, p in targets:
        dur, hits = check_video(p, every)
        tag = "🔴 疑似" if hits else "✅ 干净"
        print("%-52s %5.2fs  %s  %d 处" % (name, dur, tag, len(hits)))
        for t, y, sp, th, adj in hits[:4]:
            print("      t=%.2fs  y=%d  横向跨度=%.0f%%  厚度=%.1f%%  段数=%.0f"
                  % (t, y, sp * 100, th * 100, adj))
        for t, y, sp, th, adj in hits:
            tsv.write("%s\t%.2f\t%d\t%.2f\t%d\t%.3f\t%.3f\t%.0f\n"
                      % (name, dur, len(hits), t, y, sp, th, adj))
        bad += 1 if hits else 0
    tsv.close()
    print("\n合计 %d/%d 片段命中" % (bad, len(targets)))
    print("结构表 -> %s" % os.path.join(OUT, "_scan_result.tsv"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
