# MCP 工具套件 · 《如愿·看见》（stem_fest 制作）

把项目能力封装成 **2 个 MCP 服务器**，让 Cline 直接出图 / 出视频 / 配音 / 配乐 / 联网查资料，
不再需要为每个镜头手写一次性 Python 脚本。

| 服务器 | 名称 | 工具数 | 作用 | 依赖 |
|--------|------|:------:|------|------|
| `comfyui_mcp_server.py` | `comfyui-drama` | 15 | 驱动本机 ComfyUI 跑 12 条工作流 | ComfyUI 在线 + 模型就位 |
| `web_search_mcp_server.py` | `web-search` | 6 | 免 API Key 联网搜索/抓正文 | 仅需 `ddgs`（免密钥） |

```
mcp_server/
├── comfyui_mcp_server.py     # ① 短剧生产管线（图像/视频/语音/音乐）
├── selftest.py               #    离线自检（无需 ComfyUI）
├── comfyui_tools.md          #    ① 详解：工具清单、参数注入、实测耗时、已知约束
├── web_search_mcp_server.py  # ② 联网搜索（免密钥）
├── web_search_selftest.py    #    离线自检（无需联网）
└── README.md                 # 本文件（套件总览；② 的用法在本文件 §3）
```

---

## 1. 一键注册到 Cline

编辑 `cline_mcp_settings.json`
（Windows VS Code：`%APPDATA%\Code\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json`）：

```json
{
  "mcpServers": {
    "comfyui-drama": {
      "command": "py",
      "args": [
        "-3.10",
        "E:\\code\\stem_fest\\mcp_server\\comfyui_mcp_server.py"
      ],
      "env": {
        "COMFYUI_URL": "http://127.0.0.1:8188",
        "COMFYUI_ROOT": "E:\\code\\ComfyUI",
        "PYTHONIOENCODING": "utf-8"
      },
      "disabled": false,
      "autoApprove": [],
      "timeout": 1800
    },
    "web-search": {
      "command": "py",
      "args": [
        "-3.10",
        "E:\\code\\stem_fest\\mcp_server\\web_search_mcp_server.py"
      ],
      "env": {
        "WEB_SEARCH_DEFAULT_REGION": "cn-zh",
        "WEB_SEARCH_DEFAULT_BACKEND": "auto",
        "PYTHONIOENCODING": "utf-8"
      },
      "disabled": false,
      "autoApprove": [],
      "timeout": 120
    }
  }
}
```

- `timeout`：ComfyUI 建议 ≥ 1800（H3 视频单条 2-15 分钟）；搜索 120 足够。
- **`COMFYUI_ROOT` 必须填对**（本机 `E:\code\ComfyUI`）。它优先级高于自动探测，填错会让
  参考图回退写入错误目录；留空则自动探测（会按 `/internal/files/output` 反查真实根目录）。
- 保存后**重启 Cline**（或重载 MCP 面板）即可在对话中直接调用这些工具。

依赖（本机已验证可用）：

```powershell
pip install "mcp[cli]"        # MCP SDK，已验证 1.26.0
pip install ddgs              # 搜索服务器，已验证 9.16.0（免 API Key）
pip install beautifulsoup4 lxml   # 可选：fetch_page 的 HTML 回退路径
```

---

## 2. 运行前提与作用域（是否依赖 cwd / PATH）

结论：**不依赖当前工作目录；注册一次后每次启动 Cline 都可用**，但要满足几个运行前提。

### 2.1 不依赖 cwd（已实测）

两个服务器内部所有路径都由 `__file__` 推导，从不读取 `os.getcwd()`。
实测：`cd C:\Windows` 后启动，仍然得到

```
PROJECT_ROOT : E:\code\stem_fest
WORKFLOW_DIR : E:\code\stem_fest\workflows   (9 个工作流齐备)
OUTPUT_ROOT  : E:\code\stem_fest\OUTPUT
相对 output_dir → 落在项目内；相对参考图 ASSETS/... 正常上传
```

换句话说：**无论 Cline 在哪个目录、打开哪个文件夹，工具都可用**，
相对路径（`output_dir`、参考图路径）一律按**项目根**解析，而不是按 cwd。

### 2.2 配置是全局的，不在仓库里

