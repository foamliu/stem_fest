#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第一幕「季节口径」一致性体检（2026-09-20，幂等只读）。

★ 为什么要这个脚本
    第一幕的季节口径**改过三次**：
      09-19  「天色偏冷、无直射阳光」    → 被推翻（判为"隆冬阴霾"，与 10 月不符）
      09-19' 「深秋、白天有太阳、无积雪」 → 又被推翻（用户指出与史实不符）
      09-20  「风雪阴冷、浮土遮天、薄雪泥水」 ← **现行定稿，以史料为据**
    三次改动牵连 5 个文件（storyboard / 2 个 README / prompt 脚本 / 场景图），
    靠肉眼记不可能记全 ⇒ 本脚本做**机械核对**。

★ 判据
    `FORBIDDEN` 词出现在 **prompt 代码行**（非注释）→ ❌ FAIL（会真的污染出图）
    `FORBIDDEN` 词只出现在**注释**里            → ⚠️ WARN（允许：用于存档教训）
    `REQUIRED` 关键词缺失                       → ❌ FAIL（没改到）

用法
    py -3.10 OUTPUT/_check_winter_consistency.py
    py -3.10 OUTPUT/_check_winter_consistency.py --json OUTPUT/_winter_consistency.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 现行定稿：风雪阴冷
#
# ⚠️ 判据精度（2026-09-20 实测修正，第 1 版误报 10 条全是误伤）：
#   「暖金色」在**其他幕**是正确用词（序幕二/第三幕教室与餐车都是暖色），
#   不能当全局禁忌 ⇒ 必须**只在第一幕上下文里**查。
#   同理「无积雪 / 深秋调色锁定」出现在**引述旧记录已作废**的句子里是正常的，
#   靠关键词无法区分「现行口径」与「引述历史」⇒ 改用 **`ALLOW_MARK` 豁免**：
#   该行含豁免标记时跳过（用于存档教训、引述旧稿、说明"已作废"的行）。
FORBIDDEN = [
    "白天有太阳", "暖调为主", "暖亮", "暖黄赭石", "地面上没有积雪",
]

# 行内含以下任一标记 ⇒ 视为「在讲历史/讲其他幕」，跳过检查
ALLOW_MARK = [
    "已作废", "推翻", "引言", "旧稿", "旧记录", "其他幕", "序幕", "第三幕", "教室", "餐车",
]

# 只在第一幕范围内检查（其余幕的冷暖口径与本议题无关）
ACT1_MARK = "第一幕"

TARGETS = [
    ("storyboard.md", ["风雪阴冷", "浮土遮天"]),
    ("ASSETS/README.md", ["风雪阴冷"]),
    ("ASSETS/STYLE/README.md", ["冷灰蓝"]),
    ("OUTPUT/_diag_act1_trench.py", ["风雪阴冷的战前交通壕", "LIGHT_TONE"]),
]


def scan(path: str, required: list[str]) -> dict:
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        return {"file": path, "error": "不存在"}
    lines = open(full, encoding="utf-8").read().split("\n")
    code_hits, comment_hits, exempt_hits, req_missing = [], [], [], []
    for i, l in enumerate(lines, 1):
        is_comment = l.lstrip().startswith("#")
        exempt = any(m in l for m in ALLOW_MARK)
        for w in FORBIDDEN:
            if w in l:
                if is_comment:
                    comment_hits.append({"line": i, "word": w})
                elif exempt:
                    exempt_hits.append({"line": i, "word": w})
                else:
                    code_hits.append({"line": i, "word": w})
    text = "\n".join(lines)
    for w in required:
        if w not in text:
            req_missing.append(w)
    return {
        "file": path,
        "code_hits": code_hits,
        "comment_hits": comment_hits,
        "exempt_hits": exempt_hits,
        "required_missing": req_missing,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    # ⚠️ Windows 下重定向到文件时默认 GBK，emoji（✅❌⚠️）会 UnicodeEncodeError。
    #    统一强制 UTF-8，且把 emoji 换成 ASCII 记号（对管道/日志更友好）。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    rows, fails = [], 0
    print("=" * 78)
    for path, required in TARGETS:
        r = scan(path, required)
        rows.append(r)
        if "error" in r:
            print("[FAIL] %-34s %s" % (path, r["error"]))
            fails += 1
            continue
        bad_code = len(r["code_hits"])
        miss = len(r["required_missing"])
        if bad_code or miss:
            fails += 1
        tag = "[OK]  " if not (bad_code or miss) else "[FAIL]"
        print("%s  %-34s 代码冲突 %d / 注释 %d / 豁免 %d / 缺失关键词 %d"
              % (tag, path, bad_code, len(r["comment_hits"]),
                 len(r["exempt_hits"]), miss))
        for h in r["code_hits"]:
            print("        [X] L%-4d 代码行含「%s」" % (h["line"], h["word"]))
        for w in r["required_missing"]:
            print("        [X] 缺关键词「%s」" % w)
        if r["comment_hits"] or r["exempt_hits"]:
            allowed = sorted({h["word"] for h in r["comment_hits"] + r["exempt_hits"]})
            print("        [!] 允许出现（注释/引述历史/其他幕）：%s" % allowed)
    print("-" * 78)
    print("结论：%s（%d/%d 个文件通过）"
          % ("[OK] 全部一致" if fails == 0 else "[FAIL] 有不一致，见上",
             len(TARGETS) - fails, len(TARGETS)))

    if args.json:
        out = os.path.join(ROOT, args.json)
        json.dump({"fails": fails, "rows": rows}, open(out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("报告 → %s" % args.json)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
