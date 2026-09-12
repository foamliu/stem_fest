# web-search MCP 服务器 · 免 API Key 联网搜索

给 Cline 装上"查资料"的能力：找文档、核实事实、追行业动态、找视觉参考、读网页正文。
**全部免密钥**，不需要注册任何账号。

- 服务器文件：`mcp_server/web_search_mcp_server.py`
- MCP 名称：`web-search`
- 离线自检：`python mcp_server/web_search_selftest.py`

---

## 1. 后端选型：为什么用 ddgs

| 方案 | 免密钥 | 实测结论 |
|------|:------:|----------|
| 直接抓 `html.duckduckgo.com` / `lite.duckduckgo.com` | ✅ | ❌ **约 15 次请求后返回"选鸭子"风控页**，不可用于工具 |
| 公共 SearXNG 实例 `?format=json` | ✅ | ❌ 实测多为 `429`／返回 HTML／TLS 失败，公共实例基本不开放 JSON |
| DuckDuckGo Instant Answer API | ✅ | ✅ 可用但只有词条摘要，不是通用搜索 |
| MediaWiki API（维基百科） | ✅ | ✅ 稳定可靠，但只覆盖百科内容 |
| **`ddgs` 库（本方案）** | ✅ | ✅ **多引擎并发轮换 + cookie/指纹处理**，单引擎失效自动降级 |
| Tavily / Brave / Serper | ❌ 需 key | 免费额度小，留给有 key 的用户自选 |

`ddgs` 内置引擎：`duckduckgo`、`brave`、`bing`、`google`、`mojeek`、`yahoo`、`startpage`、`wikipedia`。
默认 `backend="auto"` 会并发查询多个引擎并去重合并；若失败，服务器会按
`duckduckgo → brave → bing → google → mojeek → yahoo → startpage` 逐个回退，
并在返回里告知 `backend_used`（哪个引擎真正出了结果）。

---

## 2. 工具详解

### `web_search(query, max_results=8, region="cn-zh", timelimit="", safesearch="moderate", page=1, backend="")`

```
查询："短剧 AI 视频生成" → backend_used="auto"，返回 3 条真实中文结果
      （剧大虾 / VIVA Short AI / Pixmax …）
```

| 参数 | 说明 |
|------|------|
| `max_results` | 1-30，默认 8 |
| `region` | `cn-zh`（默认）/ `us-en` / `jp-jp`… |
| `timelimit` | `d` 一天 / `w` 一周 / `m` 一月 / `y` 一年；留空不限（非法值自动忽略） |
| `safesearch` | `on` / `moderate` / `off` |
| `backend` | 指定引擎；留空 `auto` |
| `page` | 结果页号 |

返回：`{ok, query, backend_used, count, results:[{rank,title,url,snippet}]}`
（`title`/`snippet` 已去 HTML 标签、反转义实体、压缩空白）

### `search_news(query, max_results=8, region="cn-zh", timelimit="w", backend="")`

带 `date` 与 `source` 字段，适合追踪时效信息。示例返回
`OpenAI changes stance, calls for national AI safety rules`（The Baltimore Sun，2026-08-21）。

### `search_images(query, max_results=8, region="cn-zh", safesearch="moderate", backend="")`

返回 `{image（原图直链）, thumbnail, page_url, width, height, source}`。
本项目的用法：为分镜找视觉参考（如 "1980s lab CRT monitor reference photo"）——
注意版权，仅作参考，正式素材仍走 ComfyUI 生成。

### `wiki_lookup(query, lang="zh", max_results=5, extract_chars=1200)`

走 MediaWiki `generator=search + prop=extracts|info`，一次请求同时拿到条目、链接与首段摘要。
适合术语/人物/事件背景这类需要可靠来源的内容。已验证中文摘要正常返回。

### `fetch_page(url, max_chars=8000, offset=0, fmt="text_markdown")`

先 `web_search` 拿 URL，再 `fetch_page` 读正文：

- 主路径 `ddgs.extract`（返回 markdown），失败回退 `urllib + bs4`，再回退正则
- 长文按 `max_chars` 截断，返回 `total_chars / truncated / next_offset`
- 用 `offset=next_offset` 续读，可读完任意长文

实测 `https://docs.python.org/3/library/asyncio-task.html` → `total_chars = 62998`，
`method = ddgs.extract(text_markdown)`。

### `search_status(live_probe=False)`

返回 `ddgs` 版本、可用引擎列表、默认参数、可选依赖（bs4/lxml）是否就绪；
`live_probe=True` 会真发一次搜索验证链路。**首次使用前建议先跑一次。**

---

## 3. 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `WEB_SEARCH_DEFAULT_REGION` | `cn-zh` | 默认区域 |
| `WEB_SEARCH_DEFAULT_BACKEND` | `auto` | 默认引擎策略 |
| `WEB_SEARCH_MAX_RESULTS` | `8` | 默认返回条数 |

---

## 4. 典型用法（Cline 对话示例）

> **查资料**：用 `web_search` 搜 "MCP 协议 官方文档"，region=cn-zh，取前 3 条。
>
> **读全文**：把上一步第 1 条的 URL 用 `fetch_page` 读出来，`max_chars=6000`，
> 没读完就用返回的 `next_offset` 续读。
>
> **追动态**：用 `search_news` 搜 "AI 视频生成"，`timelimit=w`，看近一周发生了什么。
>
> **找参考图**：用 `search_images` 搜 "neon rain alley cinematic reference"，为下一场戏定色调。
>
> **核对设定**：不确定某个技术名词写进剧本是否准确 → `wiki_lookup` 拿权威定义。

---

## 5. 已知限制

| 限制 | 说明 |
|------|------|
| 依赖第三方引擎页面结构 | 引擎改版可能短暂失效；已内置多引擎回退，仍失败会返回明确 `error` 而不是空结果 |
| 不是"实时"接口 | 结果来自公开搜索引擎，有各自缓存延迟，不适合要求秒级时效的场景 |
| 搜索结果可能被风控 | 高频调用可能触发限流；`backend` 换一个或稍后重试 |
| 需遵守目标站点条款 | `fetch_page` 仅用于读取公开页面；请勿用于抓取受保护内容 |
| 不返回正文全文 | `web_search` 只给摘要（约 200 字），需要全文请配 `fetch_page` |
