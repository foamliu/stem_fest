# -*- coding: utf-8 -*-
"""场景换图重跑驱动器（2026-09-21）—— 无人值守连续跑 89 镜 ≈ 14 小时。

任务来源
    `OUTPUT/_scene_rerun.json`（由 `_plan_scene_rerun.py` 生成，
    判据 = 产物 mtime < 该幕场景图 mtime）

与 `_run_rerun.py` 的区别（为什么另写一个）
    1. **任务来源不同**：那个读 `_rerun_list.json`（prompt 污染），
       这个读 `_scene_rerun.json`（场景换图）。
    2. **必须无人值守**：用户交代「我去上班，晚 6 点前遇到问题自己决定」⇒
       单镜失败**不能中止整批**，要记下来继续跑下一镜。
    3. **单镜粒度**：按幕批量调用时，一旦**进程级**崩溃（OOM / ComfyUI 断连），
       该幕剩余镜全部丢失；单镜粒度把损失限制在 1 镜。
    4. **逐镜断点**：状态写 `_scene_rerun_state.json`，按 (幕脚本, 镜) 记账，
       父进程被杀 / 关机后重跑本脚本即可续。

串行铁律（README §6.1 #8）
    H3 模型 11.96GB，16GB 显存下**不能并行** ⇒ 本脚本严格一次一镜。

用法：
    py -3.10 OUTPUT/_run_scene_rerun.py --dry        # 只看计划
    py -3.10 OUTPUT/_run_scene_rerun.py              # 跑（可反复运行，自动续）
    py -3.10 OUTPUT/_run_scene_rerun.py --only=act2  # 只跑某一幕（按脚本名匹配）
    py -3.10 OUTPUT/_run_scene_rerun.py --retry      # 把已标记失败的镜重新纳入
"""
import glob
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")
PLAN = os.path.join(OUT, "_scene_rerun.json")
STATE = os.path.join(OUT, "_scene_rerun_state.json")
LOG = os.path.join(OUT, "_scene_rerun.log")

# 各幕 steps（★ 必须与「最后一次定案」一致，不可随意改）
#   act2 = 20（2026-09-13 用户指令：本幕用 20 步重做）
#   其余 = 10（README §7「steps 选择」表的角色镜抽卡档）
STEPS = {
    "_diag_act0_plane.py": 10,
    "_diag_act1_trench.py": 10,
    "_diag_act2_startup.py": 20,
    "_diag_act3_rice.py": 10,
    "_diag_act4_train.py": 10,
    "_diag_act5_finale.py": 10,
}

# 执行顺序：短的幕先跑（先拿到可验收的成品），长的幕后跑。
#   理由：无人值守时万一中途被中止，先完成的幕是**完整可用**的。
ORDER = ["_diag_act2_startup.py", "_diag_act5_finale.py", "_diag_act3_rice.py",
         "_diag_act4_train.py", "_diag_act1_trench.py", "_diag_act0_plane.py"]

# 单镜超时（秒）。act2 steps=20 实测 18-26 分钟，给 60 分钟余量。
TIMEOUT = {"_diag_act2_startup.py": 3600}
DEFAULT_TIMEOUT = 2400

# 幕脚本 → 产物目录（权威表）
OUTDIR = {
    "_diag_act0_plane.py": "01_paper_plane",
    "_diag_act1_trench.py": "06_trench",
    "_diag_act2_startup.py": "03_classroom_day",
    "_diag_act3_rice.py": "07_rice_field",
    "_diag_act4_train.py": "08_train_dining",
    "_diag_act5_finale.py": "05_classroom_night",
}


def log(msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        print(line.encode("ascii", "replace").decode(), flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"done": [], "fail": {}}


def save_state(st):
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)


def _fresh_output(script, shot, t0):
    """该镜当前最新产物 + 是否早于 t0 就存在过（补零三种都试）。

    返回 (path, preexisting)。判定成功的依据见 `_verdict`。
    """
    act = OUTDIR.get(script)
    if not act:
        return None, True
    vd = os.path.join(OUT, act, "video")
    best, bt = None, 0.0
    n_before = 0
    for pat in ("%d_*.mp4" % shot, "%02d_*.mp4" % shot, "%03d_*.mp4" % shot):
        for f in glob.glob(os.path.join(vd, pat)):
            b = os.path.basename(f)
            if b.startswith("_bak_") or re.search(r"_(delogo|temporal|split)\.mp4$", b):
                continue
            m = os.path.getmtime(f)
            if m < t0:
                n_before += 1
            if m > bt:
                best, bt = f, m
    return best, (n_before == 0)


def _comfy_ok(out):
    """脚本自己打印的 `[OK] <file>` 行（ComfyUI 产物复制的成功回执）。"""
    for ln in out.splitlines():
        if "[OK]" in ln:
            return ln.strip()[:220]
    return None


def _first_bad(out):
    """从脚本输出里捞首个失败标记（脚本自己打的 [X] / SUSPECT / 异常）。"""
    for ln in out.splitlines():
        if ("[X]" in ln or "SUSPECT" in ln or "MISSING_REF" in ln
                or "SUBMIT_FAIL" in ln or "EXCEPTION" in ln or "执行报错" in ln):
            return ln.strip()[:220]
    return None


