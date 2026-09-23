# comfyui-drama MCP 服务器 · 短剧生产管线

把 `workflows/` 下的 14 条 ComfyUI 工作流封装成 MCP 工具，让 Cline 直接驱动出图 / 出视频 /
配音 / 配乐 / **音效** / **视频配音效** / **音频理解** / **检测分割** / **人脸测量**，
而无需手写一次性 Python 脚本。

> 🚫 **2026-09-13 变更：`image_edit_firered` 工具已整体移除**（连带 `WORKFLOWS["firered"]` 注册项与
> `selftest.py` 的 `[3b]` 用例）。该模型在本机 **5 次运行 5 张纯黑图（mean=0.0）、零成功率**，
> 而 ComfyUI 每次都报 `success` —— 静默失败不可验收。**本项目图生图唯一工具：`image_edit_longcat`**，
> 不做 A/B 比较。工作流文件 `workflows/image_firered_image_edit1_1.json` 仅作留档，无任何工具指向它。

- 服务器文件：`mcp_server/comfyui_mcp_server.py`
- MCP 名称：`comfyui-drama`
- 离线自检：`python mcp_server/selftest.py`
- 注册配置见套件总览 **[README.md](README.md)**

---

## 1. 工具清单

| 工具 | 工作流 | 用途 |
|------|--------|------|
| `z_image_turbo_t2i` | `Z-Image-Turbo 文生图.json` | 文生图（场景 / 道具 / UI / 群像） |
| `image_edit_longcat` | `Image Edit (LongCat Image Edit).json` | 图像编辑 · **角色一致性**（定妆照 → 新场景）· **本项目唯一图生图工具** |
| `video_minimax_h3_i2v` | `video_minimax_h3_i2v.json` ⭐ | 图生视频（含环境音），视频生成首选 |
| `video_minimax_h3_r2v` | `video_minimax_h3_r2v.json` ⭐ | 参考图生视频 · 角色锁定（≤2 张参考图） |
| `video_minimax_h3_t2v` | `video_minimax_h3_t2v.json` | 文生视频（UI 动画 / 无角色镜头） |
| `qwen3_tts` | `Qwen3-TTS 语音合成.json` | 角色配音 / 旁白（FLAC/MP3） |
| `ace_step_t2audio` | `ACE-Step 1.5 文生音频.json` | 配乐 BGM / 合成音效（MP3） |
| `stable_audio_3_sfx` | `Stable Audio 3 音效生成.json` | **文生音效 / foley / 氛围底噪**（1–60 s，LCM 8 步 / CFG 1）★ **音效层首选** |
| `woosh_sfx` | `Woosh 音效生成.json` | **文生音效**（Sony Woosh 音效基础模型 · DFlow 蒸馏 4 步 / CFG 3.5）★ 音效层备选 |
| `woosh_v2a` | `Woosh 视频配音效.json` | **视频 → 音效**（按画面配 foley，≤8 s）★ 本机**唯一**能给已拍画面配色效的工具 |
| `qwen3_asr` | `Qwen3-ASR 语音识别.json` | 配音核对（mp4 音轨 → 文字）<br>★ **词级时间戳**：节点原生支持（`Qwen3-ForcedAligner-0.6B`），但**工具尚未接线** → §6.7 |
| `sound_caption` | `Sound Caption (LAION Whisper).json` | **音效验收**：音频（含 mp4 音轨）→ 英文声音描述（"听到了什么/什么音色/像什么来源"）<br>⚠️ **无 ASR 能力**，台词转写请用 `qwen3_asr`；单次输入上限 30 s |
| `image_segmentation_sam3` | `Image Segmentation (SAM3).json` | **开放词汇检测 / 分割**：文字 → 框图 + 掩膜 + 覆盖率；**图片或视频抽帧**（验收用） |
| `face_feature` | `Face Feature (InsightFace).json` | **人脸检测 + ArcFace 512 维特征**（一次可跑目录 / 通配符 / 多路径整批）<br>⚠️ 绝对余弦相似度不可当判据，只看**相对排名 + 明显差距**（项目 `README.md` §6.5） |
| `comfyui_status` | — | 服务 / 队列 / 显存 / 工作流文件检查 |
| `comfyui_upload_image` | — | 上传参考图到 ComfyUI `input` |
| `comfyui_get_result` | — | 按 `prompt_id` 取回异步结果 |

所有生成类工具都返回统一 JSON：

```json
{
  "ok": true,
  "status": "success",
  "prompt_id": "…",
  "tool": "z_image_turbo_t2i",
  "seed": 42,
  "elapsed_sec": 31.2,
  "output_dir": "E:\\…\\OUTPUT\\t2i",
  "files": [{"path": "E:\\…\\OUTPUT\\t2i\\t2i_20260911_193000_00001_.png", "size_kb": 1823.4}]
}
```

共性参数：`seed=-1` 表示随机并回传实际 seed；`wait=False` 只提交、返回 `prompt_id`，
之后用 `comfyui_get_result` 取回；`output_dir` 默认落在 `OUTPUT/<层>/`。

---

## 2. 前置条件与依赖

| 项 | 要求 |
|----|------|
| MCP SDK | `pip install "mcp[cli]"`（本机验证 1.26.0） |
| ComfyUI | 需在本机运行（默认 `http://127.0.0.1:8188`），且工作流所需模型已就位 |
| 配置 | `COMFYUI_URL`、`COMFYUI_ROOT`（默认 `E:\code\ComfyUI`）；见 [README.md](README.md) |

排查第一步永远先跑 `comfyui_status` 确认 `reachable: true`。

---

