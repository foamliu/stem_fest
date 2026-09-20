# -*- coding: utf-8 -*-
"""50 式冬装参考图**清洗**（2026-09-20）。

实测两个坑（`ref2/` 里的原始下载图）：
  ① 军品店实拍图压着**红色电话号码水印**（`18645189606`）与橙色时间戳；
  ② 复刻套装图（`uniform_set_repro`）带**红五角星帽徽** —— 正是甲方要去掉的
     东西，进了拼版等于教模型"照着画"。
本脚本按像素直接裁掉这两类污染，并把每张参考量化体检（复用
`_audit_uniform_redo.py` 的红判据），只把干净产物写进 `ref2/clean/`。

裁剪参数是**按图逐个标定**的（图高比例），不做自动检测 —— 免得裁掉帽子本体。
用法：
    py -3.10 OUTPUT/_clean_ref50.py
"""
import json
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "OUTPUT", "uniform_50shi", "ref2")
DST = os.path.join(SRC, "clean")

# 文件名 -> (左, 上, 右, 下) 图高/图宽比例；None 表示不裁
#   · cap_side：裁掉中下部"红色电话水印 + 橙色时间戳"带，只留帽顶 0~58%
#   · uniform_full：裁掉中部"红色电话水印"带（左 0~100%, 上 46%~70%）
#   · wearer/uniform_set：保留（无红色标识），但整套底部带水印的弃用
CROP = {
    "cap_side_laojunpin.jpg":      (0.00, 0.02, 1.00, 0.58),
    "cap_side_laojunpin2.jpg":     (0.00, 0.02, 1.00, 0.58),
    "uniform_full_laojunpin.jpg":  (0.00, 0.00, 1.00, 0.46),
    "uniform_full_laojunpin2.jpg": (0.00, 0.00, 1.00, 0.46),
    "cap_front_laojunpin.jpg":     (0.00, 0.02, 1.00, 0.58),
    "cap_front_997788.jpg":        (0.00, 0.02, 1.00, 0.62),
    "wearer_qq.jpg":               (0.06, 0.00, 1.00, 0.96),
}

# 这些图**不进拼版**：带红五角星/红水印，只登记不清理
BLACKLIST = {
    "uniform_set_repro.jpg": "带红五角星帽徽（甲方要去除的标识），不得进参考拼版",
    "uniform_set_laojunpin.jpg": "腰部有红色水印带，帽/衣细节被切断",
}

RED_HUE_LO, RED_HUE_HI, RED_SAT_MIN, RED_VAL_MIN = 20, 340, 0.45, 40


def red_ratio(im):
    """整图高饱和红像素占比（%）。"""
    hsv = np.asarray(im.convert("HSV")).astype(np.float32)
    h, s, v = hsv[..., 0] * 360 / 255, hsv[..., 1] / 255, hsv[..., 2] / 255
    m = ((h < RED_HUE_LO) | (h > RED_HUE_HI)) & (s > RED_SAT_MIN) & (v * 255 > RED_VAL_MIN)
    return 100.0 * m.sum() / m.size


def main():
    os.makedirs(DST, exist_ok=True)
    report = []
    for name in sorted(os.listdir(SRC)):
        p = os.path.join(SRC, name)
        if not os.path.isfile(p) or not name.lower().endswith((".jpg", ".png")):
            continue
        im = Image.open(p).convert("RGB")
        W, H = im.size
        note = BLACKLIST.get(name, "")
        box = CROP.get(name)
        if box:
            l, t, r, b = box
            im = im.crop((int(W * l), int(H * t), int(W * r), int(H * b)))
            note = (note + " " if note else "") + "裁 %d%%~%d%%H" % (t * 100, b * 100)
        out = os.path.join(DST, name)
        im.save(out, quality=95)
        rr = red_ratio(im)
        report.append({"file": name, "size": "%dx%d" % im.size,
                       "red_pct": round(rr, 4),
                       "blacklist": name in BLACKLIST, "note": note.strip()})
        print("%-30s %-11s 红 %.4f%%  %s%s"
              % (name, "%dx%d" % im.size, rr,
                 "[黑名单] " if name in BLACKLIST else "", note.strip()))

    with open(os.path.join(DST, "_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print("\n清洗结果 -> %s" % DST)
    return 0


if __name__ == "__main__":
    sys.exit(main())
