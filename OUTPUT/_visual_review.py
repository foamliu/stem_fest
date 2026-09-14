# -*- coding: utf-8 -*-
"""全片视觉审查：从每个镜头的视频抽帧，拼成「联系表」大图，供视觉模型逐镜检查。

为什么要抽帧而不是直接看视频
    视觉模型对**单帧图像**的判读最可靠（构图/人物/文字/穿帮）。
    视频需逐帧推理，成本高且易漏。本工具把 126 镜各抽 3 帧（镜首/镜中/镜尾），
    每 6 个镜拼成一张 3×6 联系表 ⇒ 约 21 张图就能覆盖全片。

检查什么（对应本项目已知的坑）
    1. **字幕污染**：prompt 元信息被渲染成画面字幕（README §6.4 硬规则），
       如镜 91 曾出现「像在消化一件很难立刻接受的事」。
    2. **水印外泄**：参考图里的「钟南山」等文字被画进帧（LESSONS_LEARNED）。
    3. **人物一致性**：同一角色跨镜是否脸/服装漂移。
    4. **画面崩坏**：手指畸形、肢体错位、模型崩图、纯色/黑帧。
    5. **构图**：人物是否出画、道具是否缺失。

用法：
    py -3.10 OUTPUT/_visual_review.py                 # 全片 126 镜，每镜 3 帧
    py -3.10 OUTPUT/_visual_review.py --shots=91,94,96
    py -3.10 OUTPUT/_visual_review.py --per=4 --cols=4 # 每镜 4 帧，4 列
    py -3.10 OUTPUT/_visual_review.py --scale=560      # 单帧缩放宽度
"""
import glob
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")
SHEET_DIR = os.path.join(OUT, "_review_sheets")

ACTS = ["01_paper_plane", "04_classroom_dusk", "06_trench",
        "07_rice_field", "08_train_dining", "05_classroom_night"]


def probe_dur(p):
    """取时长（秒）。"""
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def collect():
    """{镜号: 最新版路径}"""
    best = {}
    for d in ACTS:
        for f in glob.glob(os.path.join(OUT, d, "video", "*.mp4")):
            m = re.match(r"(\d+)_", os.path.basename(f))
            if not m:
                continue
            n = int(m.group(1))
            if n not in best or os.path.getmtime(f) > os.path.getmtime(best[n]):
                best[n] = f
    return best


def grab(path, n_frames, tag):
    """抽 n_frames 帧（均匀分布，避开首尾各 8% 防转场黑帧）。"""
    dur = probe_dur(path)
    if dur <= 0:
        return []
    files = []
    for i in range(n_frames):
        frac = 0.08 + (0.84 * i / max(1, n_frames - 1)) if n_frames > 1 else 0.5
        t = dur * frac
        fp = os.path.join(SHEET_DIR, "_f_%s_%d.jpg" % (tag, i))
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "%.3f" % t,
                        "-i", path, "-frames:v", "1", "-q:v", "3", fp],
                       capture_output=True)
        if os.path.exists(fp) and os.path.getsize(fp) > 0:
            files.append(fp)
    return files


def main():
    args = sys.argv[1:]
    only = None
    per, cols, scale, rows_per_sheet = 3, 3, 520, 6
    for a in args:
        if a.startswith("--shots="):
            only = [int(x) for x in a.split("=", 1)[1].split(",") if x.strip()]
        elif a.startswith("--per="):
            per = int(a.split("=", 1)[1])
        elif a.startswith("--cols="):
            cols = int(a.split("=", 1)[1])
        elif a.startswith("--scale="):
            scale = int(a.split("=", 1)[1])
        elif a.startswith("--rows="):
            rows_per_sheet = int(a.split("=", 1)[1])

    os.makedirs(SHEET_DIR, exist_ok=True)
    for f in glob.glob(os.path.join(SHEET_DIR, "_f_*.jpg")):
        os.remove(f)

    from PIL import Image, ImageDraw

    shots = collect()
    keys = only if only else sorted(shots)
    keys = [k for k in keys if k in shots]
    print("待审查镜数：%d（每镜 %d 帧）" % (len(keys), per))

    per_sheet = cols * rows_per_sheet
    sheets = []
    for si in range(0, len(keys), per_sheet):
        chunk = keys[si:si + per_sheet]
        tile_w, tile_h = scale, int(scale * 608 / 1056)
        rows = (len(chunk) + cols - 1) // cols
        lab_h = 22
        canvas = Image.new("RGB",
                           (cols * tile_w + (cols + 1) * 5,
                            rows * (tile_h + lab_h) + (rows + 1) * 5),
                           (14, 14, 16))
        dr = ImageDraw.Draw(canvas)
        for i, n in enumerate(chunk):
            r, c = divmod(i, cols)
            frames = grab(shots[n], per, "s%03d" % n)
            x0 = 5 + c * (tile_w + 5)
            y0 = 5 + r * (tile_h + lab_h + 5)
            # 标签
            ver = re.search(r"_(\d{5})_\.mp4$", os.path.basename(shots[n]))
            dr.text((x0 + 2, y0 + 4), "SHOT %d  v%s" % (
                n, ver.group(1) if ver else "?"), fill=(240, 240, 120))
            sub_w = (tile_w - (per - 1) * 2) // per
            for j, fp in enumerate(frames[:per]):
                try:
                    im = Image.open(fp).convert("RGB").resize(
                        (sub_w, tile_h), Image.LANCZOS)
                except Exception:
                    continue
                canvas.paste(im, (x0 + j * (sub_w + 2), y0 + lab_h))
        sp = os.path.join(SHEET_DIR, "sheet_%02d.jpg" % (len(sheets) + 1))
        canvas.save(sp, quality=88)
        sheets.append(sp)
        print("  %s  (%d 镜)" % (os.path.basename(sp), len(chunk)))

    print("\n联系表已生成：%s" % SHEET_DIR)
    for s in sheets:
        print("  " + s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
