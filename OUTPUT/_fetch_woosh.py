#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性脚本：把 Sony Woosh 的**主干权重**下载到 ComfyUI 的 woosh 模型目录。

背景（2026-09-20）：本机 `models/woosh/checkpoints/` 只到位了辅助组件
（TextConditionerA/V、Woosh-AE、Woosh-CLAP），**主干生成权重全部缺失**，
因此 `ComfyUI-Woosh` 即便装好依赖也无模型可用。

用法：
    python OUTPUT/_fetch_woosh.py                     # 默认下 4 个主干（≈5.7 GB）
    python OUTPUT/_fetch_woosh.py Woosh-DFlow         # 只下指定目录

下载源：**直连 huggingface.co**（本机 `HTTP(S)_PROXY=http://127.0.0.1:7897` 已通，实测 200）。
⚠️ 踩坑（2026-09-20）：改用镜像 `HF_ENDPOINT=https://hf-mirror.com` 会**必然失败** ——
hub 0.36 会校验 HEAD 响应头，镜像不返回该头 ⇒ `FileMetadataError: Distant resource
does not seem to be on huggingface.co` → 一路变成 `LocalEntryNotFoundError`。
脚本仍支持用环境变量 `HF_ENDPOINT` 覆盖，但**默认不设**。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download  # noqa: E402

REPO = "drbaph/Woosh"
DST = Path(r"E:\code\ComfyUI\models\woosh\checkpoints")

# 顺序即优先级：DFlow / DVFlow 是 4 步蒸馏版，最快，先拿
ALL_FOLDERS = ["Woosh-DFlow", "Woosh-DVFlow-8s", "Woosh-Flow", "Woosh-VFlow-8s"]
FILES = ["config.yaml", "weights.safetensors"]


def main() -> int:
    folders = sys.argv[1:] or ALL_FOLDERS
    print(f"[woosh] repo={REPO}  endpoint={os.environ.get('HF_ENDPOINT') or 'https://huggingface.co'}",
          flush=True)
    print(f"[woosh] dest={DST}", flush=True)

    failed: list[str] = []
    for folder in folders:
        for fname in FILES:
            target = DST / folder / fname
            if target.exists() and target.stat().st_size > 0:
                print(f"[skip] {folder}/{fname} 已经存在 "
                      f"({target.stat().st_size / 1048576:.1f} MB)", flush=True)
                continue
            print(f"[get]  {folder}/{fname}", flush=True)
            try:
                path = hf_hub_download(
                    repo_id=REPO, filename=f"{folder}/{fname}", local_dir=str(DST)
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[FAIL] {folder}/{fname}: {type(exc).__name__}: {exc}", flush=True)
                failed.append(f"{folder}/{fname}")
                continue
            size = Path(path).stat().st_size / 1048576
            print(f"  -> OK {path}  ({size:.1f} MB)", flush=True)

    if failed:
        print("[woosh] 失败项: " + ", ".join(failed), flush=True)
        return 1
    print("[woosh] DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
