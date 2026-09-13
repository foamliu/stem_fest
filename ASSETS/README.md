# ASSETS · 素材库规范

《如愿·看见》(`storyboard.md`，131 镜号) 的**全部输入素材**放在这里：

- 角色定妆照 → `CHARACTERS/`
- 场景参考图 → `SCENES/`
- 道具参考图 → `PROPS/`
- 画风 / 色调参考 → `STYLE/`

> 渲染产物**一律**落到 `OUTPUT/`（`OUTPUT/t2i`、`OUTPUT/video`、`OUTPUT/tts`、`OUTPUT/bgm`），
> 不要写回 `ASSETS/`。素材是"输入"，OUTPUT 是"输出"，两边永不混。

---

## ★ 第一条铁律：定妆照是外形的唯一权威

引用定妆照生成分镜图时，**prompt 里只允许填写定妆照中客观可见的稳定特征**
（发型发色 / 服装款式与颜色 / 眼镜 / 配饰）。

**禁止**写入体型、胖瘦、脸型、年龄感等描述 —— ⚠️ 注意：**把"偏胖"改成"偏瘦"同样是改外形**，
正确做法是**这类形容词一个都不写**（定妆照的形象信息由参考图本身承载，无需文字复述）；
**禁止**把 `storyboard.md` 里的性格/印象描述（如刘思齐"胖胖的"）当作外形依据。

> ✅ **正确做法**：先**用本地视觉模型（`qwen3.5`）读一遍定妆照**，把读到的**稳定可见特征**
> 写成提示词基串（见各角色卡 §2「提示词基串」）。**让定妆照说话，不要让剧本文字说话。**
>
> **反面案例（2026-09-12）**：镜 15 的 prompt 里写了"**圆脸、偏胖**"，
> 而刘思齐的定妆照实为 **瓜子脸、中等体型** → 生成的形象**比定妆照胖一圈、脸变圆**。
> 用户原话：「**既然是定妆照，请你不要再改动它了。否则定妆照还有什么意义！！！**」
>
> 分镜的"参考图提示"列只说明**该镜要引用哪张定妆照**，**不代表**可以按剧本描述改外形。

---

## ★ 第二条铁律：出图 prompt 必须带「风格后缀」

全片风格 = **超写实真人质感**（影视级真人风格）。
**正向/负向风格后缀**唯一出处 = [`STYLE/README.md`](STYLE/README.md)「★ 全片风格基准」，
本文件**不再复制一份**（避免两处版本漂移）。**每一次出图**（分镜图 / 场景图 / 道具图）
的 prompt 都要拼上正向后缀，并把负向后缀放进 `negative_prompt`。

**反面案例（2026-09-12）**：早期 prompt 只写泛泛的"**3D 动画风格**"，
结果人脸走了**迪士尼/皮克斯式的欧美化卡通**路线，被美术方否掉：

> 「不好莱坞和迪士尼风格，人脸要国内 AI 短剧（比如《万妖图录传》）风格，要符合东方审美。」

改成真人质感后缀后（含"绝对无二次元插画感、无 CG 数字人感、无塑料假人感"+
负面词"迪士尼风格/皮克斯风格/欧美面孔/夸张大眼"），生成结果被判定为
**真人摄影质感 + 东方脸 + 与定妆照同一人** ✅ —— 美术方确认采用。

> ⚠️ **风格后缀只描述"渲染质感与色调"，不得反过来规定人物外形**
> （胖瘦 / 脸型 / 五官尺寸一律由定妆照承载）。要加"东方审美"取向时用**否定式**
> （"不欧美化、不卡通化"），而不是规定具体脸型。

---

## 1. 为什么这样分层

| 层 | 用途 | 用哪个 MCP 工具 |
|----|------|-----------------|
| `CHARACTERS/` | **角色一致性唯一依据**（LESSONS #6：角色镜头必须引用定妆照，否则每张脸随机变化） | `image_edit_longcat` / `video_minimax_h3_r2v` |
| `SCENES/` | 环境、光线、构图参考（不需保角色） | `z_image_turbo_t2i` / `video_minimax_h3_t2v` |
| `PROPS/` | 纸飞机、稻谷、口罩等特写道具 | `z_image_turbo_t2i` → `video_minimax_h3_r2v`（以道具图为参考） |
| `STYLE/` | 全片画风锚点（**超写实真人质感**、色调 LUT） | 作为 prompt 参考文字/图；**出图必须带风格后缀** |

