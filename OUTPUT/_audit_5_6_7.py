#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 5/6/7 项审计：逐镜「语音 + 音效 + 人脸」体检并生成问题清单。

数据源
  语音 → qwen3_asr（复用 MCP 服务函数，mp4 音轨 → 文字）
  音效 → sound_caption（LAION Whisper 音效描述）
  人脸 → face_feature（InsightFace 检测 + ArcFace，reembed_px=512 修正小脸）
  期望 → storyboard.md 表格第 6 列（台词/音效）+ _shot_refs.json（该镜参考图）

产物
  OUTPUT/_audit_data.json    逐镜原始结果（**可断点续跑**：已有条目默认跳过）
  OUTPUT/_AUDIT_5_6_7.md     问题镜清单 + 改进建议

用法（py -3.10；需 ComfyUI 在线）：
  py -3.10 OUTPUT/_audit_5_6_7.py                # 全跑（约 30–60 分钟）
  py -3.10 OUTPUT/_audit_5_6_7.py --only=face    # 只做第 6 项
  py -3.10 OUTPUT/_audit_5_6_7.py --shots=1-20   # 只做指定镜
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import math
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "OUTPUT"
DATA = OUTPUT / "_audit_data.json"
REPORT = OUTPUT / "_AUDIT_5_6_7.md"
ACTS = ["01_paper_plane", "02_campus", "03_classroom_day", "05_classroom_night",
        "06_trench", "07_rice_field", "08_train_dining"]

# ── 复用 MCP 服务里的工具函数（保证与生产路径完全一致）──
spec = importlib.util.spec_from_file_location(
    "comfyui_mcp_server", ROOT / "mcp_server" / "comfyui_mcp_server.py")
srv = importlib.util.module_from_spec(spec)
sys.modules["comfyui_mcp_server"] = srv
spec.loader.exec_module(srv)


def load_data() -> dict:
    if DATA.exists():
        return json.loads(DATA.read_text(encoding="utf-8"))
    return {}


def save_data(data: dict) -> None:
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def shot_of(name: str) -> int | None:
    m = re.match(r"^(\d{1,3})_", name)
    return int(m.group(1)) if m else None


def latest_by_shot(paths: list[str]) -> dict[int, list[str]]:
    """同一镜可能有多版（重跑），按文件名排序取**最后一版**（编号最大）。"""
    out: dict[int, list[str]] = {}
    for p in sorted(paths):
        s = shot_of(os.path.basename(p))
        if s is not None:
            out.setdefault(s, []).append(p)
    return out


def load_expectations() -> tuple[dict[int, str], dict[int, str], dict[int, list[str]]]:
    """→ (台词期望, 音效期望, 参考图)"""
    dialogue, sfx, refs = {}, {}, {}
    for line in (ROOT / "storyboard.md").read_text(encoding="utf-8").splitlines():
        if not line.startswith("| "):
            continue
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) < 6 or not cols[0].isdigit():
            continue
        shot, spec = int(cols[0]), cols[5]
        sfx_m = re.search(r"音效[:：]\s*([^|]*)", spec)
        if sfx_m:
            sfx[shot] = sfx_m.group(1).strip()
        talk = re.split(r"音效[:：]", spec)[0].strip()
        talk = re.sub(r"\*\*|🍎|🌾|🎬", "", talk).strip()
        if talk:
            dialogue[shot] = talk
    sr = json.loads((OUTPUT / "_shot_refs.json").read_text(encoding="utf-8"))
    for k, v in sr.items():
        refs[int(k)] = [r for r in (v.get("refs") or []) if r]
    return dialogue, sfx, refs


def shots_of_spec(spec: str) -> set[int] | None:
    """`--shots=1-20,46` → {1..20,46}"""
    if not spec:
        return None
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            out.update(range(int(a), int(b) + 1))
        elif part:
            out.add(int(part))
    return out


# ── 比对工具 ──────────────────────────────────────────────────────
def overlap(expected: str, got: str) -> float:
    """台词吻合度：期望台词的有效字符有多少出现在转写里（0–1）。"""
    def clean(s: str) -> str:
        return re.sub(r"[^\u4e00-\u9fff\w]", "", s).lower()

    exp = clean(re.sub(r"^[^：:]{1,6}[：:]", "", expected))     # 去掉「角色：」前缀
    got_c = clean(got)
    if not exp:
        return 1.0
    if not got_c:
        return 0.0
    hit = sum(1 for ch in set(exp) if ch in got_c)
    return hit / len(set(exp))


