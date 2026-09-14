# -*- coding: utf-8 -*-
"""修正 `_diag_act3_rice.py`（第二幕）的历史编号错误。

问题（2026-09-14 核查发现）：
   脚本 TASKS 写成 **52-76**，而 storyboard 第二幕是 **47-74**。
   · 内容与 storyboard 47-71 一一对应 ⇒ 整体偏移 +5
   · 缺 storyboard 的 72/73/74（稻谷 / 背影 / 白屏日记字）
   · 75/76 越界，与第三幕（75-105）**撞号**

本脚本做两件事：
   ① `TASKS[52..76]` → `TASKS[47..71]`（按 +5→-5 重编号，内容不动）
   ② 在结尾追加缺失的 3 镜：72 / 73 / 74

★ 只改 TASKS 的键与注释里的镜号，prompt 正文不动（正文没写镜号）。
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "OUTPUT", "_diag_act3_rice.py")

src = io.open(P, encoding="utf-8").read()

# ── ① 键重编号 52..76 → 47..71 ──────────────────────────────
def shift(m):
    n = int(m.group(1))
    return "TASKS[%d] = dict(" % (n - 5) if 52 <= n <= 76 else m.group(0)

new, cnt = re.subn(r"TASKS\[(\d+)\] = dict\(", shift, src)
print("键重编号：%d 处" % cnt)

# ── ①b 补一个缺失的参考图常量（72 镜要用「刘思齐 + 袁隆平」二人合影）──
NEED_CONST = 'G_SIQI_YUAN = os.path.join(FRAMES, "_group", "liu_siqi_yuan_longping_hero_v01.png")'
if "G_SIQI_YUAN" not in new:
    anchor = 'G_FOUR_YUAN = os.path.join(FRAMES, "_group", "four_students_yuan_longping_hero_v01.png")'
    if anchor not in new:
        raise SystemExit("找不到 G_FOUR_YUAN 锚点")
    new = new.replace(anchor, anchor + "\n" + NEED_CONST, 1)
    print("已补常量：G_SIQI_YUAN")

# ── ② 追加缺失的 3 镜（72 稻谷 / 73 背影 / 74 白屏）──────────
ADD = '''
# ── 镜 72 袁隆平摘一粒稻谷，放在刘思齐手心（特写）──
TASKS[72] = dict(
    slug="yuan_puts_grain_in_her_palm", seed=9577,
    ref1=G_SIQI_YUAN, ref2=P_RICE_GRAIN, dur=5.0,
    prompt=(
        "CUT 1: 特写镜头。一位穿中山装的中年男性从稻穗上轻轻摘下一粒金黄色的稻谷，"
        "把它放进身旁一位戴细框眼镜的初中女生的手心里；两只手在画面中央、动作很轻；"
        "**他的面貌与服装严格照 <Picture 1>（中山装必须保留、不要改变长相）**；"
        "**女生的细框眼镜必须保留**；稻谷的形态与颜色照 <Picture 2>；"
        "背景是盛夏的稻田，稻浪在阳光下起伏、轻微虚化；"
        + LIGHT + "。固定机位。\\n"
        "Audio: 风吹稻浪声与蝉鸣（后期）；"
        "他轻声说：拿着。回去种不种得活，看你们。"
    ),
)

# ── 镜 73 袁隆平转身走进稻田，背影消失在稻浪中（全景）──
TASKS[73] = dict(
    slug="yuan_walks_into_rice_field", seed=9578,
    ref1=G_FOUR_YUAN, ref2=SCENE_RICE, dur=3.0,
    prompt=(
        "CUT 1: 全景镜头。那位穿中山装的中年男性转过身，"
        "沿着田埂一步步走进金绿色的稻田深处，头也不回，"
        "背影渐渐被高高扬起的稻浪挡住、最后消失在稻海里；"
        "**四位穿校服的初中生留在田埂上、望着他的方向，没有跟上去**；"
        "他的面貌与服装严格照 <Picture 1>（**中山装必须保留**）；"
        "四位学生的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那片盛夏的稻田；"
        + LIGHT + "。镜头缓慢向前推，随后定格。\\n"
        + NO_SPEECH
    ),
)

# ── 镜 74 四人站在原地，画面泛白（全景；★ 白屏日记字转场，T2V）──
TASKS[74] = dict(
    slug="white_out_diary_card_act2", seed=9579,
    ref1=None, ref2=None, dur=5.0,
    prompt=(
        "CUT 1: 全景镜头。四位穿校服的初中生站在田埂上，"
        "望着那个人消失的稻田方向，一动不动，微风吹动他们的衣角与周围的稻穗；"
        "画面从两侧开始逐渐泛白、白光一点点吞没整个画面，"
        "最后画面完全变成白屏（像一个过场转场的白光收束）；"
        "四人的面貌、发型与服装严格照参考；"
        "背景是盛夏的稻田与晴朗的天空；"
        + LIGHT + "。固定机位。\\n"
        + NO_SPEECH
    ),
)
'''

# 插到 ComfyUI 基础段之前
MARK = "# ────────────────────────────────────────────────────────────── ComfyUI 基础"
if MARK not in new:
    raise SystemExit("找不到 ComfyUI 基础段锚点")
new = new.replace(MARK, ADD.lstrip("\n") + "\n" + MARK, 1)

io.open(P, "w", encoding="utf-8").write(new)
print("已追加缺失 3 镜（72/73/74）")
print("文件行数：%d" % (new.count("\n") + 1))
