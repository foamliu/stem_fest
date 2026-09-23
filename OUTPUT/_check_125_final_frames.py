# -*- coding: utf-8 -*-
"""镜 125 三段独立生成版的抽帧验收。

抽出 12 帧覆盖三个段（段1 0-3.04s / 段2 3.04-6.08s / 段3 6.08-8.01s），
逐帧用 face_feature 记录脸高、脸顶位置，判断「头顶是否被裁」。
脸顶位置 = bbox[1] / 高度；<0.06 视为贴边（有裁头风险）。
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVER = ROOT / "mcp_server" / "comfyui_mcp_server.py"
VIDEO = ROOT / "OUTPUT" / "05_classroom_night" / "video" / "125_three_stills_flash_00006_.mp4"
OUT = ROOT / "OUTPUT" / "_shot125_final"
SEGS = [("seg1 黄继光", 0.20, 3.04), ("seg2 袁隆平", 3.04, 6.08), ("seg3 钟南山", 6.08, 8.01)]
N_PER_SEG = 4


def load_server():
    spec = importlib.util.spec_from_file_location("comfyui_mcp_server", SERVER)
    srv = importlib.util.module_from_spec(spec)
    sys.modules["comfyui_mcp_server"] = srv
    spec.loader.exec_module(srv)
    return srv


def grab(ts: float, dst: pathlib.Path) -> bool:
    cmd = ["ffmpeg", "-y", "-ss", "%.2f" % ts, "-i", str(VIDEO),
           "-frames:v", "1", "-q:v", "2", str(dst)]
    p = subprocess.run(cmd, capture_output=True)
    return p.returncode == 0 and dst.exists()


def main() -> int:
    if not VIDEO.exists():
        print("缺文件：%s" % VIDEO)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    srv = load_server()
    frames = []
    for label, t0, t1 in SEGS:
        for i in range(N_PER_SEG):
            ts = t0 + (t1 - t0) * (i + 0.5) / N_PER_SEG
            dst = OUT / ("%s_f%d.jpg" % (label.split()[0], i + 1))
            if grab(ts, dst):
                frames.append((label, ts, dst))
            else:
                print("抽帧失败 %s @%.2fs" % (label, ts))
    print("抽出 %d 帧 -> %s\n" % (len(frames), OUT))
    for label, ts, dst in frames:
        res = srv.face_feature(paths=str(dst), include_embedding=False, reembed_px=0)
        if isinstance(res, str):
            res = json.loads(res)
        blob = res.get("face_json") or {}
        data = json.loads(blob) if isinstance(blob, str) else blob
        im = (data.get("images") or [{}])[0]
        faces = im.get("faces") or []
        if not faces:
            print("%-12s @%5.2fs  脸=0（未检出/过紧/远景）" % (label, ts))
            continue
        f = faces[0]
        h = f["face_px_h"]
        top = f["bbox"][1] / float(im["height"])
        note = ""
        if top < 0.06:
            note = "!! 头顶贴边（可能裁头）"
        elif top < 0.12:
            note = "~ 偏紧"
        else:
            note = "OK 头肩完整"
        print("%-12s @%5.2fs  脸数=%d 脸高=%3dpx 脸顶=%.0f%%  %s" % (
            label, ts, len(faces), h, top * 100, note))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
