# -*- coding: utf-8 -*-
"""核对三张单格参考图的「脸占画幅比例」——H3 会按参考图的取景推镜。

经验：脸占画幅 >70% 时 H3 倾向输出大特写（容易把头顶裁掉）；
      控制在 45~60% 时输出半身中景（头肩完整）。目标区间 0.40~0.65。
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVER = ROOT / "mcp_server" / "comfyui_mcp_server.py"
SLUGS = ("a_hj", "b_ylp", "c_zns")


def load_server():
    spec = importlib.util.spec_from_file_location("comfyui_mcp_server", SERVER)
    srv = importlib.util.module_from_spec(spec)
    sys.modules["comfyui_mcp_server"] = srv
    spec.loader.exec_module(srv)
    return srv


def main() -> int:
    srv = load_server()
    ok = True
    for slug in SLUGS:
        p = ROOT / "OUTPUT" / "_shot125_refs" / "cells_one" / ("%s_ref.png" % slug)
        res = srv.face_feature(paths=str(p), include_embedding=False, reembed_px=0)
        if isinstance(res, str):
            res = json.loads(res)
        blob = res.get("face_json") or "{}"
        data = json.loads(blob) if isinstance(blob, str) else blob
        im = (data.get("images") or [{}])[0]
        faces = im.get("faces") or []
        if not faces:
            print("%-8s  未检出脸（脸可能过大/过紧，检测器漏检）" % slug)
            ok = False
            continue
        f = faces[0]
        ratio = f["face_px_h"] / float(im["height"])
        good = 0.30 <= ratio <= 0.68
        ok = ok and good
        print("%-8s  画幅=%dx%d  脸高=%dpx  占比=%.0f%%  det=%.2f  %s" % (
            slug, im["width"], im["height"], f["face_px_h"], ratio * 100,
            f["det_score"], "OK" if good else "!! 超出 30~68% 目标区间"))
    print("\n判定：%s" % ("三张单格参考图脸占比均达标" if ok else "有图需调整"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
