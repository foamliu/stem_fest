# -*- coding: utf-8 -*-
"""镜 125 定点重跑 —— 方案二（R2V + 自合成三人拼图）。

## 背景（诊断链，详见 `_make_125_triptych.py` 头部）

镜 125 原为 **T2V 无参考图**（`ref1=None, ref2=None`），三帧历史人物靠 prompt
文字描述临时编脸 ⇒ **两段错**（袁隆平画成圆脸中年人、钟南山画成白发苍苍）。
病因不是"缺参考图"，而是 **prompt 用文字描述年龄、且与定妆照设定冲突**
（`README.md:521`：袁隆平 1961 年 31 岁＝青年形象；钟南山"**不要画苍老**"）。

## 本脚本做的事

只改 `TASKS[125]` 的两处，其余一律沿用 `_diag_act5_finale.py` 的既有实现：

1. `ref1` → `OUTPUT/_shot125_refs/ref_three_heroes_v01.png`
   （三张**已定版**定妆照的像素级竖排拼图：①黄继光 ②袁隆平 ③钟南山；
     `image_edit_longcat` 不用 —— `ASSETS/README.md:178` 明文"合并合影会身份失真"）；
2. `prompt` → 三段各自 **`严格照 <Picture 1> 的第 N 格`**，并**删除年龄词**
   （不再写"中年男性"/"老年男性"），服饰只写与定妆照一致的部分。

## 命名（必须与首跑一致，否则覆盖不了旧片段）

首跑前缀 = `act5vs10/%02d_%s` ⇒ `act5vs10/125_three_stills_flash`
输出落 `OUTPUT/05_classroom_night/video/125_three_stills_flash_0000N_.mp4`，
与旧文件**同名即覆盖**，无需手工删旧。

用法：
    py -3.10 OUTPUT/_rerun_125_r2v.py --dry        # 只看将提交什么
    py -3.10 OUTPUT/_rerun_125_r2v.py --steps=8    # 实跑
    py -3.10 OUTPUT/_rerun_125_r2v.py --steps=8 --mp=0.4
"""
from __future__ import annotations

import importlib.util
import os
import sys

ROOT = r"E:\code\stem_fest"
DIAG = os.path.join(ROOT, "OUTPUT", "_diag_act5_finale.py")
TRIPTYCH = os.path.join(ROOT, "OUTPUT", "_shot125_refs", "ref_three_heroes_v01.png")

# 与首跑一致的前缀（`_diag_act5_finale.py:636`），保证同名覆盖
PREFIX_FMT = "act5vs10/%02d_%s"
SHOT = 125

NO_SPEECH = (
    "Audio: 安静教室的夜晚环境底噪；笔记本电脑散热风扇的轻微运转声；"
    "衣料摩擦声与呼吸声。"
)

# ★ 三段严格照 <Picture 1> 的三格；**不写年龄词**（年龄由参考图像素决定）
PROMPT_125 = (
    "CUT 1: 全屏画面。三段静止画面（定格摄影般，不是连续运动）依次出现、"
    "每段约 2-3 秒，中间用短暂的白光或黑场切换：\n"
    "第一段：一位穿 1950 年代志愿军冬装、戴红星军帽的年轻战士朝画面外挥手告别，"
    "面容严格照 <Picture 1> 的第一格；\n"
    "第二段：一位穿深灰色立领中山装、黑色短发侧分的男性弯腰把一束金黄色稻穗递向镜头，"
    "面容严格照 <Picture 1> 的第二格；\n"
    "第三段：一位戴细金属框眼镜、穿浅蓝衬衫的男性把一个浅蓝色口罩递向镜头，"
    "面容与发型严格照 <Picture 1> 的第三格（头发是灰黑相间，不要画成纯白）。\n"
    "三段的五官、发型、服装分别严格照 <Picture 1> 对应那一格，不要互相串用。\n"
    "画面色调庄重、干净，人物居于画面中央，背景简洁、偏暗。\n"
    + NO_SPEECH
)


def load_diag():
    """把 `_diag_act5_finale.py` 当模块载入（它没有 main 副作用，安全）。"""
    spec = importlib.util.spec_from_file_location("_diag_act5_finale", DIAG)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_diag_act5_finale"] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    args = sys.argv[1:]
    dry = "--dry" in args
    steps = 8          # 静帧镜，沿用首跑的提速档位（首跑也是 4/10 档）
    mp = 0.6
    for a in args:
        if a.startswith("--steps="):
            steps = int(a.split("=", 1)[1])
        elif a.startswith("--mp="):
            mp = float(a.split("=", 1)[1])
        elif a.startswith("--duration="):
            pass

    diag = load_diag()

    if not os.path.exists(TRIPTYCH):
        print("[X] 拼图不存在，请先跑 OUTPUT/_make_125_triptych.py：%s" % TRIPTYCH)
        return 2

    old = dict(diag.TASKS[SHOT])
    print("=" * 72)
    print("镜 %d 重跑（方案二：R2V + 三人拼图）" % SHOT)
    print("  旧：ref1=%s  ref2=%s" % (old["ref1"], old["ref2"]))
    print("  新：ref1=%s" % TRIPTYCH)
    print("  seed=%d（沿用）  dur=%.0f（沿用）  steps=%d  megapixels=%.2f" % (
        old["seed"], old["dur"], steps, mp))
    print("  前缀=%s（与首跑一致 ⇒ 同名覆盖）" % (PREFIX_FMT % (SHOT, old["slug"])))
    print("-" * 72)
    print("旧 prompt：")
    print(old["prompt"])
    print("-" * 72)
    print("新 prompt：")
    print(PROMPT_125)
    print("=" * 72)

    if dry:
        print("[dry] 未提交。")
        return 0

    # 只覆盖这一镜，其余 TASKS 不动
    diag.TASKS[SHOT] = dict(old)
    diag.TASKS[SHOT]["ref1"] = TRIPTYCH
    diag.TASKS[SHOT]["ref2"] = None            # 单参考图；H3 内部会复用 ref1
    diag.TASKS[SHOT]["prompt"] = PROMPT_125
    diag.OUT_ROOT = os.path.join(ROOT, "OUTPUT", "05_classroom_night", "video")
    diag.REPORT = os.path.join(ROOT, "OUTPUT", "_rerun_125_r2v_report.txt")

    row = diag.run_shot(SHOT, dry=False, megapixels=mp, steps=steps, timeout=3600)
    print("=" * 72)
    print("结果：镜 %d  %s  %s" % row)
    with open(diag.REPORT, "w", encoding="utf-8") as f:
        f.write("镜 125 重跑（方案二：R2V + 三人拼图）\n")
        f.write("ref1 = %s\n" % TRIPTYCH)
        f.write("steps=%d megapixels=%.2f\n\n" % (steps, mp))
        f.write("镜 %d\t%s\t%s\n" % row)
    print("报告：%s" % diag.REPORT)
    return 0 if row[1] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
