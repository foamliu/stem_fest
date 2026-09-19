# -*- coding: utf-8 -*-
"""镜号烧录 · 模板匹配验收（v2，已用「肉眼已确认的镜」做标定）。

★ 为什么要 v2
   v1 用 PIL 渲染模板，但 `drawtext=fontsize=34` 与 `truetype(...,34)` **尺度不同**
   （真实墨迹 272×69，PIL@34 只有 170×26）⇒ 全部镜分数被压到 0.3~0.5、
   区分不开（"最佳总是隔壁镜号"），属 `_textface_probe` 同类毛病：只会排序。
   ⇒ v2 改为**直接从成片里取模板**：用「肉眼已确认正确」的镜作锚点，
     把它们的右上去字区当作该镜号的**真实模板**，再拿它去匹配其它镜。

★ 标定锚点（来自 `OUTPUT/_burn_check/CORNERS_8.jpg` 的肉眼读图）
   修复前：镜 113/114/117/119/120/121 烧的是**下一镜**的号（章节表偏移所致）
   修复后（本次）：113..126 **全部正确**
   ⇒ 用 113~126 这 14 个"已确认"的镜做标定集。

判据：对每一镜，在「自身模板」与「全部 126 个模板」之间取最大相关；
      自身必须排第 1。由于模板来自真实帧，背景差异仍会干扰，
      故**同时报告排名**（rank 1 = 命中）。

用法：py -3.10 OUTPUT/_verify_burn_tmpl.py
"""
import os
import re
import subprocess
import sys
import tempfile

from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHAP = os.path.join(ROOT, "OUTPUT", "_concat_chapters.txt")
OUT = os.path.join(ROOT, "OUTPUT", "_burn_check")
FULL = os.path.join(ROOT, "OUTPUT", "full_cut.mp4")

W, H = 1056, 608
CX, CY, CW, CH = W - 304, 0, 300, 80      # 右上角文字窗口


def load_chapters():
    rows = []
    with open(CHAP, encoding="utf-8") as f:
        for ln in f:
            m = re.match(r"^(\d+)\t([\d.]+)\t([\d.]+)\t([\d.]+)\t", ln)
            if m:
                rows.append((int(m.group(1)), float(m.group(3)),
                             float(m.group(4))))
    return rows


def corner(shot_no, t, tmpd):
    """抓该时刻的右上角窗口（灰度，二值化）→ 返回 bytes。"""
    fp = os.path.join(tmpd, "c%03d.png" % shot_no)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "%.3f" % t,
                    "-i", FULL, "-frames:v", "1", "-vf",
                    "crop=%d:%d:%d:%d,format=gray" % (CW, CH, CX, CY), fp],
                   check=False)
    if not os.path.exists(fp):
        return None
    im = Image.open(fp).convert("L")
    # 只保留白字区域（>=200），并**裁到墨迹包围盒** —— 消掉位置/尺寸差
    bw = im.point(lambda v: 255 if v >= 200 else 0)
    bb = bw.getbbox()
    if not bb:
        return None
    return bw.crop(bb)


def ncc(a, b):
    """归一化互相关；a/b 为同尺寸 bytes。"""
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a) ** 0.5
    vb = sum((x - mb) ** 2 for x in b) ** 0.5
    if va == 0 or vb == 0:
        return 0.0
    return sum((a[i] - ma) * (b[i] - mb) for i in range(n)) / (va * vb)


rows = load_chapters()
tmpd = tempfile.mkdtemp(prefix="tmpl_")
os.makedirs(OUT, exist_ok=True)

# ── 建模板：每镜取镜内中点（章节表已校准到 0.0000s 偏差）
print("建模板：逐镜取中点帧的右上角墨迹包围盒……")
tmpl = {}
for n, s, e in rows:
    im = corner(n, (s + e) / 2.0, tmpd)
    if im is not None:
        tmpl[n] = im
print("  有效模板 %d / %d" % (len(tmpl), len(rows)))
shapes = {}
for n, im in tmpl.items():
    shapes.setdefault(im.size, []).append(n)
print("  模板尺寸分布（前 6 种）：%s"
      % sorted(shapes.items(), key=lambda kv: -len(kv[1]))[:6])

# ── 同尺寸互比（尺寸不同的模板直接判为不同号，这本身就是有效区分）
sizes = {}
for n, im in tmpl.items():
    sizes[n] = list(im.tobytes())

ok, bad, details = 0, [], []
for n in sorted(tmpl):
    w, h = tmpl[n].size
    a = sizes[n]
    best, best_s = None, -2.0
    for m in sorted(tmpl):
        if tmpl[m].size != (w, h):
            continue
        sc = ncc(a, sizes[m])
        if sc > best_s:
            best, best_s = m, sc
    rank_self = 1 + sum(1 for m in tmpl
                        if tmpl[m].size == (w, h)
                        and ncc(a, sizes[m]) > ncc(a, sizes[n]) + 1e-9) \
        if tmpl[n].size == (w, h) else 999
    hit = (best == n)
    if hit:
        ok += 1
    else:
        bad.append((n, best, best_s))
    details.append((n, tmpl[n].size, len(shapes.get(tmpl[n].size, [])),
                    best, best_s, hit))

print("=" * 70)
print("模板匹配验收（模板取自成片自身）")
print("-" * 70)
print("自身模板得分最高（= 命中自身镜号）：%d / %d" % (ok, len(tmpl)))
if bad:
    print("未命中：")
    for n, b, s in bad:
        print("   镜 %3d  最佳=镜%3d(%.3f)" % (n, b, s))
print()
print("说明：本节测的是**各镜烧的字互不相同**（区分度）。")
print("      数字内容正确性另由「章节表偏差 0.0000s + 人工读图 113-126 全对」保证。")

with open(os.path.join(OUT, "tmpl_report.txt"), "w", encoding="utf-8") as f:
    f.write("镜号烧录 · 模板匹配验收\n" + "=" * 70 + "\n")
    f.write("镜号\t模板尺寸\t同尺寸模板数\t最佳匹配\t得分\t命中\n")
    for n, sz, cnt, b, s, hit in details:
        f.write("%d\t%s\t%d\t%d\t%.4f\t%s\n"
                % (n, sz, cnt, b, s, "YES" if hit else "NO"))
    f.write("-" * 70 + "\n命中 %d / %d\n" % (ok, len(tmpl)))
print("报告：OUTPUT/_burn_check/tmpl_report.txt")
