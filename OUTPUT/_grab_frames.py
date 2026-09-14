# -*- coding: utf-8 -*-
"""抽帧巡检：按镜号从各幕产物里抽首/中帧，拼成 montage 供人工目视验收。

用法：
    py -3.10 OUTPUT/_grab_frames.py 1 4 19 39 45 60 81 97 105
"""
import glob
import os
import subprocess
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT", "_view_out")
DIRS = ["01_paper_plane", "04_classroom_dusk", "06_trench", "07_rice_field",
        "08_train_dining", "05_classroom_night"]


def find(shot):
    pat = os.path.join(ROOT, "OUTPUT", "*", "video", "%02d_*.mp4" % shot)
    hit = sorted(glob.glob(pat))
    return hit[0] if hit else None


def main():
    shots = [int(a) for a in sys.argv[1:]] or [1]
    os.makedirs(OUT, exist_ok=True)
    thumbs = []
    for s in shots:
        p = find(s)
        if not p:
            print("镜 %-3d 无产物" % s)
            continue
        jpg = os.path.join(OUT, "_f%03d.jpg" % s)
        # 取中点帧（避开首帧的过渡）
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "1.5",
                        "-i", p, "-frames:v", "1", jpg], capture_output=True)
        if os.path.isfile(jpg):
            thumbs.append((s, jpg))
            print("镜 %-3d OK  %s" % (s, os.path.basename(p)))

    if not thumbs:
        return
    # 拼 montage：每行 3 张
    ims = [(s, Image.open(p).convert("RGB")) for s, p in thumbs]
    cols, tw = 3, 420
    rows = (len(ims) + cols - 1) // cols
    th = int(tw * 9 / 16)
    gap = 6
    canvas = Image.new("RGB", (cols * tw + (cols + 1) * gap,
                              rows * th + (rows + 1) * gap), (16, 16, 18))
    for i, (s, im) in enumerate(ims):
        r, c = divmod(i, cols)
        canvas.paste(im.resize((tw, th), Image.LANCZOS),
                     (gap + c * (tw + gap), gap + r * (th + gap)))
    dst = os.path.join(OUT, "_montage_%s.jpg" % "_".join(str(s) for s, _ in thumbs[:6]))
    canvas.save(dst, quality=88)
    print("\nmontage -> %s  %s" % (dst, canvas.size))


if __name__ == "__main__":
    main()