## 3. 自检

```powershell
python mcp_server/selftest.py
```

离线运行，校验 **17 个工具（14 条工作流 + 3 个辅助）** 是否注册、以及每条工作流的参数是否注入到正确节点
（拦截 `_queue` 检查提交的 workflow，不依赖 ComfyUI 服务）。

---

## 4. 实测验证（2026-09-11 · ComfyUI 0.33.0 / RTX 4090 Laptop 16GB）

2026-09-11 的 7 条工作流已全部真实跑通并落盘（产物在 `OUTPUT/mcp_smoke/`，可打开验收）：

| 工具 | 产物 | 实测规格 | 耗时 |
|------|------|----------|------|
| `z_image_turbo_t2i` | `t2i/t2i_00001_.png` | 768×768 RGB（与请求尺寸一致） | 首次约 14 min（含冷加载 16GB 模型） |
| `image_edit_longcat` | `image_edit/edit_00001_.png` | 1360×768 RGB（定妆照为竖构图，按 1MP 等比缩放） | 42 s |
| `qwen3_tts` | `tts/tts_00001.flac` | FLAC 24 kHz 单声道 4.0 s | 秒级 |
| `ace_step_t2audio` | `bgm/bgm_00001.mp3` | MP3 48 kHz 立体声 **15.0 s**（与 `duration` 完全一致） | 585 s |
| `video_minimax_h3_i2v` | `video/h3_i2v_00001_.mp4` | h264 864×480@24fps + **AAC 32kHz 立体声** | 142 s（4 步 / 3 s 片长） |
| `video_minimax_h3_r2v` | `video/h3_r2v_00001_.mp4` | h264 864×480@24fps + AAC 32kHz 立体声 | ≈2.5 min |
| `video_minimax_h3_t2v` | `video/h3_t2v_00001_.mp4` | h264 864×480@24fps + AAC 32kHz 立体声 | 202 s |

> 🚫 **原第 8 条 FireRed Image Edit 1.1 —— 已移除（2026-09-13）**。它于 2026-09-12 加入时"跑通"
> 只验证了**参数注入与节点执行**（`TextEncodeQwenImageEditPlus` + `qwen_image_vae`），
> 但**产物像素从未合格**：累计 5 次运行（40 步/CFG 4、8 步/CFG 1 Lightning、880×1176、
> 后续 2 次局部编辑）**全部为纯黑图 `mean=0.0`**，工具却一律返回 `ok:true`。
> ⇒ 结论：**"ComfyUI 报 success" ≠ "产物可用"**，验收必须查像素或体积。工具已删除。

结论：
- ✅ 参数注入端到端生效（尺寸 / 时长 / megapixels / seed 与产物实测值吻合）
- ✅ 参考图自动上传到 `E:\code\ComfyUI\input` 并被 `LoadImage` 正确引用
- ✅ H3 音画联合生成有效（mp4 内确有 AAC 音轨）
- ✅ 超时路径优雅降级：生成未完成时返回 `ok:false` + `prompt_id` 提示改用 `comfyui_get_result`

> ⚠️ **性能提示**：慢的根源是**首个任务的冷加载**（Z-Image 16GB 模型冷加载 + 每步权重流式加载
> 会让文生图慢到 ~100 s/step）；热缓存后 / 中小模型（LongCat、H3）恢复至 ~17-21 s/step。
> ✅ **2026-09-12 已修正启动参数**：`E:\code\ComfyUI\launch_comfyui.bat` 去掉了
> `--lowvram --disable-pinned-memory`（原文件备份为 `launch_comfyui.bat.bak`），
> 启动日志应显示 `Set vram state to: NORMAL_VRAM` 与 `Enabled pinned memory`。
> 若要 1080p 成片，仍应按 LESSONS #10 走"低分辨率生成 + 超分"路线。

---

## 5. 典型用法（Cline 对话示例）

**① 定妆照 → 角色一致的分镜图**

> 用 `image_edit_longcat`，参考图 `ASSETS/CHARACTERS/01_liu_siqi/liu_siqi_hero_v01.png`，
> prompt："同一位初中女生坐在傍晚 6 点的教室课桌前，暖金色天光，中景" + `ASSETS/STYLE/README.md` 的风格后缀，
> seed 固定 1101，输出到 `OUTPUT/03_classroom_day/frames`（目录名沿用场景目录；2026-09-21 前为 `04_classroom_dusk`）。
> 🔒 **铁律（2026-09-13，美术方定案）：图生图一律用 `image_edit_longcat`，只用这一个工具、不做 A/B 比较。**
> **换背景 / 改色调 / 转老照片也走它的图生图**，不要退回去用文生图重新抽卡。
> （🚫 `image_edit_firered` 工具**已于 2026-09-13 从工具列表删除**：5/5 纯黑图、零成功率。）

**② 分镜图 → 视频（I2V）**

> 用 `video_minimax_h3_i2v`，首帧用上一步的图，prompt 写清 SHOT + 镜头运动 + **Audio**（环境音与台词），
> duration = 该镜时长；`megapixels 0.6`（迭代轮可用 `0.3` + `steps 4` 提速）。

**③ 配音 + 配乐（备用路径）**

> ⚠️ 本项目成片**不需要逐镜跑 TTS**：台词写在 ② 的 H3 prompt 里，音画一步联合生成。
> 仅在后期需单独补录某句台词时才用 `qwen3_tts`（同角色固定 `speaker` + `seed`）。
> 跨段落 BGM 用现成音源；`ace_step_t2audio` 仅用于补充过渡配乐
> （如 tags="solo piano, contemplative, minor key"、lyrics=""、duration=60）。

