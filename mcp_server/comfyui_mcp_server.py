#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ComfyUI MCP Server — 《如愿·看见》（stem_fest）制作流水线

把 ``workflows/`` 下的 9 条 ComfyUI 工作流封装为 MCP 工具，供 Cline 直接调用：

  🖼️ 图像层
    z_image_turbo_t2i        Z-Image-Turbo 文生图.json
    image_edit_longcat       Image Edit (LongCat Image Edit).json   (角色一致性·唯一图生图工具)
  🎬 视频层
    video_minimax_h3_i2v     video_minimax_h3_i2v.json   ⭐ 首选
    video_minimax_h3_r2v     video_minimax_h3_r2v.json   ⭐ 角色锁定
    video_minimax_h3_t2v     video_minimax_h3_t2v.json
  🎵 音频层
    qwen3_tts                Qwen3-TTS 语音合成.json
    ace_step_t2audio         ACE-Step 1.5 文生音频.json
  🔎 识别层
    qwen3_asr                Qwen3-ASR 语音识别.json   (配音核对：mp4 音轨 → 文字)
    image_segmentation_sam3  Image Segmentation (SAM3).json
                             (开放词汇检测/分割；图片或**视频抽帧**逐帧体检)

  🧰 辅助：comfyui_status / comfyui_upload_image / comfyui_get_result

启动（stdio，由 Cline 拉起）::

    python mcp_server/comfyui_mcp_server.py

环境变量::

    COMFYUI_URL       默认 http://127.0.0.1:8188
    COMFYUI_ROOT      默认自动探测（E:/code/ComfyUI、E:/ComfyUI …）
    MCP_OUTPUT_ROOT   默认 <项目根>/OUTPUT

设计约束（源自 README §13 与 LESSONS_LEARNED.md）：
  * 参数注入按 ``class_type`` 匹配节点，与现有 scripts/ 保持一致
  * 参考图先经 ``/upload/image`` 注册到 ComfyUI input 才能被 LoadImage 识别
  * TTS 的 ``custom_speaker_name`` 必须留空，否则 ValueError
  * Minimax H3 在 16GB VRAM 下 megapixels 上限 0.6，超过必 OOM