def cos(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    s = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return s / (na * nb) if na and nb else 0.0


SILENCE_WORDS = ("silence", "no sound", "silent", "no audible", "quiet room")
SPEECH_WORDS = ("speaking", "speech", "voice", "vocal", "conversation", "talk")
MUSIC_WORDS = ("music", "melody", "instrument", "piano", "guitar", "beat")


def caption_kind(cap: str) -> set[str]:
    low = (cap or "").lower()
    kinds = set()
    if any(w in low for w in SILENCE_WORDS):
        kinds.add("silence")
    if any(w in low for w in SPEECH_WORDS):
        kinds.add("speech")
    if any(w in low for w in MUSIC_WORDS):
        kinds.add("music")
    if not kinds:
        kinds.add("sfx")
    return kinds


# ── 三个执行器（结果写缓存，支持断点续跑）──
def run_asr(data: dict, shot: int, video: str) -> dict:
    r = json.loads(srv.qwen3_asr(audio=video, language="Chinese", wait=True,
                                 output_dir=str(OUTPUT / "asr"), timeout_seconds=600))
    text = ""
    for f in r.get("files") or []:
        if f.get("text"):
            text = f["text"].strip()
    return {"ok": bool(r.get("ok")), "video": os.path.basename(video),
            "text": text, "prompt_id": r.get("prompt_id"), "error": r.get("error")}


def run_caption(shot: int, video: str) -> dict:
    r = json.loads(srv.sound_caption(audio=video, wait=True,
                                     output_dir=str(OUTPUT / "caption"),
                                     timeout_seconds=600))
    cj = r.get("caption_json") or {}
    return {"ok": bool(r.get("ok")), "caption": cj.get("caption", ""),
            "duration_sec": cj.get("duration_sec"), "prompt_id": r.get("prompt_id"),
            "error": r.get("error")}


def run_face(paths: list[str], tag: str) -> dict:
    r = json.loads(srv.face_feature(paths="\n".join(paths), model_name="buffalo_l",
                                    provider="CPU", det_size=640, min_det_score=0.3,
                                    include_embedding=True, reembed_px=512,
                                    max_images=128, wait=True,
                                    output_dir=str(OUTPUT / "face_feature"),
                                    timeout_seconds=1800))
    fj = r.get("face_json") or {}
    return {"ok": bool(r.get("ok")), "tag": tag, "images": fj.get("images") or [],
            "prompt_id": r.get("prompt_id"), "error": r.get("error")}


def write_report(data: dict, dialogue: dict, sfx_exp: dict,
                 shot_refs: dict, videos: dict) -> None:
    lines: list[str] = ["# 第 5/6/7 项审计报告（语音 · 音效 · 人脸）", ""]
    lines += [f"- 生成时间：{__import__('datetime').datetime.now():%Y-%m-%d %H:%M}",
              f"- 视频镜数：{len(videos)}｜ASR 已完成：{len(data['asr'])}"
              f"｜音效描述已完成：{len(data['caption'])}"
              f"｜人脸批次：{len(data['face'])}", ""]

    # 汇总人脸：帧 → (脸高, 余弦排名)
    frame_info: dict[str, dict] = {}
    ref_emb: dict[str, list[float]] = {}
    for res in data["face"].values():
        for im in res.get("images") or []:
            fn = im.get("file", "")
            faces = im.get("faces") or []
            if not faces:
                frame_info[fn] = {"n": 0, "h": 0}
                continue
            top = faces[0]
            entry = {"n": len(faces), "h": top.get("face_px_h", 0),
                     "emb": top.get("embedding"), "reembed": top.get("reembed_crop_px")}
            if "ASSETS" in fn:
                ref_emb[os.path.basename(fn)] = entry.get("emb") or []
            else:
                frame_info[fn] = entry

    problems: list[tuple[int, str, str]] = []      # (镜, 类别, 说明)
    rows: list[str] = []

    for shot in sorted(videos):
        key = str(shot)
        asr = data["asr"].get(key) or {}
        cap = data["caption"].get(key) or {}
        exp_talk = dialogue.get(shot, "")
        exp_sfx = sfx_exp.get(shot, "")
        got_text = (asr.get("text") or "").strip()
        ov = overlap(exp_talk, got_text) if exp_talk else 1.0
        kinds = caption_kind(cap.get("caption", "")) if cap else set()

        # 人脸：该镜的帧里最好的一个
        best_cos, best_ref, best_h, n_faces, rank_margin = 0.0, "", 0, 0, 0.0
        shot_frames = [f for f in frame_info if shot_of(os.path.basename(f)) == shot]
        for f in shot_frames:
            info = frame_info[f]
            n_faces = max(n_faces, info.get("n", 0))
            if not info.get("emb"):
                continue
            sims = sorted(((cos(info["emb"], ref_emb.get(os.path.basename(r), [])),
                            os.path.basename(r)) for r in shot_refs.get(shot, [])
                           if ref_emb.get(os.path.basename(r))), reverse=True)
            if sims and sims[0][0] > best_cos:
                best_cos, best_ref, best_h = sims[0][0], sims[0][1], info.get("h", 0)
                rank_margin = sims[0][0] - sims[1][0] if len(sims) > 1 else sims[0][0]

        flags: list[str] = []
        if exp_talk and ov < 0.5:
            flags.append(f"语音不符({ov:.2f})")
            problems.append((shot, "语音",
                             f"期望「{exp_talk[:26]}」→ 实得「{got_text[:26] or '（无语音）'}」吻合度 {ov:.2f}"))
        if exp_talk and "silence" in kinds and "speech" not in kinds:
            flags.append("有台词但音轨无语音")
            problems.append((shot, "语音", "storyboard 有台词，但音效描述显示无人声"))
        if exp_sfx and not cap:
            flags.append("音效未检")
        if n_faces == 0:
            flags.append("画面无人脸")
        elif best_cos and best_h and best_h < 250:
            flags.append(f"小脸不可判({best_h:.0f}px)")
            problems.append((shot, "人脸",
                             f"脸高仅 {best_h:.0f}px（<250 判据）⇒ 无法与 {best_ref} 判定同一人；"
                             f"裁切重提后余弦 {best_cos:.3f}（仅可作相对参考）"))
        elif best_cos < 0.30 and best_h >= 250:
            flags.append(f"人脸可疑({best_cos:.2f})")
            problems.append((shot, "人脸",
                             f"与 {best_ref} 余弦 {best_cos:.3f}（脸高 {best_h:.0f}px，"
                             f"与次名差 {rank_margin:.3f}）→ 建议换更清晰的定妆照或重跑该镜"))

        rows.append(f"| {shot} | {ov:.2f} | {got_text[:22] or '—'} | "
                    f"{'/'.join(sorted(kinds)) or '—'} | {n_faces} | {best_h:.0f} | "
                    f"{best_cos:.3f} | {best_ref[:24] or '—'} | {'、'.join(flags) or 'OK'} |")

    lines += ["## 1. 逐镜数据", "",
              "| 镜 | 台词吻合 | ASR 转写 | 音效类型 | 人脸数 | 脸高px | 余弦 | 主参考 | 提示 |",
              "|---|:---:|---|---|:---:|:---:|:---:|---|---|"] + rows
    lines += ["", "## 2. 问题镜清单", ""]
    if problems:
        lines += ["| 镜 | 类别 | 问题 |", "|---|:---:|---|"]
        lines += [f"| {s} | {c} | {d} |" for s, c, d in problems]
    else:
        lines.append("（无）")

    lines += ["", "## 3. 对 storyboard 的改镜建议", ""]
    by_kind: dict[str, list[int]] = {}
    for s, c, _d in problems:
        by_kind.setdefault(c, []).append(s)
    for kind, shots in by_kind.items():
        lines.append(f"**{kind}问题（{len(shots)} 镜）**：{', '.join(map(str, sorted(set(shots))))}")
        if kind == "语音":
            lines += ["- 台词吻合度低多为 **H3 漏念/念错**：建议在 storyboard 的 `Audio:` 段"
                      "把角色名 + 语气提示写全（如 `Audio: 刘思齐（小声、急促）说：……`），"
                      "并把长句拆成 ≤12 字短句（单镜 2–4 s 更稳）。",
                      "- 若某镜本来就**不该有人声**（纯环境音），请把台词列改为 `音效：…` 并在"
                      "prompt 画面段追加「不得出现任何可读文字」（防字幕泄漏，README §6.6b）。"]
        elif kind == "人脸":
            lines += ["- 这些镜**脸太小（<250 px）**，ArcFace 无法判定：要么在 storyboard 里"
                      "**为本镜改景别**（全景/远全 → 中近景/近景），要么接受「不可判」并另配一张"
                      "**特写镜**来承担角色辨识。",
                      "- 定妆照建议统一用**近景/特写且脸高 > 400 px** 的图（如 "
                      "`*_closeup_v02_16x9.png`），不要用三视图全身照做脸一致性参考。",
                      "- 重跑时优先用 `video_minimax_h3_r2v` 并把 `<Picture 1>` 指向该角色近景定妆照。"]
    lines += ["", "> 判据说明：按项目 README §6.5 —— 绝对余弦**不可**单独作判据；"
              "脸高 < 250 px 一律判「不可判」；本报告已开启 `reembed_px=512`（裁切重提）"
              "以缓解小脸失真，但仍不改变「小脸不可判」这条硬规矩。"]
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="all", choices=("all", "voice", "face", "report"))
    ap.add_argument("--shots", default="")
    args = ap.parse_args()

    data = load_data()
    for key in ("asr", "caption", "face", "refs_emb"):
        data.setdefault(key, {})
    dialogue, sfx_exp, shot_refs = load_expectations()
    want = shots_of_spec(args.shots)
    print(f"storyboard 台词 {len(dialogue)} 镜 / 音效标注 {len(sfx_exp)} 镜 / "
          f"参考图映射 {len(shot_refs)} 镜", flush=True)

    # 镜 → 视频（每镜取最新一版）
    videos: dict[int, str] = {}
    for act in ACTS:
        got = latest_by_shot(glob.glob(str(OUTPUT / act / "video" / "*.mp4")))
        for shot, lst in got.items():
            videos[shot] = lst[-1]
    print(f"找到 {len(videos)} 个镜的视频文件", flush=True)

    # ── 第 5 项：语音（ASR）+ 音效（caption）──
    if args.only in ("all", "voice"):
        todo = sorted(s for s in videos if (want is None or s in want))
        for i, shot in enumerate(todo, 1):
            key = str(shot)
            if key not in data["asr"]:
                data["asr"][key] = run_asr(data, shot, videos[shot])
                print(f"  [{i}/{len(todo)}] 镜 {shot} ASR: "
                      f"{(data['asr'][key].get('text') or '[空]')[:40]}", flush=True)
                save_data(data)
            if key not in data["caption"]:
                data["caption"][key] = run_caption(shot, videos[shot])
                print(f"         镜 {shot} 音效: "
                      f"{(data['caption'][key].get('caption') or '[空]')[:60]}", flush=True)
                save_data(data)

    # ── 第 6 项：人脸（按幕批量，一次任务处理整幕）──
    if args.only in ("all", "face", "report"):
        for act in ACTS:
            frames = sorted(glob.glob(str(OUTPUT / act / "frames" / "*.png")))
            if not frames:
                continue
            act_shots = {shot_of(os.path.basename(f)) for f in frames}
            refs = sorted({r for s in act_shots if s in shot_refs
                           for r in shot_refs[s] if os.path.exists(r)})
            if not refs:
                continue
            tag = f"{act}|{len(frames)}frames|{len(refs)}refs"
            if tag in data["face"]:
                continue
            res = run_face(frames + refs, tag)
            data["face"][tag] = res
            print(f"  人脸 {act}: ok={res['ok']} 图 {len(res['images'])} "
                  f"有脸 {sum(1 for im in res['images'] if im.get('face_count'))}", flush=True)
            save_data(data)

    if args.only == "report":
        pass
    write_report(data, dialogue, sfx_exp, shot_refs, videos)
    print(f"\n报告已写入 {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())


