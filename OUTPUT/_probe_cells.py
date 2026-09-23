# -*- coding: utf-8 -*-
"""量拼图三格切片的检脸情况，用于诊断 seg3 参照物为何「无人脸」。"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVER = ROOT / "mcp_server" / "comfyui_mcp_server.py"
CELLS = [str(ROOT / "OUTPUT" / "_shot125_refs" / "cells_one" / ("%s_ref.png" % s))
         for s in ("a_hj", "b_ylp", "c_zns")]
TRIPTYCH = str(ROOT / "OUTPUT" / "_shot125_refs" / "ref_three_heroes_v01.png")


def load_server():
    spec = importlib.util.spec_from_file_location("comfyui_mcp_server", SERVER)
    srv = importlib.util.module_from_spec(spec)
    sys.modules["comfyui_mcp_server"] = srv
    spec.loader.exec_module(srv)
    return srv


def show(srv, paths, det_size, label):
    res = srv.face_feature(paths="\n".join(paths), include_embedding=False,
                           reembed_px=0, det_size=det_size)
    if isinstance(res, str):
        res = json.loads(res)
    blob = res.get("face_json") or "{}"
    data = json.loads(blob) if isinstance(blob, str) else blob
    print("--- %s (det_size=%d) ---" % (label, det_size))
    for img in data.get("images", []):
        faces = img.get("faces") or []
        print("%-28s %dx%d faces=%d %s" % (
            pathlib.Path(img["file"]).name, img["width"], img["height"],
            img["face_count"],
            [(int(f["face_px_h"]), round(f["det_score"], 2), int(f["bbox"][1]))
             for f in faces]))
    return data


def main() -> int:
    srv = load_server()
    # 整张拼图（有人脸？在哪一格？）
    for ds in (640, 1024):
        show(srv, [TRIPTYCH], ds, "整张拼图")
    # 三格切片（逐张单独喂，排除批量检测干扰）
    for p in CELLS:
        for ds in (640, 1024):
            show(srv, [p], ds, "单格 %s" % pathlib.Path(p).stem)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
