# -*- coding: utf-8 -*-
"""★ 逐镜总账：把「镜号 / 成片时间 / 台词原文 / ASR回读 / 字幕泄漏候选 / 裁定」对齐成一行。

为什么要它
    逐镜详读时最耗神的是**在 4 份数据之间来回找**（章节表、ASR 审计、扫描 TSV、
    人工裁定）。本工具把它们拼成一张宽表，按镜号排序，每行自带
    "该看什么 / 看到了什么 / 差在哪"。

数据源：
    OUTPUT/_concat_chapters.txt  成片对轴（镜 -> 起止秒 + 文件名）
    OUTPUT/_asr_audit.txt        ASR 逐镜回读（_audit_asr.py 产出）
    OUTPUT/_scan_result.tsv      字幕泄漏逐帧扫描（_scan_text_rows.py 产出，按**文件名**）
    OUTPUT/_asr_verdict.txt      人工终态裁定（P2 / OK）

用法：
    py -3.10 OUTPUT/_ledger.py                  # 全片
    py -3.10 OUTPUT/_ledger.py --from=30 --to=70
    py -3.10 OUTPUT/_ledger.py --x              # 只列需人工看的（非 match / 有扫描候选）
    py -3.10 OUTPUT/_ledger.py --shots=7,89,105
    py -3.10 OUTPUT/_ledger.py --x --v          # 附带原文与裁定理由
"""
from __future__ import annotations
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CHAP = os.path.join(HERE, "_concat_chapters.txt")
ASR = os.path.join(HERE, "_asr_audit.txt")
SCAN = os.path.join(HERE, "_scan_result.tsv")
VERD = os.path.join(HERE, "_asr_verdict.txt")

OK_TAGS = ("match", "OK", "silent")
# nseg = 连通块个数。字形由很多小岛组成（笔画/字缝），脸/衣服是"一片大陆"。
# 经验阈值 18：低于它的候选经读图复核全是误报（参见 README §6.10.10）。
SEG_MIN = 18


def chapters():
    out = {}
    for l in io.open(CHAP, encoding="utf-8"):
        p = l.split()
        if len(p) >= 5 and p[0].isdigit():
            out[int(p[0])] = (float(p[2]), float(p[3]), p[4])
    return out


def asr_rows():
    """行形如 '1     match    <原文>    <实得>'"""
    out = {}
    for l in io.open(ASR, encoding="utf-8").read().split("\n")[2:]:
        if not l.strip() or l.startswith("统计"):
            continue
        m = re.match(r"^(\d+)\s+(\S+)\s+(.*)$", l)
        if m:
            out[int(m.group(1))] = (m.group(2), m.group(3).rstrip())
    return out


def scan_rows():
    """逐帧表 -> {文件名: [(t, span, nseg)]}"""
    out = {}
    for l in io.open(SCAN, encoding="utf-8", errors="replace"):
        p = l.rstrip("\n").split("\t")
        if len(p) < 8 or not p[1].replace(".", "").isdigit():
            continue
        try:
            out.setdefault(p[0], []).append((float(p[3]), float(p[5]), int(p[7])))
        except ValueError:
            pass
    return out


def verdicts():
    out, cur = {}, None
    if not os.path.exists(VERD):
        return out
    for l in io.open(VERD, encoding="utf-8"):
        m = re.search(r"镜\s*(\d+)", l)
        if m:
            cur = int(m.group(1))
            tag = re.search(r"\[([^\]]+)\]", l)
            out[cur] = [tag.group(1) if tag else "?", l.strip()]
        elif cur and l.strip().startswith("处置") and cur in out:
            out[cur].append(l.strip())
    return out


def main():
    lo, hi, only_x, only_shots, show_v = 1, 126, False, None, False
    for a in sys.argv[1:]:
        if a.startswith("--from="):
            lo = int(a.split("=", 1)[1])
        elif a.startswith("--to="):
            hi = int(a.split("=", 1)[1])
        elif a in ("--x", "--fails"):
            only_x = True
        elif a.startswith("--shots="):
            only_shots = [int(x) for x in a.split("=", 1)[1].split(",")]
        elif a in ("--v", "--verdict"):
            show_v = True
    shots = only_shots or list(range(lo, hi + 1))

    ch, ar, sc, vd = chapters(), asr_rows(), scan_rows(), verdicts()
    f2s = {v[2]: n for n, v in ch.items()}

    scan_by_shot = {}
    for f, rows in sc.items():
        n = f2s.get(f)
        if n is None:
            continue
        big = [r for r in rows if r[2] >= SEG_MIN]
        if big:
            scan_by_shot[n] = big

    print("镜   成片(s)          台词  ASR      扫描候选        裁定")
    print("-" * 82)
    shown = 0
    for n in shots:
        c = ch.get(n)
        tspan = "%6.2f-%6.2f" % (c[0], c[1]) if c else "     ?-     ?"
        a = ar.get(n)
        tag = a[0] if a else "-"
        s = scan_by_shot.get(n)
        sx = ("候选%d帧 nseg<=%d" % (len(s), max(r[2] for r in s))) if s else "清"
        v = vd.get(n)
        vx = v[0] if v else ""
        if only_x and tag in OK_TAGS and not s:
            continue
        print("%-4d%s  %-4s  %-8s %-15s %s%s"
              % (n, tspan, "Y" if a else "-", tag, sx, vx, "  <<<" if vx == "P2" else ""))
        if show_v and a:
            print("      原文: %s" % a[1][:100])
        if show_v and v:
            for e in v[1:]:
                print("      %s" % e[:100])
        shown += 1
    print("-" * 82)
    print("共 %d 镜（列出 %d）" % (len(shots), shown))
    return 0


if __name__ == "__main__":
    sys.exit(main())
