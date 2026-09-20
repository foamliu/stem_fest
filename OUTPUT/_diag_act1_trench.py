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

台词与镜号严格取自 `storyboard.md` §第一幕：上甘岭（战前）（1952-10~11 朝鲜战场交通壕，风雪阴冷）。

路线（与序幕一/二一致，README §7）：
  · 有角色的镜 → `video_minimax_h3_r2v`
      ref_image_1 = 角色/合影参考图 → `<Picture 1>`
      ref_image_2 = SCENES/06_trench/trench_wide_v04.png → <Picture 2>
        （★ 该图是 **2026-09-20 用户重生成的风雪阴冷版**：原木加固壕壁 +
           沙袋垛 + 弹药木箱 + 丢弃的铁锹 + 泥水洼 + 薄雪，冷灰蓝调。
           v01~v04 四张全部替换为风雪版，实测 亮度 79.8~84.9 /
           **R-B −18.1~−20.4（冷调）** / 高亮雪像素 3.5~5.2%，四张均可用；
           **v02 雪最多、v04 最暗最冷** ⇒ 取 v04。
           ⚠️ 旧记录「v04 = 深秋枯黄暖化版（R-B 24.4）」**已作废** —— 同名文件被覆盖。）
      ⇒ 因参考图是**冷调**，`LIGHT` 也必须写冷调（H3 会照抄参考图色温，§6.10.3）。
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

# 第一幕统一光线基调（storyboard：1952-10 朝鲜战场交通壕）
#
# ★ 2026-09-19 修正（**结论已被 09-20 的四次修正推翻，保留以存档教训**）：
#   当时的推理（❌ 错）：上甘岭战役 = 1952-10-14 — 11-25，打响当天是深秋，
#     于是断定「白天有太阳、地面无积雪、严寒属 11 月下旬不用」，据此改写 LIGHT。
#   ❌ **错在哪**：把第一幕**钉死在开战当天**，又只凭「当天」的天气下结论，
#     忽略了 (a) 战役持续 43 天跨 10-11 月，(b) 炮火把山头炸成粉末后
#     「爆尘浓烟遮天蔽日、老兵以为那天是阴天」——**阴冷本身就是史实**。
#   ✅ 正确结论见下方「四次修正」。唯一保留下来的正确部分：
#     **志愿军着装 = 「50式」冬服**（棉衣/棉裤/栽绒棉帽/高腰毛皮鞋）——
#     这一点不受季节争议影响，深秋与隆冬都成立，继续使用（见 GUARD_SOLDIER_WINTER）。
#   ⚠️ 四小强仍穿现代校服（白短袖 Polo + 红领巾）：他们是 2026 年进入世界模型的
#      穿越者，按设定不应换装 —— 这是刻意的时代对比，不是错误。
#      需要修正的是志愿军战士的着装（见 GUARD_SOLDIER_WINTER）与整体气候。
# ★ 2026-09-20 二次修正（**当时的修法已被四次修正取代，教训仍有效**）：
#   现象：镜 21 出「绿油油的夏天」，与镜 19 自相矛盾。
#   根因（**这条永远有效**）= H3 在「文字 vs 参考图」冲突时**倾向照抄参考图**
#     （README §6.10.3 锚点冲突）—— 当时参考图是灰绿调、文字只写「草木枯黄」一句带过。
#   当次修法（现已被取代）：把「枯黄」写成多条可执行视觉禁令。
#   ⇒ **可复用的原则**（与冷暖无关）：
#     · 光照/季节/地面状态都要写成**可执行的物理描述**，不能一句带过；
#     · 描述必须与参考图的实际色调**方向一致**，否则 H3 二选一、结果不可控；
#     · 用**正向描述**而非否定祈使句（否定词会被 H3 渲染成字幕，见 _verify_prompt_clean.py）。
# ★★ 2026-09-20 四次修正 —— **改回「风雪阴冷」，以史料为据**（推翻 09-19 的「深秋有太阳」）
#
#   ⚠️ 为什么推翻：旧 LIGHT 写「白天有太阳、光线偏硬、无积雪」，是把第一幕钉死在
#      1952-10-14 开战当天推出的结论。用户 2026-09-20 指出其与史实不符，
#      核实两条硬史料后确认**旧稿错了**：
#        · 「爆尘、浓烟遮天蔽日，以至他走访过的许多老兵们都以为那一天是个阴天」（张嵩山）
#          —— 中国网络电视台《上甘岭战役：世界现代战争史上坚守防御的典范》
#        · 「即便在零下二三十摄氏度的冬天，战士们也不畏寒冷，凿筑着新的坑道与战壕」
#          —— 新华网《揭秘上甘岭战役中坚不可摧的「地下长城」》2022-11-25
#      ⇒ 战役 43 天跨 10-11 月，**11 月的朝鲜已冰天雪地**；坑道内**积水/泥水**亦有据。
#
#   ⚠️ 同时注意 **H3 会照抄参考图色温**（README §6.10.3 锚点冲突）：
#      场景图已全部换成**风雪冷调版**（R-B −18 ~ −20），所以 LIGHT 也必须写冷调。
#      **绝不能**再写「暖金色阳光/暖高光边」—— 那会与参考图直接冲突，H3 二选一
#      （镜 36 实测：服装描述体量压过光照句 ⇒ 光照被丢弃）。
#
#   写法沿用旧稿的**正向描述**原则（不用否定祈使句 —— 否定词会被 H3 渲染成字幕，
#   见 _verify_prompt_clean.py）：不写「不要出现阳光」，而写「只有阴天的散射光」。
LIGHT = (
    "1952 年 10 月—11 月朝鲜上甘岭，深秋转入初冬："
    "炮火把山头削平，爆尘与硝烟遮天蔽日，天色阴沉，"
    "画面里只有阴天的散射光、没有直射阳光、没有明确的光源方向，"
    "冷灰蓝的色调、能见度被烟尘压低，空气寒冷刺骨；"
    "地面是被炮火反复翻搅的焦土：干硬的土块、浮土与碎石、新落的薄雪、"
    "以及坑道里积起来的泥水洼，三种质感混在一起；"
    "阵地上的工事是原木加固的壕壁、堆叠的沙袋垛、弹药木箱与丢弃的铁锹；"
    "山头被炮火削平、植被丰茂的山头寸草未剩，画面里没有草木、没有绿色植物"
)

