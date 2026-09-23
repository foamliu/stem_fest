# -*- coding: utf-8 -*-
"""合成「三人合影拼图」参考图 —— 镜 125 的 R2V `ref1`。

## 为什么要重做（诊断链，2026-09-21 复核）

镜 125（`OUTPUT/_diag_act5_finale.py:434`）原为 **T2V 无参考图**（`ref1=None, ref2=None`），
三帧历史人物全靠 prompt 文字描述临时编脸，实测三段中**两段错**：

| 段 | prompt 原文 | 实得 | 问题 |
|---|---|---|---|
| 1 黄继光 | "1950 年代志愿军冬装、戴红星军帽的年轻战士" | 对 | 靠镜 73/74/75 的模型记忆 |
| 2 袁隆平 | "穿**中山装的中年男性**" | 错（圆脸浮肿中年人） | **"中年"与设定冲突** |
| 3 钟南山 | "戴眼镜**老年男性**" | 错（白发苍苍泛化老人） | **违反 README「不要画苍老」** |

★ 真正的病因**不是"缺参考图"**，而是 **prompt 用文字描述年龄，且描述与定妆照设定相冲突**
   （`README.md:515`「分镜里的性格/印象描述不可当外形依据」的同类错误；关键约束见 `README.md:521`）：
   * 袁隆平 1961 年实际 31 岁，**定妆照是青年形象**（"21–25 岁"读数**符合设定**，并非 bug）；
   * 钟南山 2020 年 83 岁但**本人显年轻，明令不要画苍老**。

因此修法 ＝ **把"正确设定的脸"作为像素级参考图喂给 R2V**，不再用文字描述年龄。

## 为什么是"纯 PIL 拼版"而不是 `image_edit_longcat`

`ASSETS/README.md:178` 明文：
> 不要再用 `image_edit_longcat` 合并合影 —— 实测**有些转后身份失真**。

所以本脚本**只做像素级裁剪/缩放/拼版，不经任何生成模型** —— 拼图里每一张脸都是定妆照原像素，
R2V 拿到的三格参考各是各的脸。H3 R2V 参考图上限 2 张，塞不下三个人 ⇒ 竖排三格合成 1 张。

## 每格做法

  * 用 InsightFace 检出主脸 bbox；
  * 按 bbox 中心裁一块 3:4 竖幅（含头+肩），**锁定"脸高/格高 ≈ 0.52"**（保证脸高 >=250px，README §6.5）；
  * 裁框**避开右下角水印区**（钟南山源图带「新华网 WWW.NEWS.CN」，是 P0 风险）；
  * 格间黑色分隔条 + 左上角序号（1/2/3），便于 prompt 用 `<Picture 1>` 指代三段。

用法：py -3.10 OUTPUT/_make_125_triptych.py
产物：OUTPUT/_shot125_refs/ref_three_heroes_v01.png
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVER = ROOT / "mcp_server" / "comfyui_mcp_server.py"
OUT_DIR = ROOT / "OUTPUT" / "_shot125_refs"

# (序号, 人物, 定妆照, 该图是否带右下角水印需规避)
SOURCES = [
    (1, "huang_jiguang", "ASSETS/CHARACTERS/05_huang_jiguang/huang_jiguang_closeup_v01.png", False),
    (2, "yuan_longping", "ASSETS/CHARACTERS/06_yuan_longping/yuan_longping_hero_v01.png", False),
    (3, "zhong_nanshan", "ASSETS/CHARACTERS/07_zhong_nanshan/zhong_nanshan_hero_v01.png", True),
]

CELL_W, CELL_H = 704, 768          # 单格尺寸 → 704×2352 竖排
FACE_RATIO = 0.52                  # 脸高占格高比例
FACE_CY = 0.36                     # 脸中心落在格高的该比例处（下方留肩）
BAR = 24                           # 格间黑色分隔条
WM_KEEPOUT = 0.72                  # 带水印图：裁框下边界不得超过原图高 * 该值


def load_server():
    spec = importlib.util.spec_from_file_location("comfyui_mcp_server", SERVER)
    srv = importlib.util.module_from_spec(spec)
    sys.modules["comfyui_mcp_server"] = srv
    spec.loader.exec_module(srv)
    return srv


def face_boxes(srv, paths):
    """一次取回所有人脸 bbox（用 reembed 关掉，只要检测结果）。"""
    res = srv.face_feature(paths="\n".join(paths), include_embedding=False,
                           reembed_px=0, output_dir=str(OUT_DIR))
    if isinstance(res, str):
        res = json.loads(res)
    blob = res.get("face_json") or "{}"
    data = json.loads(blob) if isinstance(blob, str) else blob
    out = {}
    for img in data.get("images", []):
        faces = img.get("faces") or []
        out[pathlib.Path(img["file"]).name] = (img, faces[0] if faces else None)
    return out


def crop_cell(src: Image.Image, face, idx: int, has_wm: bool):
    """按人脸 bbox 裁一块锁定脸高的竖幅（头+肩）。返回 (格图, 说明)。

    源图太小时裁框会超出原图边界（PIL 会补黑边）⇒ 先把源图整体放大到
    "裁框能落在图内"，再裁。纯重采样，不改变像素内容。
    """
    x1, y1, x2, y2 = face["bbox"]
    fh = float(face["face_px_h"] or (y2 - y1) or 1.0)
    scale = (CELL_H * FACE_RATIO) / fh
    cw, ch = CELL_W / scale, CELL_H / scale           # 原图坐标下的裁框尺寸

    # 裁框必须能落在图内；带水印图还要满足下边界 <= WM_KEEPOUT
    need_h = ch if not has_wm else ch / WM_KEEPOUT
    need_w = cw
    up = max(1.0, need_w / src.width, need_h / src.height)
    if up > 1.0001:
        src = src.resize((int(round(src.width * up)), int(round(src.height * up))),
                         Image.LANCZOS)
        k = up
        x1, y1, x2, y2 = (v * k for v in (x1, y1, x2, y2))
        cw, ch = cw * k, ch * k

    # 源图横向不够时，把裁框宽度压到图宽（只缩小视野，不改脸高 → 脸占比更大）
    cw = min(cw, float(src.width))
    ch = cw * (CELL_H / float(CELL_W))

    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    # ★ 脸在格内的垂直位置：**脸中心落在格高 FACE_CY 处**（下方留肩）。
    #   注意：这里必须用「脸 bbox 中心」而非 bbox 顶边，否则不同脸型的脸会高低不一，
    #   且可能让下巴被格下边界切掉（2026-09-21 实测：格 3 曾切残，face_feature 检不到）。
    top = cy - ch * FACE_CY
    left = cx - cw / 2.0

    max_top = src.height - ch
    if has_wm:
        # 水印在右下角 ⇒ 裁框下边界压到 WM_KEEPOUT 以上，避免水印进参考图
        max_top = src.height * WM_KEEPOUT - ch
    left = max(0.0, min(left, src.width - cw))
    top = max(0.0, min(top, max_top))
    box = (int(round(left)), int(round(top)),
           int(round(left + cw)), int(round(top + ch)))
    cell = src.crop(box).resize((CELL_W, CELL_H), Image.LANCZOS)

    d = ImageDraw.Draw(cell)
    d.rectangle([0, 0, 54, 54], fill=(0, 0, 0))
    d.text((20, 16), str(idx), fill=(255, 255, 255))
    return cell, "up=%.2f box=%s" % (up, box)


def main() -> int:
    srv = load_server()
    abs_paths = [str(ROOT / rel) for _, _, rel, _ in SOURCES]
    info = face_boxes(srv, abs_paths)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cells = []
    for idx, who, rel, has_wm in SOURCES:
        name = pathlib.Path(rel).name
        img_meta, face = info.get(name, ({}, None))
        if face is None:
            print("[ERR] %s 未检出人脸，无法锚定裁框" % name)
            return 2
        src = Image.open(ROOT / rel).convert("RGB")
        cell, note = crop_cell(src, face, idx, has_wm)
        cells.append(cell)
        print("[cell %d] %-16s src=%s face_px_h=%s det=%.2f %s wm_avoid=%s" % (
            idx, who, src.size, face["face_px_h"], face["det_score"], note, has_wm))

    total_h = CELL_H * 3 + BAR * 2
    canvas = Image.new("RGB", (CELL_W, total_h), (0, 0, 0))
    for i, cell in enumerate(cells):
        canvas.paste(cell, (0, i * (CELL_H + BAR)))

    out = OUT_DIR / "ref_three_heroes_v01.png"
    canvas.save(out, "PNG")
    print("\n[out] %s  %dx%d  %.1f KB" % (out, canvas.width, canvas.height,
                                          out.stat().st_size / 1024.0))

    # ── 自检：整张拼图必须检出 3 张脸，且每张落在自己那一格里 ──
    print("[verify] 回读拼图检脸 ...")
    res = srv.face_feature(paths=str(out), include_embedding=False, reembed_px=0,
                           det_size=640)
    if isinstance(res, str):
        res = json.loads(res)
    blob = res.get("face_json") or "{}"
    data = json.loads(blob) if isinstance(blob, str) else blob
    im = (data.get("images") or [{}])[0]
    faces = im.get("faces") or []
    stride = CELL_H + BAR
    print("[verify] 检出 %d 张脸（应=3）" % im.get("face_count", 0))
    ok = (len(faces) == 3)
    for f in faces:
        cy = (f["bbox"][1] + f["bbox"][3]) / 2.0
        cell = int(cy // stride)
        rel = (cy - cell * stride) / float(CELL_H)
        good = (0 <= cell <= 2) and (0.15 <= rel <= 0.70) and f["face_px_h"] >= 250
        ok = ok and good
        print("  y=%.0f h=%dpx det=%.2f -> 第 %d 格、格内 %.0f%%  %s" % (
            cy, f["face_px_h"], f["det_score"], cell + 1, rel * 100,
            "OK" if good else "!! 位置/尺寸异常"))
    if not ok:
        print("[verify] 拼图自检未通过 —— R2V 前请先修裁框参数")
        return 3
    print("[verify] 拼图自检通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
