# -*- coding: utf-8 -*-
"""核对「泄漏字幕」与 prompt 文字的来源 —— 是画面段、加粗强调，还是 Audio 段？

★ 为什么要做这个（2026-09-15）
    9 个泄漏镜里，镜 7 泄漏了「抬不也不抬」，而 prompt 画面段有加粗 `**头也不抬**`
    —— 高度疑似「加粗强调被画成字幕」。
    但镜 14/85/86/88/112 的泄漏文字与 Camera段/Audio段的哪一段对应，必须逐条核。
    只靠肉眼对不上，会把"猜的规律"写进 README（本轮已经犯过一次）。

本脚本输出（每镜一段）
    L(lak)   = 实测泄漏文字（人工从拼图读出，写死在下面 LEAK 表）
    CUT      = 画面描述段（`Audio:` 之前）的全部**中文片段**
    BOLD     = 画面段里的 `**…**` 加粗片段
    AUDIO    = `Audio:` 段之后的全部中文片段
    ⇒ 人眼/程序都能看出泄漏文字来自哪一段。

用法
    py -3.10 OUTPUT/_trace_leak.py
"""
import difflib
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")

# 实测泄漏文字（从 `_subscan` 拼图读出；`-` 表示读不出/无）
LEAK = {
    7: "抬不也不抬",
    14: "我上次竞选科技之星",
    21: "这野菜能吃吗",
    36: "你听见没",
    77: "他在高铁上……看文件",
    85: "吃了",
    86: "钟爷爷 您去武汉做什么",
    88: "很严重吗",
    112: "他问我们……咱们国家现在啥样了",
}


def seg_of(n):
    for f in glob.glob(os.path.join(OUT, "_diag_act*.py")):
        src = open(f, encoding="utf-8").read()
        marks = list(re.finditer(r"TASKS\[(\d+)\]", src))
        for i, m in enumerate(marks):
            if int(m.group(1)) != n:
                continue
            end = marks[i + 1].start() if i + 1 < len(marks) else len(src)
            return os.path.basename(f), src[m.end():end]
    return None, None


def zh_runs(s):
    """抽所有长度 >= 3 的中文片段（便于比对）。"""
    return [x for x in re.findall(r"[\u4e00-\u9fff\u2026，。、！？\u201c\u201d]{3,}", s)]


def main():
    L = ["# 泄漏字幕溯源", "",
         "匹配度 = 泄漏文字与该片段的最长公共子串占比（>=0.5 视为同源）", ""]
    for n, leak in sorted(LEAK.items()):
        f, seg = seg_of(n)
        if seg is None:
            L.append("镜 %d：找不到 prompt 段" % n)
            continue
        a = re.search(r"Audio\s*[:：]", seg)
        cut = seg[:a.start()] if a else seg
        aud = seg[a.start():] if a else ""

        bolds = re.findall(r"\*\*([^*]{2,30})\*\*", seg)
        cands = [("BOLD", x) for x in bolds]
        cands += [("CUT", x) for x in zh_runs(cut)]
        cands += [("AUDIO", x) for x in zh_runs(aud)]

        rows = []
        for tag, txt in cands:
            m = difflib.SequenceMatcher(None, leak, txt).find_longest_match(
                0, len(leak), 0, len(txt))
            ratio = m.size / max(1, len(leak))
            rows.append((ratio, tag, txt))
        rows.sort(reverse=True)
        L.append("## 镜 %d　`%s`" % (n, f))
        L.append("")
        L.append("**泄漏文字**：`%s`" % leak)
        L.append("")
        L.append("| 匹配度 | 来源段 | 候选文字 |")
        L.append("|:--:|---|---|")
        for r, tag, txt in rows[:5]:
            L.append("| %.2f | %s | %s |" % (r, tag, txt[:60]))
        L.append("")
        if rows and rows[0][0] >= 0.5:
            L.append("⇒ **同源段：%s**" % rows[0][1])
        else:
            L.append("⇒ **未找到同源段**（可能是模型自由发挥的幻觉文字）")
        L.append("")

    txt = "\n".join(L)
    print(txt)
    open(os.path.join(OUT, "_leak_trace.md"), "w", encoding="utf-8").write(txt)
    print("→ OUTPUT/_leak_trace.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
