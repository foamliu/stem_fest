# -*- coding: utf-8 -*-
"""音效产物的**客观声学画像** —— 当回读模型不可靠时的判据。

为什么需要它：`sound_caption`（LAION）实测**不可靠** —— 拿已被采纳的
`SFX-12_rice_cicada_bed`（稻田蝉鸣）去回读，它说成 *"vacuum cleaner"*。
⇒ 回读只能当**线索**，判据要用可复算的声学量。

本脚本对每个文件算：
  · 时长 / 整体 RMS / 峰值
  · **静音占比**（< −45 dBFS 的 50 ms 窗），**占空比**（> −45 dB 的窗占比）
  · **频段能量占比**：低(<250Hz) / 语音(250–4k) / 高(>4k)，以及**谱质心**
      —— 蝉鸣/键盘 → 高频为主；人声群杂 → 语音带为主；车/风 → 低频为主
  · **4 Hz 调制能量**（音节速率）：人声类（群杂/笑声）显著；纯稳态噪声不显著
  · **波峰因数 crest**（峰值/有效值）：点状 foley（敲击）高；稳态底噪低

用法：
    py -3.10 OUTPUT/_diag_sfx_profile.py                 # 全部
    py -3.10 OUTPUT/_diag_sfx_profile.py SFX-17 SFX-18   # 只看这几条
"""

import glob
import os
import re
import subprocess
import sys

import numpy as np

for _s in ("stdout", "stderr"):
    try:
        getattr(sys, _s).reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SFXDIR = os.path.join(ROOT, "OUTPUT", "sfx", "film")
SR = 16000


def pcm(path):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1",
                        "-ar", str(SR), "-f", "f32le", "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.float32)


def analyse(x, win_ms=50):
    if len(x) < SR // 10:
        return None
    w = int(SR * win_ms / 1000.0)
    n = len(x) // w
    fr = x[:n * w].reshape(n, w)
    rms = np.sqrt((fr ** 2).mean(axis=1)) + 1e-12
    db = 20 * np.log10(rms)
    # 频段能量（对整段做一次 FFT，取三段占比）
    X = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    tot = (X ** 2).sum() + 1e-20
    lo = (X[f < 250] ** 2).sum() / tot
    mid = (X[(f >= 250) & (f < 4000)] ** 2).sum() / tot
    hi = (X[f >= 4000] ** 2).sum() / tot
    cent = float((f * X ** 2).sum() / tot)
    # 4 Hz（±1Hz）调制能量：音节速率
    env = rms / rms.mean()
    E = np.abs(np.fft.rfft(env * np.hanning(len(env)))) ** 2
    ef = np.fft.rfftfreq(len(env), win_ms / 1000.0)
    band = (ef > 3.0) & (ef < 5.0)
    mod4 = float(E[band].sum() / (E.sum() + 1e-20))
    return {
        "dur": len(x) / float(SR),
        "rms": float(20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-12)),
        "peak": float(20 * np.log10(np.abs(x).max() + 1e-12)),
        "sil": float((db < -45).mean()),
        "duty": float((db > -45).mean()),
        "lo": float(lo), "mid": float(mid), "hi": float(hi),
        "cent": cent,
        "mod4": mod4,
        "crest": float(20 * np.log10((np.abs(x).max() + 1e-12)
                                     / (np.sqrt((x ** 2).mean()) + 1e-12))),
    }


def main():
    want = [a.upper() for a in sys.argv[1:]]
    files = sorted(glob.glob(os.path.join(SFXDIR, "SFX-*.mp3")))
    print("%-34s %6s %7s %7s %6s %6s %6s %6s %6s %7s %6s %6s"
          % ("文件", "时长", "整体", "峰值", "静音", "占空", "低", "中", "高",
             "质心Hz", "4Hz", "crest"))
    print("-" * 122)
    for p in files:
        name = os.path.basename(p)
        if want and not any(w in name.upper() for w in want):
            continue
        a = analyse(pcm(p))
        if not a:
            print("%-34s  (太短/解码失败)" % name)
            continue
        print("%-34s %6.2f %7.1f %7.1f %5.0f%% %5.0f%% %5.0f%% %5.0f%% %5.0f%% %7.0f %6.3f %6.1f"
              % (name, a["dur"], a["rms"], a["peak"], a["sil"] * 100,
                 a["duty"] * 100, a["lo"] * 100, a["mid"] * 100,
                 a["hi"] * 100, a["cent"], a["mod4"], a["crest"]))
    print("\n读法（经验口径）：")
    print("  群杂/笑声 → 中频段占比高 + 4Hz 调制 >0.02；蝉鸣/键盘 → 高频占比高；")
    print("  车/风/轰鸣 → 低频占比高、crest 低；点状 foley → crest 高、静音占比高。")


if __name__ == "__main__":
    main()