def _verdict(out, t0, fresh, preexisting):
    """判定本次执行是否成功。返回 (ok: bool, detail: str)。

    ★ 为什么不能只看「有无新文件」（2026-09-21 实测踩坑）：
      ComfyUI **对完全相同的 workflow 有缓存** —— prompt 一字未改时，
      `/prompt` 立刻回一个已完成的结果（日志里表现为 `0 s`、`排队=0`），
      **不产生新文件**。此时若只查「mtime > t0 的新文件」，会把一次**成功**误判为失败。
      实测：镜 10 烟测成功后，总控重跑同一条命令被判 `rc=0 且无新产物` —— 假失败。

    判定顺序（越靠前越可信）：
      1. 脚本打印了 `[OK] <file>` 且**无**失败标记        → 成功（缓存命中或新产物）
      2. 出现了 mtime > t0 的新文件                      → 成功
      3. 有失败标记（[X] / SUSPECT / EXCEPTION …）        → 失败
      4. 否则视为失败（既没回执、也没新文件）
    """
    bad = _first_bad(out)
    okline = _comfy_ok(out)
    if okline and not bad:
        return True, okline
    if fresh and preexisting is False:
        return True, os.path.basename(fresh)
    if bad:
        return False, bad
    return False, "既无 [OK] 回执、也无新产物"


def main():
    dry = "--dry" in sys.argv
    retry = "--retry" in sys.argv
    only = None
    for a in sys.argv[1:]:
        if a.startswith("--only="):
            only = a.split("=", 1)[1]

    if not os.path.exists(PLAN):
        log("!! 找不到计划 %s，先跑 py -3.10 OUTPUT/_plan_scene_rerun.py" % PLAN)
        return 2
    with open(PLAN, encoding="utf-8") as f:
        plan = json.load(f)

    st = load_state()
    if retry:
        log("--retry：清空失败记录 %s" % list(st["fail"].keys()))
        st["fail"] = {}
    done = set(st.get("done", []))

    todo = []
    for script in ORDER:
        shots = plan.get(script) or []
        if only and only not in script:
            continue
        for s in sorted(shots):
            key = "%s:%d" % (script, s)
            if key in done:
                continue
            todo.append((script, s, key))

    log("=" * 72)
    log("场景换图重跑（%d 镜待跑 / 计划 %d 镜 / 已完成 %d 镜）%s" % (
        len(todo), sum(len(v) for v in plan.values()), len(done),
        " DRY" if dry else ""))
    log("=" * 72)

    if dry:
        for script, s, _ in todo:
            log("  py -3.10 OUTPUT/%s --steps=%d %d" % (script, STEPS[script], s))
        return 0

    ok_n, fail_n = 0, 0
    for i, (script, shot, key) in enumerate(todo, 1):
        steps = STEPS[script]
        tmo = TIMEOUT.get(script, DEFAULT_TIMEOUT)
        log("")
        log("### [%d/%d] %s  镜 %d  steps=%d" % (i, len(todo), script, shot, steps))
        cmd = [sys.executable, os.path.join(OUT, script),
               "--steps=%d" % steps, str(shot)]
        t0 = time.time()
        try:
            r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=tmo)
            rc, out = r.returncode, (r.stdout or "") + (r.stderr or "")
        except subprocess.TimeoutExpired:
            rc, out = -9, "TIMEOUT after %ds" % tmo
        dt = (time.time() - t0) / 60.0

        # ★ 判定成功的硬标准：脚本回了 `[OK]` **或** 产物目录出现了晚于启动时刻的 mp4。
        #   只看 returncode 不可靠（脚本内部 catch 了异常仍可能 rc=0），
        #   只看新文件也不可靠（ComfyUI 命中缓存时不产生新文件，见 `_verdict`）。
        fresh, preexisting = _fresh_output(script, shot, t0)
        ok, detail = _verdict(out, t0, fresh, preexisting)
        if ok:
            done.add(key)
            st["done"] = sorted(done)
            st["fail"].pop(key, None)
            ok_n += 1
            log("   OK（%.1f 分钟）  %s" % (dt, detail))
        else:
            fail_n += 1
            st["fail"][key] = {"why": detail,
                               "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                               "min": round(dt, 1)}
            log("   FAIL（%.1f 分钟）  %s" % (dt, detail))
            for ln in out.strip().splitlines()[-6:]:
                log("      | %s" % ln[:200])
        save_state(st)

    log("")
    log("=" * 72)
    log("本轮完成 OK=%d  FAIL=%d  累计 done=%d  fail=%d" % (
        ok_n, fail_n, len(st["done"]), len(st["fail"])))
    if st["fail"]:
        for k, v in sorted(st["fail"].items()):
            log("   FAIL %s  %s" % (k, v["why"]))
        log("   ⇒ 修复后用 --retry 重跑这些镜")
    log("=" * 72)
    return 0 if not st["fail"] else 1


if __name__ == "__main__":
    sys.exit(main())
