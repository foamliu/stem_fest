# -*- coding: utf-8 -*-
"""第二幕《禾下乘凉》视频批量生成（镜 52-76）—— 跳过首帧，直接「人物参考图 + 场景图」喂 H3 R2V。

⚠️ 命名说明（2026-09-13 澄清）：文件里的 "act3" / `07_rice_field` 是**按 scene 目录序号**命名，
   与「第几幕」无关。全片映射如下，别再混：

       序幕一《纸飞机》  镜 1-9    → 01_paper_plane     (_diag_act1_frames.py / _diag_plane_plane_videos.py)
       序幕二《启动》    镜 10-21  → 04_classroom_dusk  (_diag_act2_startup.py)
       第一幕《上甘岭》  镜 22-51  → 06_trench
       第二幕《禾下乘凉》镜 52-76  → 07_rice_field      (本脚本 _diag_act3_rice.py)  ← ★
       第三幕《餐车一瞥》镜 77+    → 08_train_dining

   故本脚本虽然文稿里叫「第二幕」，文件名与输出目录一律用 `act3` / `07_rice_field`，
   与 `ASSETS/SCENES/07_rice_field/` 严格对齐。

台词与镜号严格取自 `storyboard.md` §第二幕：禾下乘凉（约 85 秒，1961-07 安江农校稻田）。

路线（与序幕一一致，README §7）：
  · 有角色的镜 → `video_minimax_h3_r2v`
      ref_image_1 = 角色/合影参考图 → `<Picture 1>`
      ref_image_2 = `SCENES/07_rice_field/rice_field_wide_v01.png` → `<Picture 2>`
  · 纯场景/道具镜（无角色）→ `video_minimax_h3_t2v`（本幕仅镜 57）

⚠️ 音频纪律（2026-09-13 教训）：**无台词的镜必须在 prompt 里明确写"不要出现人声"**，
   否则 H3 会自己幻觉出语音（实测镜 4 出"啊"、镜 5 出整句胡话，用 Qwen3-ASR 才查出）。

用法：
    py -3.10 OUTPUT/_diag_act3_rice.py --dry            # 只看任务清单
    py -3.10 OUTPUT/_diag_act3_rice.py --steps=20       # 全量（默认 20）
    py -3.10 OUTPUT/_diag_act3_rice.py --steps=20 52 53
"""
import json
import os
import re
import subprocess
import sys
import time
import shutil
import urllib.request

ROOT = r"E:\code\stem_fest"
COMFY = "http://127.0.0.1:8188"
COMFY_OUT = r"E:\code\ComfyUI\output"
COMFY_IN = r"E:\code\ComfyUI\input"
WORKFLOW_DIR = os.path.join(ROOT, "workflows")
OUT_ROOT = os.path.join(ROOT, "OUTPUT", "07_rice_field", "video")
REPORT = os.path.join(ROOT, "OUTPUT", "_act3_rice_report.txt")
CLIENT_ID = "act3v_rice"

FRAMES = os.path.join(ROOT, "ASSETS", "CHARACTERS")
SCENES = os.path.join(ROOT, "ASSETS", "SCENES")
PROPS = os.path.join(ROOT, "ASSETS", "PROPS")

WF_R2V = "video_minimax_h3_r2v.json"
WF_T2V = "video_minimax_h3_t2v.json"

# 第二幕统一光线基调（storyboard：1961-07 安江农校，烈日，稻田绿 + 阳光金黄）
LIGHT = "1961 年 7 月盛夏正午的烈日，阳光强烈刺眼、空气通透，稻田绿与阳光金黄，画面高饱和暖调"

SCENE_RICE = os.path.join(SCENES, "07_rice_field", "rice_field_wide_v01.png")

# 角色参考图
P_XU = os.path.join(FRAMES, "03_xu_changjing", "xu_changjing_hero_v01.png")
P_LIU_SIQI = os.path.join(FRAMES, "01_liu_siqi", "liu_siqi_hero_v01.png")
P_LIU_SICHENG = os.path.join(FRAMES, "02_liu_sicheng", "liu_sicheng_hero_v01.png")
P_ZHANG = os.path.join(FRAMES, "04_zhang_shuyang", "zhang_shuyang_hero_v01.png")
P_YUAN = os.path.join(FRAMES, "06_yuan_longping", "yuan_longping_hero_v01.png")
G_FOUR = os.path.join(FRAMES, "_group", "four_students_hero_v02.png")
G_FOUR_YUAN = os.path.join(FRAMES, "_group", "four_students_yuan_longping_hero_v01.png")
G_SIQI_YUAN = os.path.join(FRAMES, "_group", "liu_siqi_yuan_longping_hero_v01.png")

