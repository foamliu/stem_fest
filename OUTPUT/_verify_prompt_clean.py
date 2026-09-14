# -*- coding: utf-8 -*-
"""校验：幕脚本里**实际会送给 H3 的 prompt**是否还含污染文本。

背景
    2026-09-15 视觉检查铁证：H3 会把 prompt 里的**指令/元信息**渲染成画面字幕：
      · 镜 5 底部「本镜不要生成任何可语午白」  ← NO_SPEECH 常量
      · 镜 19 底部「全镜高适」                  ← 同一常量幻觉
      · 镜 91 中部「像在消化一件很难立刻接受」  ← 舞台指示
    因此必须校验**拼接后的最终 prompt**（含 + CONST 展开），而不是源码文本。

与 _scan_hazard.py 的区别
    _scan_hazard.py 是**扫描器**（列清单，含注释误报）。
    本脚本是**闸门**（gate）：只检查拼接后的真 prompt，非零退出即禁止开跑。
    规则更严：任何「本镜/该镜/不要生成/只允许/若画面」出现在真 prompt 里就 FAIL。

用法：
    py -3.10 OUTPUT/_verify_prompt_clean.py
    py -3.10 OUTPUT/_verify_prompt_clean.py --show=5
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")
SCRIPTS = ["_diag_act0_plane.py", "_diag_act1_trench.py", "_diag_act2_startup.py",
           "_diag_act3_rice.py", "_diag_act4_train.py", "_diag_act5_finale.py"]

# 出现在**真 prompt** 里即为污染（这些是"对模型说的话"，不是"对画面的描述"）
BANNED = [
    (r"本镜头?[^。；\n]{0,30}", "本镜指代"),
    (r"该镜[^。；\n]{0,30}", "该镜指代"),
    (r"此镜[^。；\n]{0,30}", "此镜指代"),
    (r"不要生成[^。；\n]{0,30}", "否定式指令"),
    (r"只允许[^。；\n]{0,30}", "否定式指令"),
    (r"若画面[^。；\n]{0,30}", "条件指令"),
    (r"不要把它念[^。；\n]{0,20}", "否定式指令"),
    (r"画面里不能少人", "否定式指令"),
    (r"没有说任何话", "否定式声明"),
    (r"没有任何台词", "否定式声明"),
    (r"像在[^。；\n]{0,30}", "内心状态"),
    (r"像是在[^。；\n]{0,30}", "内心状态"),
    (r"仿佛在[^。；\n]{0,30}", "内心状态"),
]


def expand(txt, path):
    """把 6 个幕脚本的 TASKS[N] prompt 拼接成最终字符串（展开 + CONST）。"""
    consts = {}
    for m in re.finditer(r'^([A-Z][A-Z0-9_]{2,})\s*=\s*\(([^)]*)\)', txt, re.M | re.S):
        consts[m.group(1)] = "".join(re.findall(r'"([^"]*)"', m.group(2)))
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
        j = pm.end()
        d2, s2 = 1, j
        while j < len(body) and d2:
            if body[j] == "(":
                d2 += 1
            elif body[j] == ")":
                d2 -= 1
            j += 1
        seg = body[s2:j]
        buf = []
        for t in re.split(r"\+|\n", seg):
            t = t.strip()
            if not t:
                continue
            lit = re.findall(r'"([^"]*)"', t)
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
            for n, t in expand(open(p, encoding="utf-8").read(), p).items():
                allp[n] = (s, t)

    if show:
        s, t = allp.get(show, ("?", ""))
        print("=== 镜 %d（%s）真 prompt ===" % (show, s))
        print(t)
        return 0

    bad = {}
    for n in sorted(allp):
        s, t = allp[n]
        for pat, name in BANNED:
            for m in re.finditer(pat, t):
                f = m.group(0).strip()
                if len(f) >= 3:
                    bad.setdefault(n, []).append((name, f))

    print("校验 %d 镜的真 prompt（已展开常量）" % len(allp))
    if not bad:
        print("\n✅ PASS —— 无污染文本，可以开跑")
        return 0
    print("\n❌ FAIL —— %d 镜仍含污染文本：\n" % len(bad))
    for n in sorted(bad):
        print("  镜 %d (%s)" % (n, allp[n][0]))
        seen = set()
        for name, f in bad[n]:
            if f in seen:
                continue
            seen.add(f)
            print("      [%s] %s" % (name, f[:90]))
    return 1


if __name__ == "__main__":
    sys.exit(main())