# ★ 2026-09-20：场景图四张（v01~v04）全部由用户重生成**风雪阴冷版**。
#   实测（亮度 79.8~84.9 / R-B −18.1~−20.4 / 高亮雪像素 3.5~5.2%）：
#   四张都是风雪冷调，可任选。**v02 雪最多、v04 最暗最冷** ⇒ 取 v04 作主图，
#   与 LIGHT 的「没有直射阳光」最匹配。
#   ⚠️ 旧注释里「v04 = 深秋枯黄暖化版（R-B 24.4）」的记录**已作废**（同名文件被覆盖）。
SCENE = os.path.join(SCENES, "06_trench", "trench_wide_v04.png")

# ── 角色参考图（单人镜用定妆照）────────────────────────────
P_LIU_SIQI = os.path.join(FRAMES, "01_liu_siqi", "liu_siqi_hero_v01.png")
P_LIU_SICHENG = os.path.join(FRAMES, "02_liu_sicheng", "liu_sicheng_hero_v01.png")
P_XU = os.path.join(FRAMES, "03_xu_changjing", "xu_changjing_hero_v01.png")
P_ZHANG = os.path.join(FRAMES, "04_zhang_shuyang", "zhang_shuyang_hero_v01.png")
# ★ 黄继光主图是 hero_v02（已去水印），见 README §3 / ASSETS README §2
# ⚠️ 2026-09-20 修正：原值 `huang_jiguang_hero_v02.png` **磁盘上不存在**（镜 38 因此跑不了）。
#    镜 38 是**面部特写镜**（prompt 明写「画面几乎只有一位年轻战士的脸」），
#    故改用近景定妆图 `huang_jiguang_closeup_v01.png`（2048×1152，脸部占比大）。
P_HUANG = os.path.join(FRAMES, "05_huang_jiguang", "huang_jiguang_closeup_v01.png")
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
    "（军绿色冬季棉装与栽绒棉帽，帽子前脸是素净的同色棉布、没有星徽，"
    "不可改成其他军装、不可摘下军帽）"
)
GUARD_GLASSES = "（细框眼镜必须保留）"