# 道具参考图（无角色镜走 T2V，prompt 里描述即可；有手部特写时用 R2V + 道具图）
P_RICE_EAR = os.path.join(PROPS, "05_rice_ear", "rice_ear_detail_v01.png")
P_RICE_GRAIN = os.path.join(PROPS, "06_rice_grain", "rice_grain_hero_v01.png")
P_RICE_PLANT = os.path.join(PROPS, "04_rice_plant", "rice_plant_hero_v01.png")

# 无台词镜的通用禁语音后缀（2026-09-13 按 README §4.4 重写）
NO_SPEECH = (
    "【本镜不要生成任何可辨认的语音或对白。只允许环境音与物件音；"
    "若画面有人群，也只是听不清的杂音，不要生成任何词句。】"
)

# ★ 音频三层分工（README §4.4）：带「（后期）」的音效不进 H3 prompt，由 ace_step_t2audio 后期铺。
LATE_MARK = "（后期）"


def strip_late_audio(text):
    """把「…（后期）」这类后期音效从句子里剔除，只留 L1 台词给 H3。

    句子边界 = `；` `。` 或换行；含 LATE_MARK 的那句整句丢掉。
    """
    import re as _re
    out = []
    for sent in _re.split(r"(?<=[；。])|\n", text):
        if LATE_MARK in sent:
            continue
        out.append(sent)
    return "".join(out).strip()

TASKS = {}

TASKS[47] = dict(
    slug="four_on_ridge_watching_yuan", seed=9552,
    ref1=G_FOUR, ref2=SCENE_RICE, dur=6.0,
    prompt=(
        "CUT 1: 中景四人镜头。四位初中生并肩站在稻田的田埂上，背对镜头略微侧身，"
        "一起望向画面远处 —— 远处有一位穿深灰中山装的中年男人正弯腰在稻田里翻找稻子；"
        "四人的面貌、发型、服装严格照 <Picture 1>；"
        "环境是 <Picture 2> 那片 1961 年 7 月盛夏的稻田：稻浪被风吹动、田埂泥土、远处农校建筑；"
        + LIGHT + "。镜头轻微向前缓推（slow dolly in），稻叶随风摆动。\n"
        "Audio: 蝉鸣、风吹稻浪的沙沙声（后期）；男生语气懒散地抱怨：热死了。"
    ),
)

TASKS[48] = dict(
    slug="xu_changjing_looks_far", seed=9553,
    ref1=P_XU, ref2=SCENE_RICE, dur=5.0,
    prompt=(
        "CUT 1: 近景半身镜头，人物占画面高度约三分之二。"
        "一位初中男生手搭凉棚、眯眼望向画面远处的稻田；"
        "他的面貌、发型、服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那片盛夏的稻田：绿色稻浪、远处田埂与农校建筑，画面因烈日而明亮；"
        + LIGHT + "。镜头轻微横移（slow lateral move）。\n"
        "Audio: 蝉鸣与风吹稻浪声（后期）；男生缓缓地说：安江农校。1961年。"
    ),
)


TASKS[49] = dict(
    slug="liu_siqi_shrinks_back", seed=9554,
    ref1=P_LIU_SIQI, ref2=SCENE_RICE, dur=5.0,
    prompt=(
        "CUT 1: 近景半身镜头，人物占画面高度约三分之二。"
        "一位戴细框眼镜的初中女生往田埂边微微缩了缩、身体略向后，神情好奇又有点戒备，"
        "眼睛看向画面外的远处；"
        "她的面貌、发型、眼镜与服装严格照 <Picture 1>（**细框眼镜必须保留**）；"
        "背景是 <Picture 2> 那片盛夏稻田的田埂与绿色稻浪；"
        + LIGHT + "。镜头轻微向前缓推（slow dolly in）。\n"
        "Audio: 蝉鸣、稻浪声（后期）；女生小声地问：那个人在干什么？"
    ),
)