## 2. 命名硬规则（全 ASCII）

**中文目录名/文件名一律不用。** 原因：`_upload_image()`（`mcp_server/comfyui_mcp_server.py`）
遇到非 ASCII 或含空格的文件名会**重命名为随机 `mcp_ref_<hex>.png`**，导致 ComfyUI `input/`
目录无法辨认、排查困难；ASCII 名则原样保留。

| 规则 | 写法 |
|------|------|
| 编码 | `纯 ASCII`：小写字母 + 数字 + 下划线，**不用空格、不用中文、不用大写** |
| 资产目录 | `<NN>_<slug>`，`NN` 为两位序号（与 `CHARACTERS/` 的目录序号对齐，见 §2 角色总表） |
| 图片文件 | `<slug>_<view>_v<NN>.<ext>` |
| 版本 | `v01` 起递增；**不要覆盖旧图**，新版本另存 `v02`，并在该资产 `README.md` 里注明"当前使用版本" |
| 格式 | **定妆照用 `png`**（无损，供图生图）；**场景/道具的实拍原片保留 `jpg`**（无损重封装会让 8.9 MB 变 20 MB 且不增加信息）；AI 生成的场景/道具图用 `png` |
| 大小写 | 目录保持**大写** `ASSETS/CHARACTERS/`，以匹配 `.gitignore`（Linux 区分大小写） |

`<view>` 取值：

| 类型 | 允许的 view |
|------|-------------|
| 角色（**默认**） | `hero` —— **每人物仅此一张**，该角色的所有镜头都引用它 |
| 角色（选做） | `front` / `side` / `back` / `closeup` / `expr-<情绪>`：确需多机位时才追加 |
| 场景 | `wide`（全景）/ `medium` / `detail`（细节） |
| 道具 | `hero` / `detail` |

### 命名示例

```
ASSETS/CHARACTERS/01_liu_siqi/liu_siqi_hero_v01.png          ← 刘思齐定妆照（每人物一张）
ASSETS/CHARACTERS/05_huang_jiguang/huang_jiguang_hero_v01.png
ASSETS/SCENES/04_classroom_dusk/classroom_dusk_wide_v01.png
ASSETS/PROPS/01_paper_plane/paper_plane_hero_v01.png
```

### 定妆照就位状态（★ 同时是角色总表）

| # | 角色 | 文件（`CHARACTERS/` 下） | 实测规格 | 出现镜号（焦点镜口径） | 性别 | 造型基串 prompt（写进每次 prompt 开头） | 固定 seed |
|:-:|------|------|----------|------------------------|:----:|------------------------------------------|:---------:|
| 01 | 刘思齐 | `01_liu_siqi/liu_siqi_hero_v01.png` | PNG 2048×1152 RGB（横版） | 7,15,22,39,46,51,61,68,80,82,87,95,102,109,115,120,123 | **女**（定妆照核对） | 同一位初中女生，黑色中长发扎马尾，细框眼镜，白色短袖 Polo 衫（领口红色装饰），黑色长裤，红领巾 | **1101** |
| 02 | 刘思成 | `02_liu_sicheng/liu_sicheng_hero_v01.png` | PNG 2304×1728 RGB（横版） | 8,16,17,18,19,28,30,37,53,63,65,82,92,116,119,124 | **女**（镜 19「学**她**」） | 同一位初中女生，黑色中长发扎马尾，细框眼镜，白色短袖 Polo 衫，黑色长裤，红领巾 | 待填 |
| 03 | 徐畅景 | `03_xu_changjing/xu_changjing_hero_v01.png` | PNG 1536×2048 RGB（**竖版·头肩特写**） | 7,11,13,24,33,34,50,70,79,90,110,118,122 | 未写明（按定妆照） | 同一位初中男生，黑色短发，白色短袖 Polo 衫（红色领边），深色长裤，红领巾（**不戴眼镜**） | 待填 |
| 04 | 张书扬 | `04_zhang_shuyang/zhang_shuyang_hero_v01.png` | PNG 1728×2304 RGB（**竖版**） | 5,6,12,14,16,19,23,27,32,59,72,88,97,100,112,114,117,121,124,125 | 男（镜 27「他」） | 同一位初中男生，黑色短发，白色短袖 Polo 衫，黑色长裤，红领巾（**不戴眼镜**） | 待填 |
| 05 | 黄继光 | **`05_huang_jiguang/huang_jiguang_hero_v02.png`（主·已去水印）** ＋ `hero_v01`（带水印·备查） | PNG 1664×2249（v02）/ 1664×2368（v01） | 25,26,28,29,31,34,35,38,40,41,42,45,47 | 男（史实） | 同一位男性军人，黑色短发平头，军绿色立领制服（双胸袋配纽扣），军绿色长裤，军帽带红色五角星帽徽，棕色腰带 | 待填 |
| 06 | 袁隆平 | `06_yuan_longping/yuan_longping_hero_v01.png`（主·中山装）＋ `hero_v02`（备选） | PNG 2848×1600（v01）/ 2048×1152（v02） | 52,55,56,57,60,62,64,65,66,67,69,71,73,75 | 男（史实） | 同一位男性，黑色短发侧分，深灰色立领中山装（双胸袋配纽扣） | 待填 |
| 07 | 钟南山 | `07_zhong_nanshan/zhong_nanshan_hero_v01.png` | PNG 880×1184 RGB（**小图**） | 77,83,84,86,87,89,91,93,94,96,98,99,101,103,104,106 | 男（史实） | 同一位男性，黑白相间短发侧分，细金属框眼镜，深灰格纹西装，白衬衫，蓝几何领带 | 待填 |

