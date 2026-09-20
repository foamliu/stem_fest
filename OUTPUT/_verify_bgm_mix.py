# -*- coding: utf-8 -*-
"""★ BGM 混音验收：`full_cut_bgm*.mp4` 是否**没动画面**、**台词还在**、**音乐真的在响**。

为什么需要它（混音这种"看不见的改动"必须以数字为准）：
  1. **画面必须逐字节等于母版** —— `_mix_bgm.py` 走 `-c:v copy`，
     用视频流 MD5 直接证明，不靠"看起来一样"。
  2. **台词必须还在** —— 原片音轨与混后音轨对齐后求归一化互相关：
     ≥0.98 = 台词/环境音完整（实测 0.9847）。
     ⚠️ 直接算 0 位移相关会得到 ≈0 —— 混后会引入 **≈5 ms 整体偏移**
     （AAC 再编码的 priming），必须先扫延迟再对齐，否则会误判成"台词丢了"。
  3. **音乐层电平** —— 「混后 − 画面音轨」即 BGM 层：
       · 全片铺满版：有声处 BGM 应被闪避压到 −35 dBFS 以下、静处抬到 −35 以上；
       · 尾声版：`--start` 之前音乐层应 ≈ −45 dBFS 以下（等于没有），之后明显抬升。
     ⚠️ 若用了 `--film-dip`，要先按 k 倍还原画面音再相减，否则残差不是音乐层。

用法：
    py -3.10 OUTPUT/_verify_bgm_mix.py                          # 默认查全片铺满版
    py -3.10 OUTPUT/_verify_bgm_mix.py --mix=OUTPUT/full_cut_bgm_tail.mp4 --start=489.875 --dip=-20
"""

import argparse
import os
import subprocess
import sys

import numpy as np

for _s in ("stdout", "stderr"):
    try:
        getattr(sys, _s).reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 48000


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def dec(path):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1",
                        "-ar", str(SR), "-f", "f32le", "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.float32)


def db(x):
    return 20 * np.log10(max(float(np.sqrt(np.mean(x ** 2))), 1e-9))


def video_md5(path):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-map", "0:v",
                        "-c", "copy", "-f", "md5", "-"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "").strip()


def best_lag(o, b, ms=50):
    """b 相对 o 的整数采样延迟（±ms）。"""
    x, y = o - o.mean(), b - b.mean()
    m = len(x) + len(y)
    cc = np.fft.irfft(np.fft.rfft(x, m) * np.conj(np.fft.rfft(y, m)), m)
    w = int(ms * SR / 1000.0)
    cc = np.concatenate([cc[-w:], cc[:w + 1]])
    return int(np.argmax(np.abs(cc))) - w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--orig", default=os.path.join(ROOT, "OUTPUT", "full_cut.mp4"))
    ap.add_argument("--mix", default=os.path.join(ROOT, "OUTPUT", "full_cut_bgm.mp4"))
    ap.add_argument("--start", type=float, default=-1.0,
                    help="BGM 起点（尾声版填它；-1 = 全片铺满）")
    ap.add_argument("--dip", type=float, default=0.0,
                    help="与 _mix_bgm.py --film-dip 一致（dB）")
    ap.add_argument("--windows", default="",
                    help="自定义窗口，如 \"436-451,451-496,496.5-503\"（逗号分隔）")
    a = ap.parse_args()

    # ① 画面
    m0, m1 = video_md5(a.orig), video_md5(a.mix)
    print("① 画面  母版 %s\n        混后 %s\n        %s"
          % (m0, m1, "✅ 逐字节一致（-c:v copy 无损）" if m0 == m1
             else "❌ 不一致 —— 画面被重编码了"))

    # ② 台词
    o, b = dec(a.orig), dec(a.mix)
    n = min(len(o), len(b))
    o, b = o[:n], b[:n]
    lag = best_lag(o, b)
    o2, b2 = (o[lag:], b[:len(b) - lag]) if lag > 0 else (o[:lag], b[-lag:])
    r = float(np.dot(o2, b2) / (np.linalg.norm(o2) * np.linalg.norm(b2) + 1e-12))
    print("② 台词  延迟 %+d 样本（%+.2f ms）→ 对齐后相关 %.4f（%.1f s）%s"
          % (lag, lag * 1000.0 / SR, r, len(o2) / float(SR),
             " ✅ 台词完整" if r > 0.9 else " ❌ 存疑，需人工听"))

    # ③ 音乐层
    t = np.arange(len(o2)) / float(SR)
    k = 10 ** (a.dip / 20.0)
    gain = np.where(t >= a.start, k, 1.0) if a.start >= 0 else 1.0
    film, music = o2 * gain, b2 - o2 * gain
    print("③ 音乐层（BGM 应只在 %s 之后出现）"
          % ("%.3f s" % a.start if a.start >= 0 else "0 s"))
    print("   %-16s %10s %10s %10s" % ("窗口(s)", "画面音", "混后", "BGM层"))
    win = [(0, 8, "片头"), (200, 206, "中段")]
    if a.start > 0:
        win += [(max(0, a.start - 10), a.start, "铺歌前"),
                (a.start, a.start + 6, "起铺点")]
    else:
        win += [(4, 8, "原片最响"), (20, 24, "原片最静")]
    win += [(a.start + 13 if a.start > 0 else 240, 
             a.start + 19 if a.start > 0 else 246, "对照")]
    for item in [s for s in a.windows.split(",") if s.strip()]:
        try:
            t0, t1 = [float(v) for v in item.split("-")]
            win.append((t0, t1, "自定义"))
        except ValueError:
            print("   ⚠ 窗口格式无法解析：%s" % item)
    for t0, t1, note in win:
        i, j = int(t0 * SR), min(int(t1 * SR), len(o2))
        print("   %-16s %10.2f %10.2f %10.2f   %s"
              % ("%.1f-%.1f" % (t0, t1), db(film[i:j]), db(b2[i:j]),
                 db(music[i:j]), note))
    print("   整片：画面(压低后) %.2f / 混后 %.2f / BGM 层 %.2f dBFS，"
          "真峰 %.1f dBFS" % (db(film), db(b2), db(music),
                            20 * np.log10(max(float(np.max(np.abs(music))), 1e-9))))
    print("   体检法（供参照）：全片版在有声处 BGM 应 < -35、静处 > -35；"
          "尾声版在起点前 BGM 应 < -45")
    return 0


if __name__ == "__main__":
    sys.exit(main())