TASKS[50] = dict(
    slug="yuan_bending_looking_for_rice", seed=9555,
    ref1=P_YUAN, ref2=SCENE_RICE, dur=6.0,
    prompt=(
        "CUT 1: 中景镜头，一位穿深灰中山装的中年男人弯腰在稻田里，"
        "一株一株地拨开稻叶仔细查看稻穗，汗珠从额头滴落进泥水里；神情专注、不急不躁；"
        "他的面貌、发型与服装严格照 <Picture 1>；"
        "环境是 <Picture 2> 那片盛夏稻田，稻叶茂密、泥水反光；"
        + LIGHT + "。镜头缓慢跟随他弯下的身体轻微下移（slow tilt down then hold）。\n"
        "Audio: " + NO_SPEECH
    ),
)

TASKS[51] = dict(
    slug="liu_sicheng_staring", seed=9556,
    ref1=P_LIU_SICHENG, ref2=SCENE_RICE, dur=5.0,
    prompt=(
        "CUT 1: 近景半身镜头，人物占画面高度约三分之二。"
        "一位戴细框眼镜的初中女生定定地望着画面外的方向（正看向远处弯腰找稻的人），"
        "眼神专注、微微眯眼；"
        "她的面貌、发型、眼镜与服装严格照 <Picture 1>（**细框眼镜必须保留**）；"
        "背景是 <Picture 2> 那片盛夏稻田，绿稻与明亮天光虚化在后；"
        + LIGHT + "。镜头轻微横移（slow lateral move）。\n"
        "Audio: 蝉鸣、稻浪声（后期）；女生认真地说：他在找东西。一株一株地找。"
    ),
)

TASKS[52] = dict(
    slug="rice_plant_eyes_light_up", seed=9557,
    ref1=None, ref2=None, dur=6.0,
    prompt=(
        "CUT 1: 稻株特写。一株水稻被一只手轻轻拨开叶片，露出饱满的稻穗；"
        "叶片上还挂着水光，稻穗颗粒分明；镜头从叶片缝隙缓缓推进，"
        "焦点从叶片落到稻穗上（rack focus），画面主体是这株稻子与那只手的一部分；"
        "环境阳光穿过稻叶、在画面里留下斑驳的光点；" + LIGHT + "。\n"
        "Audio: " + NO_SPEECH
    ),
)

TASKS[53] = dict(
    slug="yuan_touches_rice_ear", seed=9558,
    ref1=P_YUAN, ref2=SCENE_RICE, dur=5.0,
    prompt=(
        "CUT 1: 近景，一位穿深灰中山装的中年男人用手掌轻轻抚摸一株稻穗，"
        "手指缓缓从穗尖滑过，眼神一下子亮了起来、嘴角微微上扬；"
        "他的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那片盛夏稻田的绿色虚化；"
        + LIGHT + "。镜头轻微向前缓推（slow dolly in）到他的手与稻穗。\n"
        "Audio: 蝉鸣与稻浪声（后期）；他低声而笃定地说：找到了。"
    ),
)

TASKS[54] = dict(
    slug="yuan_stands_waves_them_over", seed=9559,
    ref1=G_FOUR_YUAN, ref2=SCENE_RICE, dur=6.0,
    prompt=(
        "CUT 1: 中景镜头。一位穿深灰中山装的中年男人从稻田里直起腰，"
        "转头看见站在田埂上的四位初中生，抬手向他们招呼、示意走近，脸上带着朴实的笑；"
        "五人的面貌、发型与服装严格照 <Picture 1>；"
        "环境是 <Picture 2> 那片盛夏稻田，他站在稻丛中、四人在田埂上；"
        + LIGHT + "。镜头轻微横移（slow lateral move）把他与田埂上的四人一并纳入。\n"
        "Audio: 蝉鸣、稻浪声（后期）；他用带口音的普通话爽朗地说：过来嘛，站那么远做啥子？"
    ),
)

TASKS[55] = dict(
    slug="yuan_pulls_normal_rice", seed=9560,
    ref1=P_YUAN, ref2=SCENE_RICE, dur=6.0,
    prompt=(
        "CUT 1: 中近景。一位穿深灰中山装的中年男人从田里拔起一株普通稻子，"
        "举在身前给画面外的人看，另一只手指着稻穗，神情认真地讲解；"
        "他的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那片盛夏稻田；" + LIGHT + "。镜头轻微向前缓推（slow dolly in）。\n"
        "Audio: 蝉鸣、稻浪声（后期）；他说：你们看，这是普通稻子。"
    ),
)

