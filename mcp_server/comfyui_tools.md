# comfyui-drama MCP 服务器 · 短剧生产管线

把 `workflows/` 下的 8 条 ComfyUI 工作流封装成 MCP 工具，让 Cline 直接驱动出图 / 出视频 /
配音 / 配乐，而无需手写一次性 Python 脚本。

- 服务器文件：`mcp_server/comfyui_mcp_server.py`
- MCP 名称：`comfyui-drama`
- 离线自检：`python mcp_server/selftest.py`
- 注册配置见套件总览 **[README.md](README.md)**

---

## 1. 工具清单

| 工具 | 工作流 | 用途 |
|------|--------|------|
| `z_image_turbo_t2i` | `Z-Image-Turbo 文生图.json` | 文生图（场景 / 道具 / UI / 群像） |
| `image_edit_longcat` | `Image Edit (LongCat Image Edit).json` | 图像编辑 · **角色一致性**（定妆照 → 新场景）· 首选 |
| `image_edit_firered` | `image_firered_image_edit1_1.json` | 图像编辑 · **角色一致性** · 与 LongCat **互为备选**（Qwen-Image-Edit 血统；`lightning=True` → 8 步/CFG 1，默认 40 步/CFG 4） |
| `video_minimax_h3_i2v` | `video_minimax_h3_i2v.json` ⭐ | 图生视频（含环境音），视频生成首选 |
| `video_minimax_h3_r2v` | `video_minimax_h3_r2v.json` ⭐ | 参考图生视频 · 角色锁定（≤2 张参考图） |
| `video_minimax_h3_t2v` | `video_minimax_h3_t2v.json` | 文生视频（UI 动画 / 无角色镜头） |
| `qwen3_tts` | `Qwen3-TTS 语音合成.json` | 角色配音 / 旁白（FLAC/MP3） |
| `ace_step_t2audio` | `ACE-Step 1.5 文生音频.json` | 配乐 BGM / 合成音效（MP3） |
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

离线运行，校验 11 个工具是否注册、以及每条工作流的参数是否注入到正确节点
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

> ℹ️ 第 8 条 **FireRed Image Edit 1.1** 于 **2026-09-12** 加入：`selftest.py` 的 `[3b]` 用例覆盖其参数注入，
> 并已真实跑通（ComfyUI `/history` 可见 `TextEncodeQwenImageEditPlus` + `qwen_image_vae` 的成功执行）。

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
> （`image_edit_firered` 本项目**弃用**：曾有 3/3 纯黑图静默失败，且已定案只用 LongCat。）

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
| 🔒 **图生图只用 `image_edit_longcat`** | **不做 A/B 比较**；换背景/改色调/转老照片同样走它的图生图，不用文生图抽卡。`image_edit_firered` **已弃用**（3/3 纯黑图静默失败） | 美术方 2026-09-13 定案 |
| 参考图需先注册到 ComfyUI input | 工具已自动走 `/upload/image`；中文/空格文件名会自动改 ASCII | — |
| 输出路径以 `ffprobe` 实测为准 | 不要相信注释里的分辨率 | `LESSONS_LEARNED.md` #10 |

---

## 7. 参数注入对照（维护者参考）

| 工作流 | 注入点 |
|--------|--------|
| Z-Image-Turbo T2I | `CLIPTextEncode.text`（负面词拼接为 `Do NOT include:`）· `EmptySD3LatentImage.width/height/batch_size` · `KSampler.seed/steps/cfg` · `PreviewImage→SaveImage.filename_prefix` |
| LongCat Image Edit | `LoadImage.image` · `TextEncodeQwenImageEdit.prompt`（node id 升序：正/负）· `ImageScaleToTotalPixels.megapixels` · `FluxGuidance.guidance` · `KSampler.seed/steps/cfg` |
| FireRed Image Edit 1.1 | `LoadImage.image` · `TextEncodeQwenImageEditPlus.prompt`（两个：正/负）· `ResizeImageMaskNode["resize_type.megapixels"]` · `KSampler.seed` · steps/cfg 经 `Switch` 选路落到 `PrimitiveInt` / `PrimitiveFloat`（`PrimitiveBoolean` = lightning：True→8 步/CFG 1，False→40 步/CFG 4）· `SaveImage.filename_prefix` |
| Qwen3-TTS | `Qwen3CustomVoice.text/language/speaker/seed/instruct/max_new_tokens`（`custom_speaker_name=""`）· `SaveAudioAdvanced.filename_prefix/format` |
| ACE-Step 1.5 | `TextEncodeAceStepAudio1.5.tags/lyrics/seed/bpm/keyscale/language/timesignature/cfg_scale/temperature/top_p` · `PrimitiveFloat.value`（时长）· `KSampler.seed/steps/cfg` · `SaveAudioAdvanced.filename_prefix/format` |
| H3 I2V | `LoadImage.image` · `MiniMaxH3ImageToVideo.prompt` · `PrimitiveFloat.value` · `RandomNoise.noise_seed` · `ResolutionSelector.aspect_ratio/megapixels` · `BasicScheduler.steps` · `SaveVideo.filename_prefix` |
| H3 R2V | `PrimitiveStringMultiline.value`（prompt）· `LoadImage.image` ×2 · 其余同 I2V |
| H3 T2V | `MiniMaxH3ImageToVideo.prompt` · 其余同 I2V |
