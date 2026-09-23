# -*- coding: utf-8 -*-
"""临时：验解析（幕后篇 spec + 台词拆分）。用完即删。py -3.10 OUTPUT/_dbg_sheet.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _make_comic as MC

info, panels = MC.parse_making_sheet(MC.SHEET_MD)
print("页标题：%s" % info.get("页标题"))
print("副标题：%s" % info.get("副标题"))
for p in panels:
    av = MC.parse_av({"n": p["i"], "av": p["av"], "pic": ""}, [])
    print("\n格 %d [%s] %s" % (p["i"], p["tag"], p["img"]))
    for w, t in av["bubbles"]:
        print("   气泡 %s（%d 字）：%s" % (w, len(t), t))
    for s in av["sfx"] + av["music"] + av["lyrics"]:
        print("   音效条：%s" % s)
    if av["narration"]:
        print("   旁白：%s %s" % (av["nlabel"], av["narration"]))
