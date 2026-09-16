# -*- coding: utf-8 -*-
"""第三幕《餐车一角》视频批量生成（镜 75-105）—— 跳过首帧，直接「人物参考图 + 场景图」喂 H3 R2V。

⚠️ 命名说明：本幕对应 scene 目录 `08_train_dining`，脚本名用 `act4_train`。
   全片映射见 `_diag_act0_plane.py` 文首。

台词与镜号严格取自 `storyboard.md` §第三幕：餐车一角（2020-01-18 夜，高铁餐车）。

★ 本幕要点：
  · 场景图唯一：`train_dining_wide_v01.png`
  · **钟南山参考图带「新华网 WWW.NEWS.CN」水印**（2026-09-14 用户提供）——
    首跑本幕时特别留意 H3 有无把该水印文字画进画面（README §8 P0 #3）
  · 镜 75 是**幕首建立镜**（餐车 + 钟南山闭眼 + 桌板文件），steps=20
  · 镜 97（9s）/ 镜 99（10s）是全片最长台词镜（钟南山讲 400 米栏 / 学医），保持原时长
  · 镜 102（6s）三拍动作：武汉站到 + 收拾文件 + 递口罩
  · 镜 104（5s）三拍动作：起身 + 走向车门 + 背影消失在夜色，情绪落点
  · 镜 105 是**白屏日记字转场**（T2V，无角色）

⚠️ steps：默认 **10**（对话/反应镜为主）；镜 75/104 为环境剧变镜可单独补 `--steps=20`。

⚠️ 音频（README §4.4）：本幕无台词镜较多（75/79/81/83/91/102/104/105 等），
   全部挂 NO_SPEECH；所有「音效：（后期）」由 strip_late_audio() 剔除。

用法：
    py -3.10 OUTPUT/_diag_act4_train.py --dry              # 只看任务清单
    py -3.10 OUTPUT/_diag_act4_train.py --steps=10         # 全量（默认 10）
    py -3.10 OUTPUT/_diag_act4_train.py --steps=20 75 104  # 环境剧变镜单独 20 步
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = r"E:\code\stem_fest"
COMFY = "http://127.0.0.1:8188"
COMFY_OUT = r"E:\code\ComfyUI\output"
COMFY_IN = r"E:\code\ComfyUI\input"
WORKFLOW_DIR = os.path.join(ROOT, "workflows")
OUT_ROOT = os.path.join(ROOT, "OUTPUT", "08_train_dining", "video")
REPORT = os.path.join(ROOT, "OUTPUT", "_act4_train_report.txt")
CLIENT_ID = "act4v_train"

FRAMES = os.path.join(ROOT, "ASSETS", "CHARACTERS")
SCENES = os.path.join(ROOT, "ASSETS", "SCENES")
PROPS = os.path.join(ROOT, "ASSETS", "PROPS")

WF_R2V = "video_minimax_h3_r2v.json"
WF_T2V = "video_minimax_h3_t2v.json"

# 第三幕统一光线基调（storyboard：2020-01-18 夜，车厢暖黄 + 窗外夜色）
LIGHT = (
    "2020 年 1 月的夜里，高铁餐车车厢内是暖黄色的顶灯照明，"
    "车窗外是深蓝黑色的夜色与偶尔掠过的灯光，画面暖黄与冷蓝对比、安静而克制"
)

SCENE = os.path.join(SCENES, "08_train_dining", "train_dining_wide_v01.png")

# ── 角色参考图 ────────────────────────────────────────────
P_ZHONG = os.path.join(FRAMES, "07_zhong_nanshan", "zhong_nanshan_hero_v01.png")

# ── 合影参考图（R2V 硬前提；一律用不带标签的 hero_v01）──
G_FOUR = os.path.join(FRAMES, "_group", "four_students_hero_v02.png")
G_FOUR_ZN = os.path.join(FRAMES, "_group", "four_students_zhong_nanshan_hero_v01.png")
G_SIQI_ZN = os.path.join(FRAMES, "_group", "liu_siqi_zhong_nanshan_hero_v01.png")
G_SICHENG_ZN = os.path.join(FRAMES, "_group", "liu_sicheng_zhong_nanshan_hero_v01.png")
G_XU_ZN = os.path.join(FRAMES, "_group", "xu_changjing_zhong_nanshan_hero_v01.png")
G_ZHANG_ZN = os.path.join(FRAMES, "_group", "zhang_shuyang_zhong_nanshan_hero_v01.png")
G_SICHENG_SIQI = os.path.join(FRAMES, "_group", "liu_sicheng_liu_siqi_hero_v01.png")
G_ZN_SOLO = os.path.join(FRAMES, "_group", "solo_zhong_nanshan_hero_v01.png")

# ── 道具参考图 ────────────────────────────────────────────
P_MASK = os.path.join(PROPS, "07_mask", "mask_hero_v02.png")
P_DOC = os.path.join(PROPS, "10_doc_covid", "doc_covid_detail_v02.png")

# 无台词镜的通用禁语音后缀（README §4.4）
NO_SPEECH = (
    "Audio: 高铁车厢行进中的低频嗡鸣与轻微晃动声；"
    "车厢里的环境底噪与远处模糊的人声，听不清任何词句。"
)

# ★ 音频三层分工（README §4.4）：带「（后期）」的音效不进 H3 prompt
LATE_MARK = "（后期）"


def strip_late_audio(text):
    """把「…（后期）」这类后期音效从句子里剔除，只留 L1 台词给 H3。

    ★ 2026-09-16 关键修复（去字幕泄漏，README §6.6b）：
      旧实现切句后 **无条件 join**，把 `\n` 段落分隔符一起吃掉 ⇒ 多行 prompt
      被压成一行，禁令句与台词**粘连**，H3 便把台词当画面字幕渲染。
      现改为 **按行处理、保留换行**：行内含 LATE_MARK 的句子才丢，`\n` 一律保留。
    """
    import re as _re
    lines = []
    for line in text.split("\n"):
        kept = [s for s in _re.split(r"(?<=[；。])", line) if LATE_MARK not in s]
        lines.append("".join(kept))
    return "\n".join(lines).strip()


# 造型护栏（README §6.1 #1：定妆照 = 外形唯一权威）
#
# ★ 2026-09-15 去泄漏化（README §6.6）：删掉 `**` 加粗标记（会被 H3 画成画面文字）。
#   本常量被镜 75/81/82/84/89/91/92/94/104 等**多个钟南山镜**共用，改一处全部受益。
#   ⚠️ 同时修掉重复拼接 bug：调用处已写「…严格照 <Picture 1>」，
#      旧常量又以「他的面貌、发型与服装严格照 <Picture 1>」开头 ⇒ 输出重复两遍。
GUARD_ZN = (
    "（只穿浅蓝色衬衫、不穿西装外套，不戴帽子；银灰短发、细框眼镜必须保留；"
    "不要把他画得苍老，面容紧致、精神矍铄）"
)


TASKS = {}

# ── 镜 75 幕首建立镜：餐车 + 钟南山闭眼 + 桌板文件（★ 5s，环境建立）──
TASKS[75] = dict(
    slug="zhong_asleep_in_dining_car", seed=9701,
    ref1=G_ZN_SOLO, ref2=SCENE, dur=5.0,
    prompt=(
        "CUT 1: 中景镜头。深夜的高铁餐车一角，一位老年男性仰靠在座椅背上闭着眼睛、"
        "神情疲惫而沉静；他面前的小桌板上摊着几份打印文件与一支笔；"
        + GUARD_ZN + "；"
        "背景是 <Picture 2> 那节高铁餐车车厢：暖黄色顶灯、成排的座椅、"
        "车窗外是深蓝黑色的夜色；"
        + LIGHT + "。镜头缓缓向前推，最后落在他的手部与桌板上的文件。\n"
        + NO_SPEECH
    ),
)

# ── 镜 76 四人站在车厢连接处（全景）──
TASKS[76] = dict(
    slug="four_at_car_vestibule", seed=9702,
    ref1=G_FOUR, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 全景镜头。四位穿着校服的初中生站在高铁车厢的连接处，"
        "有人扶着扶手、有人探头往车厢里看，表情好奇又有点茫然；"
        "四人都完整入画、处于同一个连续空间、四人之间的间距均匀；"
        "四人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那节高铁餐车与车厢连接处，暖黄顶灯 + 窗外夜色；"
        + LIGHT + "。镜头跟移着他们，随后定格。\n"
        "Audio: 高铁行驶的低频轰响（后期）；"
        "一位男生看着车厢、小声说：高铁？这不是 2020 年吗？"
    ),
)

# ── 镜 77 徐畅景看老人（中近景）──
TASKS[77] = dict(
    slug="xu_looks_at_the_elder", seed=9703,
    ref1=G_FOUR, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 中近景镜头。一位初中男生侧过身，目光望向车厢深处那位闭眼休息的老人，"
        "表情是小心而克制的打量；"
        "身后和身旁还站着另外三位同学，他们只入画一部分；"
        "四人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那节高铁餐车车厢，暖黄顶灯 + 窗外夜色；"
        + LIGHT + "。固定机位（转场留白）；★ 全画面不得出现任何可读的文字、字幕或符号。画面上没有任何文字、字幕或标识，人物脸上只有表演。\n"
        "Audio: 车轮与铁轨的节奏声（后期）；"
        "男生压低声音说：他在高铁上……看文件。"
    ),
)

# ── 镜 78 刘思齐往刘思成身后缩（中景）──
TASKS[78] = dict(
    slug="siqi_shrinks_behind_sicheng", seed=9704,
    ref1=G_SICHENG_SIQI, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 中景双人镜头，两位初中生并排站在同一光照环境里、是一个完整连续的空间："
        "一位女生下意识地往身旁那位戴细框眼镜的女生身后缩了半步、肩膀微微收紧，"
        "眼神看着车厢深处、带着一点不安；被依靠的那位站得笔直、也望着同一个方向；"
        "两人的面貌、发型、眼镜与服装严格照 <Picture 1>（细框眼镜必须保留）；"
        "背景是 <Picture 2> 那节高铁餐车车厢，暖黄顶灯 + 窗外夜色；"
        + LIGHT + "。镜头缓慢向前推（穿过车厢向前）。\n"
        "Audio: 高铁行驶的低频声（后期）；"
        "女生小声说：那个人……好累的样子。"
    ),
)

# ── 镜 79 刘思成看清文件上的字（特写；★ 信息点）──
TASKS[79] = dict(
    slug="sicheng_reads_the_document", seed=9705,
    ref1=P_DOC, ref2=G_SICHENG_ZN, dur=5.0,
    prompt=(
        "CUT 1: 特写镜头。画面主体是桌上摊开的一份打印文件，纸面上有清晰的标题文字"
        "「新型冠状病毒」；一位戴细框眼镜的初中女生的脸出现在画面一侧，"
        "她微微前倾、正盯着文件上的字看，表情先是疑惑、随即转为震动，"
        "请让她看清文件上的字、观众要读得到那行标题；"
        "文件版面照 <Picture 1>；她的面貌、发型、眼镜与服装严格照 <Picture 2>"
        "（细框眼镜必须保留）；"
        "背景是高铁餐车车厢，暖黄顶灯 + 窗外夜色；"
        + LIGHT + "。固定机位。\n"
        + NO_SPEECH
    ),
)

# ── 镜 80 刘思成开口 / 刘思齐捂嘴（中近景）──
TASKS[80] = dict(
    slug="they_recognize_zhong", seed=9706,
    ref1=G_SICHENG_SIQI, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 中近景双人镜头，两位初中生处于同一光照环境、是一个完整连续的空间："
        "左边一位戴细框眼镜的女生睁大眼睛、嘴唇轻启，震惊地念出一个名字；"
        "右边一位女生下意识地抬手捂住了自己的嘴、眼睛睁得很大；"
        "两人的面貌、发型、眼镜与服装严格照 <Picture 1>（细框眼镜必须保留）；"
        "背景是 <Picture 2> 那节高铁餐车车厢，暖黄顶灯 + 窗外夜色；"
        + LIGHT + "。固定机位。\n"
        "Audio: 车厢底噪（后期）；"
        "戴眼镜的女生震惊地说：钟南山。另一位小声接着说：钟南山爷爷。"
    ),
)

# ── 镜 81 钟南山睁眼看见四人（中景；转场静默拍）──
TASKS[81] = dict(
    slug="zhong_opens_eyes_sees_them", seed=9707,
    ref1=G_FOUR_ZN, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 中景镜头。那位老年男性缓缓睁开眼睛，目光落在面前站着的四位初中生身上，"
        "神情从疲惫转为一丝温和的意外，随即嘴角微微一松、露出一个很淡的笑；"
        "四位初中生都在画面里，围站在他面前；"
        + GUARD_ZN.replace("<Picture 1>", "<Picture 1> 中的长者") + "；"
        "四位学生的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那节高铁餐车车厢，暖黄顶灯 + 窗外夜色；"
        + LIGHT + "。固定机位（静默节拍）。\n"
        + NO_SPEECH
    ),
)

# ── 镜 82 钟南山坐直，指对面座位（中景）──
TASKS[82] = dict(
    slug="zhong_invites_them_to_sit", seed=9708,
    ref1=G_FOUR_ZN, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 中景镜头。那位老年男性在座位上坐直了身子，抬手朝对面的座位指了指，"
        "示意孩子们坐下，神态随和自然；"
        "四位初中生都在画面里，站在他面前；"
        + GUARD_ZN + "；"
        "四位学生的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那节高铁餐车车厢，暖黄顶灯 + 窗外夜色；"
        + LIGHT + "。镜头缓慢向前推。\n"
        "Audio: 车厢底噪（后期）；"
        "他随和地说：坐嘛。站着做啥？"
    ),
)

# ── 镜 83 四人坐下（全景，无台词）──
TASKS[83] = dict(
    slug="four_sit_down", seed=9709,
    ref1=G_FOUR_ZN, ref2=SCENE, dur=2.0,
    prompt=(
        "CUT 1: 全景镜头。四位穿校服的初中生依次在对面的座位上坐下来，"
        "有人把书包放在腿上、有人坐得笔直，姿态拘谨又好奇；"
        "那位老年男性坐在他们对面、也在画面里；"
        "四人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那节高铁餐车车厢，暖黄顶灯 + 窗外夜色；"
        + LIGHT + "。固定机位。\n"
        + NO_SPEECH
    ),
)

# ── 镜 84 钟南山问（中景）──
TASKS[84] = dict(
    slug="zhong_asks_if_they_ate", seed=9710,
    ref1=G_FOUR_ZN, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 中景镜头。那位老年男性看着对面坐下的孩子们，随口问了一句，"
        "神情平和、带着长者对孩子的自然关心；"
        "四位初中生都在画面里、坐在他对面；"
        + GUARD_ZN + "；"
        "四位学生的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那节高铁餐车车厢，暖黄顶灯 + 窗外夜色；"
        + LIGHT + "。镜头缓慢向后拉。\n"
        "Audio: 车厢底噪（后期）；"
        "他问：你们吃饭了没？"
    ),
)

# ── 镜 85 刘思齐小声答 / 钟南山点头（中近景）──
TASKS[85] = dict(
    slug="siqi_answers_small_voice", seed=9711,
    ref1=G_SIQI_ZN, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 中近景双人镜头，一位戴细框眼镜的初中女生与那位老年男性"
        "面对面坐在同一张餐桌两侧、处于同一光照环境："
        "女生小声地回答、声音很轻、眼睛不太敢直视对方；"
        "对面的长者听完微微点了点头、神情温和；"
        "两人的面貌、发型、眼镜与服装严格照 <Picture 1>"
        "（女生的细框眼镜必须保留）；"
        "背景是 <Picture 2> 那节高铁餐车车厢，暖黄顶灯 + 窗外夜色；"
        + LIGHT + "。固定机位；★ 全画面不得出现任何可读的文字、字幕或符号。画面上没有任何文字、字幕或标识，人物脸上只有表演。\n"
        "Audio: 车厢底噪（后期）；"
        "女生小声说：吃了。长者点头说：那就好。"
    ),
)

# ── 镜 86 张书扬问（近景）──
TASKS[86] = dict(
    slug="zhang_asks_why_wuhan", seed=9712,
    ref1=G_ZHANG_ZN, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 近景双人镜头，一位初中男生与那位老年男性隔着餐桌对坐、"
        "处于同一光照环境：男生身子微微前倾、认真地问了一个问题，"
        "眼神里有好奇也有一点小心翼翼；长者安静地看着他、准备作答；"
        "两人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那节高铁餐车车厢，暖黄顶灯 + 窗外夜色；"
        + LIGHT + "。固定机位，镜头轻微下摇；★ 全画面不得出现任何可读的文字、字幕或符号。画面上没有任何文字、字幕或标识，人物脸上只有表演。\n"
        "Audio: 车厢底噪与铁轨节奏声（后期）；"
        "男生认真地问：钟爷爷，您去武汉做什么？"
    ),
)

# ── 镜 87 钟南山想了想（近景）──
TASKS[87] = dict(
    slug="zhong_says_go_and_see", seed=9713,
    ref1=G_ZHANG_ZN, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 近景双人镜头，那位老年男性与对面的初中男生处于同一光照环境："
        "长者先是想了一下、目光落在桌面的文件上，随即平静而简短地回答；"
        "男生在一旁认真听着；"
        "两人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那节高铁餐车车厢，暖黄顶灯 + 窗外夜色；"
        + LIGHT + "。固定机位。\n"
        "Audio: 车厢底噪（后期）；"
        "长者平静地说：去看看。看看这个病到底怎么回事。"
    ),
)

# ── 镜 88 徐畅景看文件（中近景）──
TASKS[88] = dict(
    slug="xu_asks_is_it_serious", seed=9714,
    ref1=G_XU_ZN, ref2=SCENE, dur=2.0,
    prompt=(
        "CUT 1: 中近景双人镜头，一位初中男生与那位老年男性隔着餐桌对坐、"
        "处于同一光照环境：男生低头看了一眼桌上摊开的文件，"
        "随即抬眼看向长者、问了一句，神情有点担心；长者看着他；"
        "两人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那节高铁餐车车厢，暖黄顶灯 + 窗外夜色；"
        + LIGHT + "。固定机位；★ 全画面不得出现任何可读的文字、字幕或符号。画面上没有任何文字、字幕或标识，人物脸上只有表演。\n"
        "Audio: 车厢底噪（后期）；"
        "男生问：很严重吗？"
    ),
)

# ── 镜 89 钟南山问（中景）──
TASKS[89] = dict(
    slug="zhong_asks_where_from", seed=9715,
    ref1=G_FOUR_ZN, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 中景镜头。那位老年男性看着对面坐着的四个孩子，"
        "目光在他们脸上逐一停了一下，然后问出一句话，神情是探究的、不凶；"
        "四位初中生都在画面里、坐在他对面；"
        + GUARD_ZN + "；"
        "四位学生的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那节高铁餐车车厢，暖黄顶灯 + 窗外夜色；"
        + LIGHT + "。镜头缓慢向前推（双人景）。\n"
        "Audio: 车厢底噪（后期）；"
        "他问：你们从哪来的？"
    ),
)

# ── 镜 90 刘思成坦白（近景）──
TASKS[90] = dict(
    slug="sicheng_tells_the_truth", seed=9716,
    ref1=G_SICHENG_ZN, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 近景双人镜头，一位戴细框眼镜的初中女生与那位老年男性"
        "隔着餐桌对坐、处于同一光照环境：女生直视着对方、"
        "平静而坦然地回答，没有躲闪；长者安静地听着；"
        "两人的面貌、发型、眼镜与服装严格照 <Picture 1>"
        "（女生的细框眼镜必须保留）；"
        "背景是 <Picture 2> 那节高铁餐车车厢，暖黄顶灯 + 窗外夜色；"
        + LIGHT + "。固定机位。\n"
        "Audio: 车厢底噪与铁轨声（后期）；"
        "女生坦然地说：2026 年。从未来来的。"
    ),
)

# ── 镜 91 钟南山沉默，看文件，看孩子（近景；无台词）──
TASKS[91] = dict(
    slug="zhong_silent_looks_at_them", seed=9717,
    ref1=G_ZN_SOLO, ref2=G_FOUR, dur=3.0,
    prompt=(
        "CUT 1: 近景镜头。画面主体是那位老年男性，他没有立刻说话，"
        "先低头看了看桌上摊开的文件，又抬眼望向对面坐着的四个孩子，"
        "眼神很深、面无表情地沉默了几秒，喉结动了一下；"
        "四位学生作为虚化的背景坐在他对面、只入画一部分；"
        + GUARD_ZN + "；"
        "背景是 <Picture 2> 那节高铁餐车车厢的暖黄灯光；"
        + LIGHT + "。镜头缓慢向前推。\n"
        + NO_SPEECH
    ),
)

# ── 镜 92 钟南山问（中景）──
TASKS[92] = dict(
    slug="zhong_asks_can_go_outside_now", seed=9718,
    ref1=G_FOUR_ZN, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 中景镜头。那位老年男性看着对面的孩子们，"
        "问出一个他真正在意的问题，语气带着一点不易察觉的期待；"
        "四位初中生都在画面里、坐在他对面；"
        + GUARD_ZN + "；"
        "四位学生的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那节高铁餐车车厢，暖黄顶灯 + 窗外夜色；"
        + LIGHT + "。固定机位。\n"
        "Audio: 车厢底噪（后期）；"
        "他问：那……现在大家都能出门了？"
    ),
)

# ── 镜 93 刘思齐点头，眼泪掉下来（近景）──
TASKS[93] = dict(
    slug="siqi_cries_yes", seed=9719,
    ref1=G_SIQI_ZN, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 近景双人镜头，一位戴细框眼镜的初中女生与那位老年男性"
        "隔着餐桌对坐、处于同一光照环境：女生用力点了点头，"
        "眼眶里蓄着泪、一颗泪珠顺着脸颊滑落下来，她努力保持声音平稳；"
        "对面的长者安静地看着她；"
        "两人的面貌、发型、眼镜与服装严格照 <Picture 1>"
        "（女生的细框眼镜必须保留）；"
        "背景是 <Picture 2> 那节高铁餐车车厢，暖黄顶灯 + 窗外夜色；"
        + LIGHT + "。镜头缓慢向前推。\n"
        "Audio: 车厢底噪（后期）；"
        "女生带着泪点头说：能出门了。不用戴口罩了。"
    ),
)

# ── 镜 94 钟南山慢慢笑了（中景）──
TASKS[94] = dict(
    slug="zhong_smiles_slowly", seed=9720,
    ref1=G_FOUR_ZN, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 中景镜头。那位老年男性听完，先是安静了一瞬，"
        "然后慢慢露出一个很浅、很放松的笑，眼神一下子亮了起来；"
        "四位初中生都在画面里、坐在他对面；"
        + GUARD_ZN + "（他的表情必须是放松的微笑）；"
        "四位学生的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那节高铁餐车车厢，暖黄顶灯 + 窗外夜色；"
        + LIGHT + "。固定机位。\n"
        "Audio: 车厢底噪（后期）；"
        "他慢慢笑着说：那就好。那我接着去看。"
    ),
)

# ── 镜 95 张书扬问（近景）──
TASKS[95] = dict(
    slug="zhang_asks_if_he_wanted_doctor", seed=9721,
    ref1=G_ZHANG_ZN, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 近景双人镜头，一位初中男生与那位老年男性隔着餐桌对坐、"
        "处于同一光照环境：男生眼睛发亮、兴致上来了，"
        "身子往前凑了凑、问出一个关于对方小时候的问题；长者看着他；"
        "两人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那节高铁餐车车厢，暖黄顶灯 + 窗外夜色；"
        + LIGHT + "。固定机位。\n"
        "Audio: 车厢底噪与铁轨节奏声（后期）；"
        "男生问：钟爷爷，您小时候……想过自己会当医生吗？"
    ),
)


# ── 镜 96 钟南山笑了，想起很久以前的事（近景）──
TASKS[96] = dict(
    slug="zhong_remembers_running_fast", seed=9722,
    ref1=G_ZHANG_ZN, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 近景双人镜头，那位老年男性与对面的初中男生处于同一光照环境："
        "长者笑了一下，目光稍微偏开、落在窗外的夜色上，"
        "目光微微放空、嘴角带着一点笑意，语气平缓；男生专注地听着；"
        "两人的面貌、发型与服装严格照 <Picture 1>"
        "（他的表情必须是带笑意的）；"
        "背景是 <Picture 2> 那节高铁餐车车厢，暖黄顶灯 + 窗外夜色；"
        + LIGHT + "。镜头缓慢向前推。\n"
        "Audio: 车厢底噪（后期）；"
        "他笑着说：没想过。我年轻的时候，跑得很快。"
    ),
)

# ── 镜 97 钟南山靠椅背看窗外（★ 9s 长台词镜）──
TASKS[97] = dict(
    slug="zhong_tells_hurdle_record", seed=9723,
    ref1=G_ZHANG_ZN, ref2=SCENE, dur=9.0,
    prompt=(
        "CUT 1: 中景双人镜头，那位老年男性向后靠在椅背上、微微侧头看着窗外掠过的夜色，"
        "一边平静地讲述一段往事，神情平淡、语速不急不缓；"
        "对面的初中男生在画面里听着、只入画一部分；"
        "两人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那节高铁餐车车厢，暖黄顶灯 + 车窗外深蓝夜色；"
        + LIGHT + "。镜头缓慢横移，跟着窗外掠过的夜景。\n"
        "Audio: 车轮与铁轨的节奏声（后期）；"
        "他平静地说：1959 年，我打破过全国 400 米栏纪录。中央体育学院想让我去国家队。"
    ),
)

# ── 镜 98 张书扬眼睛亮了（近景）──
TASKS[98] = dict(
    slug="zhang_eyes_light_up", seed=9724,
    ref1=G_ZHANG_ZN, ref2=SCENE, dur=2.0,
    prompt=(
        "CUT 1: 近景双人镜头，一位初中男生与那位老年男性对坐、处于同一光照环境："
        "男生眼睛一下子亮了、身体不自觉前倾，"
        "脱口追问了一句，表情是单纯的好奇与兴奋；长者看着他；"
        "两人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那节高铁餐车车厢，暖黄顶灯 + 窗外夜色；"
        + LIGHT + "。固定机位。\n"
        "Audio: 车厢底噪（后期）；"
        "男生追问：那您为什么没去？"
    ),
)

# ── 镜 99 钟南山（★ 10s，全片最长台词）──
TASKS[99] = dict(
    slug="zhong_fathers_words", seed=9725,
    ref1=G_ZHANG_ZN, ref2=SCENE, dur=10.0,
    prompt=(
        "CUT 1: 近景双人镜头，那位老年男性看着对面的初中男生，"
        "平静而缓慢地说出一段改变了他一生的话，说的时候目光是稳的、"
        "语气里没有炫耀、只有一种走过来的笃定；男生安静地听着；"
        "两人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那节高铁餐车车厢，暖黄顶灯 + 窗外夜色；"
        + LIGHT + "。镜头缓慢向前推。\n"
        "Audio: 车厢底噪与轻微的铁轨声（后期）；"
        "他缓慢地说：我父亲说，体育竞技不能成为从事一生的工作，"
        "但学医可以一辈子治病救人。"
    ),
)

# ── 镜 100 刘思齐小声问（近景）──
TASKS[100] = dict(
    slug="siqi_asks_regret", seed=9726,
    ref1=G_SIQI_ZN, ref2=SCENE, dur=2.0,
    prompt=(
        "CUT 1: 近景双人镜头，一位戴细框眼镜的初中女生与那位老年男性对坐、"
        "处于同一光照环境：女生很轻地问出一句话，"
        "声音不大、眼神里带着一点小心翼翼；长者看着她；"
        "两人的面貌、发型、眼镜与服装严格照 <Picture 1>"
        "（女生的细框眼镜必须保留）；"
        "背景是 <Picture 2> 那节高铁餐车车厢，暖黄顶灯 + 窗外夜色；"
        + LIGHT + "。固定机位。\n"
        "Audio: 车厢底噪（后期）；"
        "女生小声问：那您后悔吗？"
    ),
)

# ── 镜 101 钟南山看着她，摇头（近景）──
TASKS[101] = dict(
    slug="zhong_says_no_regret", seed=9727,
    ref1=G_SIQI_ZN, ref2=SCENE, dur=6.0,
    prompt=(
        "CUT 1: 近景双人镜头，那位老年男性看着对面的初中女生，"
        "先轻轻摇了摇头，然后平静地说出两句话，"
        "神情坦然、眼神清亮，是一种走过一生之后才有的确定；女生安静地听着；"
        "两人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那节高铁餐车车厢，暖黄顶灯 + 窗外夜色；"
        + LIGHT + "。镜头缓慢向前推。\n"
        "Audio: 车厢底噪（后期）；"
        "他摇头说：不后悔。跑步是一个人的事。治病救人是很多人的事。"
    ),
)

# ── 镜 102 武汉站到了，收拾文件，递口罩（中景；三拍动作）──
TASKS[102] = dict(
    slug="wuhan_station_hands_mask", seed=9728,
    ref1=G_SIQI_ZN, ref2=P_MASK, dur=6.0,
    prompt=(
        "CUT 1: 中景镜头，车厢开始减速、窗外掠过站台的灯光。"
        "那位老年男性先把桌上摊开的文件收拢起来叠好，"
        "然后从随身的包里取出一个浅蓝色的医用口罩，"
        "伸手递向坐在对面的那位戴细框眼镜的初中女生；"
        "女生在画面里、也在伸手去接；几个动作依次连贯完成；"
        "两人与口罩的形态严格照 <Picture 1>（女生的细框眼镜必须保留）；"
        "背景是 <Picture 2> 那节高铁餐车车厢，暖黄顶灯 + 窗外站台灯光；"
        + LIGHT + "。镜头手持轻微，随车厢到站的晃动。\n"
        + NO_SPEECH
    ),
)

# ── 镜 103 把口罩放在她手心（特写）──
TASKS[103] = dict(
    slug="mask_placed_in_palm", seed=9729,
    ref1=G_SIQI_ZN, ref2=P_MASK, dur=4.0,
    prompt=(
        "CUT 1: 特写镜头。一只年长者的手把浅蓝色的医用口罩轻轻放进"
        "一只伸出的年轻女孩的手心里；两只手在画面中央、动作很轻；"
        "口罩的形态与颜色照 <Picture 2>；两人手部与衣着严格照 <Picture 1>；"
        "背景是高铁餐车车厢的暖黄灯光、轻微虚化；"
        + LIGHT + "。镜头缓慢向前推到手部。\n"
        "Audio: 车厢底噪（后期）；"
        "长者轻声嘱咐：拿着。回去的路上，戴好。"
    ),
)

# ── 镜 104 钟南山起身走向车门，背影消失在夜色（★ 5s 情绪落点）──
TASKS[104] = dict(
    slug="zhong_walks_away_into_night", seed=9730,
    ref1=G_FOUR_ZN, ref2=SCENE, dur=5.0,
    prompt=(
        "CUT 1: 全景镜头。高铁停稳，车门打开。那位老年男性从座位上起身，"
        "提起随身的小包，穿过车厢走向打开的车门，"
        "背影一步步走远、最后消失在站台夜色的灯光里；"
        "四位初中生留在座位上、望着他的背影，没有起身；"
        + GUARD_ZN + "；"
        "四位学生的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那节高铁餐车车厢与车门外深蓝的站台夜色；"
        + LIGHT + "。镜头跟移着他的背影，随后定格。\n"
        + NO_SPEECH
    ),
)

# ── 镜 105 四人站在原地，画面泛白（全景；★ 白屏日记字转场，T2V）──
TASKS[105] = dict(
    slug="white_out_diary_card_act4", seed=9731,
    ref1=None, ref2=None, dur=5.0,
    prompt=(
        "CUT 1: 全景镜头。四位穿校服的初中生站在高铁餐车车厢里，"
        "望着车门外那个人消失的方向，一动不动；"
        "画面从两侧开始逐渐泛白、白光一点点吞没整个画面，"
        "最后画面完全变成白屏（像一个过场转场的白光收束）；"
        "四位学生的面貌、发型与服装严格照参考；"
        "背景是高铁餐车车厢的暖黄灯光；"
        + LIGHT + "。固定机位。\n"
        + NO_SPEECH
    ),
)



# ────────────────────────────────────────────────────────────── ComfyUI 基础
def _api(path, payload=None):
    url = COMFY + path
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def load_workflow(name):
    with open(os.path.join(WORKFLOW_DIR, name), "r", encoding="utf-8") as f:
        return json.load(f)


def safe_name(path):
    """input 里用 ASCII 名（LESSONS #9）。"""
    return "act4v_" + re.sub(r"[^0-9A-Za-z_.-]", "_", os.path.basename(path))


