# -*- coding: utf-8 -*-
"""storyboard.md 清理压缩（方案 1：历史记录外移归档）。

★ 目标
   把「**已经落地完成的过程记录**」从 `storyboard.md` 移到 `OUTPUT/_storyboard_history.md`，
   让 storyboard 只保留**当前真相**：元信息 + 读法 + 6 幕分镜表 + 汇总章节。

★ 为什么可以外移（安全前提）
   被移出的都是「**为什么这么改**」的决策依据，而**改的结果已经落在正文里**：
     · 第三轮台词修订总表  → 措辞已逐句落到各镜「台词/音效」格
     · 第四轮镜 1 校名反转 → 已落到镜 1 画面描述 + 制作约定 #10
     · 各轮压缩说明        → 已落到「全片镜数核对」合计 + 制作约定 #12
   ⇒ 移出后**不丢任何一镜的信息**，只丢「过程」。

★ 硬闸门（改完必须过）
   `python OUTPUT/_audit_storyboard.py`：126 镜的镜号/时长/台词/景别/运镜/参考图
   必须与生产脚本 TASKS 一致 —— 压缩**不得**动任何一镜的数据列。

用法：py -3.10 OUTPUT/_slim_storyboard.py [--check]
"""
import io
import os
import re
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SB = os.path.join(ROOT, "storyboard.md")
HIST = os.path.join(ROOT, "OUTPUT", "_storyboard_history.md")

src = io.open(SB, encoding="utf-8").read()
orig_len = len(src)


# ── 1. 修确凿重复：制作约定 #10 里同一段「2026-09-19 补充」逐字出现两遍 ──
def dedupe_line10(text):
    """第 10 条里的补充段重复两遍 ⇒ 只留第一遍。"""
    marker = "⚠️ **2026-09-19 补充**"
    lines = text.split("\n")
    for i, ln in enumerate(lines):
        if ln.startswith("10. **校园展示保护**") and ln.count(marker) > 1:
            first = ln.find(marker)
            second = ln.find(marker, first + 1)
            lines[i] = ln[:second].rstrip()
            return "\n".join(lines), ln[second:]
    return text, None


src, dropped = dedupe_line10(src)
print("① 制作约定 #10 重复段：%s" % ("已删除 %d 字符" % len(dropped)
                                     if dropped else "未发现"))


# ── 2. 按「区块」切分文首的历史记录（第 1–136 行区间的引用块）──
#    策略：整体以 "## 运镜列读法" 为界，之前的部分里挑出**历史块**外移，
#    保留「元信息表 + 主题句定案 + 时长怎么定（含公式与当前压缩结论）」。
lines = src.split("\n")
try:
    cut = lines.index("## 运镜列读法")
except ValueError:
    print("!! 找不到 '## 运镜列读法'，中止")
    sys.exit(1)

head = lines[:cut]          # 文首区
rest = lines[cut:]          # 正文区（读法 + 分镜表 + 汇总）

# 文首区里要**移出**的历史块（以引用块内小节标题开头识别，见下方判据）

archived, kept, mode = [], [], None
for ln in head:
    s = ln.strip()
    # 引用块里的历史小节写作 "> ## **第三轮…**" ⇒ 去掉引用前缀再判
    plain = s.lstrip("> ").lstrip("#").strip().strip("*").strip()
    if plain.startswith("第三轮：画面实体文字排查") \
       or plain.startswith("第四轮：镜 1 校名方向反转") \
       or plain.startswith("第三轮：台词执行层修订总表"):
        mode = "arch"
    elif s.startswith("## "):            # 新的顶层小节 ⇒ 结束归档
        mode = None
    (archived if mode == "arch" else kept).append(ln)

print("② 文首历史块：归档 %d 行，保留 %d 行" % (len(archived), len(kept)))

