#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Free Web Search MCP Server — 免 API Key 的联网搜索工具集

为 Cline 提供"查资料"能力，全部走**免密钥**通道：

  web_search     通用网页搜索（ddgs 多引擎轮换：duckduckgo/brave/bing/google/mojeek/startpage/yahoo）
  search_news    新闻搜索（带日期与来源）
  search_images  图片搜索（返回原图/缩略图直链）
  wiki_lookup    维基百科检索 + 摘要（MediaWiki API，免密钥）
  fetch_page     抓取网页正文（ddgs.extract → markdown/纯文本，带分页截断）
  search_status  自检：依赖版本、可用引擎、默认参数、实时探测

启动（stdio，由 Cline 拉起）::

    python mcp_server/web_search_mcp_server.py

依赖::

    pip install ddgs        # 多引擎搜索 + 网页正文提取（本机已验证 9.16.0）
    pip install beautifulsoup4 lxml   # 仅在 fetch_page 回退路径需要（可选）

环境变量（均可选）::

    WEB_SEARCH_DEFAULT_REGION   默认 cn-zh
    WEB_SEARCH_DEFAULT_BACKEND  默认 auto
    WEB_SEARCH_MAX_RESULTS      默认 8

设计取舍：
  * 不直接抓 DuckDuckGo HTML —— 实测约 15 次请求后会被"选鸭子"风控拦截；
    改由 ddgs 统一处理 cookie/指纹并跨引擎轮换，单引擎失效自动降级。
  * `backend="auto"` 由 ddgs 并发查询多个引擎并去重合并。
