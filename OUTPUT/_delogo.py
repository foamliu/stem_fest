# -*- coding: utf-8 -*-
"""画面字幕「擦除」工具（B 方案）—— 用 ffmpeg 的 `delogo` 滤镜就地插值抹掉台词字幕。

★ 为什么用 B 方案而不是改 prompt 重跑（2026-09-15 实测结论，README §6.6）
    `Audio:` 段的**台词原文无法从 prompt 里删掉** —— H3 靠它生成口型与环境音，
    删了就没配音了。而写了台词原文就有 ~9.3% 概率被当字幕画出来（含引号组 50%）。
    ⇒ 重跑只是**再抽一次卡**，不能根治；且每镜 5–15 分钟、可能反复失败。
    ⇒ 正解：**保留现有画面，用 `delogo` 就地插值修补**（README §6.9 的"后期兜底"）。

★ `delogo` 原理
    把指定矩形当作水印，用**周边像素插值**重新填充该区域。
    比 `drawbox` 涂黑/模糊好得多：字幕背后常是**平滑背景**
    （车厢壁、桌面、墙壁），插值后基本看不出补过。

★ 用法
    # 1) 先看字幕框选得对不对（出一张标注红框的核对图）
    py -3.10 OUTPUT/_delogo.py --shots=14 --preview

    # 2) 满意后执行擦除（原地替换 + 备份原片为 _bak_*）
    py -3.10 OUTPUT/_delogo.py --shots=14,21
    py -3.10 OUTPUT/_delogo.py --all          # 全部 9 镜

★ 框写法： x:y:w:h（像素，基于该镜真实分辨率）
"""
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")

# 默认字幕框。依据 `_scan_subtitles.py` 拼图观测：泄漏字幕在**画面 78–86% 高度**、
# 水平居中；本片镜为 1056x608。
BOX_W, BOX_H, BOX_Y = 470, 46, 478


def _box(scale=1.0):
    return (int((1056 - BOX_W) / 2), int(BOX_Y), int(BOX_W * scale), int(BOX_H))


# 泄漏镜 → (幕目录, 片名 slug, 自定义 box 或 None 用默认)
SHOTS = {
    7:   ("01_paper_plane", "xu_changjing_liu_siqi_glance", None),
    14:  ("04_classroom_dusk", "zhang_defends_himself", None),
    21:  ("06_trench", "zhang_crouches_looks_at_wild_veg", None),
    36:  ("06_trench", "young_soldier_relieved_huang_smiles", None),
    77:  ("08_train_dining", "xu_looks_at_the_elder", None),
    85:  ("08_train_dining", "siqi_answers_small_voice", None),
    86:  ("08_train_dining", "zhang_asks_why_wuhan", None),
    88:  ("08_train_dining", "xu_asks_is_it_serious", None),
    112: ("05_classroom_night", "zhang_quotes_the_question", None),
}

# 泄漏文字（仅用于日志/报告）
TEXT = {
    7: "**也不抬 / 你少自恋了", 14: "我上次竞选科技之星", 21: "这野菜能吃吗",
    36: "你听见没", 77: "他在高铁上……看文件", 85: "吃了",
    86: "钟爷爷 您去武汉做什么", 88: "很严重吗",
    112: "他问我们……咱们国家现在啥样了",
}


def newest(act, slug):
    """取该镜**最新**的 mp4（与 `_concat_video.py` 同一套规则：按 mtime）。"""
    d = os.path.join(OUT, act, "video")
    cands = []
    for f in os.listdir(d):
        if f.startswith("_bak_"):
            continue
        if re.match(r"^\d+_%s_\d+_.*\.mp4$" % re.escape(slug), f):
            cands.append((os.path.getmtime(os.path.join(d, f)), f))
    if not cands:
        return None
    cands.sort()
    return os.path.join(d, cands[-1][1])


