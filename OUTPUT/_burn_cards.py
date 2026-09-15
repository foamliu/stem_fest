# -*- coding: utf-8 -*-
"""字幕镜后期叠加 —— 用 ffmpeg 把**中文文本**烧进 H3 生成的纯色底片。

★ 为什么必须这么做（2026-09-15 实测）
    H3 **写不对中文长句**：
      · 镜 123：应出 3 行，实际只出 2 行（第 3 行丢了）
      · 镜 124：「谨以此片，献给所有替我们扛过的人」（**旧文案**，2026-09-15 已改为「…扛过**风雨**的人」）被写成
        **「幔夹 晋懋乇人陁此的」**（同一次生成里另一帧却写对了）
    ⇒ 与"prompt 污染"（元信息被渲染）是**两类不同问题**：
      污染可靠改 prompt 修；**乱码是模型能力上限，改 prompt 修不掉**。
    ⇒ 字幕镜的正确做法：**H3 只出纯色/纯画面底片，中文用 ffmpeg 烧上去**（100% 可控）。

文本来源
    `storyboard.md` 的「台词/音效」列；本脚本的 `CARDS` 里按镜号写死。
    ⚠️ 写死是有意的：**字幕是人工锁定项**，不该让模型自由发挥。

用法
    py -3.10 OUTPUT/_burn_cards.py --dry            # 只打印将要烧的字幕
    py -3.10 OUTPUT/_burn_cards.py --shots=123,124  # 真烧（输出 *_card.mp4）
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")

# 镜号 → (幕目录, 底片文件名, [3 行文本])
#   底片用 H3 生成的纯黑/纯色镜；文本是**权威文案**，不许模型代笔。
CARDS = {
    123: ("05_classroom_night", "123_black_screen_three_lines_00002_.mp4", [
        "一个名字，记了七十四年。",
        "一株稻子，找了一辈子。",
        "一个口罩，等了三年。",
    ]),
    124: ("05_classroom_night", "124_three_lines_fade_last_line_00002_.mp4", [
        "上汇实验学校 · 刘思齐 刘思成 徐畅景 张书扬",
        "谨以此片，献给所有替我们扛过风雨的人",
    ]),
}

FONT = r"C:\Windows\Fonts\msyh.ttc"     # 微软雅黑（含中文）


def esc(p):
    """ffmpeg drawtext 的路径转义（Windows 盘符冒号必须转义）。"""
    return p.replace("\\", "/").replace(":", r"\:")


def main():
    dry = "--dry" in sys.argv
    only = None
    for a in sys.argv[1:]:
        if a.startswith("--shots="):
            only = set(int(x) for x in a.split("=", 1)[1].split(","))
    if not os.path.exists(FONT):
        print("!! 找不到字体 %s" % FONT)
        return 2

    for shot, (act, src, lines) in sorted(CARDS.items()):
        if only and shot not in only:
            continue
        sp = os.path.join(OUT, act, "video", src)
        if not os.path.exists(sp):
            print("镜 %d：缺少底片 %s，跳过" % (shot, src))
            continue
        n = len(lines)
        # ★ 关键：H3 底片**自带文字**（有的正确、有的是乱码），
        #   直接叠加会**重叠糊成一团**（2026-09-15 实测镜 124）。
        #   ⇒ 先铺**不透明纯黑**盖掉底片全部内容，再烧我们的权威文案。
        #   音轨从原片 copy（保底噪），画面完全由我们控制。
        parts = ["drawbox=x=0:y=0:w=iw:h=ih:color=black@1:t=fill"]
        for i, t in enumerate(lines):
            off = (i - (n - 1) / 2.0) * 0.12
            y = "h*(0.5%+.3f)" % off if off >= 0 else "h*(0.5%.3f)" % off
            parts.append(
                "drawtext=fontfile='%s':text='%s':fontcolor=white:fontsize=44:"
                "x=(w-text_w)/2:y=%s:shadowcolor=black@0.7:shadowx=2:shadowy=2"
                % (esc(FONT), t.replace(":", r"\:").replace("'", r"\'"), y))
        dst = os.path.join(OUT, act, "video",
                           src.replace(".mp4", "_card.mp4"))
        cmd = ["ffmpeg", "-y", "-v", "error", "-i", sp,
               "-vf", ",".join(parts), "-c:a", "copy", dst]
        print("镜 %d：%d 行 → %s" % (shot, n, os.path.basename(dst)))
        for t in lines:
            print("      %s" % t)
        if dry:
            continue
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if r.returncode != 0:
            print("      !! ffmpeg 失败：%s" % (r.stderr or "")[-300:])
        else:
            print("      OK %.1f KB" % (os.path.getsize(dst) / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