---

## 6. 已知约束（踩坑记录）

| 约束 | 说明 | 出处 |
|------|------|------|
| H3 `megapixels ≤ 0.6` | 16GB VRAM 下 0.92(720p) 必 OOM；要 1080p 请生成后超分 | `LESSONS_LEARNED.md` #10 |
| TTS `custom_speaker_name` 必须为空 | 该字段是音色 mixing 列表，填自定义名 → `ValueError` | README §13.7 |
| 同角色固定 `speaker` + `seed` | 跨集音色一致性的唯一手段 | README §13.11 |
| 角色镜头必须引用定妆照 | 否则每张脸随机变化，白做定妆 | `LESSONS_LEARNED.md` #6 |
| 🔒 **图生图只用 `image_edit_longcat`** | **不做 A/B 比较**；换背景/改色调/转老照片同样走它的图生图，不用文生图抽卡。🚫 `image_edit_firered` 工具**已于 2026-09-13 从工具列表删除**（5/5 纯黑图、零成功率） | 美术方 2026-09-13 定案 |
| 参考图需先注册到 ComfyUI input | 工具已自动走 `/upload/image`；中文/空格文件名会自动改 ASCII | — |
| 输出路径以 `ffprobe` 实测为准 | 不要相信注释里的分辨率 | `LESSONS_LEARNED.md` #10 |
| SAM3 文本类别写法 | 逗号分隔可写多类别，`:N` 指定该类最多检出几个（`"paper plane:2, boy"`）；CLIP 上限 **32 token**，括号会被剥掉（不做权重），用最直白的英文名词 | `E:\code\ComfyUI\comfy\text_encoders\sam3_clip.py::_parse_prompts` |
| SAM3 `individual_masks=True` 不给原始掩膜 | 0 检出时掩膜批次为空，`MaskToImage → SaveImage` 会在 `images[0]` 上抛 IndexError ⇒ 工具主动跳过该分支（框图 / 叠加图仍给） | `E:\code\ComfyUI\nodes.py::SaveImage` · 自检 `[4c]` |
| SAM3 视频抽帧依赖系统 ffmpeg | 抽帧用 `ffmpeg`（时长用 `ffprobe`，失败回退解析 stderr）；缺 ffmpeg 时**只能传图片** | 与 `OUTPUT/_visual_review.py` 同口径 |
| ★ **`mask_coverage = 0` 就是"没检出"** | 不要只看 ComfyUI 报 `success`（同 FireRed 教训）；覆盖率由 ffmpeg 解灰度裸流数非零像素得到，**不引 PIL/numpy** | 项目 `README.md` §6.1 #6 |
| SAM3 权重 / 节点 | `models/checkpoints/sam3.1_multiplex_fp16.safetensors`（1.6 GB，本机已就位）+ ComfyUI 内置节点 `SAM3_Detect` / `MaskToImage` / `DrawBBoxes` | `E:\code\ComfyUI\comfy_extras\nodes_sam3.py` |
| ★ **`filename_prefix` 里的斜杠不会建目录** | 工具把产物**平铺**下载进 `output_dir`（`_save_outputs()` 用 `out_dir / filename`，**丢弃** ComfyUI 的 `subfolder`）。想要子目录请**显式给 `output_dir`**，不要写 `filename_prefix="sfx/film/xxx"` | `mcp_server/comfyui_mcp_server.py::_save_outputs` · 2026-09-20 `_make_film_sfx.py` 踩到 |
| 音效任务会与渲染**抢单队列** | ComfyUI 是单队列 FIFO：批量音效要在镜头批量之间排队（单条 15–45 s）。**一次只提交一条**最礼貌 | 2026-09-20 `_make_film_sfx.py` |

---

## 6.5 ★ `ace_step_t2audio` 环境声 / 群杂（L2 / L3）照抄配方

> 用途见项目 `README.md` §4.4（音频三层分工）：**H3 只做 L1 台词**，
> L2 环境声与 L3 群杂人声一律用本工具，**不要交给 H3**（H3 只会产出糊状人声 / ≈ −50 dB 的静默）。

**实测指标（2026-09-13，`OUTPUT/bgm/`，脚本 `OUTPUT/_diag_audio_report.py`）**

| 文件 | 时长 | 整体 RMS | peak | 段 RMS 变异 | 平均 ZCR | 判断 |
|---|:--:|---|---|---|---|---|
| `crowd_test_classroom_00001.mp3`（L3 群杂） | 20.0s | 0.0389 | 0.855 | 4.97 | 0.0399 | 宽频噪音状 ✅ |
| `sfx_classroom_night_00001.mp3` | 25.0s | 0.0455 | 0.479 | 3.46 | 0.0302 | 宽频噪音状 ✅ |
| `sfx_rice_field_cicada_00001.mp3` | 25.0s | 0.1076 | 0.805 | 1.82 | 0.0403 | 宽频噪音状 ✅ |
| `sfx_trench_wind_00001.mp3` | 25.0s | 0.0270 | 0.751 | 8.50 | 0.0348 | 宽频噪音状 ✅ |
| `sfx_train_dining_00001.mp3` | 25.0s | 0.0036 | 0.058 | 5.33 | 0.0241 | ⚠️ RMS 偏低，音量需后期抬 |

> 判定口径：**ZCR 高 = 宽频噪音**（风声/群杂/蝉鸣等真实环境声该有的样子）；
> **ZCR 极低 = 单一音调**（可能被生成成音乐而非氛围）。
> **段 RMS 变异大 = 有自然呼吸起伏**；极小 = 像持续嗡鸣/循环旋钮。

