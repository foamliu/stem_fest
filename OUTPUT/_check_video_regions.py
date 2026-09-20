# -*- coding: utf-8 -*-
"""视频帧区域色彩量化 —— ★ 常驻工具：`新旧片段谁的时令/光线更对`。

★ 由来（2026-09-20，README §6.10.16 / §8 待重跑台账）：
   第一幕《上甘岭》重跑 7 镜（20/21/22/31/37/41/46）后，需要**逐镜**确认
   新片段真的变成了「深秋有太阳」，而不是只信眼睛。
   片段里主体（人物/土地）只占画面一部分，**全图均值会被大面积天空/沙袋拉走** ⇒
   必须**按区域**量化（同 `_check_trench_regions.py` 的纪律）。

## 判据（与场景图那一套保持同一口径）
   · 中景 R-B 升高       → 更暖（秋色）        【硬条件】
   · 中景亮度升高        → 有太阳（不是阴天漫射）【参考】
   · 天空 R-B 不降为负   → 天空没变冷蓝        【软条件】

★ 软条件说明（2026-09-20，镜 21 实例）：
   低角度近景／特写镜里，顶部那条「天空带」压根不是天空 —— 镜 21（蹲下看野菜）
   顶部取样带落在**背景枯黄草坡+远树影**上：旧版此处是绿树荫（R-B 高），
   新版换成暖黄枯草背景后 R-B 反而下降 ⇒ 报 CHECK，实为误报，人眼复核已 PASS。
   故本工具**以「中景」为硬条件**，天空带仅在**中景未达标**时才用来辅助判断；
   中景达标且天空带为负时，打印 `PASS(软条件存疑)` 并提示做一次人眼复核，
   不再直接判 CHECK（避免低角度镜系统性误判）。

## 用法
   py -3.10 OUTPUT/_check_video_regions.py --shots=20
   py -3.10 OUTPUT/_check_video_regions.py --shots=20,21,22,31,37,41,46
   py -3.10 OUTPUT/_check_video_regions.py --shots=20 --keep \
       --sky=0.0,0.18,0.30,0.95 --gnd=0.45,1.0,0.0,1.0

★ 取样区默认「天空在上、中景在下」，特写/低角度镜构图不同，可用 --sky/--gnd 调整；
   **判定看「同一区域新旧对比」**，区域选得偏一点不影响结论（新旧用同一区域即可）。
"""
import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
from PIL import Image

ROOT = r"E:\code\stem_fest"
DEFAULT_DIR = os.path.join(ROOT, "OUTPUT", "06_trench", "video")


def probe_ffmpeg():
    exe = shutil.which("ffmpeg")
    if not exe:
        sys.exit("[FAIL] 找不到 ffmpeg（请确认已加入 PATH）")
    return exe


def grab_frame(ffmpeg, path, t_ratio, dst):
    """按片段相对位置 t_ratio（0~1）抽一帧到 dst。"""
    p = subprocess.run([ffmpeg, "-hide_banner", "-i", path],
                       capture_output=True, text=True, errors="replace")
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", p.stderr)
    if not m:
        return None
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    t = max(0.05, dur * t_ratio)
    r = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                        "-ss", "%.2f" % t, "-i", path, "-frames:v", "1", dst],
                       capture_output=True, text=True, errors="replace")
    return dst if r.returncode == 0 and os.path.exists(dst) else None


def region(a, r0, r1, c0, c1):
    h, w, _ = a.shape
    return a[int(r0 * h):int(r1 * h), int(c0 * w):int(c1 * w)].reshape(-1, 3)


def parse_rect(s, default):
    if not s:
        return default
    try:
        v = tuple(float(x) for x in s.split(","))
        return v if len(v) == 4 else default
    except ValueError:
        return default


def stat(img_path, sky_r, gnd_r):
    a = np.asarray(Image.open(img_path).convert("RGB"), dtype=np.float32) / 255.0
    return region(a, *sky_r).mean(0) * 255, region(a, *gnd_r).mean(0) * 255


def versions_for(d, shot_id):
    """返回该镜号所有片段（按版本号升序）。"""
    pat = re.compile(r"^%d_.*_(\d{5})_\.mp4$" % shot_id)
    hits = []
    for p in glob.glob(os.path.join(d, "*.mp4")):
        m = pat.match(os.path.basename(p))
        if m:
            hits.append((int(m.group(1)), p))
    return [p for _, p in sorted(hits)]