# ★ 2026-09-19 新增：志愿军「50式」冬装（史实修正，用户指出 10 月场景不对）
#   依据：上甘岭战役 1952-10-14 打响，已是深秋，志愿军穿 50 式冬服。
#   只写「客观可见」的形制（不写"保暖"这类主观词，避免被当台词念）：
#     · 棉衣：厚实棉袄，战士款双肩有护肩布，袖口有袢带
#     · 棉裤：裤脚有抽带（收紧防风）
#     · 帽：栽绒棉帽（毛绒护耳，可放下），带红色五角星帽徽
#     · 鞋：高腰毛皮鞋（毛皮里子、帆布面）
#   ⚠️ 四小强**不套用**此常量（穿越者保持现代校服，形成时代对比）。
#
# ★ 2026-09-20 二次修正（镜 36 v8 读图铁证，用户「军装一定要整改」）：
#   v8 帧实测发现**三类史实错误**，全部来自 H3 对「军绿色立领军装」的默认联想
#   —— 它会漂移到 **1955 式解放军军官服**（README §6.10.3 锚点冲突）：
#     ① 领章：两领口出现**红色长方块领章**（55 式标志）—— 志愿军**没有领章**
#     ② 肩章：双肩出现**带红边的肩章/肩袢** —— 50 式志愿军冬装**没有肩章**
#     ③ 臂章：左上臂出现**红底方块图案臂章**（读图即青天白日旗样式）——
#        这是**绝对错误**：1952 年上甘岭是**中国共产党领导的人民军队**，
#        志愿军**不佩戴任何旗帜图案臂章**，胸前只有「中国人民志愿军」布胸标。
#   修法 = **正向文字锚点**（禁止否定式，见 `_verify_prompt_clean.py` BANNED 表）：
#     把「没有领章/没有肩章/没有臂章」改写成**可画的替代物**，
#     让 H3 有东西可画面不会去填空：
#       · 领口 → 「立领平整洁净，领口没有任何附加布块」
#       · 肩部 → 「双肩只有护肩布，是一整块同色棉布」
#       · 上臂 → 「两只上臂与袖管同色，平整素净」
#       · 胸前 → 正向给出唯一正当标识「左胸佩「中国人民志愿军」白底黑字布胸标」
#     ⚠️ 胸标文字是**史实必需元素**且极短（6 字），与「画面上没有任何可读文字」
#        的通用禁令冲突 ⇒ 本常量明确写成「该布胸标是唯一允许出现的文字」，
#        以**正向独家授权**方式表达，不用「不要生成其他文字」这类否定式。
# ★ 2026-09-20 三次修正（**帽徽** —— 改向"无星"，以用户实景参考图为准）：
#   ⚠️ 二次修正时写的是「**帽徽是红色五角星**」，起因是修「青天白日旗臂章」，
#      想用"正确的是红星"来压住错误臂章。**但这条现在必须去掉**，两个理由：
#     ① **与实景参考图冲突**：用户提供的上甘岭实景截图（`_50shi/in/ref_trench.png`）
#        里，战士的栽绒棉帽**前脸是素净的同色棉布、没有星徽**；
#        新生成的 50 式定妆照也是无星版。而 H3 **照抄参考图**（§6.10.3）——
#        文字写"红星"、图上是素帽 ⇒ 锚点冲突，H3 会按文字补出红星。
#     ② **史实上确实无星**：1952 年志愿军的栽绒棉帽（护耳冬帽）**不佩戴星徽**；
#        戴星的是**大檐帽/解放帽**等常服帽，与冬装棉帽不是一回事。
#   ⇒ 修法：把「帽徽是红色五角星」改写为**正向的替代物**——
#      「帽子的前脸是一整块同色棉布、平整素净」（沿用二次修正"给替代物"的思路）。
#   ⚠️ 连带经验（README §6.10.17 F2）：**R2V 是参考图锁形**。
#      既然参考图是素帽，文字就不该反着写；这次是"文字与图打架"的又一例。
#
GUARD_SOLDIER_WINTER = (
    "★ 志愿军战士一律穿 1950 年代的志愿军冬季棉装：厚实的军绿色棉袄与棉裤、"
    "战士款棉袄双肩有护肩布、裤脚有抽带；头戴栽绒棉帽、毛绒护耳可放下、"
    "帽子的前脸是一整块同色棉布、平整素净；脚穿高腰毛皮鞋；"
    "画面里没有穿单衣、戴单帽、露出手臂或脖子的人。"
    "军装的标识形制是志愿军样式：立领平整、领口是素净的同色棉布、"
    "双肩只有一整块同色护肩布、两只上臂与袖管同为军绿色且平整素净，"
    "胸前只有左胸一处白底黑字的「中国人民志愿军」布胸标，"
    "该布胸标是全画面唯一可读的文字标识。"
)

# ★★ 2026-09-20 镜 36 专项补丁 —— **已由 `LIGHT_WARM` 改为 `LIGHT_TONE`（冷调）**
#
#   ⚠️ 历史（保留以存档教训）：旧版 `LIGHT_WARM` 是为了把镜 36「丢掉的暖阳光」抢回来，
#      写法是「暖金色阳光 / 暖亮高光边 / 暖黄赭石 / 暖调为主」。
#   ❌ **2026-09-20 用户重生成场景图（风雪阴冷版）后，该常量整体作废** ——
#      参考图已是冷调（R-B −18 ~ −20），而 H3 **会照抄参考图色温**（§6.10.3）。
#      此时再写「暖金色阳光」= 文字与图**正面冲突**，H3 会二选一，结果不可控。
#   ✅ 新常量 `LIGHT_TONE` 改为**与冷调参考图一致的补充描述**：
#      把「阴天散射光、无直射光源」写成**可执行的物理描述**，
#      并给出**可见后果**（影子边界柔和而不锐利、雪面与湿泥反出冷灰的天光）。
#
#   为什么仍需要这个"补充"常量（不是直接用 LIGHT 就够）：
#     镜 36 的实测教训 —— `GUARD_SOLDIER_WINTER` 约 100 字全是具体可画物件，
#     在 prompt 里体量压过 LIGHT 的光照句 ⇒ H3 把光照当次要信息（README §6.10.14）。
#     额外一段"光照专述"能把注意力拉回来。**这条经验与冷暖无关，继续有效。**
#
#   ⚠️ 措辞纪律（见 `_verify_prompt_clean.py` 的 BANNED 表）：
#     全部写成**对画面的正向物理描述**，不含「本镜/不要生成/若画面」这类对模型说的话，
#     也不含「一种…的X」抽象情绪名词化写法 —— 否则会被 H3 渲染成字幕或被当台词念。
LIGHT_TONE = (
    "光照是阴天散射的冷光，光源被爆尘与硝烟遮住、看不到日头，"
    "因此人物脸上没有硬边阴影、影子的边界是柔和的，"
    "雪面与坑道积水反出冷灰的天光，"
    "人物的肩头、帽檐与脸颊只有天光的柔和包裹光而非直射阳光，"
    "土壁是湿冷的深褐与灰黑，全片以冷灰蓝为基调。"
)