**L3 群杂配方（照抄）**

```
tags     = ambient soundscape, classroom background walla, many indistinct young voices
           murmuring at once, no music, no melody, no singing, no instruments,
           unreadable chatter, room tone, soft and distant, documentary field recording,
           lo-fi, 60 BPM
lyrics   = 用 [Ambience - ...] 段落标记写"结构"，并反复强调
           no music, no melody, no singing, no intelligible words
duration = 要铺多长就出多长（20s 成本约 30s 机时）
```

> ⚠️ 环境声（L2）同理，把 `tags` 换成对应声源描述即可；
> **`lyrics` 里务必写死 `no music, no melody, no singing`**，否则 ACE-Step 会倾向产出旋律。

---

## 6.6 ★ `image_segmentation_sam3` 用法与约束（2026-09-15 加入）

**一句话**：给一张图（或一段视频）＋一个**文字类别**，回答"画面里到底有没有这东西、它占多大"。
图像生成模型"报 success"和"画面里真有纸飞机"是两件事 —— 这个工具就是补上**画面证据**那一环。

```python
# ① 单图：某帧里到底有没有纸飞机
image_segmentation_sam3(
    image="OUTPUT/01_paper_plane/frames/03_girl_throwing_paper_plane_00001_.png",
    prompt="paper plane", threshold=0.4)

# ② 视频：整镜抽 4 帧逐帧体检（避开首尾 8% 防转场黑帧；跑批后再用！
image_segmentation_sam3(
    image="OUTPUT/01_paper_plane/video/03_girl_throwing_paper_plane_00001_.mp4",
    prompt="paper plane:2, girl, sky", video_frames=4, threshold=0.4)

# ③ 多类别 + 每类最多检出几个（`:N`）
image_segmentation_sam3(image="...", prompt="rice plant:3, hand, hat")
```

**产物：每帧三件套（都是正式输出，不是临时预览）**

| 后缀 | 内容 | 用途 |
|---|---|---|
| `_bbox` | 原图 + 检测框（`DrawBBoxes`） | **看懂图**：框住了什么、漏了什么 |
| `_overlay` | 原图 + 掩膜叠加（`ImageAndMaskPreview` 的 composite） | 看分割轮廓贴不贴边 |
| `_mask` | 黑底白掩膜 PNG | 抠图原料；`mask_coverage` 体检也读它 |

**返回的关键数值**

| 字段 | 含义 |
|---|---|
| `frames[].mask_coverage` | 掩膜占全画面比例（0-1）。**`0` = 这帧没检出目标**；`None` = 无 ffmpeg 无法体检 |
| `frames[].detected` | `mask_coverage > 0`（`None` = 体检不可用） |
| `frames[].time_sec` | 该帧取自第几秒（视频模式；单图模式为 `null`） |
| `summary.detected_frames` / `max_mask_coverage` / `mean_mask_coverage` | 全片速览：几帧命中、最大与平均占比 |

**调参口诀**

| 症状 | 处理 |
|---|---|
| 漏检 | `threshold` 降到 0.3-0.4；`prompt` 换成更直白的英文名词（`paper plane` 好过 `origami aircraft`） |
| 误检 | `threshold` 升到 0.6-0.7 |
| 掩膜毛糙 / 缺角 | `refine_iterations` 2 → 3 |
| 只想知道"有没有" | `refine_iterations=0`（最快，只用粗掩膜） |
| 目标太多 | 用 `:N` 限制每类检出数，或 `individual_masks=True` 逐目标出掩膜 |

> ⚠️ **跑批期间别用它测长视频**：每次提交都会让 ComfyUI 换模型（SAM3 1.6 GB），
> 会打断正在跑的 H3 队列（见项目 `README.md` §6.1 #8 的纪律）。跑批中只用**单图**。

**验证状态（2026-09-15）**

| 项 | 结果 |
|---|---|
| 离线自检 `py -3.10 mcp_server/selftest.py` `[4c]` / `[4d]` | ✅ 通过（工具注册；参数注入 `SAM3_Detect`；注入的 `SaveImage(_bbox/_overlay)` + `MaskToImage → SaveImage(_mask)` 挂点正确；`individual_masks=True` 正确跳过掩膜分支；视频模式逐帧结构 / 帧号前缀 / summary） |
| 三个 ffmpeg 辅助函数（抽帧 · 时长 · 覆盖率） | ✅ 真机实测：3.042 s 视频抽 3 帧 → 0.243 / 1.521 / 2.799 s；覆盖率口径 全黑 `0.0`、上半白 `0.5` |
| **真实 ComfyUI 端到端（出图 + 覆盖率）** | ⏳ **未跑** —— 2026-09-15 全片批量正在占用队列，按 §6.1 #8 不插任务。**批量结束后补跑一次**：<br>`image_segmentation_sam3(image="ASSETS/PROPS/01_paper_plane/paper_plane_hero_v01.png", prompt="paper plane")`<br>验收口径：`mask_coverage > 0` 且 `_bbox` 图上的框套住纸飞机 |
| ⚠️ 首次实跑留意：**注入节点用的是非数字 node id** | `mcp_save_overlay` / `mcp_mask_to_image` / `mcp_save_mask` —— ComfyUI API 接受任意唯一字符串 id（本工作流本身就带 `99:75` 这类子图 id），但这一条**只有真跑一次才算数**：若 `/prompt` 报 `invalid node id`，把这三个 key 改成 `9001/9002/9003` 即可（注入点在 `_sam3_apply`） |

## 6.7 ★ `qwen3_asr`：台词核对（已接线）+ **词级时间戳（节点已支持 · 工具未接线）**

