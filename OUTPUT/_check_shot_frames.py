# -*- coding: utf-8 -*-
"""逐帧放大核验：对比新旧片下部区域，判读字幕是否消失。

★ 纪律（README §6.6b ④）：**判读泄漏必须放大下部 ≥640 宽单帧看**，
   压缩拼图（scale<600）会把细笔画与背景混掉，导致误判。

用法：
    py -3.10 OUTPUT/_check_shot_frames.py 14                      # 自动取该镜最新片 vs 备份
    py -3.10 OUTPUT/_check_shot_frames.py 14 --new=xxx.mp4 --old=yyy.mp4
    py -3.10 OUTPUT/_check_shot_frames.py 14 --n=8 --out=OUTPUT/_chk
"""
import glob
import os
import subprocess
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIDE = 640                     # ★ 下部裁剪宽度，必须 ≥640


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def duration(p):
    r = sh(["ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "csv=p=0", p])
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def grab(src, t, dst, crop="crop=iw:ih*0.34:0:ih*0.63"):
    r = sh(["ffmpeg", "-y", "-v", "error", "-ss", "%.2f" % t, "-i", src,
            "-frames:v", "1", "-vf", "%s,scale=%d:-1" % (crop, WIDE), dst])
    if not os.path.exists(dst):
        print("     ffmpeg: %s" % (r.stderr or "")[:300])
        return False
    return True


def newest_shot(shot):
    """按 mtime 找该镜最新一段视频（排除 _bak_）。"""
    pats = [
        os.path.join(ROOT, "OUTPUT", "**", "video", "*_%02d_*.mp4" % shot),
        os.path.join(ROOT, "OUTPUT", "**", "video", "%d_*.mp4" % shot),
    ]
    cand = []
    for p in pats:
        cand += [f for f in glob.glob(p, recursive=True)
                 if "_bak_" not in os.path.basename(f)]
    cand = sorted(set(cand), key=os.path.getmtime)
    return cand[-1] if cand else None


def shots_same_shot(path, shot):
    base = os.path.basename(path)
    return base.startswith("%d_" % shot) or ("_%02d_" % shot) in base


def main():
    args = sys.argv[1:]
    if not args or not args[0].isdigit():
        print(__doc__)
        return 1
    shot = int(args[0])
    n = 8
    outdir = None
    newp = oldp = None
    for a in args[1:]:
        if a.startswith("--n="):
            n = int(a.split("=", 1)[1])
        elif a.startswith("--out="):
            outdir = a.split("=", 1)[1]
        elif a.startswith("--new="):
            newp = a.split("=", 1)[1]
        elif a.startswith("--old="):
            oldp = a.split("=", 1)[1]

    newp = newp or newest_shot(shot)
    if not newp:
        print("找不到镜 %d 的视频" % shot)
        return 1
    newp = newp if os.path.isabs(newp) else os.path.join(ROOT, newp)
    if not oldp:
        d = os.path.dirname(newp)
        baks = sorted(glob.glob(os.path.join(d, "_bak_*.mp4")),
                      key=os.path.getmtime)
        same = [b for b in baks if shots_same_shot(
            os.path.basename(b).replace("_bak_", ""), shot)]
        oldp = same[-1] if same else None
    if oldp and not os.path.isabs(oldp):
        oldp = os.path.join(ROOT, oldp)

    outdir = outdir or os.path.join(ROOT, "OUTPUT", "_chk%02d" % shot)
    outdir = outdir if os.path.isabs(outdir) else os.path.join(ROOT, outdir)
    os.makedirs(outdir, exist_ok=True)

    pairs = []
    if oldp and os.path.exists(oldp):
        pairs.append(("OLD", oldp))
    pairs.append(("NEW", newp))

    print("镜 %d" % shot)
    for tag, p in pairs:
        print("  %s: %s" % (tag, os.path.basename(p)))
    durations = {}
    for tag, p in pairs:
        durations[tag] = duration(p)
        if durations[tag] <= 0:
            print("  !! 无法取 %s 时长（ffprobe 失败）" % tag)
    d = durations.get("NEW") or durations.get("OLD") or 0.0
    print("  时长: %.2fs" % d)

    frames = {}
    for tag, p in pairs:
        dd = durations.get(tag) or d
        lst = []
        for i in range(n):
            t = dd * (i + 0.5) / n
            f = os.path.join(outdir, "%s_%02d.jpg" % (tag, i))
            if grab(os.path.abspath(p), t, os.path.abspath(f)):
                lst.append(f)
            else:
                print("  !! %s frame %d 抓帧失败 (t=%.2f)" % (tag, i, t))
        frames[tag] = lst

    # 拼图：每行 n/2 张，行间距给标题
    cols = n // 2 if n % 2 == 0 else n
    rows_per = n // cols
    if not frames.get("NEW"):
        print("抽取失败")
        return 1
    w = Image.open(frames["NEW"][0]).width
    h = Image.open(frames["NEW"][0]).height
    band = 22
    total_rows = sum(rows_per for _ in pairs)
    canvas = Image.new("RGB", (w * cols, (h + band) * total_rows), (12, 12, 14))
    dr = ImageDraw.Draw(canvas)
    row = 0
    for tag, _p in pairs:
        colr = (255, 200, 90) if tag == "OLD" else (120, 230, 140)
        for i, f in enumerate(frames.get(tag, [])):
            r, c = i // cols, i % cols
            x, y = c * w, (row + r) * (h + band)
            dr.text((x + 8, y + 4), "%s  frame %d  (t=%.2fs)" % (
                tag, i, d * (i + 0.5) / n), fill=colr)
            canvas.paste(Image.open(f).convert("RGB"), (x, y + band))
        row += rows_per
    dst = os.path.join(outdir, "S%02d_OLD_vs_NEW.jpg" % shot)
    canvas.save(dst, quality=90)
    print("→ %s" % dst)
    print("   上行=%s  下行=NEW（下部 %d 宽放大）" % (
        "OLD" if len(pairs) > 1 else "(无旧片)", WIDE))
    return 0


if __name__ == "__main__":
    sys.exit(main())