"""

from __future__ import annotations

import html as _html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

# ── 配置 ──────────────────────────────────────────────────────────
DEFAULT_REGION = os.environ.get("WEB_SEARCH_DEFAULT_REGION", "cn-zh")
DEFAULT_BACKEND = os.environ.get("WEB_SEARCH_DEFAULT_BACKEND", "auto")
DEFAULT_MAX_RESULTS = int(os.environ.get("WEB_SEARCH_MAX_RESULTS") or 8)

# 单引擎回退顺序（auto 失败时逐个试）
FALLBACK_BACKENDS = ["duckduckgo", "brave", "bing", "google", "mojeek", "yahoo", "startpage"]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

mcp = FastMCP("web-search", log_level="WARNING")


# ── 通用小工具 ────────────────────────────────────────────────────
def _dump(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def _err(msg: str) -> str:
    return _dump({"ok": False, "error": str(msg)})


def _clean(text: Any) -> str:
    """去 HTML 标签、反转义实体、压缩空白。"""
    if not text:
        return ""
    s = str(text)
    if "<" in s and ">" in s:
        s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = _html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def _norm_timelimit(value: Optional[str]) -> Optional[str]:
    """ddgs 只接受 None / d / w / m / y。"""
    if not value:
        return None
    v = str(value).strip().lower()
    return v if v in {"d", "w", "m", "y"} else None


def _load_ddgs():
    try:
        from ddgs import DDGS  # noqa: PLC0415
        return DDGS
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "缺少依赖 ddgs。请先安装：pip install ddgs"
            f"（原始错误：{exc}）"
        ) from exc

# ── 搜索内核（带引擎回退）────────────────────────────────────────
def _search(category: str, query: str, *, backend: str, **kwargs: Any) -> tuple[list[dict], str]:
    """调用 ddgs 的某个 category；失败或空结果时按引擎顺序回退。

    返回 (原始结果列表, 实际生效的 backend 描述)。
    """
    DDGS = _load_ddgs()

    def attempt(engine: str) -> list:
        with DDGS() as d:
            return list(getattr(d, category)(query, backend=engine, **kwargs))

    plan = [backend] if backend and backend != "auto" else []
    plan += ["auto"] + FALLBACK_BACKENDS
    seen: set[str] = set()
    last_error = ""
    for engine in plan:
        if engine in seen:
            continue
        seen.add(engine)
        try:
            rows = attempt(engine)
        except Exception as exc:  # noqa: BLE001
            last_error = f"{engine}: {type(exc).__name__}: {str(exc)[:160]}"
            continue
        if rows:
            return rows, engine
        last_error = last_error or f"{engine}: 返回 0 条结果"
        time.sleep(0.3)
    raise RuntimeError(
        f"所有搜索引擎均未返回结果（最后错误：{last_error}）。"
        "可能是网络受限、触发风控或查询词过于特殊，可稍后重试或更换 backend。"
    )


def _text_rows(rows: list[dict], max_results: int) -> list[dict]:
    out = []
    for i, r in enumerate(rows[:max_results], 1):
        out.append({
            "rank": i,
            "title": _clean(r.get("title")),
            "url": r.get("href") or r.get("url") or "",
            "snippet": _clean(r.get("body")),
        })
    return out


def _news_rows(rows: list[dict], max_results: int) -> list[dict]:
    out = []
    for i, r in enumerate(rows[:max_results], 1):
        out.append({
            "rank": i,
            "title": _clean(r.get("title")),
            "url": r.get("url") or r.get("href") or "",
            "snippet": _clean(r.get("body")),
            "date": _clean(r.get("date")),
            "source": _clean(r.get("source")),
        })
    return out


def _image_rows(rows: list[dict], max_results: int) -> list[dict]:
    out = []
    for i, r in enumerate(rows[:max_results], 1):
        out.append({
            "rank": i,
            "title": _clean(r.get("title")),
            "image": r.get("image", ""),
            "thumbnail": r.get("thumbnail", ""),
            "page_url": r.get("url", ""),
            "width": r.get("width", ""),
            "height": r.get("height", ""),
            "source": _clean(r.get("source")),
        })
    return out

# ══════════════════════════════════════════════════════════════════
# 🔎 搜索工具
# ══════════════════════════════════════════════════════════════════
@mcp.tool()
def web_search(
    query: str,
    max_results: int = 8,
    region: str = "",
    timelimit: str = "",
    safesearch: str = "moderate",
    page: int = 1,
    backend: str = "",
) -> str:
    """通用网页搜索（免 API Key，多引擎自动轮换）。

    适合查资料、找文档、核实事实、找素材出处。若已知目标站点，
    可在 query 里用 `site:example.com 关键词` 限定。

    Args:
        query: 搜索词。中英文均可（中文建议 region="cn-zh"）。
        max_results: 返回条数，默认 8（1-30）。
        region: 区域，如 "cn-zh"（中文）、"us-en"（英文）、"jp-jp"。
            留空用默认值（当前为 cn-zh）。
        timelimit: 时间范围："d" 一天 / "w" 一周 / "m" 一月 / "y" 一年；
            留空不限。
        safesearch: "on" / "moderate" / "off"。
        page: 结果页号，从 1 开始。
        backend: 指定引擎（duckduckgo/brave/bing/google/mojeek/yahoo/startpage）；
            留空为 auto（多引擎并发去重）。指定引擎失败会自动回退。

    Returns:
        JSON 字符串：{ok, query, backend_used, count, results:[{rank,title,url,snippet}]}
    """
    try:
        n = max(1, min(int(max_results), 30))
        rows, used = _search(
            "text", query,
            backend=backend or DEFAULT_BACKEND,
            region=region or DEFAULT_REGION,
            safesearch=safesearch,
            timelimit=_norm_timelimit(timelimit),
            max_results=n,
            page=max(1, int(page)),
        )
        return _dump({
            "ok": True,
            "query": query,
            "backend_used": used,
            "count": len(rows[:n]),
            "results": _text_rows(rows, n),
        })
    except Exception as e:
        return _err(f"web_search 失败: {e}")


@mcp.tool()
def search_news(
    query: str,
    max_results: int = 8,
    region: str = "",
    timelimit: str = "w",
    backend: str = "",
) -> str:
    """新闻搜索（免 API Key），返回标题/链接/摘要/日期/来源。

    适合追踪行业动态、政策变化、产品发布等时效性信息。

    Args:
        query: 新闻关键词。
        max_results: 返回条数，默认 8（1-30）。
        region: 区域，留空用默认值（cn-zh）。
        timelimit: "d" / "w" / "m" / "y"；默认 "w"（近一周），留空不限。
        backend: 指定引擎，留空为 auto。

    Returns:
        JSON 字符串：{ok, query, backend_used, count, results:[{rank,title,url,snippet,date,source}]}
    """
    try:
        n = max(1, min(int(max_results), 30))
        rows, used = _search(
            "news", query,
            backend=backend or DEFAULT_BACKEND,
            region=region or DEFAULT_REGION,
            timelimit=_norm_timelimit(timelimit),
            max_results=n,
        )
        return _dump({
            "ok": True,
            "query": query,
            "backend_used": used,
            "count": len(rows[:n]),
            "results": _news_rows(rows, n),
        })
    except Exception as e:
        return _err(f"search_news 失败: {e}")


@mcp.tool()
def search_images(
    query: str,
    max_results: int = 8,
    region: str = "",
    safesearch: str = "moderate",
    backend: str = "",
) -> str:
    """图片搜索（免 API Key），返回原图与缩略图直链。

    适合为分镜找视觉参考、找角色/道具参考图（注意版权，仅作参考用途）。

    Args:
        query: 图片描述词，如 "1980s lab CRT monitor reference photo"。
        max_results: 返回条数，默认 8（1-30）。
        region: 区域，留空用默认值（cn-zh）。
        safesearch: "on" / "moderate" / "off"。
        backend: 指定引擎，留空为 auto。

    Returns:
        JSON 字符串：{ok, query, backend_used, count,
                     results:[{rank,title,image,thumbnail,page_url,width,height,source}]}
    """
    try:
        n = max(1, min(int(max_results), 30))
        rows, used = _search(
            "images", query,
            backend=backend or DEFAULT_BACKEND,
            region=region or DEFAULT_REGION,
            safesearch=safesearch,
            max_results=n,
        )
        return _dump({
            "ok": True,
            "query": query,
            "backend_used": used,
            "count": len(rows[:n]),
            "results": _image_rows(rows, n),
        })
    except Exception as e:
        return _err(f"search_images 失败: {e}")

# ── 网页抓取 ──────────────────────────────────────────────────────
def _http_get(url: str, timeout: int = 30) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(), resp.headers.get("Content-Type", "")


def _html_to_text(raw_html: str) -> str:
    """回退用：把 HTML 粗提取为纯文本（优先 bs4，其次正则）。"""
    try:
        from bs4 import BeautifulSoup  # noqa: PLC0415
        soup = BeautifulSoup(raw_html, "lxml")
        for tag in soup(["script", "style", "noscript", "svg", "header", "footer", "nav"]):
            tag.decompose()
        return re.sub(r"\n{3,}", "\n\n", soup.get_text("\n")).strip()
    except Exception:  # noqa: BLE001
        txt = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", raw_html)
        txt = re.sub(r"(?s)<[^>]+>", " ", txt)
        return re.sub(r"\s+", " ", _html.unescape(txt)).strip()


def _fetch_content(url: str, fmt: str) -> tuple[str, str]:
    """返回 (正文文本, 使用的抓取方式)。优先 ddgs.extract。"""
    try:
        DDGS = _load_ddgs()
        with DDGS() as d:
            result = d.extract(url, fmt=fmt)
        content = result.get("content", "")
        if isinstance(content, bytes):
            content = content.decode("utf-8", "replace")
        if content and content.strip():
            return content, f"ddgs.extract({fmt})"
    except Exception:  # noqa: BLE001
        pass

    raw, ctype = _http_get(url)
    text = raw.decode("utf-8", "replace")
    if "html" in ctype.lower() or "<html" in text[:2000].lower():
        return _html_to_text(text), "urllib+bs4"
    return text, "urllib(raw)"


@mcp.tool()
def fetch_page(
    url: str,
    max_chars: int = 8000,
    offset: int = 0,
    fmt: str = "text_markdown",
) -> str:
    """抓取网页正文并转为可读文本（免 API Key），支持分页续读。

    先用 `web_search` 拿到 url，再用本工具读取正文。长文按 max_chars 截断，
    用 offset 继续读下一段。

    Args:
        url: 目标网页地址（http/https）。
        max_chars: 单次返回的最大字符数，默认 8000（100-40000）。
        offset: 起始字符偏移，用于续读后文。
        fmt: 输出格式，"text_markdown"（默认）/"text_plain"/"text_rich"。

    Returns:
        JSON 字符串：{ok, url, method, total_chars, offset, returned_chars,
                     truncated, next_offset, title, content}
    """
    try:
        if not url.lower().startswith(("http://", "https://")):
            return _err("url 必须以 http:// 或 https:// 开头")
        limit = max(100, min(int(max_chars), 40000))
        start = max(0, int(offset))

        content, method = _fetch_content(url, fmt)
        total = len(content)
        chunk = content[start:start + limit]

        title = ""
        first_line = chunk.strip().splitlines()[0] if chunk.strip() else ""
        if first_line.startswith("#"):
            title = first_line.lstrip("# ").strip()

        next_offset = start + len(chunk) if start + len(chunk) < total else None
        return _dump({
            "ok": True,
            "url": url,
            "method": method,
            "total_chars": total,
            "offset": start,
            "returned_chars": len(chunk),
            "truncated": next_offset is not None,
            "next_offset": next_offset,
            "title": title,
            "content": chunk,
        })
    except urllib.error.HTTPError as e:
        return _err(f"fetch_page HTTP {e.code} {e.reason}: {url}")
    except Exception as e:
        return _err(f"fetch_page 失败: {e}")


@mcp.tool()
def wiki_lookup(
    query: str,
    lang: str = "zh",
    max_results: int = 5,
    extract_chars: int = 1200,
) -> str:
    """维基百科检索 + 首段摘要（MediaWiki API，免密钥，稳定可靠）。

    适合获取名词解释、人物/事件背景、术语定义等需要可靠来源的常识性内容。

    Args:
        query: 检索词，如 "生成对抗网络"、"Anthropic"。
        lang: 语言代码，"zh"（中文，默认）/"en"（英文）/"ja" 等。
        max_results: 返回条目数，默认 5（1-20）。
        extract_chars: 每个条目摘要的最大字符数，默认 1200。

    Returns:
        JSON 字符串：{ok, query, lang, count,
                     results:[{rank,title,url,summary}]}
    """
    try:
        n = max(1, min(int(max_results), 20))
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": query,
            "gsrlimit": n,
            "prop": "extracts|info",
            "exintro": 1,
            "explaintext": 1,
            "inprop": "url",
            "redirects": 1,
        }
        api = f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)
        raw, _ = _http_get(api, timeout=25)
        data = json.loads(raw.decode("utf-8", "replace"))
        pages = ((data.get("query") or {}).get("pages") or {}).values()
        results = []
        for i, p in enumerate(pages, 1):
            summary = _clean(p.get("extract"))
            if extract_chars and len(summary) > int(extract_chars):
                summary = summary[:int(extract_chars)].rstrip() + "…"
            results.append({
                "rank": i,
                "title": _clean(p.get("title")),
                "url": p.get("fullurl", ""),
                "summary": summary,
            })
        return _dump({
            "ok": True,
            "query": query,
            "lang": lang,
            "count": len(results),
            "results": results,
        })
    except Exception as e:
        return _err(f"wiki_lookup 失败: {e}")

# ══════════════════════════════════════════════════════════════════
# 🧰 自检
# ══════════════════════════════════════════════════════════════════
@mcp.tool()
def search_status(live_probe: bool = False) -> str:
    """检查搜索工具可用性：依赖版本、可用引擎、默认参数。

    首次在 Cline 里使用搜索前建议调用一次；若 `ok` 为 false 按 `hint` 安装依赖。

    Args:
        live_probe: True 时额外发一次真实搜索（约 1-3 秒），验证网络与引擎可用性。

    Returns:
        JSON 字符串：{ok, ddgs_version, backends_available, defaults, probe}
    """
    info: dict[str, Any] = {
        "defaults": {
            "region": DEFAULT_REGION,
            "backend": DEFAULT_BACKEND,
            "max_results": DEFAULT_MAX_RESULTS,
        },
        "env_keys": {
            "WEB_SEARCH_DEFAULT_REGION": DEFAULT_REGION,
            "WEB_SEARCH_DEFAULT_BACKEND": DEFAULT_BACKEND,
            "WEB_SEARCH_MAX_RESULTS": DEFAULT_MAX_RESULTS,
        },
        "optional_extras": {},
    }
    try:
        import ddgs as _ddgs  # noqa: PLC0415
        info["ddgs_version"] = getattr(_ddgs, "__version__", "unknown")
    except Exception as e:  # noqa: BLE001
        return _dump({"ok": False, "error": f"未安装 ddgs: {e}",
                      "hint": "pip install ddgs"})

    try:
        from ddgs.engines import __all__ as _engines_all  # noqa: PLC0415
        info["backends_available"] = list(_engines_all)
    except Exception:  # noqa: BLE001
        info["backends_available"] = FALLBACK_BACKENDS + ["auto"]

    for mod in ("bs4", "lxml"):
        try:
            __import__(mod)
            info["optional_extras"][mod] = True
        except Exception:  # noqa: BLE001
            info["optional_extras"][mod] = False
    info["hint_extras"] = ("fetch_page 的 HTML 回退路径建议安装："
                           "pip install beautifulsoup4 lxml")

    if live_probe:
        try:
            rows, used = _search("text", "python mcp protocol",
                                 backend="auto", region="us-en",
                                 max_results=3, safesearch="moderate",
                                 timelimit=None, page=1)
            info["probe"] = {
                "ok": True,
                "backend_used": used,
                "returned": len(rows),
                "first_title": _clean(rows[0].get("title")) if rows else "",
            }
        except Exception as e:  # noqa: BLE001
            info["probe"] = {"ok": False, "error": str(e)[:300]}

    ok = info["probe"]["ok"] if live_probe else True
    return _dump({"ok": ok, **info})


if __name__ == "__main__":
    mcp.run()