> **配角（`CHARACTERS/_extras/`）**：08 小战士（36/38/41）、09 五岁小女孩（1/2/3）、10 妈妈（1/2）、
> 11 志愿军战士群演（21/25/34/36/37/38/41/44）—— 定妆照 2026-09-13 已全部就位。
>
> **配音台账（仅在确需后期单独补录某句台词时才用）**：同一角色必须固定 `speaker` + `seed`，
> `custom_speaker_name` 必须留空。当前已定：刘思齐 = **Vivian** / seed **1101** /「13 岁女生，上海口音，语气冷、音量低，停顿多」；
> 其余 6 人 speaker 待填（口音要点：黄继光**四川**、袁隆平**四川**、钟南山**先按普通话**、四小强上海）。

> 🔎 **2026-09-13 用 PIL 实测复核**：上表尺寸此前多行有误 —— **03 / 04 / 05 / 07 实为竖版**（头肩特写 / 半身），
> 并非"横版 16:9 三视图"。**竖版定妆照可直接当 R2V 的 `<Picture 1>`**（R2V 不要求参考图比例），不要硬裁 16:9。

> ⚠️ **三视图拼版的实际风险**：一张图里含正/侧/背三个角度，`image_edit_longcat` 有可能把三个角度
> 一起画进新镜头。若出现这种情况，把**正面那一格单独裁出来**另存为 `<slug>_front_v01.png`
> （即"选做 view"的 `front`），改引用裁好的那张，母版保留备查。
> ℹ️ 例外：**黄继光**两张是**中景 + 近景单人构图**（非三视图），本风险不适用。
>
> 📐 **16:9 单人参考图（只为 LongCat 出分镜图那条支线，R2V 不需要）**：01 刘思齐 `liu_siqi_closeup_v02_16x9.png`（2304×1296，脸占 45% ★ 镜 15 定版）、
> 02 `02_liu_sicheng_closeup_v01_16x9.png`（2304×1296）、05 `05_huang_jiguang_closeup_v01_16x9.png`（1664×936）、
> 06 `06_yuan_longping_closeup_v01_16x9.png`（1829×1029）；**03 / 04 / 07 不产出**（头肩特写脸占图高 36–47%，16:9 必切脸）。

## 3. 使用方法（相对项目根解析）

MCP 工具的 `image` / `ref_image_1` / `ref_image_2` 参数**相对项目根**
（`PROJECT_ROOT = E:\code\stem_fest`）解析，与 cwd 无关：

```
用 image_edit_longcat，
image = ASSETS/CHARACTERS/01_liu_siqi/liu_siqi_hero_v01.png
prompt = "同一位初中女生，穿八（1）班校服，站在上甘岭交通壕里，中景" ＋ **风格后缀**（见 `STYLE/README.md`）
seed = 1101
output_dir = OUTPUT/12_上甘岭/frames
```

