# -*- coding: utf-8 -*-
"""综合视觉抽检器（v2）—— 一次出图，覆盖 4 类已知缺陷。

与 _visual_review.py 的区别
    _visual_review.py：全片 126 镜联系表（21 张图，适合"普查"）。
    本工具：**按缺陷类型分派探针**，每种缺陷只看最该看的地方（适合"专项复查"）：
        T1 字幕污染  → 只裁画面下 1/4，放大看字（最省图）
        T2 水印外泄  → 裁上/下边缘带
        T3 人物一致性 → 定妆照与抽帧并排（相对判断）
        T4 画面崩坏  → 全帧（黑帧/过曝/畸形）

用法：
    py -3.10 OUTPUT/_probe.py --type=T1 --shots=5,19,91
    py -3.10 OUTPUT/_probe.py --type=T4 --shots=50,73,74,117,121
    py -3.10 OUTPUT/_probe.py --type=T3 --shots=6,19,39
    py -3.10 OUTPUT/_probe.py --type=T2 --shots=75,85,95,105
"""
import glob
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")
DIR = os.path.join(OUT, "_probe")
REFS = os.path.join(OUT, "_shot_refs.json")

ACTS = ["01_paper_plane", "03_classroom_day", "06_trench",
        "07_rice_field", "08_train_dining", "05_classroom_night"]


def latest(shot):
    best, bt = None, 0
    for d in ACTS:
        for f in glob.glob(os.path.join(OUT, d, "video", "%02d_*.mp4" % shot)):
            if os.path.getmtime(f) > bt:
                best, bt = f, os.path.getmtime(f)
    return best


def dur_of(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def grab(shot, t, vf, tag):
    """抽一帧并应用 vf 滤镜链。返回 (路径, 版本号)。"""
    p = latest(shot)
    if not p:
        return None, None
    fp = os.path.join(DIR, "_%s_%03d_%s.jpg" % (tag, shot, str(t).replace(".", "p")))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "%.3f" % t, "-i", p,
                    "-frames:v", "1", "-vf", vf, "-q:v", "2", fp],
                   capture_output=True)
    if os.path.exists(fp) and os.path.getsize(fp) > 0:
        m = re.search(r"_(\d{5})_\.mp4$", os.path.basename(p))
        return fp, (m.group(1) if m else "?")
    return None, None


def probe_T1(shots):
    """T1 字幕污染：下 1/4，放大 1.42 倍看字。"""
    rows = []
    for n in shots:
        p = latest(n)
        if not p:
            rows.append((n, "?", [], "NO VIDEO"))
            continue
        d = dur_of(p)
        got, ver = [], "?"
        for frac in (0.35, 0.6, 0.85):
            fp, v = grab(n, d * frac, "crop=1056:190:0:418,scale=1500:270", "T1")
            ver = v or ver
            if fp:
                got.append(fp)
        rows.append((n, ver, got, ""))
    return rows, 1500, 270


def probe_T4(shots):
    """T4 画面崩坏：全帧（看黑帧/过曝/畸形）。"""
    rows = []
    for n in shots:
        p = latest(n)
        if not p:
            rows.append((n, "?", [], "NO VIDEO"))
            continue
        d = dur_of(p)
        got, ver = [], "?"
        for frac in (0.3, 0.7):
            fp, v = grab(n, d * frac, "scale=620:-1", "T4")
            ver = v or ver
            if fp:
                got.append(fp)
        rows.append((n, ver, got, ""))
    return rows, 620, 357


def probe_T2(shots):
    """T2 水印外泄：上 1/5 + 下 1/5 边缘带。"""
    rows = []
    for n in shots:
        p = latest(n)
        if not p:
            rows.append((n, "?", [], "NO VIDEO"))
            continue
        d = dur_of(p)
        got, ver = [], "?"
        fp, v = grab(n, d * 0.5, "crop=1056:210:0:0,scale=1400:278", "T2a")
        ver = v or ver
        if fp:
            got.append(fp)
        fp, v = grab(n, d * 0.5, "crop=1056:210:0:398,scale=1400:278", "T2b")
        if fp:
            got.append(fp)
        rows.append((n, ver, got, ""))
    return rows, 1400, 278


