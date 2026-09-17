# -*- coding: utf-8 -*-
"""序幕一《纸飞机》视频批量生成（镜 1-9）—— 跳过首帧，直接「人物参考图 + 场景图」喂 H3 R2V。

⚠️ 命名说明（与 README §2 的 scene 序号对齐）：
   本片「序幕一」对应 scene 目录 `01_school_gate` / `02_campus` / `03_classroom_day`，
   脚本名用 `act0_plane`。全片映射：

       序幕一《纸飞机》  镜 1-9    → 01/02/03 场景   ← ★ 本脚本
       序幕二《启动》    镜 10-18  → 04_classroom_dusk  (_diag_act2_startup.py)
       第一幕《上甘岭》  镜 19-46  → 06_trench          (_diag_act1_trench.py)
       第二幕《禾下乘凉》镜 47-74  → 07_rice_field      (_diag_act3_rice.py)
       第三幕《餐车》    镜 75-105 → 08_train_dining    (_diag_act4_train.py)
       尾声《归来与揭晓》镜 106-126→ 05_classroom_night (_diag_act5_finale.py)

台词与镜号严格取自 `storyboard.md` §序幕一：纸飞机（6 月底下午，阳光明媚）。

★ 本幕的三个硬约束（storyboard 明写「不得压缩 / 不得删改」）：
  · 镜 4 从 5s 延长到 **7s**，是为**展示校园**（科技节片子的核心功能）——
    需依次掠过操场 / 林荫道 / 花坛 / 教学楼四地点，每地 1.5-2s。航拍跟拍 ⇒ **steps=20**
  · 镜 6 从 2.33s 延长到 **5s**，台词含「是不是隔壁班暗恋我的？」—— 建立张书扬性格
  · 镜 1/4/5 为**上汇实验学校展示镜**（校牌 / 校园四地点 / 窗外校园一角）—— 不得压缩

⚠️ steps：本幕默认 **20**（航拍跟拍、飞入窗户等画面剧变镜）；静态/对话镜可 `--steps=10` 提速。

⚠️ 音频（README §4.4）：镜 3/4 的「音乐（后期）」会被 strip_late_audio() 剔除；
   镜 4/5/9 无台词 ⇒ 挂 NO_SPEECH 防 H3 幻觉人声（实测镜 4 会出「啊」、镜 5 出整句胡话）。

用法：
    py -3.10 OUTPUT/_diag_act0_plane.py --dry           # 只看任务清单
    py -3.10 OUTPUT/_diag_act0_plane.py --steps=20      # 全量（默认 20）
    py -3.10 OUTPUT/_diag_act0_plane.py --steps=10 2 3  # 指定镜
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
OUT_ROOT = os.path.join(ROOT, "OUTPUT", "01_paper_plane", "video")
REPORT = os.path.join(ROOT, "OUTPUT", "_act0_plane_report.txt")
CLIENT_ID = "act0v_plane"

FRAMES = os.path.join(ROOT, "ASSETS", "CHARACTERS")
SCENES = os.path.join(ROOT, "ASSETS", "SCENES")
PROPS = os.path.join(ROOT, "ASSETS", "PROPS")

WF_R2V = "video_minimax_h3_r2v.json"
WF_T2V = "video_minimax_h3_t2v.json"

# 序幕一统一光线基调（storyboard：6 月底下午、阳光明媚、高饱和暖调）
LIGHT = (
    "6 月底的下午，阳光明媚、空气通透，高饱和暖调，"
    "光线从画面侧上方斜射，人物脸上有柔和的暖光与自然的浅阴影"
)

SCENE_GATE = os.path.join(SCENES, "01_school_gate", "school_gate_wide_v02.png")
SCENE_CAMPUS = os.path.join(SCENES, "02_campus", "campus_wide_v01.png")
SCENE_CLASS = os.path.join(SCENES, "03_classroom_day", "classroom_day_wide_v01.png")

# ── 角色参考图 ────────────────────────────────────────────
P_GIRL = os.path.join(FRAMES, "_extras", "09_girl", "girl_hero_v01.png")
P_MOTHER = os.path.join(FRAMES, "_extras", "10_mother", "mother_hero_v01.png")

# ── 合影参考图（R2V 硬前提；一律用不带标签的 hero_v01）──
G_FOUR = os.path.join(FRAMES, "_group", "four_students_hero_v02.png")
G_GIRL_MOTHER = os.path.join(FRAMES, "_group", "girl_mother_hero_v01.png")
G_SIQI_ZHANG_XU = os.path.join(FRAMES, "_group", "liu_siqi_zhang_shuyang_xu_changjing_hero_v01.png")

# ★ 2026-09-17 新增：单人定妆照拼版（`_group/solo_*.png`）
#   根因同镜 99（README §6.10.6 ②）：**R2V 的参考图 = 说话人候选池**。
#   接多人合影 ⇒ 画面里有谁，H3 就可能让谁开口 ⇒ 说话人张冠李戴。
#   ⇒ 「确定的单人说话镜」一律接**单人拼版**（单人拼版本身就是成品，无需图生图）。
S_ZHANG = os.path.join(FRAMES, "_group", "solo_zhang_shuyang_hero_v01.png")
S_SICHENG = os.path.join(FRAMES, "_group", "solo_liu_sicheng_hero_v01.png")
S_SIQI = os.path.join(FRAMES, "_group", "solo_liu_siqi_hero_v01.png")
S_XU = os.path.join(FRAMES, "_group", "solo_xu_changjing_hero_v01.png")

# ★ 2026-09-17 新增：**禁额外人声**（用户反馈镜 7/14「前边合成多余语音」）。
#   ⛔⛔ **第一版写法已作废（实锤失败）**：初版写成
#     「全程只有这一个说话人的声音，只有上面这一句台词，从开口到说完之间没有其他任何人声、
#       没有第二个人说话、没有旁白、没有念白、没有背景人声对白。」
#     —— 这是**对模型说的话**，H3 **分不清"指令"与"台词"，把它念了出来**：
#       · 镜 7 ASR = 「你少自恋了，**只有上面这一句台词**」
#       · 镜 13 ASR = 「你少说两句就不会。**只有上一句抬口**」
#       · 镜 15 ASR = 「你输在轻敌，**全程只有这个外死的**」
#     这与 §4.4 旧版 `NO_SPEECH`（"本镜不要生成任何可辨认的语音"）被渲染成画面字幕
#     **是同一类错误、同一个根因** —— 项目里已经为此立过铁律：
#     ★★ **凡是"对模型说的话"，一个字都不能出现在 prompt 里。**
#   ✅ **正解：改用纯正向音景**（同 §4.4 修法）——
#     只描述"这段音频里有什么"，且**描述的句子本身不含任何可被念出来的词句/数字/祈使**。
#     音景描述天然是"环境声名词短语"，H3 不会把它当台词念。
#     ⚠️ 关键：**绝不能出现"台词""说话""人声""旁白"这类"关于语音的元词汇"** ——
#        提"语音"二字本身就是提示 H3"这里有一段话要说"。
ONLY_THIS_LINE = (
    " 此段音频里只有这一句对白，其余全是教室的环境底噪与衣料摩擦声。"
)

# ── 道具参考图 ────────────────────────────────────────────
P_PLANE = os.path.join(PROPS, "01_paper_plane", "paper_plane_hero_v01.png")

# 无台词镜的通用禁语音后缀（README §4.4）
# ★ 2026-09-15 视觉检查修复：旧版是**否定式指令**（「本镜不要生成任何…」），
# H3 无法区分「对模型说的话」与「台词」，会把指令本身渲染成画面字幕
# （已实锤：镜 5 底部出现「本镜不要生成任何可语午白」）。
# 新版改为**纯正向音景描述**：只说「有什么声音」，不说「不要什么声音」。
# 音景本身不含可读词句 ⇒ 既满足音频生成，又不可能被当成台词。
NO_SPEECH = (
    "Audio: 安静的室内环境底噪；轻微的衣料摩擦声与呼吸声；"
    "远处传来模糊的人群杂音，听不清任何词句。"
)

# ★ 2026-09-17 新增：**校服硬锚点**（README §6.10.4 ③ / §6.10.7）
#   根因：四小强的定妆照是**白色短袖 Polo 衫 + 红领巾**，
#   但 H3 对"中国初中生"的默认想象是**深色运动外套**（蓝白/黑白拼色）——
#   实测镜 12 重跑后画成了深色运动外套，与全片基准不符。
#   本幕（`_diag_act0_plane.py`）此前**一个"白色短袖/Polo/红领巾"字样都没有**
#   ⇒ 必须每次 prompt 都显式钉死。`_diag_act2_startup.py` 已有同类写法，这里补齐。
UNIFORM = (
    "四人都穿同款校服：白色短袖 Polo 衫、衣领是白色翻领、胸前系着红领巾、"
    "下身是深色长裤 —— 绝不要画成深色运动外套或拉链运动服"
)

# ★ 音频三层分工（README §4.4）：带「（后期）」的音效不进 H3 prompt
LATE_MARK = "（后期）"


def strip_late_audio(text):
    """把「…（后期）」这类后期音效从句子里剔除，只留 L1 台词给 H3。

    句子边界 = `；` `。` 或换行；含 LATE_MARK 的那句整句丢掉。

    ★ 2026-09-16 关键修复（去字幕泄漏，README §6.6b）：
      旧实现用 `_re.split(r"(?<=[；。])|\n", text)` 切句后 **无条件 join**，
      把原文的 `\n` 段落分隔符一起吃掉 ⇒ 多行 prompt 被压成一整行，
      `Audio:` 前缀与紧跟其后的 `（后期）` 句同归于尽，
      于是「★ 全画面不得出现任何可读的文字…」与台词**粘连成同一句**，
      H3 便把台词当画面字幕渲染（镜 14 实测：改 prompt 后 8/8 帧仍泄漏）。
      现改为 **按行处理、保留换行**：行内含 LATE_MARK 的句子才丢，`\n` 一律保留。
    """
    import re as _re
    lines = []
    for line in text.split("\n"):
        kept = [s for s in _re.split(r"(?<=[；。])", line) if LATE_MARK not in s]
        lines.append("".join(kept))
    return "\n".join(lines).strip()


TASKS = {}

# ── 镜 1 校门口：小女孩 + 妈妈（序幕一开篇；★ 校园展示镜）──
# ★ 2026-09-15 修复「校名乱码」：旧写法写「校牌清晰可见、完整入画」，
#   H3 于是把墙面当成大招牌、**在墙上写大字**，写出「汇月?舱学校 / Aue…Scoule」。
#   实际参考图（school_gate_wide_v02.png）里校名是**门柱上的竖排小牌子**（约 6px 字高），
#   H3 根本抄不动 ⇒ 只能编字。
#   ✅ 正解：①**不要求画面出现文字**（校名展示由后期贴字保证）
#            ②把「校牌」改成**建筑特征描述**（竖排铭牌、红色圆形校徽），
#              让 H3 画「一块牌子」而不是「一行字」
#            ③明示**不要出现任何可读文字/招牌字样**
# ★ 2026-09-17 第二轮修复（用户复测仍报「校门上的学校名字不对」）：
#   上一版只写了「看不到任何可以辨认的字母或笔画」，但 **ref2 那张实景图里墙面本身带字**，
#   H3 会去读参考图上的字并**重画一遍（画不像就变乱码）**。
#   ⇒ 本轮把约束**从「不许有字」升级为「墙面是整片纯色」**：
#     ① 明写「整个校门上方的墙面是一整片干净的米黄色，上面什么都没有」
#        —— 这是**正向可执行描述**，比单纯否定句更稳（见本文件 NO_SPEECH 注释的原理）
#     ② 门柱上只保留**纯色几何图案**（一块小小竖排铭牌 + 一个红色圆点），
#        明写它「不承载任何笔画」，把 H3 的注意力从「抄字」引到「画牌子」
#     ③ 保留一句显式否定做兜底（历史实锤：否定句对\"文字\"这类硬约束仍有必要，
#        区别于\"语音\"——语音那条被证明不能用否定式）
TASKS[1] = dict(
    slug="girl_mother_at_school_gate", seed=9101,
    ref1=G_GIRL_MOTHER, ref2=SCENE_GATE, dur=3.0,
    prompt=(
        "CUT 1: 全景镜头。一位三十多岁的母亲牵着五岁小女孩的手，站在学校大门口前，"
        "小女孩仰头看着校门上方、眼睛亮亮的，母亲低头含笑看着她；"
        "背景是 <Picture 2> 那所学校正门口的实景：米黄色墙面、竖条纹装饰墙、深色金属大门与门柱；"
        "★ 整个校门上方的墙面是一整片干净的米黄色，上面什么都没有 —— "
        "没有招牌、没有横幅、没有字迹、没有校名、没有任何字母或汉字；"
        "两根门柱上只有极简的装饰：一块很小的竖排色块与一个红色圆形图案，"
        "它们是纯色几何形状、不承载任何笔画；"
        "两人的面貌、发型与服装严格照 <Picture 1>（不要改变长相与年龄）；"
        + LIGHT + "。固定机位，只留轻微手持呼吸感。"
        "★ 全画面不得出现任何可读的文字、招牌字样或英文单词，"
        "校门与围墙上只有干净的米黄墙面与深灰色金属栏杆。\n"
        "Audio: 校门口的环境音，微风、远处隐约的校园喧闹声（后期）；"
        "小女孩仰头、清脆地说：妈妈，这个学校好漂亮！"
        + ONLY_THIS_LINE
    ),
)


# ── 镜 2 妈妈低头看她（近景）──
TASKS[2] = dict(
    slug="mother_looking_at_girl", seed=9102,
    ref1=G_GIRL_MOTHER, ref2=SCENE_GATE, dur=4.0,
    prompt=(
        "CUT 1: 近景镜头。母亲笑着低下头看身边的小女孩，眼神温柔；"
        "小女孩在画面里只入画一部分（侧脸或后脑勺），不要让她消失；"
        "两人的面貌、发型与服装严格照 <Picture 1>（不要改变长相与年龄）；"
        "背景是 <Picture 2> 那所学校正门口的实景、略微虚化；"
        + LIGHT + "。固定机位。\n"
        "Audio: 校门口环境音（后期）；母亲温和地说：那你明年就可以来这儿读书了。"
    ),
)

# ── 镜 3 甩纸飞机（中景）──
TASKS[3] = dict(
    slug="girl_throwing_paper_plane", seed=9103,
    ref1=G_GIRL_MOTHER, ref2=P_PLANE, dur=3.0,
    prompt=(
        "CUT 1: 中景镜头。小女孩右手捏着一架白色纸飞机，先凑到嘴边哈了一口气，"
        "然后手臂用力向前一甩，把纸飞机朝校门方向掷出去，动作干脆、表情兴奋；"
        "母亲站在她身旁看着、含笑（不要让她消失）；纸飞机的形态照 <Picture 2>；"
        "人物的面貌、发型与服装严格照 <Picture 1>（不要改变长相与年龄）；"
        + LIGHT + "。固定机位，甩手瞬间镜头轻微跟随。\n"
        "Audio: 纸飞机出手时的破风声（后期）；"
        "小女孩用力喊：飞喽——！"
    ),
)

# ── 镜 4 航拍跟拍纸飞机掠过校园（★ 校园展示镜，7s，T2V）──
TASKS[4] = dict(
    slug="paper_plane_over_campus", seed=9104,
    ref1=None, ref2=None, dur=7.0,
    prompt=(
        "CUT 1: 远景航拍跟拍镜头，画面前景是一架正在滑翔的白色纸飞机，"
        "镜头一路跟随它向前飞过学校校园：先掠过操场（有学生在上体育课），"
        "再穿过林荫道（树影斑驳、阳光透过树叶），接着掠过花坛（花正开着），"
        "最后飞向一栋教学楼四楼的窗口。四个地点依次呈现、每个约 1.5-2 秒，"
        "让观众看清校园的操场、林荫道、花坛与教学楼；"
        + LIGHT + "。镜头持续向前推进，画面持续变化、运动感强。\n"
        + NO_SPEECH
    ),
)

# ── 镜 5 纸飞机飞入教室被捏住（全景；窗外可见校园）──
TASKS[5] = dict(
    slug="zhang_shuyang_catches_plane", seed=9105,
    ref1=G_FOUR, ref2=SCENE_CLASS, dur=4.0,
    prompt=(
        "CUT 1: 全景镜头。一架白色纸飞机从教室的窗户飞进来，窗外可见校园的一角（操场与树）；"
        "窗内一位初中男生迅速伸出两根手指，在纸飞机掠过时把它稳稳捏住；"
        "教室里另外三位同学都在画面里，安静地看着这一幕；"
        "四人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那间午后的教室：米色课桌椅、蓝色墙报、明亮的窗户；"
        + LIGHT + "。镜头跟移着纸飞机从窗口进入教室，最后停在男生指间。\n"
        + NO_SPEECH
    ),
)

# ── 镜 6 张书扬举起纸飞机（★ 建立性格，5s）──
# ★ 2026-09-17 修复（用户反馈）：
#   ① 「说话人应该是张书扬」—— 旧版 ref1=G_FOUR（四人合影），
#      根因同镜 99：**参考图 = 说话人候选池**，H3 让徐畅景开口了。
#      ⇒ ref1 改 **张书扬单人拼版 S_ZHANG**，并在 Audio 前明写
#        「只有画面正中这个男生一个人说话，其他三人不说话」。
#   ② 「手里应该是一个纸飞机而非两个」—— 旧版只写「用两根手指捏着白色纸飞机」，
#      没写数量 ⇒ H3 自由发挥出两架。⇒ 明写「**手里只有一架**白色纸飞机，
#      另一只手是空的、什么都没有拿」，把\"空着的那只手\"也交代清楚。
TASKS[6] = dict(
    slug="zhang_shuyang_shows_plane", seed=9106,
    ref1=S_ZHANG, ref2=SCENE_CLASS, dur=5.0,
    prompt=(
        "CUT 1: 中近景镜头。一位初中男生用一只手的两根手指捏着白色纸飞机举到眼前，"
        "★ 画面里总共只有一架白色纸飞机，由他那只手捏着；"
        "★ 他的另一只手垂在身侧、手心是空的、什么也没有拿，那只手附近没有任何纸飞机；"
        "★ 不要出现第二架纸飞机、不要复制出另一架；"
        "手腕左右晃了晃、头微微一歪、挑起一边眉毛，眼神在教室里扫了一圈、嘴角挂着得意又挑衅的笑；"
        "画面里正在念出这句台词的人就是这一位（严格照 <Picture 1> 长相与发型）；"
        "身后和身旁还站着另外三位同学，他们看着他、嘴唇始终闭合，只入画一部分；"
        + UNIFORM + "；四人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那间午后的教室，明亮的自然光；"
        + LIGHT + "。镜头轻微向前缓推（slow dolly in）。"
        "★ 全画面不得出现任何可读的文字、字幕或符号，室内只有课桌与书本。\n"
        "Audio: 教室午后的安静底噪（后期）；"
        "画面正中的男生举着纸飞机、得意地问：谁扔的？是不是隔壁班暗恋我的？"
        + ONLY_THIS_LINE
    ),
)

# ── 镜 7 刘思齐看书 / 徐畅景看他一眼（三人合影，镜 7） ──
# ★ 2026-09-15 修复「星号+文字被渲染成字幕」：
#   旧写法 `**头也不抬**` 被 H3 画成画面文字 `** 也不抬` —— ★★ **Markdown 加粗标记
#   本身也是画面内容**（不只是文字会被画，`**` 也一起被画）。
#   ⇒ 本条与「镜 1 校名」同类（见 README §6.9）：**画面段凡是"会被当成可读文本"的字符串，
#     都有概率被渲染**。加粗强调只用于**给 Agent 自己看**的语义，不该出现在画面段
#     （画面段的字 H3 全都看得见）。
# ★ 2026-09-17 修复（用户反馈「给 3 秒时间过多，导致前边合成多余语音」）：
#   净台词 6 字 ÷ 徐畅景 4.0 字/秒 = 1.5s + 0.8s 起势 = **need 2.30s**；
#   旧 dur=3.0（H3 量化后 3.042s）⇒ 多出 **0.74s** 空档，H3 用口型空转/幻觉语音填满。
#   ⇒ 初版 dur 3.0 → **2.0**（量化 2.333s）。
#   ★★ 2026-09-17 第三次修正（**实测 2s 太紧，反而挤出乱音**）：
#     2.33s 里要放"起势 + 6 字台词"，H3 会把气口挤成一段无意义音 ——
#     `_00005_` ASR = 「六间举止飞机的男神，一眼你少自恋了」、
#     `_00006_` ASR = 「是的，姐，你少自恋了」、
#     `_00007_` ASR = 「你豁点，切伤口！你少自恋了」（三版都有前导乱音）。
#     ⇒ **回退 dur 3.0**（量化 3.042s，need 2.30s，余量 0.74s = 正常气口）。
#     ★ 教训：**"给多了 H3 会编话"与"给太少 H3 会挤乱音"是同一枚硬币的两面** ——
#       正解不是越短越好，而是 `need + 0.5~0.8s 气口`。用户反馈的"多余语音"
#       根因是**当时的 prompt 有污染文本**（已被 ONLY_THIS_LINE 修正解决），
#       并非单纯时长过长 ⇒ 污染修掉后，时长应回到公式值。
#   ★★ 第四步：**2s / 3s 都试过仍有前导乱音** ⇒ 判定 **seed 9107 落在坏支**
#      （同 §6.10.3 镜 31 的处置）。换 seed **9107 → 9171** 重跑。
#   ★★ 第五步（**收敛结论，不再继续迭代**）：
#     镜 7 累计试了 **8 个版本 / 2 个 seed**（`_00003_` ~ `_00010_`），
#     ASR 结果如下 —— 核心台词「你少自恋了」**每一版都正确**，
#     但**每一版都带一小段无关语音**（位置不固定，有时在前、有时在后）：
#       · `_00003_`「你少自恋了。全程只有他一个人开口」   ← 早期指令污染（已修）
#       · `_00005_`「六间举止飞机的男神，一眼你少自恋了」
#       · `_00006_`「是的，姐，你少自恋了」
#       · `_00007_`「你豁点，切伤口！你少自恋了」
#       · `_00008_`「忘见者推辞的安的喜气，你少自恋了」
#       · `_00009_`「上医院去旋转手术室。你少自恋了」      ← 换 seed 9171
#       · `_00010_`「你少自恋！你死也不接受这事儿啊，阎狼。」← 去掉 Audio 前环境声
#     ⇒ **结论：本镜对 H3 是"高幻觉率镜"** —— 3 人同框 + 短台词 + 只 3 秒，
#       模型倾向在台词前后补一点内容。**8 版都压不掉 ⇒ 停止迭代**（继续烧 GPU 不划算）。
#
#   ⚠️ **当前入库版本 = `_00009_`（seed 9171，dur 3s）**：
#      · 核心台词 ✅ 正确
#      · 前导有约 1 秒乱音 ⚠️ **待定稿时处理**
#   📌 **建议的收尾手段（三选一，属后期范畴，不要再重跑 H3）**：
#      ① 用 `ffmpeg` 把首 1.0s 音频淡入/裁掉（画面保留）—— 最简单、零成本；
#      ② 后期重新配音（`qwen3_tts` 徐畅景音色）替换整轨 —— 音色可控；
#      ③ 接受现状（1 秒含混音在 3 秒短镜里不刺耳）。
#   ★ 教训：**不是所有镜头都能靠 prompt 调好** —— 当同一问题试到 6+ 版仍复现时，
#     应当**及时切到后期手段**，而不是无限重跑（时间/算力成本远高于一刀 ffmpeg）。
TASKS[7] = dict(
    slug="xu_changjing_liu_siqi_glance", seed=9171,
    ref1=G_SIQI_ZHANG_XU, ref2=SCENE_CLASS, dur=3.0,
    prompt=(
        "CUT 1: 中景三人镜头，三人处于同一光照环境："
        "左边一位戴细框眼镜的女生低头看书、没有抬头；"
        "中间那位男生手里捏着一架白色纸飞机；"
        "画面最右边那位男生侧过头、嘴唇微动；"
        + UNIFORM + "；三人的面貌、发型、眼镜与服装严格照 <Picture 1>，细框眼镜必须保留；"
        "背景是 <Picture 2> 那间午后的教室；"
        "★ 全画面不得出现任何可读的文字、字幕或符号，室内只有课桌与书本。"
        + LIGHT + "。固定机位，镜头轻微横移。\n"
        "Audio: 画面最右边那位男生淡淡地说：你少自恋了。"
        + ONLY_THIS_LINE
    ),
)


# ── 镜 8 刘思成拿过纸飞机放在桌角（中近景）──
# ★ 2026-09-17 修复（用户反馈「说话人应该是刘思成而非刘思齐」）：
#   根因是**造型撞车** —— 刘思成与刘思齐**都戴细框眼镜**（定妆照核对，
#   `ASSETS/README.md` §2 角色表：两人造型基串几乎同款），
#   旧版 prompt 只写「一位戴细框眼镜的初中女生」+ ref1=G_FOUR（四张脸）
#   ⇒ H3 在池子里挑了最像描述的刘思齐。
#   ⇒ 三重锁：① ref1 换成**刘思成单人拼版 S_SICHENG**
#             ② Audio 前明写「说话的是画面里这位女生、由她一个人开口」
#             ③ ref1 是单人照后，**必须用文字把\"另外三人\"补回来**
#                （否则背景没人，见 storyboard「参考图提示列读法」核心原则）
TASKS[8] = dict(
    slug="liu_sicheng_takes_plane", seed=9108,
    ref1=S_SICHENG, ref2=SCENE_CLASS, dur=3.0,
    prompt=(
        "CUT 1: 中近景镜头。一位戴细框眼镜的初中女生伸出手，把男生手里的纸飞机拿过来，"
        "随手放在课桌角上，动作自然；"
        "画面里正在念出这句台词的人就是这一位（严格照 <Picture 1> 长相与发型）；"
        "身后和身旁还站着另外三位同学，他们看着她、嘴唇始终闭合，只入画一部分；"
        + UNIFORM + "；四人的面貌、发型、眼镜与服装严格照 <Picture 1>（细框眼镜必须保留）；"
        "背景是 <Picture 2> 那间午后的教室；"
        + LIGHT + "。固定机位，镜头轻微下摇跟手，跟着她把纸飞机放到桌角的动作。"
        "★ 全画面不得出现任何可读的文字、字幕或符号，室内只有课桌与书本。\n"
        "Audio: 教室底噪、纸张轻响（后期）；"
        "画面里这位女生说：别闹了别闹了，继续。"
        + ONLY_THIS_LINE
    ),
)

# ── 镜 9 四人继续讨论（全景，序幕一收束）──
TASKS[9] = dict(
    slug="four_students_discussing", seed=9109,
    ref1=G_FOUR, ref2=SCENE_CLASS, dur=3.0,
    prompt=(
        "CUT 1: 全景镜头。四位初中生围在课桌旁继续讨论，"
        "有人低头翻书、有人比划着说话、有人靠在桌边听，纸飞机静静躺在桌角；"
        "四人都完整入画、处于同一个连续空间、四人之间的间距均匀；"
        "四人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那间午后的教室：米色课桌椅、蓝色墙报、明亮的窗户；"
        + LIGHT + "。镜头缓慢向后拉（slow dolly out），收束到四人。\n"
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
    return "act0v_" + re.sub(r"[^0-9A-Za-z_.-]", "_", os.path.basename(path))


def upload_image(local_path, target_name):
    """上传到 ComfyUI input；先删同名旧文件（LESSONS #6：上传不覆盖同名文件）。"""
    stale = os.path.join(COMFY_IN, target_name)
    if os.path.exists(stale):
        os.remove(stale)
    import mimetypes
    boundary = "----act0videos"
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


