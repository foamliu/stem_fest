# -*- coding: utf-8 -*-
"""为镜 125 的段 3（钟南山）生成「头肩完整的中景」参考图。

## 为什么需要这一步

段 1（黄继光）、段 2（袁隆平）用拼图单格作参考图时，格内**本来就有肩与胸口**，
H3 R2V 于是正常输出半身中景。

段 3 的源定妆照 `zhong_nanshan_hero_v01.png` 是**紧裁的「脸 + 单肩」肖像**，
且右下角带「新华网 WWW.NEWS.CN」水印 ⇒ `_make_125_triptych.py` 用
`WM_KEEPOUT=0.72` 把裁框下边界压到水印之上，结果格 3 只剩脸与一小截肩。
H3 跟随参考图的取景松紧 ⇒ **一路推成大特写，头顶被裁出画面上边界**
（实测脸高 620–653px / 608 画幅，脸顶 −15%~−19%）。

## 做法

用 `image_edit_longcat` 以定妆照为输入，**只改景别不改身份**：
把人物放进「头 + 肩 + 胸口衬衫」的中景，背景纯净 —— 与段 1/2 的参考图同构。
生成后回读检脸，要求脸占画幅 30~50% 且脸顶 >= 8%（说明有头顶留空）。

用法：py -3.10 OUTPUT/_make_125_seg3_ref.py
产物：OUTPUT/_shot125_refs/cells_one/c_zns_ref_mid.png
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVER = ROOT / "mcp_server" / "comfyui_mcp_server.py"
SRC = ROOT / "ASSETS" / "CHARACTERS" / "07_zhong_nanshan" / "zhong_nanshan_hero_v01.png"
DST = ROOT / "OUTPUT" / "_shot125_refs" / "cells_one" / "c_zns_ref_mid.png"

EDIT_PROMPT = (
    "Same person, same face, same glasses, same grey-black combed-back hair. "
    "Change only the framing: full head and shoulders medium portrait, "
    "his head fully inside the frame with empty space above the hair, "
    "showing both shoulders and the collar and chest of his light blue shirt, "
    "plain dark grey studio background, soft even lighting, "
    "formal memorial portrait photo, vertical composition, "
    "centered, sharp focus, high detail."
)

NEGATIVE = (
    "close-up crop, cropped forehead, cut off top of head, watermark, text, "
    "extra person, different face, younger, older, distorted hands"
)


def load_server():
    spec = importlib.util.spec_from_file_location("comfyui_mcp_server", SERVER)
    srv = importlib.util.module_from_spec(spec)
    sys.modules["comfyui_mcp_server"] = srv
    spec.loader.exec_module(srv)
    return srv


def main() -> int:
    srv = load_server()
    DST.parent.mkdir(parents=True, exist_ok=True)
    print("源图：%s" % SRC)
    print("出图：%s\n" % DST)

    res = srv.image_edit_longcat(
        prompt=EDIT_PROMPT,
        image=str(SRC),
        negative_prompt=NEGATIVE,
        seed=9834,
        megapixels=0.45,
        steps=50,
        guidance=4.5,
        cfg=4.5,
        filename_prefix="act5v/zns_mid",
        output_dir=str(ROOT / "OUTPUT" / "_shot125_refs" / "_gen"),
        wait=True,
        timeout_seconds=1800,
    )
    d = json.loads(res) if isinstance(res, str) else res
    if not d.get("ok"):
        print("[X] 生成失败：%s" % json.dumps(d, ensure_ascii=False)[:400])
        return 2
    files = d.get("files") or []
    if not files:
        print("[X] 无产物")
        return 2
    src_png = pathlib.Path(files[0]["path"])
    print("[gen] %s  %.1f KB" % (src_png, src_png.stat().st_size / 1024.0))

    # 复制成目标名（保持产物可追溯）
    DST.write_bytes(src_png.read_bytes())
    print("[out] %s" % DST)

    # 回读检脸：要求脸占 30~50%、脸顶 >= 8%
    res2 = srv.face_feature(paths=str(DST), include_embedding=False, reembed_px=0,
                            det_size=1024, min_det_score=0.3)
    d2 = json.loads(res2) if isinstance(res2, str) else res2
    blob = d2.get("face_json") or {}
    data = json.loads(blob) if isinstance(blob, str) else blob
    im = (data.get("images") or [{}])[0]
    faces = im.get("faces") or []
    if not faces:
        print("[verify] 未检出脸 —— 需人工看图（可能构图过紧）")
        return 3
    f = faces[0]
    ratio = f["face_px_h"] / float(im["height"])
    top = f["bbox"][1] / float(im["height"])
    ok = (0.25 <= ratio <= 0.55) and top >= 0.06
    print("[verify] %dx%d 脸数=%d 脸高=%dpx 占比=%.0f%% 脸顶=%.0f%%  %s" % (
        im["width"], im["height"], im["face_count"], f["face_px_h"],
        ratio * 100, top * 100, "OK" if ok else "!! 仍偏紧"))
    return 0 if ok else 4


if __name__ == "__main__":
    raise SystemExit(main())