TASKS[56] = dict(
    slug="yuan_points_marked_ear", seed=9561,
    ref1=P_YUAN, ref2=SCENE_RICE, dur=5.0,
    prompt=(
        "CUT 1: 中近景。一位穿深灰中山装的中年男人伸手指向稻田里一株系着浅色布条的稻穗，"
        "神情郑重；画面中那株稻子比其他稻子明显高大、穗子更饱满，布条随风轻动；"
        "他的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那片盛夏稻田；" + LIGHT + "。镜头轻微向前缓推（slow dolly in）。\n"
        "Audio: 蝉鸣、稻浪声（后期）；他缓缓地说：那株，我找了三年才找到。"
    ),
)

TASKS[57] = dict(
    slug="zhang_shuyang_leans_in", seed=9562,
    ref1=P_ZHANG, ref2=SCENE_RICE, dur=5.0,
    prompt=(
        "CUT 1: 近景半身镜头，人物占画面高度约三分之二。"
        "一位初中男生凑近画面外的那株稻穗仔细看，眉毛挑起、表情惊讶好奇，"
        "一只手撑在膝盖上、身体前倾；"
        "他的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那片盛夏稻田的绿色虚化；"
        + LIGHT + "。镜头轻微向前缓推（slow dolly in）。\n"
        "Audio: 蝉鸣、稻浪声（后期）；男生惊讶地问：您找了三年？就为了一株稻子？"
    ),
)

TASKS[58] = dict(
    slug="yuan_asks_if_they_ate", seed=9563,
    ref1=P_YUAN, ref2=SCENE_RICE, dur=6.0,
    prompt=(
        "CUT 1: 近景半身镜头，人物占画面高度约三分之二。"
        "一位穿深灰中山装的中年男人笑着看向画面外，笑容憨厚、眼角有细纹，"
        "手里还捏着一株稻穗；"
        "他的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那片盛夏稻田的绿色虚化；"
        + LIGHT + "。镜头轻微横移（slow lateral move）。\n"
        "Audio: 蝉鸣、稻浪声（后期）；他随口问道：你们吃饭了没？"
    ),
)

TASKS[59] = dict(
    slug="liu_siqi_answers_quietly", seed=9564,
    ref1=P_LIU_SIQI, ref2=SCENE_RICE, dur=5.0,
    prompt=(
        "CUT 1: 近景半身镜头，人物占画面高度约三分之二。"
        "一位戴细框眼镜的初中女生低着头、小声回答，神情有点拘谨，"
        "手指微微攥着衣角；"
        "她的面貌、发型、眼镜与服装严格照 <Picture 1>（**细框眼镜必须保留**）；"
        "背景是 <Picture 2> 那片盛夏稻田的绿色虚化；"
        + LIGHT + "。镜头轻微向前缓推（slow dolly in）。\n"
        "Audio: 蝉鸣、稻浪声（后期）；女生小声地说：吃了。"
    ),
)

TASKS[60] = dict(
    slug="yuan_talks_about_hungry_people", seed=9565,
    ref1=P_YUAN, ref2=SCENE_RICE, dur=6.0,
    prompt=(
        "CUT 1: 近景，一位穿深灰中山装的中年男人点点头，目光望向稻田远方，"
        "神情平静而认真，说话时语气很轻；"
        "他的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那片盛夏稻田，稻浪在风里起伏；"
        + LIGHT + "。镜头轻微向前缓推（slow dolly in）。\n"
        "Audio: 蝉鸣、稻浪声（后期）；他平静地说：那就好。我以前见过饿倒的人。所以想让稻子多结一点。"
    ),
)

TASKS[61] = dict(
    slug="liu_sicheng_blurts_out", seed=9566,
    ref1=P_LIU_SICHENG, ref2=SCENE_RICE, dur=5.0,
    prompt=(
        "CUT 1: 近景半身镜头，人物占画面高度约三分之二。"
        "一位戴细框眼镜的初中女生脱口而出、刚开口就顿住，神情有点慌张又有点激动；"
        "她的面貌、发型、眼镜与服装严格照 <Picture 1>（**细框眼镜必须保留**）；"
        "背景是 <Picture 2> 那片盛夏稻田的绿色虚化；"
        + LIGHT + "。镜头轻微横移（slow lateral move）。\n"
        "Audio: 蝉鸣、稻浪声（后期）；女生脱口而出：袁爷爷……"
    ),
)

