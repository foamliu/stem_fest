# -*- coding: utf-8 -*-
"""12 小时自主执行编排器 —— 阶段化、可断点续跑、纯 CPU 检查与 GPU 重跑解耦。

设计原则
    §1 **不改 GPU 占用**：所有检查步骤纯 CPU（ffmpeg / PIL / 正则），
       只在 GPU 空闲时才推 GPU 任务（重跑、ASR）。
    §2 **等待而非空转**：每阶段先判断"能不能做"，不能做就睡（默认 180s）再判。
    §3 **留痕**：每步写 OUTPUT/_auto_state.txt，出事可回看。

阶段
    S1  等待重跑进程结束 → 汇总重跑结果
    S2  T1 探针全片复检（污染是否清零）
    S3  重拼 full_cut.mp4
    S4  音频轨体检（台词由 H3 生成，见 README §「不要另做配音」）
    S5  水印探针 T2 + 时长合规 + 覆盖度 + prompt 闸门（纯 CPU）
    S6  汇总 `_final_report.md`

用法：
    py -3.10 OUTPUT/_auto_run.py --stage=S1
    py -3.10 OUTPUT/_auto_run.py --all
    py -3.10 OUTPUT/_auto_run.py --only-cpu
"""
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")
PY = ["py", "-3.10"]
STATE = os.path.join(OUT, "_auto_state.txt")


def log(m):
    line = "[%s] %s" % (time.strftime("%m-%d %H:%M:%S"), m)
    print(line, flush=True)
    with open(STATE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(args, label, timeout=None):
    log(">> %s" % label)
    t0 = time.time()
    r = subprocess.run(PY + args, cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    dt = time.time() - t0
    ok = r.returncode == 0
    log("   %s（%.0fs）" % ("OK" if ok else "FAIL rc=%d" % r.returncode, dt))
    if not ok:
        log("   stderr: %s" % (r.stderr or "")[-300:].replace("\n", " | "))
    return ok, (r.stdout or "")


def gpu_busy():
    """ComfyUI 队列是否有任务（含正在执行）。"""
    try:
        import json as _j
        import urllib.request
        d = _j.loads(urllib.request.urlopen(
            "http://127.0.0.1:8188/queue", timeout=8).read())
        return (len(d.get("queue_running") or []) +
                len(d.get("queue_pending") or [])) > 0
    except Exception:
        return False


def rerun_alive():
    """_run_rerun.py 是否还在跑。"""
    try:
        r = subprocess.run(["wmic", "process", "where",
                            "name='python.exe'", "get", "CommandLine"],
                           capture_output=True, text=True, errors="replace")
        return "_run_rerun.py" in (r.stdout or "")
    except Exception:
        return False


def wait_for(pred, what, poll=180, max_h=6.0):
    t0 = time.time()
    while True:
        if pred():
            log("   已满足：%s" % what)
            return True
        if (time.time() - t0) / 3600.0 > max_h:
            log("   等待 %s 超时（%.1fh）" % (what, max_h))
            return False
        log("   ... 等 %s（已 %.0f 分钟），睡 %ds" % (
            what, (time.time() - t0) / 60, poll))
        time.sleep(poll)



# ─────────────── 各阶段 ───────────────

def s1_wait_rerun():
    log("=== S1 等待重跑结束 ===")
    wait_for(lambda: not rerun_alive(), "重跑进程退出", poll=180, max_h=6.0)
    wait_for(lambda: not gpu_busy(), "GPU 队列清空", poll=30, max_h=0.5)
    log("重跑状态尾部：")
    sp = os.path.join(OUT, "_rerun_state.txt")
    if os.path.exists(sp):
        for L in open(sp, encoding="utf-8").read().splitlines()[-14:]:
            log("   " + L)
    return True


def s2_probe_all():
    log("=== S2 T1 探针全片复检 ===")
    allshots = ",".join(str(i) for i in range(1, 127))
    ok, out = run([os.path.join("OUTPUT", "_probe.py"),
                   "--type=T1", "--shots=" + allshots],
                  "T1 字幕带全片拼图", timeout=1800)
    log("   输出 OUTPUT/_probe/T1.jpg —— 需读图确认无字幕")
    return ok


def s3_concat():
    log("=== S3 重新拼接成片 ===")
    ok, out = run([os.path.join("OUTPUT", "_concat_video.py")],
                  "concat → full_cut.mp4", timeout=3600)
    if ok:
        p = os.path.join(OUT, "full_cut.mp4")
        if os.path.exists(p):
            log("   full_cut.mp4 = %.1f MB  %s" % (
                os.path.getsize(p) / 1e6,
                time.strftime("%m-%d %H:%M",
                              time.localtime(os.path.getmtime(p)))))
    return ok


def s4_audio():
    log("=== S4 音频轨体检（台词由 H3 生成，不另做配音）===")
    ok, out = run([os.path.join("OUTPUT", "_diag_audio_report.py")],
                  "音频轨报告", timeout=1800)
    return ok


def s5_cpu_checks():
    log("=== S5 纯 CPU 检查 ===")
    r1, _ = run([os.path.join("OUTPUT", "_coverage.py")], "覆盖度体检", 600)
    r2, _ = run([os.path.join("OUTPUT", "_probe.py"), "--type=T2"],
                "T2 水印边缘探针", 1800)
    r3, _ = run([os.path.join("OUTPUT", "_diag_shot_duration_audit.py")],
                "时长合规审计", 1200)
    r4, _ = run([os.path.join("OUTPUT", "_verify_prompt_clean.py")],
                "prompt 洁净度闸门", 600)
    return r1 and r2 and r3 and r4


def s6_report():
    log("=== S6 生成最终报告 ===")
    parts = ["# 《如愿·看见》最终质量报告", "",
             "生成时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S"), ""]
    for name, path in (("覆盖度", "_coverage.txt"),
                       ("时长审计", "_shot_duration_audit.txt"),
                       ("音频轨", "_audio_report.txt"),
                       ("重跑状态", "_rerun_state.txt"),
                       ("prompt 危险清单", "_prompt_hazard.txt")):
        p = os.path.join(OUT, path)
        if os.path.exists(p):
            parts += ["## %s（`OUTPUT/%s`）" % (name, path), "", "```",
                      open(p, encoding="utf-8", errors="replace").read().strip(),
                      "```", ""]
    rp = os.path.join(OUT, "_final_report.md")
    open(rp, "w", encoding="utf-8").write("\n".join(parts))
    log("   已写 %s（%.1f KB）" % (rp, os.path.getsize(rp) / 1024))
    return True


STAGES = {"S1": s1_wait_rerun, "S2": s2_probe_all, "S3": s3_concat,
          "S4": s4_audio, "S5": s5_cpu_checks, "S6": s6_report}


def main():
    which = []
    for a in sys.argv[1:]:
        if a.startswith("--stage="):
            which = [a.split("=", 1)[1].upper()]
        elif a == "--all":
            which = list(STAGES)
        elif a == "--only-cpu":
            which = ["S5", "S6"]
    if not which:
        which = list(STAGES)

    log("")
    log("#" * 66)
    log("自主执行：%s" % which)
    log("#" * 66)
    for st in which:
        if st not in STAGES:
            log("!! 未知阶段 %s" % st)
            continue
        try:
            STAGES[st]()
        except Exception as e:
            log("!! %s 异常：%r" % (st, e))
    log("阶段 %s 全部处理完毕" % which)
    return 0


if __name__ == "__main__":
    sys.exit(main())
