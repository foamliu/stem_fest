# -*- coding: utf-8 -*-
"""扫描所有幕脚本里的 prompt，找出会被 H3 渲染成画面字幕的「指令性文本」。

背景（2026-09-15 视觉检查发现）
    视觉检查确认：H3 会把 prompt 里的**指令性/元信息文本**当作台词，
    直接渲染成画面字幕。已实锤两例：
      · 镜 5  底部字幕「本镜不要生成任何可口旁白」  ← 来自 NO_SPEECH 常量
      · 镜 19 底部字幕「全镜高适」                  ← 疑似同类幻觉
      · 镜 91 画面中部「像在消化一件很难立刻接受的事」← 来自描述性元信息
    根因：prompt 里出现「本镜/不要生成/只允许/若画面…」这类**对模型说的话**，
    而不是**对画面的描述**。H3 无法区分「指令」与「台词」，一律当词句输出。

扫描规则（命中即高危）
    1. 【…】 或 ［…］ 包裹的整句指令
    2. 「本镜 / 本镜头 / 该镜 / 此镜」开头的句子
    3. 「不要生成 / 不要出现 / 只允许 / 不允许 / 禁止」等否定祈使
    4. 「若画面 / 如果画面 / 如有」等条件指令
    5. 「像在 / 仿佛在 / 暗示 / 意在 / 传达出」等内心状态描述
    6. 「（后期）/（音效）/（待补）」等制作备忘

输出
    OUTPUT/_prompt_hazard.txt   命中清单（幕 / 镜号 / 命中片段 / 规则）

用法：
    py -3.10 OUTPUT/_scan_hazard.py
    py -3.10 OUTPUT/_scan_hazard.py --show=5   # 打印镜 5 的完整 prompt
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")
REFS = os.path.join(OUT, "_shot_refs.json")

SCRIPTS = ["_diag_act0_plane.py", "_diag_act1_trench.py", "_diag_act2_startup.py",
           "_diag_act3_rice.py", "_diag_act4_train.py", "_diag_act5_finale.py"]

RULES = [
    ("R1 括号指令", r"【[^】]*】|［[^］]*］"),
    ("R2 本镜指代", r"本镜头?[^。；\n]{0,40}|该镜[^。；\n]{0,40}|此镜[^。；\n]{0,40}"),
    ("R3 否定祈使", r"[^。；\n]{0,20}(不要生成|不要出现|不要有|只允许|不允许|禁止|切勿|不可)[^。；\n]{0,40}"),
    ("R4 条件指令", r"[^。；\n]{0,10}(若画面|如果画面|若有人群|如有)[^。；\n]{0,40}"),
    ("R5 内心描述", r"[^。；\n]{0,16}(像在|仿佛在|似乎已|暗示|意在|传达出|流露出)[^。；\n]{0,40}"),
    ("R6 制作备忘", r"（后期）|（音效）|（待补）|（后期铺）"),
]


def parse_prompts(path):
    """抽 {镜号: prompt 文本}。"""
    txt = open(path, encoding="utf-8").read()
    # 常量表（把 + CONST 也纳入最终 prompt）
    consts = {}
    for m in re.finditer(r'^([A-Z][A-Z0-9_]{2,})\s*=\s*\(([^)]*)\)', txt, re.M | re.S):
        parts = re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(2))
        consts[m.group(1)] = "".join(p.encode().decode("unicode_escape")
                                     if "\\" in p else p for p in parts)
    for m in re.finditer(r'^([A-Z][A-Z0-9_]{2,})\s*=\s*"([^"]*)"', txt, re.M):
        consts[m.group(1)] = m.group(2)

    out = {}
    for m in re.finditer(r"^TASKS\[(\d+)\]\s*=\s*dict\(", txt, re.M):
        n = int(m.group(1))
        i = m.end()
        depth, start = 1, i
        while i < len(txt) and depth:
            if txt[i] == "(":
                depth += 1
            elif txt[i] == ")":
                depth -= 1
            i += 1
        body = txt[start:i]
        pm = re.search(r"prompt\s*=\s*\(", body, re.S)
        if not pm:
            out[n] = ""
            continue
        # 取 prompt=( ... ) 内所有片段（含 + CONST 引用）
        j = pm.end()
        depth2, st2 = 1, j
        while j < len(body) and depth2:
            if body[j] == "(":
                depth2 += 1
            elif body[j] == ")":
                depth2 -= 1
            j += 1
        seg = body[st2:j]
        buf = []
        for t in re.split(r"\+|\n", seg):
            t = t.strip()
            if not t:
                continue
            lit = re.findall(r'"((?:[^"\\]|\\.)*)"', t)
            if lit:
                buf.append("".join(lit))
            elif t in consts:
                buf.append(consts[t])
        out[n] = "".join(buf)
    return out


def main():
    show = None
    for a in sys.argv[1:]:
        if a.startswith("--show="):
            show = int(a.split("=", 1)[1])

    allp = {}
    for s in SCRIPTS:
        p = os.path.join(OUT, s)
        if os.path.exists(p):
            got = parse_prompts(p)
            for n, t in got.items():
                allp[n] = (s, t)

    if show:
        s, t = allp.get(show, ("?", ""))
        print("=== 镜 %d（%s）prompt 全文 ===" % (show, s))
        print(t)
        return 0

    hits = {}
    for n in sorted(allp):
        s, t = allp[n]
        for rname, pat in RULES:
            for m in re.finditer(pat, t):
                frag = m.group(0).strip()
                if len(frag) < 4:
                    continue
                hits.setdefault(n, []).append((rname, frag))

    print("扫描 %d 镜，命中 %d 镜有高危文本\n" % (len(allp), len(hits)))
    by_rule = {}
    for n, lst in hits.items():
        for rname, _ in lst:
            by_rule.setdefault(rname, []).append(n)
    print("按规则统计（受影响镜数）：")
    for r, ns in sorted(by_rule.items()):
        print("   %-14s %3d 镜  %s" % (r, len(set(ns)), sorted(set(ns))[:14]))

    with open(os.path.join(OUT, "_prompt_hazard.txt"), "w", encoding="utf-8") as f:
        f.write("H3 prompt 字幕污染高危清单（按镜号）\n")
        f.write("=" * 70 + "\n")
        for n in sorted(hits):
            s, _ = allp[n]
            f.write("\n镜 %d  (%s)\n" % (n, s))
            seen = set()
            for rname, frag in hits[n]:
                if frag in seen:
                    continue
                seen.add(frag)
                f.write("   [%s] %s\n" % (rname, frag[:110]))
    print("\n清单：OUTPUT/_prompt_hazard.txt")
    if hits:
        print("\n★ 高危镜号汇总（去重）：%s" % sorted(hits))
    return 0


if __name__ == "__main__":
    sys.exit(main())