**已接线**：`mp4 / flac / wav` 直接喂（内部 ffmpeg 抽 16 kHz 单声道）→ 转写文本 ⇒ **"台词念对没有"逐字核对已完全够用**
（配合 `storyboard.md` 台词原文；`context` 可塞剧名/人名帮助识别）。

**未接线**（2026-09-15 核实 `E:\code\ComfyUI\custom_nodes\ComfyUI-Qwen3-ASR`，**能力存在、只是没接**）

| # | 断点 | 位置 | 接法 |
|:-:|---|---|---|
| ① | `forced_aligner` 写死 `None` | `workflows/Qwen3-ASR 语音识别.json` 的 `Qwen3ASRLoader`；MCP 工具也没暴露该参数 | 选 `Qwen/Qwen3-ForcedAligner-0.6B`（`nodes.py:116/159-167` 会自动下载并对齐器单独 `dtype/device_map`） |
| ② | 时间戳**没接出工作流** | 节点 `nodes.py:192-223` 返回 **3 槽**：`text` / `language` / `timestamps`；而我们的 `SaveText` 只接 `["2", 0]` | 加第二个 `SaveText ← ["2", 2]`，`filename_prefix = {prefix}_ts`（**必须换前缀**，否则两个 SaveText 同名互撞） |
| ③ | 返回里没有时间轴 | `qwen3_asr` 的结果整形只抓 `files[].text` | 把 `timestamps` 提到顶层；再加派生指标：**首句起播秒 / 末句结束秒 vs 片长**（判"被片尾截断""前摇多长""语速"） |

**对齐器模型**（本机**尚未下载**，HF 缓存里只有 `Qwen3-ASR-0.6B/1.7B`）：

```powershell
# 预下（不占显存、跑批期间也能做）
hf download Qwen/Qwen3-ForcedAligner-0.6B --local-dir E:\code\ComfyUI\models\Qwen3-ASR\Qwen3-ForcedAligner-0.6B
# 或让节点首启自动下载（source 可选 ModelScope）
```

**注意事项**

- 输出格式：`起始秒-结束秒: 文本`（逐行）——可直接与 `storyboard.md` 的分句、`_diag_shot_duration_audit.py` 的语速表交叉核对。
- 模型档位：工作流固定 `Qwen/Qwen3-ASR-0.6B`；**`1.7B` 也已在本地**（中文台词质量更好），需要时加 `repo_id` 参数切换。
- ⚠️ **别在跑批期间跑**：要加载 1.8 GB（ASR 0.6B）+ 1.2 GB（对齐器），可能把 H3 权重逐出 ⇒ 单镜重载代价远超本次检查收益（§6.1 #8 纪律）。
- 📖 **Agent 侧的能力地图与"哪些缺口是真的"** → 项目 `README.md` **§4.5**。

---

## 6.8 ★ `stable_audio_3_sfx`：点状音效 / foley（2026-09-20 实测接线）

> 与 `ace_step_t2audio` 的**分工**：**长氛围 L2 / 群杂 L3 仍按 `README.md` §4.4 用 ACE-Step**；
> 本工具管**点状音效 / foley**（一声纸飞机掠过、一次翻书、一记铁锹落地）与**短氛围片段**，
> 它不需要歌词、不吃 BPM、1–60 s 直接给定，配方比 ACE-Step 干净。

**本机模型就位情况**（ComfyUI 侧，2026-09-20 核实）

| 文件 | 位置 | 用途 |
|---|---|---|
| `stable_audio_3_medium.safetensors`（8.6 GB） | `models/checkpoints/` | MODEL + VAE（`CheckpointLoaderSimple`） |
| `t5gemma_b_b_ul2.safetensors`（1.1 GB） | `models/text_encoders/` | 文本编码器，`CLIPLoader.type = "stable_audio"` |

**清单式的 API 工作流**（`workflows/Stable Audio 3 音效生成.json`，8 节点 / 已跑通）：

```
CheckpointLoaderSimple ─┬─ MODEL ─→ KSampler(lcm / 8 步 / CFG 1 / simple)
CLIPLoader(stable_audio)─→ CLIPTextEncode(正) ─┘
                          CLIPTextEncode(负) ─┘
EmptyLatentAudio(seconds) ─→ latent ─┘
CheckpointLoaderSimple.VAE ─→ VAEDecodeAudio ─→ SaveAudioMP3(quality=V0)
```

**实测（2026-09-20，RTX 4090 Laptop 16GB）**

| 项 | 值 |
|---|---|
| prompt | `short punchy sound effect of a paper airplane whooshing past close to the microphone, clean studio recording, no music` |
| 参数 | `duration=3` · `seed=4242` · `steps=8` · `cfg=1.0` · `lcm/simple` |
| 产物 | `OUTPUT/sfx/_mcp_probe_paperplane_00001.mp3`（86.1 KB，MP3 48 kHz） |
| 耗时 | **12.1 s**（含冷加载）⇒ 约 **4 s 机时 / 1 s 音频** |

**照抄配方（英文，讲究「声源 + 动作 + 材质/空间 + 质感」）**

```
short punchy sound effect of <声源> <动作> <材质/空间>, clean studio recording, no music
```

| 目标 | prompt |
|---|---|
| 纸飞机掠过 | `short punchy sound effect of a paper airplane whooshing past close to the microphone, clean studio recording, no music` |
| 铁锹入土 | `single shovel thrust into wet soil, dull thud with grit, close perspective, outdoor field recording, no music` |
| 翻书页 | `single page of a textbook being turned, crisp paper friction, quiet classroom, close-up, no music` |
| 稻浪夜虫 | `night rice field ambience, wind through wet leaves, distant crickets, low level, natural field recording` |

