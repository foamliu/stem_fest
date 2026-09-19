# -*- coding: utf-8 -*-
"""把已生成的镜头按镜号顺序拼成一个完整视频（增量可用）。

★ 设计要点
  1. **按镜号**从 6 个幕目录里收集产物，自动排序 —— 镜号 ≠ 目录顺序，
     不能靠目录名拼（第二幕在 07_rice_field、第三幕在 08_train_dining）。
  2. **★ 右上角烧录镜号**（2026-09-19 新增，用户要求）：
     每一帧右上角显示 `SHOT NNN`，便于反馈与排查 ——
     看到任何一帧都能直接报镜号，不必再用时间码反查章节表。
     ⇒ 因此**不再走 `-c copy` 无损路径**：必须重编码（画上字）。
     **但只编码一趟** —— `drawtext` 直接挂在 concat 滤镜的各路输入上
     （详见 `encoder_args()` 与下方「体积踩坑」）。
  3. **★ 成片体积（重要教训）**：初版「每镜烧号（编码 1 趟）→ concat 拼接
     （再编码 1 趟）」两趟编码 + `-cq 20`，导致成片 **189 MB**，
     而烧号前的基线只有 **102 MB** ⇒ **帧更少、片更短、体积却涨 1.85 倍**。
     根因有二，**主因是 `-cq 20`**（实测源片仅 1784 kbps，CQ20 复压到 3878 kbps）：
       · **主因**：CQ20 对「已是 H3 有损产物」的输入过高，把编码噪声当细节全力保留。
         ⇒ 已按实测标定为 **CQ26**（1954 kbps ≈ 源 1.10×，SSIM 0.9887）。
       · **次因**：两趟编码的代际损失。
         ⇒ 已合并为**单趟**（drawtext 挂进 concat 滤镜），既省一遍编码、又免一次损失。
  4. **自动检测规格一致性**：若片段规格不同（例如将来超分过），
     先用 `scale/fps/setsar` 统一到 1056×608@24 —— 与「规格一致」时
     **走同一条转码路径**，只是多几个滤镜（不再有 `-c copy` 分支）。
  5. **镜号缺口检测**：缺号明确列出，但不阻止拼接（按现有镜号顺序拼）。
  6. 顺带生成**章节对轴表**（镜号 / 时长 / 起止时间点），便于剪辑对轴。
     ★ 章节表按**帧数 ÷ 24** 计算，**不用容器 duration** ——
     H3 容器 duration 含音频包尾巴（长 ~41ms/镜），累加会漂移 2.6s。
       ⚠️ 烧号后画面内容的起点/终点以本表为准（每段都被重编码）。

用法：
    py -3.10 OUTPUT/_concat_video.py                 # 拼到最后一镜（默认 OUTPUT/full_cut.mp4）
    py -3.10 OUTPUT/_concat_video.py --upto=50        # 只拼 1-50
    py -3.10 OUTPUT/_concat_video.py --out=OUTPUT/xx.mp4
    py -3.10 OUTPUT/_concat_video.py --list           # 只列将要拼的片段，不合并
    py -3.10 OUTPUT/_concat_video.py --no-burn        # ★ 不加镜号（沿用旧的无损 -c copy 行为）

环境变量：
    BURN_ENCODER=nvenc|x264   强制编码器（默认自动探测 nvenc，失败回退 x264）
    BURN_FONTSIZE=34          镜号字号
"""

import glob
import json
import os
import re
import shutil
import subprocess
import sys

# ★ 2026-09-19：Windows 控制台默认 GBK（cp936），打印 ✅/❌/★ 等非 GBK 字符
#   会抛 `UnicodeEncodeError` 并**让整个脚本在最后一步崩掉**
#   （README §6.8 #7「控制台中文乱码 ≠ 文件损坏」的姊妹坑：这次是真崩）。
#   ⇒ 统一把 stdout/stderr 切成 UTF-8，并对换行做兼容。
for _s in ("stdout", "stderr"):
    try:
        getattr(sys, _s).reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRS = ["01_paper_plane", "04_classroom_dusk", "06_trench",
        "07_rice_field", "08_train_dining", "05_classroom_night"]
TMP = os.path.join(ROOT, "OUTPUT", "_concat")
CHAP = os.path.join(ROOT, "OUTPUT", "_concat_chapters.txt")


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


