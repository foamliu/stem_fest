# -*- coding: utf-8 -*-
"""从 mp4 内嵌元数据里**直接读出**该片段实际使用的生成步数 —— 硬证据，不靠推断。

## 为什么这个方法成立（2026-09-22 发现）

ComfyUI 的 `SaveVideo` 会把**整张工作流 JSON** 塞进 mp4 的 `udta/meta/keys`，
键名 `prompt`：

    ffprobe -show_entries format_tags file.mp4
    → format_tags.prompt = '{"92": {...}, "124": {"inputs": {"scheduler":
        "simple", "steps": 20, "denoise": 1, ...}, "class_type": "BasicScheduler"}, ...}'

其中节点 **`BasicScheduler` 的 `steps` 就是真实采样步数**。
⇒ 「这个镜到底是不是 steps=20 出的」变成**可判定的事实**，不必再靠闪烁度猜。

## 本脚本做什么

1. 遍历全片 6 幕 `video/` 下**所有** mp4（含 `_mid_`/`_bak_`/`_v2bak_` 归档版），
   逐个读出 `steps` + `seed` + `filename_prefix` + `megapixels`；
2. 按幕 + 镜号汇总，指出**现行产物**（会被拼接采用那版）的 steps；
3. 列出所有非 20 步的现行产物 ⇒ 即重跑清单，写 `_steps_todo.json`；
4. 报告 UTF-8 落盘（控制台 cp936 会炸中文+emoji）。

用法：
    py -3.10 OUTPUT/_probe_steps.py              # 全片扫描 + 写报告
    py -3.10 OUTPUT/_probe_steps.py --act=06     # 只扫 06_trench
    py -3.10 OUTPUT/_probe_steps.py --all-vers   # 连归档版一起打明细
"""
import glob
import io
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")

ACTS = [
    ("01_paper_plane", "_diag_act0_plane.py", (1, 9)),
    ("03_classroom_day", "_diag_act2_startup.py", (10, 18)),
    ("06_trench", "_diag_act1_trench.py", (19, 46)),
    ("07_rice_field", "_diag_act3_rice.py", (47, 74)),
    ("08_train_dining", "_diag_act4_train.py", (75, 105)),
    ("05_classroom_night", "_diag_act5_finale.py", (106, 126)),
]

ARCHIVE_RE = re.compile(r"^(_bak_|_v2bak_|_mid_|_v2_|_old_)")


def probe(path):
    """读 mp4 内嵌工作流，抽出 steps / seed / prefix / megapixels。"""
    r = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json",
                        "-show_entries", "format_tags", path],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode != 0 or not r.stdout:
        return None
    try:
        tags = json.loads(r.stdout).get("format", {}).get("tags", {})
    except Exception:
        return None
    raw = tags.get("prompt") or tags.get("epr") or ""
    if not raw:
        return None
    try:
        wf = json.loads(raw)
    except Exception:
        return None
    if not isinstance(wf, dict):
        return None

    info = {"steps": None, "seed": None, "prefix": None,
            "megapixels": None, "aspect_ratio": None, "nodes": len(wf)}
    for _nid, node in wf.items():
        if not isinstance(node, dict):
            continue
        ct = node.get("class_type", "")
        ins = node.get("inputs", {}) or {}
        if ct in ("BasicScheduler", "KSampler", "KSamplerAdvanced") \
                and isinstance(ins.get("steps"), (int, float)):
            info["steps"] = int(ins["steps"])
        if ct == "RandomNoise" and "noise_seed" in ins:
            info["seed"] = ins["noise_seed"]
        if ct == "SaveVideo" and "filename_prefix" in ins:
            info["prefix"] = ins["filename_prefix"]
        if ct == "ResolutionSelector":
            info["aspect_ratio"] = ins.get("aspect_ratio")
            info["megapixels"] = ins.get("megapixels")
    return info