> ⚠️ 负向词在工作流里走**独立 `CLIPTextEncode`**（`negative_prompt` 参数），但实际采样用
> `cfg=1.0` ⇒ **负向条件被完全置零**（LCM 配方），想"排掉音乐"要写进**正向**的 `no music`。
> 与 `z_image_turbo_t2i` 把负面词拼进正向是同一个道理。

**验收（★ 必做，别只看 ComfyUI 报 success）**：拿产物跑 `sound_caption`

| 探针产物 | `sound_caption` 回读（节选） | 判定 |
|---|---|---|
| `_mcp_probe_paperplane_00001.mp3` | "a single, sharp, and loud sound … percussive … distinct metallic quality" | ✅ 确为**单次点状音效**（不是音乐、不是持续噪音） |

> 📖 `sound_caption` 的判读口径：它**只描述声音本身**（"the audio features …" 是模型训练风格，不是错误），
> **没有 ASR 能力** —— 台词核对一律用 `qwen3_asr`。

### ⛔ 铁律：审计类节点的 JSON 必须经 `PreviewAny` 才能回传

**踩坑（2026-09-20 发现并修复）**：`LAIONAudioCaption` / `InsightFaceFeature` 两个自定义节点
把结果按 `(text, {"ui": {"text": [text]}})` 返回 —— **ComfyUI 0.33 的
`execution.py::get_output_from_returns()` 只认 `{"ui": …, "result": …}` 这种 dict 形式**，
元组里的 `ui` 会被**静默丢弃**：`history.outputs` 为空 ⇒ 工具返回
`status: "no_output_files"` 且**没有任何正文**，而 ComfyUI 依然报 `success`
（★ 与 FireRed「报 success 但产物是黑图」同一类陷阱）。

**修法（已落地，无需重启 ComfyUI）**：在两条工作流里各挂一个 ComfyUI 内置节点
`PreviewAny`（`comfy_extras/nodes_preview_any.py`，它用的正是 `{"ui": …, "result": …}` 的正确写法）：

```
"Sound Caption (LAION Whisper).json":  "3": PreviewAny.source ← ["2", 0]
"Face Feature (InsightFace).json":     "2": PreviewAny.source ← ["1", 0]
```

`history.outputs` 随即出现 `text_inline`，MCP 侧 `_collect_outputs()` 命中
`nd["text"]` → `_hoist_inline_text()` 解析成 `caption_json` / `face_json`。

> ✅ **回归验证（2026-09-20）**：`sound_caption` → `status: success` + `caption_json` 有正文（12.1 s）；
> `face_feature`（定妆照 `liu_siqi_hero_v01.png`）→ `status: success` + `face_json`（2 张脸、含 512 维特征，15.1 s）。
> ⚠️ 改工作流 JSON **不需要重启 MCP / ComfyUI**（`_load_workflow()` 每次调用都读盘）。

### 音效模型盘点（2026-09-20 复查 · `E:\code\ComfyUI\models`）

| 模型 | 权重 | 节点 | 结论 |
|---|---|:--:|---|
| **Stable Audio 3 Medium** | ✅ 已就位 | ✅ 内置 | **✅ 可用（`stable_audio_3_sfx`）** |
| **ACE-Step 1.5** | ✅ 已就位 | ✅ 内置 | **✅ 可用（`ace_step_t2audio`，L2/L3）** |
| **Sony Woosh**（音效基础模型 · T2A + **V2A**） | ✅ 已就位（5 个文件夹 8.3 GB 权重） | ✅ 已加载 | **✅ 可用（`woosh_sfx` / `woosh_v2a`）** |
| HunyuanVideo Foley | ✅ `models/hunyuanvideo_foley/`（9.8 GB + VAE） | ❌ 无 | 🚫 **不可用**：全机 76 个节点类里没有任何 Foley 节点，也无对应自定义节点包 |

> 📌 分工：**`stable_audio_3_sfx` 仍是音效首选**（1–60 s 任意时长、12 s 出片）；
> `woosh_sfx` 是专用音效基础模型的备选（语义更"物件化"）；
> **`woosh_v2a` 是唯一能给已拍画面配 foley 的工具**（≤8 s）；
> `ace_step_t2audio` 继续承担长氛围 L2 与群杂 L3（见 §6.5）。

---

## 6.9 ★ Sony Woosh 接线（2026-09-20 实测落地）

**为什么值得接**：Woosh 是 Sony 的**音效专用**基础模型（arXiv 2502.07359），本机同一套权重
既能 T2A（文生音效）也能 **V2A（视频→音效）** —— 后者是本机**唯一**"看着画面配音效"的能力。

### 落地清单（照此复现，全部已验证）

| 步骤 | 内容 | 备注 |
|---|---|---|
| ① 装依赖 | `hydra-core` `torchdiffeq` `timm` `hear21passt==0.0.26`（装进 `E:\code\ComfyUI\venv`） | `pip install --dry-run` 先确认**不动 torch/torchvision**；实测只装了这 4 个 |
| ② 下权重 | HF `drbaph/Woosh` → `models/woosh/`（脚本 `OUTPUT/_fetch_woosh.py`） | 4 个主干 + 已有 4 个组件，**合计 8 个文件夹** |
| ③ 重启 ComfyUI | 自定义节点只在启动时 import | 生产渲染期间用 `OUTPUT/_restart_comfyui_when_idle.ps1` 等空闲再重启 |
| ④ 工作流 | `Woosh 音效生成.json`（T2A）· `Woosh 视频配音效.json`（V2A） | API Format，放进 `workflows/` |
| ⑤ MCP | `woosh_sfx` / `woosh_v2a` | 见 §1 与 §7 |