多角色同框（≤2 人）用 R2V：

```
用 video_minimax_h3_r2v，
ref_image_1 = ASSETS/CHARACTERS/01_liu_siqi/liu_siqi_hero_v01.png   → <Picture 1>
ref_image_2 = ASSETS/CHARACTERS/05_huang_jiguang/huang_jiguang_hero_v01.png → <Picture 2>
megapixels  = 0.4   (16GB VRAM 下勿超 0.6)
```

多人（>2 人）R2V 放不下 → 必须**先合成一张合影参考图**（存 `CHARACTERS/_group/`），再喂给 R2V。

⚠️ **合成方法（2026-09-13 更正）**：**不要**用 `image_edit_longcat` 把多张脸拼图合成 —— 实测**身份全丢**
（四小强 v01：三女一男、四人一个都认不出）⇒ 改为「**每人单独出图 → 程序抠人 → 贴到同一张场景底图**」
（脚本 `OUTPUT/_diag_group_compose.py`；身份由单人配方保证、人数与站位由程序保证）。
完整做法与**还缺 20 张合影**的清单见 `README.md` §8 P0（**2026-09-13 起 `CHARACTERS/00_INDEX.md` 已并入本文件**）。
★ **2026-09-13 新增规则**：**一对一对白镜的参考图必须含对话双方** ⇒ 多人镜 89/131、去重 28 种组合。

> ⚠️ **ComfyUI 上传不覆盖同名文件**（实测 2026-09-12）：若 `input/` 里已存在同名文件，
> `comfyui_upload_image` 不会覆盖，而是存成 `名字 (1).png`、`名字 (2).png`…
> **后果**：你更新了本地图片（例如把 hero 从近景换成中景）后按原文件名引用，
> 实际拿到的还是**旧图**。
> **正确做法**：更换同名素材后，先删掉 `E:\code\ComfyUI\input\名字.png`（及 `名字 (n).png`），
> **再上传一次**，使文件名与本地一致。

## 4. 目录总览

```
ASSETS/
├── README.md                      # ★ 本文件：命名规范 + 角色总表 + seed/配音台账 + 看图方法
├── CHARACTERS/
│   ├── 01_liu_siqi/               # 刘思齐（+ liu_siqi_hero_v01/v02、closeup_v01/v02_16x9）
│   ├── 02_liu_sicheng/            # 刘思成
│   ├── 03_xu_changjing/           # 徐畅景
│   ├── 04_zhang_shuyang/          # 张书扬
│   ├── 05_huang_jiguang/          # 黄继光
│   ├── 06_yuan_longping/          # 袁隆平
│   ├── 07_zhong_nanshan/          # 钟南山
│   ├── _group/                    # 合影参考图（≥2 人镜的 R2V 前置输入）
│   └── _extras/                   # 08 小战士 / 09 小女孩 / 10 妈妈 / 11 战士群演
├── SCENES/     # 8 个场景目录 + _school_raw/（17 张实景原片池，分类见 00_SOURCE.md）
├── PROPS/      # 12 个道具目录
└── STYLE/      # README.md —— ★ 全片风格基准（风格后缀唯一出处）
```

> 📌 **2026-09-13 消肿**：原 `CHARACTERS/00_INDEX.md`、`SCENES/00_INDEX.md`、`PROPS/00_INDEX.md`
> 与 7 份角色卡 `README.md` **已合并进本文件与 `storyboard.md`/`README.md`**（19 份台账 → 4 份）。
> 现在**每个事实只写一处**，改剧本不再需要同步多份索引。
> 场景 ↔ 镜号对照见 `storyboard.md` §视觉风格总表 + 下面的 `SCENES/` 注；
> 道具 ↔ 镜号对照见 `PROPS/` 各目录里的 `<道具>_hero_v01.png` 与 `README.md` §7 的说明。

**场景 ↔ 镜号对照（并入自原 `SCENES/00_INDEX.md`）**

