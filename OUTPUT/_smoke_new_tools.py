#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""新工具端到端冒烟测试（直连 ComfyUI，不经过 MCP 服务）。

覆盖三条链路：
  ① stable_audio_3_sfx  —— 只用 ComfyUI **核心节点**，无需重启即可验证
  ② sound_caption       —— 需要自定义节点 LAIONAudioCaption（**必须重启 ComfyUI**）
  ③ face_feature        —— 需要自定义节点 InsightFaceFeature（**必须重启 ComfyUI**）

用法：
  py -3.10 OUTPUT/_smoke_new_tools.py                # 三条全跑
  py -3.10 OUTPUT/_smoke_new_tools.py --only=sfx     # 只跑第一条
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WF_DIR = ROOT / "workflows"
OUT = ROOT / "OUTPUT" / "_smoke_new"
COMFY = "http://127.0.0.1:8188"
COMFY_INPUT = Path(r"E:\code\ComfyUI\input")


def http_json(endpoint: str, payload: dict | None = None, method: str = "POST",
              timeout: int = 60):
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(f"{COMFY}{endpoint}", data=body,
                                 headers={"Content-Type": "application/json"},
                                 method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", "replace")
    return json.loads(raw) if raw else {}


def upload(path: Path) -> str:
    boundary = "----smoke" + uuid.uuid4().hex
    name = f"smoke_{uuid.uuid4().hex[:8]}{path.suffix.lower()}"
    parts = [f"--{boundary}\r\n".encode(),
             (f'Content-Disposition: form-data; name="image"; filename="{name}"\r\n'
              "Content-Type: application/octet-stream\r\n\r\n").encode(),
             path.read_bytes(), f"\r\n--{boundary}--\r\n".encode()]
    req = urllib.request.Request(f"{COMFY}/upload/image", data=b"".join(parts),
                                 headers={"Content-Type":
                                          f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode())["name"]


def run(wf: dict, timeout: int = 1500) -> tuple[dict, float]:
    t0 = time.time()
    pid = http_json("/prompt", {"prompt": wf, "client_id": f"smoke_{uuid.uuid4().hex[:6]}"})
    pid = pid["prompt_id"]
    while time.time() - t0 < timeout:
        entry = http_json(f"/history/{pid}", method="GET", timeout=30).get(pid)
        if entry:
            st = (entry.get("status") or {}).get("status_str")
            if st == "error":
                return {"error": (entry.get("status") or {}).get("messages")}, time.time() - t0
            if entry.get("outputs") or st == "success":
                return entry, time.time() - t0
        time.sleep(3)
    return {"timeout": True, "prompt_id": pid}, time.time() - t0


def save_outputs(entry: dict) -> list[dict]:
    OUT.mkdir(parents=True, exist_ok=True)
    saved = []
    for _nid, nd in (entry.get("outputs") or {}).items():
        for key in ("audio", "images", "gifs", "videos"):
            for item in nd.get(key) or []:
                fn = item.get("filename")
                if not fn:
                    continue
                q = urllib.parse.urlencode({"filename": fn,
                                            "subfolder": item.get("subfolder", ""),
                                            "type": item.get("type", "output")})
                with urllib.request.urlopen(f"{COMFY}/view?{q}", timeout=300) as r:
                    blob = r.read()
                (OUT / fn).write_bytes(blob)
                saved.append({"file": fn, "kb": round(len(blob) / 1024, 1)})
        for txt in nd.get("text") or []:
            if isinstance(txt, str):
                saved.append({"inline_text": txt})
    return saved


def load(name: str) -> dict:
    return json.loads((WF_DIR / name).read_text(encoding="utf-8"))


def test_sfx() -> bool:
    print("\n=== ① stable_audio_3_sfx（核心节点，无需重启）===")
    wf = load("Stable Audio 3 音效生成.json")
    wf["3"]["inputs"]["text"] = ("short clean foley of a paper plane whooshing past "
                                 "the camera, outdoor ambience")
    wf["4"]["inputs"]["text"] = "music, speech, distorted"
    wf["5"]["inputs"]["seconds"] = 6.0
    wf["6"]["inputs"].update({"seed": 20260916, "steps": 8, "cfg": 1.0,
                              "sampler_name": "lcm", "scheduler": "simple"})
    wf["8"]["inputs"]["filename_prefix"] = "sfx/smoke_paper_plane"
    entry, dt = run(wf)
    if "error" in entry or entry.get("timeout"):
        print(f"  X 失败（{dt:.0f}s）：{json.dumps(entry, ensure_ascii=False)[:500]}")
        return False
    files = save_outputs(entry)
    print(f"  OK 成功（{dt:.0f}s）{json.dumps(files, ensure_ascii=False)}")
    heavy = [f for f in files if f.get("kb", 0) > 10]
    print(f"  产物体积检查：{'通过（>10KB，不是空音频）' if heavy else '偏小，需人工复核'}")
    return bool(heavy)


def test_caption() -> bool:
    print("\n=== ② sound_caption（需自定义节点 LAIONAudioCaption）===")
    wav = COMFY_INPUT / "01_school_gate_girl_mother_00001__asr16k.wav"
    if not wav.exists():
        print("  - 跳过：找不到测试音频")
        return False
    name = upload(wav)
    wf = load("Sound Caption (LAION Whisper).json")
    wf["1"]["inputs"]["audio"] = name
    entry, dt = run(wf)
    if "error" in entry or entry.get("timeout"):
        print(f"  X 失败（{dt:.0f}s）：{json.dumps(entry, ensure_ascii=False)[:600]}")
        print("  !! 若报 class_type 不存在 ⇒ 必须重启 ComfyUI 才能注册自定义节点")
        return False
    for f in save_outputs(entry):
        if f.get("inline_text"):
            d = json.loads(f["inline_text"])
            print(f"  OK 成功（{dt:.0f}s）\n  caption: {d.get('caption', '')[:300]}")
            return bool(d.get("ok"))
    print("  ? 无文本回传")
    return False


def test_face() -> bool:
    print("\n=== ③ face_feature（需自定义节点 InsightFaceFeature）===")
    hero = ROOT / "ASSETS" / "CHARACTERS" / "01_liu_siqi" / "liu_siqi_closeup_v02_16x9.png"
    wf = load("Face Feature (InsightFace).json")
    wf["1"]["inputs"].update({"paths": str(hero), "model_name": "buffalo_l",
                              "provider": "CPU", "include_embedding": True})
    entry, dt = run(wf)
    if "error" in entry or entry.get("timeout"):
        print(f"  X 失败（{dt:.0f}s）：{json.dumps(entry, ensure_ascii=False)[:600]}")
        print("  !! 若报 class_type 不存在 ⇒ 必须重启 ComfyUI 才能注册自定义节点")
        return False
    for f in save_outputs(entry):
        if f.get("inline_text"):
            d = json.loads(f["inline_text"])
            img = (d.get("images") or [{}])[0]
            faces = img.get("faces") or [{}]
            print(f"  OK 成功（{dt:.0f}s）检出 {img.get('face_count')} 张脸，"
                  f"主脸高 {faces[0].get('face_px_h')}px，emb_dim={faces[0].get('embedding_dim')}")
            return bool(d.get("ok"))
    return False


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", choices=("", "sfx", "caption", "face"))
    args = ap.parse_args()
    r = {}
    if args.only in ("", "sfx"):
        r["sfx"] = test_sfx()
    if args.only in ("", "caption"):
        r["caption"] = test_caption()
    if args.only in ("", "face"):
        r["face"] = test_face()
    print("\n结果：" + "  ".join(f"{k}={'OK' if v else 'FAIL'}" for k, v in r.items()))
    sys.exit(0 if all(r.values()) else 1)