# ★ 2026-09-15 视觉检查修复：旧版是否定式指令（「本镜不要生成任何…」），
# H3 会把指令本身渲染成画面字幕。新版 = 纯正向音景描述，不含可读词句。
NO_SPEECH = (
    "野外开阔地的环境底噪；风吹过土壁与沙袋的气流声；"
    "远处有节奏的机械轰鸣与低频震动，持续而平稳。"
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
        "稍远处有几名穿军绿色冬季棉装的志愿军战士正蹲着整理弹药箱、用铁锹挖野菜；"
        "五人的面貌、发型、服装严格照 <Picture 1>；"
        "环境是 <Picture 2> 那条风雪阴冷的战前交通壕：土壁、沙袋、弹坑、低处积着泥水；"
        + LIGHT + "。镜头缓慢横摇（slow pan）扫过整条坑道，从左侧的战士摇到右侧的四位学生。\n" +
            GUARD_SOLDIER_WINTER +
        "Audio: 野外开阔地的环境底噪；风吹过土壁与沙袋的气流声；"
        "远处有节奏的机械轰鸣与低频震动，持续而平稳。"
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
        "背景是 <Picture 2> 那条风雪阴冷的战前交通壕，土壁与沙袋，壕壁上是原木与堆叠的沙袋、低处有积水；"
        + LIGHT + "。镜头轻微手持晃动（subtle handheld），跟着她的视线缓慢横摇。\n"
        "Audio: 风声与远处零星炮响（后期）；女生说：这里……好像还没打起来？"
    ),
)

TASKS[21] = dict(
    slug="zhang_crouches_looks_at_wild_veg", seed=9702,
    ref1=G_ZHANG_XU, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 中景双人镜头，两位初中生处于同一光照环境、画面是一个完整连续的空间："
        "左边那位（男生）蹲在交通壕边上，伸手拨开一丛贴着地面长出的干枯野菜低头打量，"
        "表情是好奇加嫌弃；那丛野菜叶片发干、边缘卷起、上面压着薄雪，是从焦土里冒出来的最后一点野菜；"
        "右边那位（男生，不戴眼镜）站在他身后侧；"
        "两人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那条风雪阴冷的战前交通壕，土壁上是原木加固的痕迹、堆叠的沙袋、地面浮土里落着一层薄雪；"
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
        "背景是 <Picture 2> 那条风雪阴冷的战前交通壕，土壁与堆叠的沙袋、地面的薄雪；"
        + LIGHT + "。镜头固定不动。\n"
        "Audio: 风声（后期）；左边的男生压低声音说：别乱动。战前补给紧张。"
    ),
)

TASKS[23] = dict(
    slug="huang_shares_wild_veg_with_young_soldier", seed=9704,
    ref1=G_YOUNG_SOL_HUANG, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 中景三人镜头，三人蹲在交通壕里同一处、处于同一光照环境、"
        "画面是一个完整连续的空间：中间那位（穿军绿色冬季棉装、戴栽绒棉帽的年轻战士）"
        "正在帮炊事班分拣一堆野菜，把手里几片好的菜叶挑出来拨给身边那位年纪更小的战士；"
        "小战士伸手去接；稍远处另一位战士低头整理弹药；"
        "三人的面貌、发型与服装严格照 <Picture 1>" + GUARD_HUANG + "；" +
            GUARD_SOLDIER_WINTER +
        "背景是 <Picture 2> 那条风雪阴冷的战前交通壕，土壁与沙袋；"
        + LIGHT + "。镜头缓慢向前推近（slow dolly in）落到他们分菜的手上。\n"
        "Audio: 野外开阔地的环境底噪；风吹过土壁与沙袋的气流声；"
        "远处有节奏的机械轰鸣与低频震动，持续而平稳。"
    ),
)

TASKS[24] = dict(
    slug="huang_looks_up_sees_four_smiles", seed=9705,
    ref1=G_FOUR_HUANG, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 中景多人镜头，五个人（四位穿白色短袖 Polo 衫系红领巾的初中生，"
        "与一位穿军绿色冬季棉装、戴栽绒棉帽的年轻战士）站在同一段交通壕里、"
        "处于同一光照环境、画面是一个完整连续的空间："
        "军装战士蹲着抬起头，视线落到面前四位学生身上，愣了一下、然后友善地笑了笑；"
        "五人的面貌、发型、眼镜与服装严格照 <Picture 1>" + GUARD_HUANG + "；" +
            GUARD_SOLDIER_WINTER +
        "背景是 <Picture 2> 那条风雪阴冷的战前交通壕，土壁与沙袋；"
        + LIGHT + "。镜头固定，随后轻微向后拉（slight pull back）。\n"
        "Audio: 风声（后期）；战士问：你们是哪个部队的？"
    ),
)

TASKS[25] = dict(
    slug="zhang_steps_forward_almost_slips", seed=9706,
    ref1=G_ZHANG_HUANG, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 中景双人镜头，一位穿白色短袖 Polo 衫系红领巾的初中男生与一位"
        "穿军绿色冬季棉装、戴栽绒棉帽的年轻战士面对面站在交通壕里、处于同一光照环境、"
        "画面是一个完整连续的空间：男生往前迈了一步、嘴快地说到一半突然意识到不对、"
        "话音卡住、表情有点慌，身体向后一僵；战士静静看着他、没有接话；"
        "两人的面貌、发型与服装严格照 <Picture 1>" + GUARD_HUANG + "；" +
            GUARD_SOLDIER_WINTER +
        "背景是 <Picture 2> 那条风雪阴冷的战前交通壕，土壁与沙袋；"
        + LIGHT + "。镜头轻微手持晃动（subtle handheld），跟着他上前的脚步。\n"
        "Audio: 风声（后期）；男生说：我们不是这个部队的，我们是从——"
    ),
)