"""

from __future__ import annotations

import json
import os
import random
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

# ── 路径与全局配置 ────────────────────────────────────────────────
SERVER_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SERVER_DIR.parent
WORKFLOW_DIR = PROJECT_ROOT / "workflows"
OUTPUT_ROOT = Path(os.environ.get("MCP_OUTPUT_ROOT") or (PROJECT_ROOT / "OUTPUT"))
COMFYUI_URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")

# workflow key → 文件名（工作流以 API Format JSON 存放于 workflows/）
WORKFLOWS: dict[str, str] = {
    "t2i": "Z-Image-Turbo 文生图.json",
    "image_edit": "Image Edit (LongCat Image Edit).json",
    # 🚫 "firered": 已于 2026-09-13 **整体移除**（5/5 次运行产出纯黑图，零成功率）
    "tts": "Qwen3-TTS 语音合成.json",
    "ace": "ACE-Step 1.5 文生音频.json",
    "asr": "Qwen3-ASR 语音识别.json",
    "sam3": "Image Segmentation (SAM3).json",
    "h3_i2v": "video_minimax_h3_i2v.json",
    "h3_r2v": "video_minimax_h3_r2v.json",
    "h3_t2v": "video_minimax_h3_t2v.json",
}

# Qwen3-TTS 预置音色（填非预置名 → ValueError，见 README §13.7）
TTS_SPEAKERS = [
    "Vivian",      # 年轻女声，28-35 岁女性
    "Dylan",       # 沉稳男声，30-40 岁男性
    "Serena",      # 柔和女声，AI 系统语音感
    "aiden",
    "eric",
    "ryan",
    "ono_anna",
    "sohee",
    "uncle_fu",
]

# ResolutionSelector 常用取值（H3 视频工作流）
ASPECT_RATIOS = [
    "16:9 (Widescreen)",
    "9:16 (Portrait)",
    "1:1 (Square)",
    "4:3 (Standard)",
    "3:4 (Portrait)",
    "3:2 (Photo)",
    "2:3 (Portrait)",
    "21:9 (Cinematic)",
]

MAX_SEED = 2 ** 48

_COMFYUI_ROOT_CACHE: Optional[Path] = None

mcp = FastMCP("comfyui-drama-tools", log_level="WARNING")

# ── 通用小工具 ────────────────────────────────────────────────────
def _dump(obj: Any) -> str:
    """统一 JSON 输出（中文不转义，便于 Cline 阅读）。"""
    return json.dumps(obj, ensure_ascii=False, indent=2)


def _err(msg: str) -> str:
    return _dump({"ok": False, "error": str(msg)})


def _now() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _pick_seed(seed: int) -> int:
    """seed < 0 → 随机；否则原样使用（同角色固定 seed 保证音色一致性）。"""
    return int(seed) if int(seed) >= 0 else random.randrange(0, MAX_SEED)


def _resolve_output_dir(output_dir: Optional[str], default_sub: str) -> Path:
    if output_dir:
        p = Path(output_dir)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
    else:
        p = OUTPUT_ROOT / default_sub
    p.mkdir(parents=True, exist_ok=True)
    return p


def _detect_comfyui_root() -> Path:
    """定位 ComfyUI 根目录（/upload/image 回退与本地文件回退用）。

    优先级：
      1. ``COMFYUI_ROOT`` 环境变量
      2. 候选目录中 output/ 命中服务端 ``/internal/files/output`` 报出的文件名
      3. 候选目录中 input/ 存在者
    结果缓存，避免重复探测。
    """
    global _COMFYUI_ROOT_CACHE
    if _COMFYUI_ROOT_CACHE is not None:
        return _COMFYUI_ROOT_CACHE

    env = os.environ.get("COMFYUI_ROOT")
    if env and Path(env).is_dir():
        _COMFYUI_ROOT_CACHE = Path(env)
        return _COMFYUI_ROOT_CACHE

    candidates = [
        Path("E:/code/ComfyUI"),
        Path("E:/ComfyUI"),
        Path("E:/ComfyUI_windows_portable/ComfyUI"),
        Path.home() / "ComfyUI",
    ]
    candidates = [c for c in candidates if c.is_dir()]

    # 用服务端报出的输出文件名反查哪个目录才是真正的 ComfyUI
    try:
        listed = _http_json("/internal/files/output", method="GET", timeout=8)
        names = {str(item).rsplit(" [", 1)[0] for item in listed} if isinstance(listed, list) else set()
        if names:
            for c in candidates:
                out = c / "output"
                if out.is_dir() and any((out / n).exists() for n in list(names)[:40]):
                    _COMFYUI_ROOT_CACHE = c
                    return _COMFYUI_ROOT_CACHE
    except Exception:
        pass

    for c in candidates:
        if (c / "input").is_dir():
            _COMFYUI_ROOT_CACHE = c
            return _COMFYUI_ROOT_CACHE

    _COMFYUI_ROOT_CACHE = Path(env) if env else Path("E:/code/ComfyUI")
    return _COMFYUI_ROOT_CACHE


def _comfyui_input_dir() -> Path:
    d = _detect_comfyui_root() / "input"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _comfyui_output_dir() -> Path:
    return _detect_comfyui_root() / "output"


# ── ComfyUI REST API 封装 ─────────────────────────────────────────
def _http_json(endpoint: str, payload: Optional[dict] = None,
               method: str = "POST", timeout: int = 60) -> dict:
    url = f"{COMFYUI_URL}{endpoint}"
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")[:2000]
        except Exception:
            pass
        raise RuntimeError(f"ComfyUI HTTP {e.code} {e.reason} @ {endpoint}\n{detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"无法连接 ComfyUI ({COMFYUI_URL})：{e.reason}。请先启动 ComfyUI。"
        ) from e


def _load_workflow(key: str) -> dict:
    path = WORKFLOW_DIR / WORKFLOWS[key]
    if not path.exists():
        raise FileNotFoundError(f"工作流不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _queue(wf: dict) -> str:
    result = _http_json("/prompt",
                        {"prompt": wf, "client_id": f"mcp_{uuid.uuid4().hex[:8]}"})
    pid = result.get("prompt_id", "")
    if not pid:
        raise RuntimeError(f"提交失败: {result}")
    return pid


def _wait(pid: str, timeout: int) -> dict:
    """轮询 /history/{prompt_id} 直到完成，返回该 history entry。"""
    start = time.time()
    while time.time() - start < timeout:
        data = _http_json(f"/history/{pid}", method="GET", timeout=30)
        entry = data.get(pid)
        if entry:
            status = (entry.get("status") or {}).get("status_str", "")
            if status == "error":
                msgs = (entry.get("status") or {}).get("messages") or []
                raise RuntimeError(
                    "ComfyUI 执行失败: " + json.dumps(msgs, ensure_ascii=False)[:1500]
                )
            if entry.get("outputs") or status == "success":
                return entry
        time.sleep(3)
    raise TimeoutError(
        f"等待超时 ({timeout}s)：prompt_id={pid} 仍在执行，"
        f'可稍后调用 comfyui_get_result(prompt_id="{pid}") 取回结果'
    )

# ── 参考图上传（LoadImage 只能读取已注册到 ComfyUI input 的文件）──
def _upload_image(image_path: str, target_name: Optional[str] = None) -> str:
    """把本地图像上传到 ComfyUI input，返回 LoadImage 可用的文件名。"""
    src = Path(image_path)
    if not src.is_absolute():
        src = PROJECT_ROOT / src
    if not src.exists():
        raise FileNotFoundError(f"输入图像不存在: {src}")

    # 中文/空格文件名在部分环境下会让 LoadImage 失败 → 归一化为 ASCII 名
    fname = target_name or src.name
    if any(ord(ch) > 127 for ch in fname) or " " in fname:
        fname = f"mcp_ref_{uuid.uuid4().hex[:8]}{src.suffix.lower() or '.png'}"

    boundary = "----ComfyUIMCPBoundary" + uuid.uuid4().hex
    parts = [
        f"--{boundary}\r\n".encode("utf-8"),
        (
            f'Content-Disposition: form-data; name="image"; filename="{fname}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode("utf-8"),
        src.read_bytes(),
        f"\r\n--{boundary}--\r\n".encode("utf-8"),
    ]
    req = urllib.request.Request(
        f"{COMFYUI_URL}/upload/image",
        data=b"".join(parts),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8", errors="replace"))
        name = result.get("name", fname)
        sub = result.get("subfolder", "")
        return f"{sub}/{name}" if sub else name
    except Exception as e:
        # API 不可用时回退为直接拷贝到 input 目录
        dst = _comfyui_input_dir() / fname
        try:
            shutil.copy2(src, dst)
            return fname
        except Exception:
            raise RuntimeError(f"上传参考图失败: {e}") from e


# ── 输出收集与下载 ────────────────────────────────────────────────
def _collect_outputs(history_entry: dict) -> list[dict]:
    """从 history 中收集输出文件（兼容 images / gifs / videos / audio / text）。"""
    outputs: list[dict] = []
    for node_id, nd in (history_entry.get("outputs") or {}).items():
        if not isinstance(nd, dict):
            continue
        for key in ("images", "gifs", "videos", "audio"):
            for item in nd.get(key) or []:
                if isinstance(item, dict) and item.get("filename"):
                    outputs.append({
                        "filename": item["filename"],
                        "subfolder": item.get("subfolder", "") or "",
                        "type": item.get("type", "output"),
                        "node_id": node_id,
                    })
        # SaveText 节点：文字结果可能内联在 history 里，也可能落成 .txt 文件
        for item in nd.get("text") or []:
            if isinstance(item, str):
                outputs.append({
                    "filename": "",
                    "subfolder": "",
                    "type": "text_inline",
                    "node_id": node_id,
                    "text": item,
                })
    return outputs


def _download_file(item: dict, dst: Path) -> Optional[str]:
    """通过 /view 下载（失败回退文件系统拷贝）。成功返回绝对路径。"""
    fname = item["filename"]
    sub = item.get("subfolder", "") or ""
    ftype = item.get("type", "output")
    params = urllib.parse.urlencode({"filename": fname, "subfolder": sub, "type": ftype})
    try:
        req = urllib.request.Request(f"{COMFYUI_URL}/view?{params}")
        with urllib.request.urlopen(req, timeout=180) as resp:
            blob = resp.read()
        if len(blob) > 100:
            dst.write_bytes(blob)
            return str(dst)
    except Exception:
        pass

    out_root = _comfyui_output_dir()
    for candidate in (out_root / sub / fname, out_root / "temp" / fname, out_root / fname):
        if candidate.exists():
            shutil.copy2(candidate, dst)
            return str(dst)
    return None


def _save_outputs(history_entry: dict, out_dir: Path) -> list[dict]:
    items = _collect_outputs(history_entry)
    # 有正式输出（type=output）时丢弃预览节点产生的临时文件，避免重复下载
    if any(i["type"] == "output" for i in items):
        items = [i for i in items if i["type"] == "output"]
    saved: list[dict] = []
    for item in items:
        # 内联文字（SaveText）：直接返回，不落盘
        if item["type"] == "text_inline":
            saved.append({"path": None, "filename": None,
                          "text": item.get("text", "")})
            continue
        dst = out_dir / item["filename"]
        path = _download_file(item, dst)
        if path:
            entry = {
                "path": path,
                "filename": item["filename"],
                "size_kb": round(dst.stat().st_size / 1024, 1),
            }
            # .txt 结果顺手读出来，便于直接看到转写文本
            if dst.suffix.lower() == ".txt":
                try:
                    entry["text"] = dst.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass
            saved.append(entry)
    return saved


def _run(wf: dict, out_dir: Path, wait: bool, timeout: int, meta: dict) -> str:
    """提交 → （等待）→ 下载，返回统一 JSON 结果。"""
    prompt_id = _queue(wf)
    base = {"ok": True, "prompt_id": prompt_id, "comfyui": COMFYUI_URL, **meta}
    if not wait:
        return _dump({**base, "status": "queued",
                      "hint": "用 comfyui_get_result(prompt_id) 取回结果"})
    t0 = time.time()
    history = _wait(prompt_id, timeout)
    saved = _save_outputs(history, out_dir)
    return _dump({
        **base,
        "status": "success" if saved else "no_output_files",
        "elapsed_sec": round(time.time() - t0, 1),
        "output_dir": str(out_dir),
        "files": saved,
    })


def _preview_to_save(wf: dict, filename_prefix: str) -> None:
    """PreviewImage(临时文件) → SaveImage(正式输出)，保证产物落在 output/ 可下载。

    与 README §13.5 记录的 SaveImage + filename_prefix 用法一致。
    """
    for node in wf.values():
        if node.get("class_type") == "PreviewImage":
            node["class_type"] = "SaveImage"
            node["inputs"] = {"images": node["inputs"]["images"],
                              "filename_prefix": filename_prefix}


def _set_inputs(wf: dict, class_type: str, **values: Any) -> int:
    """按 class_type 注入参数，返回命中节点数。"""
    hits = 0
    for node in wf.values():
        if node.get("class_type") == class_type:
            node.setdefault("inputs", {}).update(values)
            hits += 1
    return hits

# ══════════════════════════════════════════════════════════════════
# 🖼️ 图像层
# ══════════════════════════════════════════════════════════════════
@mcp.tool()
def z_image_turbo_t2i(
    prompt: str,
    negative_prompt: str = "",
    width: int = 1024,
    height: int = 1280,
    seed: int = -1,
    steps: int = 8,
    cfg: float = 1.0,
    batch_size: int = 1,
    filename_prefix: Optional[str] = None,
    output_dir: Optional[str] = None,
    wait: bool = True,
    timeout_seconds: int = 1800,
) -> str:
    """Z-Image-Turbo 文生图（工作流 `Z-Image-Turbo 文生图.json`，国产首选 T2I）。

    用于生成场景图、道具、UI、群像等**不需要角色一致性**的镜头；
    需要引用定妆照保持角色一致时改用 `image_edit_longcat`。

    Args:
        prompt: 画面描述（英文效果最佳）。
        negative_prompt: 负面词。该工作流负面条件被 ConditioningZeroOut 置零，
            因此负面词以 "Do NOT include: ..." 追加到正向提示词
            （与根目录 `README.md` §7 的做法一致）。
        width: 宽（像素）。横屏 1280 / 竖屏 720 / 方图 1024。
        height: 高（像素）。横屏 720 / 竖屏 1280 / 方图 1024。
        seed: 随机种子；-1 表示随机（会回传实际使用的 seed 便于复现）。
        steps: 采样步数（Turbo 模型推荐 8）。
        cfg: 引导强度（Turbo 推荐 1.0）。
        batch_size: 一次生成张数。
        filename_prefix: 保存前缀，默认 `t2i/<时间戳>`。
        output_dir: 输出目录（绝对路径或相对项目根），默认 `OUTPUT/t2i`。
        wait: True 阻塞直到完成并下载；False 只提交，返回 prompt_id。
        timeout_seconds: 等待超时秒数。

    Returns:
        JSON 字符串：{ok, status, prompt_id, seed, files:[{path,size_kb}], ...}
    """
    try:
        seed_used = _pick_seed(seed)
        wf = _load_workflow("t2i")

        full_prompt = prompt.strip()
        if negative_prompt.strip():
            full_prompt += f"\n\nDo NOT include: {negative_prompt.strip()}"

        _set_inputs(wf, "CLIPTextEncode", text=full_prompt)
        _set_inputs(wf, "EmptySD3LatentImage",
                    width=int(width), height=int(height), batch_size=int(batch_size))
        _set_inputs(wf, "KSampler", seed=seed_used, steps=int(steps), cfg=float(cfg))

        prefix = filename_prefix or f"t2i/{_now()}"
        _preview_to_save(wf, prefix)

        out_dir = _resolve_output_dir(output_dir, "t2i")
        return _run(wf, out_dir, wait, timeout_seconds, {
            "tool": "z_image_turbo_t2i",
            "workflow": WORKFLOWS["t2i"],
            "seed": seed_used,
            "width": int(width),
            "height": int(height),
        })
    except Exception as e:
        return _err(f"z_image_turbo_t2i 失败: {e}")


@mcp.tool()
def image_edit_longcat(
    prompt: str,
    image: str,
    negative_prompt: str = "",
    seed: int = -1,
    megapixels: float = 1.0,
    guidance: float = 4.5,
    steps: int = 50,
    cfg: float = 4.5,
    filename_prefix: Optional[str] = None,
    output_dir: Optional[str] = None,
    wait: bool = True,
    timeout_seconds: int = 1800,
) -> str:
    """Image Edit · LongCat 图像编辑（工作流 `Image Edit (LongCat Image Edit).json`）。

    **角色一致性关键工具**（LESSONS_LEARNED #6）：把角色定妆照作为 `image` 输入，
    再用 `prompt` 描述新场景，即可让同一角色出现在不同镜头而脸不变。
    例：定妆照 `ASSETS/CHARACTERS/01_liu_siqi/liu_siqi_hero_v01.png`
    + "同一位初中女生坐在傍晚的教室课桌前，暖金色天光，中景"。

    Args:
        prompt: 编辑/重绘描述（如"同一位女性在地铁车厢里观察人群"）。
        image: 参考图路径（定妆照），自动上传到 ComfyUI input。
        negative_prompt: 负面描述。
        seed: 随机种子；-1 = 随机（同角色建议固定 seed）。
        megapixels: 输出总像素（百万）。1920×1920 ≈ 3.69；默认 1.0。
        guidance: FluxGuidance 强度（工作流默认 4.5）。
        steps: 采样步数（工作流默认 50）。
        cfg: KSampler cfg（工作流默认 4.5）。
        filename_prefix: 保存前缀，默认 `image_edit/<时间戳>`。
        output_dir: 输出目录，默认 `OUTPUT/image_edit`。
        wait: True 阻塞等待；False 仅提交。
        timeout_seconds: 等待超时秒数。

    Returns:
        JSON 字符串：{ok, status, prompt_id, seed, reference_image, files, ...}
    """
    try:
        seed_used = _pick_seed(seed)
        ref_name = _upload_image(image)
        wf = _load_workflow("image_edit")

        _set_inputs(wf, "LoadImage", image=ref_name)
        _set_inputs(wf, "ImageScaleToTotalPixels", megapixels=float(megapixels))
        _set_inputs(wf, "FluxGuidance", guidance=float(guidance))
        _set_inputs(wf, "KSampler", seed=seed_used, steps=int(steps), cfg=float(cfg))

        # 两个 TextEncodeQwenImageEdit：node id 小的为正向，另一个为负向
        encoders = sorted(
            ((nid, n) for nid, n in wf.items()
             if n.get("class_type") == "TextEncodeQwenImageEdit"),
            key=lambda x: x[0],
        )
        if encoders:
            encoders[0][1]["inputs"]["prompt"] = prompt.strip()
        if len(encoders) > 1:
            encoders[1][1]["inputs"]["prompt"] = negative_prompt.strip()

        prefix = filename_prefix or f"image_edit/{_now()}"
        _preview_to_save(wf, prefix)

        out_dir = _resolve_output_dir(output_dir, "image_edit")
        return _run(wf, out_dir, wait, timeout_seconds, {
            "tool": "image_edit_longcat",
            "workflow": WORKFLOWS["image_edit"],
            "seed": seed_used,
            "reference_image": ref_name,
        })
    except Exception as e:
        return _err(f"image_edit_longcat 失败: {e}")

# ══════════════════════════════════════════════════════════════════
# 🚫 图像层 · FireRed-Image-Edit 1.1 —— **已于 2026-09-13 整体移除**
# ══════════════════════════════════════════════════════════════════
# 移除依据（美术方 2026-09-13 指示 + 运行时证据）：该模型在本机 **5 次运行 5 张纯黑图**，
# **零成功率**，且 ComfyUI 每次均报 `success`（静默失败）：
#   v01  40 步 / CFG 4        1360×768   9.3 KB   mean=0.0
#   v12  40 步 / CFG 4        1672×936  10.7 KB   mean=0.0（耗时 26.5 min）
#   v13   8 步 / CFG 1        1672×936  10.7 KB   mean=0.0（Lightning）
#   extra08_young_soldier_v03_nolp   880×1176   7.9 KB   mean=0.0
#   extra11_soldiers_v01_nolp       1360×768   8.0 KB   mean=0.0
# ⇒ 工具与 `WORKFLOWS["firered"]` 注册项一并删除（不再出现在工具列表中）。
# ⇒ **本项目图生图（角色一致性）唯一工具：`image_edit_longcat`**，不做 A/B 比较。
# 历史证据保留在 `ASSETS/CHARACTERS/01_liu_siqi/README.md` §6.5，工作流文件
# `workflows/image_firered_image_edit1_1.json` 仅作留档、无任何工具指向它。



# ══════════════════════════════════════════════════════════════════
# 🎵 音频层
# ══════════════════════════════════════════════════════════════════
@mcp.tool()
def qwen3_tts(
    text: str,
    speaker: str = "Vivian",
    instruct: str = "",
    seed: int = -1,
    language: str = "Auto",
    audio_format: str = "flac",
    max_new_tokens: int = 2048,
    filename_prefix: Optional[str] = None,
    output_dir: Optional[str] = None,
    wait: bool = True,
    timeout_seconds: int = 1800,
) -> str:
    """Qwen3-TTS 语音合成（工作流 `Qwen3-TTS 语音合成.json`，输出 FLAC/MP3）。

    用于角色配音 / 旁白。**同一角色固定 `speaker` + `seed` 才能跨集保持一致音色**
    （README §13.7、§13.11）。

    Args:
        text: 要合成的台词/旁白，可用 `⏸️（稍作停顿）` 等中文提示控制节奏。
        speaker: 预置音色，可选 Vivian（年轻女声）/ Dylan（沉稳男声）/
            Serena（柔和女声·AI 系统感）/ aiden / eric / ryan / ono_anna /
            sohee / uncle_fu。
        instruct: 音色与表演指令，如 "28岁女性，北京口音，自嘲节奏感。"。
        seed: 随机种子；-1 = 随机。**同角色务必固定 seed**。
        language: 语言，默认 "Auto"。
        audio_format: 输出格式，flac（无损）或 mp3。
        max_new_tokens: 生成长度上限（长台词可调大）。
        filename_prefix: 保存前缀，默认 `tts/<时间戳>`。
        output_dir: 输出目录，默认 `OUTPUT/tts`。
        wait: True 阻塞等待并下载；False 仅提交。
        timeout_seconds: 等待超时秒数（TTS 约 1-2 分钟）。

    Returns:
        JSON 字符串：{ok, status, prompt_id, seed, speaker, files, ...}

    Note:
        `custom_speaker_name` 不是自定义名字字段，而是音色 mixing 的 speaker 名
        列表，填非预置名会导致 ValueError —— 本工具始终置空。
    """
    try:
        if speaker not in TTS_SPEAKERS:
            return _err(
                f"非法 speaker='{speaker}'。该字段只接受预置音色："
                f"{', '.join(TTS_SPEAKERS)}（填自定义名字会触发 ValueError）"
            )
        seed_used = _pick_seed(seed)
        wf = _load_workflow("tts")

        _set_inputs(
            wf, "Qwen3CustomVoice",
            text=text,
            language=language,
            speaker=speaker,
            seed=seed_used,
            instruct=instruct,
            custom_speaker_name="",      # ⚠️ 必须为空
            max_new_tokens=int(max_new_tokens),
        )
        prefix = filename_prefix or f"tts/{_now()}"
        _set_inputs(wf, "SaveAudioAdvanced", filename_prefix=prefix,
                    format=audio_format)

        out_dir = _resolve_output_dir(output_dir, "tts")
        return _run(wf, out_dir, wait, timeout_seconds, {
            "tool": "qwen3_tts",
            "workflow": WORKFLOWS["tts"],
            "seed": seed_used,
            "speaker": speaker,
            "audio_format": audio_format,
            "text_chars": len(text),
        })
    except Exception as e:
        return _err(f"qwen3_tts 失败: {e}")

@mcp.tool()
def ace_step_t2audio(
    tags: str,
    lyrics: str = "",
    duration: float = 60.0,
    seed: int = -1,
    bpm: int = -1,
    keyscale: str = "",
    language: str = "en",
    timesignature: str = "4",
    steps: int = 8,
    cfg: float = 1.0,
    cfg_scale: float = 2.0,
    temperature: float = 0.85,
    top_p: float = 0.9,
    audio_format: str = "mp3",
    filename_prefix: Optional[str] = None,
    output_dir: Optional[str] = None,
    wait: bool = True,
    timeout_seconds: int = 1800,
) -> str:
    """ACE-Step 1.5 文生音频（工作流 `ACE-Step 1.5 文生音频.json`，输出 MP3）。

    用于配乐 BGM / 合成音效。遵循 `ASSETS/配乐提示词规格.md` 的
    **Caption（氛围总谱）+ Lyrics（分镜脚本）双管齐下**法则。

    Args:
        tags: 音乐风格/情绪总谱，如
            "solo piano, contemplative, sparse notes, minor key, 60 BPM"。
        lyrics: 歌词/结构脚本，可含 `[Intro][Verse][Chorus][Bridge][Outro]`
            段落标记；**纯器乐留空字符串**。
        duration: 时长（秒）。
        seed: 随机种子；-1 = 随机。
        bpm: 每分钟节拍数；-1 表示沿用工作流默认值。
        keyscale: 调式，如 "C major" / "E minor"；空则沿用默认。
        language: 歌词语言（en / zh ...）。
        timesignature: 拍号，默认 "4"。
        steps: 采样步数（Turbo 推荐 8）。
        cfg: KSampler cfg。
        cfg_scale: 文本编码器的 cfg_scale。
        temperature: 生成温度。
        top_p: 核采样阈值。
        audio_format: 输出格式，mp3（默认）/ flac / wav。
        filename_prefix: 保存前缀，默认 `bgm/<时间戳>`。
        output_dir: 输出目录，默认 `OUTPUT/bgm`。
        wait: True 阻塞等待并下载；False 仅提交。
        timeout_seconds: 等待超时秒数。

    Returns:
        JSON 字符串：{ok, status, prompt_id, seed, duration, files, ...}
    """
    try:
        seed_used = _pick_seed(seed)
        wf = _load_workflow("ace")

        encoder_payload: dict[str, Any] = {
            "tags": tags,
            "lyrics": lyrics,
            "seed": seed_used,
            "language": language,
            "timesignature": timesignature,
            "generate_audio_codes": True,
            "cfg_scale": float(cfg_scale),
            "temperature": float(temperature),
            "top_p": float(top_p),
        }
        if int(bpm) > 0:
            encoder_payload["bpm"] = int(bpm)
        if keyscale.strip():
            encoder_payload["keyscale"] = keyscale.strip()
        _set_inputs(wf, "TextEncodeAceStepAudio1.5", **encoder_payload)

        # 时长由 PrimitiveFloat("Song Duration") 同时驱动 Latent 与 TextEncode
        _set_inputs(wf, "PrimitiveFloat", value=float(duration))
        _set_inputs(wf, "KSampler", seed=seed_used, steps=int(steps), cfg=float(cfg))

        prefix = filename_prefix or f"bgm/{_now()}"
        _set_inputs(wf, "SaveAudioAdvanced", filename_prefix=prefix,
                    format=audio_format)

        out_dir = _resolve_output_dir(output_dir, "bgm")
        return _run(wf, out_dir, wait, timeout_seconds, {
            "tool": "ace_step_t2audio",
            "workflow": WORKFLOWS["ace"],
            "seed": seed_used,
            "duration": float(duration),
            "audio_format": audio_format,
        })
    except Exception as e:
        return _err(f"ace_step_t2audio 失败: {e}")

# ══════════════════════════════════════════════════════════════════
# 🎬 视频层 · Minimax H3（画面 + 环境音联合生成）
# ══════════════════════════════════════════════════════════════════
def _apply_h3_common(wf: dict, duration: float, seed: int, aspect_ratio: str,
                     megapixels: float, steps: int, filename_prefix: str) -> None:
    """H3 三条工作流共有的参数注入。"""
    _set_inputs(wf, "PrimitiveFloat", value=float(duration))   # Float (duration)
    _set_inputs(wf, "RandomNoise", noise_seed=seed)
    _set_inputs(wf, "ResolutionSelector",
                aspect_ratio=aspect_ratio, megapixels=float(megapixels))
    _set_inputs(wf, "BasicScheduler", steps=int(steps))
    _set_inputs(wf, "SaveVideo", filename_prefix=filename_prefix)


def _h3_meta(tool: str, key: str, duration: float, seed: int,
             aspect_ratio: str, megapixels: float) -> dict:
    return {
        "tool": tool,
        "workflow": WORKFLOWS[key],
        "seed": seed,
        "duration_sec": float(duration),
        "aspect_ratio": aspect_ratio,
        "megapixels": float(megapixels),
        "audio_note": "H3 音画联合生成，成片已含环境音；角色配音用 qwen3_tts、配乐用 ace_step_t2audio 后期三层混音。",
    }


@mcp.tool()
def video_minimax_h3_i2v(
    prompt: str,
    image: str,
    duration: float = 5.0,
    seed: int = -1,
    aspect_ratio: str = "16:9 (Widescreen)",
    megapixels: float = 0.6,
    steps: int = 20,
    filename_prefix: Optional[str] = None,
    output_dir: Optional[str] = None,
    wait: bool = True,
    timeout_seconds: int = 1800,
) -> str:
    """Minimax H3 图生视频 I2V ⭐（工作流 `video_minimax_h3_i2v.json`，视频生成首选）。

    以一张首帧图 + 运动描述生成带环境音的视频片段（音画天然同步，README §13.3）。

    Args:
        prompt: 分镜描述——建议写清 SHOT 段落、镜头运动与 Audio 环境音，例：
            "SHOT 1: 中景，她放下咖啡杯并转头看向窗外… Audio: 办公室底噪、键盘声"。
        image: 首帧图路径（通常来自 `z_image_turbo_t2i` / `image_edit_longcat`
            的输出），自动上传到 ComfyUI input。
        duration: 时长（秒）。工作流内部换算为 24fps 并对齐 17 帧倍数。
        seed: 随机种子；-1 = 随机。
        aspect_ratio: 画幅，如 "16:9 (Widescreen)" / "9:16 (Portrait)"。
        megapixels: 目标像素。⚠️ 16GB VRAM 上限 **0.6**（≈1056×608）；
            调到 0.92(720p) 必定 torch.OutOfMemoryError（LESSONS_LEARNED #10）。
            要 1080p 请生成后超分。
        steps: 采样步数（默认 20）。
        filename_prefix: 保存前缀，默认 `video/<时间戳>_h3_i2v`。
        output_dir: 输出目录，默认 `OUTPUT/video`。
        wait: True 阻塞等待（单条 5-15 分钟）；False 仅提交。
        timeout_seconds: 等待超时秒数。

    Returns:
        JSON 字符串：{ok, status, prompt_id, seed, duration_sec, files, ...}
    """
    try:
        seed_used = _pick_seed(seed)
        first_frame = _upload_image(image)
        wf = _load_workflow("h3_i2v")

        _set_inputs(wf, "LoadImage", image=first_frame)
        _set_inputs(wf, "MiniMaxH3ImageToVideo", prompt=prompt)

        prefix = filename_prefix or f"video/{_now()}_h3_i2v"
        _apply_h3_common(wf, duration, seed_used, aspect_ratio, megapixels, steps, prefix)

        out_dir = _resolve_output_dir(output_dir, "video")
        return _run(wf, out_dir, wait, timeout_seconds, {
            **_h3_meta("video_minimax_h3_i2v", "h3_i2v", duration,
                       seed_used, aspect_ratio, megapixels),
            "first_frame": first_frame,
        })
    except Exception as e:
        return _err(f"video_minimax_h3_i2v 失败: {e}")

@mcp.tool()
def video_minimax_h3_r2v(
    prompt: str,
    ref_image_1: str,
    ref_image_2: Optional[str] = None,
    duration: float = 5.0,
    seed: int = -1,
    aspect_ratio: str = "16:9 (Widescreen)",
    megapixels: float = 0.4,
    steps: int = 20,
    filename_prefix: Optional[str] = None,
    output_dir: Optional[str] = None,
    wait: bool = True,
    timeout_seconds: int = 1800,
) -> str:
    """Minimax H3 参考图生视频 R2V ⭐（工作流 `video_minimax_h3_r2v.json`，角色锁定）。

    最多 2 张参考图（定妆照/场景图），在 prompt 中用 `<Picture 1>` / `<Picture 2>`
    引用，适合**多镜头角色一致性**与风格化打斗分镜（README §13.4）。

    Args:
        prompt: 分镜描述，用 `<Picture 1>`、`<Picture 2>` 指代参考图，
            用 `CUT 1:` / `CUT 2:` 划分段落，并写明 Audio 描述。
        ref_image_1: 参考图 1（对应 `<Picture 1>`），自动上传。
        ref_image_2: 参考图 2（对应 `<Picture 2>`）；**不传则复用参考图 1**。
        duration: 时长（秒）。
        seed: 随机种子；-1 = 随机。
        aspect_ratio: 画幅。
        megapixels: 目标像素。R2V 双参考图显存占用更高，默认 0.4；
            16GB VRAM 下不建议超过 0.6。
        steps: 采样步数。
        filename_prefix: 保存前缀，默认 `video/<时间戳>_h3_r2v`。
        output_dir: 输出目录，默认 `OUTPUT/video`。
        wait: True 阻塞等待；False 仅提交。
        timeout_seconds: 等待超时秒数。

    Returns:
        JSON 字符串：{ok, status, prompt_id, seed, duration_sec, files, ...}
    """
    try:
        seed_used = _pick_seed(seed)
        ref1 = _upload_image(ref_image_1)
        ref2 = _upload_image(ref_image_2) if ref_image_2 else ref1
        wf = _load_workflow("h3_r2v")

        _set_inputs(wf, "PrimitiveStringMultiline", value=prompt)

        # LoadImage 节点：137 → ref_image_0，139 → ref_image_1（按 node id 升序）
        load_nodes = sorted(
            (nid for nid, n in wf.items() if n.get("class_type") == "LoadImage"),
            key=lambda x: int(x),
        )
        if len(load_nodes) >= 1:
            wf[load_nodes[0]]["inputs"]["image"] = ref1
        if len(load_nodes) >= 2:
            wf[load_nodes[1]]["inputs"]["image"] = ref2

        prefix = filename_prefix or f"video/{_now()}_h3_r2v"
        _apply_h3_common(wf, duration, seed_used, aspect_ratio, megapixels, steps, prefix)

        out_dir = _resolve_output_dir(output_dir, "video")
        return _run(wf, out_dir, wait, timeout_seconds, {
            **_h3_meta("video_minimax_h3_r2v", "h3_r2v", duration,
                       seed_used, aspect_ratio, megapixels),
            "ref_image_1": ref1,
            "ref_image_2": ref2,
        })
    except Exception as e:
        return _err(f"video_minimax_h3_r2v 失败: {e}")

@mcp.tool()
def video_minimax_h3_t2v(
    prompt: str,
    duration: float = 5.0,
    seed: int = -1,
    aspect_ratio: str = "16:9 (Widescreen)",
    megapixels: float = 0.4,
    steps: int = 20,
    filename_prefix: Optional[str] = None,
    output_dir: Optional[str] = None,
    wait: bool = True,
    timeout_seconds: int = 1800,
) -> str:
    """Minimax H3 文生视频 T2V（工作流 `video_minimax_h3_t2v.json`）。

    无需参考图，直接由文本生成带环境音的视频，适合纯文本转视频 /
    UI 动画 / 无角色动态镜头（README §13.5）。

    Args:
        prompt: 分镜脚本，建议含镜头类型、故事板时间轴与 Audio 描述，例：
            "[0s-1.5s] Shot 1: 高侧角度… Audio: 风声、脚步、低频配乐"。
        duration: 时长（秒）。
        seed: 随机种子；-1 = 随机。
        aspect_ratio: 画幅。
        megapixels: 目标像素；16GB VRAM 建议 ≤ 0.6（默认 0.4）。
        steps: 采样步数。
        filename_prefix: 保存前缀，默认 `video/<时间戳>_h3_t2v`。
        output_dir: 输出目录，默认 `OUTPUT/video`。
        wait: True 阻塞等待；False 仅提交。
        timeout_seconds: 等待超时秒数。

    Returns:
        JSON 字符串：{ok, status, prompt_id, seed, duration_sec, files, ...}
    """
    try:
        seed_used = _pick_seed(seed)
        wf = _load_workflow("h3_t2v")

        _set_inputs(wf, "MiniMaxH3ImageToVideo", prompt=prompt)

        prefix = filename_prefix or f"video/{_now()}_h3_t2v"
        _apply_h3_common(wf, duration, seed_used, aspect_ratio, megapixels, steps, prefix)

        out_dir = _resolve_output_dir(output_dir, "video")
        return _run(wf, out_dir, wait, timeout_seconds,
                    _h3_meta("video_minimax_h3_t2v", "h3_t2v", duration,
                             seed_used, aspect_ratio, megapixels))
    except Exception as e:
        return _err(f"video_minimax_h3_t2v 失败: {e}")

# ══════════════════════════════════════════════════════════════════
# 🧰 辅助工具
# ══════════════════════════════════════════════════════════════════
@mcp.tool()
def comfyui_status() -> str:
    """检查 ComfyUI 服务状态、队列、可用工作流与默认输出目录。

    在批量生成前先调用它确认服务在线（否则所有生成工具都会报连接失败）。

    Returns:
        JSON 字符串：{ok, comfyui, reachable, system, queue, workflows, output_root}
    """
    info: dict[str, Any] = {
        "comfyui": COMFYUI_URL,
        "project_root": str(PROJECT_ROOT),
        "workflow_dir": str(WORKFLOW_DIR),
        "output_root": str(OUTPUT_ROOT),
        "comfyui_root": str(_detect_comfyui_root()),
        "workflows": {},
    }
    for key, fname in WORKFLOWS.items():
        info["workflows"][key] = {
            "file": fname,
            "exists": (WORKFLOW_DIR / fname).exists(),
        }
    try:
        stats = _http_json("/system_stats", method="GET", timeout=10)
        queue = _http_json("/queue", method="GET", timeout=10)
        info["reachable"] = True
        info["system"] = {
            "comfyui_version": stats.get("system", {}).get("comfyui_version"),
            "python_version": stats.get("system", {}).get("python_version"),
            "os": stats.get("system", {}).get("os"),
            "devices": [
                {
                    "name": d.get("name"),
                    "vram_total_gb": round((d.get("vram_total") or 0) / 1024 ** 3, 1),
                    "vram_free_gb": round((d.get("vram_free") or 0) / 1024 ** 3, 1),
                }
                for d in stats.get("devices", [])
            ],
        }
        info["queue"] = {
            "running": len(queue.get("queue_running", [])),
            "pending": len(queue.get("queue_pending", [])),
        }
    except Exception as e:
        info["reachable"] = False
        info["error"] = str(e)
        info["hint"] = "启动 ComfyUI 后重试：python main.py --listen 127.0.0.1 --port 8188"
    return _dump({"ok": info.get("reachable", False), **info})


@mcp.tool()
def comfyui_upload_image(image_path: str, target_name: Optional[str] = None) -> str:
    """把本地图像上传/注册到 ComfyUI input 目录，供 LoadImage 使用。

    当需要先确认参考图可用，或想复用一个上传后的文件名时可单独调用。

    Args:
        image_path: 本地图像路径（绝对路径或相对项目根）。
        target_name: 在 ComfyUI input 中的目标文件名；留空自动生成
            （含中文或空格的文件名会被自动改为 ASCII 名）。

    Returns:
        JSON 字符串：{ok, uploaded_as, comfyui_input_dir}
    """
    try:
        name = _upload_image(image_path, target_name)
        return _dump({
            "ok": True,
            "uploaded_as": name,
            "comfyui_input_dir": str(_comfyui_input_dir()),
        })
    except Exception as e:
        return _err(f"comfyui_upload_image 失败: {e}")


@mcp.tool()
def comfyui_get_result(prompt_id: str, output_dir: Optional[str] = None) -> str:
    """按 prompt_id 取回异步任务结果（配合 `wait=False` 使用）。

    Args:
        prompt_id: 提交任务时返回的 prompt_id。
        output_dir: 下载目录，默认 `OUTPUT/mcp_fetch`。

    Returns:
        JSON 字符串：{ok, status, prompt_id, files, ...}
    """
    try:
        history = _http_json(f"/history/{prompt_id}", method="GET", timeout=30)
        entry = history.get(prompt_id)
        if not entry:
            return _dump({"ok": False, "status": "not_found",
                          "prompt_id": prompt_id,
                          "hint": "任务可能仍在执行或 prompt_id 有误，可稍后重试。"})
        status = (entry.get("status") or {}).get("status_str", "")
        out_dir = _resolve_output_dir(output_dir, "mcp_fetch")
        saved = _save_outputs(entry, out_dir)
        return _dump({
            "ok": bool(saved) or status == "success",
            "status": status or ("success" if saved else "unknown"),
            "prompt_id": prompt_id,
            "output_dir": str(out_dir),
            "files": saved,
        })
    except Exception as e:
        return _err(f"comfyui_get_result 失败: {e}")


# ══════════════════════════════════════════════════════════════════
# 🔎 音频层 · Qwen3-ASR（语音识别 / 配音核对）
# ══════════════════════════════════════════════════════════════════
AUDIO_EXT = {".wav", ".flac", ".mp3", ".m4a", ".ogg", ".opus", ".aac"}


def _upload_audio(audio_path: str, target_name: Optional[str] = None) -> str:
    """把本地音频注册到 ComfyUI input，返回 LoadAudio 可用的文件名。

    与 `_upload_image` 同构：中文/空格名会破坏引用，统一归一化为 ASCII。
    """
    src = Path(audio_path)
    if not src.is_absolute():
        src = PROJECT_ROOT / src
    if not src.exists():
        raise FileNotFoundError(f"输入音频不存在: {src}")

    fname = target_name or src.name
    if any(ord(ch) > 127 for ch in fname) or " " in fname:
        fname = f"mcp_audio_{uuid.uuid4().hex[:8]}{src.suffix.lower() or '.wav'}"

    boundary = "----ComfyUIMCPAudio" + uuid.uuid4().hex
    parts = [
        f"--{boundary}\r\n".encode("utf-8"),
        (
            f'Content-Disposition: form-data; name="image"; filename="{fname}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode("utf-8"),
        src.read_bytes(),
        f"\r\n--{boundary}--\r\n".encode("utf-8"),
    ]
    req = urllib.request.Request(
        f"{COMFYUI_URL}/upload/image",
        data=b"".join(parts),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8", errors="replace"))
        name = result.get("name", fname)
        sub = result.get("subfolder", "")
        return f"{sub}/{name}" if sub else name
    except Exception as e:
        dst = _comfyui_input_dir() / fname
        try:
            shutil.copy2(src, dst)
            return fname
        except Exception:
            raise RuntimeError(f"上传音频失败: {e}") from e


def _extract_audio(media_path: Path) -> Path:
    """从 mp4/mov 抽音轨为 16 kHz 单声道 wav（ComfyUI LoadAudio 只吃音频容器）。

    已有音频文件则原样返回。依赖系统 ffmpeg。
    """
    if media_path.suffix.lower() in AUDIO_EXT:
        return media_path
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError(
            f"输入是视频（{media_path.suffix}）但系统里找不到 ffmpeg ⇒ 无法抽音轨。"
            "请安装 ffmpeg 或直接传入音频文件。"
        )
    dst = media_path.with_name(media_path.stem + "_asr16k.wav")
    proc = subprocess.run(
        [ffmpeg, "-y", "-v", "error", "-i", str(media_path),
         "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", str(dst)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0 or not dst.exists():
        raise RuntimeError(f"抽音轨失败: {(proc.stderr or '')[:400]}")
    return dst


@mcp.tool()
def qwen3_asr(
    audio: str,
    language: str = "auto",
    context: str = "",
    return_timestamps: bool = False,
    precision: str = "bf16",
    local_model_path: str = "",
    filename_prefix: Optional[str] = None,
    output_dir: Optional[str] = None,
    wait: bool = True,
    timeout_seconds: int = 900,
) -> str:
    """Qwen3-ASR 语音识别（工作流 `Qwen3-ASR 语音识别.json`）—— 用来**核对配音/台词**。

    ★ 典型用途：H3 生成的片段**配音对不对**，靠耳朵听不可靠 ⇒ 用本工具把 mp4 的
    音轨转成文字，与 `storyboard.md` 的台词原文逐字比对（含中文方言/口音，52 语种）。

    Args:
        audio: 音频或视频路径（**可直接传 .mp4**，内部用 ffmpeg 抽 16 kHz 单声道音轨），
            相对路径按项目根解析，自动上传到 ComfyUI input。
        language: 语言，默认 "auto"（自动识别）；可强制如 "Chinese" / "English"。
        context: 上下文提示（帮助模型认专有名词/人名），默认空。
        return_timestamps: True 时输出带时间戳（需模型支持）。
        precision: 模型精度，默认 bf16（16GB 显存下推荐）。
        local_model_path: 本地模型目录；留空则用工作流里的 `repo_id`
            （`Qwen/Qwen3-ASR-0.6B`，需已下载到 `models/Qwen3-ASR/`）。
        filename_prefix: 转写文本的保存前缀，默认 `asr/<时间戳>`。
        output_dir: 输出目录，默认 `OUTPUT/asr`。
        wait: True 阻塞等待并返回转写文本；False 仅提交。
        timeout_seconds: 等待超时秒数。

    Returns:
        JSON 字符串：{ok, status, prompt_id, text, files, ...}；
        `text` 即转写结果（内联返回，无需再打开文件）。
    """
    try:
        src = Path(audio)
        if not src.is_absolute():
            src = PROJECT_ROOT / src
        if not src.exists():
            return _err(f"输入不存在: {src}")

        # 视频 → 先抽音轨
        media = _extract_audio(src)
        audio_name = _upload_audio(str(media))
        if media != src:
            try:
                media.unlink()      # 清理临时 wav
            except Exception:
                pass

        wf = _load_workflow("asr")

        # LoadAudio.audio ← 上传后的文件名
        _set_inputs(wf, "LoadAudio", audio=audio_name)

        # Qwen3ASRTranscribe：language / context / return_timestamps
        _set_inputs(wf, "Qwen3ASRTranscribe",
                    language=language,
                    context=context,
                    return_timestamps=bool(return_timestamps))

        # Qwen3ASRLoader：精度 / 本地模型路径（留空沿用 repo_id）
        loader_payload: dict[str, Any] = {"precision": precision}
        if local_model_path.strip():
            loader_payload["local_model_path"] = local_model_path.strip()
        _set_inputs(wf, "Qwen3ASRLoader", **loader_payload)

        prefix = filename_prefix or f"asr/{_now()}"
        _set_inputs(wf, "SaveText", filename_prefix=prefix, format="txt")

        out_dir = _resolve_output_dir(output_dir, "asr")
        result = json.loads(_run(wf, out_dir, wait, timeout_seconds, {
            "tool": "qwen3_asr",
            "workflow": WORKFLOWS["asr"],
            "audio": audio_name,
            "language": language,
        }))

        # 把转写文本提到顶层，便于直接阅读
        if isinstance(result, dict) and result.get("files"):
            texts = [f.get("text") for f in result["files"] if f.get("text")]
            if texts:
                result["text"] = "\n".join(texts).strip()
        return _dump(result)
    except Exception as e:
        return _err(f"qwen3_asr 失败: {e}")


# ══════════════════════════════════════════════════════════════════
# 🔍 检测层 · SAM3（开放词汇检测 / 分割；图片 or 视频抽帧体检）
# ══════════════════════════════════════════════════════════════════
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}

# SAM3 文本类别的写法（出处：`E:\code\ComfyUI\comfy\text_encoders\sam3_clip.py::_parse_prompts`）：
#   逗号分隔可写多类别，`:N` 指定该类最多检出几个 —— 例 "paper plane:2, boy, sky"；
#   CLIP 上限 32 token，括号会被剥掉（不做权重），请用最直白的英文名词。


def _probe_duration(media: Path) -> float:
    """读媒体时长（秒）：ffprobe 优先，回退解析 ffmpeg stderr；失败返回 0.0。

    口径与 `OUTPUT/_visual_review.py::probe_dur()` 一致。
    """
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        proc = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(media)],
            capture_output=True, text=True,
        )
        try:
            return float((proc.stdout or "").strip())
        except Exception:
            pass
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        proc = subprocess.run([ffmpeg, "-i", str(media)], capture_output=True, text=True)
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr or "")
        if m:
            return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    return 0.0


def _extract_frames(video: Path, count: int, start: float, end: float,
                    out_dir: Path) -> list[dict]:
    """从视频**均匀抽帧**（默认避开首尾各 8%，防转场黑帧），返回 [{path, time_sec}]。

    时间戳口径与 `OUTPUT/_visual_review.py::grab()` 一致；依赖系统 ffmpeg。
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError(
            f"输入是视频（{video.suffix}）但系统里找不到 ffmpeg ⇒ 无法抽帧。"
            "请安装 ffmpeg 或直接传图片。"
        )
    total = _probe_duration(video)
    if total <= 0:
        raise RuntimeError(f"读不到视频时长（ffprobe / ffmpeg 均失败）: {video}")
    lo = max(0.0, float(start))
    hi = min(float(end) if float(end) > 0 else total, total)
    if hi <= lo:
        raise RuntimeError(
            f"抽帧区间非法：start={lo:.3f}s ≥ end={hi:.3f}s（视频时长 {total:.3f}s）"
        )

    frames_dir = out_dir / "_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    # 帧图名保持 ASCII，避免 ComfyUI 上传时被改名后无法辨认
    stem = "".join(ch for ch in video.stem if ord(ch) < 128)[:32] or "video"
    frames: list[dict] = []
    for i in range(count):
        frac = (0.08 + 0.84 * i / (count - 1)) if count > 1 else 0.5
        t = lo + (hi - lo) * frac
        dst = frames_dir / f"{stem}_f{i:02d}.jpg"
        subprocess.run(
            [ffmpeg, "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video),
             "-frames:v", "1", "-q:v", "2", str(dst)],
            capture_output=True,
        )
        if dst.exists() and dst.stat().st_size > 0:
            frames.append({"path": str(dst), "time_sec": round(t, 3)})
    if not frames:
        raise RuntimeError(f"抽帧失败（0 帧）: {video}")
    return frames


