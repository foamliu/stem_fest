# -*- coding: utf-8 -*-
"""字幕泄漏**人工复核裁定表** —— 程序扫描的**唯一权威补充**。

★★★ 为什么必须有这张表（README §6.6 铁律）
    `_scan_text_rows.py` 是**筛查器不是判官**：全片扫出 7 镜"疑似"，
    但**逐帧读图复核后只有 2 镜是真的**（镜 36 的「继光哥」、镜 61 的「袁隆平爷爷」）。
    另 5 镜全是误报：白校服/白裙/白纸飞机/白球鞋 的**高光块**在掩膜下
    也呈"多个窄白块横向排列"，与字形在统计上不可分。

    ⇒ **程序只能把候选缩到个位数；"到底有没有字"必须读图确认**（§6.4/§6.6）。
      本表记录每次扫描的复核结论，作为回归基线：
      下次扫描若**新增**未登记的命中镜 ⇒ 才是新问题。

复核方法（每次都要做）：
    py -3.10 OUTPUT/_scan_text_rows.py --every=0.35     # 写 _scan_result.tsv
    py -3.10 OUTPUT/_crop_candidates.py                 # 按命中帧裁字幕带
    # 然后用 read_files 逐个看 OUTPUT/_chk7/crop*.jpg
"""
from __future__ import annotations
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# 镜 → (扫描命中帧数, 读图结论, 处置)
VERDICT = {
    1:  (9, "❌ 误报", "白裙 + 白上衣高光（画面无任何文字）"),
    36: (7, "🔴 真字幕「继光哥」", "**已修复**：换 seed 重跑 ⇒ 复扫 0/8 帧、读图无字 ✅"),
    61: (4, "🔴 真字幕「袁隆平爷爷」", "**已修复**：换 seed + 补文字守护句 ⇒ 复扫 0/8 帧、读图无字 ✅"),
    7:  (3, "❌ 误报", "白衬衫 + 手部高光"),
    54: (3, "❌ 误报", "白球鞋 + 草叶高光"),
    4:  (1, "❌ 误报", "白纸飞机高光"),
    48: (1, "❌ 误报", "白校服 + 红领巾高光"),
}
REAL = [n for n, v in VERDICT.items() if "真字幕" in v[1]]
FIXED = [n for n, v in VERDICT.items() if "已修复" in v[2]]


def main():
    lines = ["字幕泄漏复核裁定（扫描 7 镜 → 真 2 镜）", "=" * 88]
    for n, (frames, verdict, act) in sorted(VERDICT.items()):
        lines.append("  镜 %-4d 命中 %2d 帧  %-22s %s" % (n, frames, verdict, act))
    lines.append("-" * 88)
    lines.append("  ★ 曾真泄漏镜：%s  ⇒  %s  ※ 已全部修复" % (REAL, FIXED))
    lines.append("  ★ 复核方法：_crop_candidates.py 裁带 → read_files 读图（不可只看扫描计数）")
    txt = "\n".join(lines)
    print(txt)
    io.open(os.path.join(HERE, "_textrows_verdict.txt"), "w", encoding="utf-8").write(txt + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