def probe_T3(shots, refs):
    """T3 人物一致性：定妆照 + 抽帧并排（相对判断）。"""
    rows = []
    for n in shots:
        p = latest(n)
        v = refs.get(str(n), {})
        d = dur_of(p) if p else 0
        got, ver = [], "?"
        for frac in (0.2, 0.5, 0.8):
            fp, vv = grab(n, d * frac, "scale=470:271", "T3")
            ver = vv or ver
            if fp:
                got.append(fp)
        rows.append((n, ver, got, v.get("refs", [])))
    return rows, 470, 271


def build(rows, tw, th, tag, title):
    from PIL import Image, ImageDraw
    lab_h, gap = 20, 5
    has_ref = any(isinstance(r[3], list) and r[3] for r in rows)
    ref_w = int(tw * 0.72) if has_ref else 0
    maxf = max(len(r[2]) for r in rows) if rows else 3
    W = ref_w + maxf * (tw + 4) + 16
    H = 4 + len(rows) * (th + lab_h + gap)
    canvas = Image.new("RGB", (W, H), (12, 12, 14))
    dr = ImageDraw.Draw(canvas)
    dr.text((6, 2), title, fill=(255, 225, 130))
    for ri, (n, ver, fs, extra) in enumerate(rows):
        y = 4 + ri * (th + lab_h + gap)
        lab = extra if isinstance(extra, str) else "定妆照对照"
        dr.text((6, y), "SHOT %d  v%s  %s" % (n, ver, lab),
                fill=(240, 240, 120))
        x0 = 6
        if isinstance(extra, list) and extra:
            each_h = th // max(1, len(extra[:2]))
            each_w = int(each_h * 1056 / 608)
            for j, rp in enumerate(extra[:2]):
                try:
                    im = Image.open(rp).convert("RGB").resize((each_w, each_h),
                                                               Image.LANCZOS)
                    canvas.paste(im, (x0 + j * (each_w + 3), y + lab_h))
                except Exception:
                    pass
            x0 += ref_w
        for j, fp in enumerate(fs):
            try:
                im = Image.open(fp).convert("RGB").resize((tw, th), Image.LANCZOS)
                canvas.paste(im, (x0 + j * (tw + 4), y + lab_h))
            except Exception:
                pass
    sp = os.path.join(DIR, "%s.jpg" % tag)
    canvas.save(sp, quality=86)
    return sp


def main():
    ttype, shots = "T1", []
    for a in sys.argv[1:]:
        if a.startswith("--type="):
            ttype = a.split("=", 1)[1].upper()
        elif a.startswith("--shots="):
            shots = [int(x) for x in a.split("=", 1)[1].split(",") if x.strip()]
    if not shots:
        print("!! 请用 --shots=1,2,3 指定镜号（避免全片误跑）")
        return 1

    os.makedirs(DIR, exist_ok=True)
    for f in glob.glob(os.path.join(DIR, "_*.jpg")):
        os.remove(f)

    refs = json.load(open(REFS, encoding="utf-8")) if os.path.exists(REFS) else {}
    if ttype == "T1":
        rows, tw, th = probe_T1(shots)
        title = "T1 字幕污染探针 —— 看画面下 1/4 是否有字幕字样"
    elif ttype == "T2":
        rows, tw, th = probe_T2(shots)
        title = "T2 水印外泄探针 —— 看上/下边缘是否有水印文字"
    elif ttype == "T4":
        rows, tw, th = probe_T4(shots)
        title = "T4 画面崩坏探针 —— 看黑帧/过曝/畸形"
    else:
        rows, tw, th = probe_T3(shots, refs)
        title = "T3 人物一致性探针 —— 左=定妆照 右=抽帧，判是否同一人"
    sp = build(rows, tw, th, ttype, title)
    print("输出：%s" % sp)
    return 0


if __name__ == "__main__":
    sys.exit(main())

