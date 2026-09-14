# -*- coding: utf-8 -*-
"""诊断第二幕脚本：列出 TASKS 镜号 ↔ slug，并与 storyboard 47-74 对照。"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = io.open(os.path.join(ROOT, "OUTPUT", "_diag_act3_rice.py"), encoding="utf-8").read()

# storyboard 第二幕 47-74 的 slug 线索（画面关键词 → 比对用）
SB = {
    47: "田埂远景/四人看袁隆平/热死了",
    48: "徐畅景手搭凉棚/安江农校",
    49: "刘思齐往田埂边缩",
    50: "袁隆平弯腰看稻穗/汗滴",
    51: "刘思成盯着看/一株一株地找",
    52: "袁隆平蹲下拨开稻叶/眼睛亮了",
    53: "袁隆平抚摸稻穗/找到了",
    54: "袁隆平直起腰招手/过来嘛",
    55: "四人走过去/拔普通稻子",
    56: "袁隆平指系布条的稻穗/找了三年",
    57: "张书扬凑近看/就为了一株稻子",
    58: "袁隆平问/吃饭了没",
    59: "刘思齐小声答/吃了",
    60: "袁隆平/见过饿倒的人",
    61: "刘思成脱口而出/袁爷爷",
    62: "袁隆平愣/你叫我啥子",
    63: "刘思成坦白/从未来来",
    64: "袁隆平沉默看稻子看孩子",
    65: "袁隆平问/能吃饱了",
    66: "刘思齐点头掉泪/能吃饱了",
    67: "袁隆平笑了/接着找",
    68: "徐畅景问/还要找多久",
    69: "袁隆平/找到找不动为止",
    70: "张书扬/禾下乘凉梦",
    71: "袁隆平眼睛亮/活到那时候",
    72: "摘稻谷放刘思齐手心",
    73: "转身走进稻田/背影",
    74: "四人站在原地/白屏日记字",
}

got = [(int(m.group(1)), m.group(2))
       for m in re.finditer(r'TASKS\[(\d+)\] = dict\(\s*slug="([^"]+)"', src)]

print("脚本共 %d 个 TASKS（镜号 %d-%d）" % (len(got), got[0][0], got[-1][0]))
print()
print("脚本镜号  slug                               storyboard 内容对照")
print("-" * 100)
for i, (n, slug) in enumerate(got):
    sb = SB.get(n - 5, "") if n >= 52 else ""
    print("%3d  %-40s %s" % (n, slug, sb))
