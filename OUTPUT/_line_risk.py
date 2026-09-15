# -*- coding: utf-8 -*-
"""统计「Audio 段里带具体台词原文」的镜 —— 定位「台词被渲染成字幕」的风险面。

★ 为什么要统计这个（2026-09-15）
    实锤规律：**Audio 段里写了「说：<具体台词>」的镜，H3 有概率把台词显示成字幕**
    （镜 14 底部出现「我上次竞选科技之星」「就输在少说了两句」）；
    而只写「轻声说了一句」（不给原文）的镜（如镜 15）**没有字幕**。
    ⇒ 与 §6.4 的"元信息污染"是**同一机制的不同表现**：
      H3 分不清 prompt 里"要它表演的文本"与"要它显示的文本"，**写什么就可能显示什么**。

输出
    `OUTPUT/_line_risk.txt`：逐镜列出「Audio 段含台词原文」的镜号 + 该句摘录
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")

# Audio 段后面紧跟「中文/引号」= 疑似台词原文
RE_TASK = re.compile(r"TASKS\[(\d+)\]")
RE_AUDIO_TALK = re.compile(
    r"(?:说|念|问|答|喊|道|讲)\s*[:：]\s*([\u4e00-\u9fff\u201c\u300c][^\n\"'）)]{2,60})")


def main():
    rows = []
    for f in sorted(glob.glob(os.path.join(OUT, "_diag_act*.py"))):
        src = open(f, encoding="utf-8").read()
        marks = list(RE_TASK.finditer(src))
        for i, m in enumerate(marks):
            n = int(m.group(1))
            end = marks[i + 1].start() if i + 1 < len(marks) else len(src)
            seg = src[m.end():end]
            hits = RE_AUDIO_TALK.findall(seg)
            if hits:
                rows.append((n, os.path.basename(f), hits[0][:40]))
    rows.sort()
    L = ["「Audio 段含台词原文」的镜（H3 有把它当字幕渲染的风险）",
         "=" * 72,
         "合计 %d 镜" % len(rows), "",
         "%-6s %-26s %s" % ("镜号", "幕脚本", "台词摘录")]
    for n, f, t in rows:
        L.append("%-6d %-26s %s" % (n, f, t))
    L.append("")
    L.append("⇒ 对策见 README §6.4：台词是必需信息（H3 要念），无法删除；")
    L.append("  若成片确认画面出现该行字，改用 `OUTPUT/_burn_cards.py` 思路做**后期处理**，")
    L.append("  或把 Audio 里的原文改写成\"（内容见后期字幕）\"让 H3 不显示。")
    txt = "\n".join(L)
    print(txt)
    open(os.path.join(OUT, "_line_risk.txt"), "w", encoding="utf-8").write(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