TASKS[62] = dict(
    slug="yuan_is_startled", seed=9567,
    ref1=P_YUAN, ref2=SCENE_RICE, dur=5.0,
    prompt=(
        "CUT 1: 近景，一位穿深灰中山装的中年男人愣了一下，动作停住、"
        "眉毛微微抬起、眼神里带着困惑，侧头看向画面外；"
        "他的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那片盛夏稻田的绿色虚化；"
        + LIGHT + "。镜头轻微向前缓推（slow dolly in）。\n"
        "Audio: 蝉鸣、稻浪声（后期）；他疑惑地问：你叫我啥子？"
    ),
)

TASKS[63] = dict(
    slug="liu_sicheng_confesses", seed=9568,
    ref1=G_FOUR_YUAN, ref2=SCENE_RICE, dur=6.0,
    prompt=(
        "CUT 1: 中景双人镜头，一位戴细框眼镜的初中女生与一位穿深灰中山装的中年男人"
        "面对面站在稻田里，女生仰头认真地说着什么、神情坦诚，男人微微低头听着、表情一怔；"
        "两人的面貌、发型、眼镜与服装严格照 <Picture 1>（**眼镜必须保留**）；"
        "背景是 <Picture 2> 那片盛夏稻田，绿稻与天光；"
        + LIGHT + "。镜头轻微横移（slow lateral move），两人处于同一光照环境、画面是完整连续的空间。\n"
        "Audio: 蝉鸣、稻浪声（后期）；女生认真地说：袁隆平爷爷。我们是从未来来的。"
    ),
)

TASKS[64] = dict(
    slug="yuan_silent_looks_at_kids", seed=9569,
    ref1=P_YUAN, ref2=SCENE_RICE, dur=6.0,
    prompt=(
        "CUT 1: 近景，一位穿深灰中山装的中年男人一时沉默：先低头看了看手里的稻子，"
        "再缓缓抬起头，目光认真地看向画面外的孩子们；他的表情复杂、安静，没有说活的动作；"
        "他的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那片盛夏稻田，稻浪在风里起伏；"
        + LIGHT + "。镜头极缓慢地向前推进（very slow dolly in）。\n"
        "Audio: 只有稻浪声与蝉鸣（后期）。" + NO_SPEECH
    ),
)



TASKS[65] = dict(
    slug="yuan_asks_if_they_are_fed", seed=9570,
    ref1=P_YUAN, ref2=SCENE_RICE, dur=5.0,
    prompt=(
        "CUT 1: 近景，一位穿深灰中山装的中年男人迟疑地开口，"
        "眼神里有期待也有一丝不确定，微微前倾；"
        "他的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那片盛夏稻田的绿色虚化；"
        + LIGHT + "。镜头轻微向前缓推（slow dolly in）。\n"
        "Audio: 蝉鸣、稻浪声（后期）；他轻声问：那……现在大家能吃饱了？"
    ),
)

TASKS[66] = dict(
    slug="liu_siqi_tears_up", seed=9571,
    ref1=P_LIU_SIQI, ref2=SCENE_RICE, dur=5.0,
    prompt=(
        "CUT 1: 近景半身镜头，人物占画面高度约三分之二。"
        "一位戴细框眼镜的初中女生用力点头，眼眶泛红、一滴眼泪顺着脸颊掉下来，"
        "嘴唇动了动才把话说出口；"
        "她的面貌、发型、眼镜与服装严格照 <Picture 1>（**细框眼镜必须保留**）；"
        "背景是 <Picture 2> 那片盛夏稻田的绿色虚化；"
        + LIGHT + "。镜头轻微向前缓推（slow dolly in）。\n"
        "Audio: 蝉鸣、稻浪声（后期）；她带着哭腔轻声说：能吃饱了。"
    ),
)

