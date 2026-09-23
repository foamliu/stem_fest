# -*- coding: utf-8 -*-
"""把 `OUTPUT/sfx/film/` 的音效铺进成片 —— **混音**，不替换 H3 台词音轨。

★ 设计要点
  1. **只动音频，画面不动**：`-c:v copy` 直通 ⇒ 与 `_mix_bgm.py` 同规，画面逐字节不变。
  2. **必须混音，不能替换**：成片音轨是 H3 一步联合生成的 L1 台词（README §4.4），
     替换掉等于全片哑掉。
  3. **电平按「实测响度」归一化，不用固定 dB 偏移**（2026-09-21 定）：
       gain = **目标 LUFS − 该文件实测 LUFS**（ebur128）。
     为什么：20 条音效源响度差 **30 dB**（实测 −14 ~ −45 LUFS），固定偏移会把弱的那条
     直接压到听不见（首版 SFX-17 实测 −44.9，减 20 dB 后 ≈ −65 dB）。
     目标值：`bed`（底噪/环境）**−34 LUFS**（≈ 比母版台词低 20 dB）；`point`（点状 foley）
     **−27 LUFS**。改这两个数用 `--level-bed / --level-point`。
  4. **段长受镜时长约束**：每条音效 `atrim` 到 `min(音效时长, 本镜剩余)`，
     **绝不越镜**（越镜会把下一镜的声音提前带进来）。
  5. **时间轴来源唯一**：镜起点一律取 `_concat_chapters.txt`（= 帧数 ÷ 24，
     与 `_concat_video.py` 同源；README §6.11 的规矩）。
  6. 产物**另存**（默认 `OUTPUT/full_cut_sfx.mp4`），绝不覆盖无音效母版。
  7. **铺位表 = storyboard §音效铺位 的 16 条**（原 34 处标注去重后 16 条），
     另补两条**规格里有、素材里缺**的：SFX-17（镜 9 教室群杂）、SFX-18（镜 109 键盘骤停）。
     ⚠️ **两条都是按「客观画像」判收的**，不是靠回读：`sound_caption`(LAION) 实测**不可靠**
     （拿已采纳的 SFX-12 稻田蝉鸣去回读，它说成 *"vacuum cleaner"*）。判据用
     `OUTPUT/_diag_sfx_profile.py`（频段占比 / 静音占比 / 波峰因数 crest / 4Hz 音节调制）：
       · SFX-18 键盘骤停 crest **31.7** ≈ 已采纳的 SFX-05/06（30.8/31.2）⇒ ✅ 采纳；
       · SFX-17 首版整体 **−44.9 dB**、静音 63% ⇒ ❌ 太稀疏，已废（留 `_00001` 作反例）；
       · SFX-17 二版中频 **86%**、静音 11%、crest 15.1，回读 *"unintelligible muffled speech"* ⇒ ✅ 采纳；
       · 备选 `SFX-17b_..._woosh_00001.mp3`（woosh 版）同族，保留备用（同 SFX-14b/14c 的做法）。


不属于本节的三类（storyboard 已定，别硬塞给音效模型）：
  播报语音（镜 81/102）走 `qwen3_tts`；音乐动机（镜 3/4/45/73/104）走 `ace_step_t2audio`；
  「寂静」（镜 111/113/119）是**留白**，不生成。

用法：
    py -3.10 OUTPUT/_mix_sfx.py --list       # 打印铺位表（镜号 / 绝对时间 / 电平）
    py -3.10 OUTPUT/_mix_sfx.py --dry-run    # 只打印滤镜图与命令
    py -3.10 OUTPUT/_mix_sfx.py              # 混音 → OUTPUT/full_cut_sfx.mp4
    py -3.10 OUTPUT/_mix_sfx.py --film=OUTPUT/full_cut_bgm_chorus.mp4 \\
        --out=OUTPUT/full_cut_bgm_sfx.mp4    # 在带 BGM 的成片上再叠音效
    py -3.10 OUTPUT/_mix_sfx.py --measure    # 顺带量每条音效的响度
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
TMP = os.path.join(OUT, "_mixsfx")
SFXDIR = os.path.join(OUT, "sfx", "film")
CHAP = os.path.join(OUT, "_concat_chapters.txt")

FILM = os.path.join(OUT, "full_cut.mp4")
SR = 48000      # 混音总线采样率（成片原轨 32 kHz ⇒ 统一到 48 k）
AC = 2
TAIL_GUARD = 0.05   # 音效最多铺到「镜尾 − TAIL_GUARD」

# ── 铺位表（storyboard §音效铺位 的唯一实现；改铺位只改这里）────────────
# (ID, 文件名, 镜号, 本镜内偏移 s, 类型, 中文标注)
#   · 偏移 0 = 从镜首铺起（底噪类）；点状 foley 给一个落在「动作发生处」的偏移（估算，可调）
#   · 类型 bed = 底噪/环境（默认 −20 dB）；point = 点状（默认 −10 dB）
PLACEMENTS = [
    ("SFX-01", "SFX-01_paper_snap_00001.mp3",    5,   2.0, "point", "纸飞机被夹住的轻响"),
    ("SFX-02", "SFX-02_device_beep_00001.mp3",   17,  2.0, "point", "轻微「滴」声"),
    ("SFX-03", "SFX-03_holo_chime_00001.mp3",    117, 1.5, "point", "轻微电子音（全息屏）"),
    ("SFX-03", "SFX-03_holo_chime_00001.mp3",    122, 1.5, "point", "轻微电子音（屏幕亮起）"),
    ("SFX-04", "SFX-04_heartbeat_00001.mp3",     110, 0.4, "point", "心跳声，一声"),
    ("SFX-05", "SFX-05_key_once_00001.mp3",      120, 2.5, "point", "键盘声，一声"),
    ("SFX-06", "SFX-06_key_rising_00001.mp3",    121, 0.4, "point", "键盘声渐起"),
    ("SFX-07", "SFX-07_rice_leaf_00001.mp3",     50,  0.6, "point", "稻叶拨动声"),
    ("SFX-08", "SFX-08_seat_creak_00001.mp3",    83,  0.5, "point", "座位轻响"),
    ("SFX-09", "SFX-09_soft_laugh_00001.mp3",    23,  0.8, "point", "轻笑声"),
    ("SFX-10", "SFX-10_wind_open_air_00001.mp3", 4,   0.0, "bed",   "风声（纸飞机掠过校园）"),
    ("SFX-11", "SFX-11_trench_wind_shovel_00001.mp3", 19, 0.0, "bed", "风声＋铁锹声（战壕）"),
    ("SFX-11", "SFX-11_trench_wind_shovel_00001.mp3", 27, 0.0, "bed", "同上（镜 27 风声突然清晰）"),
    ("SFX-12", "SFX-12_rice_cicada_bed_00001.mp3", 47,  0.0, "bed",   "稻田蝉鸣与风吹稻浪"),
    ("SFX-12", "SFX-12_rice_cicada_bed_00001.mp3", 52,  0.0, "bed",   "同上（镜 52 蝉鸣突然清晰）"),
    ("SFX-12", "SFX-12_rice_cicada_bed_00001.mp3", 64,  0.0, "bed",   "同上（镜 64 稻浪声）"),
    ("SFX-12", "SFX-12_rice_cicada_bed_00001.mp3", 106, 0.0, "bed",   "同上（镜 106 蝉鸣又回来）"),
    ("SFX-13", "SFX-13_cicada_stop_00001.mp3",   18,  2.0, "point", "蝉鸣骤停"),
    ("SFX-14", "SFX-14c_hsr_woosh_00001.mp3",    75,  0.0, "bed",   "高铁低频轰响"),
    ("SFX-14", "SFX-14c_hsr_woosh_00001.mp3",    91,  0.0, "bed",   "同上（镜 91 高铁轰响）"),
    ("SFX-15", "SFX-15_rail_rhythm_00001.mp3",   79,  0.0, "bed",   "车轮与铁轨的节奏声"),
    ("SFX-16", "SFX-16_platform_stop_00001.mp3", 102, 0.0, "bed",   "高铁到站环境底噪"),
    ("SFX-16", "SFX-16_platform_stop_00001.mp3", 104, 0.0, "bed",   "同上（镜 104 已停稳）"),
    ("SFX-17", "SFX-17_classroom_chatter_00002.mp3", 9, 0.0, "bed", "教室群杂（原规格缺，本次补；首版太稀疏已废）"),
    ("SFX-18", "SFX-18_typing_stop_00001.mp3",   109, 0.5, "point", "键盘声突然停住（原规格缺，本次补）"),
]


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
    """→ (画面时长, 音轨时长, 文件时长)；画面按「帧数 ÷ fps」算（同 `_mix_bgm.py`）。

    ⚠️ 判「片长」必须用**画面时长** —— 音轨可能比画面长（H3 音频包尾巴，README §6.1/§6.11）。
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


