#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对照探针：V2A 到底是「跟画面走」还是「跟文字走」？

首轮验收（见 `OUTPUT/_woosh_verify_report.md`）里，喂的是镜 35（人物点头喊话），
文字写的是 "wind over soil and distant footsteps on gravel"，候选却是
"a single, loud, and sharp vocal burst ... shout or yell"。
本探针换一条**没有发声动作**的镜头（人物蹲下看野菜）再跑一次，
看文字提示能否把 V2A 引向环境声。

用法：python OUTPUT/_probe_woosh_v2a_quiet.py [视频路径] [prompt] [prefix]
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "mcp_server" / "comfyui_mcp_server.py"
CLIP = ROOT / "OUTPUT" / "06_trench" / "video" / "_mid_21_zhang_crouches_looks_at_wild_veg_00001_.mp4"
PROMPT = "wind over dry soil, faint distant artillery rumble, cloth rustling, no voices"
PREFIX = "_probe_woosh_v2a_quiet"


def load_server():
    spec = importlib.util.spec_from_file_location("comfyui_mcp_server", SERVER)
    srv = importlib.util.module_from_spec(spec)
    sys.modules["comfyui_mcp_server"] = srv
    spec.loader.exec_module(srv)
    return srv


def main() -> int:
    srv = load_server()
    clip = Path(sys.argv[1]) if len(sys.argv) > 1 else CLIP
    if not clip.is_absolute():
        clip = ROOT / clip
    prompt = sys.argv[2] if len(sys.argv) > 2 else PROMPT
    prefix = sys.argv[3] if len(sys.argv) > 3 else PREFIX
    print(f"[probe] clip = {clip.name}", flush=True)
    print(f"[probe] prompt = {prompt}", flush=True)

    res = json.loads(srv.woosh_v2a(
        video=str(clip), prompt=prompt,
        duration=4.0, model="dvflow", seed=7777,
        filename_prefix=prefix, timeout_seconds=900,
    ))
    print("[probe] woosh_v2a -> " + json.dumps(res, ensure_ascii=False)[:300], flush=True)

    files = res.get("files") or []
    if files and files[0].get("path"):
        cap = json.loads(srv.sound_caption(audio=files[0]["path"], max_new_tokens=200))
        body = cap.get("caption_json") or {}
        print("[probe] sound_caption -> " + str(body.get("caption")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
