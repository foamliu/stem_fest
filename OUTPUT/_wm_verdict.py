# -*- coding: utf-8 -*-
"""★ 从 _wm_result.tsv 里筛出**真正的水印**：利用「水印固定不动」这一时间特性。

为什么 930 条候选要再筛一次
    单帧判据（横向暗块 + nseg>=6）几乎在所有镜头都会命中：
    树叶、沙袋缝、栅栏、墙报、校徽……这些是**真纹理**。但水印有一个纹理没有的
    性质 —— **它相对画面固定不动**。所以：
        真水印  = 多帧出现在**同一个像素位置**（坐标抖动 < 12px）
        假候选  = 位置随镜头/画面运动漂移

判据
    1. 按镜分组，把候选按 (x0,y0) 贪心聚类（容差 12px）；
    2. 真候选需要 >= 4 帧落在同一簇（8 帧抽样的 50%）；
    3. 簇内 nseg 中位数 >= 6；
    4. 输出每镜最强簇，附带裁剪块路径供读图确认。

用法：
    py -3.10 OUTPUT/_wm_verdict.py           # 全部
    py -3.10 OUTPUT/_wm_verdict.py --min=4   # 调高时间稳定性要求
"""
from __future__ import annotations
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TSV = os.path.join(HERE, "_wm_result.tsv")
CROPS = os.path.join(HERE, "_wm_crops")


def load():
    rows = []
    for l in io.open(TSV, encoding="utf-8"):
        p = l.rstrip("\n").split("\t")
        if len(p) < 9 or not p[0].endswith(".mp4"):
            continue
        try:
            rows.append(dict(shot=int(p[1]), t=float(p[2]),
                             x0=int(p[3]), y0=int(p[4]),
                             x1=int(p[5]), y1=int(p[6]),
                             nseg=int(p[7]), asp=float(p[8])))
        except ValueError:
            pass
    return rows


def main():
    minf, tol = 4, 12
    for a in sys.argv[1:]:
        if a.startswith("--min="):
            minf = int(a.split("=", 1)[1])
        elif a.startswith("--tol="):
            tol = int(a.split("=", 1)[1])

    rows = load()
    by = {}
    for r in rows:
        by.setdefault(r["shot"], []).append(r)

    print("镜   稳定簇帧数  中位nseg  位置            宽高比  裁剪")
    print("-" * 78)
    hits = []
    for n in sorted(by):
        # 贪心聚类：按 (x0,y0) 就近归簇
        clusters = []
        for r in sorted(by[n], key=lambda z: z["t"]):
            for c in clusters:
                if abs(c["x0"] - r["x0"]) <= tol and abs(c["y0"] - r["y0"]) <= tol:
                    c["items"].append(r)
                    c["x0"] = sum(i["x0"] for i in c["items"]) // len(c["items"])
                    c["y0"] = sum(i["y0"] for i in c["items"]) // len(c["items"])
                    break
            else:
                clusters.append(dict(x0=r["x0"], y0=r["y0"], items=[r]))
        for c in clusters:
            it = c["items"]
            if len(it) < minf:
                continue
            med = sorted(i["nseg"] for i in it)[len(it) // 2]
            if med < 6:
                continue
            asp = sum(i["asp"] for i in it) / len(it)
            best = max(it, key=lambda i: i["nseg"])
            crop = os.path.join(CROPS, "s%03d_t%.2f.jpg" % (n, best["t"]))
            hits.append((n, len(it), med, c["x0"], c["y0"], asp, crop))
    for n, cnt, med, x0, y0, asp, crop in hits:
        print("%-4d %-10d %-9d (%-5d,%-5d) %-7.2f %s"
              % (n, cnt, med, x0, y0, asp, os.path.basename(crop) if os.path.exists(crop) else "-"))
    print("-" * 78)
    print("%d 镜有「时间稳定」候选（共 %d 镜有任意候选）" % (len(hits), len(by)))
    print("\n★ 提醒：稳定候选≠水印，必须读图确认（栅栏/招牌/静止道具同样稳定）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