def chapters(path=CHAP):
    """`_concat_chapters.txt` → {镜号: (起点, 终点)}（= 帧数 ÷ 24，权威时间轴）。"""
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                continue
            p = line.rstrip("\n").split("\t")
            if len(p) >= 4:
                try:
                    out[int(p[0])] = (float(p[2]), float(p[3]))
                except ValueError:
                    pass
    return out


def audio_len(path):
    """音轨**解码**后的时长（不是容器 duration；容器值可能少报几十毫秒）。"""
    r = run(["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=duration", "-of", "csv=p=0", path])
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def measure_loudness(path):
    """ebur128 → (I LUFS 字符串, 真峰 dBFS 字符串)。"""
    r = run(["ffmpeg", "-nostats", "-v", "info", "-i", path,
             "-filter_complex", "ebur128=peak=true", "-f", "null", "-"])
    I = P = None
    for line in ((r.stderr or "") + (r.stdout or "")).splitlines():
        s = line.strip()
        if s.startswith("I:"):
            I = s.split()[1]
        elif s.startswith("Peak:"):
            P = s.split()[1]
    return I, P


def lufs(path):
    """该音效的**整体响度**（LUFS）；测不到（近静音）返回 None。"""
    I, _P = measure_loudness(path)
    try:
        v = float(I)
    except (TypeError, ValueError):
        return None
    return v if v > -70.0 else None