`cline_mcp_settings.json` 位于
`%APPDATA%\Code\User\globalStorage\saoudrizwan.claude-dev\settings\`，
即**所有 VS Code 工作区共用**、且**不受 git 影响**（不随仓库提交/切换分支变化）。
仓库内没有工作区级 MCP 配置（已确认无 `.vscode/mcp.json`、无 `.cline/`）。

### 2.3 解释器绑定：为什么用 `py -3.10`

| 写法 | 可靠性 |
|------|--------|
| `"command": "python"` | 一般。依赖 PATH 顺序；若从"已激活 venv/conda 的终端"启动 VS Code，`python` 会变成那个环境 → `No module named mcp` |
| `"command": "py", "args": ["-3.10", ...]` ✅ **当前配置** | 高。`py.exe` 固定在 `C:\WINDOWS\py.exe`（系统 PATH），由 Python Launcher 按版本注册表解析 `-3.10`，不受 PATH 顺序与 venv 影响 |
| 绝对路径 `D:\Python310\python.exe` | 最高（完全不查 PATH），但 Python 升级/移动后需改配置 |

> 换机器或换了 Python 版本时，把 `-3.10` 改成对应版本（`py -0` 可列出本机所有版本）。

### 2.4 每次使用时的运行前提

| 前提 | 影响的服务器 | 检查方式 |
|------|--------------|----------|
| Python 环境含 `mcp`（及 `ddgs`） | 两者 | `py -3.10 -c "import mcp, ddgs; print('ok')"` |
| ComfyUI 在本机运行 | `comfyui-drama` | `comfyui_status` → `reachable: true` |
| 能访问外网 | `web-search` | `search_status(live_probe=true)` |
| 项目仍在 `E:\code\stem_fest` | `comfyui-drama` | 移动目录后需改 `args` 与 `COMFYUI_ROOT` |

`web-search` 不依赖本项目任何文件，可整段复制到别的项目直接复用。

### 2.5 会失效的场景（唯一需要重新注册的情况）

1. **移动/重命名项目目录** → 改 `args` 里的脚本路径（两处）。
2. **卸载或更换 Python**，或新版本没装 `mcp`/`ddgs` → 改 `-3.10` 并补装依赖。
3. **ComfyUI 未启动**（不是配置问题，是运行前提）→ 工具会返回带 `hint` 的明确错误。
4. **在其它机器上** → `cline_mcp_settings.json` 不随仓库走，需重新注册一次（配置可直接复制）。

---

## 3. 工具索引

### ① comfyui-drama — 生产管线（15 个）

| 工具 | 工作流 | 用途 |
|------|--------|------|
| `z_image_turbo_t2i` | `Z-Image-Turbo 文生图.json` | 文生图（场景 / 道具 / UI / 群像） |
| `image_edit_longcat` | `Image Edit (LongCat Image Edit).json` | 图像编辑 · **角色一致性**（定妆照 → 新场景）· **本项目唯一图生图工具** |
| `video_minimax_h3_i2v` | `video_minimax_h3_i2v.json` ⭐ | 图生视频（含环境音） |
| `video_minimax_h3_r2v` | `video_minimax_h3_r2v.json` ⭐ | 参考图生视频 · 角色锁定（≤2 张参考图） |
| `video_minimax_h3_t2v` | `video_minimax_h3_t2v.json` | 文生视频（UI 动画 / 无角色镜头） |
| `qwen3_tts` | `Qwen3-TTS 语音合成.json` | 角色配音 / 旁白 |
| `ace_step_t2audio` | `ACE-Step 1.5 文生音频.json` | 配乐 BGM / 合成音效 |
| 🆕 `stable_audio_3_sfx` | `Stable Audio 3 音效生成.json` | **音效 / foley / 环境底噪**（LCM 8 步，单次音效比 ACE 更合适） |
| 🆕 `sound_caption` | `Sound Caption (LAION Whisper).json` | **音效描述**（听到什么 / 音色 / 疑似来源；≤30 s，**无 ASR 能力**） |
| 🆕 `face_feature` | `Face Feature (InsightFace).json` | **人脸检测 + ArcFace 512 维特征**（目录/通配符批量，可与定妆照比对） |
| `qwen3_asr` | `Qwen3-ASR 语音识别.json` | 配音核对（mp4 音轨 → 文字）<br>★ **词级时间戳**节点已支持（`Qwen3-ForcedAligner-0.6B`），**工具未接线** → `comfyui_tools.md` §6.7 |
| `image_segmentation_sam3` | `Image Segmentation (SAM3).json` | **开放词汇检测 / 分割**（图片或视频抽帧 → 框图 + 掩膜 + 覆盖率，验收用） |
| `comfyui_status` | — | 服务 / 队列 / 显存 / 工作流文件检查 |
| `comfyui_upload_image` | — | 上传参考图到 ComfyUI `input` |
| `comfyui_get_result` | — | 按 `prompt_id` 取回异步结果 |

> 🆕 = **2026-09-16 新增**（音效生成 / 音效描述 / 人脸特征）。
> 后两者依赖自定义节点包 `E:\code\ComfyUI\custom_nodes\comfyui_media_audit`
> —— **新增自定义节点后必须重启一次 ComfyUI** 才会注册（重启会中断正在跑的队列任务）。
> 冒烟测试（直连 ComfyUI，不经 MCP 服务）：`py -3.10 OUTPUT/_smoke_new_tools.py`
> （可加 `--only=sfx|caption|face` 单跑一条）。

→ 详见 **[comfyui_tools.md](comfyui_tools.md)**

### ② web-search — 免密钥联网搜索（6 个）

| 工具 | 用途 |
|------|------|
| `web_search(query, max_results=8, region="cn-zh", timelimit="", safesearch="moderate", page=1, backend="")` | 通用网页搜索（`ddgs` 多引擎并发轮换 + 去重，失败自动按 `duckduckgo → brave → bing → google → mojeek → yahoo → startpage` 回退，返回里告知 `backend_used`） |
| `search_news` | 新闻搜索（额外带 `date` / `source`） |
| `search_images` | 图片搜索（返回原图/缩略图直链 + 尺寸）—— 为分镜找视觉参考，**注意版权** |
| `wiki_lookup(query, lang="zh", max_results=5, extract_chars=1200)` | 维基百科检索 + 首段摘要（MediaWiki `generator=search + prop=extracts`，需可靠来源时用它） |
| `fetch_page(url, max_chars=8000, offset=0, fmt="text_markdown")` | 抓网页正文；主路径 `ddgs.extract`，回退 `urllib+bs4`，再回退正则；用 `next_offset` 续读长文 |
| `search_status(live_probe=False)` | 返回 `ddgs` 版本 / 可用引擎 / 默认参数 / 可选依赖；**首次使用前先跑一次** |

**后端选型（为什么用 `ddgs`）**

| 方案 | 免密钥 | 实测结论 |
|------|:------:|----------|
| 直抓 `html./lite.duckduckgo.com` | ✅ | ❌ 约 15 次请求后返回"选鸭子"风控页，不可用 |
| 公共 SearXNG `?format=json` | ✅ | ❌ 多为 429 / 返回 HTML / TLS 失败 |
| DuckDuckGo Instant Answer API | ✅ | ✅ 可用但只有词条摘要，不是通用搜索 |
| **`ddgs` 库（本方案）** | ✅ | ✅ **多引擎并发轮换 + cookie/指纹处理**，单引擎失效自动降级 |
| Tavily / Brave / Serper | ❌ 需 key | 免费额度小，留给有 key 者自选 |

**环境变量**：`WEB_SEARCH_DEFAULT_REGION`（默认 `cn-zh`）、`WEB_SEARCH_DEFAULT_BACKEND`（默认 `auto`）、`WEB_SEARCH_MAX_RESULTS`（默认 `8`）。

**已知限制**：依赖第三方引擎页面结构（改版可能短暂失效，已内置回退）；有缓存延迟；高频调用可能被限流；
`fetch_page` 仅用于读取公开页面；`web_search` 只给摘要（约 200 字），要全文请配 `fetch_page`。

---

## 4. 自检

```powershell
python mcp_server/selftest.py              # ComfyUI 套件（离线，不需要 ComfyUI 在线）
python mcp_server/web_search_selftest.py   # 搜索套件（离线，不需要联网）
```

两个自检都拦截真实网络/ComfyUI 调用，只校验 **工具注册 + 参数注入 + 结果整形 + 错误路径**，
CI 或改代码后可随时跑。当前状态：**全部通过**。

---

## 5. 实测验证速览（2026-09-11，ComfyUI 0.33.0 / RTX 4090 Laptop 16GB）

7 条工作流全部真实跑通并落盘（产物在 `OUTPUT/mcp_smoke/`）；
搜索侧 `web_search`（中/英）、`search_news`、`search_images`、`wiki_lookup`、
`fetch_page`（单页 62,998 字符，offset 续读正常）均返回真实结果。
逐工具的实测规格、耗时与踩坑见 **[comfyui_tools.md](comfyui_tools.md) §4**。

> 🚫 **原第 8 条 FireRed Image Edit 1.1 —— 工具已删除（2026-09-13）**。2026-09-12 加入时只验证了
> 参数注入与节点执行；**产物 5/5 全部纯黑（mean=0.0）** 却返回 `ok:true` ⇒ 零成功率，已整体移除。
> 教训：**"ComfyUI 报 success" ≠ "产物可用"**，验收必须查像素或体积。

> 🆕 **2026-09-15 新增 `image_segmentation_sam3`（SAM3 开放词汇检测 / 分割）**：图片**或视频抽帧** →
> 框图 / 掩膜叠加 / 原始掩膜三件套，并回传每帧 **`mask_coverage`**（`0` = 这帧没检出目标）。
> **离线自检 + ffmpeg 抽帧 / 覆盖率口径已真机实测通过**；真实 ComfyUI 端到端**因全片批量占用队列未跑**
> （按 §6.1 #8 的纪律不插任务）。用法、调参口诀与验收口径见
> **[comfyui_tools.md §6.6](comfyui_tools.md)**。

> 🧭 **2026-09-15 · Agent 侧能力与边界（动手前先读）**：基模**自带视觉**但额度 ≈7 张/会话、**不可复现**、
> 读不准低对比度小字与任何数值 ⇒ 验收一律落**数值**；`qwen3_asr` 的**词级时间戳节点已支持但工具未接线**
> （**不需要** WhisperX）；**两套 Python 环境别混**（MCP = `py -3.10`，ComfyUI = 它自己的环境）。
> 📖 全表 → 项目 **[README.md §4.5 Agent 能力地图](../README.md)**；`qwen3_asr` 接线细则 → **[comfyui_tools.md §6.7](comfyui_tools.md)**。

---

## 6. 常见问题

| 现象 | 原因 / 解决 |
|------|-------------|
| `comfyui_status` 返回 `reachable:false` | ComfyUI 没启动；`python main.py --listen 127.0.0.1 --port 8188` |
| 生成工具报 `ok:false` 但带 `prompt_id` | 等待超时（任务仍在跑）；用 `comfyui_get_result(prompt_id=...)` 取回 |
| 参考图无效 / 脸不一致 | 走 `image_edit_longcat` 并传定妆照；确认 `COMFYUI_ROOT` 正确 |
| 文生图慢到 ~100 s/step | 多为**首个任务的模型冷加载**（16 GB 模型权重流式加载）。2026-09-12 已从 `launch_comfyui.bat` 去掉 `--lowvram --disable-pinned-memory`，启动日志应为 `NORMAL_VRAM` + 已启用 pinned memory；若仍慢，先确认是否冷加载、以及 ComfyUI 是否需先释放模型缓存 |
| 搜索报"所有搜索引擎均未返回结果" | 触发风控或网络受限；换个 query/`backend`，或稍后重试 |
| 搜索提示缺 `ddgs` | `pip install ddgs` |

---

## 7. 设计原则（改代码前先读）
1. **工具返回统一 JSON 字符串**：`{"ok": bool, ...}`；失败必带 `error` 字段，绝不抛裸异常给模型。
2. **参数注入按 `class_type` 匹配节点**，与 `workflows/*.json` 的节点结构解耦，工作流微调不致失效。
3. **可复现**：`seed=-1` 表示随机，但一定把**实际使用的 seed** 回传，便于复刻与前后的镜头对齐。
4. **长任务可异步**：`wait=False` 先拿 `prompt_id`，避免 MCP 调用超时；配套取回工具。
5. **不引入必需的新依赖**（除 `ddgs`）；搜索侧对 `ddgs` 缺失、引擎失效均有降级与明确提示。
