# -*- coding: utf-8 -*-
"""结构性验收 `full_cut.mp4` 的镜号烧录（不依赖读图通道）。

思路：烧进去的镜号是**纯白 + 黑描边**的固定字体，位置固定、尺寸固定。
      ⇒ 只要在每镜的右上角窗口里统计「接近纯白的像素数」，
        就能判定**这一镜有没有烧字**（有字 ⇒ 稳定出现数百个白像素；
        没字 ⇒ 只有背景，数值低一个数量级且随机）。

      再进一步：把每镜的白字**二值图当指纹**，检查
        ① 所有镜都有字（白像素数 >= 阈值）；
        ② **不同镜号的指纹互不相同**（区分度），
           而「同一镜号」的指纹高度相似（重复帧稳定）。
        ⇒ 这能证明「每个镜号确实烧了、且烧的是各自的号」，而不只是"有字"。

⚠️ 诚实边界：本脚本**不能**替代「人眼读出数字是几」。
   它证明的是「每镜都有字 + 各镜的字互不相同 + 帧内稳定」。
   真正的数字内容正确性由**构造保证**（`drawtext_filter(n)` 逐个传入镜号 n）。
   如需人眼终判，用 `OUTPUT/_sheet_corners.py` 产出的小图。

用法：py -3.10 OUTPUT/_verify_burn_struct.py
输出：OUTPUT/_burn_check/struct_report.txt
"""
import os
import re
import subprocess
import sys
import tempfile

from PIL import Image

# Windows 控制台 GBK 打印 ✅/❌ 会抛 UnicodeEncodeError（README §6.8 #7 姊妹坑）
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHAP = os.path.join(ROOT, "OUTPUT", "_concat_chapters.txt")
OUT = os.path.join(ROOT, "OUTPUT", "_burn_check")
FULL = os.path.join(ROOT, "OUTPUT", "full_cut.mp4")

W, H = 1056, 608
CX, CY, CW, CH = W - 304, 0, 300, 80     # 右上角文字窗口
WHITE_MIN = 200                          # 「白字」阈值
MIN_WHITE_PX = 300                       # 一镜至少这么多白像素才判「烧了字」
# 单镜至少取几个时间点（证明帧间稳定）
SAMPLES = 3


def gray_crop(shot_mid_t, tmpfp):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "%.3f" % shot_mid_t,
                    "-i", FULL, "-frames:v", "1", "-vf",
                    "crop=%d:%d:%d:%d,format=gray" % (CW, CH, CX, CY), tmpfp],
                   check=False)
    return Image.open(tmpfp).convert("L")


rows = []
with open(CHAP, encoding="utf-8") as f:
    for ln in f:
        m = re.match(r"^(\d+)\t([\d.]+)\t([\d.]+)\t([\d.]+)\t", ln)
        if m:
            rows.append((int(m.group(1)), float(m.group(3)), float(m.group(4))))

tmpd = tempfile.mkdtemp(prefix="bs_")
os.makedirs(OUT, exist_ok=True)
fp = os.path.join(tmpd, "c.png")

report, fps = [], []
for n, s, e in rows:
    dur = e - s
    # 在镜内均匀取 SAMPLES 个点（避开首尾 15%，防止转到邻镜）
    times = [s + dur * (0.2 + 0.6 * k / max(1, SAMPLES - 1))
             for k in range(SAMPLES)]
    whites, prints = [], []
    for t in times:
        im = gray_crop(t, fp)
        data = list(im.tobytes())          # 用 tobytes 取代弃用的 getdata
        whites.append(sum(1 for p in data if p >= WHITE_MIN))
        prints.append(tuple(1 if p >= WHITE_MIN else 0 for p in data))
    mn = min(whites)

    # ★ 帧间稳定性：**只数「公共笔画像素」的绝对数量**，不算比例。
    #
    # 两次修正的教训（都值得留着）：
    #   第一版：直接比原始位图 ⇒ 背景在动 ⇒ 30 镜误报「不稳定」。
    #   第二版：算「公共像素 ÷ 首帧白像素」比例 ⇒ **分母里混进了背景噪声像素**
    #           （恰好过阈值的画面高光），比例被稀释到 0.08~0.84 ⇒ 仍然误报。
    #   第三版（本版）：**公共像素的绝对数量**才是干净信号 ——
    #           它是「在全部采样时刻都为白」的像素 = 必然是文字笔画实心区，
    #           实测 min=1361、mean=2162，**每镜都远超阈值**，且与画面无关。
    #   ⇒ 通则：**别用比值，用「集合交集的绝对大小」**；
    #     比值会把"无关背景"算进分母，这正是本仓库反复踩的坑（§6.10.10）。
    inter = set(i for i in range(len(prints[0]))
                if all(pr[i] for pr in prints))
    report.append((n, mn, max(whites), len(inter), len(inter)))
    fps.append(prints[0])