def build_plan(film_dur, chap, target_bed, target_point):
    """铺位 → [dict]；顺带做「缺文件 / 无此镜 / 越镜 / 镜内放不下」四道保护。

    ★ **按实测响度归一化**（2026-09-21 定）：`gain = 目标 LUFS − 该文件实测 LUFS`。
      为什么不能用固定 dB 偏移：20 条音效源响度差 **30 dB**（实测 −14 ~ −44.9 LUFS），
      固定偏移会把弱的那条直接压到听不见（实测 SFX-17 首版 −44.9，减 20 dB 后 ≈ −65）。
    """
    plan, warns = [], []
    for cid, fn, shot, off, kind, cn in PLACEMENTS:
        p = os.path.join(SFXDIR, fn)
        if not os.path.exists(p):
            warns.append("缺文件：%s（%s）" % (fn, cn))
            continue
        if shot not in chap:
            warns.append("章节表无此镜：%d（%s）" % (shot, cn))
            continue
        s0, s1 = chap[shot]
        t = s0 + off
        avail = (s1 - TAIL_GUARD) - t
        ln = min(audio_len(p), avail, film_dur - t)
        if ln <= 0.05:
            warns.append("镜 %d 放不下（剩余 %.3f s）：%s" % (shot, avail, cn))
            continue
        I = lufs(p)
        if I is None:
            warns.append("测不到响度（近静音）：%s（%s）" % (fn, cn))
            continue
        target = target_bed if kind == "bed" else target_point
        plan.append({
            "tag": "s%d" % len(plan), "path": p, "t": t, "ln": ln,
            "gain": target - I, "lufs": I, "target": target,
            "kind": kind, "cn": cn, "shot": shot, "cid": cid,
        })
    for w in warns:
        print("  [!] %s" % w)
    return plan