# ── 镜号烧录（2026-09-19 新增，用户要求「每一帧都在右上角清晰显示镜号」）──
# 用途：成片逐帧可溯源 —— 用户/评审看到任何一帧都能直接报出镜号，
#       不必再靠时间码反查 `_concat_chapters.txt`。
BURN_FONT = "C:/Windows/Fonts/msyhbd.ttc"     # 微软雅黑 Bold（有中文字形，镜号用不到但保持通用）
BURN_FONTSIZE = 34                            # 1056×608 下 34px ≈ 画高 5.6%，足够清晰
BURN_MARGIN = 24                              # 距右边/上边像素


def drawtext_filter(shot_no):
    """生成单镜的 `drawtext` 滤镜串（右上角白色描边镜号）。

    ★ 写法要点：
      · `fontfile` 里的 `C:/...` 必须把盘符冒号转义成 `C\\:`（ffmpeg 滤镜语法要求）
      · `text='SHOT 019'` —— 三位补零，固定宽度，不会因镜号位数变化而左右跳动
      · `x=w-text_w-24` —— 用表达式贴右边距，而不是写死坐标
      · 描边 `borderw=3:bordercolor=black@0.85` —— 亮背景（雪地/白墙）下也能看清
      · `fix_bounds=1` 保证文字不出画
    """
    font = BURN_FONT.replace(":", r"\:")
    return (
        "drawtext=fontfile='%s':text='SHOT %03d':fontsize=%d:fontcolor=white:"
        "borderw=3:bordercolor=black@0.85:x=w-text_w-%d:y=%d:fix_bounds=1"
        % (font, shot_no, BURN_FONTSIZE, BURN_MARGIN, BURN_MARGIN)
    )


def encoder_args():
    """优选 GPU（h264_nvenc）；不可用则回退 libx264。环境变量 BURN_ENCODER 可强制。

    ★ 探测陷阱（2026-09-19 实测踩到）：
      NVENC **有最小分辨率限制**（64×64 会报 `Frame Dimension less than the
      minimum supported value`）。第一版探针用 `64x64` 空跑 ⇒ 永远失败 ⇒
      静默回退 CPU。**必须用真实分辨率（1056×608）探测**。
      另一条：`-f null -` 在部分 ffmpeg 版本下返回码不可靠 ⇒ 写出真实文件再删。

    ★★ 2026-09-19 码率标定（BURN_CQ 可覆盖，默认 26）★★
      背景：旧设置 `-cq 20` 让成片体积**膨胀到 189 MB**（基线 102 MB）。
      单镜实测（源 `01_girl_mother_at_school_gate_00003_.mp4`，本身 1784 kbps）：

          -cq 20   → 3878 kbps   SSIM 0.9939   （2.17× 源，纯浪费）
          -cq 23   → 2776 kbps   SSIM 0.9921
          -cq 24   → 2471 kbps   SSIM 0.9912
          -cq 26   → 1954 kbps   SSIM 0.9887   ← **本脚本采用（用户选定）**

      为什么 CQ20 是错的：CQ（恒定质量）是给**干净原片一次压缩**设计的。
      本项目输入是 **H3 生成的有损产物**，本身就带编码噪声；CQ20 会把噪声当
      「细节」尽全力保留 ⇒ 码率远超源片本身，纯属无效膨胀。
      **判据：复压后的码率不应显著超过源片段码率。**
      CQ26 复压码率 1954 kbps ≈ 源片 1784 kbps 的 1.10 倍 —— 既不再无效膨胀，
      又留了少量余量补偿重新编码的损失；SSIM 0.9887 仍属高质量区间。
    """
    force = os.environ.get("BURN_ENCODER", "").strip().lower()
    cq = os.environ.get("BURN_CQ", "").strip() or "26"
    NVENC = ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr",
             "-cq", cq, "-b:v", "0"]
    X264 = ["-c:v", "libx264", "-crf", cq, "-preset", "veryfast"]
    if force == "x264":
        return X264
    if force == "nvenc":
        return NVENC

    # 自动探测：按**真实输出分辨率**跑 0.2s 并写成真文件（比 -f null 可靠）
    tmp = os.path.join(TMP, "_enc_probe.mp4")
    probe = run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                 "color=c=black:s=1056x608:d=0.2:r=24"] + NVENC +
                ["-pix_fmt", "yuv420p", tmp])
    ok = probe.returncode == 0 and os.path.exists(tmp) \
        and os.path.getsize(tmp) > 0
    try:
        os.remove(tmp)
    except OSError:
        pass
    return NVENC if ok else X264



