# -*- coding: utf-8 -*-
"""成片抽检 —— 从 `full_cut.mp4` 均匀抽 N 帧拼成一张总览图。

为什么要看"成片"而不只看分镜
    分镜各自没问题 ≠ 接起来没问题。拼接后要复核：
      · **转场是否突兀**（上一镜结尾与下一镜开头反差过大）
      · **色调是否连续**（同场景内亮度/色温是否一致）
      · **是否有坏帧/黑帧**（`-c copy` 无损拼接若源有坏帧会原样带过来）
    本脚本给出**不依赖模型读图**的量化指标（每帧平均亮度/对比度），
    异常帧能直接看出来，比纯肉眼看更可靠。

用法
    py -3.10 OUTPUT/_check_final.py                 # 抽 24 帧
    py -3.10 OUTPUT/_check_final.py --n=40
    py -3.10 OUTPUT/_check_final.py --src=OUTPUT/full_cut.mp4
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")


def main():
    n, src = 24, os.path.join(OUT, "full_cut.mp4")
    for a in sys.argv[1:]:
        if a.startswith("--n="):
            n = int(a.split("=", 1)[1])
        elif a.startswith("--src="):
            v = a.split("=", 1)[1]
            src = v if os.path.isabs(v) else os.path.join(ROOT, v)
    if not os.path.exists(src):
        print("!! 找不到 %s（先跑 OUTPUT/_concat_video.py）" % src)
        return 1

    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", src],
                       capture_output=True, text=True)
    try:
        dur = float(r.stdout.strip())
    except Exception:
        print("!! 读不到时长")
        return 1

    od = os.path.join(OUT, "_final_check")
    os.makedirs(od, exist_ok=True)
    from PIL import Image, ImageDraw
    import numpy as np

    rows = []
    tiles = []
    for i in range(n):
        t = dur * (i + 0.5) / n
        p = os.path.join(od, "f%02d.jpg" % i)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "%.2f" % t,
                        "-i", src, "-frames:v", "1", "-vf", "scale=320:-1", p],
                       capture_output=True)
        if not os.path.exists(p):
            continue
        im = Image.open(p).convert("RGB")
        a = np.asarray(im).astype("float32")
        lum = float(a.mean())
        std = float(a.std())
        rows.append((i, t, lum, std))
        tiles.append((t, im))

    # 量化体检：亮度极低（疑似黑帧）/ 对比度极低（疑似纯色）
    bad = [x for x in rows if x[2] < 6 or x[3] < 3.0]
    L = ["成片抽检：%s" % os.path.relpath(src, ROOT),
         "时长 %.1f s（%.2f 分）　抽 %d 帧" % (dur, dur / 60, len(rows)), "",
         "%-4s %-8s %-8s %-8s %s" % ("#", "时刻s", "亮度", "对比度", "判定")]
    for i, t, lum, std in rows:
        flag = "★可疑（近黑/纯色）" if (lum < 6 or std < 3.0) else ""
        L.append("%-4d %-8.1f %-8.1f %-8.1f %s" % (i, t, lum, std, flag))
    L.append("")
    L.append("可疑帧：%d 个 %s" % (len(bad),
                               "" if not bad else "→ " + str(
                                   [x[0] for x in bad])))
    L.append("⚠️ 字幕镜/黑屏转场镜（46/74/105/123/124）本身就该是黑或白，"
             "出现\"可疑\"先核对镜号再下结论。")

    # 拼图（每行 4 张）
    if tiles:
        cols = 4
        tw = tiles[0][1].width
        th = tiles[0][1].height + 16
        rn = (len(tiles) + cols - 1) // cols
        canvas = Image.new("RGB", (tw * cols, th * rn), (14, 14, 16))
        dr = ImageDraw.Draw(canvas)
        for k, (t, im) in enumerate(tiles):
            x = (k % cols) * tw
            y = (k // cols) * th
            dr.text((x + 4, y + 2), "%.1fs" % t, fill=(255, 210, 120))
            canvas.paste(im, (x, y + 16))
        pp = os.path.join(od, "final_sheet.jpg")
        canvas.save(pp, quality=86)
        L.append("拼图：%s" % os.path.relpath(pp, ROOT))

    txt = "\n".join(L)
    print(txt)
    open(os.path.join(OUT, "_final_check.txt"), "w",
         encoding="utf-8").write(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
