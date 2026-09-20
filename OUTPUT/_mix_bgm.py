# -*- coding: utf-8 -*-
"""把现成音源 BGM（《如愿》）铺进成片 —— **混音**，不替换 H3 台词音轨。

★ 设计要点
  1. **只动音频，画面不动**：`-c:v copy` 直通 ⇒ 1056×608 / 24fps / 126 镜
     画面**零代际损失**，整个混音只要「解一遍音频」的时间。
  2. **必须混音，不能替换**：`full_cut.mp4` 的音轨是 H3 一步联合生成的
     L1 台词（README §4.4）—— 替换掉等于全片哑掉。
  3. **电平是这里唯一的危险源（实测）**：
       · 成片音轨 `I = -12.4 LUFS`，真峰 **+0.1 dBFS**（已经很满）
       · 歌曲      `I = -11.1 LUFS`，真峰 **+1.0 dBFS**（商业母带，几乎顶格）
     两者直接相加 = **必削波**。⇒ 三重保险：
       ① BGM 先降 `--level`（默认 **-14 dB**）；
       ② `sidechaincompress` 用**成片音轨自己**当侧链做闪避（有人说话时 BGM 让路）；
       ③ 总线上挂 `alimiter`（-1 dBFS 真峰守门）。
  4. **循环用 `acrossfade` 而不是简单拼接**：歌曲正文只有 260.83 s
     （末尾还有 17 s 静音，必须裁掉），成片 525.6 s ⇒ 需要 3 段。
     直接 concat 会在接缝处「断一下」；`acrossfade=d=2` 做 2 s 交叉淡化，
     接缝听不出来。3 段交叉后总长 778.5 s，再 `atrim` 到片长。
  5. **尾部留淡出**：`--fade-out`（默认 4 s），避免音乐被硬切。
  6. 产物**另存**，绝不覆盖 `full_cut.mp4`（保留无 BGM 母版，方便随时重铺）。

用法：
    py -3.10 OUTPUT/_mix_bgm.py                                 # 全片铺满（默认）
    py -3.10 OUTPUT/_mix_bgm.py --start=489.9                   # 只从尾声镜 122 起铺
    py -3.10 OUTPUT/_mix_bgm.py --level=-18 --no-duck           # 更轻 / 不闪避
    py -3.10 OUTPUT/_mix_bgm.py --dry-run                       # 只打印滤镜图与命令

`--start / --end` 用 `OUTPUT/_concat_chapters.txt` 的绝对时间。
"""

import argparse
import json
import os
import subprocess
import sys

# Windows 控制台默认 GBK，打印 ✅/★ 等字符会 UnicodeEncodeError（同 _concat_video.py）
for _s in ("stdout", "stderr"):
    try:
        getattr(sys, _s).reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")
TMP = os.path.join(OUT, "_mixbgm")

FILM = os.path.join(OUT, "full_cut.mp4")
SONG = os.path.join(ROOT, "audio", "王菲如願Faye Wong.mp3")   # 现成音源（用户下载）

SR = 48000      # 混音总线采样率（成片原轨 32 kHz、BGM 44.1 kHz ⇒ 统一到 48 k）
AC = 2
XFADE = 2.0     # BGM 循环接缝的交叉淡化时长（s）
FADE_IN = 1.5   # BGM 进入淡入（s）


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


def probe(path, *entries):
    cmd = ["ffprobe", "-v", "error", "-print_format", "json"]
    for e in entries:
        cmd += ["-show_entries", e]
    cmd += [path]
    r = run(cmd)
    try:
        return json.loads(r.stdout or "{}")
    except ValueError:
        return {}


def durations(path):
    """→ (画面时长, 音轨时长, 文件时长)；画面按「帧数 ÷ fps」算。

    ⚠️ 成片**音轨比画面长 2.6 s**（H3 音频包尾巴，README §6.1 同源坑）
    ⇒ 判「片长」必须用画面时长，否则混出来的音轨会多出一截。
    """
    d = probe(path, "format=duration",
              "stream=codec_type,duration,nb_frames,avg_frame_rate")
    v = a = None
    for s in d.get("streams", []):
        try:
            dur = float(s.get("duration") or 0)
        except (TypeError, ValueError):
            dur = 0.0
        if s.get("codec_type") == "video":
            n, fr = s.get("nb_frames"), s.get("avg_frame_rate") or "0/0"
            if n and fr and fr != "0/0":
                num, den = fr.split("/")
                if float(den):
                    dur = float(n) * float(den) / float(num)
            v = dur
        elif s.get("codec_type") == "audio":
            a = dur
    f = float(d.get("format", {}).get("duration") or 0)
    return v or f, a or f, f


