#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《如愿·看见》音效批量生产（Stable Audio 3 / Sony Woosh）★ storyboard「音效铺位」的落地脚本。

依据：`storyboard.md` 逐镜表第 6 列里所有 `音效：…（后期）` 标注（共 34 处，去重后 16 条）。
分工（详见 `README.md` §4.4 与 `mcp_server/comfyui_tools.md` §6.8 / §6.9）：

  * `sa3`   → `stable_audio_3_sfx`：点状 foley 与环境底噪的**首选**（1–60 s，约 4 s 机时 / 1 s 音频）
  * `woosh` → `woosh_sfx`：Sony 音效基础模型，物件感更"实"，慢一些（DFlow 4 步）

每个产物都过 `sound_caption` 回读 —— **音效模型报 success ≠ 出的是你要的声音**，
脚本把回读正文写进报告，人工据此判收。

用法::

    python OUTPUT/_make_film_sfx.py            # 全量
    python OUTPUT/_make_film_sfx.py SFX-05     # 只跑指定条目
    python OUTPUT/_make_film_sfx.py --list     # 只打印清单

产物：`OUTPUT/sfx/film/<ID>_<slug>_00001.mp3`
报告：`OUTPUT/_film_sfx_report.md`
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "mcp_server" / "comfyui_mcp_server.py"
REPORT = ROOT / "OUTPUT" / "_film_sfx_report.md"
OUT_DIR = ROOT / "OUTPUT" / "sfx" / "film"
# ⚠️ MCP 工具**忽略 ComfyUI 的 subfolder**，产物一律落进 `output_dir` 的平层 ——
#    所以目录必须由 output_dir 参数指定，不能指望 filename_prefix 里的 "xxx/" 建目录。
PREFIX_DIR = ""

# (ID, 服务镜, 中文标注, slug, 工具, 英文 prompt, 时长秒, seed)
CLIPS: list[tuple[str, str, str, str, str, str, float, int]] = [
    ("SFX-01", "5", "纸飞机被夹住的轻响", "paper_snap", "sa3",
     "a single soft paper snap, two fingers pinching a paper airplane out of the air, "
     "close perspective, quiet classroom, no music", 2.0, 5101),
    ("SFX-02", "17", "轻微「滴」声", "device_beep", "sa3",
     "one single short soft electronic beep, small device UI tick, close-up, quiet room, no music",
     1.5, 5102),
    ("SFX-03", "117,122", "轻微电子音（全息屏）", "holo_chime", "sa3",
     "soft futuristic hologram chime, gentle single electronic tone, clean, sci-fi UI, no music",
     2.0, 5103),
    ("SFX-04", "110", "心跳声，一声", "heartbeat", "sa3",
     "one single deep heartbeat thump, close and intimate, quiet room tone, no music", 2.0, 5104),
    ("SFX-05", "120", "键盘声，一声", "key_once", "sa3",
     "one single mechanical keyboard key press, crisp and close, quiet room, no music", 1.5, 5105),
    ("SFX-06", "121", "键盘声渐起", "key_rising", "sa3",
     "mechanical keyboard typing gradually picking up speed, several keys per second, "
     "quiet room, close perspective, no music", 4.0, 5106),
    ("SFX-07", "50", "稻叶拨动声", "rice_leaf", "sa3",
     "hands pushing apart tall rice plant leaves, dry leaf rustle, close perspective, "
     "sunny field, no music", 3.0, 5107),
    ("SFX-08", "83", "座位轻响", "seat_creak", "sa3",
     "train seat cushion creak and a faint metal click as someone sits down, close, no music",
     2.0, 5108),
    ("SFX-09", "23", "轻笑声", "soft_laugh", "woosh",
     "a few soft quiet chuckles from one person, short, gentle, clean recording", 2.0, 5109),
    ("SFX-10", "4", "风声（纸飞机掠过校园）", "wind_open_air", "sa3",
     "open air wind blowing past, medium strength, clean field recording, no music", 6.0, 5110),
    ("SFX-11", "19,27", "风声＋铁锹声（战壕）", "trench_wind_shovel", "sa3",
     "wind across a dirt trench, an occasional shovel cutting into soil, distant and open, no music",
     8.0, 5111),
    ("SFX-12", "47,52,64,106", "稻田蝉鸣与风吹稻浪", "rice_cicada_bed", "sa3",
     "summer rice field ambience, wind through dense rice leaves, loud cicadas, "
     "natural field recording, no music", 12.0, 5112),
    ("SFX-13", "18", "蝉鸣骤停", "cicada_stop", "sa3",
     "loud summer cicadas abruptly stopping into silence, hard cut, outdoor field recording, no music",
     4.0, 5113),
    ("SFX-14", "75,91", "高铁低频轰响", "hsr_rumble", "sa3",
     "high speed train interior low frequency rumble and hum, constant, close perspective, no music",
     10.0, 5114),
    ("SFX-15", "79", "车轮与铁轨的节奏声", "rail_rhythm", "sa3",
     "train wheels rolling over rail joints in a steady rhythm, clickety-clack, close, no music",
     8.0, 5115),
    ("SFX-16", "102,104", "高铁到站环境底噪", "platform_stop", "sa3",
     "high speed train slowing to a stop, brakes and rail friction fading, station ambience, no music",
     8.0, 5116),
]