| # | 目录 | 场景 | 镜号 | 时间 / 天色 | 色调与光线 |
|:-:|------|------|------|-------------|------------|
| 01 | `01_school_gate` | 学校大门口 | 1-3 | 6 月底下午 | 阳光明媚、高饱和暖调 |
| 02 | `02_campus` | 校园全景 | 4 | 下午 | 阳光、亮绿 |
| 03 | `03_classroom_day` | 八（1）班教室（白天） | 5-9 | 下午 | 明亮、白平衡中性 |
| 04 | `04_classroom_dusk` | 八（1）班教室（傍晚 6 点） | 10-21 | 天还亮着 | 暖金色天光 + 蓝紫冷光 |
| 05 | `05_classroom_night` | 八（1）班教室（夜） | 113-135 | 现实只过了一小会儿 | 深蓝 + 橙红、屏幕光打脸 |
| 06 | `06_trench` | 上甘岭战前交通壕 | 22-52 | 1952-10，灰蒙蒙 | 灰绿 + 土黄（★ `trench_wide_v02` 调色锁定） |
| 07 | `07_rice_field` | 安江农校稻田 | 53-78 | 1961-07，烈日 | 稻田绿 + 阳光金黄 |
| 08 | `08_train_dining` | 高铁餐车一角 | 79-112 | 2020-01-18 夜 | 暖黄车厢 + 窗外夜色 |

> 镜 128-131 无场景图（黑屏字幕 / 三帧静帧 / 定格）；镜 9、126 复用 `03` / `05`。
> 生成参数：06/07/08 = `z_image_turbo_t2i` seed **3001/3002/3003**（1280×720，无人物）；
> 01 校门 = 学校实景原片（`_school_raw/school_raw_04`）；02 校园 = LongCat 改视角（seed 2001）。

## 5. 版本控制

`.gitignore` 已忽略 `ASSETS/**/` 下的 `png/jpg/jpeg/webp`（大图不入库），
但**保留所有 `.md` 与 `.gitkeep`** —— 即"**结构随仓库走，图片本地存**"。
换机器时把图片按同样的路径和文件名拷进来即可。

## 6. 待补素材