TASKS[26] = dict(
    slug="sicheng_pulls_him_back_confesses", seed=9707,
    ref1=G_SICHENG_HUANG, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 中景双人镜头，一位戴细框眼镜、穿白色短袖 Polo 衫系红领巾的初中女生与一位"
        "穿军绿色冬季棉装、戴栽绒棉帽的年轻战士面对面站在交通壕里、处于同一光照环境、"
        "画面是一个完整连续的空间：女生伸手拉了一下身后同伴的胳膊、把他挡在身后，"
        "然后自己站到前面，抬眼看着战士、神情认真而坦诚地说出实话；战士安静地听着；"
        "两人的面貌、发型、眼镜与服装严格照 <Picture 1>" + GUARD_GLASSES + GUARD_HUANG + "；" +
            GUARD_SOLDIER_WINTER +
        "背景是 <Picture 2> 那条风雪阴冷的战前交通壕，土壁与沙袋；"
        + LIGHT + "。镜头固定，轻微横移（slow lateral move）。\n"
        "Audio: 风声（后期）；女生说：我们是从未来来的。74年后。"
    ),
)

TASKS[27] = dict(
    slug="huang_silent_then_says_future", seed=9708,
    ref1=G_FOUR_HUANG, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 近景多人镜头，五个人（四位穿白色短袖 Polo 衫系红领巾的初中生，"
        "与一位穿军绿色冬季棉装、戴栽绒棉帽的年轻战士）在交通壕里、处于同一光照环境、"
        "画面是一个完整连续的空间：军装战士没有说话，只是挨个看进四位学生的眼睛里、"
        "沉默了几秒，脸上的笑意慢慢收住，然后平静地开口；四位学生屏住呼吸看着他；"
        "五人的面貌、发型、眼镜与服装严格照 <Picture 1>" + GUARD_HUANG + "；" +
            GUARD_SOLDIER_WINTER +
        "背景是 <Picture 2> 那条风雪阴冷的战前交通壕，土壁与沙袋；"
        + LIGHT + "。镜头缓慢向前推近（slow dolly in），气氛安静下来。\n"
        "Audio: 风声（后期）；战士说：未来？你们说未来？"
    ),
)

TASKS[28] = dict(
    slug="sicheng_nods_2026", seed=9709,
    ref1=G_SICHENG_HUANG, ref2=SCENE, dur=2.0,
    prompt=(
        "CUT 1: 近景双人镜头，一位戴细框眼镜、穿白色短袖 Polo 衫系红领巾的初中女生与一位"
        "穿军绿色冬季棉装、戴栽绒棉帽的年轻战士面对面、处于同一光照环境、"
        "画面是一个完整连续的空间：女生用力点了一下头，眼神坚定；战士在她对面看着；"
        "两人的面貌、发型、眼镜与服装严格照 <Picture 1>" + GUARD_GLASSES + GUARD_HUANG + "；" +
            GUARD_SOLDIER_WINTER +
        "背景是 <Picture 2> 那条风雪阴冷的战前交通壕，土壁虚化；"
        + LIGHT + "。镜头固定不动。\n"
        "Audio: 风声（后期）；女生说：二零二六年。"
    ),
)

TASKS[29] = dict(
    slug="huang_asks_about_our_country", seed=9710,
    ref1=G_FOUR_HUANG, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 中景多人镜头，五个人（四位穿白色短袖 Polo 衫系红领巾的初中生，"
        "与一位穿军绿色冬季棉装、戴栽绒棉帽的年轻战士）在交通壕里、处于同一光照环境、"
        "画面是一个完整连续的空间：军装战士问出一个所有人都没想到的问题，"
        "、带着一点不确定的期待，眼神认真；四位学生一时都愣住了；"
        "五人的面貌、发型、眼镜与服装严格照 <Picture 1>" + GUARD_HUANG + "；" +
            GUARD_SOLDIER_WINTER +
        "背景是 <Picture 2> 那条风雪阴冷的战前交通壕，土壁与沙袋；"
        + LIGHT + "。镜头缓慢向前推近（slow dolly in）。\n"
        "Audio: 风声（后期）；军装战士问：那……咱们国家，现在啥样了？"
    ),
)