def newest_video(act, shot):
    """该镜现行产物（会被拼接采用的那一版）：排除所有 `_` 前缀归档文件。

    镜号可能补零：01_paper_plane 用 %02d，其余幕用 %d（`_run_rerun.py` 踩过坑）。
    """
    vd = os.path.join(OUT, act, "video")
    best, bt = None, 0.0
    seen = set()
    for pat in ("%d_*.mp4" % shot, "%02d_*.mp4" % shot, "%03d_*.mp4" % shot):
        for f in glob.glob(os.path.join(vd, pat)):
            b = os.path.basename(f)
            if b in seen or ARCHIVE_RE.match(b):
                continue
            seen.add(b)
            m = os.path.getmtime(f)
            if m > bt:
                best, bt = f, m
    return best


def scan_main():
    argv = sys.argv[1:]
    only = None
    show_all = False
    for a in argv:
        if a.startswith("--act="):
            only = a.split("=", 1)[1]
        elif a == "--all-vers":
            show_all = True

    rep = []

    def emit(s=""):
        rep.append(s)

    emit("=" * 100)
    emit("全片生成步数 —— 硬证据（mp4 内嵌 ComfyUI 工作流 BasicScheduler.steps）")
    emit("=" * 100)

    todo, detail = {}, []
    for act, script, (lo, hi) in ACTS:
        if only and not act.startswith(only):
            continue
        vd = os.path.join(OUT, act, "video")
        if not os.path.isdir(vd):
            emit("[%s] 无目录" % act)
            continue
        emit("\n[%s]  镜 %d-%d" % (act, lo, hi))
        emit("  %-5s %-7s %-8s %-7s %s" % ("镜", "steps", "seed", "MP", "文件"))
        emit("  " + "-" * 92)
        bad = []
        for shot in range(lo, hi + 1):
            p = newest_video(act, shot)
            if not p:
                emit("  %-5d  缺       --       无产物" % shot)
                continue
            inf = probe(p)
            b = os.path.basename(p)
            if not inf or inf["steps"] is None:
                emit("  %-5d  ??       --       %s  (无内嵌工作流)" % (shot, b))
                detail.append((act, shot, None, b))
                continue
            flag = "  " if inf["steps"] == 20 else "  <<< 需重跑"
            emit("  %-5d  %-7s %-8s %-7s %s%s"
                 % (shot, inf["steps"], inf["seed"], inf["megapixels"], b, flag))
            detail.append((act, shot, inf["steps"], b))
            if inf["steps"] != 20:
                bad.append(shot)
        if bad:
            emit("  ⇒ 需重跑（steps≠20）：%s" % bad)
            todo[script] = bad
        else:
            emit("  该幕现行产物全部 steps=20")

    if show_all:
        emit("\n" + "=" * 100)
        emit("★ 归档版（_mid_ / _bak_）步数明细 —— 追溯「哪些镜曾经低步数」")
        emit("=" * 100)
        for act, script, (lo, hi) in ACTS:
            if only and not act.startswith(only):
                continue
            vd = os.path.join(OUT, act, "video")
            files = sorted(glob.glob(os.path.join(vd, "*.mp4")))
            arch = [f for f in files if ARCHIVE_RE.match(os.path.basename(f))]
            if not arch:
                continue
            emit("\n[%s]  归档 %d 个" % (act, len(arch)))
            for f in arch:
                inf = probe(f)
                st = inf["steps"] if inf and inf["steps"] is not None else "?"
                emit("  steps=%-5s %s" % (st, os.path.basename(f)))

    emit("\n" + "=" * 100)
    n = sum(len(v) for v in todo.values())
    emit("合计需重跑（现行产物 steps≠20）：%d 个镜" % n)
    for scr, v in todo.items():
        emit("   %-24s %s" % (scr, v))
    emit("=" * 100)

    with io.open(os.path.join(OUT, "_steps_probe_report.txt"), "w",
                 encoding="utf-8") as fh:
        fh.write("\n".join(rep) + "\n")
    with io.open(os.path.join(OUT, "_steps_todo.json"), "w",
                 encoding="utf-8") as fh:
        json.dump(todo, fh, ensure_ascii=False, indent=1)

    print("合计需重跑：%d 个镜" % n)
    for scr, v in todo.items():
        print("   %-24s %s" % (scr, v))
    print("报告：%s" % os.path.join(OUT, "_steps_probe_report.txt"))
    print("清单：%s" % os.path.join(OUT, "_steps_todo.json"))
    return 0


if __name__ == "__main__":
    sys.exit(scan_main())
