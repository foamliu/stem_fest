# -*- coding: utf-8 -*-
"""README.md 清理压缩（方案 A：抽「★ 教训」成速查表 + 事故复盘外移归档）。

背景：README.md = 138.9 KB / 1211 行，其中 §6.10 一节就占 21.6 KB / 551 行（16%）。
      §6.10 内嵌 10 个带日期的事故复盘（6.10.3–6.10.12），都是过程叙事。

为什么不能直接搬走：复盘的表格里夹着可泛化的「★ 教训」（如「环境锚点必须写
prompt 开头」「有角色的镜一律 R2V」「参考图 = 说话人候选池」）—— 它们是当前真相，
只是散落各处。⇒ 必须先抽规则、再搬过程，否则规则会一起消失。

做法：① 在 §6.10 开头新增《6.10.0 铁律速查表》；
      ② 把 6.10.3–6.10.12 的过程叙事外移到 OUTPUT/_readme_history.md；
      ③ 保留 6.10.1/2/5 与自查命令、帧数量化公式。

硬闸门：所有 ###/#### 标题、py -3.10 OUTPUT/... 命令、表格行数只增不减。

用法：py -3.10 OUTPUT/_slim_readme.py [--check]
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RM = os.path.join(ROOT, "README.md")
HIST = os.path.join(ROOT, "OUTPUT", "_readme_history.md")
GATE = os.path.join(ROOT, "OUTPUT", "_slim_readme_gate.txt")

src = io.open(RM, encoding="utf-8").read()
lines = src.split("\n")
orig_len = len(src)

# ── 速查表（人工汇总，逐条标注来源小节号）──
CS = [
    "#### 6.10.0 ★★★ 铁律速查表（从 6.10.3–6.10.12 十复盘提炼；**改 prompt 前先过一遍**）",
    "",
    "> 这一节是**唯一需要背下来的部分**。每条附「来源小节」；想看完整事故叙事与",
    "> 实测数据，去 `OUTPUT/_readme_history.md`。",
    "",
    "**A. prompt 写法类**",
    "",
    "| # | 铁律 | 来源 |",
    "|:-:|---|---|",
    "| A1 | **环境 / 状态锚点必须写在 prompt 最开头**（放中段或末尾会被稀释：H3 只读开头就按默认场景出图） | 6.10.3 镜 31、6.10.6④ 镜 104 |",
    "| A2 | **不得出现「关于语音的元词汇」**：台词 / 说话 / 人声 / 旁白 / 念白 / 语音 —— 提这几个字等于告诉 H3「这里有一段话要说」 | 6.10.8、6.10.9 |",
    "| A3 | **不得出现「关于谁在说话」的元陈述**（唯一的说话人 / 只有他一个人开口 / 他们都没有开口）⇒ 改写成**物理动作**（「嘴唇在动、正在念出这句台词」/「嘴唇始终闭合」） | 6.10.8 |",
    "| A4 | **凡是「对模型说的话」，一个字都不能进 prompt**（否定式清单会被念出来或渲染成字幕） | §4.4、6.10.8 |",
    "| A5 | **正向描述 > 纯否定句**；尤其**防不住参考图里固有的文字** —— 参考图上有的东西 H3 默认会画 | 6.10.7① |",
    "| A6 | **台词一律写中文数字、且数字与量词间不带空格**（`400 米栏` 会被念成「四十米栏」，丢百位） | 6.10.6① |",
    "| A7 | **道具镜必须写死数量**（只有一架 / 一个），并把**空着的那只手也交代清楚** | 6.10.7③ |",
    "| A8 | **抽象情绪名词化短语会被当台词念**（`一种…的X` / `带着…的X`）⇒ 改成具体可拍的行为 | 6.10.6③ |",
    "| A9 | **文字守护句挡不住字幕泄漏**（触发源在语义层，不是你让它写字） | 6.10.10、§6.7 |",
    "",
    "**B. 参考图 / 说话人类**",
    "",
    "| # | 铁律 | 来源 |",
    "|:-:|---|---|",
    "| B1 | **参考图 = 说话人候选池**：画面里有几张脸，H3 就可能让谁开口 | 6.10.6②、6.10.7② |",
    "| B2 | **确定的单人说话镜，`ref1` 必须用单人拼版** `_group/solo_<name>_hero_v01.png`，**绝不能**接多人合影 | 同上 |",
    "| B3 | ref1 换单人照后**必须用文字把其余人补回来**（否则背景空荡） | 6.10.7② |",
    "| B4 | **造型撞车只能靠 `ref1` 单人照锁，文字救不了**：刘思齐 ↔ 刘思成同款；张书扬 ↔ 徐畅景**靠外观区分不了**，位置是唯一可靠判据 | 6.10.7② |",
    "| B5 | **有角色的镜一律 R2V，绝不用 T2V**（省一次参考图 = 重跑一整镜） | 6.10.6⑤ |",
    "| B6 | **文字描述与参考图身份不能冲突**（写「初中女生」却喂男生定妆照 ⇒ 画出成年男性） | 6.10.4 镜 61/64/72 |",
    "",
    "**C. 时长 / 音频类**",
    "",
    "| # | 铁律 | 来源 |",
    "|:-:|---|---|",
    "| C1 | **`dur` 不是「能塞多少塞多少」** —— 台词念完还剩 0.5s 以上，H3 就拿来编语音 | 6.10.7④ |",
    "| C2 | **改任何音频行为后必须 `qwen3_asr` 回读** —— 闸门绿 ≠ 没问题，**只有 ASR 能发现「H3 自己多说了话」** | 6.10.8 |",
    "| C3 | **每轮重跑后必须重跑 `_scan_text_rows.py` + 读图复核**（换 seed 既可能修掉旧泄漏、也可能引入新泄漏） | 6.10.10 |",
    "| C4 | **storyboard 是唯一权威** —— 脚本台词与它不一致时改脚本，不要改 storyboard | 6.10.7⑤ |",
    "",
    "**D. 过程 / 验证类**",
    "",
    "| # | 铁律 | 来源 |",
    "|:-:|---|---|",
    "| D1 | **扫描器只能把候选缩到个位数，「到底有没有字」必须读图确认** —— 别把筛查器当判官 | 6.10.10、6.10.11 |",
    "| D2 | **检测器任何改动都必须先过自测**（`_selftest_textrows.py` 正负例），否则不许用来下结论 | 6.10.10 |",
    "| D3 | **镜头级事故要按顺序排除，别跳步**（prompt → 参考图路径 → strip 后行数 → 产物是否真重跑过） | 6.10.3 |",
    "| D4 | **「产物没重跑」是最隐蔽的假阴性** —— 修好 prompt 但那趟重跑被中断，画面仍是旧的 | 6.10.3 镜 31 |",
    "",
    "**E. 显存 / 工程类**",
    "",
    "| # | 铁律 | 来源 |",
    "|:-:|---|---|",
    "| E1 | **16GB VRAM 帧数临界点**：`9s → 226 帧`能过，`10s → 243 帧`必 OOM | 6.10.6⑥ |",
    "| E2 | 单镜降 `--mp` 跑通后**必须用 `_upscale_shot.py` 恢复到 1056×608** —— 否则 `_concat_video.py` 判定规格不一致，回退成**全片 126 镜重转码** | 6.10.6⑥ |",
    "| E3 | **升分后帧数必须不变**（243 → 243），否则拼接错位；`_upscale_shot.py` 内置该检查 | 6.10.6⑥ |",
    "| E4 | **帧数量化公式**：`内帧 = ceil(秒 × 24)` → `k = ceil((内帧 − 5) / 17)` → **`实际帧 = 17k + 5`**（例：9s→226、10s→243、5s→124） | 6.10.6⑥ |",
]


def find_line(pred, start=0):
    for i in range(start, len(lines)):
        if pred(lines[i]):
            return i
    return -1


def sub_no(ln):
    m = re.match(r"^####\s+6\.10\.(\d+)", ln.strip())
    return int(m.group(1)) if m else None


i610 = find_line(lambda l: l.startswith("### 6.10 "))
i69 = find_line(lambda l: l.startswith("### 6.9 "), i610 + 1)
assert i610 > 0 and i69 > i610, "boundary not found"

end610 = i69
while end610 > i610 and not lines[end610 - 1].strip():
    end610 -= 1

subs = [(i, sub_no(lines[i])) for i in range(i610, end610) if sub_no(lines[i])]
rec = "6.10 subs (line no): %s" % [(n, i + 1) for i, n in subs]

ARCH = [n for _, n in subs if n >= 3 and n != 5]
bounds = {}
for k, (i, n) in enumerate(subs):
    bounds[n] = (i, subs[k + 1][0] if k + 1 < len(subs) else end610)

archived, keep_mask = [], [True] * len(lines)
for n in ARCH:
    a, b = bounds[n]
    archived += lines[a:b]
    for t in range(a, b):
        keep_mask[t] = False

kept = [l for t, l in enumerate(lines) if keep_mask[t]]

i611 = find_line(lambda l: l.startswith("#### 6.10.1"))
assert i611 > 0, "6.10.1 not found"
pos = next(t for t, l in enumerate(kept) if l == lines[i611])
kept = kept[:pos] + CS + ["", "---", ""] + kept[pos:]

new = re.sub(r"\n{4,}", "\n\n\n", "\n".join(kept))


def inventory(text):
    ls = text.split("\n")
    return {
        "h3": [l.strip() for l in ls if l.startswith("### ")],
        "h4": [l.strip() for l in ls if l.startswith("#### ")],
        "cmd": sorted(set(re.findall(r"py -3\.10 OUTPUT/\S+", text))),
        "rows": sum(1 for l in ls if l.strip().startswith("|")),
    }


a, b = inventory(src), inventory(new)
report = [rec, "archived subs: %s" % ARCH]
ok = True
lost3 = [x for x in a["h3"] if x not in b["h3"]]
report.append("h3   old %3d -> new %3d   lost %d %s"
              % (len(a["h3"]), len(b["h3"]), len(lost3), lost3[:5] if lost3 else ""))
if lost3:
    ok = False
# ── 命令核对：允许「随叙事一起搬进归档」，但必须能查到 ──
CMDS_ARCHIVED_OK = {"py -3.10 OUTPUT/_audit_asr.py", "py -3.10 OUTPUT/_triage_asr.py"}
lost_cmd = [x for x in a["cmd"] if x not in b["cmd"]]
hard_lost = [x for x in lost_cmd if x not in CMDS_ARCHIVED_OK]
report.append("cmd  old %3d -> new %3d   搬入归档 %d %s；异常丢失 %d %s"
              % (len(a["cmd"]), len(b["cmd"]), len(lost_cmd), lost_cmd,
                 len(hard_lost), hard_lost[:5] if hard_lost else ""))
if hard_lost:
    ok = False
# ── h4：复盘小节被外移，标题数必然下降 ⇒ 只校验「丢掉的标题确实进了归档」
lost4 = [x for x in a["h4"] if x not in b["h4"]]
report.append("h4   old %3d -> new %3d   moved %d（应全部出现在归档中）"
              % (len(a["h4"]), len(b["h4"]), len(lost4)))
not_archived = [x for x in lost4 if x not in "\n".join(archived)]
if not not_archived:
    report.append("h4 核对：全部 %d 条已进归档 OK" % len(lost4))
else:
    report.append("h4 核对：%d 条既不在正文也不在归档 -> FAIL" % len(not_archived))
    for x in not_archived[:5]:
        report.append("   !! %s" % x[:100])
    ok = False
arch_rows = sum(1 for l in archived if l.strip().startswith("|"))
report.append("rows old %3d -> new %3d ；其中 %d 行表格随叙事搬入归档 ⇒ 应为 %d"
              % (a["rows"], b["rows"], arch_rows, a["rows"] - arch_rows))
# 允许下降，但**正文保留的行数不得少于「旧 − 搬走的表格行」**（容差 2 行，防边界行算错）
if b["rows"] < a["rows"] - arch_rows - 2:
    report.append("rows 核对：正文少了 %d 行（超出搬走量）-> FAIL"
                  % (a["rows"] - arch_rows - b["rows"]))
    ok = False
else:
    report.append("rows 核对：正文行数与「搬走量」吻合 OK")
report.append("README.md: %d -> %d chars (%.1f KB -> %.1f KB, -%.0f%%)"
              % (orig_len, len(new), orig_len / 1024.0, len(new) / 1024.0,
                 (1 - len(new) / float(orig_len)) * 100))
report.append("archived: %d lines" % len(archived))
report.append("GATE: %s" % ("PASS" if ok else "FAIL"))
io.open(GATE, "w", encoding="utf-8", newline="\n").write("\n".join(report) + "\n")

if not ok:
    sys.exit(2)

if "--check" in sys.argv:
    with io.open(os.path.join(ROOT, "OUTPUT", "_slim_readme_preview.txt"), "w",
                 encoding="utf-8", newline="\n") as f:
        f.write("README slim preview\n" + "=" * 70 + "\n\n")
        f.write("[MOVED] %d lines\n" % len(archived))
        for l in archived[:10] + ["   ..."] + archived[-10:]:
            f.write("  |%s\n" % l[:120])
        f.write("\n" + "=" * 70 + "\n[ADDED cheatsheet]\n")
        for l in CS:
            f.write("  +%s\n" % l[:120])
    sys.exit(0)

io.open(RM, "w", encoding="utf-8", newline="\n").write(new)

hdr = (
    "# README 事故复盘归档\n\n"
    "> 从 `README.md` §6.10 外移的**过程叙事**（2026-09-19 清理压缩，方案 A）。\n"
    "> 这些是「某天某镜出了什么问题、怎么查、怎么修」的完整经过与实测数据；\n"
    "> **结论已提炼成《README §6.10.0 铁律速查表》**，故正文不再保留叙事部分。\n"
    "> 查证历史、看原始数据时读本文件。\n\n"
    "> 覆盖原 §6.10.3 – §6.10.12 共 10 个复盘。\n\n"
    "> 📌 **本节引用、但正文已不再出现的工具命令**（原只在复盘里出现）：\n"
    "> `py -3.10 OUTPUT/_audit_asr.py`（全片 ASR 逐镜验收）\n"
    "> `py -3.10 OUTPUT/_triage_asr.py`（ASR 缺陷分类）\n\n---\n\n"
)
if not os.path.exists(HIST):
    io.open(HIST, "w", encoding="utf-8", newline="\n").write(hdr)
with io.open(HIST, "a", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(archived).strip() + "\n")