def build_filtergraph(film_dur, plan):
    fmt = ("aresample=%d,aformat=sample_fmts=fltp:sample_rates=%d:"
           "channel_layouts=stereo" % (SR, SR))
    ch = []
    for i, p in enumerate(plan):
        # 输入 0 = 成片 ⇒ 第 i 条铺位对应输入 i+1
        ch.append("[%d:a]%s,volume=%.1fdB,atrim=0:%.3f,asetpts=N/SR/TB,"
                  "adelay=%d:all=1[%s]"
                  % (i + 1, fmt, p["gain"], p["ln"], int(round(p["t"] * 1000)),
                     p["tag"]))
    ch.append("%samix=inputs=%d:duration=longest:dropout_transition=0:"
              "normalize=0[bus]"
              % ("".join("[%s]" % p["tag"] for p in plan), len(plan)))
    ch.append("[bus]apad,atrim=0:%.3f,asetpts=N/SR/TB[bus2]" % film_dur)
    ch.append("[0:a]%s,atrim=0:%.3f,asetpts=N/SR/TB[F]" % (fmt, film_dur))
    ch.append("[F][bus2]amix=inputs=2:duration=first:dropout_transition=0:"
              "normalize=0[mix]")
    ch.append("[mix]alimiter=limit=0.891:level=0:attack=5:release=50[aout]")
    return ";\n".join(ch)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--film", default=FILM)
    ap.add_argument("--out", default=os.path.join(OUT, "full_cut_sfx.mp4"))
    ap.add_argument("--chapter", default=CHAP)
    ap.add_argument("--level-bed", type=float, default=-34.0,
                    help="bed（底噪）**目标响度 LUFS 绝对值**（默认 -34 ≈ 比台词低 20 dB）")
    ap.add_argument("--level-point", type=float, default=-27.0,
                    help="point（点状 foley）**目标响度 LUFS 绝对值**（默认 -27）")
    ap.add_argument("--list", action="store_true", help="只打印铺位表")
    ap.add_argument("--measure", action="store_true", help="再逐条打印音效响度（交叉核对）")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不执行")
    a = ap.parse_args()

    if not os.path.exists(a.film):
        print("找不到成片：%s" % a.film)
        return 1
    film_dur, film_a_dur, _ = durations(a.film)
    chap = chapters(a.chapter)
    if not chap:
        print("章节表为空：%s" % a.chapter)
        return 1

    print("成片      %s" % os.path.relpath(a.film, ROOT))
    print("          画面 %.3f s / 音轨 %.3f s（差 %+.3f s）"
          % (film_dur, film_a_dur, film_a_dur - film_dur))
    print("章节表    %d 镜（%s）" % (len(chap), os.path.relpath(a.chapter, ROOT)))
    print("母版响度  I=%s" % measure_loudness(a.film)[0])
    print("目标响度  bed %.1f LUFS / point %.1f LUFS（按**实测**归一化，不是固定偏移）"
          % (a.level_bed, a.level_point))

    print("\n铺位表（%d 条；绝对时间 = 章节表起点 + 镜内偏移）：" % len(PLACEMENTS))
    plan = build_plan(film_dur, chap, a.level_bed, a.level_point)
    print("  %-7s %-5s %-5s %9s %8s %8s %8s  %s"
          % ("ID", "类型", "镜", "起点(s)", "段长(s)", "源LUFS", "增益dB", "标注"))
    for p in plan:
        print("  %-7s %-5s %-5d %9.3f %8.3f %8.1f %+8.1f  %s"
              % (p["cid"], p["kind"], p["shot"], p["t"], p["ln"],
                 p["lufs"], p["gain"], p["cn"]))
    if not plan:
        print("没有可铺的音效")
        return 1

    if a.measure:
        print("\n音效响度（ebur128；判据用数值，不靠耳朵）：")
        for p in plan:
            I, P = measure_loudness(p["path"])
            print("  %-7s %-4s I=%-9s Peak=%-9s %s"
                  % (p["cid"], p["kind"], I, P, p["cn"]))

    if a.list:
        return 0

    inputs = []
    for p in plan:      # ★ 同一文件被多条铺位引用就重复给输入（ffmpeg 支持）
        inputs += ["-i", p["path"]]
    fc = build_filtergraph(film_dur, plan)
    os.makedirs(TMP, exist_ok=True)
    fcfile = os.path.join(TMP, "filtergraph_%s.txt"
                          % os.path.splitext(os.path.basename(a.out))[0])
    with open(fcfile, "w", encoding="utf-8") as f:
        f.write(fc)
    print("\n滤镜图    %.1f KB 走文件（%d 路音效输入）" % (len(fc) / 1024.0, len(plan)))

    cmd = (["ffmpeg", "-y", "-v", "error", "-i", a.film] + inputs +
           ["-filter_complex_script", fcfile, "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-ar", str(SR), "-ac", str(AC), "-movflags", "+faststart", a.out])
    if a.dry_run:
        print("\n滤镜图 → %s\n\n%s\n\n命令：\n%s"
              % (fcfile, fc, " ".join(cmd)))
        return 0

    print("\n混音中（画面直通 copy，只重编码音轨）…")
    r = run(cmd)
    if r.returncode != 0:
        print("混音失败：\n%s" % (r.stderr or "")[:2000])
        return 1

    # ── 体检：时长对齐 + 响度/真峰（防削波）─────────────────────────
    v, au, _ = durations(a.out)
    print("✅ 已出 %s" % os.path.relpath(a.out, ROOT))
    print("   时长：画面 %.3f s / 音轨 %.3f s（差 %+.3f s） / %.1f MB"
          % (v, au, au - v, os.path.getsize(a.out) / 1e6))
    I, P = measure_loudness(a.out)
    print("   响度：I=%s  Peak=%s（母版 I=%s）"
          % (I, P, measure_loudness(a.film)[0]))
    print("   铺位：%d 条（bed %d / point %d）"
          % (len(plan), sum(1 for x in plan if x["kind"] == "bed"),
             sum(1 for x in plan if x["kind"] == "point")))
    return 0


if __name__ == "__main__":
    sys.exit(main())