def upload_image(local_path, target_name):
    """上传到 ComfyUI input；先删同名旧文件（LESSONS #6：上传不覆盖同名文件）。"""
    stale = os.path.join(COMFY_IN, target_name)
    if os.path.exists(stale):
        os.remove(stale)
    import mimetypes
    boundary = "----act4train"
    with open(local_path, "rb") as f:
        content = f.read()
    ctype = mimetypes.guess_type(local_path)[0] or "image/png"
    body = b""
    body += ("--%s\r\n" % boundary).encode()
    body += ('Content-Disposition: form-data; name="image"; filename="%s"\r\n' % target_name).encode()
    body += ("Content-Type: %s\r\n\r\n" % ctype).encode()
    body += content + b"\r\n"
    body += ("--%s\r\n" % boundary).encode()
    body += b'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n'
    body += ("--%s--\r\n" % boundary).encode()
    req = urllib.request.Request(
        COMFY + "/upload/image", data=body,
        headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode("utf-8"))["name"]


def set_inputs(wf, class_type, **values):
    """按 class_type 注入参数（复刻 MCP 的 _set_inputs），返回命中数。"""
    hits = 0
    for node in wf.values():
        if node.get("class_type") == class_type:
            node.setdefault("inputs", {}).update(values)
            hits += 1
    return hits