def probe(p):
    out = run(["ffprobe", "-v", "error", "-show_entries",
               "format=duration:stream=codec_type,codec_name,width,height,"
               "sample_rate,channels,r_frame_rate",
               "-of", "json", p])
    try:
        d = json.loads(out.stdout)
    except Exception:
        return None
    info = {"dur": float(d["format"]["duration"])}
    for s in d["streams"]:
        if s.get("codec_type") == "video":
            info.update(w=s.get("width"), h=s.get("height"),
                        vc=s.get("codec_name"), fps=s.get("r_frame_rate"))
        elif s.get("codec_type") == "audio":
            info.update(ac=s.get("codec_name"), sr=s.get("sample_rate"),
                        ch=s.get("channels"))
    return info


def nframes(p):
    """视频**帧数**（比容器 duration 可靠）。

    ★ 2026-09-19 踩坑：ComfyUI/H3 片段的容器 `format.duration` 比
      「帧数 ÷ 24」**长一点**（音频包尾巴），例如 73 帧 → 3.041016s 而非 3.0s。
      用它逐段累加做章节表，126 镜会累积 **~2.6s 误差**（实测 528.15 vs 实际 525.58），
      导致「按章节表时间点抽帧」会抽到**下一镜**（验收时表现为"镜号错位"）。
      ⇒ 章节表一律用**帧数 ÷ fps** 计算。
    """
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0",
               "-count_frames", "-show_entries", "stream=nb_read_frames",
               "-of", "csv=p=0", p])
    try:
        return int(out.stdout.strip())
    except (ValueError, AttributeError):
        return 0


def collect(upto=None):
    """按镜号收集产物：{镜号: 路径}（同号取 mtime 最新的）

    ⚠️ 必须排除：
      · `_bak_*`（擦除/重跑前的备份）
      · `_rejected/` 子目录（镜 14 多 seed 择优后的落选版本）
      · `*_delogo.mp4` / `*_temporal.mp4` / `*_split.mp4`（失败的临时文件）
    """
    found = {}
    for d in DIRS:
        for f in glob.glob(os.path.join(ROOT, "OUTPUT", d, "video", "*.mp4")):
            base = os.path.basename(f)
            if base.startswith("_bak_"):
                continue
            if re.search(r"_(delogo|temporal|split)\.mp4$", base):
                continue
            m = re.match(r"(\d+)_", base)
            if not m:
                continue
            n = int(m.group(1))
            if upto and n > upto:
                continue
            if n not in found or os.path.getmtime(f) > os.path.getmtime(found[n]):
                found[n] = f
    return found


