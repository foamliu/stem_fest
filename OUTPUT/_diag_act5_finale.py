# -*- coding: utf-8 -*-
"""尾声《归来与揭晓》视频批量生成（镜 106-126）—— 跳过首帧，直接「人物参考图 + 场景图」喂 H3 R2V。

⚠️ 命名说明：本幕对应 scene 目录 `05_classroom_night`，脚本名用 `act5_finale`。
   全片映射见 `_diag_act0_plane.py` 文首。

台词与镜号严格取自 `storyboard.md` §尾声：归来与揭晓（现实空间 · 傍晚，天色已暗）。

★ 本幕要点（storyboard「制作约定」明写的锚点，**不得删改**）：
  · **世界模型设定锚点**：镜 106/116/121 的**半透明全息稻谷与口罩**
    （带出模型的只有全息影像、没有实物）—— 三镜都必须画出全息投影质感
  · **尾声减话锚点**：镜 113 / 117 为**无台词**反应镜；
    镜 117 的「科技要为人民服务」改为**屏幕字幕**呈现（不是台词）；
    镜 118 的「德才兼备。德是知道学一身本事为了谁」是**全片最后一句台词**
  · 镜 106 是**幕首建立镜**（回教室 + 天色已暗 + 双手托全息稻谷口罩），人工锁定 5s
  · 镜 109 三拍动作：打开电脑 + 照片弹出 + 手停在键盘（含一顿），6s
  · 镜 122「如愿·看见」片名揭晓 / 123-124 黑屏字幕 / 125 三帧静帧 / 126 定格 —— 全是刻意留白

⚠️ steps：默认 **10**；镜 123/124/125/126 为**纯字幕 / 静帧 / 定格**镜，
   画面几乎不动 ⇒ 可降到 **4**（见脚本末尾 STEPS_LOW 说明，用 `--steps=4 123 124 125 126`）。

⚠️ 音频（README §4.4）：本幕大量「音效：（后期）」；镜 106/109/110/111/113/117/119/120/121/122
   等无台词镜全部挂 NO_SPEECH。
   ⚠️ 镜 123/124 含**歌词**与**《如愿》前奏**，属后期音乐（不进 H3 prompt）。

用法：
    py -3.10 OUTPUT/_diag_act5_finale.py --dry                # 只看任务清单
    py -3.10 OUTPUT/_diag_act5_finale.py --steps=10           # 全量（默认 10）
    py -3.10 OUTPUT/_diag_act5_finale.py --steps=4 123 124 125 126  # 字幕/静帧镜提速
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
OUT_ROOT = os.path.join(ROOT, "OUTPUT", "05_classroom_night", "video")
REPORT = os.path.join(ROOT, "OUTPUT", "_act5_finale_report.txt")
CLIENT_ID = "act5v_finale"

FRAMES = os.path.join(ROOT, "ASSETS", "CHARACTERS")
SCENES = os.path.join(ROOT, "ASSETS", "SCENES")
PROPS = os.path.join(ROOT, "ASSETS", "PROPS")

WF_R2V = "video_minimax_h3_r2v.json"
WF_T2V = "video_minimax_h3_t2v.json"

# 尾声统一光线基调（storyboard：现实只过了一小会儿，天色已暗，深蓝 + 橙红、屏幕光打脸）
LIGHT = (
    "傍晚的教室，窗外天色已暗下来，是深蓝与橙红交界的暮色；"
    "室内没有开主灯，只有电脑屏幕的冷白光打在孩子们脸上，"
    "画面是深蓝暖橙的对比色调，安静而有重量"
)

SCENE = os.path.join(SCENES, "05_classroom_night", "classroom_night_wide_v01.png")

# ── 角色参考图 ────────────────────────────────────────────
P_ZHANG = os.path.join(FRAMES, "04_zhang_shuyang", "zhang_shuyang_hero_v01.png")

# ── 合影参考图（R2V 硬前提；一律用不带标签的 hero_v01）──
G_FOUR = os.path.join(FRAMES, "_group", "four_students_hero_v02.png")
G_SICHENG_ZHANG = os.path.join(FRAMES, "_group", "liu_sicheng_zhang_shuyang_hero_v01.png")

# ── 道具参考图 ────────────────────────────────────────────
P_LAPTOP = os.path.join(PROPS, "08_laptop", "laptop_hero_v03.png")
P_HOLO_SCREEN = os.path.join(PROPS, "03_holo_screen", "holo_screen_hero_v01.png")
P_RICE_GRAIN = os.path.join(PROPS, "06_rice_grain", "rice_grain_hero_v01.png")
P_MASK = os.path.join(PROPS, "07_mask", "mask_hero_v02.png")
P_PLANE = os.path.join(PROPS, "01_paper_plane", "paper_plane_hero_v01.png")
P_PHOTO_HUANG = os.path.join(PROPS, "09_photo_huang_jiguang", "photo_huang_jiguang_hero_v02.png")

# 无台词镜的通用禁语音后缀（README §4.4）
NO_SPEECH = (
    "Audio: 安静教室的夜晚环境底噪；笔记本电脑散热风扇的轻微运转声；"
    "衣料摩擦声与呼吸声。"
)

# ★ 音频三层分工（README §4.4）：带「（后期）」的音效不进 H3 prompt
LATE_MARK = "（后期）"


def strip_late_audio(text):
    """把「…（后期）」这类后期音效从句子里剔除，只留 L1 台词给 H3。"""
    import re as _re
    out = []
    for sent in _re.split(r"(?<=[；。])|\n", text):
        if LATE_MARK in sent:
            continue
        out.append(sent)
    return "".join(out).strip()


# 造型护栏（README §6.1 #1：定妆照 = 外形唯一权威）
GUARD_GLASSES = "（**细框眼镜必须保留**）"

TASKS = {}


# ── 镜 106 幕首建立镜：回教室 + 双手托全息稻谷口罩（★ 世界模型锚点，5s）──
TASKS[106] = dict(
    slug="back_to_classroom_holo_in_hands", seed=9801,
    ref1=G_FOUR, ref2=SCENE, dur=5.0,
    prompt=(
        "CUT 1: 全景镜头。四位穿校服的初中生回到了教室里，窗外天色已经暗下来。"
        "一位戴细框眼镜的女生站在课桌旁，双手掌心向上托着两样**半透明的、"
        "微微发着蓝白色光的全息投影**：一束稻穗和一个口罩；"
        "影像悬浮在她手心上方轻轻浮动、明显是光的投影而不是实物；"
        "另外三位同学围在她旁边、都看着那两样全息影像；"
        "四人的面貌、发型、眼镜与服装严格照 <Picture 1>（**细框眼镜必须保留**）；"
        "背景是 <Picture 2> 那间傍晚已暗的教室：米色课桌椅、蓝色墙报、"
        "窗外是深蓝橙红的暮色；"
        + LIGHT + "。镜头缓慢向前推。\n"
        + NO_SPEECH
    ),
)

# ── 镜 107 刘思齐擦掉眼泪（近景）──
TASKS[107] = dict(
    slug="siqi_wipes_tears", seed=9802,
    ref1=G_FOUR, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 近景镜头。一位戴细框眼镜的初中女生抬手用手背擦掉脸上的眼泪，"
        "动作很快、像不想被人看见，擦完抬起头、眼神变得坚定；"
        "**身后和身旁还站着另外三位同学，他们只入画一部分**；"
        "四人的面貌、发型、眼镜与服装严格照 <Picture 1>（**细框眼镜必须保留**）；"
        "背景是 <Picture 2> 那间傍晚已暗的教室，只有屏幕的冷白光；"
        + LIGHT + "。镜头缓慢向前推。\n"
        "Audio: 教室安静底噪、窗外蝉鸣（后期）；"
        "女生擦掉眼泪、坚定地说：我们要把看到的，做成视频。"
    ),
)

# ── 镜 108 徐畅景点头（近景）──
TASKS[108] = dict(
    slug="xu_nods_let_everyone_see", seed=9803,
    ref1=G_FOUR, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 近景镜头。一位初中男生看着说话的女生，认真地点了点头，"
        "然后简短地补了一句，语气很稳；"
        "**身后和身旁还站着另外三位同学，他们只入画一部分**；"
        "四人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那间傍晚已暗的教室，只有屏幕的冷白光；"
        + LIGHT + "。固定机位。\n"
        "Audio: 教室安静底噪（后期）；"
        "男生点头说：让所有人都看见。"
    ),
)

# ── 镜 109 张书扬打开电脑，照片弹出，手停在键盘（★ 三拍动作，6s）──
TASKS[109] = dict(
    slug="zhang_opens_laptop_photo_pops", seed=9804,
    ref1=G_FOUR, ref2=P_LAPTOP, dur=6.0,
    prompt=(
        "CUT 1: 中景镜头。一位初中男生在课桌前打开笔记本电脑，"
        "屏幕亮起、一张**人物照片**在屏幕上弹出来，"
        "他伸向键盘的手**停在半空、没有敲下去**，整个人顿住；"
        "笔记本的屏幕与机身照 <Picture 2>，屏幕左下角要显示一行小字"
        "「世界模型 · 训练日志」；"
        "**身后和身旁还站着另外三位同学，他们看着屏幕、只入画一部分**；"
        "四人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是那间傍晚已暗的教室；"
        + LIGHT + "。镜头缓慢向前推，照片弹出时轻微一顿。\n"
        + NO_SPEECH
    ),
)

# ── 镜 110 张书扬震惊（特写，无台词）──
TASKS[110] = dict(
    slug="zhang_shocked_closeup", seed=9805,
    ref1=G_FOUR, ref2=SCENE, dur=2.0,
    prompt=(
        "CUT 1: 特写镜头。一位初中男生的脸几乎占满画面，"
        "他正盯着眼前的屏幕，眼睛睁大、瞳孔收缩，嘴唇微微张开、"
        "下巴绷紧、整个人僵住不动；"
        "**身后三位同学作为虚化的背景、只入画一部分**；"
        "四人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那间傍晚已暗的教室，冷白的屏幕光打在他脸上；"
        + LIGHT + "。镜头较快地缓慢向前推。\n"
        + NO_SPEECH
    ),
)

# ── 镜 111 三人围过来，没人说话（全景，无台词）──
TASKS[111] = dict(
    slug="three_gather_no_one_speaks", seed=9806,
    ref1=G_FOUR, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 全景镜头。另外三位同学慢慢围到电脑前，四个人一起看着屏幕，"
        "四人的肩膀紧挨着、组成了一个紧凑的环形站位；"
        "四人都完整入画、处于同一个连续空间；"
        "四人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那间傍晚已暗的教室：米色课桌椅、蓝色墙报、窗外暮色；"
        + LIGHT + "。镜头缓慢向后拉。\n"
        + NO_SPEECH
    ),
)

# ── 镜 112 张书扬轻声（近景）──
TASKS[112] = dict(
    slug="zhang_quotes_the_question", seed=9807,
    ref1=G_FOUR, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 近景镜头。一位初中男生看着屏幕，声音很轻地念出一句话，"
        "表情是压着的难过与郑重；"
        "**身后和身旁还站着另外三位同学，他们只入画一部分**；"
        "四人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那间傍晚已暗的教室，冷白的屏幕光；"
        + LIGHT + "。镜头缓慢向前推。\n"
        "Audio: 教室安静底噪（后期）；"
        "男生轻声说：他问我们……“咱们国家现在啥样了”。"
    ),
)

# ── 镜 113 刘思齐看着照片，没有台词（★ 减话锚点，2s）──
TASKS[113] = dict(
    slug="siqi_looks_at_photo_silent", seed=9808,
    ref1=G_FOUR, ref2=SCENE, dur=2.0,
    prompt=(
        "CUT 1: 近景镜头。一位戴细框眼镜的初中女生看着屏幕上的照片，"
        "眼眶泛红、下唇轻抿、她眨了眨眼把泪忍了回去，"
        "镜头就停在她的脸上；"
        "**身后三位同学作为虚化的背景、只入画一部分**；"
        "四人的面貌、发型、眼镜与服装严格照 <Picture 1>（**细框眼镜必须保留**）；"
        "背景是 <Picture 2> 那间傍晚已暗的教室；"
        + LIGHT + "。固定机位（静默节拍、镜头停住）。\n"
        + NO_SPEECH
    ),
)

# ── 镜 114 刘思成看着屏幕，补了一句（近景）──
TASKS[114] = dict(
    slug="sicheng_adds_a_line", seed=9809,
    ref1=G_FOUR, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 近景镜头。一位戴细框眼镜的初中女生看着屏幕，"
        "语气平静、语速不快；"
        "**身后和身旁还站着另外三位同学，他们只入画一部分**；"
        "四人的面貌、发型、眼镜与服装严格照 <Picture 1>（**细框眼镜必须保留**）；"
        "背景是 <Picture 2> 那间傍晚已暗的教室，冷白的屏幕光；"
        + LIGHT + "。固定机位。\n"
        "Audio: 教室安静底噪（后期）；"
        "女生补了一句：后来有人回答了。在稻田里。也在餐车里。"
    ),
)

# ── 镜 115 刘思成摇头，把话说透（近景）──
TASKS[115] = dict(
    slug="sicheng_explains_the_point", seed=9810,
    ref1=G_FOUR, ref2=SCENE, dur=6.0,
    prompt=(
        "CUT 1: 近景镜头。一位戴细框眼镜的初中女生轻轻摇了摇头，"
        "把话往下说透，神情认真、语气不快但很清楚；"
        "**身后和身旁还站着另外三位同学，他们只入画一部分**；"
        "四人的面貌、发型、眼镜与服装严格照 <Picture 1>（**细框眼镜必须保留**）；"
        "背景是 <Picture 2> 那间傍晚已暗的教室，冷白的屏幕光；"
        + LIGHT + "。镜头缓慢向前推。\n"
        "Audio: 教室安静底噪（后期）；"
        "女生摇头说：不只是看见。他们想知道，自己做的事，有没有结果。"
    ),
)

# ── 镜 116 刘思齐摊开双手，全息稻谷口罩浮在手心（★ 世界模型锚点，8s）──
TASKS[116] = dict(
    slug="siqi_holds_holo_and_speaks", seed=9811,
    ref1=G_FOUR, ref2=SCENE, dur=8.0,
    prompt=(
        "CUT 1: 特写镜头，镜头缓慢推到手部。一位戴细框眼镜的初中女生摊开双手，"
        "**一束半透明的稻穗与一个口罩以全息投影的形态悬浮在她手心上方**，"
        "发着淡淡的蓝白色光、边缘微微透亮、能看出是光而不是实物；"
        "她低头看着手心的影像、一字一句地说出一段话；"
        "**她身后还站着另外三位同学、作为虚化的背景**；"
        "四人的面貌、发型、眼镜与服装严格照 <Picture 1>（**细框眼镜必须保留**）；"
        "背景是那间傍晚已暗的教室；"
        + LIGHT + "。镜头缓慢向前推到手部。\n"
        "Audio: 教室安静底噪（后期）；"
        "女生说：他们本来可以选别的，但他们选了让别人能吃饱、能出门、能活着。"
    ),
)

# ── 镜 117 徐畅景站起看全息屏，屏幕字幕（★ 减话锚点：字幕不是台词，4s）──
TASKS[117] = dict(
    slug="xu_stands_holo_subtitle", seed=9812,
    ref1=G_FOUR, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 中景镜头。一位初中男生从座位上站起来，抬头看着面前的**全息屏幕**，"
        "站姿笔直、双手自然垂下；"
        "全息屏幕上清晰地映出一行发光的中文字幕：**「科技要为人民服务。」**，"
        "这行字悬浮在半空、是画面视觉重心、字形完整清晰；"
        "**身后和身旁还站着另外三位同学、只入画一部分**；"
        "四人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是那间傍晚已暗的教室；"
        + LIGHT + "。固定机位，镜头轻微上摇。\n"
        + NO_SPEECH
    ),
)

# ── 镜 118 刘思齐停顿一下，轻声（★ 全片最后一句台词，6s）──
TASKS[118] = dict(
    slug="siqi_final_line", seed=9813,
    ref1=G_FOUR, ref2=SCENE, dur=6.0,
    prompt=(
        "CUT 1: 特写镜头。一位戴细框眼镜的初中女生的脸占满画面，"
        "她先停顿了一下、轻轻吸了一口气，然后声音很轻但很清楚地说出一句话；"
        "**身后三位同学作为虚化的背景**；"
        "四人的面貌、发型、眼镜与服装严格照 <Picture 1>（**细框眼镜必须保留**）；"
        "背景是那间傍晚已暗的教室，冷白的屏幕光打在她脸上；"
        + LIGHT + "。镜头缓慢向前推。\n"
        "Audio: 教室安静底噪（后期）；"
        "女生停顿一下、轻声说：德才兼备。德是知道学一身本事为了谁。"
    ),
)

# ── 镜 119 张书扬侧头看刘思成；刘思成点头（固定双人，无台词）──
TASKS[119] = dict(
    slug="zhang_glances_sicheng_nods", seed=9814,
    ref1=G_SICHENG_ZHANG, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 中近景双人镜头，两位初中生并排站在课桌旁、处于同一光照环境、"
        "是一个完整连续的空间：一位男生停了一下，侧过头看向身旁的女生；"
        "那位女生很轻地点了一下头作为回应，两人没有说话，但彼此都懂了；"
        "两人的面貌、发型、眼镜与服装严格照 <Picture 1>"
        "（**女生的细框眼镜必须保留**）；"
        "背景是那间傍晚已暗的教室，冷白的屏幕光；"
        + LIGHT + "。固定双人机位。\n"
        + NO_SPEECH
    ),
)

# ── 镜 120 张书扬嘴角微扬，敲下第一个键（特写，无台词，5s）──
TASKS[120] = dict(
    slug="zhang_presses_first_key", seed=9815,
    ref1=G_FOUR, ref2=SCENE, dur=5.0,
    prompt=(
        "CUT 1: 特写镜头，镜头缓慢推到手部。一位男生坐在笔记本电脑前，"
        "嘴角慢慢向上扬了一下、眼神落定，然后抬起手、"
        "用食指轻轻敲下了键盘上的第一个键；"
        "**他身后三位同学作为虚化的背景**；"
        "四人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是那间傍晚已暗的教室，屏幕的冷白光；"
        + LIGHT + "。镜头缓慢向前推到手部。\n"
        + NO_SPEECH
    ),
)

# ── 镜 121 四人围在电脑前（★ 世界模型锚点：全息仍在，4s）──
TASKS[121] = dict(
    slug="four_around_laptop_holo_float", seed=9816,
    ref1=G_FOUR, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 全景镜头。四位穿校服的初中生围在课桌前的笔记本电脑旁，"
        "屏幕的光照在他们脸上、每个人都在看着屏幕；"
        "课桌角上那架白色纸飞机还在；"
        "**桌旁仍然悬浮着那两样半透明的全息投影：一束稻穗和一个口罩**，"
        "发出淡蓝色微光、轻轻浮动（是光，不是实物）；"
        "四人都完整入画、处于同一个连续空间、四人之间的间距均匀；"
        "四人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那间傍晚已暗的教室：米色课桌椅、蓝色墙报、窗外暮色；"
        + LIGHT + "。镜头缓慢向后拉。\n"
        + NO_SPEECH
    ),
)

# ── 镜 122 屏幕亮起「如愿·看见」（特写，纯物件，无台词）──
TASKS[122] = dict(
    slug="screen_shows_title", seed=9817,
    ref1=None, ref2=P_LAPTOP, dur=6.0,
    prompt=(
        "CUT 1: 特写镜头。一台笔记本电脑的屏幕在暗下来的教室里亮起来，"
        "屏幕上清晰地显示出四个发光的中文字：**「如愿·看见」**"
        "（字要清晰、居中、完整可读）；"
        "屏幕周围是那间傍晚已暗的教室，只有屏幕的光照亮周围一小片桌面；"
        "屏幕与机身照 <Picture 1>；"
        + LIGHT + "。固定机位。\n"
        + NO_SPEECH
    ),
)

# ── 镜 123 黑屏 + 三行字幕逐行浮现（★ 纯字幕，可 steps=4）──
TASKS[123] = dict(
    slug="black_screen_three_lines", seed=9818,
    ref1=None, ref2=None, dur=6.0,
    prompt=(
        "CUT 1: 纯黑背景的固定画面。黑屏上，三行白色的中文字幕依次逐行浮现，"
        "从上到下排开、居中对齐、字体干净清晰：\n"
        "第一行：🍎 一个名字，记了七十六年。\n"
        "第二行：🌾 一株稻子，找了一辈子。\n"
        "第三行：😷 一个口罩，等了三年。\n"
        "每一行浮现的动作要慢、有明显的时间间隔；"
        "背景始终是纯黑色，画面里不要出现任何人物、场景或物件。\n"
        + NO_SPEECH
    ),
)

# ── 镜 124 三行字幕淡出，最后一行字幕浮现（★ 纯字幕，可 steps=4）──
TASKS[124] = dict(
    slug="three_lines_fade_last_line", seed=9819,
    ref1=None, ref2=None, dur=6.0,
    prompt=(
        "CUT 1: 纯黑背景的固定画面。原本的三行白色字幕缓慢淡出、消失，"
        "随后黑屏中央浮现出最后两行居中的中文字：\n"
        "上汇实验学校 · 刘思齐 刘思成 徐畅景 张书扬\n"
        "谨以此片，献给所有替我们扛过的人\n"
        "字幕淡出与浮现的动作要缓慢、庄重；"
        "背景始终是纯黑色，画面里不要出现任何人物、场景或物件。\n"
        + NO_SPEECH
    ),
)

# ── 镜 125 三帧静帧依次闪过（★ 黄继光/袁隆平/钟南山各一帧，可 steps=4）──
TASKS[125] = dict(
    slug="three_stills_flash", seed=9820,
    ref1=None, ref2=None, dur=8.0,
    prompt=(
        "CUT 1: 全屏画面。三段静止画面依次出现、每段约 2-3 秒，"
        "中间用短暂的白光或黑场切换：\n"
        "第一段：一位穿 1950 年代志愿军冬装、戴红星军帽的年轻战士朝画面外挥手告别；\n"
        "第二段：一位穿中山装的中年男性弯腰把一束金黄色稻穗递向镜头；\n"
        "第三段：一位戴细框眼镜、穿浅蓝衬衫的老年男性把一个浅蓝色口罩递向镜头。\n"
        "三段都是**静态摄影般的定格画面**（不是连续运动），"
        "画面色调庄重、干净，人物居于画面中央。\n"
        + NO_SPEECH
    ),
)

# ── 镜 126 最后定格四人背影（★ 收束镜，可 steps=4）──
TASKS[126] = dict(
    slug="final_freeze_four_backs", seed=9821,
    ref1=G_FOUR, ref2=SCENE, dur=8.0,
    prompt=(
        "CUT 1: 全景镜头。四位穿校服的初中生背对着镜头、并排站在课桌前，"
        "一起看着桌上笔记本的屏幕；画面**完全定格不动**、"
        "只有窗外深蓝的夜色与被夜风吹动的窗帘有一点极缓的移动；"
        "四人的背影与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那间傍晚已暗的教室：米色课桌椅、蓝色墙报、"
        "窗外深蓝橙红的暮色；"
        + LIGHT + "。固定机位（定格收束），画面最后缓慢淡出。\n"
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
    return "act5v_" + re.sub(r"[^0-9A-Za-z_.-]", "_", os.path.basename(path))


def upload_image(local_path, target_name):
    """上传到 ComfyUI input；先删同名旧文件（LESSONS #6：上传不覆盖同名文件）。"""
    stale = os.path.join(COMFY_IN, target_name)
    if os.path.exists(stale):
        os.remove(stale)
    import mimetypes
    boundary = "----act5finale"
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

    prefix = "act5vs10/%02d_%s" % (shot, task["slug"])
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
    # 本幕默认 10；镜 123/124（纯字幕）/125（三帧静帧）/126（定格）可 --steps=4 提速
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
            f.write("尾声《归来与揭晓》视频片段 · 生成报告（跳过首帧，直接 R2V/T2V，镜 106-126）\n")
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
