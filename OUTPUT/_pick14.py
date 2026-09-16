# -*- coding: utf-8 -*-
"""镜 14 定版：把「字幕干净」的那个版本设为正式片，其余移入 _rejected/。

为什么需要：镜 14 有多个 seed 版本（00002–00008），`_concat_video.py`
按 **mtime 取最新** —— 若不清理，会把**含字幕的晚期版本**当正式片用。

做法：
  1. 用「字幕带白像素量」给所有候选打分（越小越干净）
  2. 最优版**保持原名不动**；其它版移入 `_rejected/` 子目录（不删除，留证据）
  3. 打印最终选定结果

用法：
  py -3.10 OUTPUT/_pick14.py            # 预览
  py -3.10 OUTPUT/_pick14.py --apply    # 落盘
"""
import glob
import os
import shutil
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "OUTPUT", "04_classroom_dusk", "video")
SLUG = "zhang_defends_himself"
CROP = "crop=iw:150:0:ih-170"


def strength(p, nfr=8):
    """字幕强度：底部字幕带高亮像素累计（越小越干净）。"""
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True)
    try:
        d = float(r.stdout.strip())
    except ValueError:
        d = 4.0
    tot = 0
    for i in range(nfr):
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss",
                            "%.2f" % (d * (i + 0.5) / nfr), "-i", p,
                            "-frames:v", "1", "-f", "rawvideo",
                            "-pix_fmt", "gray", "-vf", CROP, "-"],
                           capture_output=True)
        if r.stdout:
            tot += int((np.frombuffer(r.stdout, dtype=np.uint8) > 205).sum())
    return tot


def main():
    cands = [f for f in glob.glob(os.path.join(DIR, "14_*.mp4"))
             if "_bak_" not in os.path.basename(f)
             and "_split" not in f and "_temporal" not in f
             and "_delogo" not in f]
    if not cands:
        print("无候选片")
        return 1
    scored = sorted(((strength(p), p) for p in cands))
    print("候选片（按字幕强度升序，越小越干净）：")
    for sc, p in scored:
        print("  %-50s %8d" % (os.path.basename(p), sc))
    best_sc, best = scored[0]
    print("\n★ 选定：%s（字幕强度 %d）" % (os.path.basename(best), best_sc))
    others = [p for _sc, p in scored[1:]]
    print("   落选 %d 个，将移入 _rejected/" % len(others))
    if "--apply" not in sys.argv:
        print("\n（预览；加 --apply 落盘）")
        return 0
    rej = os.path.join(DIR, "_rejected")
    os.makedirs(rej, exist_ok=True)
    for p in others:
        dst = os.path.join(rej, os.path.basename(p))
        if os.path.exists(dst):
            os.remove(dst)
        shutil.move(p, dst)
        print("   移出 %s" % os.path.basename(p))
    # 备份也清理（只留 best 对应的 _bak_，其余移走）
    for b in glob.glob(os.path.join(DIR, "_bak_14_*.mp4")):
        base = os.path.basename(b).replace("_bak_", "")
        if base != os.path.basename(best):
            dst = os.path.join(rej, os.path.basename(b))
            if os.path.exists(dst):
                os.remove(dst)
            shutil.move(b, dst)
    print("\n✅ 完成。镜 14 正式片 = %s" % os.path.basename(best))
    print("   （_rejected/ 里保留了其余版本与备份，可随时回查）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