TASKS[30] = dict(
    slug="zhang_blurts_out_amazing", seed=9711,
    ref1=G_ZHANG_HUANG, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 近景双人镜头，一位穿白色短袖 Polo 衫系红领巾的初中男生与一位"
        "穿军绿色冬季棉装、戴栽绒棉帽的年轻战士面对面、处于同一光照环境、"
        "画面是一个完整连续的空间：男生嘴快、眼睛发亮，一口气往外报、"
        "手还比划着，表情是压不住的兴奋；战士安静地看着他；"
        "两人的面貌、发型与服装严格照 <Picture 1>" + GUARD_HUANG + "；" +
            GUARD_SOLDIER_WINTER +
        "背景是 <Picture 2> 那条风雪阴冷的战前交通壕，土壁虚化；"
        + LIGHT + "。镜头固定不动。\n"
        "Audio: 风声（后期）；男生说：那可太牛了！高铁、空间站、人工智能——"
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
        #        ② 正向写「光线来源」而不是只写「深秋干冷」；
        #        ③ 换 seed（旧 seed 落在坏支上）。
        "CUT 1: 风雪阴冷的战前交通壕里，土壁与沙袋堆成的壕壁占满背景，"
        "壕壁上是原木与沙袋垛、地面是炮火翻搅过的焦土与薄雪、低处积着泥水；"
        "坑道口透进一线微光、被炸松的焦土与弹坑；"
        "中近景双人镜头，两位穿白色短袖 Polo 衫系红领巾的初中男生站在壕沟里、"
        "处在同一光照环境、画面是一个完整连续的空间："
        "左边那位（男生，不戴眼镜）神情冷静、抬起手腕轻轻碰了一下身边同伴的胳膊，"
        "动作很轻、是提醒的意思；右边那位（男生）还在兴头上；"
        "两人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那条风雪阴冷的战前交通壕，土壁与沙袋；"
        + LIGHT + "。镜头固定不动。\n"
        "Audio: 风声（后期）；男生说：你慢一点，吓着人家。"
    ),
)

TASKS[32] = dict(
    slug="xu_answers_politely", seed=9713,
    ref1=G_XU_SOL_HUANG, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 中景三人镜头，一位穿白色短袖 Polo 衫系红领巾的初中男生（不戴眼镜）、"
        "一位穿军绿色冬季棉装戴栽绒棉帽的年轻战士，与稍远处另一名志愿军战士，"
        "站在同一段交通壕里、处于同一光照环境、画面是一个完整连续的空间："
        "男生面对这位陌生战士，神情礼貌、地回答，"
        "每说一句都轻轻点头、说得很认真；战士蹲着听，眼神一点点亮起来；"
        "三人的面貌、发型与服装严格照 <Picture 1>" + GUARD_HUANG + "；" +
            GUARD_SOLDIER_WINTER +
        "背景是 <Picture 2> 那条风雪阴冷的战前交通壕，土壁与沙袋；"
        + LIGHT + "。镜头缓慢向前推近（slow dolly in）。\n"
        "Audio: 风声（后期）；男生回答：大家都能吃饱。每个孩子都能上学。"
    ),
)

TASKS[33] = dict(
    slug="huang_eyes_light_up_mother", seed=9714,
    ref1=G_FOUR_HUANG, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 近景多人镜头，五个人（四位穿白色短袖 Polo 衫系红领巾的初中生，"
        "与一位穿军绿色冬季棉装、戴栽绒棉帽的年轻战士）在交通壕里、处于同一光照环境、"
        "画面是一个完整连续的空间：军装战士的眼睛突然亮了一下、嘴角不由自主地扬起来，"
        "目光越过眼前、落在远处的地平线上；四位学生围看着他；"
        "五人的面貌、发型、眼镜与服装严格照 <Picture 1>" + GUARD_HUANG + "；" +
            GUARD_SOLDIER_WINTER +
        "背景是 <Picture 2> 那条风雪阴冷的战前交通壕，土壁虚化；"
        + LIGHT + "。镜头固定，轻微向前推近（slight push in）到他的脸。\n"
        "Audio: 风声（后期）；军装战士说：那就好。我娘在四川，总饿肚子。"
    ),
)

TASKS[34] = dict(
    slug="young_soldier_asks_did_we_win", seed=9715,
    ref1=G_SICHENG_YOUNG_SOL, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 中近景三人镜头，一位戴细框眼镜、穿白色短袖 Polo 衫系红领巾的初中女生，"
        "一位穿着偏大的军绿色冬季棉装的年轻战士（不戴领章），"
        "与稍远处另一名志愿军战士，站在同一段交通壕里、处于同一光照环境、"
        "画面是一个完整连续的空间：小战士凑到女生跟前、仰着脸、"
        "眼里满是急切地问了一句话；女生低头看着他；"
        "三人的面貌、发型、眼镜与服装严格照 <Picture 1>" + GUARD_GLASSES + "；"
        "背景是 <Picture 2> 那条风雪阴冷的战前交通壕，土壁与沙袋；"
        + LIGHT + "。镜头固定，轻微横移（slow lateral move）。\n" +
            GUARD_SOLDIER_WINTER +
        "Audio: 风声（后期）；小战士问：那咱们打赢了吗？"
    ),
)

TASKS[35] = dict(
    slug="sicheng_nods_we_won", seed=9716,
    ref1=G_SICHENG_YOUNG_SOL, ref2=SCENE, dur=2.0,
    prompt=(
        "CUT 1: 近景双人镜头，一位戴细框眼镜、穿白色短袖 Polo 衫系红领巾的初中女生，"
        "与一位穿着偏大军绿色冬季棉装的年轻战士（不戴领章），"
        "面对面站在同一段交通壕里、处于同一光照环境、画面是一个完整连续的空间："
        "女生深深地、用力地点了一下头，眼神毫不含糊；小战士仰头看着她；"
        "两人的面貌、发型、眼镜与服装严格照 <Picture 1>" + GUARD_GLASSES + "；"
        "背景是 <Picture 2> 那条风雪阴冷的战前交通壕，土壁虚化；"
        + LIGHT + "。镜头固定不动。\n" +
            GUARD_SOLDIER_WINTER +
        "Audio: 风声（后期）；女生用力说：打赢了。"
    ),
)

