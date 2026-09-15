# -*- coding: utf-8 -*-
"""修复：禁令行（★ 全画面不得…）后补 \\n，使其与 Audio: 分成两段。

根因（2026-09-16 定位）：批量插入 R3 禁令时，原 `"...。\\n"` 结构里
`Audio:` 行本身没有前置 `\\n`，插入禁令后变成
    "★ 全画面不得出现任何可读的文字、字幕或符号。"
    "Audio: ……"
Python 隐式拼接 → `符号。Audio: ……` 同一行，禁令与台词粘连，
H3 仍把台词当画面字幕渲染（镜 14 实测：改 prompt 后字幕依旧）。

修法：把禁令行末尾的 `。"` 改成 `。\\n"`。
用法：
    py -3.10 OUTPUT/_fix_guard_nl.py            # 预览
    py -3.10 OUTPUT/_fix_guard_nl.py --apply    # 落盘（自动 .bak 备份）
    py -3.10 OUTPUT/_fix_guard_nl.py --verify   # 复查 TASKS 内拼出的 prompt
"""
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = [
    "OUTPUT/_diag_act0_plane.py",
    "OUTPUT/_diag_act1_trench.py",
    "OUTPUT/_diag_act2_startup.py",
    "OUTPUT/_diag_act4_train.py",
    "OUTPUT/_diag_act5_finale.py",
]

GUARD = "★ 全画面不得出现任何可读的文字、字幕或符号。"


def shot_map(lines):
    tasks, cur = [], None
    for i, ln in enumerate(lines):
        m = re.match(r"TASKS\[(\d+)\]\s*=\s*dict\(", ln)
        if m:
            if cur:
                cur["end"] = i
                tasks.append(cur)
            cur = {"shot": int(m.group(1)), "start": i, "end": len(lines)}
    if cur:
        tasks.append(cur)

    def of(n):
        for t in tasks:
            if t["start"] <= n < t["end"]:
                return t["shot"]
        return None
    return of


def fix_text(text):
    """把 `GUARD。"` 改成 `GUARD。\\n"`（仅当其后紧跟 "Audio: 行时）。"""
    lines = text.split("\n")
    of = shot_map(lines)
    hits = []
    for i, ln in enumerate(lines):
        if GUARD in ln and re.match(r'\s*"' + re.escape(GUARD) + r'"\s*$', ln):
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if re.match(r'\s*"Audio:', nxt):
                lines[i] = ln.replace(GUARD + '"', GUARD + '\\n"')
                hits.append((of(i), i + 1))
    return "\n".join(lines), hits


def main():
    apply = "--apply" in sys.argv
    for rel in FILES:
        p = os.path.join(ROOT, rel)
        s = open(p, encoding="utf-8").read()
        new, hits = fix_text(s)
        if not hits:
            continue
        print("== %s  （%d 处）" % (os.path.basename(rel), len(hits)))
        for shot, nl in hits:
            print("   镜 %-4s  行 %-5d  → 补 \\n" % (shot, nl))
        if apply:
            shutil.copy2(p, p + ".guardnl.bak")
            open(p, "w", encoding="utf-8", newline="").write(new)
            print("   [已写入]  备份：%s.guardnl.bak" % os.path.basename(p))
    if not apply:
        print("\n（预览模式，加 --apply 落盘）")
    else:
        print("\n修复完成。请运行 --verify 复查。")


if __name__ == "__main__":
    main()