# ── 3. 把「第三轮台词修订总表」等表格也外移（它在 kept 里，以 '> |' 形式出现）──
#    识别：引用块内以 "| 镜 | 原措辞" 开头的表 ⇒ 整表外移
out_kept, mode2, moved_tbl = [], None, []
for ln in kept:
    s = ln.strip().lstrip("> ").strip()
    if s.startswith("| 镜 | 原措辞"):
        mode2 = "table"
    elif mode2 == "table" and not s.startswith("|"):
        mode2 = None
    (moved_tbl if mode2 == "table" else out_kept).append(ln)
print("③ 台词修订总表：归档 %d 行" % len(moved_tbl))

kept = out_kept

# ── 3b. 「时长怎么定的」里的**压缩历史**（公式必须留，历史外移）──
#   该节结构：公式与口径（28-41 行，**必留**）+ 三轮压缩记录（**外移**）。
#   判据：以「★ **2026-」或「★ **2026-09-17 第二轮压缩」开头的小标题 ⇒ 整块外移到下一小标题。
out2, mode3, moved_hist = [], None, []
for ln in kept:
    s = ln.strip().lstrip("> ").strip()
    if re.match(r"^★\s*\*\*2026-", s):
        mode3 = "hist"
    elif mode3 == "hist" and s.startswith("## "):
        mode3 = None
    (moved_hist if mode3 == "hist" else out2).append(ln)
kept = out2
print("③b 时长节压缩历史：归档 %d 行" % len(moved_hist))

# ── 4. 组装新 storyboard ──
new = "\n".join(kept + rest)
# 清理连续空行（>2 个压成 1 个空行）
new = re.sub(r"\n{3,}", "\n\n", new)

if "--check" in sys.argv:
    pv = os.path.join(ROOT, "OUTPUT", "_slim_preview.txt")
    with io.open(pv, "w", encoding="utf-8", newline="\n") as f:
        f.write("storyboard 清理压缩 · 预演\n" + "=" * 70 + "\n\n")
        f.write("【移到归档】文首历史块 %d 行\n" % len(archived))
        for ln in archived:
            f.write("  |%s\n" % ln[:120])
        f.write("\n【移到归档】时长节压缩历史 %d 行\n" % len(moved_hist))
        for ln in moved_hist:
            f.write("  |%s\n" % ln[:120])
        f.write("\n【移到归档】台词修订总表 %d 行\n" % len(moved_tbl))
        for ln in moved_tbl:
            f.write("  |%s\n" % ln[:120])
        f.write("\n" + "=" * 70 + "\n【保留】新 storyboard 文首 %d 行\n" % len(kept))
        for ln in kept:
            f.write("  |%s\n" % ln[:120])
        f.write("\n" + "=" * 70 + "\n预演：%d → %d 字符（↓%.0f%%）；未写盘。\n"
                % (orig_len, len(new), (1 - len(new) / float(orig_len)) * 100))
    print("预演已写入 OUTPUT/_slim_preview.txt（UTF-8，直接用编辑器看）")
    print("预演：%d → %d 字符（↓%.0f%%）；未写盘。"
          % (orig_len, len(new), (1 - len(new) / float(orig_len)) * 100))
    sys.exit(0)

io.open(SB, "w", encoding="utf-8", newline="\n").write(new)

# ── 5. 组装归档文件 ──
if not os.path.exists(HIST):
    io.open(HIST, "w", encoding="utf-8", newline="\n").write(
        "# storyboard 历史记录归档\n\n"
        "> 从 `storyboard.md` 外移的**过程记录**（2026-09-19 清理压缩）。\n"
        "> 这些是「为什么这么改」的决策依据；**改动结果已落在 storyboard 正文**，\n"
        "> 故正文不再重复保留。查证历史时看本文件。\n\n---\n\n")
with io.open(HIST, "a", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(archived + moved_hist + moved_tbl).strip() + "\n\n---\n\n")

print("-" * 70)
print("storyboard.md : %d → %d 字符（%.1f KB → %.1f KB，↓%.0f%%）"
      % (orig_len, len(new), orig_len / 1024.0, len(new) / 1024.0,
         (1 - len(new) / float(orig_len)) * 100))
print("归档         : %s" % os.path.relpath(HIST, ROOT))
