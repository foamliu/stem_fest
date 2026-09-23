# -*- coding: utf-8 -*-
"""测量镜 125 候选定妆照的「脸高」，为 R2V 拼图选图定依据。

README §6.5 判据：`face_px_h >= 250` 才可判（更小的脸提的 ArcFace 特征严重失真）。
用法：py -3.10 OUTPUT/_probe_face_h.py
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVER = ROOT / "mcp_server" / "comfyui_mcp_server.py"

CANDS = [
    "ASSETS/CHARACTERS/05_huang_jiguang/huang_jiguang_closeup_v01.png",
    "ASSETS/CHARACTERS/_group/solo_huang_jiguang_hero_v01.png",
    "ASSETS/CHARACTERS/06_yuan_longping/06_yuan_longping_closeup_v01_16x9.png",
    "ASSETS/CHARACTERS/06_yuan_longping/yuan_longping_hero_v02.png",
    "ASSETS/CHARACTERS/_group/solo_yuan_longping_hero_v01.png",
    "ASSETS/CHARACTERS/07_zhong_nanshan/zhong_nanshan_hero_v01.png",
    "ASSETS/CHARACTERS/_group/solo_zhong_nanshan_hero_v01.png",
]


def load_server():
    spec = importlib.util.spec_from_file_location("comfyui_mcp_server", SERVER)
    srv = importlib.util.module_from_spec(spec)
    sys.modules["comfyui_mcp_server"] = srv
    spec.loader.exec_module(srv)
    return srv


def main() -> int:
    srv = load_server()
    res = srv.face_feature(paths="\n".join(CANDS), include_embedding=False)
    if isinstance(res, str):
        res = json.loads(res)
    blob = res.get("face_json") or "{}"
    data = json.loads(blob) if isinstance(blob, str) else blob

    print("%-46s %-11s %-6s %s" % ("文件", "尺寸", "脸数", "脸高/置信（主脸在前）"))
    print("-" * 96)
    for img in data.get("images", []):
        name = pathlib.Path(img["file"]).name
        faces = img.get("faces") or []
        detail = ", ".join("%dpx/%.2f" % (f["face_px_h"], f["det_score"]) for f in faces) or "无脸"
        ok = "[OK]" if faces and faces[0]["face_px_h"] >= 250 else ("[WARN]" if faces else "[NO-FACE]")
        print("%-46s %-11s %-6d %s %s" % (
            name, "%dx%d" % (img["width"], img["height"]), img["face_count"], detail, ok))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