def song_body(path):
    """歌曲「正文」区间（去掉首尾静音）→ (start, end, 正文时长)。

    实测（`silencedetect=n=-45dB:d=0.5`）：0 → 0.700 静音、260.829 → 277.873 静音。
    含 17 s 静音的原文直接循环会在每次接缝插一段空白 ⇒ 必须裁。
    """
    r = run(["ffmpeg", "-nostats", "-v", "info", "-i", path, "-af",
             "silencedetect=n=-45dB:d=0.5", "-vn", "-f", "null", "-"])
    log = (r.stderr or "") + (r.stdout or "")
    starts, ends = [], []
    for line in log.splitlines():
        if "silence_start:" in line:
            try:
                starts.append(float(line.split("silence_start:")[1].split()[0]))
            except (IndexError, ValueError):
                pass
        elif "silence_end:" in line:
            try:
                ends.append(float(line.split("silence_end:")[1].split()[0]))
            except (IndexError, ValueError):
                pass
    all_d = durations(path)[0]
    b0 = ends[0] if starts and starts[0] <= 0.01 and ends else 0.0     # 首段静音结束点
    b1 = starts[-1] if starts and starts[-1] > (b0 + 1) else all_d     # 末段静音起点
    return b0, b1, b1 - b0


def seg_count(need, body, xfade):
    """要铺 `need` 秒，用几段 `body` 秒的循环 + 交叉淡化 → n。

    总长 = n × body − (n − 1) × xfade ≥ need。
    """
    if need <= body - 0.05:
        return 1                       # 一段就够，直接裁
    n = 2
    while n * body - (n - 1) * xfade < need:
        n += 1
    return n


