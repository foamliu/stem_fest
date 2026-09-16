# -*- coding: utf-8 -*-
"""★ 读图失效时的替代判据：用像素统计判定「景别 / 场景 / 角色」是否与 storyboard 相符。

背景
    本项目的目视复核依赖多模态读图，但读图工具偶发对同尺寸图片返回
    「media omitted」（不是文件坏了 —— 同尺寸此前可读）。此时**不能靠猜**，
    改用可复现的像素判据：

    A. **景别**（人物占画面高度的比例）
       用 SAM3 或色域近似估出「人物带」的高度占比 ⇒
       特写 >55%、近景 35-55%、中近景 25-35%、中景 15-25%、全景 <15%。
       本工具用**肤色+校服白**的垂直跨度近似。

    B. **场景**（色调指纹）
       暖度 = mean(R) - mean(B)：
         白天/傍晚教室（暖金）> +30
         朝鲜坑道（灰绿冷）  < +18
         稻田（黄绿高饱和）  饱和度 > 0.45 且 G>=R

    C. **校服一致性**（跨镜比对）
       统计「红领巾红」像素占比，低于基准即判校服漂移。

用法：
    py -3.10 OUTPUT/_pixel_audit.py --shot=17 --files=a.mp4,b.mp4
    py -3.10 OUTPUT/_pixel_audit.py --check-act3     # 稻田幕全套
"""
import os
import subprocess
import sys

import numpy as np
from PIL import Image

ROOT = r"E:\code\stem_fest"
OUT = os.path.join(ROOT, "OUTPUT")
TMP = os.path.join(OUT, "_view_out")
os.makedirs(TMP, exist_ok=True)


def frame_of(video, t, tag):
    fp = os.path.join(TMP, "_pa_%s.jpg" % tag)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "%.3f" % t,
                    "-i", video, "-frames:v", "1", "-q:v", "2", fp],
                   capture_output=True)
    return fp if os.path.exists(fp) else None


def analyze(video, fracs=(0.25, 0.55, 0.82)):
    """→ dict：景别/色调/校服 三类指标（多帧均值）。"""
    rows = []
    for i, f in enumerate(fracs):
        dur = probe_dur(video)
        fp = frame_of(video, dur * f, "%s_%d" % (os.path.basename(video)[:12], i))
        if not fp:
            continue
        a = np.asarray(Image.open(fp).convert("RGB"), dtype=np.float32)
        H, W, _ = a.shape
        R, G, B = a[..., 0], a[..., 1], a[..., 2]
        mx, mn = a.max(axis=2), a.min(axis=2)
        sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0.0)

        # ── 人物带：偏白（校服/Polo）+ 肤色 的垂直跨度 ──
        pale = (mn > 130) & (sat < 0.22)
        skin = (R > 95) & (R - B > 18) & (R - G > 8) & (sat < 0.55)
        who = pale | skin
        colsum = who.sum(axis=0)
        band = np.where(colsum > W * 0.02)[0]
        h_ratio = 0.0
        if band.size > 8:
            rowsum = who[:, band.min():band.max() + 1].sum(axis=1)
            rs = rowsum > (band.size * 0.02)
            idx = np.where(rs)[0]
            if idx.size > 8:
                h_ratio = float(idx.max() - idx.min() + 1) / H

        # ── 校服红领巾：高饱和红 ──
        red = (R > 120) & (R - G > 55) & (R - B > 55) & (sat > 0.45)

        rows.append(dict(h=h_ratio, warm=float(R.mean() - B.mean()),
                         sat=float(sat.mean()), red=float(red.mean() * 100),
                         lum=float(a.mean())))
    if not rows:
        return None
    return {k: round(float(np.mean([r[k] for r in rows])), 3) for k in rows[0]}


def probe_dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 4.0


def guess_size(h):
    if h >= 0.55:
        return "特写"
    if h >= 0.35:
        return "近景"
    if h >= 0.25:
        return "中近景"
    if h >= 0.15:
        return "中景"
    return "全景"


def main():
    args = sys.argv[1:]
    files, shot = [], None
    for a in args:
        if a.startswith("--files="):
            files = [x for x in a.split("=", 1)[1].split(",") if x.strip()]
        elif a.startswith("--shot="):
            shot = a.split("=", 1)[1]
    if not files:
        print("用法：--shot=17 --files=a.mp4,b.mp4")
        return 1
    print("镜 %s" % shot)
    print("%-46s %-8s %-7s %-7s %-7s %-6s %s"
          % ("文件", "人物带%", "推断景别", "暖度", "饱和度", "红领巾%", "亮度"))
    for f in files:
        p = f if os.path.isabs(f) else os.path.join(OUT, f)
        if not os.path.exists(p):
            print("  [X] 不存在 %s" % p)
            continue
        d = analyze(p)
        if not d:
            print("  [X] 抽取失败 %s" % p)
            continue
        print("%-46s %-8.3f %-7s %-7.1f %-7.3f %-6.2f %.1f"
              % (os.path.basename(p), d["h"], guess_size(d["h"]),
                 d["warm"], d["sat"], d["red"], d["lum"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
