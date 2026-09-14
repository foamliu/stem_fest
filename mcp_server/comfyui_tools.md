# comfyui-drama MCP 服务器 · 短剧生产管线

把 `workflows/` 下的 9 条 ComfyUI 工作流封装成 MCP 工具，让 Cline 直接驱动出图 / 出视频 /
配音 / 配乐 / **检测分割**，而无需手写一次性 Python 脚本。

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
| `qwen3_asr` | `Qwen3-ASR 语音识别.json` | 配音核对（mp4 音轨 → 文字） |
| `image_segmentation_sam3` | `Image Segmentation (SAM3).json` | **开放词汇检测 / 分割**：文字 → 框图 + 掩膜 + 覆盖率；**图片或视频抽帧**（验收用） |
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

离线运行，校验 12 个工具是否注册、以及每条工作流的参数是否注入到正确节点
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
> seed 固定 1101，输出到 `OUTPUT/04_classroom_dusk/frames`。
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
