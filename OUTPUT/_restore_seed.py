# -*- coding: utf-8 -*-
"""自检 + 恢复：确认 act2 的 TASKS[14].seed 是否被 _seed_override 残留污染。"""
import hashlib
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACT2 = os.path.join(ROOT, "OUTPUT", "_diag_act2_startup.py")
TMP = ACT2 + ".seedtmp.bak"
PAT = r'TASKS\[14\]\s*=\s*dict\(\s*\n\s*slug="[^"]+",\s*seed=(\d+)'


def seed_of(p):
    m = re.search(PAT, open(p, encoding="utf-8").read())
    return m.group(1) if m else None


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()[:12]


print("当前脚本 TASKS[14].seed =", seed_of(ACT2))
print("当前脚本 md5 =", md5(ACT2))
if os.path.exists(TMP):
    print("临时备份存在，其 seed =", seed_of(TMP), "md5 =", md5(TMP))
    if seed_of(TMP) == "9614":
        print("→ 临时备份是干净版（seed=9614），正在恢复…")
        import shutil
        shutil.copy2(TMP, ACT2)
        os.remove(TMP)
        print("已恢复。当前 seed =", seed_of(ACT2), "md5 =", md5(ACT2))
    else:
        print("→ 临时备份 seed 也不对，需人工检查")
else:
    print("无临时备份（已还原或从未创建）")
    if seed_of(ACT2) != "9614":
        print("!! 但当前 seed 不是 9614 → 需人工修回")