def build_video_wf(task, ref1_name, ref2_name, megapixels, steps, prefix):
    """复刻 MCP video_minimax_h3_r2v / t2v 的注入逻辑。"""
    n_load = 0
    if task["ref1"] is not None:
        wf = load_workflow(WF_R2V)
        set_inputs(wf, "PrimitiveStringMultiline", value=task["prompt"])
        # LoadImage 节点：按 node id 升序 → ref_image_0 / ref_image_1
        load_nodes = sorted(
            (nid for nid, n in wf.items() if n.get("class_type") == "LoadImage"),
            key=lambda x: int(x))
        if len(load_nodes) >= 1:
            wf[load_nodes[0]]["inputs"]["image"] = ref1_name
        if len(load_nodes) >= 2:
            wf[load_nodes[1]]["inputs"]["image"] = ref2_name or ref1_name
        kind = "R2V"
        n_load = len(load_nodes)
    else:
        wf = load_workflow(WF_T2V)
        set_inputs(wf, "MiniMaxH3ImageToVideo", prompt=task["prompt"])
        kind = "T2V"

    # _apply_h3_common
    set_inputs(wf, "PrimitiveFloat", value=float(task["dur"]))
    set_inputs(wf, "RandomNoise", noise_seed=task["seed"])
    set_inputs(wf, "ResolutionSelector",
               aspect_ratio="16:9 (Widescreen)", megapixels=float(megapixels))
    set_inputs(wf, "BasicScheduler", steps=int(steps))
    set_inputs(wf, "SaveVideo", filename_prefix=prefix)
    return wf, kind, n_load


