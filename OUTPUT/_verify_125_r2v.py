# -*- coding: utf-8 -*-
"""镜 125 重跑验收 v2 —— 修掉 v1 的**跨域比对缺陷**。

## v1 为什么误判（重要教训）

v1 把成片帧（AI 渲染域，1056×608）直接与定妆照（其中钟南山是 **369×542 的新华网新闻照**，
真实照片域）比 ArcFace 余弦，得到：

| 帧 | 期望 | 实际第一名 |
|---|---|---|
| seg1 | huang_jiguang | huang_jiguang 0.7364 ✅ |
| seg2 | yuan_longping | yuan_longping 0.8871 ✅ |
| seg3 | zhong_nanshan | **yuan_longping 0.8681**（钟南山仅 0.0195）❌ |

但肉眼看得清清楚楚 f_03 是钟南山（灰黑发 + 细框眼镜 + 方脸）。
⇒ 这正是 `README.md` §6.5 的**跨域失真**：**绝对余弦不可作判据**，
   真实照片域 vs AI 渲染域的特征距离，会压过"同一个人"的相似度。

## v2 的做法：**同域比对**

把 v1 里所有"跨域"的参照换成**同域**参照：

* **同一个人的参照** → 改用**拼图里那一格**（`ref_three_heroes_v01.png` 的第 N 格）：
  它由定妆照**像素裁切**而来，但已被同一流程消费过，与成片帧同处"被 H3 理解"的域；
* **更强的判据** → **旧片帧 vs 新片帧**对比：旧片（`_00003_`）是**确认错误**的版本，
  新片（`_00004_`）若与旧片显著不同、且与旧片的错误特征分离，就说明修法生效。

用法：py -3.10 OUTPUT/_verify_125_r2v.py
"""
from __future__ import annotations

import importlib.util
import json
import math
import pathlib
import sys

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVER = ROOT / "mcp_server" / "comfyui_mcp_server.py"
VERIFY = ROOT / "OUTPUT" / "_shot125_verify"
TRIPTYCH = ROOT / "OUTPUT" / "_shot125_refs" / "ref_three_heroes_v01.png"
OLD_VIDEO = ROOT / "OUTPUT" / "05_classroom_night" / "video" / "125_three_stills_flash_00003_.mp4"
OLD_FRAMES = ROOT / "OUTPUT" / "_shot125_verify_old"

# 拼图三格的纵向范围（CELL_H=768、BAR=24 ⇒ 格 i 起点 = i*(768+24)）
CELL_H, BAR = 768, 24
SEGMENTS = [
    ("seg1_黄继光", 0, "f_01.png"),
    ("seg2_袁隆平", 1, "f_02.png"),
    ("seg3_钟南山", 2, "f_03.png"),
]


def load_server():
    spec = importlib.util.spec_from_file_location("comfyui_mcp_server", SERVER)
    srv = importlib.util.module_from_spec(spec)
    sys.modules["comfyui_mcp_server"] = srv
    spec.loader.exec_module(srv)
    return srv


