# -*- coding: utf-8 -*-
"""实验：把镜 14 改成「镜 7 式」禁令写法（禁令嵌在画面段内、后接缓冲画面语）。

假设（2026-09-16 定位）：
  镜 7 是唯一修好的镜，其禁令**嵌在画面描述行内**、后面还有画面语；
  8 个失败镜的禁令**独占一行且紧贴台词行**。
  ⇒ 正确的 R3 形式应是「画面段末句；★ 禁令，<画面语>。\n 台词行」

用法：
  py -3.10 OUTPUT/_exp_s14_inline.py --dry     # 预览
  py -3.10 OUTPUT/_exp_s14_inline.py --apply   # 落盘
"""
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "OUTPUT", "_diag_act2_startup.py")

# 用正则匹配「镜头轻微向前缓推（slow dolly in）。\n」+ 禁令行 + Audio 行
PAT = re.compile(
    r'(?P<indent>[ \t]*)'
    r'(?:\+ LIGHT \+ "\.镜头轻微向前缓推（slow dolly in）。\\\\n")\n'
    r'(?P=indent)"★ 全画面不得出现任何可读的文字、字幕或符号。\\\\n"\n'
    r'(?P=indent)"Audio: '
)

NEW = (
    '{indent}+ LIGHT + "。镜头轻微向前缓推（slow dolly in）；"\n'
    '{indent}"★ 全画面不得出现任何可读的文字、字幕或符号，"\n'
    '{indent}"这是一间普通教室，墙面与屏幕上没有文字，人物脸上只有表演。\\\\n"\n'
    '{indent}"Audio: '
)


def main():
    lines = open(P, encoding="utf-8").read().split("\n")
    # 定位镜 14 block
    start = None
    for i, L in enumerate(lines):
        if L.startswith("TASKS[14] = dict("):
            start = i
            break
    if start is None:
        print("!! 找不到 TASKS[14]")
        return 1
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("TASKS[") or lines[j].startswith("def "):
            end = j
            break

    guard_idx = None
    for k in range(start, end):
        if "★ 全画面不得" in lines[k]:
            guard_idx = k
            break
    if guard_idx is None:
        print("!! 镜 14 内找不到禁令行")
        return 1

    ind = lines[guard_idx][:len(lines[guard_idx]) - len(lines[guard_idx].lstrip())]
    prev = lines[guard_idx - 1]
    print("【原 禁令行 %d】 %s" % (guard_idx + 1, lines[guard_idx]))
    print("【原 上一行 %d】 %s" % (guard_idx, prev))

    SUF = "\\n\""          # 文件里真实存在的 3 个字符：\ n "
    if not prev.rstrip().endswith(SUF):
        print("!! 上一行结尾不是「\\n\"」，实际：%r，中止以避免误改。"
              % prev[-16:])
        return 1

    # 1) 上一行「…\n"」→「…；★ 禁令，缓冲画面语。\n"」，并把原独立禁令行删掉
    lines[guard_idx - 1] = (
        prev.rstrip()[:-len(SUF)] +
        '；★ 全画面不得出现任何可读的文字、字幕或符号，'
        '这是一间普通教室、墙面与屏幕上没有文字，人物脸上只有表演。' + SUF
    )
    # 2) 删掉原来的独立禁令行
    del lines[guard_idx]

    out = "\n".join(lines)
    if "--apply" not in sys.argv:
        print("\n【改写后】")
        for k in range(start, end):
            if k - 1 < len(lines) and (lines[k].strip() or lines[k - 1].strip()):
                print("%4d | %s" % (k + 1, lines[k]))
        print("（预览模式，加 --apply 落盘）")
        return 0
    shutil.copy2(P, P + ".inlinetest.bak")
    open(P, "w", encoding="utf-8", newline="").write(out)
    print("\n已落盘，备份 %s.inlinetest.bak" % os.path.basename(P))
    return 0


if __name__ == "__main__":
    sys.exit(main())
