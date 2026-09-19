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

★ 镜 1「校牌」的正解（2026-09-19 **第四轮**；前三轮方向已全部推翻，见 README §6.9b）：
  参考图 `school_gate_wide_v02.png` 门柱上**本来就有**一行大号金色立体校名
  （红色圆徽在上、「上汇实验学校 / Shanghai Experimental School」金色立体字在下）。
  四轮实测（读帧）：
    一轮「校牌清晰可见」        → 乱码，且跑到墙上自造招牌          ❌
    二/三轮「抹成白板」          → 校名消失 + 构图退化成墙面特写      ❌ 过度防御
    三轮改「照抄 <Picture 2>」   → 位置对了，但字错 `里江勇舱学校`    ⚠️ 半对
    四轮（本条）逐字锚点 + 推近  → **`上汇实验学校` 全对**            ✅
  ★ 第三轮为什么字错：H3 把「照抄」当成「请在这里画一些汉字」，
    便按**字形结构相似性**合成了像字的字（上→里、汇→江、实→勇、验→舱）。
  ★ 第四轮对策（两条同时用）：
    ① **把目标字符序列本身写进 prompt**（逐字列出「上汇实验学校」+ 逐词列出英文三词）
       —— 给模型明确 token 对齐，而不是让它自由合成；
    ② **机位从「全景」推到「中景」**，让字够大（0.6MP 下 38px 字必糊）。
  ⚠️ 字符锚点属**画面用途**，不是"对模型说的话"（A4 铁律）；为免被念，
     锚点放 `Audio:` 段之前且不带"读作/念作"字样，`Audio:` 只留真台词。
  ⚠️ 「不许发明参考图里没有的文字」仍然成立（横幅/标语/广告/第二块招牌/水印）。

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
# ★★ 2026-09-17 第二轮：**ONLY_THIS_LINE 又踩了同一个坑，已改为纯物理音景**
#
#   历史（两次同源错误，README §6.10.8 / §6.10.9）：
#     ① 初版：`全程只有这一个说话人的声音，只有上面这一句台词，…没有其他任何人声、`
#        `没有第二个人说话、没有旁白、没有念白、没有背景人声对白。`
#        ⇒ H3 分不清「对模型说的话」与「台词」，**把它念了出来**
#          （镜 7 ASR「你少自恋了，只有上面这一句台词」）。
#     ② 改后版本：`此段音频里只有这一句对白，其余全是教室的环境底噪…`
#        ⇒ 仍然含**语音元词汇**（"这一句对白"），ASR 残留「只有上面这一句台词」类碎片。
#
#   ★ 铁律：**只要句子在谈"语音/对白/台词/人声"本身，H3 就可能把它念出来。**
#     正解 = 完全不提语音，只描述**物理声源**：
#       · 有哪些环境声（底噪 / 摩擦声 / 电流声）
#       · 声源是什么（衣料 / 设备 / 风）
#     这样既抑制了额外人声，又不可能被念出来（因为句中没有可念的"话术"）。
#
#   ⚠️ 原文里"只有这一句对白"的功能由**台词行本身**承担：Audio 段里写了
#      `X说：<台词>`，H3 自然只念这一句。
ONLY_THIS_LINE = (
    " 其余是教室的环境底噪、衣料摩擦声与全息设备低沉的电流嗡鸣。"
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
    "远处传来低沉的轰鸣与空气流动的呼嗤声。"
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

# ★★ 2026-09-17 全片 ASR 逐镜验收发现（**并证伪了一个看起来很聪明的手段**）
#
# 现象：H3 在「说话人：台词」结构里会把台词按**发音**重建，同音字被打错：
#     稻子(dào zi) → 豆子 / 哨子 / 瘦子      （镜 55/57/60/70，4 处）
#     继光(jì guāng) → 季光 / 激光           （镜 36/42，2 处）
#     袁爷爷(yuán)  → 原夜                    （镜 61）
#     物资(wù zī)   → 日再 / 世子官           （镜 22）
#     戴好(dài)     → 带好                    （镜 103）
#
# ⛔ **第一版对策（给词加拼音锚点）实测失败、且更糟**：
#     写成 `普通稻子（dào zi）` ⇒ ASR 实得「普通**对子导爱**」；
#     写成 `物资（wù zī）`     ⇒ ASR 实得「战前**世子官**」。
#   ⇒ **括号里的拼音是一串额外 token，H3 会把它一起念进去并搅乱原词**。
#     这和 §6.10.8「对模型说的话会被念」是**同一条铁律** —— 拼音标注也是"对模型说的话"。
#
# ✅ **正解：改句子，让脆弱词不再是必念词**（或换成不易错的同义说法）。
#     H3 是按**语音 n-gram 上下文**重建的，拆词/加字/换语序都能显著降低同音错率：
#       `这是普通稻子`        → `这是最普通的稻子`
#       `就为了一株稻子？`     → `就为了稻田里的一株禾苗？`
#       `想让稻子多结一点`     → `想让稻穗多结一点谷粒`
#       `稻子会像高粱那么高`   → `稻田里的禾苗会像高粱那么高`
#       `袁爷爷……`           → `袁隆平爷爷……`
#       `战前物资紧张`        → `战前补给紧张`
#       `戴好`               → `记得戴上`
#
# ★ 若某词**必须**原样保留（如史实人名「黄继光」），则改用**换 seed 重跑**——
#   同音错是概率问题，多试一两次通常能拿到正确读法（镜 36/42 即如此处理）。
#
# ★ 另两类（见 README §6.10.9）：
#   · 镜 97：`他平静地说：<台词>` 里的**舞台指示**被念 ⇒ Audio 段只留 `他说：<台词>`
#   · 镜 46/74/105：白屏卡片镜写「听不清任何词句」⇒ H3 编造语音
#     正解：换成纯物理声源（「远处有节奏的机械轰鸣与低频震动」）
PINYIN = {}

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
# ★★★ 2026-09-19 第三轮修正（**推翻前两轮的方向**，用户判定）
#
# ⛔ 前两轮（2026-09-15 / 2026-09-17）的方向是「**压制一切文字**」：
#     二轮产物把校门墙面写成「一整片干净的米黄色，上面什么都没有」，
#     门柱只剩「纯色几何形状、不承载任何笔画」。
#   后果（读帧实测 `OUTPUT/_s1check/s1_f010.png` / `s1_f200.png`）：
#     ① 校名**彻底消失**，墙上只剩一个抽象红方块 + 一条绿条冒充「校徽/铭牌」；
#     ② 构图退化 —— 机位贴墙，「上汇实验学校大门口」变成了**墙面纹理特写**，
#        观众根本看不出这是校门（storyboard「校园展示镜」的核心功能丢了）。
#
# ★ 根因（读参考图 `school_gate_wide_v02.png` 后确认，前两轮记载有误）：
#   参考图里校名**根本不是**「门柱上的竖排小牌子（约 6px 字高）」——
#   实为**左侧门柱竖条纹木饰面上的一行大号金色金属立体字**：
#       红色圆形校徽（金色图案）在上，
#       「上汇实验学校」金色立体字在**正下方**（中文字高约 38px / 原图 1080 宽），
#       「Shanghai Experimental School」金色小字再下一行。
#   ⇒ 字**足够大、足够清晰**，R2V 完全有能力照抄。
#   ⇒ 前两轮「压掉它」= 为了躲一个**并不存在的抄不动问题**，
#     反而把参考图里本来正确的实体信息一起删了。这是**过度防御**。
#
# ✅ 本轮方向（用户原话：「参考图中已经有『上汇实验学校』字样了，保持即可，
#    不要搞成白板，对 AI 这么不自信吗？」）：
#     ① **正向要求保留参考图原有的校名与校徽**，明写它们在门柱上的**位置与形态**
#        （红圆徽在上、中英文字在下的金色立体字），让 H3 走「照抄参考图」而不是「编字」；
#     ② **禁止**的是「**参考图里没有的**额外文字」—— 横幅 / 标语 / 广告 / 水印 /
#        第二块招牌，以及**英文拼写错误**（旧版 `Scoule`）；
#     ③ 保留构图约束：机位要**看得见完整校门与门柱**，不许贴墙特写。
#
# ⚠️ 与 README §6.9 的关系：§6.9 的结论「H3 渲染中文不可靠、不要要求它写字」
#    在**这段话之前**只被镜 1 一例支撑，而那例的失败根因是
#    「我们**主动新造**了一块参考图里没有的招牌」（prompt 写「校牌清晰可见、完整入画」，
#    且当时 ref2 用的是**另一张**图）。**照抄参考图里已存在的大字**是另一回事。
#    ⇒ 本轮把 §6.9 降级为「**不要发明参考图里没有的文字**」，而非「一律不要文字」。
# ★★★ 2026-09-19 第四轮修正（实测基于第三轮产物读帧，**用户判定方向正确、需加强**）
#
# 第三轮（上面这段注释）方向对：**保留参考图原有的校名校徽**。
# 实测产物 `01_girl_mother_at_school_gate_00003_.mp4`（旧 prompt）读帧：
#     校名区域是**一片空白米黄墙**，红圆徽退化成一个抽象红方块 —— 校名消失。
# 第四轮（本条）改进 prompt 后重跑 `..._00004_.mp4`，读帧结果：
#     校名**出现了**、红圆徽也对了、位置排版与参考图一致 —— **但字是错的**：
#     实际渲染成 `里江勇舱学校 / Shanppr Apennial Shoule`，
#     正确应为 `上汇实验学校 / Shanghai Experimental School`。
#
# ★ 根因（新发现，值得写进 README）：
#   只写「照抄 <Picture 2> 里的校名」时，H3 把它当成**「请在这里画出一些汉字」**，
#   而不是「请复制这 7 个特定字符」。中文字形在潜空间里是按**结构相似性**聚类的，
#   `上汇实验学校` 与 `里江勇舱学校` 在笔画密度/部件结构上高度相似
#   ⇒ 模型合成了一串「看起来像校名的汉字」。**英文同理**（`Shoule` 是 `School` 的近形）。
#   ⇒ 结论：**照抄**这个指令对**汉字**无效，必须给出**目标字符序列本身**作为锚点。
#
# ✅ 本轮对策（三条，均针对上条根因）：
#   ① **把 7 个汉字逐字写进 prompt**，并标注中文/英文分别是哪一串 ——
#      给模型一个**明确的 token 序列**去对齐，而不是让它自由生成"像校名的字"。
#      ⚠️ 依据：本仓 README §6.10.8「对模型说的话会被念」是**音频**铁律
#         （prompt 里的说明会被当台词念）；这里写明字符是**画面**用途。
#         为避免被当台词念，把字符锚点放在 **Audio 段之前**、且**不带"读作/念作"字样**，
#         并让 Audio 段明确只含小女孩那一句台词（ONLY_THIS_LINE 已做这件事）。
#   ② **放大校名在画面里的占幅**：把机位从"全景"推到**中景**，
#      并明确「校名占据画面左上区域、每个字清晰可辨」——
#      字太小是抄不对的直接原因（0.6MP 输出下 38px 字会糊）。
#   ③ **给英文拼写逐词锚点**（`Shanghai` / `Experimental` / `School` 三个词分开写），
#      针对实测的 `Shanppr Apennial Shoule`。
#
# ⚠️ 保留第三轮的所有正确约束（红圆徽在上、门柱竖条纹木饰面、不许贴墙特写、
#    禁止参考图里没有的额外文字）。
# ⚠️ 「不要改变长相与年龄」「固定机位」等仍保留。
TASKS[1] = dict(
    slug="girl_mother_at_school_gate", seed=9101,
    ref1=G_GIRL_MOTHER, ref2=SCENE_GATE, dur=3.0,
    prompt=(
        "CUT 1: 中景镜头。一位三十多岁的母亲牵着五岁小女孩的手，站在学校大门口前，"
        "小女孩仰头看着校门上方、眼睛亮亮的，母亲低头含笑看着她；"
        "★ 机位要让观众看清这是一所学校的大门：画面里完整入画的是"
        "<Picture 2> 里那面竖条纹木饰面门柱、柱上红色圆形校徽与它下方那行金色校名立体字，"
        "以及深色金属大门与门柱 —— 不要贴到墙面上拍特写。"
        "★★ 门柱上的金色校名立体字按 <Picture 2> 原样呈现，"
        "这组字是七个汉字「上汇实验学校」，下面一行金色英文小字是"
        "「Shanghai」「Experimental」「School」三个单词；"
        "位置、字号、颜色、排版都与 <Picture 2> 一致，笔画完整、字口清晰，"
        "七个汉字就是上、汇、实、验、学、校这七个字，"
        "英文就是 Shanghai、Experimental、School 这三个词，"
        "不许替换成别的汉字、不许换成别的英文单词、不许把字母拼错；"
        "校徽是红色圆形、内部有金色图案，位于这行校名的正上方。"
        "★ 除参考图里已有的这组校名与校徽之外，画面上不得再出现任何其它文字 —— "
        "没有横幅、没有标语、没有广告、没有第二块招牌、没有落款、没有水印角标。"
        "两人的面貌、发型与服装严格照 <Picture 1>（不要改变长相与年龄）；"
        + LIGHT + "。固定机位，只留轻微手持呼吸感。\n"
        "Audio: 校门口的环境音，微风、远处隐约的校园喧闹声（后期）；"
        "小女孩说：妈妈，这个学校好漂亮！"
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
        "Audio: 校门口环境音（后期）；母亲说：那你明年就可以来这儿读书了。"
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
        "小女孩用力喊出一个拖长的语气词，先从高音起、再拖长下落：飞——喽——！"
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
        "男生问：谁扔的？是不是隔壁班暗恋我的？"
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
        "Audio: 男生说：你少自恋了。"
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