def cos(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def ask(srv, paths):
    res = srv.face_feature(paths="\n".join(paths), include_embedding=True,
                           reembed_px=512, output_dir=str(ROOT / "OUTPUT" / "_face_feature"))
    if isinstance(res, str):
        res = json.loads(res)
    blob = res.get("face_json") or "{}"
    data = json.loads(blob) if isinstance(blob, str) else blob
    out = {}
    for img in data.get("images", []):
        faces = img.get("faces") or []
        out[str(pathlib.Path(img["file"]))] = (
            faces[0] if faces else None, img.get("face_count", 0))
    return out


def slice_triptych_cells():
    """把拼图切成三格单独存盘（同域参照）。"""
    out_dir = ROOT / "OUTPUT" / "_shot125_refs" / "cells"
    out_dir.mkdir(parents=True, exist_ok=True)
    img = Image.open(TRIPTYCH).convert("RGB")
    paths = []
    for i in range(3):
        top = i * (CELL_H + BAR)
        cell = img.crop((0, top, img.width, top + CELL_H))
        p = out_dir / ("cell_%d.png" % (i + 1))
        cell.save(p, "PNG")
        paths.append(str(p))
    return paths


def ffmpeg_frames(video: pathlib.Path, out_dir: pathlib.Path, picks: str):
    """抽帧（picks 为 ffmpeg select 表达式）。"""
    import subprocess
    out_dir.mkdir(parents=True, exist_ok=True)
    exe = "ffmpeg"
    cmd = [exe, "-v", "error", "-i", str(video), "-vf",
           "select='%s'" % picks, "-vsync", "0",
           str(out_dir / "o_%02d.png"), "-y"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        print("  [X] ffmpeg 失败：%s" % (r.stderr or "")[:300])
        return []
    return sorted(str(p) for p in out_dir.glob("o_*.png"))


def main() -> int:
    srv = load_server()
    cells = slice_triptych_cells()
    print(">>> 拼图三格已切出：%s" % ", ".join(pathlib.Path(c).name for c in cells))

    new_frames = {name: str(VERIFY / name) for _, _, name in SEGMENTS}

    print(">>> 抽旧片帧（_00003_，确认错误版）用于「改没改」对照")
    old_frames = ffmpeg_frames(OLD_VIDEO, OLD_FRAMES,
                               "eq(n\\,12)+eq(n\\,60)+eq(n\\,108)")
    print("    旧帧 %d 张：%s" % (len(old_frames), [pathlib.Path(p).name for p in old_frames]))

    targets = list(new_frames.values()) + cells + old_frames
    print(">>> 提取特征（共 %d 张）" % len(targets))
    info = ask(srv, targets)

    ok = True
    for seg, cell_idx, fname in SEGMENTS:
        npath = new_frames[fname]
        cpath = cells[cell_idx]
        nf = info.get(str(pathlib.Path(npath)), (None, 0))[0]
        cf = info.get(str(pathlib.Path(cpath)), (None, 0))[0]
        print("=" * 78)
        print("%s  帧=%s  参照=拼图第 %d 格" % (seg, fname, cell_idx + 1))
        if nf is None or cf is None:
            print("  [X] 缺人脸（帧=%s 参照=%s）→ 不可判" % (nf is not None, cf is not None))
            ok = False
            continue

        # ① 与「自己那格」比（同域）
        s_self = cos(nf["embedding"], cf["embedding"])
        # ② 与「其他两格」比（同域），看自己是否排第一
        others = []
        for j in range(3):
            if j == cell_idx:
                continue
            of2 = info.get(str(pathlib.Path(cells[j])), (None, 0))[0]
            if of2 is not None:
                others.append((cos(nf["embedding"], of2["embedding"]), j))
        best_other = max(others) if others else (float("-inf"), -1)
        # ③ 与旧片同格帧比（看改没改）
        s_old = None
        if cell_idx < len(old_frames):
            of = info.get(str(pathlib.Path(old_frames[cell_idx])), (None, 0))[0]
            if of is not None:
                s_old = cos(nf["embedding"], of["embedding"])

        print("  人脸：脸高=%dpx det=%.2f" % (nf["face_px_h"], nf["det_score"]))
        print("  ① 与「自己那格」同域余弦 = %.4f" % s_self)
        print("  ② 与「其他格」最高同域余弦 = %.4f（第 %d 格）" % (best_other[0], best_other[1] + 1))
        if s_old is not None:
            print("  ③ 与「旧片同段帧」余弦 = %.4f  %s" % (
                s_old, "（越接近 1 说明画面没变 ⇒ 修法无效）" if s_old > 0.65 else "（已明显改变）"))
        win = s_self > best_other[0]
        print("  -> 判据①「对自己那格得分最高」= %s；脸高%s" % (
            "成立" if win else "不成立",
            "达标" if nf["face_px_h"] >= 250 else "偏小(仅参考)"))
        if not win:
            ok = False

    print("=" * 78)
    print("总判定：%s" % ("三段同域归组全部成立" if ok else "存在不成立项，需人工看图"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
