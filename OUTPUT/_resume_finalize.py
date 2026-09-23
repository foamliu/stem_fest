# -*- coding: utf-8 -*-
"""收尾断点续跑：只补做「昨晚被强杀时尚未完成」的镜头。

背景（2026-09-14 → 09-15）
    主生成 126 镜于 09-14 21:55 全部完成；`_finalize_all.py` 21:57 开始收尾，
    完成 4/5/19/39 四镜后，在**镜 45 生成中途**被人工强杀（为了睡觉）。
    ComfyUI 的 SaveVideo 会自动递增 `_00002_`/`_00003_` 后缀，
    所以「重跑同一命令」不会覆盖旧版，重跑版天然可区分。

本脚本做的事
    1. **幂等**：按 `--steps` 对应的目标版本号判断某镜是否已完成，
       已完成的直接跳过（不会重复烧机时）。
    2. **严格串行**：一批跑完再起下一批（README §6.1 #8：并行会引发
       11.96 GB 模型反复重载，总耗时翻倍）。
    3. **断点可续**：中途 Ctrl-C / 关机后，再跑一次即可从断点继续。
    4. **完成即记账**：写 `_resume_state.txt`，与 `_finalize_state.txt` 分开，
       不污染原有记录。

用法：
    py -3.10 OUTPUT/_resume_finalize.py            # 续跑全部未完成项
    py -3.10 OUTPUT/_resume_finalize.py --list      # 只看还差哪些镜
    py -3.10 OUTPUT/_resume_finalize.py --only=REDO # 只跑 B 类（元信息修复）
"""
import glob
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")
STATE = os.path.join(OUT, "_resume_state.txt")

# 各幕产物目录（镜号 → 目录名不是顺序，必须显式列出）
ACTS = {
    "_diag_act0_plane.py": "01_paper_plane",
    "_diag_act1_trench.py": "06_trench",
    "_diag_act2_startup.py": "03_classroom_day",
    "_diag_act3_rice.py": "07_rice_field",
    "_diag_act4_train.py": "08_train_dining",
    "_diag_act5_finale.py": "05_classroom_night",
}

# ── A. 环境剧变镜提步数（治闪烁/糊）──
STEP_UP = [
    ("_diag_act0_plane.py", 20, [4, 5]),          # 已完成
    ("_diag_act1_trench.py", 20, [19, 39, 45]),   # 19/39 已完成，45 被杀
    ("_diag_act4_train.py", 20, [75, 104]),       # 未跑
    ("_diag_act2_startup.py", 20, [18]),          # 白光吞没教室，未跑
    ("_diag_act3_rice.py", 20, [74]),             # 泛白转场，未跑
]

# ── B. prompt 元信息修复后必须重跑（否则画面出现不该有的字幕）──
REDO = [
    ("_diag_act0_plane.py", 10, [6]),
    ("_diag_act1_trench.py", 10, [23, 33, 38, 43]),
    ("_diag_act3_rice.py", 10, [52]),
    ("_diag_act4_train.py", 10, [91, 94, 96]),
]

# ── C. 纯字幕/静帧/定格镜降步数（省机时）──
STEP_DOWN = [
    ("_diag_act5_finale.py", 4, [123, 124, 125, 126]),
]


def log(msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        print(line.encode("ascii", "replace").decode(), flush=True)
    with open(STATE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def versions(script, shot):
    """返回该镜在产物目录里的所有 `_000NN_` 序号集合。"""
    d = os.path.join(OUT, ACTS[script], "video")
    v = set()
    for f in glob.glob(os.path.join(d, "%02d_*.mp4" % shot)):
        m = re.search(r"_(\d{5})_\.mp4$", os.path.basename(f))
        if m:
            v.add(int(m.group(1)))
    return v


def done(script, shot):
    """该镜是否已有「重跑版」（序号 >= 2）。

    注意：镜 10-17 的 _00002_ 是**主生成阶段**第一幕调优留下的，
    对本脚本而言同样算「已重做过」，因此一并跳过 —— 它们的 prompt
    未在元信息修复清单里，无需二次重跑。
    """
    return any(n >= 2 for n in versions(script, shot))


def run(script, steps, shots, tag):
    log("-" * 66)
    log(">> %s  %s  steps=%d  镜 %s" % (tag, script, steps, shots))
    cmd = [sys.executable, os.path.join(OUT, script),
           "--steps=%d" % steps] + [str(s) for s in shots]
    lf = os.path.join(OUT, "_resume_%s_%s.log" % (tag, script[9:13]))
    t0 = time.time()
    with open(lf, "wb") as f:
        rc = subprocess.Popen(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT,
                              env=dict(os.environ, PYTHONIOENCODING="utf-8")).wait()
    dt = (time.time() - t0) / 60.0
    txt = ""
    try:
        txt = open(lf, encoding="utf-8", errors="replace").read()
    except Exception:
        pass
    ok = txt.count("[OK]")
    bad = len([l for l in txt.splitlines()
               if "[X]" in l or "SUSPECT" in l or "MISSING" in l or "EXCEPTION" in l])
    log("<< %s rc=%d  %.1f 分  OK=%d 异常=%d  日志=%s" % (
        tag, rc, dt, ok, bad, os.path.basename(lf)))
    return rc


def main():
    only = None
    for a in sys.argv[1:]:
        if a.startswith("--only="):
            only = a.split("=", 1)[1].upper()
    list_only = "--list" in sys.argv[1:]

    groups = [("STEPUP", STEP_UP), ("REDO", REDO), ("STEPDOWN", STEP_DOWN)]
    if only:
        groups = [g for g in groups if g[0] == only]

    # 计算待办
    plan = []
    skipped = []
    for tag, items in groups:
        for script, steps, shots in items:
            todo = []
            for s in shots:
                if done(script, s):
                    skipped.append((tag, s))
                else:
                    todo.append(s)
            if todo:
                plan.append((tag, script, steps, todo))

    log("=" * 66)
    log("收尾断点续跑" + ("（只跑 %s）" % only if only else ""))
    log("已跳过（已有重跑版）：%s" % (
        ", ".join("%s%d" % (t[0], s) for t, s in skipped) or "无"))
    if not plan:
        log("没有待办，收尾已完成")
        return 0
    total = sum(len(x[3]) for x in plan)
    log("待办 %d 批 / %d 镜：" % (len(plan), total))
    est = 0.0
    for tag, script, steps, shots in plan:
        per = 17.0 if steps >= 20 else (8.5 if steps >= 10 else 3.5)
        est += per * len(shots)
        log("   %-9s %-24s steps=%-3d 镜 %-22s 预计 %.0f 分/镜" % (
            tag, script, steps, shots, per))
    log("预计总耗时 %.0f 分（%.1f 小时）" % (est, est / 60.0))

    if list_only:
        return 0

    for tag, script, steps, shots in plan:
        run(script, steps, shots, tag)

    log("=" * 66)
    log("续跑完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
