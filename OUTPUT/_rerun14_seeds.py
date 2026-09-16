# -*- coding: utf-8 -*-
"""镜 14 多 seed 重跑：一次跑 N 个 seed，挑字幕最干净的版本。

为什么这么做：镜 14 的泄漏是 H3 对台词的**概率性**行为（约 45%），
单次重跑是抽卡；批量跑 N 次后按「字幕带白像素量」自动挑最优，
可把成功率提到 (1-0.45^N)。

关键：这 8 个镜的其余 7 个已用 delogo 解决，只剩镜 14
（delogo 对它在白衣+红领巾处产生竖条纹，不适用）。

用法：
  py -3.10 OUTPUT/_rerun14_seeds.py                  # 默认 3 个 seed
  py -3.10 OUTPUT/_rerun14_seeds.py --n=3 --steps=20
  py -3.10 OUTPUT/_rerun14_seeds.py --pick           # 只对已有版本重新挑最优
"""
import glob
import os
import shutil
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")
ACT = os.path.join(OUT, "04_classroom_dusk", "video")
SLUG = "zhang_defends_himself"
BASE_SEED = 9614
CROP = "crop=iw:150:0:ih-170"


def sub_strength(p, nfr=8):
    """字幕强度：底部字幕带的高亮像素累计（越低越干净）。"""
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


def candidates():
    """所有镜 14 候选片（排除备份）。"""
    cand = []
    for pat in (os.path.join(ACT, "%d_*.mp4" % 14),
                os.path.join(ACT, "*_14_*.mp4")):
        cand += [f for f in glob.glob(pat)
                 if "_bak_" not in os.path.basename(f)]
    return sorted(set(cand), key=os.path.getmtime)


def pick(best_only=True):
    cs = candidates()
    if not cs:
        print("没有候选片")
        return None
    scores = [(sub_strength(p), p) for p in cs]
    scores.sort()
    print("候选片字幕强度（越小越干净）：")
    for sc, p in scores:
        print("  %-52s %8d" % (os.path.basename(p), sc))
    best = scores[0][1]
    print("\n最优：%s（强度 %d）" % (os.path.basename(best), scores[0][0]))
    if best_only:
        return best
    return best


def main():
    n = 3
    steps = 20
    for a in sys.argv[1:]:
        if a.startswith("--n="):
            n = int(a.split("=", 1)[1])
        elif a.startswith("--steps="):
            steps = int(a.split("=", 1)[1])
    if "--pick" in sys.argv:
        pick()
        return 0

    print("镜 14 多 seed 重跑：%d 个 seed，steps=%d" % (n, steps))
    print("（每个约 4–12 分钟；ComfyUI 串行）\n")
    ok = 0
    for i in range(n):
        seed = BASE_SEED + 1 + i          # 避开原 9614
        # 用环境变量把 seed 传给 act 脚本？act2 脚本的 seed 写在 TASKS 里，
        # 这里改用「临时改脚本」的方式 —— 见 _seed_override.py
        env = dict(os.environ, S14_SEED=str(seed))
        r = subprocess.run(
            ["py", "-3.10", os.path.join(OUT, "_seed_override.py"),
             "--seed=%d" % seed, "--steps=%d" % steps],
            cwd=ROOT, capture_output=True, text=True, env=env)
        tail = (r.stdout or "").strip().splitlines()[-12:]
        for L in tail:
            print("  " + L)
        if r.returncode == 0:
            ok += 1
        else:
            for L in (r.stderr or "").strip().splitlines()[-6:]:
                print("  ! " + L)
    print("\n完成 %d/%d" % (ok, n))
    print("\n下一步：py -3.10 OUTPUT/_rerun14_seeds.py --pick")
    return 0


if __name__ == "__main__":
    sys.exit(main())