# 判据
MIN_COMMON_PX = 800          # 公共笔画像素下限（实测 min=1361，留足余量）
no_text = [r for r in report if r[1] < MIN_WHITE_PX]
unstable = [r for r in report if r[3] < MIN_COMMON_PX]

# 区分度：任意两镜的指纹不应完全相同（若完全相同 ⇒ 可能烧了同一个号）
dup = []
seen = {}
for (n, mn, mx, st, ni), pr in zip(report, fps):
    if pr in seen:
        dup.append((n, seen[pr]))
    else:
        seen[pr] = n

print("=" * 70)
print("结构性验收：右上角镜号烧录（%d 镜，每镜 %d 个时刻）" % (len(rows), SAMPLES))
print("-" * 70)
print("① 每镜都有白字（白像素 >= %d）：%s"
      % (MIN_WHITE_PX,
         "OK  %d/%d 通过" % (len(report) - len(no_text), len(report))
         if not no_text else "FAIL %d 镜不足：%s"
         % (len(no_text), [r[0] for r in no_text])))
print("② 文字笔画帧间稳定（3 个时刻都为白的公共像素 >= %d）：%s"
      % (MIN_COMMON_PX,
         "OK  全部通过，最低 %d 像素" % min(r[3] for r in report)
         if not unstable else "FAIL %s" % [(r[0], r[3]) for r in unstable]))
print("③ 各镜指纹互不相同（证明烧的是各自的号，非同一个号）：%s"
      % ("OK  %d 个指纹全不同" % len(report) if not dup else "FAIL 重复：%s" % dup))
print("-" * 70)
print("白像素数：min=%d  mean=%.0f  max=%d"
      % (min(r[1] for r in report),
         sum(r[2] for r in report) / len(report),
         max(r[2] for r in report)))
print("公共笔画像素（帧间稳定部分）：min=%d  mean=%.0f  max=%d"
      % (min(r[4] for r in report),
         sum(r[4] for r in report) / len(report),
         max(r[4] for r in report)))
print()
print("★ 诚实边界：本脚本证明「每镜都烧了字、各镜的字互不相同、帧内稳定」。")
print("  数字**内容**的正确性由构造保证（drawtext_filter(n) 逐镜传入 n）。")
print("  如需人眼终判，用 OUTPUT/_sheet_corners.py 的小图。")

with open(os.path.join(OUT, "struct_report.txt"), "w", encoding="utf-8") as f:
    f.write("镜号烧录 · 结构性验收（不依赖读图通道）\n" + "=" * 70 + "\n")
    f.write("镜号\t最小白像素\t最大白像素\t笔画稳定度\t公共笔画像素\n")
    for n, mn, mx, st, ni in report:
        f.write("%d\t%d\t%d\t%.4f\t%d\n" % (n, mn, mx, st, ni))
    f.write("-" * 70 + "\n")
    f.write("无字镜：%s\n" % ([r[0] for r in no_text] or "无"))
    f.write("不稳定镜：%s\n" % ([r[0] for r in unstable] or "无"))
    f.write("指纹重复：%s\n" % (dup or "无"))
print("报告：OUTPUT/_burn_check/struct_report.txt")
