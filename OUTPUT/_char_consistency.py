# -*- coding: utf-8 -*-
"""人物一致性比对图：把「镜头抽帧」与「该镜所用定妆照」并排贴在一起。

为什么这样做
    「人物跟定妆照是不是同一个人」是个**相对判断**，只看镜头帧无从判断，
    必须把**基准（定妆照）**和**待测（镜头帧）**放在同一张图里并排看。
    视觉模型在这种并排布局下判「脸型/发型/服装/年龄感是否一致」最稳。

布局（每个镜一行）
    ┌─────────────┬──────┬──────┬──────┐
    │  定妆照(1~2) │ 抽帧1 │ 抽帧2 │ 抽帧3 │
    └─────────────┴──────┴──────┴──────┘
    行首标注 SHOT N，定妆照格上标注 REF 文件名，方便报问题时精确定位。

成本控制（用户要求抽检，不逐帧）
    每镜只抽 3 帧（首/中/尾，避开转场黑帧），一镜一行；
    默认每张比对表放 4 镜 ⇒ 126 镜约 32 张图。可用 --shots 只查指定的镜。

用法：
    py -3.10 OUTPUT/_char_consistency.py                  # 全片，每表 4 镜
    py -3.10 OUTPUT/_char_consistency.py --shots=6,10,39
    py -3.10 OUTPUT/_char_consistency.py --per=3 --rows=4 --scale=430
"""
import glob
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")
DIR = os.path.join(OUT, "_consistency")
REFS_JSON = os.path.join(OUT, "_shot_refs.json")

# ★ 必须与各幕脚本的 OUT_ROOT 一致（act2→03_classroom_day 是 2026-09-21 目录合并后的口径，勿猜）
ACTS = ["01_paper_plane", "03_classroom_day", "06_trench",
        "07_rice_field", "08_train_dining", "05_classroom_night"]


def latest(shot):
    """该镜最新版视频路径。"""
    best, bt = None, 0
    for d in ACTS:
        for f in glob.glob(os.path.join(OUT, d, "video", "%02d_*.mp4" % shot)):
            if os.path.getmtime(f) > bt:
                best, bt = f, os.path.getmtime(f)
    return best


def dur_of(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def frames(shot, path, per):
    """抽 per 帧，返回文件列表。"""
    d = dur_of(path)
    if d <= 0:
        return []
    got = []
    for i in range(per):
        frac = 0.10 + 0.80 * i / max(1, per - 1) if per > 1 else 0.5
        fp = os.path.join(DIR, "_f%03d_%d.jpg" % (shot, i))
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "%.3f" % (d * frac),
                        "-i", path, "-frames:v", "1", "-q:v", "3", fp],
                       capture_output=True)
        if os.path.exists(fp) and os.path.getsize(fp) > 0:
            got.append(fp)
    return got


def main():
    args = sys.argv[1:]
    per, rows, scale = 3, 4, 430
    only = None
    for a in args:
        if a.startswith("--shots="):
            only = [int(x) for x in a.split("=", 1)[1].split(",") if x.strip()]
        elif a.startswith("--per="):
            per = int(a.split("=", 1)[1])
        elif a.startswith("--rows="):
            rows = int(a.split("=", 1)[1])
        elif a.startswith("--scale="):
            scale = int(a.split("=", 1)[1])

    if not os.path.exists(REFS_JSON):
        print("!! 请先运行 _shot_refs.py 生成镜-参考图映射")
        return 1
    refs = json.load(open(REFS_JSON, encoding="utf-8"))

    os.makedirs(DIR, exist_ok=True)
    for f in glob.glob(os.path.join(DIR, "_f*.jpg")):
        os.remove(f)

    from PIL import Image, ImageDraw

    keys = only if only else sorted(int(k) for k in refs)
    keys = [k for k in keys if str(k) in refs]
    print("人物一致性比对：%d 镜（每镜 %d 帧）" % (len(keys), per))

    tile_h = int(scale * 608 / 1056)
    ref_w = int(scale * 0.72)          # 定妆照列宽（可容纳 2 张并排）
    lab = 20
    sheets = []
    for si in range(0, len(keys), rows):
        chunk = keys[si:si + rows]
        W = ref_w + per * scale + 24
        H = lab + len(chunk) * (tile_h + 6) + 8
        canvas = Image.new("RGB", (W, H), (14, 14, 16))
        dr = ImageDraw.Draw(canvas)
        dr.text((6, 4), "REF(定妆照)  ||  SHOT 抽帧 x%d   —— 判断人物是否同一人" % per,
                fill=(255, 220, 120))
        for ri, n in enumerate(chunk):
            y = lab + ri * (tile_h + 6)
            v = refs[str(n)]
            # 定妆照列（最多 2 张竖排）
            rs = v["refs"][:2]
            if rs:
                each_h = tile_h // max(1, len(rs))
                each_w = int(each_h * 1056 / 608)
                for j, rp in enumerate(rs):
                    try:
                        im = Image.open(rp).convert("RGB").resize(
                            (each_w, each_h), Image.LANCZOS)
                        canvas.paste(im, (6 + j * (each_w + 3), y))
                    except Exception:
                        pass
                dr.text((8, y + 2), os.path.basename(rs[0])[:26],
                        fill=(120, 240, 160))
            else:
                dr.text((10, y + tile_h // 2), "(T2V 无角色)", fill=(200, 120, 120))
            # 抽帧列
            p = latest(n)
            if not p:
                dr.text((ref_w + 10, y + tile_h // 2), "NO VIDEO",
                        fill=(255, 90, 90))
                continue
            ver = re.search(r"_(\d{5})_\.mp4$", os.path.basename(p))
            dr.text((ref_w + 6, y + 2), "SHOT %d v%s" % (
                n, ver.group(1) if ver else "?"), fill=(240, 240, 120))
            for j, fp in enumerate(frames(n, p, per)):
                try:
                    im = Image.open(fp).convert("RGB").resize(
                        (scale, tile_h), Image.LANCZOS)
                    canvas.paste(im, (ref_w + 6 + j * (scale + 3), y))
                except Exception:
                    pass
        sp = os.path.join(DIR, "cons_%02d.jpg" % (len(sheets) + 1))
        canvas.save(sp, quality=86)
        sheets.append(sp)
        print("  %s  (%s)" % (os.path.basename(sp),
                              ",".join(str(x) for x in chunk)))
    print("\n输出目录：%s" % DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