| 文件 | 被谁引用 | 状态 |
|------|----------|------|
| `ASSETS/配乐提示词规格.md` | `ace_step_t2audio` 工具说明（"Caption + Lyrics 双管齐下"法则） | 尚未创建 |
| `CHARACTERS/_group/liu_sicheng_zhang_shuyang_hero_v01.png` | 刘思成 + 张书扬 同框镜（16/19/121/124） | ✅ **已到位**（2026-09-13 用户提供；已抹姓名标签 + 裁水印） |
| `CHARACTERS/_group/four_students_hero_v02.png` | 四小强同框镜（9/10/43/78/85/108/113/126/131）｜v01 **❌ 报废**（混脸） | ✅ **已到位**（2026-09-13 用户提供宽幅合影；只裁不修 → 2848×1062） |
| `CHARACTERS/_group/four_students_yuan_longping_hero_v01.png` | 四小强 + 袁隆平 同框镜（49/56/57/58/60/67/69/76） | ✅ **已到位**（2026-09-13 用户提供 5 人宽幅合影；3560×1221；**零清理，像素未动**） |
| `CHARACTERS/_group/four_students_huang_jiguang_hero_v01.png` | 四小强 + 黄继光 同框镜（26/29/31/35/42/45/47/48） | ✅ **已到位**（同上；3560×1221；**零清理**） |
| `CHARACTERS/_group/four_students_zhong_nanshan_hero_v01.png` | 四小强 + 钟南山 同框镜（83/84/86/91/94/96/107） | ✅ **已到位**（同上；3560×1221；**零清理**） |
| `CHARACTERS/_group/girl_mother_hero_v01.png` | 小女孩 + 妈妈（1/2） | ✅ **已到位** |
| **以下 20 张：2026-09-13 由「裁→拼→LongCat 图生图」管线新产**（见 `README.md` §8 P0） | | |
| `liu_siqi_zhang_shuyang_hero_v01.png` | 刘思齐 + 张书扬（15） | ✅ 新产 |
| `zhang_shuyang_zhong_nanshan_hero_v01.png` | 张书扬 + 钟南山（88,89,97,98,99,100,101） | ✅ 新产 |
| `liu_siqi_zhong_nanshan_hero_v01.png` | 刘思齐 + 钟南山（87,95,102,103,104,105） | ✅ 新产 |
| `zhang_shuyang_xu_changjing_hero_v01.png` | 张书扬 + 徐畅景（13,14,23,24,33） | ✅ 新产 |
| `young_soldier_soldiers_huang_jiguang_hero_v01.png` | 小战士 + 战士群演 + 黄继光（25,38,41） | ✅ 新产 |
| `zhang_shuyang_huang_jiguang_hero_v01.png` | 张书扬 + 黄继光（27,32,111） | ✅ 新产 |
| `zhang_shuyang_yuan_longping_hero_v01.png` | 张书扬 + 袁隆平（59,72,73） | ✅ 新产 |
| `liu_siqi_yuan_longping_hero_v01.png` | 刘思齐 + 袁隆平（61,68,74） | ✅ 新产 |
| `liu_sicheng_yuan_longping_hero_v01.png` | 刘思成 + 袁隆平（63,64,65） | ✅ 新产 |
| `liu_sicheng_young_soldier_soldiers_hero_v01.png` | 刘思成 + 小战士 + 战士群演（36,37） | ✅ 新产 |
| `liu_sicheng_liu_siqi_hero_v01.png` | 刘思成 + 刘思齐（22,80） | ✅ 新产 |
| `liu_sicheng_huang_jiguang_hero_v01.png` | 刘思成 + 黄继光（28,30） | ✅ 新产 |
| `xu_changjing_yuan_longping_hero_v01.png` | 徐畅景 + 袁隆平（70,71） | ✅ 新产 |
| `four_students_soldiers_hero_v01.png` | 四小强 + 战士群演（21） | ✅ 新产 |
| `liu_siqi_zhang_shuyang_xu_changjing_hero_v01.png` | 刘思齐 + 张书扬 + 徐畅景（7） | ✅ 新产 |
| `xu_changjing_soldiers_huang_jiguang_hero_v01.png` | 徐畅景 + 战士群演 + 黄继光（34） | ✅ 新产 |
| `soldiers_huang_jiguang_hero_v01.png` | 战士群演 + 黄继光（44） | ✅ 新产 |
| `liu_siqi_huang_jiguang_hero_v01.png` | 刘思齐 + 黄继光（46） | ✅ 新产 |
| `xu_changjing_zhong_nanshan_hero_v01.png` | 徐畅景 + 钟南山（90） | ✅ 新产 |
| `liu_sicheng_zhong_nanshan_hero_v01.png` | 刘思成 + 钟南山（92） | ✅ 新产 |

> ★ 每张新合影都有两个版本：`<slug>_hero_v01.png`（**喂 R2V 用这个**，无文字）
> 与 `<slug>_hero_v01_labeled.png`（底部带人名标签栏，**只给人看**）。
> ⚠️ 别把 `_labeled` 喂给 R2V —— 参考图里的文字有被 H3 画进画面的风险。
> ⚠️ **图片文件全部被 `.gitignore` 忽略** ⇒ 这 20 张只在本地，不入库（与既有合影一致）。

> ★ **入库策略变更（2026-09-13）**：合影类参考图**默认零清理**（不改任何像素），
> 不再默认「抹标签 / 裁水印」——那些是参考图，不是成片画面；先跑 R2V 看有无泄漏，有再清。
>
> ⚠️ **还缺的合影 / 配角清单（含覆盖镜号、站位提示、出图硬要求）见 `README.md` §8 P0 #19** ——
> 拆出去的 `_group/00_要图清单.md` 已删除，内容已并入那里。
> ⛔ 2026-09-13：原「徐畅景 + 刘思齐」合影（`xu_changjing_liu_siqi_hero_v01.png`）**文件留档但当前无镜引用**
> —— 现在需要的是三人组「刘思齐 + 张书扬 + 徐畅景」（镜 7），见 `README.md` §8。

---

## 7. 用本地视觉模型「看图」（ollama + qwen3.5）★ 强烈推荐

**背景**：Cline 里驱动项目的模型**不支持图像输入**，所以"哪张照片是校门""定妆照长什么样"
这类问题原本只能靠人眼看。本机 ollama 里有一个**可用的视觉模型**正好补上这个缺口。

### 模型选择

