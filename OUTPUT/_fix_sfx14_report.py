# -*- coding: utf-8 -*-
"""把 SFX-14 的最终产物与回读结论回写进 `_film_sfx_report.md`。

背景：SFX-14（镜 75/91 高铁低频轰响）原用 `stable_audio_3_sfx` 跑，902.4s 后
产出为空（❌ None）。本脚本记录补跑结论：

  * `stable_audio_3_sfx` 两版回读均不合格
      - 原 prompt → "a vehicle passing by"（外景经过事件，非车厢内）
      - 改写 prompt → "high-pitched sustained electronic tone"（高频正弦，更差）
    ⇒ Stable Audio 对「低频稳态、无事件」的底噪能力不足。
  * `woosh_sfx`（DFlow）一版通过
      - 回读 "vehicle idling, low-frequency rumble, no other prominent sounds"
      - 稳态低频、无经过事件 ⇒ 符合「车厢内低频轰响」判收口径（README §4.4）。

产物：`OUTPUT/sfx/film/SFX-14c_hsr_woosh_00001.mp3`（122.9 KB / 10.0 s / 48 kHz）
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
REPORT = ROOT / "OUTPUT" / "_film_sfx_report.md"

OLD_ROW = ("| SFX-14 | 75,91 | 高铁低频轰响 | `stable_audio_3_sfx` | 10.0s | 902.4s | "
           "❌ None |  |")
NEW_ROW = ("| SFX-14 | 75,91 | 高铁低频轰响 | `woosh_sfx` | 10.0s | 36.2s | "
           "`SFX-14c_hsr_woosh_00001.mp3` | A vehicle, likely a car, is heard idling. "
           "The sound is a low-frequency rumble, consistent with an engine idling. "
           "There are no other prominent sounds. |")

OLD_PROMPT = '"high speed train interior low frequency rumble and hum, constant, close perspective, no music"'
NEW_PROMPT = ('"inside a fast moving high speed train carriage, steady deep engine rumble, '
              'low frequency drone, muffled and continuous"')


def main() -> int:
    text = REPORT.read_text(encoding="utf-8")
    lines = text.splitlines()

    n_row = n_prompt = 0
    for i, line in enumerate(lines):
        if line.startswith("| SFX-14 |"):
            lines[i] = NEW_ROW
            n_row += 1
        elif line.startswith("**SFX-14**"):
            # 标题里的工具标记与正文 prompt 一并更新
            lines[i] = "**SFX-14**（镜 75,91，woosh，10.0s，seed 5114）"
            for j in range(i + 1, min(i + 5, len(lines))):
                if lines[j].startswith("high speed train") or lines[j].startswith("inside a fast"):
                    lines[j] = NEW_PROMPT.strip('"')
                    n_prompt += 1
                    break
    text = "\n".join(lines) + "\n"

    note = (
        "\n## SFX-14 补跑记录（2026-09-21）\n\n"
        "原 `stable_audio_3_sfx` 产出于 2026-09-20 以 `❌ None` 收场（耗时 902.4s）。\n"
        "本次补跑三条，逐条过 `sound_caption` 回读：\n\n"
        "| 版本 | 工具 | 耗时 | 回读 | 判定 |\n|---|---|:--:|---|:--:|\n"
        "| 原 prompt | `stable_audio_3_sfx` | 15.1s | *a vehicle passing by … engine and tire "
        "sounds* | ❌ 外景经过事件 |\n"
        "| 改写为 interior/constant | `stable_audio_3_sfx` | 6.1s | *high-pitched, sustained "
        "electronic tone … sine wave* | ❌ 高频电子音，方向相反 |\n"
        "| 改写为 carriage/steady rumble | `woosh_sfx`(dflow) | 36.2s | *vehicle idling … "
        "low-frequency rumble … no other prominent sounds* | ✅ **采用** |\n\n"
        "结论：**低频稳态、无事件**的底噪是 `stable_audio_3_sfx` 的弱项（两版都把\"车\"画成"
        "\"经过\"或\"高频\"）；`woosh_sfx` 的物件感更实，一次通过。\n"
        "镜 75/91 铺位改取 `OUTPUT/sfx/film/SFX-14c_hsr_woosh_00001.mp3`。\n"
    )
    if "SFX-14 补跑记录" not in text:
        text = text.rstrip() + "\n" + note

    REPORT.write_text(text, encoding="utf-8")

    print(f"row replaced: {n_row}, prompt replaced: {n_prompt}")
    for line in text.splitlines():
        if "SFX-14" in line:
            print("  " + re.sub(r"\s+", " ", line)[:150])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