def probe_size(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height", "-of", "csv=p=0", p],
                       capture_output=True, text=True)
    try:
        w, h = r.stdout.strip().split(",")[:2]
        return int(w), int(h)
    except Exception:
        return None


def do_delogo(src, box, dst):
    x, y, w, h = box
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", src,
           "-vf", "delogo=x=%d:y=%d:w=%d:h=%d" % (x, y, w, h),
           "-c:v", "libx264", "-preset", "medium", "-crf", "19",
           "-c:a", "copy", dst]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode == 0, (r.stderr or "")[:300]


def do_preview(src, box, dst):
    """出两张带红框的图（0.35/0.6 时长处），核对框位。"""
    x, y, w, h = box
    d = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", src],
                       capture_output=True, text=True)
    try:
        dur = float(d.stdout.strip())
    except Exception:
        dur = 3.0
    made = []
    for i, fr in enumerate((0.35, 0.6)):
        q = dst.replace(".jpg", "_%d.jpg" % i)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "%.2f" % (dur * fr),
                        "-i", src, "-frames:v", "1",
                        "-vf", "drawbox=x=%d:y=%d:w=%d:h=%d:color=red@1:t=3" % (x, y, w, h),
                        q], capture_output=True)
        made.append(q)
    return made

def main():
    shots, allf, preview, box_override = [], False, False, None
    for a in sys.argv[1:]:
        if a.startswith("--shots="):
            shots = [int(x) for x in a.split("=", 1)[1].split(",")]
        elif a == "--all":
            allf = True
        elif a == "--preview":
            preview = True
        elif a.startswith("--box="):
            box_override = tuple(int(x) for x in a.split("=", 1)[1].split(":"))

    if not shots and not allf:
        print("用法：py -3.10 OUTPUT/_delogo.py --shots=14[,21] [--preview|--box=x:y:w:h]")
        print("      py -3.10 OUTPUT/_delogo.py --all")
        return 1
    if allf:
        shots = sorted(SHOTS)

    pv_dir = os.path.join(OUT, "_delogo_preview")
    os.makedirs(pv_dir, exist_ok=True)
    ok_n = 0
    for n in shots:
        if n not in SHOTS:
            print("⚠️ 镜 %d 不在泄漏清单里，跳过" % n)
            continue
        act, slug, custom = SHOTS[n]
        src = newest(act, slug)
        if not src:
            print("✗ 镜 %-3d 找不到视频（%s/%s）" % (n, act, slug))
            continue
        wh = probe_size(src)
        box = box_override or custom or _box()
        print("[镜 %-3d] %s  %s" % (n, os.path.basename(src), wh))

        if preview:
            made = do_preview(src, box, os.path.join(pv_dir, "s%03d.jpg" % n))
            print("   ↳ 核对图：%s" % ", ".join(os.path.relpath(m, ROOT) for m in made))
            print("     框 = x=%d y=%d w=%d h=%d ｜ 泄漏文字「%s」"
                  % (box + (TEXT.get(n, ""),)))
            ok_n += 1
            continue

        tmp = src.replace(".mp4", "_delogo.mp4")
        ok, err = do_delogo(src, box, tmp)
        if not ok:
            print("   ✗ 失败：%s" % err)
            continue
        bak = os.path.join(os.path.dirname(src), "_bak_" + os.path.basename(src))
        shutil.move(src, bak)
        shutil.move(tmp, src)
        print("   ✅ 已擦除（框 x=%d y=%d w=%d h=%d）｜原片备份 %s"
              % (box + (os.path.basename(bak),)))
        print("      泄漏文字「%s」" % TEXT.get(n, ""))
        ok_n += 1

    print()
    print("完成 %d/%d" % (ok_n, len(shots)))
    if preview:
        print("⚠️ 请用 read_files 读上面的核对图，确认红框**完整盖住字幕**且**不压到人物**，")
        print("   再跑不带 --preview 的正式擦除。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
