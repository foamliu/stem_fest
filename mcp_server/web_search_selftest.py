#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""web_search MCP 服务器离线自检 —— 不需要联网。

校验：工具注册、结果整形、fetch_page 分页、wiki_lookup 解析、参数归一化、错误路径。

用法::

    python mcp_server/web_search_selftest.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parent / "web_search_mcp_server.py"
spec = importlib.util.spec_from_file_location("web_search_mcp_server", SERVER)
srv = importlib.util.module_from_spec(spec)
sys.modules["web_search_mcp_server"] = srv
spec.loader.exec_module(srv)

FAILURES: list[str] = []


def _check(label: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}"
          + (f"  -> {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(label)


# ── 桩：拦截网络 ──────────────────────────────────────────────────
FAKE = {
    "text": [
        {"title": "T1 <b>bold</b>", "href": "https://a.test/1", "body": "S1  A   B"},
        {"title": "T2", "href": "https://a.test/2", "body": "S2"},
    ],
    "news": [
        {"title": "N1", "url": "https://n.test/1", "body": "NS1",
         "date": "2026-09-10T01:00:00+00:00", "source": "SrcA"},
    ],
    "images": [
        {"title": "I1", "image": "https://i.test/1.jpg",
         "thumbnail": "https://t.test/1.jpg", "url": "https://p.test/1",
         "width": "1024", "height": "768", "source": "SrcB"},
    ],
}
CALLS: list[tuple] = []


def fake_search(category, query, *, backend, **kwargs):
    CALLS.append((category, query, backend, kwargs))
    return FAKE[category], "mock-engine"


def fake_fetch(url, fmt):
    # 1000 字符且各段互不相同，以便校验 offset 续读确实换内容
    return ("".join(f"{i:04d}" for i in range(250)), f"mock({fmt})")


WIKI_JSON = {
    "query": {
        "pages": {
            "1": {"title": "人工智能", "fullurl": "https://zh.wikipedia.org/wiki/X",
                  "extract": "人工智能（AI）指让计算机完成需要人类智能的任务。"},
        }
    }
}


def fake_http_get(url, timeout=30):
    return json.dumps(WIKI_JSON).encode("utf-8"), "application/json"


srv._search = fake_search
srv._fetch_content = fake_fetch
srv._http_get = fake_http_get
def main() -> int:
    print("=" * 68)
    print(" web_search MCP Server 自检（离线）")
    print("=" * 68)

    print("\n[1] 工具注册")
    tools = sorted(t.name for t in srv.mcp._tool_manager.list_tools())
    expected = ["fetch_page", "search_images", "search_news", "search_status",
                "web_search", "wiki_lookup"]
    _check("工具数量 = 6", len(tools) == 6, f"实际 {len(tools)}: {tools}")
    for name in expected:
        _check(f"已注册 {name}", name in tools)

    print("\n[2] web_search 结果整形")
    CALLS.clear()
    out = json.loads(srv.web_search("hello", max_results=5))
    _check("ok 且 count 正确", out.get("ok") and out.get("count") == 2, str(out)[:160])
    r0 = out["results"][0]
    _check("title 去除 HTML 标签", r0["title"] == "T1 bold", r0["title"])
    _check("snippet 压缩空白", r0["snippet"] == "S1 A B", r0["snippet"])
    _check("rank 从 1 开始", [r["rank"] for r in out["results"]] == [1, 2])
    _check("回传 backend_used", out.get("backend_used") == "mock-engine")
    _check("默认 region=cn-zh 生效", CALLS[0][3]["region"] == "cn-zh", str(CALLS[0][3]))
    json.loads(srv.web_search("x", region="us-en"))
    _check("region 可覆盖", CALLS[-1][3]["region"] == "us-en")
    json.loads(srv.web_search("x", timelimit="zzz"))
    _check("timelimit 非法值归一为 None", CALLS[-1][3]["timelimit"] is None)
    json.loads(srv.web_search("x", timelimit="W"))
    _check("timelimit 合法值小写透传", CALLS[-1][3]["timelimit"] == "w")

    print("\n[3] search_news / search_images")
    news = json.loads(srv.search_news("n", max_results=3))
    _check("news 含 date/source",
           news["results"][0]["date"].startswith("2026-09-10")
           and news["results"][0]["source"] == "SrcA", str(news["results"][0]))
    _check("news 默认 timelimit=w", CALLS[-1][3]["timelimit"] == "w")
    imgs = json.loads(srv.search_images("i", max_results=3))
    _check("images 含 image/thumbnail/page_url",
           imgs["results"][0]["image"].endswith(".jpg")
           and imgs["results"][0]["page_url"] == "https://p.test/1",
           str(imgs["results"][0]))

    print("\n[4] fetch_page 分页与截断")
    LIMIT = 100
    p1 = json.loads(srv.fetch_page("https://x.test/page", max_chars=LIMIT))
    _check("返回 total_chars", p1["total_chars"] == 1000, str(p1["total_chars"]))
    _check("返回内容长度=limit", p1["returned_chars"] == LIMIT)
    _check("truncated=True", p1["truncated"] is True)
    _check("next_offset=limit", p1["next_offset"] == LIMIT)
    p2 = json.loads(srv.fetch_page("https://x.test/page", max_chars=LIMIT,
                                   offset=p1["next_offset"]))
    _check("续读内容不同", p2["content"] != p1["content"])
    _check("续读 offset 正确", p2["offset"] == LIMIT)
    p3 = json.loads(srv.fetch_page("https://x.test/page", max_chars=40000))
    _check("一次读完 truncated=False", p3["truncated"] is False
           and p3["next_offset"] is None)
    bad = json.loads(srv.fetch_page("ftp://bad"))
    _check("非法协议被拒绝", bad.get("ok") is False, str(bad)[:120])

    print("\n[5] wiki_lookup")
    wk = json.loads(srv.wiki_lookup("人工智能", lang="zh", max_results=2,
                                    extract_chars=1000))
    _check("ok 且解析条目", wk.get("ok") and wk["count"] == 1, str(wk)[:160])
    _check("标题与链接解析", wk["results"][0]["title"] == "人工智能"
           and wk["results"][0]["url"].startswith("https://"), str(wk["results"][0]))
    _check("摘要非空", len(wk["results"][0]["summary"]) > 5)

    print("\n[6] search_status")
    st = json.loads(srv.search_status())
    _check("默认值暴露完整",
           st["defaults"]["region"] == "cn-zh" and "backend" in st["defaults"],
           str(st)[:200])
    _check("ddgs 版本可见", bool(st.get("ddgs_version")), str(st)[:200])
    st2 = json.loads(srv.search_status(live_probe=True))
    _check("live_probe 走通（已桩化）", st2.get("probe", {}).get("ok") is True)

    print("\n[7] 错误路径")
    orig = srv._search

    def _boom(*a, **k):
        raise RuntimeError("all engines down")

    srv._search = _boom
    err = json.loads(srv.web_search("x"))
    _check("搜索失败返回 ok:false", err.get("ok") is False
           and "失败" in err.get("error", ""), str(err)[:120])
    srv._search = orig

    print("\n" + "=" * 68)
    if FAILURES:
        print(f" 结果：{len(FAILURES)} 项失败")
        for f in FAILURES:
            print(f"   x {f}")
        return 1
    print(" 结果：全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
