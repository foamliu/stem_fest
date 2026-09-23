# -*- coding: utf-8 -*-
"""镜 125 重跑方案二·改 —— **三段独立生成 + ffmpeg 拼接**。

## 为什么从"单条 8s 三段"改成"三条独立段"

单条 8s prompt 内塞 `CUT 1/2/3` 时，实测**渲染不满三段**：
* run1（`_00004_`）：三段脸都对，但第 3 段质量不稳；
* run2（`_00005_`）：**第 3 段直接串成第 2 格的脸（袁隆平）**，且口罩消失。

⇒ 根因是 **8 秒内同时做「3 张脸 + 3 种道具 + 2 次转场」超出 H3 的内容调度能力**，
   模型退化成"复用上一张脸"。

## 新结构：每人一段，各自独立

每段 = **单张参考图**（只含该人那一格的拼图变体）+ 2~3 秒 + 自己的 prompt：

  * 只有一张脸可参考 ⇒ **无串脸空间**；
  * 三段各跑一次 H3 R2V，再用 ffmpeg `concat` 拼成 8s（段间插白闪）。

用法：
    py -3.10 OUTPUT/_rerun_125_segments.py --dry
    py -3.10 OUTPUT/_rerun_125_segments.py --steps=8
"""
from __future__ import annotations

import importlib.util
import os
import pathlib
import subprocess
import sys

from PIL import Image

ROOT = pathlib.Path(r"E:\code\stem_fest")
DIAG = ROOT / "OUTPUT" / "_diag_act5_finale.py"
TRIPTYCH = ROOT / "OUTPUT" / "_shot125_refs" / "ref_three_heroes_v01.png"
CELLS_DIR = ROOT / "OUTPUT" / "_shot125_refs" / "cells_one"
SEG_DIR = ROOT / "OUTPUT" / "05_classroom_night" / "video" / "_seg125"
VIDEO_DIR = ROOT / "OUTPUT" / "05_classroom_night" / "video"

CELL_H, BAR = 768, 24
STRIDE = CELL_H + BAR

NO_SPEECH = (
    "Audio: 安静教室的夜晚环境底噪；笔记本电脑散热风扇的轻微运转声；"
    "衣料摩擦声与呼吸声。"
)

# 每段： slug, 格号(1-based), 时长, 描述（面部一律「严格照 <Picture 1>」）
#
# ★ 2026-09-21 关键教训（两轮连续踩坑，务必保留）：
#   H3（Minimax）会把提示词里**"手部的道具动作"当成构图主体**，把景别压到道具上：
#     · 写"双手捧稻穗抱在胸前" → 出**躯干特写**，头被挤出画面（段 2 第一版）
#     · 写"抬起双手在胸口整理口罩" → 出**脸部大特写**，脸顶被裁出上边界（段 3 第二版）
#   ⇒ 修法：① 用「脸是画面主体」开头，明确"脸位于画面中央、头顶留有空白"；
#           ② 道具写成**被动持有**（拿着/握着），不写"举/递/捧到胸前"这类空间动作；
#           ③ 正向提示词末尾追加**显式禁止语**（不要大特写/不要躯干特写/不要裁头）。
SEGMENTS = [
    ("a_hj", 1, 3.0,
     "这是一张**半身肖像照**：画面主体是这位人物的头部与脸，"
     "他的脸位于画面正中央、头顶距画面上沿留有约一成空白，肩膀与胸口在画面下方；"
     "人物穿 1950 年代志愿军冬装、戴红星军帽，"
     "他抬起右手朝画面外挥手告别，动作缓慢庄重、像定格照片般稳定；"
     "他的五官与军帽严格照 <Picture 1>，只有这一位人物。"
     "★ 禁止：不要大特写、不要躯干特写、不要把头部或帽子裁掉。"
     "画面色调庄重、干净，背景简洁、偏暗。"),
    ("b_ylp", 2, 3.0,
     "这是一张**半身肖像照**：画面主体是这位人物的头部与脸，"
     "他的脸位于画面正中央、头顶距画面上沿留有约一成空白，肩膀与胸口在画面下方；"
     "人物穿深灰色立领中山装、黑色短发侧分，"
     "他手里拿着一束金黄色稻穗放在身前，动作缓慢庄重、像定格照片般稳定；"
     "他的五官与发型严格照 <Picture 1>，只有这一位人物。"
     "★ 禁止：不要大特写、不要躯干特写、不要把稻穗画满画面、不要把头部裁掉。"
     "画面色调庄重、干净，背景简洁、偏暗。"),
    ("c_zns", 3, 2.0,
     "这是一张**半身肖像照**：画面主体是这位人物的头部与脸，"
     "他的脸位于画面正中央、额头与头顶完整可见，头顶距画面上沿留有空隙，"
     "肩膀与胸口在画面下方；"
     "人物戴细金属框眼镜、穿浅蓝衬衫，"
     "他**双手在胸口高度拿着一个浅蓝色医用口罩**（口罩不遮脸、不接触面部），"
     "动作缓慢庄重、像定格照片般稳定；"
     "他的五官、发型（灰黑相间的短发，不要画成纯白）与眼镜严格照 <Picture 1>，"
     "只有这一位人物。"
     "★ 禁止：不要戴口罩、不要口罩遮住脸、不要大特写、不要裁掉额头或眼睛、"
     "不要只拍脸和口罩。"
     "画面色调庄重、干净，背景简洁、偏暗。"),
]

