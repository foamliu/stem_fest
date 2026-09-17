# -*- coding: utf-8 -*-
"""第一幕《上甘岭（战前）》视频批量生成（镜 19-46）—— 跳过首帧，直接「人物参考图 + 场景图」喂 H3 R2V。

⚠️ 命名说明（与 README §2 的 scene 序号对齐）：
   本片「第一幕」对应 scene 目录 `06_trench`，脚本名与输出目录一律用 `act1_trench`。
   全片映射（见 `_diag_act3_rice.py` 文首）：

       序幕一《纸飞机》  镜 1-9    → 01_paper_plane     (_diag_plane_plane_videos.py)
       序幕二《启动》    镜 10-18  → 04_classroom_dusk  (_diag_act2_startup.py)
       第一幕《上甘岭》  镜 19-46  → 06_trench          ← ★ 本脚本
       第二幕《禾下乘凉》镜 47-74  → 07_rice_field      (_diag_act3_rice.py)

⚠️ 命名说明（2026-09-13 删「Ouch 梗」后重排）：
   旧镜 18、19（Ouch 第一次 / 张书扬学她）已删除，**全片 131 镜 → 129 镜**，
   旧 20-131 整体前移 2 位 ⇒ 本幕由 **旧 21-48 变为新 19-46**。

台词与镜号严格取自 `storyboard.md` §第一幕：上甘岭（战前）（1952-10 朝鲜战场交通壕，灰蒙蒙）。

路线（与序幕一/二一致，README §7）：
  · 有角色的镜 → `video_minimax_h3_r2v`
      ref_image_1 = 角色/合影参考图 → `<Picture 1>`
      ref_image_2 = `SCENES/06_trench/trench_wide_v02.png` → `<Picture 2>`
        （★ 该图是**调色锁定**版：`_diag_grade_trench.py` 施加 gain RGB
         (0.930, 1.050, 0.995)，把土壁 G/R 由 0.946 抬到 1.068 —— 灰绿土黄）
  · 纯转场/无角色镜 → `video_minimax_h3_t2v`（本幕仅镜 46 白屏日记字）

★ 参考图纪律（2026-09-13 修正 —— 用户反馈「说话时背景没人了」）：
  **多人场景（同一空间）里的「单人说话镜」，参考图不能只给说话人一张脸** ——
  H3 只能从参考图认识「画面里有谁」，只给一个人 ⇒ 其余人凭空消失。
  本幕的单人说话镜（新 37/38）已挂 `GUARD_*` 并在 prompt 里写明旁人在场；
  仅「面部特写（close-up）」镜例外 —— 特写下旁人本就不该入画。

★ 本幕的关键戏剧点：
  · 镜 19 横摇交代环境：四人 + 战士整理弹药挖野菜（全幕唯一「环境交代」镜）
  · 镜 25-29 「我们是从未来来的」坦白 → 黄继光只回「……未来？」
  · 镜 38-39 「那我要活到那时候，亲眼看看」+ 小战士拉手约定（全幕情绪高点）
  · 镜 45 「我姓黄。黄继光。」—— 口琴声起，名字的落点
  · 镜 46 白屏日记字 = 转场到第二幕

⚠️ 音频纪律（2026-09-13 教训，见 `_diag_act3_rice.py`）：
   **无台词的镜必须在 prompt 里明确写"不要出现人声"**，否则 H3 会自己幻觉出语音
   （实测镜 4 出"啊"、镜 5 出整句胡话，用 Qwen3-ASR 才查出）。
   本幕无台词镜：19（风声/铁锹声）、23（轻笑声）；镜 46 是白屏字幕，同样禁人声。

⚠️ steps 选择（README §4.2）：
   4（静态/单人/对话镜）/ 10（角色镜抽卡）/ 20（环境剧变镜）。
   本幕的 20 步候选：镜 19（横摇扫过整条坑道、画面持续剧变）、
   镜 39（7s 特写，握手动作 + 最长台词）、镜 45（全景跟移 + 缓拉）。
   其余按 10 步跑；纯静态对话镜可降到 4。

用法：
    py -3.10 OUTPUT/_diag_act1_trench.py --dry                 # 只看任务清单
    py -3.10 OUTPUT/_diag_act1_trench.py --steps=10            # 全量（默认 10）
    py -3.10 OUTPUT/_diag_act1_trench.py --steps=10 19 20      # 指定镜
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
OUT_ROOT = os.path.join(ROOT, "OUTPUT", "06_trench", "video")
REPORT = os.path.join(ROOT, "OUTPUT", "_act1_trench_report.txt")
CLIENT_ID = "act1v_trench"

FRAMES = os.path.join(ROOT, "ASSETS", "CHARACTERS")
SCENES = os.path.join(ROOT, "ASSETS", "SCENES")
EXTRAS = os.path.join(FRAMES, "_extras")
PROPS = os.path.join(ROOT, "ASSETS", "PROPS")

WF_R2V = "video_minimax_h3_r2v.json"
WF_T2V = "video_minimax_h3_t2v.json"

# 第一幕统一光线基调（storyboard：1952-10 朝鲜战场交通壕，灰蒙蒙；色调 灰绿 + 土黄）
# 依据 ASSETS/STYLE/README.md：上甘岭 = 灰绿 + 土黄 / 坑道口的微光 / 风声 + 零星炮响
LIGHT = (
    "1952 年 10 月朝鲜战场，天灰蒙蒙的、没有直射阳光；色调是低饱和的灰绿与土黄，"
    "坑道口透进一线微光，被炸松的焦土、沙袋与弹坑构成背景，空气里有硝烟与尘土"
)

SCENE = os.path.join(SCENES, "06_trench", "trench_wide_v02.png")

# ── 角色参考图（单人镜用定妆照）────────────────────────────
P_LIU_SIQI = os.path.join(FRAMES, "01_liu_siqi", "liu_siqi_hero_v01.png")
P_LIU_SICHENG = os.path.join(FRAMES, "02_liu_sicheng", "liu_sicheng_hero_v01.png")
P_XU = os.path.join(FRAMES, "03_xu_changjing", "xu_changjing_hero_v01.png")
P_ZHANG = os.path.join(FRAMES, "04_zhang_shuyang", "zhang_shuyang_hero_v01.png")
# ★ 黄继光主图是 hero_v02（已去水印），见 README §3 / ASSETS README §2
P_HUANG = os.path.join(FRAMES, "05_huang_jiguang", "huang_jiguang_hero_v02.png")
P_YOUNG_SOLDIER = os.path.join(EXTRAS, "08_young_soldier", "young_soldier_hero_v01.png")
P_SOLDIERS = os.path.join(EXTRAS, "11_volunteer_soldiers", "volunteer_soldiers_hero_v01.png")

# ── 合影参考图（R2V 硬前提：≥2 人必须合成一张合影）────────
G_FOUR = os.path.join(FRAMES, "_group", "four_students_hero_v02.png")
G_FOUR_HUANG = os.path.join(FRAMES, "_group", "four_students_huang_jiguang_hero_v01.png")
G_FOUR_SOLDIERS = os.path.join(FRAMES, "_group", "four_students_soldiers_hero_v01.png")
G_SIQI_SICHENG = os.path.join(FRAMES, "_group", "liu_sicheng_liu_siqi_hero_v01.png")
G_ZHANG_XU = os.path.join(FRAMES, "_group", "zhang_shuyang_xu_changjing_hero_v01.png")
G_ZHANG_HUANG = os.path.join(FRAMES, "_group", "zhang_shuyang_huang_jiguang_hero_v01.png")
G_SICHENG_HUANG = os.path.join(FRAMES, "_group", "liu_sicheng_huang_jiguang_hero_v01.png")
G_YOUNG_SOL_HUANG = os.path.join(
    FRAMES, "_group", "young_soldier_soldiers_huang_jiguang_hero_v01.png")
G_SICHENG_YOUNG_SOL = os.path.join(
    FRAMES, "_group", "liu_sicheng_young_soldier_soldiers_hero_v01.png")
G_XU_SOL_HUANG = os.path.join(
    FRAMES, "_group", "xu_changjing_soldiers_huang_jiguang_hero_v01.png")
G_SOL_HUANG = os.path.join(FRAMES, "_group", "soldiers_huang_jiguang_hero_v01.png")
G_SIQI_HUANG = os.path.join(FRAMES, "_group", "liu_siqi_huang_jiguang_hero_v01.png")

# ── 道具参考图（本幕不单独走道具 R2V，场景由 <Picture 2> 承载）──
P_WILD_VEG = os.path.join(PROPS, "11_wild_vegetables", "wild_vegetables_hero_v01.png")
P_AMMO_GEAR = os.path.join(PROPS, "12_ammo_gear", "ammo_gear_hero_v01.png")

# 造型护栏（README §6.1 #1：定妆照 = 外形唯一权威，prompt 禁止改动外形）
# 只写「客观可见的稳定特征」：军帽红星帽徽必须保留（README §5 硬事实）
#
# ★ 2026-09-15 去泄漏化（README §6.6）：删掉全部 `**` 加粗标记。
#   理由：`**` 会被 H3 当画面文字画出来（镜 7 实测 `** 也不抬`），
#   `**` 是**给 Agent 自己看**的语义强调，H3 不需要 ⇒ 只增泄漏面。
#   本常量被 **19 个镜**共用（镜 22–60 一带的志愿军/战士镜），改一处全部受益。
#   ⚠️ 同时修掉旧版的**重复拼接 bug**：调用处已写「…严格照 <Picture 1>」，
#      旧常量又以「他的面貌、发型与服装严格照 <Picture 1>」开头 ⇒ 输出重复两遍
#      （镜 36 旧 prompt 实测出现「严格照 <Picture 1>他的面貌、发型与服装严格照 <Picture 1>」）。
GUARD_HUANG = (
    "（军绿色立领军装与军帽上的红色五角星帽徽必须保留，"
    "不可改成其他军装、不可摘下军帽）"
)
GUARD_GLASSES = "（细框眼镜必须保留）"


# ★ 2026-09-15 视觉检查修复：旧版是否定式指令（「本镜不要生成任何…」），
# H3 会把指令本身渲染成画面字幕。新版 = 纯正向音景描述，不含可读词句。
NO_SPEECH = (
    "Audio: 野外开阔地的环境底噪；风吹过土壁与沙袋的气流声；"
    "远处零星的人声杂音，听不清任何词句。"
)

# ★ 音频三层分工（README §4.4）：剧本文本里带「（后期）」的音效一律不进 H3 prompt，
# 由 ace_step_t2audio 在后期铺。H3 只负责 L1 台词。
LATE_MARK = "（后期）"


def strip_late_audio(text):
    """把「…（后期）」这类后期音效从句子里剔除，只留 L1 台词给 H3。

    兼容两种写法：
      A) 显式 `Audio: 环境音（后期）；台词…`
      B) 无 Audio 前缀、环境音与台词用 `。` 连写（Act3 早期写法）
    规则：**凡是含 LATE_MARK 的那一句整句丢掉**；句子边界 = `；` `。` 或换行。
    ★ 2026-09-16 关键修复（去字幕泄漏，README §6.6b）：
      旧实现切句后 **无条件 join**，把 `\n` 段落分隔符一起吃掉 ⇒ 多行 prompt
      被压成一行，禁令句与台词**粘连**，H3 便把台词当画面字幕渲染。
      现改为 **按行处理、保留换行**。
    """
    import re as _re
    lines = []
    for line in text.split("\n"):
        kept = [s for s in _re.split(r"(?<=[；。])", line) if LATE_MARK not in s]
        lines.append("".join(kept))
    return "\n".join(lines).strip()

TASKS = {}

TASKS[19] = dict(
    slug="trench_wide_four_and_soldiers", seed=9700,
    ref1=G_FOUR_SOLDIERS, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 全景镜头。一条被炸松土的朝鲜战场交通壕，画面里一共有五个人："
        "四位穿白色短袖 Polo 衫、系红领巾的初中生站在交通壕里，"
        "稍远处有几名穿军绿色立领军装的志愿军战士正蹲着整理弹药箱、用铁锹挖野菜；"
        "五人的面貌、发型、服装严格照 <Picture 1>；"
        "环境是 <Picture 2> 那条灰蒙蒙的战前交通壕：土壁、沙袋、弹坑、稀稀拉拉的野草；"
        + LIGHT + "。镜头缓慢横摇（slow pan）扫过整条坑道，从左侧的战士摇到右侧的四位学生。\n"
        "Audio: 野外开阔地的环境底噪；风吹过土壁与沙袋的气流声；"
        "远处零星的人声杂音，听不清任何词句。"
    ),
)

TASKS[20] = dict(
    slug="siqi_looks_around_shrinks_back", seed=9701,
    ref1=G_SIQI_SICHENG, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 中景双人镜头，两位初中生站在同一段交通壕里、处于同一光照环境、"
        "画面是一个完整连续的空间：左边那位（戴细框眼镜的女生，马尾）环顾四周、"
        "神情有点紧张，身体往右边那位身后缩了缩；右边那位（戴细框眼镜的女生）站得稳一些；"
        "两人的面貌、发型、眼镜与服装严格照 <Picture 1>" + GUARD_GLASSES + "；"
        "背景是 <Picture 2> 那条灰蒙蒙的战前交通壕，土壁与沙袋；"
        + LIGHT + "。镜头轻微手持晃动（subtle handheld），跟着她的视线缓慢横摇。\n"
        "Audio: 风声与远处零星炮响（后期）；左边的女生小声地说：这里……好像还没打起来？"
    ),
)

TASKS[21] = dict(
    slug="zhang_crouches_looks_at_wild_veg", seed=9702,
    ref1=G_ZHANG_XU, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 中景双人镜头，两位初中生处于同一光照环境、画面是一个完整连续的空间："
        "左边那位（男生）蹲在交通壕边上，伸手拨开一丛野草低头打量，表情是好奇加嫌弃；"
        "右边那位（男生，不戴眼镜）站在他身后侧；"
        "两人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那条灰蒙蒙的战前交通壕，土壁上长着稀稀拉拉的野菜野草；"
        + LIGHT + "。镜头固定，随后轻微下摇（slight tilt down）落到那丛野菜上；★ 全画面不得出现任何可读的文字、字幕或符号。画面上没有任何文字、字幕或标识，人物脸上只有表演。\n"
        "Audio: 风声（后期）；蹲着的男生问：这野菜能吃吗？"
    ),
)

TASKS[22] = dict(
    slug="xu_polite_stop_touching", seed=9703,
    ref1=G_ZHANG_XU, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 中近景双人镜头，两位初中生处于同一光照环境、画面是一个完整连续的空间："
        "左边那位（男生，不戴眼镜）神情礼貌而克制、抬手做了个往下按的制止手势；"
        "右边那位（男生）还保持着蹲着的姿势；"
        "两人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那条灰蒙蒙的战前交通壕，土壁与野草；"
        + LIGHT + "。镜头固定不动。\n"
        "Audio: 风声（后期）；左边的男生压低声音说：别乱动。战前物资紧张。"
    ),
)

TASKS[23] = dict(
    slug="huang_shares_wild_veg_with_young_soldier", seed=9704,
    ref1=G_YOUNG_SOL_HUANG, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 中景三人镜头，三人蹲在交通壕里同一处、处于同一光照环境、"
        "画面是一个完整连续的空间：中间那位（穿军绿色立领军装、戴红星军帽的年轻战士）"
        "正在帮炊事班分拣一堆野菜，把手里几片好的菜叶挑出来拨给身边那位年纪更小的战士；"
        "小战士伸手去接；稍远处另一位战士低头整理弹药；"
        "三人的面貌、发型与服装严格照 <Picture 1>" + GUARD_HUANG + "；"
        "背景是 <Picture 2> 那条灰蒙蒙的战前交通壕，土壁与沙袋；"
        + LIGHT + "。镜头缓慢向前推近（slow dolly in）落到他们分菜的手上。\n"
        "Audio: 野外开阔地的环境底噪；风吹过土壁与沙袋的气流声；"
        "远处零星的人声杂音，听不清任何词句。"
    ),
)

TASKS[24] = dict(
    slug="huang_looks_up_sees_four_smiles", seed=9705,
    ref1=G_FOUR_HUANG, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 中景多人镜头，五个人（四位穿白色短袖 Polo 衫系红领巾的初中生，"
        "与一位穿军绿色立领军装、戴红星军帽的年轻战士）站在同一段交通壕里、"
        "处于同一光照环境、画面是一个完整连续的空间："
        "军装战士蹲着抬起头，视线落到面前四位学生身上，愣了一下、然后友善地笑了笑；"
        "五人的面貌、发型、眼镜与服装严格照 <Picture 1>" + GUARD_HUANG + "；"
        "背景是 <Picture 2> 那条灰蒙蒙的战前交通壕，土壁与沙袋；"
        + LIGHT + "。镜头固定，随后轻微向后拉（slight pull back）。\n"
        "Audio: 风声（后期）；军装战士抬起头，语气随意地问：你们是哪个部队的？"
    ),
)

TASKS[25] = dict(
    slug="zhang_steps_forward_almost_slips", seed=9706,
    ref1=G_ZHANG_HUANG, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 中景双人镜头，一位穿白色短袖 Polo 衫系红领巾的初中男生与一位"
        "穿军绿色立领军装、戴红星军帽的年轻战士面对面站在交通壕里、处于同一光照环境、"
        "画面是一个完整连续的空间：男生往前迈了一步、嘴快地说到一半突然意识到不对、"
        "话音卡住、表情有点慌，身体向后一僵；战士静静看着他、没有接话；"
        "两人的面貌、发型与服装严格照 <Picture 1>" + GUARD_HUANG + "；"
        "背景是 <Picture 2> 那条灰蒙蒙的战前交通壕，土壁与沙袋；"
        + LIGHT + "。镜头轻微手持晃动（subtle handheld），跟着他上前的脚步。\n"
        "Audio: 风声（后期）；男生急着说、说到一半断掉：我们不是这个部队的，我们是从——"
    ),
)

TASKS[26] = dict(
    slug="sicheng_pulls_him_back_confesses", seed=9707,
    ref1=G_SICHENG_HUANG, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 中景双人镜头，一位戴细框眼镜、穿白色短袖 Polo 衫系红领巾的初中女生与一位"
        "穿军绿色立领军装、戴红星军帽的年轻战士面对面站在交通壕里、处于同一光照环境、"
        "画面是一个完整连续的空间：女生伸手拉了一下身后同伴的胳膊、把他挡在身后，"
        "然后自己站到前面，抬眼看着战士、神情认真而坦诚地说出实话；战士安静地听着；"
        "两人的面貌、发型、眼镜与服装严格照 <Picture 1>" + GUARD_GLASSES + GUARD_HUANG + "；"
        "背景是 <Picture 2> 那条灰蒙蒙的战前交通壕，土壁与沙袋；"
        + LIGHT + "。镜头固定，轻微横移（slow lateral move）。\n"
        "Audio: 风声（后期）；女生平静而认真地说：我们是从未来来的。74年后。"
    ),
)

TASKS[27] = dict(
    slug="huang_silent_then_says_future", seed=9708,
    ref1=G_FOUR_HUANG, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 近景多人镜头，五个人（四位穿白色短袖 Polo 衫系红领巾的初中生，"
        "与一位穿军绿色立领军装、戴红星军帽的年轻战士）在交通壕里、处于同一光照环境、"
        "画面是一个完整连续的空间：军装战士没有说话，只是挨个看进四位学生的眼睛里、"
        "沉默了几秒，脸上的笑意慢慢收住，然后平静地开口；四位学生屏住呼吸看着他；"
        "五人的面貌、发型、眼镜与服装严格照 <Picture 1>" + GUARD_HUANG + "；"
        "背景是 <Picture 2> 那条灰蒙蒙的战前交通壕，土壁与沙袋；"
        + LIGHT + "。镜头缓慢向前推近（slow dolly in），气氛安静下来。\n"
        "Audio: 风声（后期）；军装战士平静地重复了一遍：……未来？"
    ),
)

TASKS[28] = dict(
    slug="sicheng_nods_2026", seed=9709,
    ref1=G_SICHENG_HUANG, ref2=SCENE, dur=2.0,
    prompt=(
        "CUT 1: 近景双人镜头，一位戴细框眼镜、穿白色短袖 Polo 衫系红领巾的初中女生与一位"
        "穿军绿色立领军装、戴红星军帽的年轻战士面对面、处于同一光照环境、"
        "画面是一个完整连续的空间：女生用力点了一下头，眼神坚定；战士在她对面看着；"
        "两人的面貌、发型、眼镜与服装严格照 <Picture 1>" + GUARD_GLASSES + GUARD_HUANG + "；"
        "背景是 <Picture 2> 那条灰蒙蒙的战前交通壕，土壁虚化；"
        + LIGHT + "。镜头固定不动。\n"
        "Audio: 风声（后期）；女生点头说：二零二六年。"
    ),
)

TASKS[29] = dict(
    slug="huang_asks_about_our_country", seed=9710,
    ref1=G_FOUR_HUANG, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 中景多人镜头，五个人（四位穿白色短袖 Polo 衫系红领巾的初中生，"
        "与一位穿军绿色立领军装、戴红星军帽的年轻战士）在交通壕里、处于同一光照环境、"
        "画面是一个完整连续的空间：军装战士问出一个所有人都没想到的问题，"
        "语气很轻、带着一点不确定的期待，眼神认真；四位学生一时都愣住了；"
        "五人的面貌、发型、眼镜与服装严格照 <Picture 1>" + GUARD_HUANG + "；"
        "背景是 <Picture 2> 那条灰蒙蒙的战前交通壕，土壁与沙袋；"
        + LIGHT + "。镜头缓慢向前推近（slow dolly in）。\n"
        "Audio: 风声（后期）；军装战士轻声问：那……咱们国家，现在啥样了？"
    ),
)

TASKS[30] = dict(
    slug="zhang_blurts_out_amazing", seed=9711,
    ref1=G_ZHANG_HUANG, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 近景双人镜头，一位穿白色短袖 Polo 衫系红领巾的初中男生与一位"
        "穿军绿色立领军装、戴红星军帽的年轻战士面对面、处于同一光照环境、"
        "画面是一个完整连续的空间：男生嘴快、眼睛发亮，一口气往外报、"
        "手还比划着，表情是压不住的兴奋；战士安静地看着他；"
        "两人的面貌、发型与服装严格照 <Picture 1>" + GUARD_HUANG + "；"
        "背景是 <Picture 2> 那条灰蒙蒙的战前交通壕，土壁虚化；"
        + LIGHT + "。镜头固定不动。\n"
        "Audio: 风声（后期）；男生脱口而出、越说越快：那可太牛了！高铁、空间站、AI——"
    ),
)

TASKS[31] = dict(
    slug="xu_nudges_zhang_to_slow_down", seed=9731,
    ref1=G_ZHANG_XU, ref2=SCENE, dur=3.0,
    prompt=(
        # ★ 2026-09-16 修复「场景漂移成白天教室」（README §6.10）：
        #   旧版把环境锚点（土壁/沙袋）放在 prompt **末尾**，H3 只读到开头的
        #   「两位初中生…同一光照环境」就按默认校园场景出图，
        #   成片出现两侧黑板 + 暖金阳光的**白天教室**（整幕唯一一镜出戏）。
        #   修法：① 环境锚点**提到最前**（第一句就写死交通壕+沙袋+土壁）；
        #        ② 正向写「光线来源」而不是只写「灰蒙蒙」；
        #        ③ 换 seed（旧 seed 落在坏支上）。
        "CUT 1: 灰蒙蒙的战前交通壕里，土壁与沙袋堆成的壕壁占满背景，"
        "坑道口透进一线微光、被炸松的焦土与弹坑；"
        "中近景双人镜头，两位穿白色短袖 Polo 衫系红领巾的初中男生站在壕沟里、"
        "处在同一光照环境、画面是一个完整连续的空间："
        "左边那位（男生，不戴眼镜）神情冷静、抬起手腕轻轻碰了一下身边同伴的胳膊，"
        "动作很轻、是提醒的意思；右边那位（男生）还在兴头上；"
        "两人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那条灰蒙蒙的战前交通壕，土壁与沙袋；"
        + LIGHT + "。镜头固定不动。\n"
        "Audio: 风声（后期）；左边的男生低声提醒：你慢点，吓着人家。"
    ),
)

TASKS[32] = dict(
    slug="xu_answers_politely", seed=9713,
    ref1=G_XU_SOL_HUANG, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 中景三人镜头，一位穿白色短袖 Polo 衫系红领巾的初中男生（不戴眼镜）、"
        "一位穿军绿色立领军装戴红星军帽的年轻战士，与稍远处另一名志愿军战士，"
        "站在同一段交通壕里、处于同一光照环境、画面是一个完整连续的空间："
        "男生面对这位陌生战士，神情礼貌、语气平稳地回答，"
        "每说一句都轻轻点头、说得很认真；战士蹲着听，眼神一点点亮起来；"
        "三人的面貌、发型与服装严格照 <Picture 1>" + GUARD_HUANG + "；"
        "背景是 <Picture 2> 那条灰蒙蒙的战前交通壕，土壁与沙袋；"
        + LIGHT + "。镜头缓慢向前推近（slow dolly in）。\n"
        "Audio: 风声（后期）；男生一板一眼、礼貌地回答：大家都能吃饱。每个孩子都能上学。不用再打仗了。"
    ),
)

TASKS[33] = dict(
    slug="huang_eyes_light_up_mother", seed=9714,
    ref1=G_FOUR_HUANG, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 近景多人镜头，五个人（四位穿白色短袖 Polo 衫系红领巾的初中生，"
        "与一位穿军绿色立领军装、戴红星军帽的年轻战士）在交通壕里、处于同一光照环境、"
        "画面是一个完整连续的空间：军装战士的眼睛突然亮了一下、嘴角不由自主地扬起来，"
        "目光越过眼前、落在远处的地平线上；四位学生围看着他；"
        "五人的面貌、发型、眼镜与服装严格照 <Picture 1>" + GUARD_HUANG + "；"
        "背景是 <Picture 2> 那条灰蒙蒙的战前交通壕，土壁虚化；"
        + LIGHT + "。镜头固定，轻微向前推近（slight push in）到他的脸。\n"
        "Audio: 风声（后期）；军装战士轻声说：那就好。我娘在四川，总饿肚子。"
    ),
)

TASKS[34] = dict(
    slug="young_soldier_asks_did_we_win", seed=9715,
    ref1=G_SICHENG_YOUNG_SOL, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 中近景三人镜头，一位戴细框眼镜、穿白色短袖 Polo 衫系红领巾的初中女生，"
        "一位穿着偏大的军绿色立领军装的年轻小战士（不戴领章），"
        "与稍远处另一名志愿军战士，站在同一段交通壕里、处于同一光照环境、"
        "画面是一个完整连续的空间：小战士凑到女生跟前、仰着脸、"
        "眼里满是急切地问了一句话；女生低头看着他；"
        "三人的面貌、发型、眼镜与服装严格照 <Picture 1>" + GUARD_GLASSES + "；"
        "背景是 <Picture 2> 那条灰蒙蒙的战前交通壕，土壁与沙袋；"
        + LIGHT + "。镜头固定，轻微横移（slow lateral move）。\n"
        "Audio: 风声（后期）；小战士急着问：那咱们打赢了吗？"
    ),
)

TASKS[35] = dict(
    slug="sicheng_nods_we_won", seed=9716,
    ref1=G_SICHENG_YOUNG_SOL, ref2=SCENE, dur=2.0,
    prompt=(
        "CUT 1: 近景双人镜头，一位戴细框眼镜、穿白色短袖 Polo 衫系红领巾的初中女生，"
        "与一位穿着偏大军绿色立领军装的年轻小战士（不戴领章），"
        "面对面站在同一段交通壕里、处于同一光照环境、画面是一个完整连续的空间："
        "女生深深地、用力地点了一下头，眼神毫不含糊；小战士仰头看着她；"
        "两人的面貌、发型、眼镜与服装严格照 <Picture 1>" + GUARD_GLASSES + "；"
        "背景是 <Picture 2> 那条灰蒙蒙的战前交通壕，土壁虚化；"
        + LIGHT + "。镜头固定不动。\n"
        "Audio: 风声（后期）；女生用力点头说：打赢了。"
    ),
)

TASKS[36] = dict(
    slug="young_soldier_relieved_huang_smiles", seed=9717,
    ref1=G_YOUNG_SOL_HUANG, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 中景三人镜头，一位穿着偏大军绿色立领军装的年轻小战士（不戴领章）、"
        "一位穿军绿色立领军装戴红星军帽的年轻战士，与稍远处另一名志愿军战士，"
        "蹲在同一段交通壕里、处于同一光照环境、画面是一个完整连续的空间："
        "小战士长长松了一口气、整个人松下来、笑起来，转头去喊身边的人；"
        "戴军帽的战士也跟着笑了，低头看着他；"
        "三人的面貌、发型与服装严格照 <Picture 1>" + GUARD_HUANG + "；"
        "背景是 <Picture 2> 那条灰蒙蒙的战前交通壕，土壁与沙袋；"
        + LIGHT + "。镜头缓慢向后拉（slow pull back）；★ 全画面不得出现任何可读的文字、字幕或符号。画面上没有任何文字、字幕或标识，人物脸上只有表演。\n"
        "Audio: 风声（后期）；小战士压着嗓子兴奋地喊：继光哥！你听见没！打赢了！"
    ),
)

TASKS[37] = dict(
    slug="siqi_softly_no_more_war", seed=9718,
    ref1=P_LIU_SIQI, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 近景半身镜头，人物占画面高度约三分之二。"
        "一位戴细框眼镜、穿白色短袖 Polo 衫系红领巾的初中女生，"
        "神情有点犹豫、声音很轻地补了一句，眼睛看着地面又抬起来；"
        "她的面貌、发型、眼镜与服装严格照 <Picture 1>" + GUARD_GLASSES + "；"
        "背景是 <Picture 2> 那条灰蒙蒙的战前交通壕，土壁虚化；"
        + LIGHT + "。镜头缓慢向前推近（slow dolly in）。\n"
        "Audio: 风声（后期）；女生小声地说：还有……不用打仗了。"
    ),
)

TASKS[38] = dict(
    slug="huang_smiles_slowly_closeup", seed=9719,
    ref1=P_HUANG, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 面部特写镜头（close-up），画面几乎只是一位年轻战士的脸；"
        "他穿军绿色立领军装、戴红星军帽，脸上沾着一点尘土，"
        "慢慢露出一个很轻、很干净的笑，眼神望向画面外的远处，目光望着远方、眼睛微微发亮；"
        + GUARD_HUANG + "；"
        "背景是 <Picture 2> 那条灰蒙蒙的战前交通壕，土壁完全虚化；"
        + LIGHT + "。镜头缓慢向前推近（slow dolly in）到他的眼睛。\n"
        "Audio: 风声（后期）；战士慢慢地说：那我要活到那时候，亲眼看看。"
    ),
)

TASKS[39] = dict(
    slug="young_soldier_and_huang_promise", seed=9720,
    ref1=G_YOUNG_SOL_HUANG, ref2=SCENE, dur=8.0,
    prompt=(
        "CUT 1: 手部特写镜头（close-up）。一位穿着偏大军绿色立领军装的年轻小战士"
        "（不戴领章）伸出手，拉住身边那位穿军绿色立领军装、戴红星军帽的"
        "年轻战士的手，两只沾着泥土的手握在一起、用力晃了晃；"
        "镜头落在这两只握着的手上，两人的手与军装严格照 <Picture 1>" + GUARD_HUANG + "；"
        "背景是 <Picture 2> 那条灰蒙蒙的战前交通壕，土壁与沙袋完全虚化；"
        + LIGHT + "。镜头缓慢向前推近（slow dolly in），到握手动作为止。\n"
        "Audio: 风声（后期）；小战士先开口、语气像小孩一样笃定：打完仗一起回去。"
        "你去看你娘，我去看我妹妹。接着另一个更沉稳的声音应了一声：说好了。"
    ),
)

TASKS[40] = dict(
    slug="huang_asks_do_you_know_us", seed=9721,
    ref1=G_FOUR_HUANG, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 中景多人镜头，五个人（四位穿白色短袖 Polo 衫系红领巾的初中生，"
        "与一位穿军绿色立领军装、戴红星军帽的年轻战士）在交通壕里、处于同一光照环境、"
        "画面是一个完整连续的空间：军装战士转过头，把视线从一个人移到另一个人，"
        "看着这四位学生，神色认真、带着一点小心地问了一句话；"
        "五人的面貌、发型、眼镜与服装严格照 <Picture 1>" + GUARD_HUANG + "；"
        "背景是 <Picture 2> 那条灰蒙蒙的战前交通壕，土壁与沙袋；"
        + LIGHT + "。镜头固定，轻微横摇（slow pan）从一个学生移到另一个。\n"
        "Audio: 风声（后期）；军装战士认真地问：那……你们知道我们吗？"
    ),
)

TASKS[41] = dict(
    slug="four_silent_then_sicheng_nods", seed=9722,
    ref1=G_FOUR, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 全景镜头。四位穿白色短袖 Polo 衫、系红领巾的初中生并排站在交通壕里、"
        "背对坑道口的微光，四个人都沉默着没有说话，气氛一下子沉下来；"
        "停了一秒之后，中间那位戴细框眼镜的女生缓缓地点了一下头，神情郑重；"
        "四人的面貌、发型、眼镜与服装严格照 <Picture 1>" + GUARD_GLASSES + "；"
        "环境是 <Picture 2> 那条灰蒙蒙的战前交通壕，土壁、沙袋与弹坑；"
        + LIGHT + "。镜头固定不动，留出一秒安静。\n"
        "Audio: 风声（后期）；戴眼镜的女生郑重地说：知道。我们都知道。"
    ),
)

TASKS[42] = dict(
    slug="shell_lands_soldier_summoned", seed=9723,
    ref1=G_SOL_HUANG, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 中景双人镜头，两名穿军绿色立领军装、戴红星军帽的志愿军战士"
        "站在同一段交通壕里、处于同一光照环境、画面是一个完整连续的空间："
        "远处一发炮弹落地、画面与人物随之剧烈一晃，"
        "左边的战士猫着腰急跑过来、一把扶住壕壁，冲着右边那位急促地喊话；"
        "右边那位战士闻声站直、神情瞬间转为严肃；"
        "两人的面貌、发型与服装严格照 <Picture 1>" + GUARD_HUANG + "；"
        "背景是 <Picture 2> 那条灰蒙蒙的战前交通壕，土壁与硝烟；"
        + LIGHT + "。镜头轻微手持晃动（handheld shake），在炮响的瞬间明显一震。\n"
        "Audio: 炮响与尘土声（后期）；跑来的战士急促地喊：继光！营部通知，准备出发了。"
    ),
)

TASKS[43] = dict(
    slug="huang_stands_tells_them_to_go_back", seed=9724,
    ref1=G_FOUR_HUANG, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 中景多人镜头，五个人（四位穿白色短袖 Polo 衫系红领巾的初中生，"
        "与一位穿军绿色立领军装、戴红星军帽的年轻战士）在交通壕里、处于同一光照环境、"
        "画面是一个完整连续的空间：军装战士扶着壕壁站起来，拍掉身上的土，"
        "挨个看了看面前四位学生，然后笑了，语气目光一直跟着他们、手停在半空没有放下；"
        "四位学生抬头看着他；"
        "五人的面貌、发型、眼镜与服装严格照 <Picture 1>" + GUARD_HUANG + "；"
        "背景是 <Picture 2> 那条灰蒙蒙的战前交通壕，土壁与沙袋；"
        + LIGHT + "。镜头缓慢向后拉（slow pull back）。\n"
        "Audio: 风声（后期）；军装战士笑着说：你们该回去了。这里不是你们该待的地方。"
    ),
)

TASKS[44] = dict(
    slug="siqi_asks_his_name", seed=9725,
    ref1=G_SIQI_HUANG, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 近景双人镜头，一位戴细框眼镜、穿白色短袖 Polo 衫系红领巾的初中女生"
        "与一位穿军绿色立领军装、戴红星军帽的年轻战士面对面、处于同一光照环境、"
        "画面是一个完整连续的空间：女生想说什么、张了张嘴又停了一下，"
        "终于开口问了一句，眼神里带着明知道可能问不出答案的犹豫；"
        "战士安静地看着她、还没回答；"
        "两人的面貌、发型、眼镜与服装严格照 <Picture 1>" + GUARD_GLASSES + GUARD_HUANG + "；"
        "背景是 <Picture 2> 那条灰蒙蒙的战前交通壕，土壁虚化；"
        + LIGHT + "。镜头缓慢向前推近（slow dolly in）。\n"
        "Audio: 风声（后期）；女生犹豫地问：你……你叫什么名字？"
    ),
)

TASKS[45] = dict(
    slug="huang_turns_waves_goodbye", seed=9726,
    ref1=G_FOUR_HUANG, ref2=SCENE, dur=5.0,
    prompt=(
        "CUT 1: 全景多人镜头，五个人（四位穿白色短袖 Polo 衫系红领巾的初中生，"
        "与一位穿军绿色立领军装、戴红星军帽的年轻战士）在交通壕里、处于同一光照环境、"
        "画面是一个完整连续的空间：军装战士背起枪、转身沿着交通壕往坑道深处走了几步，"
        "走到一半忽然回头，冲身后四名学生挥了挥手，笑了一下，然后继续往远处走去；"
        "四位学生站在原地目送他；"
        "五人的面貌、发型、眼镜与服装严格照 <Picture 1>" + GUARD_HUANG + "；"
        "环境是 <Picture 2> 那条灰蒙蒙的战前交通壕，土壁、沙袋与延伸向远处的壕沟；"
        + LIGHT + "。镜头跟随他移动（tracking shot），随后缓慢向后拉（slow pull back），"
        "他的身影在坑道尽头越来越小。\n"
        "Audio: 风声与口琴声（后期）；战士回头时笑着报出自己的名字：我姓黄。黄继光。"
    ),
)

TASKS[46] = dict(
    slug="white_screen_diary_text_transition", seed=9727,
    ref1=None, ref2=None, dur=6.0,
    prompt=(
        "CUT 1: 纯白画面转场。画面从一片战壕的灰蒙色调迅速被刺眼的白光完全吞没，"
        "最后只剩下干净纯白的画面；白色画面上以安静的黑色手写日记字体浮现出两行中文："
        "「1952年10月，上甘岭。他说他叫黄继光。"
        "我们告诉他，74年后的中国，很好。」"
        "字体是端正的中文手写体、笔画清晰、不多不少正好这两行，居中排布；"
        "画面干净、没有任何其他元素、没有人物、没有边框、没有多余文字。\n"
        "Audio: " + NO_SPEECH
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
    return "act1tv_" + re.sub(r"[^0-9A-Za-z_.-]", "_", os.path.basename(path))


def upload_image(local_path, target_name):
    """上传到 ComfyUI input；先删同名旧文件（LESSONS #6：上传不覆盖同名文件）。"""
    stale = os.path.join(COMFY_IN, target_name)
    if os.path.exists(stale):
        os.remove(stale)
    import mimetypes
    boundary = "----act1trenches"
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


def run_shot(shot, dry=False, megapixels=0.6, steps=10, timeout=3600):
    """steps 按镜头类型选（见 README §4.2）：
    静态/单人/对话镜 4；角色镜抽卡 10（本幕默认）；环境剧变镜（横摇扫坑道 / 长特写）20。"""
    task = dict(TASKS[shot])
    # ★ 音频三层分工（README §4.4）：把「音效：（后期）」从句子里剔掉，只把 L1 台词交给 H3
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

    prefix = "act1tv/%02d_%s" % (shot, task["slug"])
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
    # --steps=N / --mp=X 可选覆盖
    # ★ 本幕默认 10 步（角色镜抽卡）；静态对话镜可用 --steps=4 提速，
    #   镜 21/41/47 建议单独用 --steps=20 跑。
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
            f.write("第一幕《上甘岭（战前）》视频片段 · 生成报告（跳过首帧，直接 R2V/T2V，镜 21-48）\n")
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