TASKS[36] = dict(
    slug="young_soldier_relieved_huang_smiles", seed=9740,
    ref1=G_YOUNG_SOL_HUANG, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 中景三人镜头，一位穿着偏大军绿色冬季棉装的年轻战士，"
        "一位穿军绿色冬季棉装戴栽绒棉帽的年轻战士，与稍远处另一名志愿军战士，"
        "蹲在同一段交通壕里、处于同一光照环境、画面是一个完整连续的空间："
        "小战士长长松了一口气、整个人松下来、笑起来，转头去喊身边的人；"
        "戴军帽的战士也跟着笑了，低头看着他；"
        "三人的面貌、发型与服装严格照 <Picture 1>" + GUARD_HUANG + "；" +
            GUARD_SOLDIER_WINTER +
        "背景是 <Picture 2> 那条风雪阴冷的战前交通壕，土壁与沙袋；"
        + LIGHT + "。" + LIGHT_TONE + "。镜头缓慢向后拉（slow pull back）；画面上的文字元素只有战士左胸那处布胸标，其余地方是干净的土壁、沙袋、军装与天空，人物脸上只有表演。\n"
        "Audio: 风声（后期）；小战士压着嗓子兴奋喊：黄继光哥！你听见没！打赢了！"
    ),
)

TASKS[37] = dict(
    slug="siqi_softly_no_more_war", seed=9718,
    ref1=P_LIU_SIQI, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 近景半身镜头，人物占画面高度约三分之二。"
        "一位戴细框眼镜、穿白色短袖 Polo 衫系红领巾的初中女生，"
        "神情有点犹豫、地补了一句，眼睛看着地面又抬起来；"
        "她的面貌、发型、眼镜与服装严格照 <Picture 1>" + GUARD_GLASSES + "；"
        "背景是 <Picture 2> 那条风雪阴冷的战前交通壕，土壁虚化，壕壁上是原木与沙袋、低处有积水；"
        + LIGHT + "。镜头缓慢向前推近（slow dolly in）。\n"
        "Audio: 风声（后期）；女生说：还有……不用打仗了。"
    ),
)

TASKS[38] = dict(
    slug="huang_smiles_slowly_closeup", seed=9719,
    ref1=P_HUANG, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 面部特写镜头（close-up），画面几乎只是一位年轻战士的脸；"
        "他穿军绿色冬季棉装、戴栽绒棉帽，脸上沾着一点尘土，"
        "慢慢露出一个很轻、很干净的笑，眼神望向画面外的远处，目光望着远方、眼睛微微发亮；"
        + GUARD_HUANG + "；" +
            GUARD_SOLDIER_WINTER +
        "背景是 <Picture 2> 那条风雪阴冷的战前交通壕，土壁完全虚化；"
        + LIGHT + "。镜头缓慢向前推近（slow dolly in）到他的眼睛。\n"
        "Audio: 风声（后期）；战士说：那我要活到那时候，亲眼看看。"
    ),
)

TASKS[39] = dict(
    slug="young_soldier_and_huang_promise", seed=9720,
    ref1=G_YOUNG_SOL_HUANG, ref2=SCENE, dur=8.0,
    prompt=(
        "CUT 1: 手部特写镜头（close-up）。一位穿着偏大军绿色冬季棉装的年轻战士"
        "（不戴领章）伸出手，拉住身边那位穿军绿色冬季棉装、戴栽绒棉帽的"
        "年轻战士的手，两只沾着泥土的手握在一起、用力晃了晃；"
        "镜头落在这两只握着的手上，两人的手与军装严格照 <Picture 1>" + GUARD_HUANG + "；" +
            GUARD_SOLDIER_WINTER +
        "背景是 <Picture 2> 那条风雪阴冷的战前交通壕，土壁与沙袋完全虚化；"
        + LIGHT + "。镜头缓慢向前推近（slow dolly in），到握手动作为止。\n"
        "Audio: 风声（后期）；小战士：打完仗一起回去。"
        "你去看你娘，我去看我妹妹。接着另一个更沉稳的声音应了一声：说好了。"
    ),
)

TASKS[40] = dict(
    slug="huang_asks_do_you_know_us", seed=9721,
    ref1=G_FOUR_HUANG, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 中景多人镜头，五个人（四位穿白色短袖 Polo 衫系红领巾的初中生，"
        "与一位穿军绿色冬季棉装、戴栽绒棉帽的年轻战士）在交通壕里、处于同一光照环境、"
        "画面是一个完整连续的空间：军装战士转过头，把视线从一个人移到另一个人，"
        "看着这四位学生，神色认真、带着一点小心地问了一句话；"
        "五人的面貌、发型、眼镜与服装严格照 <Picture 1>" + GUARD_HUANG + "；" +
            GUARD_SOLDIER_WINTER +
        "背景是 <Picture 2> 那条风雪阴冷的战前交通壕，土壁与沙袋；"
        + LIGHT + "。镜头固定，轻微横摇（slow pan）从一个学生移到另一个。\n"
        "Audio: 风声（后期）；战士问：那……你们知道我们吗？"
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
        "环境是 <Picture 2> 那条风雪阴冷的战前交通壕，土壁、沙袋与弹坑，壕壁上是原木与沙袋、地面浮土里落着一层薄雪；"
        + LIGHT + "。镜头固定不动，留出一秒安静。\n"
        "Audio: 风声（后期）；女生说：知道。我们都知道。"
    ),
)

