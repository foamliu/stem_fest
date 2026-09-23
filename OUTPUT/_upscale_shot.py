# -*- coding: utf-8 -*-
"""把单镜（默认镜 99）从低分辨率超分/缩放到成片标准规格 1056x608。

背景（2026-09-17 事故）
    镜 99 是 10s 长台词镜，用 0.6 MP + 20 步跑出 torch.OutOfMemoryError
    （16GB VRAM，243 帧是临界点；镜 97 的 227 帧刚好能过）。
    降到 --mp=0.4 才跑通，但输出变成 864x480 —— 与其余 125 镜的
    1056x608 不一致，会触发 _concat_video.py 的「全片重转码」兜底，
    为一镜损失整片画质，不可接受。

本脚本的作用
    只把这**一镜**用高质量缩放（lanczos）升到 1056x608，其余 125 镜
    保持原样 → 全片重新回到「无损 concat -c copy」路径。

⚠️ 这是**恢复规格**不是「真超分」：864x480 → 1056x608 是 1.22x 放大，
   细节不会凭空长出来。若要真超分（ESRGAN 类）需另配模型，本脚本不做。

用法：
    py -3.10 OUTPUT/_upscale_shot.py 99              # 写真·默认 act4 目录
    py -3.10 OUTPUT/_upscale_shot.py 99 --dry        # 只看会做什么
    py -3.10 OUTPUT/_upscale_shot.py 99 --crf=14     # 指定质量（默认 14）
"""
import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

W, H, FPS = 1056, 608, 24

# 幕目录映射（与 _concat_video.py 保持一致）
ACT_DIRS = {
    "01_paper_plane": (1, 9),
    "03_classroom_day": (10, 18),
    "06_trench": (19, 46),
    "07_rice_field": (47, 74),
    "08_train_dining": (75, 105),
    "05_classroom_night": (106, 126),
}


def find_shot(shot):
    """按镜号找最新版本文件（排除 _bak）。"""
    for d in ACT_DIRS:
        video_dir = os.path.join(ROOT, "OUTPUT", d, "video")
        if not os.path.isdir(video_dir):
            continue
        cands = []
        for fn in os.listdir(video_dir):
            if not fn.startswith("%d_" % shot) or not fn.endswith(".mp4"):
                continue
            if "_bak" in fn:
                continue
            cands.append(os.path.join(video_dir, fn))
        if cands:
            cands.sort(key=os.path.getmtime)
            return cands[-1], [os.path.basename(c) for c in cands]
    return None, []


def probe(path):
    """读分辨率 / 时长 / 帧率。"""
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=width,height,r_frame_rate",
           "-show_entries", "format=duration", "-of", "csv=p=0", path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return None
    lines = [x for x in r.stdout.strip().split("\n") if x]
    w = h = fps = dur = None
    for ln in lines:
        p = ln.split(",")
        if len(p) == 3:
            w, h, fps = int(p[0]), int(p[1]), p[2]
        elif len(p) == 1 and p[0].replace(".", "").isdigit():
            dur = float(p[0])
    return dict(w=w, h=h, fps=fps, dur=dur)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("shot", type=int)
    ap.add_argument("--crf", type=int, default=14,
                    help="x264 质量，越小越好（默认 14，成片主档为 16）")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    src, allv = find_shot(a.shot)
    if not src:
        print("!! 找不到镜 %d 的任何 mp4" % a.shot)
        return 1

    print("镜 %d 候选版本（按 mtime 升序）：" % a.shot)
    for fn in allv:
        print("   %s" % fn)
    info = probe(src)
    print("\n选用：%s" % os.path.basename(src))
    print("  当前规格：%sx%s @%s  时长 %.2fs" % (info["w"], info["h"], info["fps"], info["dur"]))

    if info["w"] == W and info["h"] == H:
        print("\n已是标准规格 %dx%d，无需处理。" % (W, H))
        return 0

    newname = os.path.basename(src).replace(".mp4", "_norm.mp4")
    dst = os.path.join(os.path.dirname(src), newname)
    scale = "%d:%d:flags=lanczos" % (W, H)

    cmd = ["ffmpeg", "-y", "-v", "error", "-i", src,
           "-vf", "scale=%s,fps=%d,setsar=1" % (scale, FPS),
           "-c:v", "libx264", "-crf", str(a.crf), "-preset", "slow",
           "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-ar", "32000", "-ac", "2", "-b:a", "128k",
           "-movflags", "+faststart", dst]

    print("\n缩放：%dx%d -> %dx%d（lanczos，CRF %d）" % (info["w"], info["h"], W, H, a.crf))
    print("输出：%s" % newname)
    if a.dry:
        print("\n[dry] 未执行。命令：\n  %s" % " ".join(cmd))
        return 0

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("!! ffmpeg 失败：\n%s" % (r.stderr or "")[:1200])
        return 1

    got = probe(dst)
    print("  产出规格：%sx%s @%s  时长 %.2fs  %.0f KB" % (
        got["w"], got["h"], got["fps"], got["dur"],
        os.path.getsize(dst) / 1024.0))

    ok = (got["w"] == W and got["h"] == H and abs(got["dur"] - info["dur"]) < 0.05)
    print("\n%s 规格恢复%s" % ("✅" if ok else "⚠️", "成功" if ok else "异常，请人工核对"))

    print("\n下一步：让 _concat_video.py 优先取用 _norm 版本 ——")
    print("  它按 mtime 取最新，_norm 文件刚生成所以会被选中；")
    print("  若未被选中，请确认 _norm 的 mtime 是最新的。")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
