# -*- coding: utf-8 -*-
"""镜 19-46（第一幕·上甘岭）：史实修正 —— 10 月深秋气候 + 志愿军『50式』冬装。

★ 起因（用户指出）：「上甘岭这一战是在 10 月份，场景不对。」

★ 史实核对（用户检索确认）：
   · 上甘岭战役 = **1952-10-14 — 11-25**。打响当天是**深秋**，早晨寒意未褪，
     但**白天有太阳**（有记载当天「艳阳高照」）。
   · 严寒（-20~-39℃、冻土一米、大雪狂风）属于**11 月下旬战役后期及 1953 年初
     后续部队接防时期**，**不是 10 月**。
   · 志愿军着装 = **「50式」冬服**：棉衣（战士款双肩护肩布、袖口袢带）、
     棉裤（裤脚抽带）、**栽绒棉帽（带听孔/可放护耳）**、**高腰毛皮鞋**。

★ 修什么 / 不修什么
   修：① 统一光线基调 LIGHT（旧版「天灰蒙蒙、没有直射阳光」= 把深秋写成隆冬阴霾）
       ② 所有出现**志愿军战士**的镜，补挂 `GUARD_SOLDIER_WINTER` 冬装护栏
   不修：四小强**仍穿白短袖 Polo + 红领巾** —— 他们是 2026 年进入世界模型的穿越者，
         按设定不应换装；「现代学生 vs 1952 战士」的时代对比是**刻意设计**，不是错误。

用法：py -3.10 OUTPUT/_patch_act1_winter.py [--check]
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "OUTPUT", "_diag_act1_trench.py")
GATE = os.path.join(ROOT, "OUTPUT", "_patch_act1_winter_gate.txt")

# 需要挂冬装护栏的镜（含"志愿军战士"或"战士"的镜；含黄继光的镜另挂 GUARD_HUANG）
import importlib.util
spec = importlib.util.spec_from_file_location("act1", SRC)
mod = importlib.util.module_from_spec(spec)
sys.modules["act1"] = mod
spec.loader.exec_module(mod)

targets = []
for n, t in sorted(mod.TASKS.items()):
    p = t.get("prompt", "")
    if ("战士" in p) or ("志愿军" in p):
        targets.append(n)

print("需要补冬装护栏的镜：%s（共 %d 镜）" % (targets, len(targets)))

text = io.open(SRC, encoding="utf-8").read()
orig = text

# 逐镜处理：在该镜 prompt 的 "+ LIGHT" 或 "+ GUARD_HUANG" 之后插入冬装护栏
lines = text.split("\n")
out = []
cur = None
inserted = {}
for i, ln in enumerate(lines):
    m = re.match(r"^TASKS\[(\d+)\]\s*=", ln)
    if m:
        cur = int(m.group(1))
    # 插入点：该镜块内、首次出现 "GUARD_HUANG" 或 "LIGHT" 拼装的那一行
    # ★ 关键：必须**接在表达式链里**（`+ GUARD_SOLDIER_WINTER` 作为续行），
    #   不能另起一条独立语句 —— 否则会切断隐式字符串拼接，导致 SyntaxError。
    if cur in targets and cur not in inserted:
        if ("+ GUARD_HUANG" in ln) or ("+ LIGHT" in ln) or ("+GUARD_HUANG" in ln):
            ind = re.match(r"^(\s*)", ln).group(1)
            # ★ 行尾补 `+`，使**下一行的隐式字符串拼接仍成立**；
            #   否则插入后 `GUARD_SOLDIER_WINTER` 与后续字面量之间没有运算符
            #   ⇒ SyntaxError: invalid syntax（首次尝试就是这么炸的）。
            out.append(ln.rstrip() + " +")
            out.append("%sGUARD_SOLDIER_WINTER +" % (ind + "    "))
            inserted[cur] = i + 1
            continue
    out.append(ln)

text = "\n".join(out)
missing = [n for n in targets if n not in inserted]
print("已插入：%s" % sorted(inserted))
if missing:
    print("!! 未找到插入点的镜：%s" % missing)

# 校验：原文的 LIGHT 出现次数不变、GUARD_SOLDIER_WINTER 出现次数 = len(inserted)
n_light = text.count("+ LIGHT")
# ★ 语法闸门（必须过）：首版补丁切断了隐式字符串拼接 ⇒ SyntaxError。
#   任何文本级插入都必须先 compile 一遍再落盘。
syn_ok, syn_err = True, ""
try:
    compile(text, SRC, "exec")
except SyntaxError as e:
    syn_ok, syn_err = False, "%s (line %s)" % (e.msg, e.lineno)

report = [
    "targets: %s" % targets,
    "inserted at line: %s" % sorted(inserted.items()),
    "missing: %s" % missing,
    "GUARD_SOLDIER_WINTER occurrences: %d" % text.count("+ GUARD_SOLDIER_WINTER"),
    "LIGHT usages: %d" % n_light,
    "syntax: %s %s" % ("OK" if syn_ok else "FAIL", syn_err),
]
ok = (not missing) and syn_ok
report.append("GATE: %s" % ("PASS" if ok else "FAIL"))
io.open(GATE, "w", encoding="utf-8", newline="\n").write("\n".join(report) + "\n")

if not ok:
    print("gate failed; not written")
    sys.exit(2)

if "--check" in sys.argv:
    print("check mode: not written")
    sys.exit(0)

io.open(SRC, "w", encoding="utf-8", newline="\n").write(text)
print("已写回 %s" % os.path.relpath(SRC, ROOT))
