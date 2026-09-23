# -*- coding: utf-8 -*-
"""定妆照 vs 镜头帧 —— 并排三联图（定位「人脸漂移」是照片的锅还是 H3 的锅）。

为什么要三张并排
    只比「帧 vs 定妆照」得分低，**无法区分**：
      (A) 定妆照本身有多个版本，引用了旧的/差的 → 换图即可（成本低）
      (B) H3 没遵循参考图 → 得改 prompt/提 steps（成本高）
    把 **同角色所有候选定妆照** 与 **帧** 并排，一眼就能分辨。

布局
    第 1 行：帧（放大到脸区）
    第 2 行：该镜 `_shot_refs.json` 实际引用的人像参考图
    第 3 行：同角色目录下**其他候选**定妆照（备选换图用）

用法
    py -3.10 OUTPUT/_face_tri.py --shot=66 --char=01_liu_siqi
    py -3.10 OUTPUT/_face_tri.py --shot=49 --char=01_liu_siqi --out=_tri49.jpg
"""
import glob
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")
ASSETS = os.path.join(ROOT, "ASSETS")

ACTS = ["01_paper_plane", "03_classroom_day", "06_trench", "07_rice_field",
        "08_train_dining", "05_classroom_night"]


def latest_mp4(shot):
    best = None
    for a in ACTS:
        for f in glob.glob(os.path.join(OUT, a, "video", "%d_*.mp4" % shot)):
            if best is None or os.path.getmtime(f) > os.path.getmtime(best):
                best = f
    return best


def dur_of(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def main():
    shot, char, outname = None, None, "_tri.jpg"
    for a in sys.argv[1:]:
        if a.startswith("--shot="):
            shot = int(a.split("=", 1)[1])
        elif a.startswith("--char="):
            char = a.split("=", 1)[1]
        elif a.startswith("--out="):
            outname = a.split("=", 1)[1]
    if shot is None:
        print("!! 需要 --shot=<镜号>")
        return 1

    os.makedirs(os.path.join(OUT, "_tri"), exist_ok=True)
    mp4 = latest_mp4(shot)
    if not mp4:
        print("!! 镜 %d 没有 mp4" % shot)
        return 1

    tiles = []
    # 1) 帧
    d = dur_of(mp4)
    fp = os.path.join(OUT, "_tri", "_s%d_frame.jpg" % shot)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "%.3f" % (d * 0.5),
                    "-i", mp4, "-frames:v", "1", fp], capture_output=True)
    tiles.append(("FRAME 镜%d  %s" % (shot, os.path.basename(mp4)), fp))

    # 2) 实际引用的参考图
    refs_all = json.load(open(os.path.join(OUT, "_shot_refs.json"),
                              encoding="utf-8"))
    for r in (refs_all.get(str(shot), {}).get("refs") or []):
        bn = os.path.basename(r)
        if any(k in bn for k in ("hero", "closeup", "portrait")):
            tiles.append(("USED  %s" % bn, r))

    # 3) 同角色其他候选
    if char:
        for p in sorted(glob.glob(os.path.join(ASSETS, "CHARACTERS", char,
                                               "*.png"))):
            bn = os.path.basename(p)
            if any(t[1].endswith(bn) for t in tiles):
                continue
            tiles.append(("CAND  %s" % bn, p))

    from PIL import Image, ImageDraw
    tw = 620
    ims = []
    for lab, p in tiles:
        if not os.path.exists(p):
            continue
        im = Image.open(p).convert("RGB")
        im = im.resize((tw, int(tw * im.height / im.width)), Image.LANCZOS)
        ims.append((lab, im))
    if not ims:
        print("!! 没有可用图")
        return 1

    lab_h = 22
    H = sum(im.height + lab_h + 4 for _, im in ims) + 10
    canvas = Image.new("RGB", (tw + 12, H), (14, 14, 16))
    dr = ImageDraw.Draw(canvas)
    y = 4
    for lab, im in ims:
        dr.text((6, y), lab, fill=(255, 220, 120))
        canvas.paste(im, (6, y + lab_h))
        y += im.height + lab_h + 4
    sp = os.path.join(OUT, "_tri", outname)
    canvas.save(sp, quality=88)
    print("输出：%s" % sp)
    for lab, _ in ims:
        print("   %s" % lab)
    return 0


if __name__ == "__main__":
    sys.exit(main())