TASKS[42] = dict(
    slug="shell_lands_soldier_summoned", seed=9723,
    ref1=G_SOL_HUANG, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 中景双人镜头，两名穿军绿色冬季棉装、戴栽绒棉帽的志愿军战士"
        "站在同一段交通壕里、处于同一光照环境、画面是一个完整连续的空间："
        "远处一发炮弹落地、画面与人物随之剧烈一晃，"
        "左边的战士猫着腰急跑过来、一把扶住壕壁，冲着右边那位急促地喊话；"
        "右边那位战士闻声站直、神情瞬间转为严肃；"
        "两人的面貌、发型与服装严格照 <Picture 1>" + GUARD_HUANG + "；" +
            GUARD_SOLDIER_WINTER +
        "背景是 <Picture 2> 那条风雪阴冷的战前交通壕，土壁与硝烟；"
        + LIGHT + "。镜头轻微手持晃动（handheld shake），在炮响的瞬间明显一震。\n"
        "Audio: 炮响与尘土声（后期）；战士急促喊：黄继光！营部通知，准备出发了。"
    ),
)

TASKS[43] = dict(
    slug="huang_stands_tells_them_to_go_back", seed=9724,
    ref1=G_FOUR_HUANG, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 中景多人镜头，五个人（四位穿白色短袖 Polo 衫系红领巾的初中生，"
        "与一位穿军绿色冬季棉装、戴栽绒棉帽的年轻战士）在交通壕里、处于同一光照环境、"
        "画面是一个完整连续的空间：军装战士扶着壕壁站起来，拍掉身上的土，"
        "挨个看了看面前四位学生，然后笑了，语气目光一直跟着他们、手停在半空没有放下；"
        "四位学生抬头看着他；"
        "五人的面貌、发型、眼镜与服装严格照 <Picture 1>" + GUARD_HUANG + "；" +
            GUARD_SOLDIER_WINTER +
        "背景是 <Picture 2> 那条风雪阴冷的战前交通壕，土壁与沙袋；"
        + LIGHT + "。镜头缓慢向后拉（slow pull back）。\n"
        "Audio: 风声（后期）；军装战士笑着说：你们该回去了。这里不是你们该待的地方。"
    ),
)

TASKS[44] = dict(
    slug="siqi_asks_his_name", seed=9725,
    ref1=G_SIQI_HUANG, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 近景双人镜头，一位戴细框眼镜、穿白色短袖 Polo 衫系红领巾的初中女生"
        "与一位穿军绿色冬季棉装、戴栽绒棉帽的年轻战士面对面、处于同一光照环境、"
        "画面是一个完整连续的空间：女生想说什么、张了张嘴又停了一下，"
        "终于开口问了一句，眼神里带着明知道可能问不出答案的犹豫；"
        "战士安静地看着她、还没回答；"
        "两人的面貌、发型、眼镜与服装严格照 <Picture 1>" + GUARD_GLASSES + GUARD_HUANG + "；" +
            GUARD_SOLDIER_WINTER +
        "背景是 <Picture 2> 那条风雪阴冷的战前交通壕，土壁虚化；"
        + LIGHT + "。镜头缓慢向前推近（slow dolly in）。\n"
        "Audio: 风声（后期）；女生犹豫问：你……你叫什么名字？"
    ),
)

TASKS[45] = dict(
    slug="huang_turns_waves_goodbye", seed=9726,
    ref1=G_FOUR_HUANG, ref2=SCENE, dur=5.0,
    prompt=(
        "CUT 1: 全景多人镜头，五个人（四位穿白色短袖 Polo 衫系红领巾的初中生，"
        "与一位穿军绿色冬季棉装、戴栽绒棉帽的年轻战士）在交通壕里、处于同一光照环境、"
        "画面是一个完整连续的空间：军装战士背起枪、转身沿着交通壕往坑道深处走了几步，"
        "走到一半忽然回头，冲身后四名学生挥了挥手，笑了一下，然后继续往远处走去；"
        "四位学生站在原地目送他；"
        "五人的面貌、发型、眼镜与服装严格照 <Picture 1>" + GUARD_HUANG + "；" +
            GUARD_SOLDIER_WINTER +
        "环境是 <Picture 2> 那条风雪阴冷的战前交通壕，土壁、沙袋与延伸向远处的壕沟；"
        + LIGHT + "。镜头跟随他移动（tracking shot），随后缓慢向后拉（slow pull back），"
        "他的身影在坑道尽头越来越小。\n"
        "Audio: 风声与口琴声（后期）；战士说：我姓黄。黄继光。"
    ),
)

TASKS[46] = dict(
    slug="white_screen_diary_text_transition", seed=9727,
    ref1=None, ref2=None, dur=6.0,
    prompt=(
        "CUT 1: 纯白画面转场。画面从一片风雪阴冷的战壕色调迅速被刺眼的白光完全吞没，"
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