def _mask_coverage(png_path: str) -> Optional[float]:
    """掩膜图的**非零像素占比**（0-1）—— `0` 表示这一帧没检出目标。

    ★ 这是 SAM3 的验收指标（`README.md` §6.1 #6 的口径：产物必须查像素，
    不能只看 ComfyUI 报 success）。用 ffmpeg 解码成灰度裸流后数非零字节，
    **不引入 PIL / numpy 依赖**；ffmpeg 不可用时返回 None（只少一个数值，不影响产物）。
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    try:
        proc = subprocess.run(
            [ffmpeg, "-v", "error", "-i", str(png_path),
             "-f", "rawvideo", "-pix_fmt", "gray", "-"],
            capture_output=True,
        )
        raw = proc.stdout or b""
        if not raw:
            return None
        return round((len(raw) - raw.count(0)) / len(raw), 6)
    except Exception:
        return None


def _sam3_apply(wf: dict, image_name: str, prompt: str, threshold: float,
                refine_iterations: int, individual_masks: bool,
                ckpt_name: str, prefix: str) -> None:
    """注入 SAM3 工作流，并把「边界框图 / 掩膜叠加图 / 原始掩膜图」落成**正式输出**。

    原工作流只有 `PreviewImage` + `ImageAndMaskPreview`（都是临时预览文件），
    直接提交会被 `_save_outputs` 当预览丢掉 ⇒ 这里补 `SaveImage` / `MaskToImage` 节点。

    ⚠️ `individual_masks=True` 时**不挂原始掩膜分支**：0 检出时掩膜批次为空，
    `MaskToImage → SaveImage` 会在 `images[0].shape` 上抛 IndexError（`nodes.py::SaveImage`）。
    """
    _set_inputs(wf, "LoadImage", image=image_name)
    if prompt.strip():
        _set_inputs(wf, "CLIPTextEncode", text=prompt.strip())
    _set_inputs(wf, "SAM3_Detect",
                threshold=float(threshold),
                refine_iterations=int(refine_iterations),
                individual_masks=bool(individual_masks))
    if ckpt_name.strip():
        _set_inputs(wf, "CheckpointLoaderSimple", ckpt_name=ckpt_name.strip())

    # ① 边界框图：PreviewImage（temp）→ SaveImage（output）
    _preview_to_save(wf, f"{prefix}_bbox")

    # ② 掩膜叠加图：复用 ImageAndMaskPreview 的 composite 输出（它自己只出临时预览）
    overlays = sorted(k for k, n in wf.items()
                      if n.get("class_type") == "ImageAndMaskPreview")
    if overlays:
        wf["mcp_save_overlay"] = {
            "class_type": "SaveImage",
            "inputs": {"images": [overlays[0], 0],
                       "filename_prefix": f"{prefix}_overlay"},
        }

    # ③ 原始掩膜（黑底白图）：供抠图 / 掩膜面积体检
    detects = sorted(k for k, n in wf.items() if n.get("class_type") == "SAM3_Detect")
    if detects and not individual_masks:
        wf["mcp_mask_to_image"] = {
            "class_type": "MaskToImage",
            "inputs": {"mask": [detects[0], 0]},
        }
        wf["mcp_save_mask"] = {
            "class_type": "SaveImage",
            "inputs": {"images": ["mcp_mask_to_image", 0],
                       "filename_prefix": f"{prefix}_mask"},
        }


@mcp.tool()
def image_segmentation_sam3(
    image: str,
    prompt: str = "",
    threshold: float = 0.5,
    refine_iterations: int = 2,
    individual_masks: bool = False,
    ckpt_name: str = "",
    video_frames: int = 4,
    video_start: float = 0.0,
    video_end: float = 0.0,
    filename_prefix: Optional[str] = None,
    output_dir: Optional[str] = None,
    wait: bool = True,
    timeout_seconds: int = 600,
) -> str:
    """SAM3 开放词汇检测 / 分割（工作流 `Image Segmentation (SAM3).json`）。

    ★ **"画面里到底有没有某样东西、它占多大"这类只能看图才能回答的问题，用它。**
    给一张图（**或一段视频**）＋一个**文字**类别，返回三件套：
    边界框图（`_bbox`）/ 掩膜叠加图（`_overlay`）/ 原始掩膜图（`_mask`）；
    视频输入会均匀抽帧、逐帧检测，并回传每帧**掩膜覆盖率**
    ⇒ 可用来验收"这一镜有没有纸飞机 / 目标是不是太小 / 第几帧出现"。

    典型用途：
      * H3 出片后抽查某镜是否真的出现了剧本要求的道具（纸飞机、稻穗、书本…）
      * 量目标在画面里的**占比**（`mask_coverage`），判断"太小看不见 / 被遮挡"
      * 拿掩膜 PNG 供后续抠图、局部重绘

    Args:
        image: 输入图片路径；**也可以是视频**（.mp4/.mov/.mkv/.webm/.avi/.m4v，
            内部用 ffmpeg 均匀抽帧，见 `video_frames`）。相对路径按项目根解析。
        prompt: 要找的东西（**英文效果最好**）。逗号分隔可写多类别，`:N` 指定该类最多
            检出几个（例 `"paper plane:2, boy, sky"`）；CLIP 上限 32 token、括号会被
            剥掉（不做权重），请用最直白的英文名词。留空 → 沿用工作流里写死的 "book"。
        threshold: 检测阈值 0-1，越低越灵敏（默认 0.5）。漏检就降、误检就升。
        refine_iterations: 掩膜精修迭代次数 0-5（默认 2；0 = 只用粗掩膜，最快）。
        individual_masks: True 时每个目标一张掩膜；⚠️ 该模式**不额外保存原始掩膜图**
            （0 检出时掩膜批次为空会让 SaveImage 报错），只给框图与叠加图。
        ckpt_name: 自定义 SAM3 权重名；留空沿用工作流的 `sam3.1_multiplex_fp16.safetensors`。
        video_frames: 输入是视频时的抽帧数 1-8（默认 4；均匀分布并避开首尾 8%）。
        video_start: 抽帧起始秒（默认 0 = 片头）。
        video_end: 抽帧结束秒；0 = 到片尾。
        filename_prefix: 保存前缀，默认 `sam3/<时间戳>`；视频模式自动带帧号 `_f00`，
            三类产物另加 `_bbox` / `_overlay` / `_mask` 后缀。
        output_dir: 输出目录，默认 `OUTPUT/sam3`（抽出的帧图落在其 `_frames/` 子目录）。
        wait: True 阻塞到完成并下载；False 只提交（视频模式逐帧提交、回传多个 prompt_id）。
        timeout_seconds: **每帧**的等待超时秒数（SAM3 检测通常数十秒）。

    Returns:
        JSON 字符串：{ok, mode, prompt, frames:[{time_sec, mask_coverage, detected, files}],
        summary:{frames, detected_frames, max_mask_coverage, mean_mask_coverage}}；
        单图模式另把 prompt_id / files / mask_coverage / detected 提到顶层。
        `mask_coverage` = 掩膜占画面比例，**0 = 这帧没检出目标**（None = 无 ffmpeg 无法体检）。
    """
    try:
        src = Path(image)
        if not src.is_absolute():
            src = PROJECT_ROOT / src
        if not src.exists():
            return _err(f"输入不存在: {src}")
        if not 0.0 <= float(threshold) <= 1.0:
            return _err(f"threshold 必须在 0-1 之间，收到 {threshold}")
        if not 0 <= int(refine_iterations) <= 5:
            return _err(f"refine_iterations 必须在 0-5 之间，收到 {refine_iterations}")
        if not 1 <= int(video_frames) <= 8:
            return _err(f"video_frames 必须在 1-8 之间，收到 {video_frames}")

        out_dir = _resolve_output_dir(output_dir, "sam3")
        base = filename_prefix or f"sam3/{_now()}"
        is_video = src.suffix.lower() in VIDEO_EXT
        frames = (
            _extract_frames(src, int(video_frames), video_start, video_end, out_dir)
            if is_video else [{"path": str(src), "time_sec": None}]
        )

        meta_common = {
            "tool": "image_segmentation_sam3",
            "workflow": WORKFLOWS["sam3"],
            "mode": "video" if is_video else "image",
            "source": str(src),
            "prompt": prompt.strip() or "(工作流默认)",
            "threshold": float(threshold),
            "refine_iterations": int(refine_iterations),
            "individual_masks": bool(individual_masks),
        }

        per_frame: list[dict] = []
        for i, fr in enumerate(frames):
            tag = f"_f{i:02d}" if is_video else ""
            wf = _load_workflow("sam3")
            _sam3_apply(wf, _upload_image(fr["path"]), prompt, threshold,
                        refine_iterations, individual_masks, ckpt_name, f"{base}{tag}")
            run = json.loads(_run(wf, out_dir, wait, timeout_seconds, {
                **meta_common,
                "frame_index": i if is_video else None,
                "time_sec": fr["time_sec"],
                "frame_image": fr["path"],
            }))
            entry: dict[str, Any] = {
                "frame_index": i,
                "time_sec": fr["time_sec"],
                "frame_image": fr["path"],
                "prompt_id": run.get("prompt_id"),
                "status": run.get("status"),
                "files": run.get("files", []),
            }
            # ★ 掩膜面积体检：0 = 这帧没检出目标（不靠 ComfyUI 的 success 下结论）
            areas = [
                a for a in (
                    _mask_coverage(f["path"]) for f in entry["files"]
                    if f.get("path") and "_mask" in (f.get("filename") or "")
                ) if a is not None
            ]
            entry["mask_coverage"] = max(areas) if areas else None
            entry["detected"] = (None if entry["mask_coverage"] is None
                                 else entry["mask_coverage"] > 0)
            if run.get("error"):
                entry["error"] = run["error"]
            per_frame.append(entry)

        areas_all = [e["mask_coverage"] for e in per_frame if e["mask_coverage"] is not None]
        failed = [e for e in per_frame if not e.get("prompt_id") or e.get("error")]
        result: dict[str, Any] = {
            "ok": not failed,
            "tool": "image_segmentation_sam3",
            "mode": meta_common["mode"],
            "status": ("queued" if not wait
                       else ("success" if not failed else "partial_failure")),
            "prompt": meta_common["prompt"],
            "source": str(src),
            "output_dir": str(out_dir),
            "frames": per_frame,
            "summary": {
                "frames": len(per_frame),
                "detected_frames": sum(1 for e in per_frame if e.get("detected")),
                "max_mask_coverage": max(areas_all) if areas_all else None,
                "mean_mask_coverage": (round(sum(areas_all) / len(areas_all), 6)
                                       if areas_all else None),
            },
        }
        if not is_video and per_frame:
            result.update({
                "prompt_id": per_frame[0]["prompt_id"],
                "files": per_frame[0]["files"],
                "mask_coverage": per_frame[0]["mask_coverage"],
                "detected": per_frame[0]["detected"],
            })
        if not wait:
            result["hint"] = ("逐帧已提交，用 comfyui_get_result(prompt_id) 取回"
                              "（prompt_id 见 frames[].prompt_id）")
        return _dump(result)
    except Exception as e:
        return _err(f"image_segmentation_sam3 失败: {e}")


if __name__ == "__main__":
    mcp.run()
