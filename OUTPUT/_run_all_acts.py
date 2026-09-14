# -*- coding: utf-8 -*-
"""全片 126 镜批量生成编排器（后台串行跑 6 个幕级脚本）。

★ 为什么要编排：README §6.1 #8 的教训 —— 不能让多个脚本同时在队列里抢 GPU
  （曾发生两批任务交替执行、每个都重载 11.96 GB 模型 ⇒ 纯浪费）。
  本编排器**严格串行**：一幕跑完才启下一幕，并在每幕前后核对队列清零。

★★ 关键纪律（README §6.1 #8）：
   · 每幕开跑前先 `--dry` 核对镜数
   · 每幕跑完核对：子进程已退出 + ComfyUI 队列清零
   · 不同幕的输出前缀不同（act0vs / act2vs / act1vs…），便于区分

用法：
    py -3.10 OUTPUT/_run_all_acts.py --dry            # 只做 6 幕 dry 校验，不真跑
    py -3.10 OUTPUT/_run_all_acts.py                  # 串行跑完全片（数小时～十几小时）
    py -3.10 OUTPUT/_run_all_acts.py --only=act0      # 只跑某一幕
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMFY = "http://127.0.0.1:8188"

# (幕名, 脚本, steps, 额外参数)  —— 顺序即执行顺序
PLAN = [
    ("act0", "_diag_act0_plane.py",   10, []),
    ("act2", "_diag_act2_startup.py", 20, []),
    ("act1", "_diag_act1_trench.py",  10, []),
    ("act3", "_diag_act3_rice.py",    10, []),
    ("act4", "_diag_act4_train.py",   10, []),
    ("act5", "_diag_act5_finale.py",  10, []),
]

STATE = os.path.join(ROOT, "OUTPUT", "_run_all_state.txt")


def log(msg):
    """写日志。★ 只用 ASCII 标记 —— PS 5.1 的 stdout 是 GBK，
    写 '✓/✗/▶/◀' 这类符号会 UnicodeEncodeError（README §6.3 #2 同类坑）。"""
    msg = (msg.replace("✓", "[OK]").replace("✗", "[X]")
              .replace("▶", ">>").replace("◀", "<<")
              .replace("→", "->"))
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        print(line.encode("ascii", "replace").decode("ascii"), flush=True)
    with open(STATE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def queue_depth():
    try:
        with urllib.request.urlopen(COMFY + "/queue", timeout=10) as r:
            q = json.loads(r.read().decode("utf-8"))
        return len(q.get("queue_running") or []), len(q.get("queue_pending") or [])
    except Exception as e:
        return -1, -1


def main():
    args = sys.argv[1:]
    dry_only = "--dry" in args
    only = None
    for a in args:
        if a.startswith("--only="):
            only = a.split("=", 1)[1]

    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    if not dry_only:
        log("=" * 70)
        log("全片 126 镜批量生成启动")

    plan = [p for p in PLAN if only is None or p[0] == only]

    # ── 阶段一：全部 --dry 校验 ──
    log("阶段一：逐幕 --dry 校验")
    for name, script, steps, extra in plan:
        cmd = [sys.executable, os.path.join(ROOT, "OUTPUT", script), "--dry"] + extra
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        out = subprocess.run(cmd, capture_output=True, timeout=300, env=env)
        stdout = (out.stdout or b"").decode("utf-8", "replace")
        stderr = (out.stderr or b"").decode("utf-8", "replace")
        first = stdout.splitlines()
        head = first[0] if first else "(无输出)"
        m = re.search(r"shots=\[(\d+),.*?(\d+)\]", head)
        cnt = None
        if m:
            cnt = int(m.group(2)) - int(m.group(1)) + 1
        ok = out.returncode == 0 and cnt is not None
        log("  %-6s %-26s %s  镜数=%s" % (name, script, "✓" if ok else "✗ 失败", cnt))
        if not ok:
            log("     stderr: %s" % stderr[:300])
            return 1
    if dry_only:
        log("dry 校验完成（未真跑）")
        return 0

    # ── 阶段二：串行真跑 ──
    log("阶段二：串行真跑")
    t_all = time.time()
    for name, script, steps, extra in plan:
        log("-" * 70)
        log("▶ 开始 %s（%s, steps=%d）" % (name, script, steps))
        r0 = queue_depth()
        log("  开跑前队列 running/pending = %s" % (r0,))

        cmd = [sys.executable, os.path.join(ROOT, "OUTPUT", script),
               "--steps=%d" % steps] + extra
        logfile = os.path.join(ROOT, "OUTPUT", "_run_%s.log" % name)
        t0 = time.time()
        # ★ 子进程 stdout 强制 UTF-8：否则 PS 5.1 下子脚本 print 中文会 UnicodeEncodeError
        cenv = dict(os.environ, PYTHONIOENCODING="utf-8")
        with open(logfile, "wb") as lf:
            proc = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT,
                                    cwd=ROOT, env=cenv)
            log("  PID=%d  日志=%s" % (proc.pid, os.path.basename(logfile)))
            rc = proc.wait()
        dt = time.time() - t0

        # 跑完核对：进程已退出（wait 已保证）+ 队列清零
        time.sleep(10)
        r1 = queue_depth()
        log("◀ 结束 %s  rc=%d  耗时 %.1f 分  队列 running/pending = %s" % (
            name, rc, dt / 60.0, r1))

        # 汇总该幕日志里的结果
        try:
            txt = open(logfile, encoding="utf-8", errors="replace").read()
            oks = len(re.findall(r"^\s+镜\s+\d+\s+OK", txt, re.M))
            bads = re.findall(r"^\s+镜\s+(\d+)\s+(?!OK)(\S+)", txt, re.M)
            log("  本幕 OK=%d  异常=%d %s" % (
                oks, len(bads), ("→ " + str(bads[:8])) if bads else ""))
        except Exception as e:
            log("  读日志失败：%r" % e)

    log("=" * 70)
    log("全片跑完，总耗时 %.1f 小时" % ((time.time() - t_all) / 3600.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