def wait_for(prompt_id, timeout):
    """轮询 /history 直到出现 outputs 或 error。返回 (entry, status)。"""
    t0 = time.time()
    last = ""
    while time.time() - t0 < timeout:
        try:
            h = _api("/history/" + prompt_id)
        except Exception:
            h = {}
        entry = h.get(prompt_id)
        if entry:
            st = (entry.get("status") or {}).get("status_str")
            if (entry.get("outputs") or st == "error") and st != "running":
                return entry, (st or "done")
        try:
            q = _api("/queue")
            run = len(q.get("queue_running") or [])
            pend = len(q.get("queue_pending") or [])
            line = " ... 运行中=%d 排队=%d  %.0f s" % (run, pend, time.time() - t0)
        except Exception:
            line = " ... %.0f s" % (time.time() - t0)
        if line != last:
            print(line, flush=True)
            last = line
        time.sleep(15)
    return None, "timeout"



def probe(path):
    """用 ffprobe 实测规格（LESSONS #7：不要相信注释里的分辨率）。"""
    exe = shutil.which("ffprobe") or "ffprobe"
    try:
        out = subprocess.run(
            [exe, "-v", "error", "-show_entries",
             "format=duration:stream=index,codec_type,codec_name,width,height,sample_rate,channels",
             "-of", "json", path],
            capture_output=True, text=True, timeout=60)
        if out.returncode != 0:
            return dict(error=(out.stderr or "")[:200])
        d = json.loads(out.stdout)
        info = {"duration": round(float(d["format"]["duration"]), 2), "kb": round(
            os.path.getsize(path) / 1024.0, 1)}
        for s in d.get("streams", []):
            if s.get("codec_type") == "video":
                info["w"] = s.get("width")
                info["h"] = s.get("height")
                info["vcodec"] = s.get("codec_name")
            elif s.get("codec_type") == "audio":
                info["acodec"] = s.get("codec_name")
                info["sr"] = s.get("sample_rate")
                info["ch"] = s.get("channels")
        return info
    except Exception as e:
        return dict(error=str(e)[:200])