def main():
    args = sys.argv[1:]
    upto = None
    out = os.path.join(ROOT, "OUTPUT", "full_cut.mp4")
    list_only = "--list" in args
    burn = "--no-burn" not in args          # ★ 默认烧镜号；--no-burn 回到旧的无损拼接
    for a in args:
        if a.startswith("--upto="):
            upto = int(a.split("=", 1)[1])
        elif a.startswith("--out="):
            v = a.split("=", 1)[1]
            out = v if os.path.isabs(v) else os.path.join(ROOT, v)

    found = collect(upto)
    if not found:
        print("没有找到任何产物")
        return 1
    shots = sorted(found)
    last = shots[-1]
    missing = [n for n in range(1, last + 1) if n not in found]

    print("=" * 70)
    print("镜号范围：1 - %d（%d 个片段）" % (last, len(shots)))
    print("区间内缺号：%s" % (missing if missing else "无 [OK]"))

    specs, rows, total = {}, [], 0.0
    for n in shots:
        info = probe(found[n])
        if not info:
            print("!! 镜 %d 探测失败：%s" % (n, found[n]))
            continue
        key = (info.get("w"), info.get("h"), info.get("vc"),
               info.get("ac"), info.get("sr"), info.get("ch"), info.get("fps"))
        specs.setdefault(key, []).append(n)
        total += info["dur"]
        rows.append((n, info["dur"], os.path.basename(found[n])))

    print("片段总时长：%.1f s（%.2f 分）" % (total, total / 60.0))
    print("规格分布：")
    for k, v in specs.items():
        print("   %sx%s %s / %s %sHz %sch @%s  -> %d 个镜 %s" % (
            k[0], k[1], k[2], k[3], k[4], k[5], k[6], len(v),
            (str(v[:8]) + "...") if len(v) > 8 else str(v)))
    uniform = len(specs) == 1

    if list_only:
        print("\n将要拼接（镜号 / 时长 / 文件）：")
        for n, d, fn in rows:
            print("  %3d  %5.2fs  %s" % (n, d, fn))
        return 0

    os.makedirs(TMP, exist_ok=True)
    os.makedirs(os.path.dirname(out), exist_ok=True)

    # ★ 2026-09-19：默认走「逐段烧镜号 → 统一转码 → 无损拼接」
    #   即便规格本来一致也走这条路（因为要画字，必须重编码）。
    #   规格不一致时只是多挂 scale/fps/setsar 三个滤镜。
    parts = []
    if burn:
        enc = encoder_args()
        print("\n[烧镜号] 单趟 concat：%s%s" % (
            enc[1], "（GPU）" if "nvenc" in enc[1] else "（CPU）"))
        if not uniform:
            print("   ⚠️ 片段规格不一致 ⇒ 追加 scale=1056:608,fps=24,setsar=1 统一规格")

        # ★★★ 2026-09-19 体积膨胀修复：**把「烧号」与「拼接」合并成单趟编码** ★★★
        #
        # 问题（实测）：旧实现是两趟编码 ——
        #   第 1 趟：每镜 `-i seg -vf drawtext -cq 20 burn_NNN.mp4`   （编码 1）
        #   第 2 趟：`-i burn_*.mp4 ... -filter_complex concat -cq 20` （编码 2）
        # 实测体积：full_cut.mp4 = 189.3 MB / 2883 kbps，
        #   而烧号前的基线 full_cut.pre_audit.mp4 = 102.1 MB / 1308 kbps
        #   ⇒ **帧数更少（12615 < 14230）、片更短（528s < 593s），体积却涨 1.85 倍**。
        #
        # 根因（两个叠加）：
        #   ① **代际损失**：H3 产物本身就是有损压缩、带编码噪声。第 1 趟用 CQ20 把噪声
        #      「固化成细节」，第 2 趟为了在这些假细节上保住 CQ20，只能**狂提码率**。
        #      注意**源片段自己才 1784 kbps**，我复压到 2883 kbps 明显不合理。
        #   ② 双趟 = 每个像素被编码两次，误差累积。
        #
        # ✅ 正解：烧号不必单独一趟 —— 把 `drawtext` 直接挂到 **concat 滤镜的每一路输入**上，
        #    只编码一次。实测体积回落到与基线同级（见文件头 §烧号体积）。
        #
        # ★ 实现细节：126 路输入 + 126 个 drawtext 的 filtergraph 约 20 KB，
        #   逼近 Windows 命令行 ~32 KB 上限 ⇒ 必须用 `-filter_complex_script` 从**文件**读，
        #   而不是 `-filter_complex` 直接塞命令行（ffmpeg 原生支持，无长度限制）。
        #
        # ★ 保留「必须用 concat 滤镜、不能用 concat demuxer + copy」这条教训：
        #   ComfyUI/H3 产出的片段，**容器 duration 比「帧数 ÷ 24」长一点**
        #   （音频包尾巴），例如 73 帧的视频 duration=**3.041016** 而非 3.000000。
        #   `-f concat -c copy` 按**容器时长**推进时间轴 ⇒ 每个镜边界多推 41ms，
        #   实测 3 段拼接后帧间隔统计：
        #       41.7ms × 250  +  72.0ms × 1  +  63.3ms × 1
        #   ⇒ **每个镜头切换处有 1 帧被多停了 ~30ms**（126 镜 = 126 处微卡顿）。
        #   试过 `-video_track_timescale`（段级 / 输出级、1/12288 / 1/24000）**均无效**。
        #   ✅ concat 滤镜按**实际解码帧**重排时间轴，实测全片间隔一致，零卡顿。
        n = len(shots)
        fin = []
        for fn_ in (found[s] for s in shots):
            fin += ["-i", fn_]
        chains = []
        for i, s in enumerate(shots):
            vf = [drawtext_filter(s)]
            if not uniform:
                vf = ["scale=1056:608", "fps=24", "setsar=1"] + vf
            chains.append("[%d:v]%s[v%d]" % (i, ",".join(vf), i))
        fc = (";".join(chains) + ";"
              + "".join("[v%d]" % i for i in range(n))
              + "concat=n=%d:v=1:a=0[v];" % n
              + "".join("[%d:a]" % i for i in range(n))
              + "concat=n=%d:v=0:a=1[a]" % n)
        fcfile = os.path.join(TMP, "filtergraph.txt")
        with open(fcfile, "w", encoding="utf-8") as f:
            f.write(fc)
        print("  [单趟] %d 路 drawtext + concat 滤镜（filtergraph %.1f KB 走文件）"
              % (n, len(fc) / 1024.0))
        cmd = (["ffmpeg", "-y", "-v", "error"] + fin +
               ["-filter_complex_script", fcfile, "-map", "[v]", "-map", "[a]"] + enc +
               ["-c:a", "aac", "-ar", "32000", "-ac", "2",
                "-movflags", "+faststart", out])
        r = run(cmd)
        if r.returncode != 0:
            print("烧号+拼接失败：\n%s" % (r.stderr or "")[:1500])
            return 1
        # ★ 章节表按**源片段的帧数**重算（不用容器 duration，见 nframes()）。
        #   单趟编码后每段帧数 = 源段的**实际解码帧数**（fps 已统一为 24），
        #   故直接对源文件数帧即可，与成片逐段对齐。
        rows = [(s, nframes(found[s]) / 24.0, os.path.basename(found[s]))
                for s in shots]

    elif uniform:
        lst = os.path.join(TMP, "list.txt")
        with open(lst, "w", encoding="utf-8") as f:
            for n in shots:
                f.write("file '%s'\n" % found[n].replace("\\", "/"))
        print("\n[无损拼接] ffmpeg -f concat -c copy  ->  %s" % os.path.relpath(out, ROOT))
        r = run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                 "-i", lst, "-c", "copy", "-movflags", "+faststart", out])
        if r.returncode != 0:
            print("拼接失败：\n%s" % (r.stderr or "")[:1500])
            return 1
        rows = [(n, nframes(found[n]) / 24.0, os.path.basename(found[n]))
                for n in shots]
    else:
        print("\n!! 片段规格不一致，回退到「统一转码后拼接」（较慢、会轻微损失画质）")
        for n in shots:
            seg = os.path.join(TMP, "seg_%03d.mp4" % n)
            r = run(["ffmpeg", "-y", "-v", "error", "-i", found[n],
                     "-vf", "scale=1056:608,fps=24,setsar=1",
                     "-c:v", "libx264", "-crf", "16", "-preset", "medium",
                     "-c:a", "aac", "-ar", "32000", "-ac", "2", seg])
            if r.returncode != 0:
                print("转码失败 镜 %d：%s" % (n, (r.stderr or "")[:400]))
                return 1
            parts.append(seg)
        lst = os.path.join(TMP, "list_norm.txt")
        with open(lst, "w", encoding="utf-8") as f:
            for s in parts:
                f.write("file '%s'\n" % s.replace("\\", "/"))
        r = run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                 "-i", lst, "-c", "copy", "-movflags", "+faststart", out])
        if r.returncode != 0:
            print("拼接失败：\n%s" % (r.stderr or "")[:1500])
            return 1

    t = 0.0
    with open(CHAP, "w", encoding="utf-8") as f:
        f.write("# 合成片章节对轴表（%s）\n" % os.path.basename(out))
        if burn:
            f.write("# ★ 右上角已烧录镜号（SHOT NNN）⇒ 看到任意一帧可直接报镜号\n")
        else:
            f.write("# ⚠️ 本片未烧镜号（--no-burn）；对轴请用时间码\n")
        f.write("# 镜号\t片长(s)\t起点\t终点\t文件\n")
        for n, d, fn in rows:
            f.write("%d\t%.4f\t%.4f\t%.4f\t%s\n" % (n, d, t, t + d, fn))
            t += d
        f.write("# 合计\t%.4f\n" % t)

    info = probe(out)
    print("-" * 70)
    if info:
        print("产物：%s" % os.path.relpath(out, ROOT))
        print("      %sx%s %s / %s %sHz %sch @%s" % (
            info.get("w"), info.get("h"), info.get("vc"), info.get("ac"),
            info.get("sr"), info.get("ch"), info.get("fps")))
        print("      时长 %.1f s（%.2f 分）  大小 %.1f MB  %d 个镜（1-%d）" % (
            info["dur"], info["dur"] / 60.0,
            os.path.getsize(out) / 1048576.0, len(shots), last))

        # ★ 闸门：章节表合计必须等于「成片总帧数 ÷ 24」
        #   （2026-09-19 新增：此前章节表用容器 duration 累加，虚高 2.6s，
        #    按它抽帧会抽到下一镜 —— 这类"静默偏移"必须被自动拦住）
        tot_f = nframes(out)
        tot_sec = tot_f / 24.0
        drift = t - tot_sec
        print("-" * 70)
        print("章节表合计 %.4fs  vs  成片 %d 帧 = %.4fs   偏差 %+.4fs  %s"
              % (t, tot_f, tot_sec, drift,
                 "[OK]" if abs(drift) < 0.05 else "[!! 偏差过大，检查章节表]"))
        if abs(drift) >= 0.05:
            print("  ⚠️ 抽帧验收会错位 —— 请检查 rows 是否用了容器 duration")

    print("镜号烧录：%s" % ("✅ 右上角 SHOT NNN" if burn else "❌ 未烧（--no-burn）"))
    print("章节对轴表：%s" % os.path.relpath(CHAP, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