TASKS[67] = dict(
    slug="yuan_smiles_keeps_looking", seed=9572,
    ref1=P_YUAN, ref2=SCENE_RICE, dur=5.0,
    prompt=(
        "CUT 1: 近景，一位穿深灰中山装的中年男人慢慢地笑了，"
        "笑得很轻、很平静，随后把目光重新投向脚下的稻田；"
        "他的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那片盛夏稻田的绿色虚化；"
        + LIGHT + "。镜头轻微横移（slow lateral move）。\n"
        "Audio: 蝉鸣、稻浪声（后期）；他平静地说：那就好。那我接着找。"
    ),
)

TASKS[68] = dict(
    slug="xu_changjing_asks_how_long", seed=9573,
    ref1=P_XU, ref2=SCENE_RICE, dur=5.0,
    prompt=(
        "CUT 1: 近景半身镜头，人物占画面高度约三分之二。"
        "一位初中男生轻声向画面外的中年男人发问，语气恭敬、神情认真；"
        "他的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那片盛夏稻田的绿色虚化；"
        + LIGHT + "。镜头轻微向前缓推（slow dolly in）。\n"
        "Audio: 蝉鸣、稻浪声（后期）；男生轻声问：您还要找多久？"
    ),
)

TASKS[69] = dict(
    slug="yuan_search_till_he_cannot", seed=9574,
    ref1=P_YUAN, ref2=SCENE_RICE, dur=5.0,
    prompt=(
        "CUT 1: 近景，一位穿深灰中山装的中年男人想了想，随后语气平淡而坚定地回答，"
        "目光始终落在稻田上；"
        "他的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那片盛夏稻田，稻浪起伏；"
        + LIGHT + "。镜头轻微向前缓推（slow dolly in）。\n"
        "Audio: 蝉鸣、稻浪声（后期）；他平静地说：找到找不动为止。"
    ),
)

TASKS[70] = dict(
    slug="zhang_shuyang_dream_of_shade", seed=9575,
    ref1=P_ZHANG, ref2=SCENE_RICE, dur=6.0,
    prompt=(
        "CUT 1: 近景半身镜头，人物占画面高度约三分之二。"
        "一位初中男生眼睛发亮、语气兴奋地向画面外描述，"
        "抬手在半空比划出一个很高的高度，脸上是向往的神情；"
        "他的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那片盛夏稻田的绿色虚化；"
        + LIGHT + "。镜头轻微向前缓推（slow dolly in）。\n"
        "Audio: 蝉鸣、稻浪声（后期）；男生兴奋地说：稻子会像高粱那么高。您能在稻穗下乘凉。"
    ),
)

TASKS[71] = dict(
    slug="yuan_eyes_light_up", seed=9576,
    ref1=P_YUAN, ref2=SCENE_RICE, dur=6.0,
    prompt=(
        "CUT 1: 近景，一位穿深灰中山装的中年男人听完后眼睛一下子亮了，"
        "随即笑出声来，笑容里有孩子般的期待；"
        "他的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那片盛夏稻田的绿色虚化；"
        + LIGHT + "。镜头轻微向前缓推（slow dolly in）。\n"
        "Audio: 蝉鸣、稻浪声（后期）；他笑着说：那我要活到那时候，亲眼看看。"
    ),
)

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
        + LIGHT + "。固定机位。\n"
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
        + LIGHT + "。镜头缓慢向前推，随后定格。\n"
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
    return "act3r_" + re.sub(r"[^0-9A-Za-z_.-]", "_", os.path.basename(path))


def upload_image(local_path, target_name):
    """上传到 ComfyUI input；先删同名旧文件（LESSONS #6：上传不覆盖同名文件）。"""
    stale = os.path.join(COMFY_IN, target_name)
    if os.path.exists(stale):
        os.remove(stale)
    import mimetypes
    boundary = "----act1videos"
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
        # LoadImage 节点：137 → ref_image_0，139 → ref_image_1（按 node id 升序）
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
    """steps 必须是 4 —— 沿用 README §7 的定版配方（镜 15 实测 199 s / 5.17 s 片段）。
    ⚠️ 2026-09-13 教训：曾误用 MCP 函数默认值 steps=20，耗时变 5 倍（1100-1560 s）。"""
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

    prefix = "act3rid/%02d_%s" % (shot, task["slug"])
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
    # --steps=N / --mp=X 可选覆盖（第二幕默认 steps=20：含稻田航拍 / 环境剧变镜）
    steps = 20
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
            f.write("第二幕《禾下乘凉》视频片段 · 生成报告（跳过首帧，直接 R2V/T2V，镜 52-76）\n")
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