def run_shot(shot, dry=False, megapixels=0.6, steps=20, timeout=3600):
    task = dict(TASKS[shot])
    # ★ 音频三层分工（README §4.4）：剔掉「音效：（后期）」，只把 L1 台词交给 H3
    task["prompt"] = strip_late_audio(task["prompt"])
    print("=" * 72)
    print("[镜 %d] %s | seed %d | 时长 %.0fs | %s" % (
        shot, task["slug"], task["seed"], task["dur"],
        "T2V（无角色）" if task["ref1"] is None else
        "R2V | <Picture 1> = %s" % os.path.basename(task["ref1"])))
    if dry:
        print("  ref2 = %s" % (os.path.basename(task["ref2"]) if task["ref2"] else "-"))
        print("  prompt = %s..." % task["prompt"][:70])
        return (shot, "DRY", "")

    ref1_name = ref2_name = None
    for key in ("ref1", "ref2"):
        p = task[key]
        if p is None:
            continue
        if not os.path.exists(p):
            print("  [X] 参考图不存在：%s" % p)
            return (shot, "MISSING_REF", p)
        nm = upload_image(p, safe_name(p))
        print("  %s 上传 -> %s" % (os.path.basename(p), nm))
        if key == "ref1":
            ref1_name = nm
        else:
            ref2_name = nm

    prefix = "act4vs10/%02d_%s" % (shot, task["slug"])
    wf, kind, n_load = build_video_wf(task, ref1_name, ref2_name,
                                      megapixels, steps, prefix)
    print("  注入：wf=%s kind=%s LoadImage节点=%d megapixels=%.2f steps=%d prompt字数=%d" % (
        WF_R2V if task["ref1"] is not None else WF_T2V, kind, n_load,
        megapixels, steps, len(task["prompt"])))

    t0 = time.time()
    try:
        r = _api("/prompt", {"prompt": wf, "client_id": CLIENT_ID})
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:900]
        print("  [X] 提交失败 %s\n%s" % (e.code, detail))
        return (shot, "SUBMIT_FAIL", detail[:200])
    pid = r["prompt_id"]
    print("  已提交 prompt_id=%s" % pid)

    entry, st = wait_for(pid, timeout=timeout)
    dt = time.time() - t0
    if entry is None:
        print("  [!] 等待超时（任务可能仍在跑）prompt_id=%s" % pid)
        return (shot, "TIMEOUT", pid)
    if st == "error":
        msg = json.dumps(entry.get("status", {}), ensure_ascii=False)[:600]
        print("  [X] 执行报错：%s" % msg)
        return (shot, "ERROR", msg[:200])

    files = []
    for node_out in entry.get("outputs", {}).values():
        for key in ("videos", "gifs", "images", "audio"):
            for it in node_out.get(key) or []:
                src = os.path.join(COMFY_OUT, it.get("subfolder", ""), it["filename"])
                if not os.path.exists(src):
                    continue
                dst = os.path.join(OUT_ROOT, it["filename"])
                shutil.copy2(src, dst)
                v = probe(dst)
                flag = "OK" if "error" not in v and v.get("w") else "SUSPECT"
                extra = ("%sx%s %s | %.2fs %s %sHz %sch | %.0fKB" % (
                    v.get("w"), v.get("h"), v.get("vcodec", "?"),
                    v.get("duration", -1), v.get("acodec", "无音轨"),
                    v.get("sr", "-"), v.get("ch", "-"), v.get("kb", 0))
                    ) if "error" not in v else v["error"]
                print("  [%s] %s  %s  %.0f s" % (flag, it["filename"], extra, dt))
                files.append((it["filename"], flag, extra))
    if not files:
        print("  [!] history 里没有输出文件（可能被中断）")
        return (shot, "NO_OUTPUT", pid)
    return (shot, files[0][1], "%s | %s" % (files[0][0], files[0][2]))


