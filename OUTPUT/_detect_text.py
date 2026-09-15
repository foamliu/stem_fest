# -*- coding: utf-8 -*-
"""画面文字自动检测（启发式）—— ⚠️ **实测不可用，保留仅作负面记录**。

★ 2026-09-15 实测结论：**这个启发式不可用，别再用它下结论。**

    思路：字幕 = 近白高亮 + 低饱和 + 成行 → 在下部 38% 统计白色覆盖率与白带行数。
    在 9 镜样本（5 有字幕 / 4 干净）上实测：

      | 镜   | 真值 | 覆盖率 | 白带 | 结果 |
      |:----:|:----:|-------:|:----:|:----:|
      | 14   | 有字 | 0.0664 | 2    | ✅ 检出 |
      | 85   | 有字 | 0.0626 | 3    | ✅ 检出 |
      | 88   | 有字 | 0.0206 | 3    | ✅ 检出 |
      | **86**  | 有字 | 0.0082 | 2    | ❌ **漏报** |
      | **112** | 有字 | 0.0098 | 1    | ❌ **漏报** |
      | **15**  | 干净 | 0.0423 | 3    | ❌ **误报**（白校服）|
      | **30**  | 干净 | 0.2209 | 3    | ❌ **严重误报**（白衣占画面）|
      | 60   | 干净 | 0.0028 | 0    | ✅ |
      | 113  | 干净 | 0.0000 | 0    | ✅ |

      ⇒ **误报 3/4、漏报 2/5** —— 白校服/白桌面/白字道具与字幕同一特征，
        而细字/半透明字又达不到覆盖率阈值。**没有可用的分辨阈值。**

★ 正确做法（当前唯一可靠）
    1. `py -3.10 OUTPUT/_scan_subtitles.py --all --batch=12`  → 出**下部带拼图**
    2. **人眼**逐张读，找**成行的中文句子**
    3. 有疑问再用 `_trace_leak.py` **溯源**（比对泄漏文字与 prompt 各段）
    ⚠️ 这一步现在无法自动化；README §4.1 早就说明"读图不可复现"，
       本脚本就是那次教训的复现。

用法（照旧可跑，但**结论不可信**）
    py -3.10 OUTPUT/_detect_text.py --shots=7,14,85
"""
import glob
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")
DIRS = ["01_paper_plane", "04_classroom_dusk", "06_trench",
        "07_rice_field", "08_train_dining", "05_classroom_night"]


def latest(n):
    best = None
    for d in DIRS:
        for f in glob.glob(os.path.join(OUT, d, "video", "%d_*.mp4" % n)):
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


def detect(path, frames=(0.3, 0.45, 0.6, 0.75, 0.9)):
    """返回 [(帧序号, 覆盖率, 白带数)]。"""
    import numpy as np
    from PIL import Image

    d = dur_of(path)
    od = os.path.join(OUT, "_textdet")
    os.makedirs(od, exist_ok=True)
    res = []
    for i, fr in enumerate(frames):
        p = os.path.join(od, "_t%03d_%d.png" % (abs(hash(path)) % 1000, i))
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "%.2f" % (d * fr),
                        "-i", path, "-frames:v", "1", p], capture_output=True)
        if not os.path.exists(p):
            continue
        im = Image.open(p).convert("RGB")
        w, h = im.size
        im = im.crop((0, int(h * 0.62), w, h))          # 下部 38%
        a = np.asarray(im).astype("float32")
        mx, mn = a.max(axis=2), a.min(axis=2)
        white = (mx > 200) & ((mx - mn) < 45)
        rows = white.sum(axis=1)
        cov = float(white.mean())
        row_mask = rows > (w * 0.06)
        bands, run = 0, 0
        for v in row_mask:
            if v:
                run += 1
            else:
                if run >= 6:
                    bands += 1
                run = 0
        if run >= 6:
            bands += 1
        res.append((i, cov, bands))
        try:
            os.remove(p)
        except Exception:
            pass
    return res


def main():
    thresh = 0.010
    only, allf = None, False
    for a in sys.argv[1:]:
        if a.startswith("--shots="):
            only = [int(x) for x in a.split("=", 1)[1].split(",")]
        elif a == "--all":
            allf = True
        elif a.startswith("--thresh="):
            thresh = float(a.split("=", 1)[1])

    shots = only or (list(range(1, 127)) if allf else None)
    if not shots:
        print("!! 用 --shots=… 或 --all")
        return 1

    L = ["画面文字自动检测（启发式）—— ⚠️ **误报/漏报率高，结论不可信**",
         "仅作交叉参考；终判必须用 _scan_subtitles.py 拼图人眼读。", "",
         "%-6s %-10s %-8s %s" % ("镜", "最大覆盖", "白带数", "启发式判定")]
    flagged = []
    for n in shots:
        p = latest(n)
        if not p:
            continue
        r = detect(p)
        if not r:
            continue
        cov = max(x[1] for x in r)
        bands = max(x[2] for x in r)
        bad = cov > thresh or bands >= 2
        if bad:
            flagged.append(n)
        L.append("%-6d %-10.4f %-8d %s" % (n, cov, bands,
                                          "★ 疑似有字" if bad else ""))

    L += ["", "启发式标出的镜：%d 个" % len(flagged),
          "   %s" % (flagged[:60] if len(flagged) <= 60
                     else flagged[:60] + ["..."]),
          "", "⚠️ 实测误报 3/4、漏报 2/5（白衣服/白桌面误报；细字/半透明漏报）。",
          "   **不要据此判定成片有无字幕。**"]
    txt = "\n".join(L)
    print(txt)
    open(os.path.join(OUT, "_text_detect.txt"), "w",
         encoding="utf-8").write(txt)
    print("\n→ OUTPUT/_text_detect.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
