#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Woosh 接线自动验收（等 ComfyUI 带 Woosh 节点重启后自动开跑）。

背景（2026-09-20）：Woosh 的依赖与权重装好时，本机正有生产渲染在跑
（`OUTPUT/_diag_act1_trench.py`），不能硬重启 ComfyUI，于是用
`OUTPUT/_restart_comfyui_when_idle.ps1` 等队列空闲再重启。
本脚本先**等 Woosh 节点出现**（= 已按新配置重启完成），再跑端到端验收：

  ① `WooshLoadFlow` / `WooshSample` / `WooshLoadVideo` 三个节点类是否已注册；
  ② `WooshLoadFlow.model_name` 下拉里是否列出 4 个主干 checkpoint；
  ③ `woosh_sfx`（T2A · DFlow 4 步）真跑一条 2 s 音效；
  ④ `woosh_v2a`（V2A · DVFlow 4 步）拿一条真实镜头 mp4 配 4 s 音轨；
  ⑤ 两条产物都用 `sound_caption` 回读 —— **音效模型报 success ≠ 出的是要的声音**。

走的是 MCP 服务器本体的函数（同 `selftest.py` 的加载方式），因此参数注入、
提交、下载、错误处理都是**真实链路**，只是不经过 stdio transport。

用法::

    python OUTPUT/_verify_woosh_after_restart.py            # 等最多 40 分钟
    python OUTPUT/_verify_woosh_after_restart.py --no-wait  # 已重启好，立即跑

报告：`OUTPUT/_woosh_verify_report.md`
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # E:\code\stem_fest
SERVER = ROOT / "mcp_server" / "comfyui_mcp_server.py"
REPORT = ROOT / "OUTPUT" / "_woosh_verify_report.md"
COMFY = "http://127.0.0.1:8188"
NEEDED_NODES = ["WooshLoadFlow", "WooshSample", "WooshLoadVideo"]
EXPECTED_CKPTS = ["Woosh-DFlow", "Woosh-DVFlow-8s", "Woosh-Flow", "Woosh-VFlow-8s"]

# 取一条已经拍好的镜头做 V2A 输入（H3 自带音轨，Woosh 只按画面重配）
V2A_SOURCE_CANDIDATES = [
    ROOT / "OUTPUT" / "06_trench" / "video",
    ROOT / "OUTPUT" / "01_trench" / "video",
    ROOT / "OUTPUT" / "sfx",
]


def log(line: str) -> None:
    print(line, flush=True)


def http_json(path: str, timeout: int = 30):
    with urllib.request.urlopen(COMFY + path, timeout=timeout) as r:
        return json.load(r)


def wait_for_woosh(max_minutes: int = 40) -> bool:
    """等 Woosh 节点注册（= ComfyUI 已带新节点重启）。

    只查单个节点（`/object_info/WooshSample`），比拉全量 object_info 轻得多
    —— 全量在重启的时间窗里会被每 15 s 拉一次，几十 MB。
    """
    deadline = time.time() + max_minutes * 60
    while time.time() < deadline:
        try:
            node = http_json("/object_info/WooshSample", timeout=20)
            if node:
                return True
            log(f"[wait] ComfyUI 在线但还没有 Woosh 节点（{int(deadline - time.time())}s 剩余）")
        except Exception as exc:  # noqa: BLE001
            log(f"[wait] ComfyUI 不可达：{type(exc).__name__}: {exc}")
        time.sleep(15)
    return False


def pick_video() -> Path | None:
    for d in V2A_SOURCE_CANDIDATES:
        if not d.is_dir():
            continue
        vids = sorted(d.glob("*.mp4"), key=lambda p: p.stat().st_size)
        if vids:
            return vids[0]
    return None


