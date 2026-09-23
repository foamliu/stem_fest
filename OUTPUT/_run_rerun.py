# -*- coding: utf-8 -*-
"""批量重跑「污染修复镜」—— 按幕分组、逐镜串行，带断点续跑。

为什么必须**串行**
    README §6.1 #8：H3 模型 11.96GB，16GB 显存下**不能并行**（会 OOM 或 swap）。
    本脚本一次只提交一个幕的一条命令，幕内由 diag 脚本自己逐镜串行。

为什么按「幕」而不是「逐镜」调用
    每个 diag 脚本启动时会 `import + 加载 workflow JSON`，逐镜调用会反复付这个开销。
    按幕批量调用（如 `_diag_act0_plane.py 4 5 9`）只付一次。

断点续跑
    状态写 OUTPUT/_rerun_state.txt；重跑前先查该镜是否已有**新版**
    （mtime > 本脚本启动时刻的记录），有则跳过。

用法：
    py -3.10 OUTPUT/_run_rerun.py --dry              # 只看计划
    py -3.10 OUTPUT/_run_rerun.py                    # 跑全部 41 镜
    py -3.10 OUTPUT/_run_rerun.py --steps=10         # 指定步数（默认 10）
    py -3.10 OUTPUT/_run_rerun.py --only=P1          # 只跑 P1
"""
import glob
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")
LIST = os.path.join(OUT, "_rerun_list.json")
STATE = os.path.join(OUT, "_rerun_state.txt")

# 优先级 → 幕脚本（顺序即执行顺序：P1 先跑，最快见到修复效果）
TIER_FILES = {
    "P1 否定式残留新修": "_diag_act5_finale.py",
    "P2 NO_SPEECH 引用": None,      # 跨 5 幕，见下
    "P3 元信息旧视频": "_diag_act4_train.py",
}

# ★ 镜号 → 幕脚本：从 _shot_refs.json 自动读，避免手写映射与清单不同步
#   （2026-09-15 教训：手写映射漏了 P2 的镜 16、P3 的镜 10）
SCRIPTS = ["_diag_act0_plane.py", "_diag_act1_trench.py", "_diag_act2_startup.py",
           "_diag_act3_rice.py", "_diag_act4_train.py", "_diag_act5_finale.py"]


def shots_by_script(need):
    """按幕脚本归组需要重跑的镜号。"""
    refs_path = os.path.join(OUT, "_shot_refs.json")
    refs = json.load(open(refs_path, encoding="utf-8"))
    by = {}
    missed = []
    for n in need:
        v = refs.get(str(n))
        if not v:
            missed.append(n)
            continue
        by.setdefault(v["script"], []).append(n)
    if missed:
        log("!! 清单里这些镜在 _shot_refs.json 中找不到幕归属：%s" % missed)
    return {k: sorted(v) for k, v in by.items()}


def tier_label(key):
    """把 JSON 的 key（如 'P1 否定式残留新修'）映射成短标签。"""
    return key.split()[0] if key and key[0] == "P" else key


