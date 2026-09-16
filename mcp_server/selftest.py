#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP 服务器离线自检 —— 不需要 ComfyUI 在线。

校验两件事：
  1. 15 个工具均已注册到 FastMCP（12 条工作流 + 3 个辅助工具）
  2. 每条工作流的参数注入落到了正确的节点上（拦截 `_queue` 检查提交的 workflow）

用法::

    python mcp_server/selftest.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parent / "comfyui_mcp_server.py"

spec = importlib.util.spec_from_file_location("comfyui_mcp_server", SERVER)
srv = importlib.util.module_from_spec(spec)
sys.modules["comfyui_mcp_server"] = srv
spec.loader.exec_module(srv)

CAPTURED: dict = {}
FAILURES: list[str] = []


def _check(label: str, cond: bool, detail: str = "") -> None:
    mark = "PASS" if cond else "FAIL"
    print(f"  [{mark}] {label}" + (f"  -> {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(label)


# ── 拦截 ComfyUI 调用（离线跑通注入逻辑）─────────────────────────
def _fake_queue(wf: dict) -> str:
    CAPTURED["wf"] = wf
    return "offline-test-prompt-id"


srv._queue = _fake_queue
srv._wait = lambda pid, timeout: {"outputs": {}}                    # noqa: E731
srv._save_outputs = lambda entry, out_dir: []                      # noqa: E731
srv._upload_image = lambda p, target_name=None: "ref_test.png"     # noqa: E731
srv._upload_media = lambda p, target_name=None, kind="": "mcp_test_media.bin"   # noqa: E731
srv._upload_audio = lambda p, target_name=None: "audio_test.wav"   # noqa: E731
srv._extract_audio = lambda p: p                                   # noqa: E731
# SAM3 视频模式：抽帧与掩膜体检都依赖 ffmpeg，离线用例改为桩
srv._extract_frames = lambda video, count, start, end, out_dir: [  # noqa: E731
    {"path": str(video), "time_sec": round(0.5 + i, 3)} for i in range(count)
]
srv._mask_coverage = lambda png: None                              # noqa: E731
# ASR 用例需要一个存在的输入文件（真实路径检查在工具内）
_ASR_FIXTURE = SERVER.parent.parent / "OUTPUT" / "_selftest_audio_fixture.wav"
_VIDEO_FIXTURE = SERVER.parent.parent / "OUTPUT" / "_selftest_clip.mp4"


def call(fn, **kwargs) -> tuple[dict, dict]:
    CAPTURED.clear()
    result = json.loads(fn(**kwargs))
    return result, CAPTURED.get("wf", {})


def inputs_of(wf: dict, class_type: str) -> list[dict]:
    return [n["inputs"] for n in wf.values() if n.get("class_type") == class_type]


def main() -> int:
    print("=" * 68)
    print(" ComfyUI MCP Server 自检（离线，不依赖 ComfyUI 服务）")
    print("=" * 68)

    # 1. 工具注册
    print("\n[1] 工具注册")
    tools = sorted(t.name for t in srv.mcp._tool_manager.list_tools())
    expected = [
        "ace_step_t2audio", "comfyui_get_result", "comfyui_status",
        "comfyui_upload_image", "face_feature", "image_edit_longcat",
        "image_segmentation_sam3",
        "qwen3_asr", "qwen3_tts", "sound_caption", "stable_audio_3_sfx",
        "video_minimax_h3_i2v", "video_minimax_h3_r2v",
        "video_minimax_h3_t2v", "z_image_turbo_t2i",
    ]
    _check("工具数量 = 15（FireRed 已移除；2026-09-16 新增 stable_audio_3_sfx / sound_caption / face_feature）",
           len(tools) == 15,
           f"实际 {len(tools)}: {tools}")
    for name in expected:
        _check(f"已注册 {name}", name in tools)
    for key, fname in srv.WORKFLOWS.items():
        _check(f"工作流文件存在 [{key}]", (srv.WORKFLOW_DIR / fname).exists(), fname)

    # 2. Z-Image-Turbo T2I
    print("\n[2] z_image_turbo_t2i")
    res, wf = call(srv.z_image_turbo_t2i, prompt="cinematic bar, charcoal",
                   negative_prompt="logo, text", width=1280, height=720,
                   seed=42, steps=8)
    _check("提交成功", res.get("ok") is True and res.get("seed") == 42, str(res))
    enc = inputs_of(wf, "CLIPTextEncode")[0]
    _check("prompt 注入 CLIPTextEncode", "cinematic bar, charcoal" in enc["text"])
    _check("negative 追加为 Do NOT include", "Do NOT include: logo, text" in enc["text"])
    lat = inputs_of(wf, "EmptySD3LatentImage")[0]
    _check("尺寸注入 EmptySD3LatentImage", (lat["width"], lat["height"]) == (1280, 720))
    _check("seed 注入 KSampler", inputs_of(wf, "KSampler")[0]["seed"] == 42)
    _check("PreviewImage 转为 SaveImage", not inputs_of(wf, "PreviewImage")
           and "t2i/" in inputs_of(wf, "SaveImage")[0]["filename_prefix"])

    # 3. LongCat 图像编辑
    print("\n[3] image_edit_longcat")
    res, wf = call(srv.image_edit_longcat, prompt="same girl at a desk",
                   image="ASSETS/CHARACTERS/01_liu_siqi/liu_siqi_hero_v01.png",
                   negative_prompt="different face", seed=100, megapixels=2.0)
    _check("提交成功", res.get("ok") is True, str(res))
    _check("LoadImage 注入参考图", inputs_of(wf, "LoadImage")[0]["image"] == "ref_test.png")
    _check("megapixels 注入 ImageScaleToTotalPixels",
           inputs_of(wf, "ImageScaleToTotalPixels")[0]["megapixels"] == 2.0)
    _check("seed 注入 KSampler", inputs_of(wf, "KSampler")[0]["seed"] == 100)
    te = inputs_of(wf, "TextEncodeQwenImageEdit")
    _check("正向 prompt 注入首个 TextEncodeQwenImageEdit",
           te[0]["prompt"] == "same girl at a desk")
    _check("负向 prompt 注入第二个 TextEncodeQwenImageEdit",
           te[1]["prompt"] == "different face")

    # 3b. FireRed Image Edit —— 🚫 **已于 2026-09-13 整体移除**（5/5 次运行产出纯黑图，
    #     零成功率；本项目图生图一律用 image_edit_longcat）。原参数注入用例随之删除。

    # 4. Qwen3-TTS
    print("\n[4] qwen3_tts")
    res, wf = call(srv.qwen3_tts, text="明天那个模型的上线评审，你准备一下。",
                   speaker="Vivian", seed=1301, instruct="28岁女性，北京口音。")
    _check("提交成功", res.get("ok") is True and res.get("speaker") == "Vivian", str(res))
    cv = inputs_of(wf, "Qwen3CustomVoice")[0]
    _check("speaker/seed 注入", cv["speaker"] == "Vivian" and cv["seed"] == 1301)
    _check("custom_speaker_name 必须为空", cv["custom_speaker_name"] == "")
    _check("text/instruct 注入", "上线评审" in cv["text"] and "北京口音" in cv["instruct"])
    sav = inputs_of(wf, "SaveAudioAdvanced")[0]
    _check("SaveAudioAdvanced 前缀+格式",
           sav["format"] == "flac" and sav["filename_prefix"].startswith("tts/"))
    bad = json.loads(srv.qwen3_tts(text="x", speaker="不存在的音色"))
    _check("非法 speaker 被拒绝", bad.get("ok") is False, str(bad))

    # 4b. Qwen3-ASR（配音核对）
    print("\n[4b] qwen3_asr")
    _ASR_FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    _ASR_FIXTURE.write_bytes(b"RIFF....WAVEfmt ")   # 占位内容，仅用于存在性检查
    try:
        res, wf = call(srv.qwen3_asr, audio=str(_ASR_FIXTURE),
                       language="Chinese", context="如愿·看见",
                       return_timestamps=False)
        _check("提交成功", res.get("ok") is True, str(res))
        tr = inputs_of(wf, "Qwen3ASRTranscribe")[0]
        _check("language/context 注入 Qwen3ASRTranscribe",
               tr["language"] == "Chinese" and tr["context"] == "如愿·看见"
               and tr["return_timestamps"] is False)
        _check("LoadAudio 注入音频名",
               inputs_of(wf, "LoadAudio")[0]["audio"] == "audio_test.wav")
        _check("SaveText 前缀 + txt 格式",
               inputs_of(wf, "SaveText")[0]["format"] == "txt"
               and inputs_of(wf, "SaveText")[0]["filename_prefix"].startswith("asr/"))
    finally:
        try:
            _ASR_FIXTURE.unlink()
        except Exception:
            pass

    # 4c. SAM3 检测 / 分割（图片）—— 开放词汇：用文字找东西
    print("\n[4c] image_segmentation_sam3（图片）")
    _SAM3_IMG = "ASSETS/PROPS/01_paper_plane/paper_plane_hero_v01.png"
    res, wf = call(srv.image_segmentation_sam3,
                   image=_SAM3_IMG,
                   prompt="paper plane:2, boy", threshold=0.4, refine_iterations=1)
    _check("提交成功 / mode=image",
           res.get("ok") is True and res.get("mode") == "image", str(res)[:300])
    _check("LoadImage 注入输入图", inputs_of(wf, "LoadImage")[0]["image"] == "ref_test.png")
    _check("prompt 注入 CLIPTextEncode",
           inputs_of(wf, "CLIPTextEncode")[0]["text"] == "paper plane:2, boy")
    det = inputs_of(wf, "SAM3_Detect")[0]
    _check("threshold/refine_iterations/individual_masks 注入 SAM3_Detect",
           det["threshold"] == 0.4 and det["refine_iterations"] == 1
           and det["individual_masks"] is False)
    _check("PreviewImage 转为 SaveImage（_bbox 后缀）",
           not inputs_of(wf, "PreviewImage")
           and any(s["filename_prefix"].endswith("_bbox")
                   for s in inputs_of(wf, "SaveImage")))
    overlay_ids = [k for k, n in wf.items() if n.get("class_type") == "ImageAndMaskPreview"]
    _check("叠加图 SaveImage 挂在 ImageAndMaskPreview 的 composite 上",
           wf.get("mcp_save_overlay", {}).get("inputs", {}).get("images") == [overlay_ids[0], 0],
           str(wf.get("mcp_save_overlay")))
    det_ids = [k for k, n in wf.items() if n.get("class_type") == "SAM3_Detect"]
    _check("MaskToImage 接 SAM3_Detect 的 masks 输出",
           wf.get("mcp_mask_to_image", {}).get("inputs", {}).get("mask") == [det_ids[0], 0],
           str(wf.get("mcp_mask_to_image")))
    _check("原始掩膜落成 SaveImage（_mask 后缀）",
           wf.get("mcp_save_mask", {}).get("inputs", {}).get("images")
           == ["mcp_mask_to_image", 0]
           and wf["mcp_save_mask"]["inputs"]["filename_prefix"].endswith("_mask"))
    _check("单图模式顶层平铺 files / detected / mask_coverage",
           "files" in res and "detected" in res and "mask_coverage" in res, str(res)[:300])
    res, wf = call(srv.image_segmentation_sam3,
                   image=_SAM3_IMG,
                   prompt="boy", individual_masks=True)
    _check("individual_masks=True 时跳过原始掩膜分支（0 检出会让 SaveImage 崩）",
           "mcp_mask_to_image" not in wf and "mcp_save_overlay" in wf, str(list(wf))[:200])
    bad = json.loads(srv.image_segmentation_sam3(image=_SAM3_IMG, threshold=1.5))
    _check("非法 threshold 被拒绝", bad.get("ok") is False, str(bad))
    bad = json.loads(srv.image_segmentation_sam3(image=_SAM3_IMG, video_frames=99))
    _check("非法 video_frames 被拒绝", bad.get("ok") is False, str(bad))

    # 4d. SAM3 检测（视频 → 均匀抽帧，逐帧检测）
    print("\n[4d] image_segmentation_sam3（视频抽帧）")
    _VIDEO_FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    _VIDEO_FIXTURE.write_bytes(b"\x00\x00\x00\x18ftypmp42")   # 占位内容（抽帧已被桩替换）
    try:
        res, wf = call(srv.image_segmentation_sam3, image=str(_VIDEO_FIXTURE),
                       prompt="paper plane", video_frames=3)
        _check("mode=video 且逐帧返回 3 帧",
               res.get("ok") is True and res.get("mode") == "video"
               and len(res.get("frames", [])) == 3, str(res)[:300])
        _check("逐帧时间戳 / 帧图路径齐全",
               all(f.get("time_sec") is not None and f.get("frame_image")
                   for f in res["frames"]), str(res["frames"])[:200])
        _check("summary 统计齐全",
               res.get("summary", {}).get("frames") == 3
               and "detected_frames" in res["summary"], str(res.get("summary")))
        _check("视频模式顶层不重复平铺 files", "files" not in res, str(list(res))[:200])
        # wf 是最后一帧（index=2）提交的内容 ⇒ 前缀应带 _f02
        _check("逐帧保存前缀带帧号",
               any(s["filename_prefix"].endswith("_f02_bbox")
                   for s in inputs_of(wf, "SaveImage")),
               str([s["filename_prefix"] for s in inputs_of(wf, "SaveImage")]))
    finally:
        try:
            _VIDEO_FIXTURE.unlink()
        except Exception:
            pass

    # 4e. 新增三件套（2026-09-16）：音效生成 / 音效描述 / 人脸特征
    print("\n[4e] stable_audio_3_sfx / sound_caption / face_feature")

    res, wf = call(srv.stable_audio_3_sfx,
                   prompt="paper plane whooshing past, clean foley",
                   negative_prompt="music", duration=6.5, seed=777,
                   steps=8, cfg=1.0, filename_prefix="sfx/selftest")
    _check("提交成功且回传 seed", res.get("ok") is True and res.get("seed") == 777,
           str(res)[:200])
    _check("duration 注入 EmptyLatentAudio",
           inputs_of(wf, "EmptyLatentAudio")[0]["seconds"] == 6.5,
           str(inputs_of(wf, "EmptyLatentAudio")))
    enc = sorted(((k, n) for k, n in wf.items()
                  if n.get("class_type") == "CLIPTextEncode"), key=lambda x: int(x[0]))
    _check("正向 prompt 进第 1 个 CLIPTextEncode",
           enc[0][1]["inputs"]["text"] == "paper plane whooshing past, clean foley")
    _check("负向 prompt 进第 2 个 CLIPTextEncode",
           enc[1][1]["inputs"]["text"] == "music")
    ks = inputs_of(wf, "KSampler")[0]
    _check("KSampler 取 LCM 配方（steps/cfg/sampler/scheduler）",
           ks["steps"] == 8 and ks["cfg"] == 1.0
           and ks["sampler_name"] == "lcm" and ks["scheduler"] == "simple", str(ks)[:200])
    _check("SaveAudioMP3 前缀注入",
           inputs_of(wf, "SaveAudioMP3")[0]["filename_prefix"] == "sfx/selftest")
    _check("CLIPLoader 用 stable_audio 类型的 t5gemma",
           inputs_of(wf, "CLIPLoader")[0]["type"] == "stable_audio")

    res, wf = call(srv.sound_caption, audio="OUTPUT/_selftest_audio_fixture.wav",
                   max_new_tokens=256, num_beams=1)
    _check("提交成功且回传 audio_input",
           res.get("ok") is True and res.get("audio_input") == "mcp_test_media.bin",
           str(res)[:200])
    _check("LoadAudio 指向上传后的文件名",
           inputs_of(wf, "LoadAudio")[0]["audio"] == "mcp_test_media.bin")
    cap = inputs_of(wf, "LAIONAudioCaption")[0]
    _check("max_new_tokens / num_beams 注入，且模型目录非空",
           cap["max_new_tokens"] == 256 and cap["num_beams"] == 1
           and cap["model_dir"].endswith("laion_sound_effect_captioning_whisper"),
           str(cap)[:300])

    res, wf = call(srv.face_feature,
                   paths="ASSETS/CHARACTERS/01_liu_siqi/liu_siqi_closeup_v02_16x9.png",
                   model_name="buffalo_l", provider="CPU", det_size=1024,
                   min_det_score=0.4, reembed_px=512, max_images=32)
    _check("提交成功", res.get("ok") is True, str(res)[:200])
    face = inputs_of(wf, "InsightFaceFeature")[0]
    _check("参数注入 InsightFaceFeature",
           face["model_name"] == "buffalo_l" and face["det_size"] == 1024
           and face["min_det_score"] == 0.4 and face["reembed_px"] == 512 and face["max_images"] == 32, str(face)[:300])
    _check("项目相对路径已转成绝对路径（节点才能读盘）",
           "ASSETS" in face["paths"] and ":\\" in face["paths"], face["paths"][:200])

    # 5. ACE-Step
    print("\n[5] ace_step_t2audio")
    res, wf = call(srv.ace_step_t2audio, tags="solo piano, contemplative",
                   lyrics="", duration=45.0, seed=4001, bpm=60, keyscale="E minor")
    _check("提交成功", res.get("ok") is True and res.get("duration") == 45.0, str(res))
    ace = inputs_of(wf, "TextEncodeAceStepAudio1.5")[0]
    _check("tags/lyrics/bpm/keyscale 注入",
           ace["tags"].startswith("solo piano") and ace["lyrics"] == ""
           and ace["bpm"] == 60 and ace["keyscale"] == "E minor")
    _check("duration 注入 PrimitiveFloat",
           inputs_of(wf, "PrimitiveFloat")[0]["value"] == 45.0)
    _check("seed 注入 KSampler", inputs_of(wf, "KSampler")[0]["seed"] == 4001)
    _check("输出格式 mp3", inputs_of(wf, "SaveAudioAdvanced")[0]["format"] == "mp3")

    # 6. H3 I2V
    print("\n[6] video_minimax_h3_i2v")
    res, wf = call(srv.video_minimax_h3_i2v, prompt="SHOT 1: medium shot ...",
                   image="OUTPUT/t2i/frame.png", duration=8.0, seed=8001,
                   megapixels=0.6)
    _check("提交成功", res.get("ok") is True and res.get("duration_sec") == 8.0, str(res))
    _check("LoadImage 注入首帧", inputs_of(wf, "LoadImage")[0]["image"] == "ref_test.png")
    _check("prompt 注入 MiniMaxH3ImageToVideo",
           inputs_of(wf, "MiniMaxH3ImageToVideo")[0]["prompt"].startswith("SHOT 1"))
    _check("duration 注入 PrimitiveFloat",
           inputs_of(wf, "PrimitiveFloat")[0]["value"] == 8.0)
    _check("seed 注入 RandomNoise",
           inputs_of(wf, "RandomNoise")[0]["noise_seed"] == 8001)
    rs = inputs_of(wf, "ResolutionSelector")[0]
    _check("画幅/像素注入 ResolutionSelector",
           rs["aspect_ratio"] == "16:9 (Widescreen)" and rs["megapixels"] == 0.6)
    _check("SaveVideo 前缀",
           "h3_i2v" in inputs_of(wf, "SaveVideo")[0]["filename_prefix"])

    # 7. H3 R2V
    print("\n[7] video_minimax_h3_r2v")
    res, wf = call(srv.video_minimax_h3_r2v, prompt="CUT 1: use <Picture 1> ...",
                   ref_image_1="a.png", ref_image_2="b.png", duration=5.0)
    _check("提交成功", res.get("ok") is True, str(res))
    _check("prompt 注入 PrimitiveStringMultiline",
           inputs_of(wf, "PrimitiveStringMultiline")[0]["value"].startswith("CUT 1"))
    load = [n["inputs"]["image"] for n in wf.values()
            if n.get("class_type") == "LoadImage"]
    _check("两张参考图分别注入", len(load) == 2 and all(v == "ref_test.png" for v in load))
    _check("SaveVideo 前缀",
           "h3_r2v" in inputs_of(wf, "SaveVideo")[0]["filename_prefix"])

    # 8. H3 T2V
    print("\n[8] video_minimax_h3_t2v")
    res, wf = call(srv.video_minimax_h3_t2v, prompt="[0s-1.5s] Shot 1: ...",
                   duration=5.0, seed=7)
    _check("提交成功", res.get("ok") is True, str(res))
    _check("prompt 注入 MiniMaxH3ImageToVideo",
           inputs_of(wf, "MiniMaxH3ImageToVideo")[0]["prompt"].startswith("[0s-1.5s]"))
    _check("工作流无 LoadImage（纯文生视频）", not inputs_of(wf, "LoadImage"))
    _check("seed 注入 RandomNoise", inputs_of(wf, "RandomNoise")[0]["noise_seed"] == 7)

    # 9. 异步提交路径
    print("\n[9] wait=False 异步提交")
    res, _ = call(srv.video_minimax_h3_t2v, prompt="async test", wait=False)
    _check("返回 queued 与 prompt_id",
           res.get("status") == "queued" and res.get("prompt_id"), str(res))

    # 10. 辅助工具（ComfyUI 离线也应优雅返回）
    print("\n[10] 辅助工具")
    status = json.loads(srv.comfyui_status())
    _check("comfyui_status 返回结构完整",
           "workflows" in status and "reachable" in status, str(status)[:200])
    _check("所有工作流可被 status 列出",
           len(status.get("workflows", {})) == len(srv.WORKFLOWS),
           str(status.get("workflows")))

    print("\n" + "=" * 68)
    if FAILURES:
        print(f" 结果：{len(FAILURES)} 项失败")
        for f in FAILURES:
            print(f"   x {f}")
        return 1
    print(" 结果：全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