def load_server():
    spec = importlib.util.spec_from_file_location("comfyui_mcp_server", SERVER)
    srv = importlib.util.module_from_spec(spec)
    sys.modules["comfyui_mcp_server"] = srv
    spec.loader.exec_module(srv)
    return srv


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-wait", action="store_true", help="跳过等待，立即验收")
    args = ap.parse_args()

    log("=" * 70)
    log(" Woosh 接线验收")
    log("=" * 70)

    if not args.no_wait and not wait_for_woosh():
        REPORT.write_text("# Woosh 验收：失败\n\n等待 Woosh 节点超时（ComfyUI 未按新配置重启）。\n",
                          encoding="utf-8")
        log("[X] 等不到 Woosh 节点，放弃")
        return 1

    info = {}
    for n in NEEDED_NODES:
        try:
            got = http_json(f"/object_info/{n}", timeout=30)
            if got:
                info.update(got)
        except Exception:  # noqa: BLE001
            pass
    missing = [n for n in NEEDED_NODES if n not in info]
    log(f"[1] 节点注册：缺失 {missing or '无'}")

    combo = []
    try:
        spec = info["WooshLoadFlow"]["input"]["required"]["model_name"][0]
        combo = list(spec) if isinstance(spec, list) else []
    except Exception as exc:  # noqa: BLE001
        log(f"    读 model_name 下拉失败：{exc}")
    log(f"[2] model_name 下拉：{combo}")

    srv = load_server()
    log("[3] MCP 工具 woosh_sfx（T2A · DFlow 4 步 · 2 s）")
    t2a = json.loads(srv.woosh_sfx(
        prompt="short crisp paper airplane whooshing past close to the microphone",
        duration=2.0, model="dflow", seed=4242,
        filename_prefix="_woosh_verify_t2a", timeout_seconds=900,
    ))
    log("    " + json.dumps(t2a, ensure_ascii=False)[:400])

    v2a: dict = {"ok": False, "skipped": True}
    src = pick_video()
    if src is None:
        log("[4] 跳过 V2A：找不到可用的 mp4 输入")
    else:
        log(f"[4] MCP 工具 woosh_v2a（V2A · DVFlow 4 步 · 4 s）← {src.name}")
        v2a = json.loads(srv.woosh_v2a(
            video=str(src), prompt="wind over soil and distant footsteps on gravel",
            duration=4.0, model="dvflow", seed=5252,
            filename_prefix="_woosh_verify_v2a", timeout_seconds=900,
        ))
        log("    " + json.dumps(v2a, ensure_ascii=False)[:400])

    captions: dict[str, dict] = {}
    for tag, res in (("t2a", t2a), ("v2a", v2a)):
        files = res.get("files") or []
        if not files:
            continue
        path = files[0].get("path")
        if not path:
            continue
        log(f"[5] sound_caption ← {tag}")
        captions[tag] = json.loads(srv.sound_caption(audio=path, max_new_tokens=200))
        log("    " + json.dumps(captions[tag].get("caption_json") or captions[tag],
                                ensure_ascii=False)[:500])

    # ── 报告 ──────────────────────────────────────────────────────
    ok_nodes = not missing
    ok_combo = all(c in combo for c in EXPECTED_CKPTS)
    ok_t2a = bool(t2a.get("ok")) and t2a.get("status") == "success"
    ok_v2a = bool(v2a.get("skipped")) or (bool(v2a.get("ok")) and v2a.get("status") == "success")

    lines = [
        "# Woosh 接线验收报告（2026-09-20）",
        "",
        f"- 运行时刻：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "| 检查 | 结果 |",
        "|---|---|",
        f"| ① 节点注册（{', '.join(NEEDED_NODES)}） | {'✅ 全部就位' if ok_nodes else '❌ 缺 ' + str(missing)} |",
        f"| ② model_name 下拉含 4 个主干 | {'✅' if ok_combo else '❌ ' + str(combo)} |",
        f"| ③ woosh_sfx（T2A） | {('✅ ' + str(t2a.get('elapsed_sec')) + ' s') if ok_t2a else '❌ ' + str(t2a)[:200]} |",
        f"| ④ woosh_v2a（V2A） | {'⏭ 跳过（无 mp4 输入）' if v2a.get('skipped') else (('✅ ' + str(v2a.get('elapsed_sec')) + ' s') if ok_v2a else '❌ ' + str(v2a)[:200])} |",
        "",
        "## 产物与回读（sound_caption）",
        "",
    ]
    for tag, res in (("T2A", t2a), ("V2A", v2a)):
        lines += [f"### {tag}", "", "```json",
                  json.dumps(res, ensure_ascii=False, indent=2)[:2000], "```"]
        cap = captions.get(tag.lower())
        if cap:
            body = cap.get("caption_json") or {}
            lines += ["", f"**回读**：`{body.get('caption', '(无)')}`"]
        lines.append("")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    log(f"[report] {REPORT}")
    log(f"[result] nodes={ok_nodes} combo={ok_combo} t2a={ok_t2a} v2a={ok_v2a}")

    return 0 if (ok_nodes and ok_combo and ok_t2a and ok_v2a) else 2


if __name__ == "__main__":
    raise SystemExit(main())