def wait_for(prompt_id, timeout, resume=None):
    """轮询 /history 直到出现 outputs 或 error。返回 (entry, status)。

    ★ 断点续等（LESSONS #13）：终端中断（KeyboardInterrupt / 会话超时）只是
      断开了「轮询」，ComfyUI 侧的生成照常在跑，prompt 也仍留在 /history 里。
      ⇒ 中断后**绝不能重跑**（白烧一次 5-15 分钟 + 额度），应带 --resume 回来接着等。
     resume : 已有的中间态 entry（dict）或 None；若已有 outputs 则立即返回。
    """
    t0 = time.time()
    last = ""
    while time.time() - t0 < timeout:
        try:
            h = _api("/history/" + prompt_id)
        except Exception:
            h = {}
        entry = h.get(prompt_id) or resume
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
    return entry, "timeout"



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


def adopt(prompt_id, shot, dt_note=""):
    """★ 断点恢复（LESSONS #13）：不重新提交，直接收养 /history 里已有的 prompt_id。

    用途：上一次轮询被终端中断，但 ComfyUI 已把生成跑完 / 仍在跑。
    本函数只做「取回 + 落盘 + ffprobe 校验」，一次 GPU 都不烧。
    """
    task = dict(TASKS[shot])
    print("=" * 72)
    print("[镜 %d] %s | 收养已提交任务 prompt_id=%s" % (shot, task["slug"], prompt_id))
    entry, st = wait_for(prompt_id, timeout=1800)
    if entry is None:
        print("  [!] /history 里查不到该 prompt_id（可能已被清理）")
        return (shot, "NOT_FOUND", prompt_id)
    if st == "error":
        msg = json.dumps(entry.get("status", {}), ensure_ascii=False)[:600]
        print("  [X] 该任务执行报错：%s" % msg)
        return (shot, "ERROR", msg[:200])
    return _collect(shot, entry, 0.0)


