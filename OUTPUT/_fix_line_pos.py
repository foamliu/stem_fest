# -*- coding: utf-8 -*-
"""台词「字幕泄漏」排查与改写 —— 基于 2026-09-15 实测溯源结论。

★ 实测结论（见 `_trace_leak.py` → `_leak_trace.md`）
    规则：**`Audio:` 段里的台词原文，H3 会"念"，但也有约 12% 概率"显示"成字幕**。
      实测 8/9 镜的泄漏文字与 `Audio:` 段**逐字相同**（匹配度 1.00）：
        镜 14「我上次竞选科技之星」、镜 21「这野菜能吃吗」、镜 36「你听见没」、
        镜 77「他在高铁上……看文件」、镜 85「吃了」、镜 88「很严重吗」…
      唯一例外：镜 7「抬不也不抬」来自**画面段的加粗 `**头也不抬**`**
      ⇒ **画面段的中文（尤其 `**加粗**`）也可能被画成字幕**，不止 Audio 段。
    风险面：`Audio:` 含台词原文的镜 ≈ 78/126（62%），实际泄漏 9 镜（≈12%）。

本脚本做什么
    ① 扫描 `Audio:` 段里「说/问/喊：<引号台词>」写法，列出**有泄漏风险的镜**。
    ② 给出**改写建议**：把引号台词改成不带引号的间接描述
       （H3 仍能据此生成语音与口型，但没有"可复制的文本"可显示）。
    ③ 默认**只报告**；`--apply` 才写回（先备份 `.bak`）。

用法
    py -3.10 OUTPUT/_fix_line_pos.py                    # 报告风险镜（默认）
    py -3.10 OUTPUT/_fix_line_pos.py --apply            # 改写已确认泄漏的 9 镜（写 .bak）
"""
import glob
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")

# 已由 `_scan_subtitles.py` + 人眼确认**实际泄漏**的镜
CONFIRMED_LEAK = (7, 14, 21, 36, 77, 85, 86, 88, 112)

RE_AUDIO = re.compile(r"Audio\s*[:：]")
# 说话前缀 + 引号台词
RE_QUOTED_LINE = re.compile(
    r"([\u4e00-\u9fff]{0,20}(?:说|问|喊|道|念|答|应|讲|嘟囔|开口)[\u4e00-\u9fff]{0,12})"
    r"[:：]\s*[\u201c\u300c]?"
    r"([\u4e00-\u9fff\u2026\uff01\uff1f\uff0c\u3002！？，。、\s\u201d\u300d]{3,90})")


def scan(path):
    """返回 [(镜号, 说话前缀, 台词正文)]（只扫 Audio 段）。"""
    src = open(path, encoding="utf-8").read()
    marks = list(re.finditer(r"TASKS\[(\d+)\]", src))
    hits = []
    for i, m in enumerate(marks):
        n = int(m.group(1))
        end = marks[i + 1].start() if i + 1 < len(marks) else len(src)
        seg = src[m.end():end]
        a = RE_AUDIO.search(seg)
        if not a:
            continue
        for mm in RE_QUOTED_LINE.finditer(seg[a.start():]):
            pre, line = mm.group(1).strip(), mm.group(2).strip()
            if len(line) >= 3:
                hits.append((n, pre, line))
    return hits


def main():
    apply_fix = "--apply" in sys.argv
    total, plans = 0, []
    for f in sorted(glob.glob(os.path.join(OUT, "_diag_act*.py"))):
        hits = scan(f)
        if not hits:
            continue
        print("\n%s  —— %d 处「Audio 段含引号台词」（有泄漏风险）"
              % (os.path.basename(f), len(hits)))
        for n, pre, line in hits:
            total += 1
            plans.append((f, n, pre, line))
            flag = "  ← 已确认泄漏" if n in CONFIRMED_LEAK else ""
            print("   镜 %-4d %s：%s%s" % (n, pre, line[:52], flag))
    print("\n合计 %d 处（占全片 126 镜的 %.0f%%）" % (total, total / 126 * 100))
    print("实测泄漏 ≈12% ⇒ **不必全改**；优先改这 %d 镜：%s"
          % (len(CONFIRMED_LEAK), list(CONFIRMED_LEAK)))

    if not apply_fix:
        print("\n（加 --apply 才真正改写；会先写 .bak 备份）")
        return 0

    touched = set()
    for f, n, pre, line in plans:
        if n not in CONFIRMED_LEAK:
            continue
        bak = f + ".bak"
        if f not in touched and not os.path.exists(bak):
            shutil.copy2(f, bak)
            print("   备份 → %s" % os.path.basename(bak))
        touched.add(f)
        src = open(f, encoding="utf-8").read()
        new = src
        for colon in ("：", ":"):
            new = new.replace(pre + colon + line,
                              pre.rstrip("：:") + "（台词内容见后期处理）")
        if new != src:
            open(f, "w", encoding="utf-8").write(new)
            print("   已改写镜 %d（%s）" % (n, os.path.basename(f)))
    if touched:
        print("\n⚠️ 改写后语音/口型会变，**必须重跑这些镜并复核**：")
        print("   py -3.10 OUTPUT/_run_rerun.py --only=P2 --steps=10")
    return 0


if __name__ == "__main__":
    sys.exit(main())
