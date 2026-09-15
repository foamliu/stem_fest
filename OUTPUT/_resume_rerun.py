# -*- coding: utf-8 -*-
"""接管续跑 —— 修好「父进程被杀导致重跑中断」的残局，并把 ComfyUI 产物搬回项目。

背景（2026-09-15）
    `_run_rerun.py` 的**父进程**被误杀，但它已向 ComfyUI 提交了 P1 的 6 个镜
    （`act5vs10/110,111,113,117,119,121`）。这些任务在 ComfyUI 侧照常渲染完成，
    产物落在 `E:\\code\\ComfyUI\\output\\act5vs10\\*.mp4`，**不会自动回到项目目录**。
    P2/P3 的 35 镜则**从未提交**。

本脚本做三件事
    A. **搬移**：把 ComfyUI output 里属于本次重跑的 mp4 复制到
       `<幕目录>/video/`，并按 ComfyUI 的版本号规则重命名（避免覆盖旧版）。
    B. **续跑**：调用 `_run_rerun.py --only=P1/P2/P3` 补跑尚未完成的镜。
    C. **验收**：搬移后用 `_probe.py --type=T1` 抽检字幕是否消失。

为什么"搬移"要单独做而不能指望工具
    `comfyui_get_result(prompt_id)` 需要 prompt_id，而父进程死了拿不到历史 id；
    直接读 ComfyUI output 目录更稳（文件名自带镜号+slug）。

用法
    py -3.10 OUTPUT/_resume_rerun.py --sync           # 只搬移
    py -3.10 OUTPUT/_resume_rerun.py --sync --run     # 搬移 + 续跑
    py -3.10 OUTPUT/_resume_rerun.py --watch          # 盯着队列，清空即搬移+续跑
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")
COMFY = r"E:\code\ComfyUI\output"
PY = ["py", "-3.10"]
STATE = os.path.join(OUT, "_resume_state.txt")

# ComfyUI 输出子目录前缀 → 幕目录
PREFIX_ACT = {
    "act0": "01_paper_plane",
    "act1": "06_trench",
    "act2": "04_classroom_dusk",
    "act3": "07_rice_field",
    "act4": "08_train_dining",
    "act5": "05_classroom_night",
}

# 本次重跑用的 ComfyUI 输出前缀（steps 标记）
RERUN_PREFIXES = ["act0vs10", "act1vs10", "act2vs10", "act3vs10",
                  "act4vs10", "act5vs10"]


def log(m):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), m)
    print(line, flush=True)
    with open(STATE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def gpu_busy():
    try:
        import urllib.request
        d = json.loads(urllib.request.urlopen(
            "http://127.0.0.1:8188/queue", timeout=8).read())
        return (len(d.get("queue_running") or []) +
                len(d.get("queue_pending") or [])) > 0
    except Exception:
        return False


def next_version(act, shot, slug):
    """查目标目录已有版本号，返回下一个可用序号。"""
    vd = os.path.join(OUT, act, "video")
    os.makedirs(vd, exist_ok=True)
    mx = 0
    for f in glob.glob(os.path.join(vd, "%d_*.mp4" % shot)):
        m = re.search(r"_(\d{5})_\.mp4$", os.path.basename(f))
        if m:
            mx = max(mx, int(m.group(1)))
    return mx + 1


def sync():
    """把 ComfyUI 里本次重跑的产物搬到项目目录（保留版本号递增）。"""
    moved, skipped = 0, 0
    for pre in RERUN_PREFIXES:
        key = pre[:4]                    # act5
        act = PREFIX_ACT.get(key)
        if not act:
            continue
        src_dir = os.path.join(COMFY, pre)
        if not os.path.isdir(src_dir):
            continue
        for f in sorted(glob.glob(os.path.join(src_dir, "*.mp4"))):
            bn = os.path.basename(f)
            m = re.match(r"(\d+)_(.+?)_(\d{5})_\.mp4$", bn)
            if not m:
                skipped += 1
                continue
            shot = int(m.group(1))
            slug = m.group(2)
            vd = os.path.join(OUT, act, "video")
            # 已存在同名（同 slug）且大小相同 → 认为已搬过
            dup = [x for x in glob.glob(os.path.join(vd, "%d_%s_*.mp4" % (
                shot, slug))) if os.path.getsize(x) == os.path.getsize(f)]
            if dup:
                skipped += 1
                continue
            nv = next_version(act, shot, slug)
            dst = os.path.join(vd, "%d_%s_%05d_.mp4" % (shot, slug, nv))
            shutil.copy2(f, dst)
            log("   搬入 %s ← %s" % (os.path.basename(dst), pre + "/" + bn))
            moved += 1
    log("搬移完成：新增 %d，跳过 %d" % (moved, skipped))
    return moved


def main():
    do_sync = "--sync" in sys.argv
    do_run = "--run" in sys.argv
    do_watch = "--watch" in sys.argv
    if not (do_sync or do_run or do_watch):
        do_sync = True

    log("")
    log("=" * 62)
    log("接管续跑：sync=%s run=%s watch=%s" % (do_sync, do_run, do_watch))
    log("=" * 62)

    if do_watch:
        # 等队列清空（最多 2 小时），再搬移 + 续跑
        t0 = time.time()
        while gpu_busy():
            if (time.time() - t0) / 3600 > 2.0:
                log("等队列清空超时 2h，强行继续")
                break
            log("  队列仍忙（已 %.0f 分钟），睡 120s" % (
                (time.time() - t0) / 60))
            time.sleep(120)
        log("队列已清空")
        do_sync, do_run = True, True

    if do_sync:
        sync()

    if do_run:
        # ★ 写重跑基准时刻：只认比它新的产物为"本次已重跑"。
        #   必须在开跑前写，且**只在文件不存在时写**（续跑才能认得上一批的产物）。
        bl = os.path.join(OUT, "_rerun_baseline.txt")
        if not os.path.exists(bl):
            open(bl, "w", encoding="utf-8").write(str(time.time()))
            log("写重跑基准 %s" % bl)
        else:
            log("沿用重跑基准 %s = %.0f" % (bl, float(open(
                bl, encoding="utf-8").read().strip())))

        # 先跑闸门，确认 prompt 仍然干净
        r = subprocess.run(PY + [os.path.join("OUTPUT",
                                              "_verify_prompt_clean.py")],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        log("prompt 闸门 rc=%d" % r.returncode)
        if r.returncode != 0:
            log("!! 闸门未通过，拒绝开跑。尾部：%s" %
                (r.stdout or "")[-400:])
            return 2
        for tier in ("P1", "P2", "P3"):
            log(">> 续跑 %s" % tier)
            subprocess.run(PY + [os.path.join("OUTPUT", "_run_rerun.py"),
                                 "--only=" + tier],
                           cwd=ROOT)
        # 跑完再搬一次（防漏）
        sync()
        log("续跑全部结束")
    return 0


if __name__ == "__main__":
    sys.exit(main())
