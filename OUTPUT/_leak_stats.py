# -*- coding: utf-8 -*-
"""泄漏镜 vs 干净镜：Audio 段写法的统计学对照。

背景（README §6.6）：`Audio:` 段的**台词原文**约 11% 概率被 H3 当字幕画出来。
本脚本用来验证一个具体假设 —— 「泄漏是否与 Audio 段的写法有关」：

  H1  写了台词原文（`他说：xxx`）      ⇒ 更易泄漏
  H2  台词被**直接引号**包裹（`"xxx"`）⇒ 更易泄漏（镜 112 带引号被画出来）
  H3  只写环境音（无台词）             ⇒ 不易泄漏

用法：
    py -3.10 OUTPUT/_leak_stats.py
无需 ComfyUI，纯静态解析 6 个幕脚本。
"""
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = {
    "0": "_diag_act0_plane.py",
    "1": "_diag_act1_trench.py",
    "2": "_diag_act2_startup.py",
    "3": "_diag_act3_rice.py",
    "4": "_diag_act4_train.py",
    "5": "_diag_act5_finale.py",
}
LEAK = [7, 14, 21, 36, 77, 85, 86, 88, 112]

# 台词动词（中英冒号都算）
VERB = re.compile(r"(说|问|喊|答|念|道|回嘴|惊呼|脱口)")
# 直接引号（中文弯引号 / 日式引号）
QUOTE = re.compile(r"[\u201C\u201D\u2018\u2019\u300C\u300D]")
# 英文直引号对（在 prompt 字符串里被转义成 \" 的）
ESC_QUOTE = re.compile(r'\\"')


def parse(path):
    """切出每个 TASKS[n] 块，返回 {n: 该块内所有字符串字面量拼接}。"""
    src = open(path, encoding="utf-8").read()
    out = {}
    parts = re.split(r"TASKS\[(\d+)\]\s*=\s*dict\(", src)
    for i in range(1, len(parts), 2):
        n = int(parts[i])
        body = parts[i + 1]
        # 块结束：下一个 TASKS[ 或文件尾
        nxt = re.search(r"\nTASKS\[", body)
        if nxt:
            body = body[: nxt.start()]
        lits = re.findall(r'"([^"\n]*)"', body)
        out[n] = "".join(lits)
    return out


def analyze(text):
    """返回 (audio 段文本, 有台词动词, 有引号, 角色数)。"""
    m = re.search(r"Audio[：:]", text)
    audio = text[m.start():] if m else ""
    # 只取 Audio 段（到下一个句号结束的自然段，粗略取 200 字）
    audio = audio[:220]
    return (
        audio,
        bool(VERB.search(audio)),
        bool(QUOTE.search(audio)) or bool(ESC_QUOTE.search(audio)),
    )


def main():
    rows = []
    for act, fn in SCRIPTS.items():
        for n, text in parse(os.path.join(ROOT, fn)).items():
            audio, has_verb, has_quote = analyze(text)
            if not audio:
                continue  # 该镜没写 Audio 段
            rows.append(dict(n=n, act=act, verb=has_verb, quote=has_quote,
                             leak=n in LEAK, audio=audio))
    rows.sort(key=lambda r: r["n"])

    print("=" * 96)
    print("泄漏镜 vs 干净镜 —— Audio 段写法对照（★ = 实际泄漏）")
    print("=" * 96)
    print("%-6s %-5s %-8s %-8s %s" % ("镜", "幕", "含台词", "含引号", "Audio 段"))
    print("-" * 96)
    for r in rows:
        print("%s%-5d %-5s %-8s %-8s %s" % (
            "★ " if r["leak"] else "  ", r["n"], r["act"],
            "是" if r["verb"] else "—",
            "是" if r["quote"] else "—",
            r["audio"].replace("\n", " ")[:56]))

    # ── 交叉统计 ──────────────────────────────────────────────
    print()
    print("=" * 96)
    print("交叉统计")
    print("=" * 96)

    def rate(pred):
        sel = [r for r in rows if pred(r)]
        if not sel:
            return 0, 0, 0.0
        hit = sum(1 for r in sel if r["leak"])
        return hit, len(sel), 100.0 * hit / len(sel)

    combos = [
        ("有台词 + 有引号", lambda r: r["verb"] and r["quote"]),
        ("有台词、无引号", lambda r: r["verb"] and not r["quote"]),
        ("无台词（纯环境音）", lambda r: not r["verb"]),
        ("A. 有台词（合计）", lambda r: r["verb"]),
        ("B. 全样本", lambda r: True),
    ]
    print("%-22s %-10s %-10s %s" % ("分组", "泄漏数", "组内总数", "泄漏率"))
    print("-" * 96)
    for name, pred in combos:
        hit, tot, pct = rate(pred)
        bar = "#" * int(round(pct / 2.5))
        print("%-22s %-10d %-10d %5.1f%%  %s" % (name, hit, tot, pct, bar))

    print()
    print("★ 结论提示：")
    print("  · 若「无台词」组泄漏率为 0 ⇒ 环境音不诱发泄漏，只有台词原文诱发。")
    print("  · 若「有引号」组显著高于「无引号」⇒ 引号（标点标记）是放大器，")
    print("    对应 §6.6「泄漏的是 prompt 原文连标点一起画」（镜 112 / 镜 7 的 `**`）。")


if __name__ == "__main__":
    main()