### ⛔ 铁律 1：Woosh 的模型文件夹必须**直接**放在 `models/woosh/` 下

`folder_paths` 只注册了 `models/woosh` 这一个根（`ComfyUI-Woosh/__init__.py`），而
`nodes/model_paths.py::resolve_woosh_path()` 只在**根下第一层**找名字：

```
models/woosh/Woosh-DFlow/{config.yaml,weights.safetensors}   ✅ 能认
models/woosh/checkpoints/Woosh-DFlow/…                       ❌ 认不到
```

更要命的是它**不报错**：`Woosh-DFlow/config.yaml` 里写的是 `path: checkpoints/TextConditionerA`，
节点会用 `resolve_woosh_path("TextConditionerA")` 把它改写成**绝对路径**；若组件被放在
`checkpoints/` 这一层，改写出来的路径指向不存在的 `models/woosh/TextConditionerA` ⇒
脚本一跑就"找不到模型"。（本机 2026-09-20 发现：组件原先就在错误的 `checkpoints/` 层，
已全部上移一层。）

### ⛔ 铁律 2：`WooshSample` 的 **audio 在输出槽 1**，槽 0 是 `video_frames`

T2A 模式下槽 0 会返回一张 **1×1 像素占位图**（`torch.zeros(1,1,1,3)`）——
把它接到 `SaveImage` 只会得到一张废图。**只接槽 1**：

```
"SaveAudioMP3".audio ← ["2", 1]     # T2A 工作流，节点 2 = WooshSample
```

### 参数配方（官方建议值，工具已内置为默认）

| 任务 | checkpoint | `model_type` | steps | cfg | latent_frames |
|---|---|---|:--:|:--:|---|
| 文生音效（快） | `Woosh-DFlow` | `DFlow` | **4** | **3.5** | 100 ≈ 1 s @48 kHz |
| 文生音效（质量） | `Woosh-Flow` | `Flow` | 50 | 4.5 | 同上 |
| 视频配音效（快） | `Woosh-DVFlow-8s` | `DVFlow` | **4** | **3.5** | 800 ≈ 8 s（V2A 上限） |
| 视频配音效（质量） | `Woosh-VFlow-8s` | `VFlow` | 50 | 4.5 | 同上 |

> ⚠️ **`model_name` 与 `model_type` 必须配对**，否则节点直接抛
> `ValueError: Selected model_type 'X' does not match checkpoint 'Y'`（工具已按 model 参数自动配对）。
> ⚠️ 蒸馏版（DFlow/DVFlow）内部把步数**夹到 ≤8**，填 50 也只会跑 8 步。
> ⚠️ `subprocess=True`（**工具默认**）：in-process 时 ComfyUI 改过的全局 PyTorch 状态
> （attention backend / FP16 累加）可能让 Woosh 产出**语义不符**的声音；子进程慢约 15 s 但可靠。

### 📊 V2A 行为实测：**它跟画面走，文字只是弱提示**（2026-09-20 三点探针）

| 输入镜头 | 文字 prompt | `sound_caption` 回读 | 判读 |
|---|---|---|---|
| 镜 35 `35_sicheng_nods_we_won`（人物喊话） | `wind over soil and distant footsteps on gravel` | "a single, loud, and sharp **vocal burst** … shout or yell" | ⚠️ 出了**人声**，与文字不符 |
| 镜 21 `_mid_21_zhang_crouches_looks_at_wild_veg`（人物张口） | `wind over dry soil, faint distant artillery rumble, cloth rustling, **no voices**` | "The audio contains **speech**. The speaker is a male with a medium pitch…" | ⚠️ 仍出人声（写了 `no voices` 也没用） |
| 镜 4 `04_paper_plane_over_campus`（空镜，无人） | `paper airplane whooshing … light wind, birdsong, no voices` | 音轨已产出（`OUTPUT/sfx/_probe_woosh_v2a_noface_00001.mp3`），回读排在当日渲染之后 | — |

**结论（前两点一致）**：V2A 用 Synchformer 提的**视觉特征**会把"有人在说话/喊"这块压过文字提示
⇒ 有发声动作的镜头，它**就是要生成语音**。

| 用途 | 怎么做 |
|---|---|
| 想配**环境声 / 风声 / 脚步** | **挑画面里没有明显发声动作的镜头**；文字照常给（它仍有微调作用） |
| 想要**喊话 / 人声类 foley** | 它对路，直接用 |
| 无论哪种 | **必须回读验收**：判"是不是人声"用 `qwen3_asr`（专测语音）或 `sound_caption`（测音色）—— `status: success` 什么都说明不了 |

> ⚠️ `WooshLoadFlow.model_name` 下拉里还会出现 `Woosh-AE` / `Woosh-CLAP`（上游把
> `TextConditionerA/V` 之外的东西都列出来了）。**别选这两个**：它们是组件不是生成权重，
> 选了会在加载时被 `_infer_model_type_from_config()` 拒掉。工具的 `model` 参数已锁定 4 个主干。

### 下载踩坑：**不要用 `HF_ENDPOINT=https://hf-mirror.com`**

本机 `HTTP(S)_PROXY=http://127.0.0.1:7897` 已直通 huggingface.co（实测 200）。
改用镜像会**必然失败**：hub 0.36 会校验 HEAD 响应头，镜像不返回该头 ⇒
`FileMetadataError: Distant resource does not seem to be on huggingface.co`
→ 被包成 `LocalEntryNotFoundError`（看上去像"断网"，其实是头校验没过）。
`OUTPUT/_fetch_woosh.py` 因此**默认不设** `HF_ENDPOINT`。