def main():
    args = sys.argv[1:]
    dry = "--dry" in args
    args = [a for a in args if not a.startswith("--")]
    # 本幕默认 10（对话/反应镜为主）；镜 75/104 环境剧变镜可单独补 --steps=20
    steps = 10
    mp = 0.6
    for a in sys.argv[1:]:
        if a.startswith("--steps="):
            steps = int(a.split("=", 1)[1])
        elif a.startswith("--mp="):
            mp = float(a.split("=", 1)[1])
    shots = [int(a) for a in args] if args else sorted(TASKS)
    print(">>> steps=%d megapixels=%.2f shots=%s" % (steps, mp, shots))

    os.makedirs(OUT_ROOT, exist_ok=True)
    report = []
    for shot in shots:
        try:
            row = run_shot(shot, dry=dry, megapixels=mp, steps=steps)
        except Exception as e:
            row = (shot, "EXCEPTION", repr(e)[:200])
            print("  [X] 异常：%r" % e)
        report.append(row)
        with open(REPORT, "w", encoding="utf-8") as f:
            f.write("第三幕《餐车一角》视频片段 · 生成报告（跳过首帧，直接 R2V/T2V，镜 75-105）\n")
            f.write("输出目录：%s\n\n" % OUT_ROOT)
            for s, st, fn in report:
                f.write("镜 %-2d\t%-12s\t%s\n" % (s, st, fn))

    print("=" * 72)
    print("汇总：")
    for s, st, fn in report:
        print("  镜 %-2d  %-12s %s" % (s, st, fn))
    print("报告：%s" % REPORT)


if __name__ == "__main__":
    main()