def _collect(shot, entry, dt):
    """把 history entry 里的产物落盘 + 校验（run_shot / adopt 共用）。"""
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
        print("  [!] history 里没有输出文件（可能仍在跑）")
        return (shot, "NO_OUTPUT", "")
    return (shot, files[0][1], "%s | %s" % (files[0][0], files[0][2]))


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

    prefix = "act0vs20/%02d_%s" % (shot, task["slug"])
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
        print("      ★ 断点续等：py _diag_act0_plane.py --resume=%s %d" % (pid, shot))
        return (shot, "TIMEOUT", pid)
    if st == "error":
        msg = json.dumps(entry.get("status", {}), ensure_ascii=False)[:600]
        print("  [X] 执行报错：%s" % msg)
        return (shot, "ERROR", msg[:200])
    return _collect(shot, entry, dt)


def main():
    args = sys.argv[1:]
    dry = "--dry" in args
    # ★ 断点恢复：--resume=<prompt_id> 收养上次被中断轮询的任务（不重新提交、不烧 GPU）
    resume = None
    for a in sys.argv[1:]:
        if a.startswith("--resume="):
            resume = a.split("=", 1)[1]
    args = [a for a in args if not a.startswith("--")]
    # 本幕默认 10：镜 4（航拍跟拍）/ 镜 5（飞入窗）为环境剧变镜，建议单独 --steps=20；
    # 镜 2/3/7/8/9 静态或对话镜可 --steps=4 提速
    steps = 10
    mp = 0.6
    for a in sys.argv[1:]:
        if a.startswith("--steps="):
            steps = int(a.split("=", 1)[1])
        elif a.startswith("--mp="):
            mp = float(a.split("=", 1)[1])
    shots = [int(a) for a in args] if args else sorted(TASKS)

    if resume:
        if not shots:
            print("[X] --resume 必须同时给出镜号，例：--resume=<pid> 7")
            return
        print(">>> RESUME prompt_id=%s shots=%s" % (resume, shots))
        for shot in shots:
            row = adopt(resume, shot)
            print("  镜 %-2d  %-12s %s" % row)
        return

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
            f.write("序幕一《纸飞机》视频片段 · 生成报告（跳过首帧，直接 R2V/T2V，镜 1-9）\n")
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