### 踩坑：`.ps1` 里写中文 = 语法炸（PowerShell 5.1）

Windows PowerShell 5.1 **没有 BOM 就按 ANSI 解析 `.ps1`**。第一版看门狗脚本带中文注释/日志，
被解析成一堆碎 token：`Log` 的字符串引号被吃掉、**kill 段被跳过**，结果
"没杀掉旧进程却又启动了一个新 ComfyUI -> 同端口起两个实例"（当场已清理）。
⇒ **给 PS 的脚本文件一律纯 ASCII**；写完先跑一次语法校验：

```powershell
$errs = $null
$null = [System.Management.Automation.Language.Parser]::ParseFile($p, [ref]$null, [ref]$errs)
if ($errs) { $errs | ForEach-Object Message } else { 'PARSE OK' }
```

---

## 7. 参数注入对照（维护者参考）

| 工作流 | 注入点 |
|--------|--------|
| Z-Image-Turbo T2I | `CLIPTextEncode.text`（负面词拼接为 `Do NOT include:`）· `EmptySD3LatentImage.width/height/batch_size` · `KSampler.seed/steps/cfg` · `PreviewImage→SaveImage.filename_prefix` |
| LongCat Image Edit | `LoadImage.image` · `TextEncodeQwenImageEdit.prompt`（node id 升序：正/负）· `ImageScaleToTotalPixels.megapixels` · `FluxGuidance.guidance` · `KSampler.seed/steps/cfg` |
| ~~FireRed Image Edit 1.1~~ | 🚫 **工具已移除（2026-09-13）**，注入点记录不再维护（历史：`ResizeImageMaskNode["resize_type.megapixels"]` · steps/cfg 经 `Switch` 落到 `PrimitiveInt` / `PrimitiveFloat`） |
| Qwen3-TTS | `Qwen3CustomVoice.text/language/speaker/seed/instruct/max_new_tokens`（`custom_speaker_name=""`）· `SaveAudioAdvanced.filename_prefix/format` |
| ACE-Step 1.5 | `TextEncodeAceStepAudio1.5.tags/lyrics/seed/bpm/keyscale/language/timesignature/cfg_scale/temperature/top_p` · `PrimitiveFloat.value`（时长）· `KSampler.seed/steps/cfg` · `SaveAudioAdvanced.filename_prefix/format` |
| H3 I2V | `LoadImage.image` · `MiniMaxH3ImageToVideo.prompt` · `PrimitiveFloat.value` · `RandomNoise.noise_seed` · `ResolutionSelector.aspect_ratio/megapixels` · `BasicScheduler.steps` · `SaveVideo.filename_prefix` |
| H3 R2V | `PrimitiveStringMultiline.value`（prompt）· `LoadImage.image` ×2 · 其余同 I2V |
| H3 T2V | `MiniMaxH3ImageToVideo.prompt` · 其余同 I2V |
| SAM3 检测 / 分割 | `LoadImage.image`（图片或抽出的帧）· `CLIPTextEncode.text`（类别）· `SAM3_Detect.threshold/refine_iterations/individual_masks` · `CheckpointLoaderSimple.ckpt_name`（可选）<br>**外加 3 个注入节点**：`PreviewImage→SaveImage(_bbox)` · `SaveImage(_overlay)` ← `ImageAndMaskPreview` 的 composite · `MaskToImage→SaveImage(_mask)` ← `SAM3_Detect` 的 masks |
| Qwen3-ASR | `Qwen3ASRLoader.repo_id/precision/forced_aligner/local_model_path`（⚠️ `forced_aligner` 目前**写死 `"None"`**，工具未暴露）· `Qwen3ASRTranscribe.language/context/return_timestamps` · `SaveText.text ← ["2", 0]`<br>⚠️ **`timestamps` 在输出槽 `2`，尚未接出**（接法见 §6.7） |
| Stable Audio 3 音效 | `CLIPTextEncode.text`（节点号升序：正/负）· `EmptyLatentAudio.seconds/batch_size` · `KSampler.seed/steps/cfg/sampler_name/scheduler/denoise` · `SaveAudioMP3.filename_prefix/quality` |
| Sound Caption | `LoadAudio.audio`（先经 `/upload/image` 注册）· `LAIONAudioCaption.model_dir/processor_dir/max_new_tokens/num_beams` · **`PreviewAny.source ← ["2", 0]`**（见 §6.8 铁律） |
| Face Feature | `InsightFaceFeature.paths/model_name/provider/det_size/min_det_score/include_embedding/reembed_px/max_images`（节点在本机执行，**项目相对路径直接读盘**，不走上传）· **`PreviewAny.source ← ["1", 0]`** |
| Woosh 文生音效（T2A） | `WooshLoadFlow.model_name/model_type`（按 `model` 参数配对，见表）· `WooshSample.prompt/steps/cfg/seed/latent_frames/subprocess/force_offload` · `SaveAudioMP3.filename_prefix/quality` ← **`["2", 1]`（audio，不是槽 0）** |
| Woosh 视频配音效（V2A） | `WooshLoadVideo.video_path/max_duration_s` · `WooshLoadFlow.model_name/model_type` · `WooshSample.prompt/steps/cfg/seed/latent_frames/subprocess/force_offload`（**`video ← ["1", 0]` 是关键：接上即自动切 V2A**）· `SaveAudioMP3` ← `["3", 1]` |