| 模型 | 结论 |
|------|------|
| **`qwen3.5:latest`** | ★ **用这个**。9.7B / Q4_K_M / 262144 上下文；`ollama show` 的 Capabilities 含 **vision**；**原生多模态**（视觉塔内建，无独立 projector）；中文强、自带 thinking |
| `llava:latest` | ❌ **别用**。同一张图三次给出互相矛盾的答案（"校门"→"教学楼"→"否"），批量时还会复读退化 |

### 调用要点（踩过的坑）

```python
# 关键：think=False，否则思考过程会吃光 token，response 返回空字符串
payload = json.dumps({
    "model": "qwen3.5:latest",
    "prompt": "看图，用中文回答……",
    "images": [base64.b64encode(jpeg_bytes).decode()],
    "stream": False,
    "think": False,                      # ★ 必须
    "options": {"num_predict": 300, "temperature": 0.1},
}).encode("utf-8")                       # ★ 必须显式 utf-8，否则中文变问号
```

| 坑 | 现象 | 解法 |
|----|------|------|
| 不关 thinking | `response` 为**空字符串**，`done_reason=length`（token 被思考吃光） | 加 `"think": False` |
| PowerShell 发中文 | 模型收到 `???????` | body 显式 `[Text.Encoding]::UTF8.GetBytes()`，或直接用 Python |
| 图片太大 | 慢、占显存 | 缩到 **长边 1024**、JPEG q90 再送 |
| 模型库路径 | 见下方"迁移"说明 | 设 `OLLAMA_MODELS` |

### 已用它解决的问题

- `SCENES/_school_raw/` 17 张学校实景照片的**分类与用途推荐**（见其 `00_SOURCE.md` §2、§3）
- 结论：学校建筑是**橙色系外墙**；校门有**大型欢迎电子屏 + 立体校名标识**

---

## 6. 角色卡（`CHARACTERS/<NN>_<slug>/README.md`）

**2026-09-13 消肿后只剩 1 份**：`01_liu_siqi/README.md`（定版角色的完整实验记录，
含「输出尺寸 = 参考图尺寸」「denoise=1 ⇒ 必须写死景别」「脸高 ≥250 px」等**全项目通用结论**）。
其余 6 位角色的角色卡**已删除**，内容并入：

| 原本写在角色卡里的 | 现在看哪里 |
|--------------------|-----------|
| 姓名 / 身份 / 性格 / 出现镜号 / 性别 | 本文件 §2「定妆照就位状态」总表 |
| 服装发型眼镜等造型要点、造型基串 prompt | 同上（基串列） |
| 逐镜台词与表情 | `storyboard.md`（唯一权威） |
| 定妆照规格 / sha256 / 换图与防呆校验记录 | 本文件 §2 总表 ＋ `git log` |

## 7. 素材关键规格（并入自原 `SCENES/00_INDEX.md` 与 `PROPS/00_INDEX.md`）

**场景图**（8 张，均**无人物**）

| 场景 | 文件 | 规格 | 来源 / 生成参数 |
|------|------|------|------------------|
| 01 校门 | ★ `01_school_gate/school_gate_wide_v01.jpg` | JPG 4595×3064（8.9 MB） | 学校实景原片（`_school_raw/school_raw_04`）。⚠️ 画面有**积水倒影**，镜 1 是晴天，出图不要照搬 |
| 01 校门（备选角度） | `school_gate_wide_v02.png` | 1080×721 | 用户提供（分辨率低，仅作补充） |
| 02 校园全景 | ★ `02_campus/campus_wide_v01.png` | 1360×768 | LongCat（seed **2001** / 1MP / 261 s），基础图 = `school_raw_06` 裁 16:9，视角改为**略高俯视** |
| 03 教室·白天 | ★ `03_classroom_day/classroom_day_wide_v01.png` | 1920×1080 | 豆包图生图（源：用户教室白天照） |
| 04 教室·傍晚 | ★ `04_classroom_dusk/classroom_dusk_wide_v01.png` | 1920×1080 | 豆包图生图。**镜 15 小样素材** |
| 05 教室·夜晚 | ★ `05_classroom_night/classroom_night_wide_v01.png` | 1920×1080 | 豆包图生图（一台发光笔记本提供冷光源） |
| 06 战壕 | ★ `06_trench/trench_wide_v02.png`（v01 弃用） | 1280×720 | `z_image_turbo_t2i` seed **3001** ＋**调色锁定**（线性增益 R×0.93 / G×1.05 / B×0.995 → 土壁 G/R 0.946→**1.068**；脚本 `OUTPUT/_diag_grade_trench.py`，报告 `_trench_grade.json`） |
| 07 稻田 | ★ `07_rice_field/rice_field_wide_v01.png` | 1280×720 | `z_image_turbo_t2i` seed **3002** |
| 08 餐车 | ★ `08_train_dining/train_dining_wide_v01.png` | 1280×720 | `z_image_turbo_t2i` seed **3003** |