def log(msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    with open(STATE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ★ 重跑基准时刻：只认「比这个时间新」的产物才算"刚重跑过"。
#   不能简单用「24 小时内」——昨晚 21:55 的**污染版**也在 24h 内，会误判为"已完成"。
#   基准由 `_resume_rerun.py` 在开跑时写入 `_rerun_baseline.txt`（epoch 秒）。
BASELINE_FILE = os.path.join(OUT, "_rerun_baseline.txt")


def _baseline():
    """读重跑基准时刻（epoch 秒）。文件不存在则返回"现在"（即不跳过任何镜）。"""
    try:
        return float(open(BASELINE_FILE, encoding="utf-8").read().strip())
    except Exception:
        return time.time()


def already_done(script, shots, since_hours=None):
    """跳过「**本次重跑**已产出过新版」的镜（防重复重跑烧 GPU）。

    判据：该镜在 `<幕>/video/` 下存在 mtime **晚于本次重跑基准时刻**的 mp4。
    ⚠️ 基准是"本次重跑开始的时刻"，不是"24 小时内"——
       否则会把昨晚的污染版误判成已完成（2026-09-15 踩过，白等 20 分钟）。
    """
    keep, done = [], []
    # 幕脚本 → 输出目录（权威表，与 _coverage.py 保持一致）
    OUTDIR = {
        "_diag_act0_plane.py": "01_paper_plane",
        "_diag_act1_trench.py": "06_trench",
        "_diag_act2_startup.py": "03_classroom_day",
        "_diag_act3_rice.py": "07_rice_field",
        "_diag_act4_train.py": "08_train_dining",
        "_diag_act5_finale.py": "05_classroom_night",
    }
    cutoff = _baseline()
    for s in shots:
        act = OUTDIR.get(script)
        if not act:
            keep.append(s)
            continue
        # ⚠️ 文件名里镜号**可能补零**（01_paper_plane 用 "%02d"，其余用 "%d"）
        #    ⇒ 两种都试，否则 1–9 号镜永远匹配不到（2026-09-15 踩过）
        fs = (glob.glob(os.path.join(OUT, act, "video", "%d_*.mp4" % s)) +
              glob.glob(os.path.join(OUT, act, "video", "%02d_*.mp4" % s)) +
              glob.glob(os.path.join(OUT, act, "video", "%03d_*.mp4" % s)))
        if fs and max(os.path.getmtime(f) for f in fs) > cutoff:
            done.append(s)
        else:
            keep.append(s)
    if done:
        log("   跳过本次已重跑：%s" % done)
    return sorted(keep)


def main():
    dry = "--dry" in sys.argv
    steps = 10
    only = None
    for a in sys.argv[1:]:
        if a.startswith("--steps="):
            steps = int(a.split("=", 1)[1])
        elif a.startswith("--only="):
            only = a.split("=", 1)[1].upper()

    batches = []
    for key, shots in json.load(open(LIST, encoding="utf-8")).items():
        tag = tier_label(key)
        if tag not in ("P1", "P2", "P3"):
            continue                    # P4 不跑
        if only and tag != only:
            continue
        batches.append((key, shots_by_script(shots)))

    total = sum(len(v) for _, d in batches for v in d.values())
    log("=" * 66)
    log("批量重跑修复镜（steps=%d%s）—— 合计 %d 镜" % (
        steps, " DRY" if dry else "", total))
    for name, d in batches:
        n = sum(len(v) for v in d.values())
        log("  %-26s %2d 镜" % (name, n))
    log("=" * 66)

    if dry:
        for name, d in batches:
            log("[%s]" % name)
            for scr, shots in sorted(d.items()):
                log("    py -3.10 OUTPUT/%s --steps=%d %s" % (
                    scr, steps, " ".join(str(s) for s in sorted(shots))))
        return 0

    done, fail = 0, []
    for name, d in batches:
        log("")
        log("### %s" % name)
        for scr, shots in sorted(d.items()):
            shots = sorted(shots)
            shots = already_done(scr, shots)        # 跳过刚跑过的，防重复烧 GPU
            if not shots:
                log("   全部已重跑过，跳过 %s" % scr)
                continue
            cmd = ["py", "-3.10", os.path.join("OUTPUT", scr),
                   "--steps=%d" % steps] + [str(s) for s in shots]
            log(">> %s  镜 %s" % (scr, shots))
            t0 = time.time()
            r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            dt = (time.time() - t0) / 60.0
            if r.returncode == 0:
                done += len(shots)
                log("   OK（%.1f 分钟）" % dt)
            else:
                fail.append((scr, shots))
                log("   FAIL rc=%d（%.1f 分钟）" % (r.returncode, dt))
                tail = (r.stdout or "")[-400:]
                log("   tail: %s" % tail.replace("\n", " | "))

    log("")
    log("=" * 66)
    log("完成 %d/%d 镜；失败批次 %d 个" % (done, total, len(fail)))
    for scr, shots in fail:
        log("   FAIL %s %s" % (scr, shots))
    log("=" * 66)
    return 0 if not fail else 1


if __name__ == "__main__":
    sys.exit(main())
