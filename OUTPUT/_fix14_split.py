# -*- coding: utf-8 -*-
"""镜 14 专项：用**多个窄框分段**擦除字幕，规避单大框跨高对比区产生的竖条纹。

原理（镜 14 实测）：
  · 单框 400×66（跨白衣 + 红领巾）→ delogo 横向插值把红领巾抹成竖条纹 ❌
  · 单框 460×130 → 整块糊掉 ❌
  ⇒ 拆成多个**窄而矮**的框，每个框只覆盖**单一材质**（纯白衣 / 纯领巾），
     这样插值源与目标同色，伪影最小。

用法：
  py -3.10 OUTPUT/_fix14_split.py --dry     # 预览框布局（出标注图）
  py -3.10 OUTPUT/_fix14_split.py --apply   # 落盘
"""
import glob
import os
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 镜 14 字幕位于 y≈502..568，x≈330..730。按 x 方向切成若干窄条，
# 每条只跨一种材质；同时上下各内收 2px 避开领巾边缘。
BANDS = [
    (330, 502, 100, 66),   # 左段（白衣）
    (430, 502, 100, 66),   # 中左（白衣 / 领巾边缘）
    (530, 502, 100, 66),   # 中右（领巾）
    (630, 502, 100, 66),   # 右段（白衣）
]


def newest(shot=14):
    cand = []
    for pat in (
        os.path.join(ROOT, "OUTPUT", "**", "video", "*_%02d_*.mp4" % shot),
        os.path.join(ROOT, "OUTPUT", "**", "video", "%d_*.mp4" % shot),
    ):
        cand += [f for f in glob.glob(pat, recursive=True)
                 if "_bak_" not in os.path.basename(f)
                 and "_delogo" not in f and "_temporal" not in f]
    cand = sorted(set(cand), key=os.path.getmtime)
    return cand[-1] if cand else None


def vf_chain(bands):
    return ",".join("delogo=x=%d:y=%d:w=%d:h=%d" % b for b in bands)


def main():
    src = newest()
    if not src:
        print("找不到镜 14 视频")
        return 1
    print("源：%s" % os.path.basename(src))
    for b in BANDS:
        print("  框 x=%d y=%d w=%d h=%d（下沿 %d）" % (b + (b[1] + b[3],)))
    dst = src.replace(".mp4", "_split.mp4")
    r = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", src, "-vf", vf_chain(BANDS),
         "-c:v", "libx264", "-preset", "medium", "-crf", "19",
         "-c:a", "copy", dst],
        capture_output=True, text=True)
    if r.returncode != 0:
        print("✗ 失败：%s" % (r.stderr or "")[:300])
        return 1
    # 出对比图（放大）
    cd = os.path.join(ROOT, "OUTPUT", "_fix14")
    os.makedirs(cd, exist_ok=True)
    made = []
    for tag, p in (("BEFORE", src), ("AFTER", dst)):
        f = os.path.join(cd, "%s.jpg" % tag)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "2.6", "-i", p,
                        "-frames:v", "1", "-vf",
                        "crop=520:120:280:480,scale=1040:-1", f],
                       capture_output=True)
        made.append(f)
    # 标注框布局图
    b = os.path.join(cd, "BOXES.jpg")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "2.6", "-i", src,
                    "-frames:v", "1",
                    "-vf", ",".join("drawbox=x=%d:y=%d:w=%d:h=%d:color=red@0.9:t=2"
                                    % t for t in BANDS),
                    b], capture_output=True)
    print("对比图：%s" % ", ".join(made + [b]))
    if "--apply" in sys.argv:
        bak = os.path.join(os.path.dirname(src),
                           "_bak_split_" + os.path.basename(src))
        if not os.path.exists(bak):
            shutil.copy2(src, bak)
        shutil.move(dst, src)
        print("✅ 已落盘（备份 %s）" % os.path.basename(bak))
    else:
        print("（预览；确认 AFTER 无条纹后加 --apply）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