> ★ **通用原则（战壕得出的方法）**：色调 / 饱和度 / 明暗这类**可量化**的问题，优先**数值校正**，
> 不要反复重抽（重抽每次 27 s 起且不可控）。

**道具图**（12 张，`z_image_turbo_t2i` / `steps 8` / 1280×720，除 06/07 含手外**均无人物**）

| # | 文件 | seed | 备注 |
|:-:|------|:----:|------|
| 01 | `01_paper_plane/paper_plane_hero_v01.png` | 4001 | 全片核心意象（呼应《阿甘正传》羽毛），镜 3-8、126 |
| 02 | `02_holo_device/holo_device_hero_v01.png` | 4002 | 全息设备，镜 10/17/20（夹手触发第一次 Ouch） |
| 03 | `03_holo_screen/holo_screen_hero_v01.png` | 4003 | 全息屏（界面文字**故意不可读**），镜 11/122/127 |
| 04 | `04_rice_plant/rice_plant_hero_v01.png` | 4004 | 整株稻（含系布条标记那株），中景用 |
| 05 | `05_rice_ear/rice_ear_detail_v01.png` | 4005 | 稻穗特写，与 04 不要混用 |
| 06 | `06_rice_grain/rice_grain_hero_v01.png` | 4006 | ⚠️ **有手**（符合设计）；掌中谷粒，镜 74/108/120/126/130 |
| 07 | `07_mask/mask_hero_v02.png`（v01 作废） | 4007 → **7001**（LongCat） | ⚠️ **有手**；背景已由**金色稻田**换成**夜间室内深色**（四角亮度 88.8→**55.7**、R−B 67.6→**−15.7**），否则暖调会污染镜 104/105/108/120/126 的夜景 |
| 08 | `08_laptop/laptop_hero_v03.png`（中景·**空屏**）＋ `laptop_screen_detail_v02_photo.png`（屏幕特写＋贴入的老照片） | 4008 / 4013 | 中景版故意留空屏；特写版由 `OUTPUT/_diag_screen_compose.py` **数值贴合**（屏幕框 924×545 → 内缩 8% → 照片 296×422，**脸 156 px**）。⚠️ 更早版本屏幕里是**别人的照片**，与镜 111「认出他」矛盾，已作废 |
| 09 | `09_photo_huang_jiguang/photo_huang_jiguang_hero_v02.png` | 4009 | 由 LongCat 以**黄继光定妆照**为参考转 1950 年代老照片（棕褐单色 + 胶片颗粒，**8 项面部特征全一致**，1.5MP/395.7 s）。⚠️ 它是**合成影像、不是史料原图**；若老师认为应陈列真实烈士照片，请另取权威公开档案 |
| 10 | `10_doc_covid/doc_covid_detail_v02.png` | 4010 | 标题「新型冠状病毒」清晰、**正文失焦为灰块**（v01 是伪汉字乱码，作废） |
| 11 | `11_wild_vegetables/wild_vegetables_hero_v01.png` | 4011 | 柳条筐野菜，镜 21/23/25 |
| 12 | `12_ammo_gear/ammo_gear_hero_v01.png` | 4012 | 弹药木箱 + 军绿布袋，镜 21 |

> ⚠️ **道具图两个坑**：① **不需要文字的道具必须显式禁止文字**（否则模型自加界面/标签）；
> 需要文字时只让**标题清晰、其余要求失焦成灰块**。② **笔记本屏幕**要明确写出"里面该有什么"，
> 只说"内容虚化"会得到**视频会议界面 + 多彩头像**。
> ⚠️ **待人工复核**：`06_rice_grain` 与 `07_mask` 的手部机位本应一致（镜 126 要把两者放一起），
> 分类核查显示掌心朝向一致但左右手判定不稳，**用前请目视一次**。