def build_filtergraph(film_dur, need, body, level_db, duck, start,
                      fade_out, fade_in, xfade, film_dip=0.0, dip_start=None):
    """滤镜图：n 段音源 → acrossfade 循环 → 铺到区间 → 闪避混音 → 限幅。

    `film_dip`（dB，负数）：把**画面自带音轨**在 BGM 区间内压低 —— 尾声这种
    「歌曲主导」的段落必须用它（实测镜 126 成片自带音 −16.9 dBFS，不压的话
    音乐被限幅器挤到 −30 dBFS，等于听不见）。
    ★ 用 `atrim` 切两段再 `concat`（而不是 `volume` 的 if() 表达式）——
    表达式里的逗号在 filtergraph 文件里要转义，切段法零转义风险。
    """
    fmt = ("aresample=%d,aformat=sample_fmts=fltp:sample_rates=%d:"
           "channel_layouts=stereo" % (SR, SR))
    n = seg_count(need, body, xfade)
    ln = need if n == 1 else body      # 单段时只截到需要的长度

    chains = []
    for i in range(n):
        # 每段都从**歌曲正文开头**取 ⇒ 这就是「循环」
        chains.append("[%d:a]%s,atrim=0:%.3f,asetpts=N/SR/TB[s%d]"
                      % (i + 1, fmt, ln, i))
    if n == 1:
        chains.append("[s0]anull[bed]")
    else:
        prev = "[s0]"
        for i in range(1, n):
            tag = "[bed]" if i == n - 1 else "[x%d]" % i
            chains.append("%s[s%d]acrossfade=d=%.2f:c1=tri:c2=tri%s"
                          % (prev, i, xfade, tag))
            prev = tag

    # 裁到 need + 淡入淡出 + 电平
    fade = ""
    if fade_in > 0:
        fade += ",afade=t=in:st=0:d=%.2f" % fade_in
    if 0 < fade_out < need:
        fade += ",afade=t=out:st=%.3f:d=%.2f" % (need - fade_out, fade_out)
    chains.append("[bed]atrim=0:%.3f,asetpts=N/SR/TB%s,volume=%.1fdB[bedv]"
                  % (need, fade, level_db))

    # 不在 0 s 起铺时整体后移
    bed = "[bedv]"
    if start > 0.001:
        chains.append("[bedv]adelay=%d:all=1[bedd0]" % int(round(start * 1000)))
        bed = "[bedd0]"

    # 成片音轨（裁到画面时长，去掉 2.6 s 音频尾巴）
    chains.append("[0:a]%s,atrim=0:%.3f,asetpts=N/SR/TB[F]" % (fmt, film_dur))

    # 画面音轨在 BGM 区间内压低（★ `dip_start` 可与 `start` 解耦：
    #   对话镜要保留原电平让闪避去让路，只压"卡片/纯音乐"段）
    # ★ 只用 atrim + volume + concat（**不用** adelay：先延迟再 concat 会把延迟叠加；
    #   也不加斜坡：起点落在镜边界上，硬切是剪辑惯例，且避免 afade 只能到 0 的坑）
    if film_dip < -0.01:
        k = 10.0 ** (film_dip / 20.0)
        d0 = start if dip_start is None else dip_start
        if d0 > 0.001:
            chains.append("[F]asplit=2[Fh][Ft]")
            chains.append("[Fh]atrim=0:%.3f,asetpts=N/SR/TB[Fh2]" % d0)
            chains.append("[Ft]atrim=%.3f:%.3f,asetpts=N/SR/TB,volume=%.4f[Ft2]"
                          % (d0, film_dur, k))
            chains.append("[Fh2][Ft2]concat=n=2:v=0:a=1[Fd]")
        else:
            chains.append("[F]volume=%.4f[Fd]" % k)
        chains.append("[Fd]atrim=0:%.3f,asetpts=N/SR/TB[F]" % film_dur)

    # 闪避（用画面音轨当侧链）+ 相加 + 限幅
    if duck:
        chains.append("[F]asplit=2[Fmain][Fsc]")
        chains.append("%s[Fsc]sidechaincompress=threshold=0.05:ratio=8:"
                      "attack=20:release=600:makeup=1[bedc]" % bed)
        bgm_in = "[bedc]"
    else:
        chains.append("[F]anull[Fmain]")
        bgm_in = bed
    chains.append("[Fmain]%samix=inputs=2:duration=first:"
                  "dropout_transition=0:normalize=0[mix]" % bgm_in)
    chains.append("[mix]alimiter=limit=0.891:level=0:attack=5:release=50[aout]")
    return ";\n".join(chains), n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--film", default=FILM)
    ap.add_argument("--song", default=SONG)
    ap.add_argument("--out", default=os.path.join(OUT, "full_cut_bgm.mp4"))
    ap.add_argument("--start", type=float, default=0.0,
                    help="BGM 起点（成片绝对秒；0 = 片头就铺）")
    ap.add_argument("--end", type=float, default=0.0, help="BGM 终点（0 = 到片尾）")
    ap.add_argument("--level", type=float, default=-14.0,
                    help="BGM 相对电平 dB（越负越轻；默认 -14）")
    ap.add_argument("--fade-in", type=float, default=FADE_IN)
    ap.add_argument("--fade-out", type=float, default=4.0)
    ap.add_argument("--xfade", type=float, default=XFADE)
    ap.add_argument("--no-duck", action="store_true", help="关掉侧链闪避")
    ap.add_argument("--film-dip", type=float, default=0.0,
                    help="画面自带音轨压低多少 dB（负数；尾声这种「歌曲主导」段建议 -20）")
    ap.add_argument("--film-dip-start", type=float, default=0.0,
                    help="压低从哪一秒开始（0 = 与 --start 相同）。铺歌起点早于尾声时用："
                         "对话段不压（交给闪避），只压卡片段")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不执行")
    a = ap.parse_args()

    for p, what in ((a.film, "成片"), (a.song, "音源")):
        if not os.path.exists(p):
            print("找不到%s：%s" % (what, p))
            return 1

    film_dur, film_a_dur, _ = durations(a.film)
    b0, b1, body = song_body(a.song)
    end = a.end if a.end > 0 else film_dur
    need = end - a.start
    print("成片           画面 %.3f s / 音轨 %.3f s" % (film_dur, film_a_dur))
    print("歌曲           正文 %.3f–%.3f s（%.3f s；首尾静音已排除）"
          % (b0, b1, body))
    print("BGM 区间       %.3f–%.3f s（%.3f s）  电平 %+.1f dB  闪避 %s  画面音压低 %+.1f dB%s"
          % (a.start, end, need, a.level, "关" if a.no_duck else "开", a.film_dip,
             "（自 %.3f s 起）" % a.film_dip_start if a.film_dip_start > 0 else ""))
    if need <= 0:
        print("BGM 区间长度必须为正")
        return 1

    fc, nseg = build_filtergraph(film_dur, need, body, a.level, not a.no_duck,
                                 a.start, a.fade_out, a.fade_in, a.xfade,
                                 a.film_dip,
                                 a.film_dip_start if a.film_dip_start > 0 else None)
    os.makedirs(TMP, exist_ok=True)
    fcfile = os.path.join(TMP, "filtergraph_%s.txt"
                          % os.path.splitext(os.path.basename(a.out))[0])
    with open(fcfile, "w", encoding="utf-8") as f:
        f.write(fc)
    print("BGM 循环       %d 段（交叉淡化 %.1f s）→ 滤镜图 %.1f KB 走文件"
          % (nseg, a.xfade, len(fc) / 1024.0))

    cmd = (["ffmpeg", "-y", "-v", "error", "-i", a.film] + ["-i", a.song] * nseg +
           ["-filter_complex_script", fcfile, "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-ar", str(SR), "-ac", str(AC), "-movflags", "+faststart", a.out])
    if a.dry_run:
        print("\n滤镜图 → %s\n\n%s\n\n命令：\n%s"
              % (fcfile, fc, " ".join(cmd)))
        return 0

    print("混音中（画面直通 copy，只重编码音轨）…")
    r = run(cmd)
    if r.returncode != 0:
        print("混音失败：\n%s" % (r.stderr or "")[:2000])
        return 1

    # ── 体检：时长对齐 + 响度/真峰（防削波）──────────────────────
    v, au, _ = durations(a.out)
    print("✅ 已出 %s" % a.out)
    print("   时长：画面 %.3f s / 音轨 %.3f s（差 %+.3f s） / %.1f MB"
          % (v, au, au - v, os.path.getsize(a.out) / 1e6))
    r = run(["ffmpeg", "-nostats", "-v", "info", "-i", a.out,
             "-filter_complex", "ebur128=peak=true", "-f", "null", "-"])
    for line in ((r.stderr or "") + (r.stdout or "")).splitlines():
        s = line.strip()
        if s.startswith("I:") or s.startswith("LRA:") or s.startswith("Peak:"):
            print("   %s" % s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
