# -*- coding: utf-8 -*-
"""★ 字幕区域「时间域补片」：用同镜其他帧的同区域内容填补字幕带。

适用场景（镜 14 实测）：`delogo` 空间插值在**框内有大面积高对比物体**
（白衣 + 红领巾）时会产生**竖条纹伪影**；且镜头缓慢推移，字幕位置
随时间**在画面里移动** —— 因此可以用「同一位置、其他时刻（无字幕处）」
的像素来填补。

做法（简化版，稳定可靠）：
  1. 逐帧计算字幕掩膜（白字+描边）→ 只在掩膜为真的像素上做替换
  2. 对每帧，在时间轴上取 ±N 帧中**对应像素不是字幕**的最近帧值
  3. 边缘羽化 1–2 px

比 delogo 好的地方：**只改字幕像素本身**，白衣/红领巾原样保留，
不会糊掉整块区域。

用法：
  py -3.10 OUTPUT/_delogo_temporal.py --shot=14           # 预览（出对比图）
  py -3.10 OUTPUT/_delogo_temporal.py --shot=14 --apply   # 落盘
"""
import glob
import os
import subprocess
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")


def newest(shot):
    cand = []
    for pat in (
        os.path.join(ROOT, "OUTPUT", "**", "video", "*_%02d_*.mp4" % shot),
        os.path.join(ROOT, "OUTPUT", "**", "video", "%d_*.mp4" % shot),
    ):
        cand += [f for f in glob.glob(pat, recursive=True)
                 if "_bak_" not in os.path.basename(f)
                 and "_delogo.mp4" not in f]
    cand = sorted(set(cand), key=os.path.getmtime)
    return cand[-1] if cand else None


def sub_mask_bgr(fr):
    """白字 + 描边 → 掩膜（全图）。"""
    g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
    bright = (g > 200).astype(np.uint8)
    dark = (g < 95).astype(np.uint8)
    dk = cv2.dilate(dark, np.ones((5, 5), np.uint8))
    cand = cv2.bitwise_or(cv2.bitwise_and(bright, dk), bright)
    return cv2.morphologyEx(cand, cv2.MORPH_CLOSE, np.ones((3, 5), np.uint8))


def process(src, dst, box, span=12, verbose=True):
    cap = cv2.VideoCapture(src)
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frames = []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        frames.append(fr)
    cap.release()
    n = len(frames)
    if n < 3:
        return False, "帧数太少"

    x, y, bw, bh = box
    x2, y2 = min(w, x + bw), min(h, y + bh)
    # 只处理框内
    rois = [f[y:y2, x:x2] for f in frames]
    masks = [sub_mask_bgr(r) for r in rois]
    masks = [cv2.dilate(m, np.ones((3, 3), np.uint8)) for m in masks]

    out_frames = [f.copy() for f in frames]
    fixed_px = 0
    for i in range(n):
        m = masks[i]
        if m.sum() < 20:
            continue
        m3 = m.astype(bool)
        # 找时间轴上最近的"无字幕"帧
        src_idx = None
        for d in range(1, span + 1):
            for j in (i - d, i + d):
                if 0 <= j < n and masks[j].sum() < 20:
                    src_idx = j
                    break
            if src_idx is not None:
                break
        if src_idx is None:
            continue
        roi_new = out_frames[src_idx][y:y2, x:x2].copy()
        base = out_frames[i][y:y2, x:x2]
        base[m3] = roi_new[m3]
        out_frames[i][y:y2, x:x2] = base
        fixed_px += int(m3.sum())

    tmp = dst + ".tmp.mp4"
    vw = cv2.VideoWriter(tmp, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for f in out_frames:
        vw.write(f)
    vw.release()
    # 用 ffmpeg 重编码（带原音轨）
    r = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", tmp, "-i", src,
         "-map", "0:v", "-map", "1:a?", "-c:v", "libx264",
         "-preset", "medium", "-crf", "18", "-c:a", "copy", dst],
        capture_output=True, text=True)
    os.remove(tmp)
    if verbose:
        print("   修补像素累计 %d，span=%d" % (fixed_px, span))
    return r.returncode == 0, (r.stderr or "")[:250]


def main():
    shot = 14
    apply_ = "--apply" in sys.argv
    for a in sys.argv[1:]:
        if a.startswith("--shot="):
            shot = int(a.split("=", 1)[1])
    import _subbox_coords as C
    box = C.get(shot)
    src = newest(shot)
    if not src or not box:
        print("镜 %d 缺视频或框" % shot)
        return 1
    print("镜 %d  %s  框=%s" % (shot, os.path.basename(src), box))
    dst = src.replace(".mp4", "_temporal.mp4")
    ok, err = process(src, dst, box)
    if not ok:
        print("  ✗ 失败：%s" % err)
        return 1
    # 出对比图
    cd = os.path.join(OUT, "_temporal_prev")
    os.makedirs(cd, exist_ok=True)
    tags = []
    for tag, p in (("BEFORE", src), ("AFTER", dst)):
        f = os.path.join(cd, "%s_%03d.jpg" % (tag, shot))
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "2.6", "-i", p,
                        "-frames:v", "1", "-vf",
                        "crop=520:120:280:480,scale=1040:-1", f],
                       capture_output=True)
        tags.append(f)
    print("  对比图：%s" % ", ".join(tags))
    if apply_:
        import shutil
        bak = os.path.join(os.path.dirname(src),
                           "_bak_temporal_" + os.path.basename(src))
        if not os.path.exists(bak):
            shutil.copy2(src, bak)
        shutil.move(dst, src)
        print("  ✅ 已落盘（原片备份 %s）" % os.path.basename(bak))
    else:
        print("  （预览；确认对比图后加 --apply）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