def pick_version(d, shot_id, suffix):
    """按显式版本号取片段；suffix 形如 '00003'。找不到返回 None。"""
    if not suffix:
        return None
    cands = [p for p in versions_for(d, shot_id)
             if re.search(r"_%s_\.mp4$" % suffix, os.path.basename(p))]
    return cands[0] if cands else None


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--shots", default="20", help="镜号，逗号分隔（如 20,21,22）")
    ap.add_argument("--dir", default=None, help="片段目录（相对项目根或绝对）")
    ap.add_argument("--sky", default=None, help="天空取样 行起,行止,列起,列止（0~1）")
    ap.add_argument("--gnd", default=None, help="中景取样 行起,行止,列起,列止（0~1）")
    ap.add_argument("--keep", action="store_true", help="保留抽出的帧图")
    ap.add_argument("--old-suffix", default=None,
                    help="指定旧版版本号（如 00001）；默认自动取倒二版本")
    ap.add_argument("--new-suffix", default=None,
                    help="指定新版版本号（如 00002,00003，逗号分隔时逐镜顺次对应）")
    args, _ = ap.parse_known_args()

    ffmpeg = probe_ffmpeg()
    d = args.dir or DEFAULT_DIR
    if not os.path.isabs(d):
        d = os.path.join(ROOT, d)
    sky_r = parse_rect(args.sky, (0.02, 0.18, 0.30, 0.95))
    gnd_r = parse_rect(args.gnd, (0.45, 1.00, 0.00, 1.00))
    shots = [int(x) for x in re.split(r"[,\s]+", args.shots) if x.strip()]

    outdir = os.path.join(ROOT, "OUTPUT", "_autumn_check", "video_frames")
    os.makedirs(outdir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="vrf_")

    print("目录：%s" % d)
    print("取样：SKY 行 %.2f~%.2f / 列 %.2f~%.2f ｜ MID 行 %.2f~%.2f / 列 %.2f~%.2f"
          % (sky_r + gnd_r))
    passed = checked = skipped = 0

    for sid in shots:
        vs = versions_for(d, sid)
        if len(vs) < 2:
            print("\n[镜 %d] 版本不足（找到 %d 个）→ 跳过" % (sid, len(vs)))
            skipped += 1
            continue
        old, new = vs[-2], vs[-1]
        if args.old_suffix:
            hit = pick_version(d, sid, args.old_suffix)
            if hit:
                old = hit
        if args.new_suffix:
            # 多镜时逐镜顺次对应（20→00002, 21→00003 …）；单镜可用逗号给多个（取末个）
            suffs = [s.strip() for s in args.new_suffix.split(",") if s.strip()]
            idx = shots.index(sid)
            want = suffs[min(idx, len(suffs) - 1)] if suffs else None
            if len(shots) == 1 and len(suffs) > 1:
                want = suffs[-1]
            hit = pick_version(d, sid, want)
            if hit:
                new = hit
        print("\n[镜 %d] %s  →  %s" % (sid, os.path.basename(old), os.path.basename(new)))
        res = {}
        for tag, path in (("old", old), ("new", new)):
            dst = os.path.join(tmp, "%s_%d.png" % (tag, sid))
            got = grab_frame(ffmpeg, path, 0.6, dst)
            res[tag] = stat(got, sky_r, gnd_r) if got else None
            if got and args.keep:
                shutil.copy2(got, os.path.join(outdir, "s%d_%s.png" % (sid, tag)))
        if not (res.get("old") and res.get("new")):
            print("  抽帧失败 → 跳过")
            skipped += 1
            continue

        (osm, ogm), (nsm, ngm) = res["old"], res["new"]
        print("  %-5s %-18s %-18s %-9s %-9s"
              % ("", "sky RGB", "mid RGB", "skyLum", "midLum"))
        for tag, (sm, gm) in (("OLD", (osm, ogm)), ("NEW", (nsm, ngm))):
            print("  %-5s %-18s %-18s %-9.1f %-9.1f"
                  % (tag, "%.0f/%.0f/%.0f" % tuple(sm),
                     "%.0f/%.0f/%.0f" % tuple(gm), sm.mean(), gm.mean()))
        dmid_lum = ngm.mean() - ogm.mean()
        dmid_rb = (ngm[0] - ngm[2]) - (ogm[0] - ogm[2])
        dsky_rb = (nsm[0] - nsm[2]) - (osm[0] - osm[2])
        print("  中景亮度 %+.1f ｜ 中景 R-B %+.1f ｜ 天空 R-B %+.1f"
              % (dmid_lum, dmid_rb, dsky_rb))
        # 白屏/近白过渡镜（如镜 46 白屏日记）：画面本就纯白，R-B 恒为 0，
        # 本脚本的「暖化」指标在此**不适用**，不能判 PASS 也不能判 CHECK。
        # 判据：新旧两版中景亮度都 > 200 且三通道差 < 6（纯白特征）。
        def _is_white(rgb):
            return min(rgb) > 200 and (max(rgb) - min(rgb)) < 6
        if _is_white(ogm) and _is_white(ngm):
            print("  判定：N/A 白屏过渡镜（中景 %d/%d/%d ≈ 纯白）—— "
                  "本镜画面即白底字幕，暖化指标不适用，请改用字幕/文字核对"
                  % tuple(int(v) for v in ngm))
            skipped += 1
            continue
        # 硬条件：中景 R-B 升高（更暖）。天空带只作软条件 —— 低角度/特写镜
        # 顶部往往不是天空而是背景景物，R-B 天然会降，不应据此判 CHECK。
        if dmid_rb > 0:
            if dsky_rb < -2:
                verdict = "PASS(软条件存疑) 中景已转暖，但顶部带 R-B %+.1f —— 若为低角度/特写镜，顶部多为背景景物，建议人眼复核一次" % dsky_rb
            else:
                verdict = "PASS 更暖"
            ok = True
        else:
            verdict = "CHECK 中景未转暖，需人眼复核"
            ok = False
        print("  判定：%s" % verdict)
        checked += 1
        passed += 1 if ok else 0

    print("\n汇总：PASS=%d / 有效对比=%d  跳过=%d" % (passed, checked, skipped))
    if args.keep:
        print("帧图：%s" % outdir)
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
