#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按角色统计「出场镜号」与其中「≥2 人的镜数」——用于规划每个角色要多少张合成参考图。

★ 每改完剧本（增删镜号 / 改参考图提示）必须重跑本脚本，并用它的产物
  `OUTPUT/_cast_per_char.txt` 去同步 `README.md` §8 P0 的合影台账与
  `ASSETS/README.md` §2 的角色出场镜号。

用法： py -3.10 OUTPUT/_diag_cast_per_char.py
"""
import os
import re

ROOT = r"E:\code\stem_fest"
SB = os.path.join(ROOT, "storyboard.md")
REPORT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cast_per_char.txt")

ALIASES = {
    "刘思齐": "刘思齐", "刘思成": "刘思成", "徐畅景": "徐畅景", "张书扬": "张书扬",
    "黄继光": "黄继光", "袁隆平": "袁隆平", "钟南山": "钟南山",
    "小战士": "小战士", "小女孩": "小女孩", "妈妈": "妈妈",
    "战士": "战士群演", "志愿军": "战士群演",
}
MAIN4 = ["刘思齐", "刘思成", "徐畅景", "张书扬"]

# 已知假阳性：该「组合」只是因为**台词里提到了某人**才成立，画面里并没有这个人
# ⇒ 不需要为它做合影图。key 必须与 combos 的 key 一致（tuple(sorted(cast))）。
FALSE_POSITIVE = {
    ("刘思成", "刘思齐", "钟南山"):
        "镜 80 的台词点名「钟南山」，画面里只有刘思成 + 刘思齐 ⇒ 直接用「刘思成、刘思齐」那张两人合影即可",
}

rows = []
COLS = None
NEED = ["镜号", "时长", "画面", "台词/音效", "参考图提示"]
for line in open(SB, encoding="utf-8").read().splitlines():
    if not line.startswith("|"):
        COLS = None if COLS is None else COLS
        continue
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if cells and cells[0] == "镜号":
        COLS = {n: i for i, n in enumerate(cells)}
        continue
    if not COLS or any(n not in COLS for n in NEED):
        continue
    if max(COLS[n] for n in NEED) >= len(cells):
        continue
    if not re.fullmatch(r"\d+", cells[COLS["镜号"]]):
        continue
    if not re.fullmatch(r"\d+s", cells[COLS["时长"]]):
        continue
    rows.append((int(cells[COLS["镜号"]]),
                 int(cells[COLS["时长"]][:-1]),
                 cells[COLS["画面"]],
                 cells[COLS["台词/音效"]],
                 cells[COLS["参考图提示"]]))

per_shot = []
for sid, dur, vis, dia, ref in rows:
    blob = vis + " " + dia + " " + ref
    cast = set()
    if re.search(r"四人", blob):
        cast.update(MAIN4)
    for alias, canon in ALIASES.items():
        if alias in blob:
            cast.add(canon)
    per_shot.append((sid, dur, sorted(cast)))

chars = {}
for sid, dur, cast in per_shot:
    for c in cast:
        chars.setdefault(c, []).append(sid)

combos = {}
for sid, dur, cast in per_shot:
    if len(cast) >= 2:
        combos.setdefault(tuple(cast), []).append(sid)

out = []
w = out.append
w("# 按角色统计（有效 %d 镜）" % len(per_shot))
w("")
w("> 生成方式：`python OUTPUT/_diag_cast_per_char.py`（★ 每改剧本必重跑）")
w("")
w("| 角色 | 出场镜数 | 全是单人 | 多人镜（≥2 人） | 单人镜号 | 多人镜号 |")
w("|---|:--:|:--:|:--:|---|---|")
for c, ids in sorted(chars.items(), key=lambda kv: -len(kv[1])):
    solo = [i for i in ids if len(dict((s, cs) for s, d, cs in per_shot)[i]) == 1]
    multi = [i for i in ids if i not in solo]
    w("| %s | %d | %d | **%d** | %s | %s |" % (
        c, len(ids), len(solo), len(multi),
        ",".join(map(str, solo)) or "—", ",".join(map(str, multi)) or "—"))

w("")
w("说明：'出场' = 该角色名出现在该镜的 画面/台词/参考图提示 任一列（「四人」按四小强展开）。")
w("")
w("## 多人镜的「角色组合」去重 —— 每一行 = 需要合成 **一张** 参考图")
w("")
tot = sum(len(v) for v in combos.values())
w("共 **%d** 种组合，覆盖 %d 个多人镜。" % (len(combos), tot))
w("")
w("| # | 人数 | 角色组合 | 镜号 | 镜数 |")
w("|:-:|:-:|---|---|:--:|")
for i, (key, ids) in enumerate(sorted(combos.items(), key=lambda kv: (-len(kv[1]), -len(kv[0]))), 1):
    mark = " ⚠️见下" if key in FALSE_POSITIVE else ""
    w("| %d | %d | %s | %s | %d%s |" % (i, len(key), "、".join(key),
                                        ",".join(map(str, ids)), len(ids), mark))
w("")
w("### 假阳性（不需要做图）")
w("")
for key, why in FALSE_POSITIVE.items():
    w("- **%s** —— %s" % ("、".join(key), why))

with open(REPORT, "w", encoding="utf-8") as f:
    f.write("\n".join(out) + "\n")
print("镜数=%d 角色=%d 组合=%d" % (len(per_shot), len(chars), len(combos)))
print("done -> %s" % REPORT)