def load_server():
    spec = importlib.util.spec_from_file_location("comfyui_mcp_server", SERVER)
    srv = importlib.util.module_from_spec(spec)
    sys.modules["comfyui_mcp_server"] = srv
    spec.loader.exec_module(srv)
    return srv


def log(line: str) -> None:
    print(line, flush=True)


def main() -> int:
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--list" in sys.argv:
        for cid, shots, cn, slug, tool, _p, dur, seed in CLIPS:
            log(f"{cid}  镜 {shots:<12} [{tool:<5}] {dur:>5.1f}s  {cn}")
        return 0

    srv = load_server()
    force = "--force" in sys.argv
    todo = [c for c in CLIPS if not argv or c[0] in argv]
    log(f"[sfx] 共 {len(todo)} 条要生成（工具：stable_audio_3_sfx / woosh_sfx）"
        + ("　--force：覆盖已存在产物" if force else "　（已存在的自动跳过，可重复跑）"))

    rows: list[dict] = []
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for cid, shots, cn, slug, tool, prompt, dur, seed in todo:
        prefix = f"{PREFIX_DIR}{cid}_{slug}"
        t0 = time.time()

        # 续跑保护：同一 ID 已有产物就跳过（ComfyUI 会给重名加 _00002，别白烧机时）
        done = [] if force else sorted(OUT_DIR.glob(f"{cid}_*"))
        if done:
            log(f"\n===== {cid} · {cn} =====")
            log(f"  [skip] 已存在 {done[0].name}")
            rows.append({"id": cid, "shots": shots, "cn": cn, "tool": tool, "prompt": prompt,
                         "dur": dur, "seed": seed, "ok": True, "status": "skipped",
                         "path": str(done[0]), "elapsed": 0.0, "caption": None})
            continue

        log(f"\n===== {cid} 镜 {shots} · {cn} · [{tool}] {dur}s =====")
        try:
            if tool == "sa3":
                res = json.loads(srv.stable_audio_3_sfx(
                    prompt=prompt, duration=dur, seed=seed,
                    filename_prefix=prefix, output_dir=str(OUT_DIR),
                    timeout_seconds=900))
            else:
                res = json.loads(srv.woosh_sfx(
                    prompt=prompt, duration=dur, model="dflow", seed=seed,
                    filename_prefix=prefix, output_dir=str(OUT_DIR),
                    timeout_seconds=900))
        except Exception as exc:  # noqa: BLE001
            res = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

        ok = bool(res.get("ok")) and res.get("status") == "success"
        files = res.get("files") or []
        out = files[0].get("path") if files else None
        log(f"  status={res.get('status')} ok={res.get('ok')} {time.time() - t0:.1f}s -> {out}")

        caption = None
        if ok and out:
            try:
                cap = json.loads(srv.sound_caption(audio=out, max_new_tokens=200))
                caption = (cap.get("caption_json") or {}).get("caption")
            except Exception as exc:  # noqa: BLE001
                caption = f"(回读失败 {type(exc).__name__})"
            log(f"  caption: {caption}")

        rows.append({"id": cid, "shots": shots, "cn": cn, "tool": tool, "prompt": prompt,
                     "dur": dur, "seed": seed, "ok": ok, "status": res.get("status"),
                     "path": out, "elapsed": round(time.time() - t0, 1), "caption": caption})

    write_report(rows)
    bad = [r["id"] for r in rows if not r["ok"]]
    log(f"\n[sfx] 完成 {len(rows) - len(bad)}/{len(rows)}" + (f"，失败：{bad}" if bad else ""))
    log(f"[report] {REPORT}")
    return 0 if not bad else 2


def write_report(rows: list[dict]) -> None:
    lines = [
        "# 《如愿·看见》音效生产报告",
        "",
        f"- 运行时刻：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 工具：`stable_audio_3_sfx`（Stable Audio 3 Medium）· `woosh_sfx`（Sony Woosh DFlow）",
        f"- 产物目录：`OUTPUT/sfx/film/`",
        "",
        "> ⚠️ **caption 是 LAION 音效描述模型的回读**，只描述\"听到了什么音色、像什么来源\"。",
        "> 判收口径：**它说得对不对**，不看 ComfyUI 报没报 success。",
        "",
        "| ID | 镜 | 音效 | 工具 | 时长 | 耗时 | 产物 | sound_caption 回读 |",
        "|---|:--:|---|:--:|:--:|:--:|---|---|",
    ]
    for r in rows:
        cap = (r.get("caption") or "").replace("|", "/")[:220]
        if r.get("status") == "skipped":
            cap = "⏭ 本次跳过（已有产物）"
        tool = {"sa3": "`stable_audio_3_sfx`", "woosh": "`woosh_sfx`"}.get(r["tool"], r["tool"])
        fl = f"`{Path(r['path']).name}`" if r.get("path") else f"❌ {r.get('status')}"
        el = f"{r['elapsed']}s" if r.get("elapsed") else "—"
        lines.append(
            f"| {r['id']} | {r['shots']} | {r['cn']} | {tool} | {r['dur']}s | "
            f"{el} | {fl} | {cap} |")
    lines += ["", "## prompt 全文（照抄用）", ""]
    for r in rows:
        lines += [f"**{r['id']}**（镜 {r['shots']}，{r['tool']}，{r['dur']}s，seed {r['seed']}）", "",
                  "```", r["prompt"], "```", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
