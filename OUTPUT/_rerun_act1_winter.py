# -*- coding: utf-8 -*-
"""第一幕（上甘岭）批量重跑：把 21 个含战士的镜用**修正后的 prompt** 重生成。

★ 起因：用户指出「上甘岭这一战是在 10 月份，场景不对」⇒ 见 `_patch_act1_winter.py`
   与 `_fix_act1_wording.py`（已改 LIGHT + 挂 GUARD_SOLDIER_WINTER + 清灰蒙蒙措辞）。
   这些镜的**产物全部早于 prompt 修改**（09-14 ~ 09-18 产物 vs 09-19 prompt），
   即成片里仍是旧「灰蒙蒙 + 战士单衣」画面 ⇒ 必须重跑。

★ 重跑清单 = 脚本里实际挂了 `GUARD_SOLDIER_WINTER` 的镜
   （即"含志愿军战士"的 21 镜；由脚本自身反推，不写死，避免与 patch 结果脱节）。

★ 用法
    py -3.10 OUTPUT/_rerun_act1_winter.py --dry        # 只列清单 + 核对 prompt 已含新措辞
    py -3.10 OUTPUT/_rerun_act1_winter.py --run        # 真跑（后台，单镜 4-7 分钟）
    py -3.10 OUTPUT/_rerun_act1_winter.py --run 19 23  # 只跑指定镜

★ 为什么串行不并发：16GB VRAM 上 H3 单任务已占约 14GB，并发必 OOM
   （README §6.10.6⑥ E1）。ComfyUI 队列本身会串行，这里再显式串行一次更稳。
"""
import io
import importlib.util
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "OUTPUT", "_diag_act1_trench.py")
LOG = os.path.join(ROOT, "OUTPUT", "_rerun_act1_winter_log.txt")

# 反推重跑清单：脚本里挂了 GUARD_SOLDIER_WINTER 的镜
spec = importlib.util.spec_from_file_location("act1", SRC)
mod = importlib.util.module_from_spec(spec)
sys.modules["act1"] = mod
spec.loader.exec_module(mod)

raw = io.open(SRC, encoding="utf-8").read()

targets = sorted(n for n, t in mod.TASKS.items() if "冬季棉装" in t.get("prompt", ""))

# ── 前置闸门：每镜 prompt 必须 (a) 含新 LIGHT 措辞 (b) 含冬装护栏 (c) 不含旧「灰蒙蒙」
gate = []
for n in targets:
    p = mod.TASKS[n]["prompt"]
    ok_light = "深秋时节" in p
    ok_winter = "冬季棉装" in p
    ok_nogrey = "灰蒙蒙" not in p
    gate.append((n, ok_light, ok_winter, ok_nogrey))

print("=" * 70)
print("第一幕重跑清单（含志愿军战士的镜）：%s" % targets)
print("共 %d 镜" % len(targets))
bad = [g for g in gate if not all(g[1:])]
for n, a, b, c in gate:
    flag = "OK " if (a and b and c) else "!! "
    print("  %s镜 %-3d 新LIGHT=%s 冬装护栏=%s 无灰蒙蒙=%s" % (flag, n, a, b, c))
if bad:
    print("\n!! 闸门失败：%s —— 先修 prompt 再重跑" % [g[0] for g in bad])
    sys.exit(2)
print("\n闸门通过：全部 %d 镜的 prompt 均为修正后版本" % len(targets))

args = sys.argv[1:]
dry = "--dry" in args
run = "--run" in args
picked = [int(a) for a in args if a.isdigit()]
todo = picked if picked else targets

print("\n待跑：%s" % todo)
if dry or not run:
    print("\n（--dry / 未给 --run：不实际生成）")
    sys.exit(0)

log = io.open(LOG, "w", encoding="utf-8", newline="\n")
ok, fail = [], []
for i, n in enumerate(todo, 1):
    line = "[%d/%d] 镜 %d ..." % (i, len(todo), n)
    print(line, flush=True)
    log.write(line + "\n")
    log.flush()
    r = subprocess.run([sys.executable, SRC, str(n)],
                       cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    tail = (r.stdout or "").strip().splitlines()[-3:]
    log.write("\n".join(tail) + "\n\n")
    log.flush()
    if r.returncode == 0 and "OK" in (r.stdout or ""):
        ok.append(n)
        print("    OK", flush=True)
    else:
        fail.append(n)
        print("    FAIL rc=%s" % r.returncode, flush=True)

print("\n" + "=" * 70)
print("完成：成功 %d 镜 %s" % (len(ok), ok))
if fail:
    print("失败：%s" % fail)
print("日志：%s" % LOG)
log.close()
