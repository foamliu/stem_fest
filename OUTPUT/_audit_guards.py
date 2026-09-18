# -*- coding: utf-8 -*-
"""★ 逐幕审计：列出每个镜的 slug / seed / 是否有 NO_TEXT_SCENE / 是否宽景，
   用于判断"哪些镜可能像镜 104 那样自发渲染场景 UI 文字"。

用法：
    py -3.10 OUTPUT/_audit_guards.py            # 全部 diag 脚本
    py -3.10 OUTPUT/_audit_guards.py --wide     # 只列宽景（全景/中景）且无禁令的
"""
from __future__ import annotations
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = ["_diag_act0_plane.py", "_diag_act1_trench.py", "_diag_act2_startup.py",
           "_diag_act3_rice.py", "_diag_act4_train.py", "_diag_act5_finale.py"]
PAT = re.compile(r"TASKS\[(\d+)\]\s*=\s*dict\(\s*\n\s*slug=\"([^\"]+)\",\s*seed=(\d+)")

# ★ 风险载体（README §6.10.12）：这些**场景元素**才会让 H3 自发补文字。
#   不是"宽景就危险"，而是"画面里有**信息承载面**才危险"——
#   屏幕 / 告示牌 / 海报 / 文件 / 笔 / 包装 / 招牌 / 桌牌 / 车厢端墙。
RISK = (
    "全息", "光幕", "屏幕", "投影", "电脑", "笔记本", "手机", "平板",  # 电子屏
    "文件", "纸", "笔", "打开", "翻开", "记录", "日记", "字卡",        # 纸面
    "车厢", "高铁", "餐车", "站台", "报站", "指示灯",                  # 车厢 UI
    "墙报", "海报", "标语", "黑板", "展板", "公告",                    # 墙面
    "口罩", "包装", "盒子", "箱子", "牌", "标签", "商标",              # 包装标识
)
# 已有禁令的镜（人工确认，见各 diag 脚本）
KNOWN_GUARDED = {104, 105, 15, 17, 18}



def bodies(text):
    out = []
    for m in PAT.finditer(text):
        end = text.find("\n)\n", m.start())
        out.append((int(m.group(1)), m.group(2), int(m.group(3)),
                    text[m.start():end if end > 0 else m.start() + 2500]))
    return out


def main():
    wide_only = "--wide" in sys.argv
    tot = risk_n = 0
    risky = []
    for s in SCRIPTS:
        p = os.path.join(HERE, s)
        if not os.path.exists(p):
            continue
        rows = bodies(io.open(p, encoding="utf-8").read())
        if not rows:
            continue
        for n, slug, seed, body in sorted(rows):
            guard = "NO_TEXT_SCENE" in body
            hit = [k for k in RISK if k in body]
            tot += 1
            if hit and not guard:
                risk_n += 1
                risky.append((s, n, slug, seed, hit))
    print("== **有文字载体风险且无全画面禁令** 的镜（镜 104 型）")
    for s, n, slug, seed, hit in risky:
        print("   %-4d %-40s seed=%-5d 载体=%s" % (n, slug, seed, ",".join(hit[:6])))
    print("\n合计 %d 镜；风险镜 %d" % (tot, risk_n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
