# -*- coding: utf-8 -*-
"""全片收尾：等编排器跑完后，自动补跑「需要重做 / 需要提步数」的镜头。

三类镜头：
  A. **prompt 元信息修复后的镜**（2026-09-14 修了 14 处「像在…/本镜/暗示…」写法，
     其中镜 91 曾把舞台指示渲染成画面字幕）⇒ 必须用新 prompt 重跑
  B. **环境剧变镜提步数**（4→10→20 那档）⇒ 提质量
  C. **纯字幕/静帧/定格镜降步数**（省机时，画面几乎不动）

本脚本**先等编排器退出**（轮询 py.exe 命令行），再串行执行补跑，互不抢 GPU。
"""
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── A. prompt 修复后必须重跑（用各幕原 steps）──
REDO = [
    ("_diag_act0_plane.py", 10, [6]),
    ("_diag_act2_startup.py", 20, [10, 16]),
    ("_diag_act1_trench.py", 10, [19, 23, 33, 38, 43]),
    ("_diag_act3_rice.py", 10, [52]),
    ("_diag_act4_train.py", 10, [91, 94, 96]),
]

# ── B. 环境剧变镜提步数（覆盖上面的同镜，取更高 steps）──
STEP_UP = [
    ("_diag_act0_plane.py", 20, [4, 5]),
    ("_diag_act1_trench.py", 20, [19, 39, 45]),
    ("_diag_act4_train.py", 20, [75, 104]),
    ("_diag_act2_startup.py", 20, [18]),      # 白光吞没教室
    ("_diag_act3_rice.py", 20, [74]),         # 泛白转场
]

# ── C. 纯字幕/静帧/定格镜降步数（省机时）──
STEP_DOWN = [
    ("_diag_act5_finale.py", 4, [123, 124, 125, 126]),
]

STATE = os.path.join(ROOT, "OUTPUT", "_finalize_state.txt")


def log(msg):
    msg = msg.replace("✓", "[OK]").replace("✗", "[X]").replace("▶", ">>").replace("◀", "<<")
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        print(line.encode("ascii", "replace").decode(), flush=True)
    with open(STATE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def orchestrator_alive():
    """编排器是否还在跑（命令行含 _run_all_acts）。"""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='py.exe'\" | "
             "Where-Object { $_.CommandLine -like '*_run_all_acts*' } | "
             "Measure-Object | Select-Object -ExpandProperty Count"],
            capture_output=True, timeout=60, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        n = int((out.stdout or b"0").decode("utf-8", "replace").strip() or 0)
        return n > 0
    except Exception:
        return False


def wait_orchestrator(timeout_h=8.0):
    t0 = time.time()
    log("等待编排器 _run_all_acts.py 结束（最多 %.1f 小时）" % timeout_h)
    last = ""
    while time.time() - t0 < timeout_h * 3600:
        if not orchestrator_alive():
            log("编排器已退出，开始收尾补跑")
            return True
        el = time.time() - t0
        line = "  仍在跑… 已等 %.0f 分" % (el / 60.0)
        if line != last:
            log(line)
            last = line
        time.sleep(120)
    log("等待超时，放弃收尾")
    return False


def run(script, steps, shots, tag):
    log("-" * 66)
    log(">> %s：%s  steps=%d  镜 %s" % (tag, script, steps, shots))
    cmd = [sys.executable, os.path.join(ROOT, "OUTPUT", script),
           "--steps=%d" % steps] + [str(s) for s in shots]
    lf = os.path.join(ROOT, "OUTPUT", "_finalize_%s_%s.log" % (tag, script[6:12]))
    t0 = time.time()
    with open(lf, "wb") as f:
        rc = subprocess.Popen(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT,
                              env=dict(os.environ, PYTHONIOENCODING="utf-8")).wait()
    dt = (time.time() - t0) / 60.0
    try:
        txt = open(lf, encoding="utf-8", errors="replace").read()
        ok = txt.count("[OK]")
        bad = len([l for l in txt.splitlines()
                   if "[X]" in l or "SUSPECT" in l or "MISSING" in l])
        log("<< %s rc=%d  %.1f 分  OK=%d 异常=%d  日志=%s" % (
            tag, rc, dt, ok, bad, os.path.basename(lf)))
    except Exception:
        log("<< %s rc=%d  %.1f 分（读日志失败）" % (tag, rc, dt))


def main():
    skip_wait = "--now" in sys.argv
    log("=" * 66)
    log("全片收尾启动（prompt 修复重跑 + 步数调优）")
    if not skip_wait and not wait_orchestrator():
        return 1

    # 顺序：先 B（提步数，含与 A 重叠的镜），再 A 的其余镜，最后 C
    done = set()
    for script, steps, shots in STEP_UP:
        run(script, steps, shots, "STEPUP")
        done |= set((script, s) for s in shots)

    todo = {}
    for script, steps, shots in REDO:
        rest = [s for s in shots if (script, s) not in done]
        if rest:
            todo.setdefault((script, steps), []).extend(rest)
    for (script, steps), shots in todo.items():
        run(script, steps, sorted(shots), "REDO")

    for script, steps, shots in STEP_DOWN:
        run(script, steps, shots, "STEPDOWN")

    log("=" * 66)
    log("收尾完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
