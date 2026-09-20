# -*- coding: utf-8 -*-
"""战壕（及任意场景图）区域色彩量化 —— ★ 常驻工具：`场景图 v01~vN 谁更「秋/亮/暖」`。

★ 由来（2026-09-20，README §6.10.16）：
   `_diag_grade_trench_autumn.py` 的 `stats()` 是**全图均值**，
   **天空占了画面上部很大面积** ⇒ 全图 R-B 被天空拉高，**看不出地面是否真的变亮**。
   v03 就吃过这个亏：全图数值达标（R-B 26.8），但**画面下半部亮度只有 66「发闷」**，
   与「白天有太阳、斜射硬光」的文字对不上 —— 靠本脚本的**分区域量化**才发现。

## 判据（口语 → 数值）
   · 地面 R-B 升高               → 暖（秋色）
   · 地面亮度升高               → 有太阳（不是阴天漫射）
   · 天空 R-B ≥ 0               → 暖灰天空（不是冷蓝灰）

## 用法
   py -3.10 OUTPUT/_check_trench_regions.py                     # 默认战壕 v01~v04
   py -3.10 OUTPUT/_check_trench_regions.py --dir=SCENES/07_rice_field
   py -3.10 OUTPUT/_check_trench_regions.py --sky=0.02,0.16,0.45,0.95 --gnd=0.55,1.0
       --sky / --gnd 可自定义取样矩形（行起,行止,列起,列止，均为 0~1 比例）。

★ 通用纪律：**全图均值会骗人**。画面里若有「大面积高亮区」（天空 / 白墙 / 屏幕），
   它的色偏会把整图统计拉走 ⇒ 判定「主体是否达标」必须**按区域分别量化**。
"""
import argparse
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
from PIL import Image

ROOT = r"E:\code\stem_fest"
DEFAULT_DIR = os.path.join(ROOT, "ASSETS", "SCENES", "06_trench")
DEFAULT_NAMES = ["trench_wide_v01.png", "trench_wide_v02.png",
                 "trench_wide_v03.png", "trench_wide_v04.png"]


def region(a, r0, r1, c0, c1):
    """按比例取矩形区域，返回 (N,3) 的 0..1 数组。"""
    h, w, _ = a.shape
    return a[int(r0 * h):int(r1 * h), int(c0 * w):int(c1 * w)].reshape(-1, 3)


def parse_rect(s, default):
    if not s:
        return default
    try:
        v = tuple(float(x) for x in s.split(","))
        return v if len(v) == 4 else default
    except ValueError:
        return default


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--dir", default=None, help="场景目录（相对项目根或绝对路径）")
    ap.add_argument("--sky", default=None, help="天空取样 行起,行止,列起,列止（0~1）")
    ap.add_argument("--gnd", default=None, help="地面取样 行起,行止,列起,列止（0~1）")
    args, _ = ap.parse_known_args()

    d = args.dir or DEFAULT_DIR
    if not os.path.isabs(d):
        d = os.path.join(ROOT, d)
    sky_r = parse_rect(args.sky, (0.02, 0.16, 0.45, 0.95))
    gnd_r = parse_rect(args.gnd, (0.55, 1.00, 0.00, 1.00))

    names = DEFAULT_NAMES if d == DEFAULT_DIR else sorted(
        f for f in os.listdir(d) if f.lower().endswith((".png", ".jpg", ".jpeg"))
        and "_v" in f)

    print("目录：%s" % d)
    print("取样：SKY 行 %.2f~%.2f / 列 %.2f~%.2f ｜ GND 行 %.2f~%.2f / 列 %.2f~%.2f"
          % (sky_r + gnd_r))
    print("\n%-24s %-16s %-16s %-8s %-8s %-9s"
          % ("file", "sky RGB", "gnd RGB", "skyLum", "gndLum", "gndR-B"))
    rows = []
    for n in names:
        p = os.path.join(d, n)
        if not os.path.exists(p):
            print("%-24s MISSING" % n)
            continue
        a = np.asarray(Image.open(p).convert("RGB"), dtype=np.float32) / 255.0
        sky = region(a, *sky_r)
        gnd = region(a, *gnd_r)
        sm, gm = sky.mean(0) * 255, gnd.mean(0) * 255
        rows.append((n, sm, gm))
        print("%-24s %-16s %-16s %-8.1f %-8.1f %-9.1f"
              % (n, "%.0f/%.0f/%.0f" % tuple(sm), "%.0f/%.0f/%.0f" % tuple(gm),
                 sm.mean(), gm.mean(), gm[0] - gm[2]))

    if len(rows) >= 2:
        f, l = rows[0], rows[-1]
        print("\n%s → %s：" % (f[0], l[0]))
        print("  地面亮度 %.1f → %.1f（%+.1f）" % (f[2].mean(), l[2].mean(),
                                              l[2].mean() - f[2].mean()))
        print("  地面 R-B %.1f → %.1f（%+.1f）"
              % (f[2][0] - f[2][2], l[2][0] - l[2][2],
                 (l[2][0] - l[2][2]) - (f[2][0] - f[2][2])))
        print("  天空 R-B %.1f → %.1f" % (f[1][0] - f[1][2], l[1][0] - l[1][2]))
        ok = (l[2].mean() > f[2].mean()) and \
             ((l[2][0] - l[2][2]) > (f[2][0] - f[2][2])) and (l[1][0] - l[1][2]) >= 0
        print("\n闸门（更亮 + 更暖 + 天空非冷蓝）：%s" % ("PASS" if ok else "FAIL"))


if __name__ == "__main__":
    main()