FINAL_PREFIX = "act5vs10/125_three_stills_flash"
FINAL_NAME = "125_three_stills_flash_00006_.mp4"


def pick_seg(slug: str, fixed_only: bool = False) -> pathlib.Path | None:
    """取某段产物。★ 不用 `Path.glob()` —— Windows 上它对 `_seg125` 这类
    下划线开头目录会返回空（实测：`iterdir()` 能列出文件、`glob()` 却为空）。
    改为 `iterdir()` + startswith 过滤，并按 mtime 取最新。
    """
    pre = "125_%s_fixed_" % slug if fixed_only else "125_%s_" % slug
    cands = [p for p in SEG_DIR.iterdir()
             if p.is_file() and p.name.startswith(pre) and p.name.endswith(".mp4")]
    if not cands:
        return None
    return max(cands, key=lambda p: p.stat().st_mtime)


def pick_seg_any(slug: str) -> pathlib.Path | None:
    """优先 `_fixed_`（构图修正版），否则该段 mtime 最新。"""
    return pick_seg(slug, fixed_only=True) or pick_seg(slug, fixed_only=False)


def load_diag():
    spec = importlib.util.spec_from_file_location("_diag_act5_finale", str(DIAG))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_diag_act5_finale"] = mod
    spec.loader.exec_module(mod)
    return mod


