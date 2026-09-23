# -*- coding: utf-8 -*-
"""镜 125 段 3 构图修正：把「脸部大特写 + 头顶被裁」改为「头顶完整进画」。

## 为什么要后期修

段 3 的源定妆照只有「脸 + 单肩」（右下角带新华网水印，无法往下裁到胸口），
即使换成 AI 重绘的 35% 中景参考图、原文里写死"不要裁掉额头"、并换了 seed，
H3 R2V 仍**稳定地**把人脸推到画幅 500+px、头顶出界（实测 554/540/513px，脸顶 −9%~−7%）。
这是模型对"肖像类单参考图"的取景偏好，文字与参考图都压不住。

## 做法

不再和模型搏斗，改为**后期把画面缩小 + 下移**：
  * 缩放 `SCALE`（默认 0.86）⇒ 脸高 554 → ~476px（画幅 78%）；
  * 整体下移 `OFFSET_Y`（默认 0.06 画幅高）⇒ 头顶露出，顶部黑边用深灰填充；
  * 左右按比例居中，避免人物被横向拉伸。

只动这一段的像素，不改另两段；输出写回 `_seg125` 供 concat 使用。

用法：
    py -3.10 OUTPUT/_fix_125_seg3_framing.py --dry      # 只看参数
    py -3.10 OUTPUT/_fix_125_seg3_framing.py            # 出图
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SEG_DIR = ROOT / "OUTPUT" / "05_classroom_night" / "video" / "_seg125"
BAR = (24, 24, 24)
SCALE = 0.86          # 内容缩放（越小头顶留白越多）
OFFSET_Y = 0.06       # 内容下移比例（画幅高）
FIT_W = 1056
FIT_H = 608


def newest(pat: str, exclude: str = "") -> pathlib.Path | None:
    """★ 不用 `Path.glob()`：Windows 上对 `_seg125` 这类下划线开头目录会返回空。
    改用 `iterdir()` + startswith 过滤。
    """
    pre = pat[:-1] if pat.endswith("*") else pat
    cands = [p for p in SEG_DIR.iterdir()
             if p.is_file() and p.name.startswith(pre)
             and p.name.endswith(".mp4")
             and (not exclude or exclude not in p.name)]
    return max(cands, key=lambda p: p.stat().st_mtime) if cands else None


def main() -> int:
    dry = "--dry" in sys.argv
    src = newest("125_c_zns_", exclude="_fixed_")
    if not src:
        print("[X] 找不到 125_c_zns_*.mp4")
        return 2
    print("源段：%s" % src.name)

    cw, ch = int(FIT_W * SCALE), int(FIT_H * SCALE)
    # 居中横向、纵向下移
    x = (FIT_W - cw) // 2
    y = int(FIT_H * OFFSET_Y)
    vf = ("scale=%d:%d:force_original_aspect_ratio=increase,"
          "crop=%d:%d,"
          "pad=%d:%d:%d:%d:color=0x181818,setsar=1"
          % (cw, ch, cw, ch, FIT_W, FIT_H, x, y))
    print("滤镜：%s" % vf)
    if dry:
        print("[dry] 未出图。")
        return 0

    out = SEG_DIR / "125_c_zns_fixed_.mp4"
    # ★ 音频必须与画面**严格等长**：源段音轨 2.325s vs 画面 2.333s（短 8ms），
    #   若用 `-c:a copy` 直接带走，concat + tpad 补长后音轨会比画面短，
    #   整条链的余量会累积到末镜 —— 实测导致镜 126 出现 +120ms 偏移
    #   （基线要求逐镜 |偏移| ≤ 10ms）。
    #   修法：`apad` + `-shortest` 让音轨以静音补齐到画面长度。
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(src),
           "-vf", vf + ",fps=24",
           # ★ `-r 24` 必须显式写，否则帧率会被标成 289/12，与其余 125 镜不一致
           "-r", "24",
           "-af", "apad",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "128k", "-ar", "32000", "-ac", "2",
           "-shortest", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        print("[X] ffmpeg 失败：%s" % (r.stderr or "")[:400])
        return 3
    print("[out] %s  %.1f KB" % (out, out.stat().st_size / 1024.0))

    # 抽 3 帧检脸验收
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "comfyui_mcp_server", ROOT / "mcp_server" / "comfyui_mcp_server.py")
    srv = importlib.util.module_from_spec(spec)
    sys.modules["comfyui_mcp_server"] = srv
    spec.loader.exec_module(srv)

    tmp = ROOT / "OUTPUT" / "_shot125_final"
    tmp.mkdir(parents=True, exist_ok=True)
    ok_all = True
    for i, ts in enumerate((0.7, 1.4, 2.0), 1):
        f = tmp / ("fixed_probe_%d.jpg" % i)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "%.2f" % ts,
                        "-i", str(out), "-frames:v", "1", "-q:v", "2",
                        str(f)], capture_output=True)
        res = srv.face_feature(paths=str(f), include_embedding=False,
                               reembed_px=0, det_size=1024, min_det_score=0.3)
        d = json.loads(res) if isinstance(res, str) else res
        blob = d.get("face_json") or {}
        data = json.loads(blob) if isinstance(blob, str) else blob
        im = (data.get("images") or [{}])[0]
        faces = im.get("faces") or []
        if not faces:
            print("  @%.1fs 未检出脸" % ts)
            ok_all = False
            continue
        fh = faces[0]["face_px_h"]
        top = faces[0]["bbox"][1] / float(im["height"])
        good = top >= 0.04
        ok_all = ok_all and good
        print("  @%.1fs 脸高=%dpx 脸顶=%.0f%%  %s" % (
            ts, fh, top * 100, "OK 头顶进画" if good else "!! 仍贴边"))
    return 0 if ok_all else 4


if __name__ == "__main__":
    raise SystemExit(main())
