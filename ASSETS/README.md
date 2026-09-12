# ASSETS · 素材库规范

《如愿·看见》(`storyboard.md`，139 镜号) 的**全部输入素材**放在这里：

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

全片风格 = **超写实真人质感**（影视级真人风格）。**每一次出图**（分镜图 / 场景图 / 道具图）
的 prompt 都要拼上 `ASSETS/STYLE/README.md` 里的**正向风格后缀**，并把**负向风格后缀**
放进 `negative_prompt`。

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
| `PROPS/` | 纸飞机、稻谷、口罩等特写道具 | `z_image_turbo_t2i` → `video_minimax_h3_i2v` |
| `STYLE/` | 全片画风锚点（**超写实真人质感**、色调 LUT） | 作为 prompt 参考文字/图；**出图必须带风格后缀** |

## 2. 命名硬规则（全 ASCII）

**中文目录名/文件名一律不用。** 原因：`_upload_image()`（`mcp_server/comfyui_mcp_server.py`）
遇到非 ASCII 或含空格的文件名会**重命名为随机 `mcp_ref_<hex>.png`**，导致 ComfyUI `input/`
目录无法辨认、排查困难；ASCII 名则原样保留。

| 规则 | 写法 |
|------|------|
| 编码 | `纯 ASCII`：小写字母 + 数字 + 下划线，**不用空格、不用中文、不用大写** |
| 资产目录 | `<NN>_<slug>`，`NN` 为两位序号（与 `00_INDEX.md` 对齐） |
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

### 定妆照就位状态

| # | 角色 | 文件 | 实测规格 | 状态 |
|:-:|------|------|----------|:----:|
| 01 | 刘思齐 | `CHARACTERS/01_liu_siqi/liu_siqi_hero_v01.png` | PNG 2848×1600 RGB（16:9 三视图拼版） | ✅ 已就位 |
| 02 | 刘思成 | `CHARACTERS/02_liu_sicheng/liu_sicheng_hero_v01.png` | PNG 2048×1152 RGB（16:9 三视图拼版，明亮中性底） | ✅ 已就位 |
| 03 | 徐畅景 | `CHARACTERS/03_xu_changjing/xu_changjing_hero_v01.png` | PNG 2848×1600 RGB（16:9 三视图拼版） | ✅ 已就位 |
| 04 | 张书扬 | `CHARACTERS/04_zhang_shuyang/zhang_shuyang_hero_v01.png` | PNG 2048×1152 RGB（16:9，明亮中性底） | ✅ 已就位 |
| 05 | 黄继光 | `CHARACTERS/05_huang_jiguang/huang_jiguang_hero_v01.png`（另有 `closeup_v01` 近景） | PNG 2048×1152 RGB（中景 + 近景，土黄暖调） | ✅ 已就位 ×2 |
| 06 | 袁隆平 | `CHARACTERS/06_yuan_longping/yuan_longping_hero_v01.png`（另有 v02 备选） | PNG 2048×1152 RGB（16:9 三视图拼版） | ✅ 已就位 ×2 |
| 07 | 钟南山 | `CHARACTERS/07_zhong_nanshan/zhong_nanshan_hero_v01.png` | PNG 2048×1152 RGB（16:9 三视图拼版，中性灰底） | ✅ 已就位 |

> ⚠️ **三视图拼版的实际风险**：一张图里含正/侧/背三个角度，`image_edit_longcat` 有可能把三个角度
> 一起画进新镜头。若出现这种情况，把**正面那一格单独裁出来**另存为 `liu_siqi_front_v01.png`
> （即"选做 view"的 `front`），改引用裁好的那张，母版三视图保留备查。
>
> ℹ️ 例外：**黄继光**的两张是**中景 + 近景单人构图**（非三视图），本风险不适用，见
> `CHARACTERS/05_huang_jiguang/README.md`。另：本项标注依据项目发起人的说明，
> 我方自动判据（三分栏自相似度）**未能证实**任何一张为三视图，故仅供参考。

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

四人同框（>2 人）R2V 放不下 → 先用 `image_edit_longcat` 逐人拼一张**合影参考图**
（存 `CHARACTERS/_group/`），再喂给 I2V。

> ⚠️ **ComfyUI 上传不覆盖同名文件**（实测 2026-09-12）：若 `input/` 里已存在同名文件，
> `comfyui_upload_image` 不会覆盖，而是存成 `名字 (1).png`、`名字 (2).png`…
> **后果**：你更新了本地图片（例如把 hero 从近景换成中景）后按原文件名引用，
> 实际拿到的还是**旧图**。
> **正确做法**：更换同名素材后，先删掉 `E:\code\ComfyUI\input\名字.png`（及 `名字 (n).png`），
> **再上传一次**，使文件名与本地一致。

## 4. 目录总览

```
ASSETS/
├── README.md                      # 本文件：命名与使用规范
├── CHARACTERS/
│   ├── 00_INDEX.md                # 7 人清单 · 镜号 · 固定 seed 台账
│   ├── 01_liu_siqi/               # 刘思齐
│   ├── 02_liu_sicheng/            # 刘思成
│   ├── 03_xu_changjing/           # 徐畅景
│   ├── 04_zhang_shuyang/          # 张书扬
│   ├── 05_huang_jiguang/          # 黄继光
│   ├── 06_yuan_longping/          # 袁隆平
│   ├── 07_zhong_nanshan/          # 钟南山
│   └── _extras/                   # 小战士 / 小女孩 / 妈妈 / 战士群演
├── SCENES/  (00_INDEX.md + 8 个场景)
├── PROPS/   (00_INDEX.md + 12 个道具)
└── STYLE/   (README.md)
```

每个资产目录内可选放一个 `README.md`：写清"哪一镜用到 + 当前使用版本 + 生成参数"。
模板见 `CHARACTERS/01_liu_siqi/README.md`。

## 5. 版本控制

`.gitignore` 已忽略 `ASSETS/**/` 下的 `png/jpg/jpeg/webp`（大图不入库），
但**保留所有 `.md` 与 `.gitkeep`** —— 即"**结构随仓库走，图片本地存**"。
换机器时把图片按同样的路径和文件名拷进来即可。

## 6. 待补素材

| 文件 | 被谁引用 | 状态 |
|------|----------|------|
| `ASSETS/配乐提示词规格.md` | `ace_step_t2audio` 工具说明（"Caption + Lyrics 双管齐下"法则） | 尚未创建 |
| `CHARACTERS/_group/four_students_hero_v01.png` | 四人同框镜头（9/10/22/53/79/113/118/135 等） | 尚未创建 |

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