def make_single_cells() -> dict:
    """把拼图每格单独存成"只含一个人"的参考图（单参考图 ⇒ 杜绝串脸）。

    ★ 2026-09-21 实测教训（两轮迭代）：
      ① 直接取整格（768px 高、脸占 77%）→ H3 推成大特写，**头被裁出画面**。
      ② 下方只补 0.55 倍高（脸降到 52%）→ 脸完整但**脸顶仍贴边/出界**（-11%~-14%），
         因为 H3 的景别主要跟随**参考图本身的取景松紧**，文字压不住。
      ③ 现改为**左右也补边、把脸压到画幅 38% 左右**，参考图看起来是一张「头肩完整的中景肖像」，
         H3 才会按中景而非特写取景。
    """
    CELLS_DIR.mkdir(parents=True, exist_ok=True)
    img = Image.open(TRIPTYCH).convert("RGB")
    out = {}
    for slug, cell_no, _, _ in SEGMENTS:
        # ★ 段 3 若已有「中景参考图」（_make_125_seg3_ref.py 产出）则优先使用：
        #   拼图格 3 因水印规避只剩「脸+单肩」，会让 H3 推成大特写（详见该脚本注释）。
        mid = CELLS_DIR / ("%s_ref_mid.png" % slug)
        if mid.exists():
            out[slug] = str(mid)
            continue
        top = (cell_no - 1) * STRIDE
        cell = img.crop((0, top, img.width, top + CELL_H))
        # 目标：脸高占画幅 ~38%。③ 号格（钟南山）原脸更大（61%@0.78），单独再压一档。
        shrink = 0.62 if slug == "c_zns" else 0.78
        bg = Image.new("RGB", (cell.width, CELL_H), (24, 24, 24))
        cw2 = int(cell.width * shrink)
        ch2 = int(CELL_H * shrink)
        cell2 = cell.resize((cw2, ch2), Image.LANCZOS)
        # 水平居中、垂直略偏上（头顶留空）
        bg.paste(cell2, ((bg.width - cw2) // 2, int(CELL_H * 0.09)))
        p = CELLS_DIR / ("%s_ref.png" % slug)
        bg.save(p, "PNG")
        out[slug] = str(p)
    return out


def concat_with_flash(diag, segs, out_path, total=8.0):
    """三段 + 段间白闪 → 8s；末段定格补足总长，统一到 1056×608/24fps/aac32k。

    ★ 2026-09-21 教训：一开始用**单个复杂 filter_complex**（scale+pad+fps+concat+tpad+apad
      再配 `-t`）在 Windows 上会**挂死**（ffmpeg 进程跑 40 分钟不退出、输出文件无 moov）。
      现改为**两阶段**，每步都简单、可单独重试：

        阶段 1：把每段 + 白闪各自转码成「同规格中间片」（1056×608 / 24fps / aac 32k 立体声）
        阶段 2：用 concat demuxer（`-f concat -c copy`）拼成一条，速度快且不吃滤镜图
        阶段 3：若不足 total，末帧定格补足（`tpad` 在这一步只做一件事）
    """
    exe = "ffmpeg"
    work = SEG_DIR / "_work"
    work.mkdir(parents=True, exist_ok=True)

    def norm(src: pathlib.Path, dst: pathlib.Path, dur=None):
        cmd = [exe, "-v", "error", "-i", str(src),
               "-vf", "scale=1056:608:force_original_aspect_ratio=decrease,"
                      "pad=1056:608:(ow-iw)/2:(oh-ih)/2,fps=24,setsar=1",
               # ★ `-r 24` 必须显式写：只靠 `-vf fps=24` 时，concat 出的文件
               #   帧率会被标成 289/12（≈24.083），与其余 125 镜的 `24/1` 不一致
               #   ⇒ `_concat_video.py` 判定规格不一致 → 触发**全片 126 镜重转码**。
               "-r", "24",
               "-c:v", "libx264", "-preset", "medium", "-crf", "18",
               "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "128k", "-ar", "32000", "-ac", "2"]
        if dur:
            cmd += ["-t", "%.3f" % dur]
        cmd += [str(dst), "-y"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            print("  [X] 归一化失败 %s: %s" % (src.name, (r.stderr or "")[:300]))
            return False
        return True

    # 白闪（0.15s，够看清一次闪白）
    flash = work / "flash.mp4"
    subprocess.run([exe, "-v", "error", "-f", "lavfi", "-i",
                    "color=c=white:s=1056x608:r=24:d=0.15",
                    "-f", "lavfi", "-i", "anullsrc=r=32000:cl=stereo",
                    "-t", "0.15", "-c:v", "libx264", "-crf", "18",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
                    "-ar", "32000", "-ac", "2", str(flash), "-y"],
                   check=True, timeout=180)

    # 阶段 1：归一化每条
    normed = []
    for i, p in enumerate(segs):
        d = work / ("seg%d.mp4" % i)
        if not norm(pathlib.Path(p), d):
            return False
        normed.append(d)
    flash_n = work / "flash_n.mp4"
    if not norm(flash, flash_n, dur=0.15):
        return False

    # 阶段 2：concat demuxer 拼（段-闪-段-闪-段）
    order = []
    for i, p in enumerate(normed):
        order.append(p)
        if i < len(normed) - 1:
            order.append(flash_n)
    lst = work / "list.txt"
    with open(lst, "w", encoding="utf-8") as f:
        for p in order:
            f.write("file '%s'\n" % str(p).replace("\\", "/"))
    joined = work / "joined.mp4"
    r = subprocess.run([exe, "-v", "error", "-f", "concat", "-safe", "0",
                        "-i", str(lst), "-c", "copy", str(joined), "-y"],
                       capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        print("[X] concat 失败：%s" % (r.stderr or "")[:400])
        return False

    # 阶段 3：末帧定格补足 total（只做一件事，避免复杂滤镜挂死）
    # ★ `apad` 让音轨以静音补到与画面等长，避免音轨比画面短而在末镜累积偏移。
    r = subprocess.run([exe, "-v", "error", "-i", str(joined),
                        "-vf", "tpad=stop_mode=clone:stop_duration=%.2f" % total,
                        "-af", "apad",
                        "-r", "24",
                        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                        "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "128k", "-ar", "32000", "-ac", "2",
                        "-t", "%.2f" % total, str(out_path), "-y"],
                       capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        print("[X] 补长失败：%s" % (r.stderr or "")[:400])
        return False
    v = diag.probe(str(out_path))
    print(">>> 规格：%s" % v)
    return "error" not in v and abs(float(v.get("duration", 0)) - total) < 0.5


def main() -> int:
    args = sys.argv[1:]
    dry = "--dry" in args
    concat_only = "--concat-only" in args
    only_slug = None
    steps = 8
    mp = 0.6
    for a in args:
        if a.startswith("--steps="):
            steps = int(a.split("=", 1)[1])
        elif a.startswith("--mp="):
            mp = float(a.split("=", 1)[1])
        elif a.startswith("--only="):
            only_slug = a.split("=", 1)[1].strip()

    diag = load_diag()
    cells = make_single_cells()
    print("=" * 78)
    print("镜 125 方案二·改：三段独立生成（每段单参考图）")
    for slug, cell_no, dur, _ in SEGMENTS:
        print("  %-8s 格%d  %.0fs  ref=%s" % (slug, cell_no, dur, cells[slug]))
    print("  最终合成 -> %s" % (VIDEO_DIR / FINAL_NAME))
    print("=" * 78)
    if dry:
        for slug, cell_no, dur, prompt in SEGMENTS:
            print("--- %s (格%d, %.0fs) ---\n%s\n" % (slug, cell_no, dur, prompt))
        print("[dry] 未提交。")
        return 0

    SEG_DIR.mkdir(parents=True, exist_ok=True)

    if concat_only:
        # 复用已生成的段，只重做合成（调试滤镜用）
        # ★ 取片规则与正式路径一致：优先 `_fixed_`（构图修正版），否则该段 mtime 最新。
        ordered = []
        for slug, _, _, _ in SEGMENTS:
            p = pick_seg_any(slug)
            if not p:
                print("[X] 缺段 %s" % slug)
                return 1
            ordered.append(p)
        print(">>> 仅合成：%s" % [p.name for p in ordered])
        out_path = VIDEO_DIR / FINAL_NAME
        ok = concat_with_flash(diag, ordered, out_path)
        print(">>> 合成：%s  %s" % (out_path, "OK" if ok else "FAIL"))
        return 0 if ok else 1

    results = []
    for i, (slug, cell_no, dur, prompt) in enumerate(SEGMENTS):
        if only_slug and slug != only_slug:
            print("\n[skip] %s（--only=%s）" % (slug, only_slug))
            continue
        # ★ 段 3（c_zns）单独换 seed：同一 seed 会稳定复现同一套构图问题
        #   （前 4 轮段 3 都是「脸被推到 620–679px、额头出界」），换 seed 才能跳出该局部最优。
        seed = 9841 if slug == "c_zns" else 9820 + i * 7
        task = dict(
            slug=slug,
            seed=seed,
            ref1=cells[slug],
            ref2=None,
            dur=dur,
            prompt=("CUT 1: 全屏画面。" + prompt + "\n" + NO_SPEECH),
        )
        diag.TASKS[125] = task
        diag.OUT_ROOT = str(SEG_DIR)
        print("\n>>> 生成 %s（seed=%d dur=%.0fs ref=%s）" % (
            slug, task["seed"], dur, os.path.basename(cells[slug])))
        row = diag.run_shot(125, dry=False, megapixels=mp, steps=steps, timeout=3600)
        print("    -> %s" % (row,))
        results.append((slug, row))
        if row[1] != "OK":
            print("[X] 段 %s 未成功，中止后续段以免拼出残缺片段" % slug)
            return 1

    # 合成取片：优先用本轮的产物，未跑的段取该段**最新**（mtime）版本
    # ★ 段 3 若存在 `_fixed_`（_fix_125_seg3_framing.py 的构图修正版）则优先用它：
    #   H3 对肖像类单参考图会稳定推成大特写、头顶出界，靠后期缩放下移修正。
    seg_files = []
    done = {slug: row for slug, row in results}
    for slug, cell_no, dur, _ in SEGMENTS:
        p = pick_seg_any(slug)
        if p:
            print("[pick] %s -> %s%s" % (
                slug, p.name,
                "（构图修正版）" if "_fixed_" in p.name else "（最新）"))
            seg_files.append(p)
            continue
        row = done.get(slug)
        if row:
            fn = row[2].split(" | ")[0] if " | " in row[2] else row[2]
            seg_files.append(SEG_DIR / fn)
            continue
        print("[X] 段 %s 无可用产物" % slug)
        return 1
    print("\n>>> 待合并：%s" % [p.name for p in seg_files])
    out_path = VIDEO_DIR / FINAL_NAME
    ok = concat_with_flash(diag, seg_files, out_path)
    print(">>> 合成：%s  %s" % (out_path, "OK" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
