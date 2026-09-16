# -*- coding: utf-8 -*-
"""把泄漏镜的禁令从「独占一行」改成「镜 7 式：嵌在画面段内 + 缓冲画面语」。

★ 实验依据（2026-09-16）：
  · 镜 7（唯一修好）：禁令**嵌在画面描述行内**，其后还有画面语，台词独立下一行 → ✅ 0 泄漏
  · 8 个泄漏镜：禁令**独占一行、紧贴台词行** → ❌ 8/8 帧仍泄漏（镜 14 实测）
  ⇒ 有效形式 = `画面段末句；★ 禁令，<画面语>。\n 台词行`

用法：
  py -3.10 OUTPUT/_fix_guard_inline.py           # 预览
  py -3.10 OUTPUT/_fix_guard_inline.py --apply   # 落盘（.inline.bak 备份）
  py -3.10 OUTPUT/_dump_prompt.py <镜号>          # 复查结构（应为 2 行）
"""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGETS = {
    21: "_diag_act1_trench.py", 36: "_diag_act1_trench.py",
    77: "_diag_act4_train.py", 85: "_diag_act4_train.py",
    86: "_diag_act4_train.py", 88: "_diag_act4_train.py",
    112: "_diag_act5_finale.py",
}
GUARD = "★ 全画面不得出现任何可读的文字、字幕或符号。"
SUF = "\\n\""                        # 文件里真实的 3 字符：\ n "
BUFFER = "画面上没有任何文字、字幕或标识，人物脸上只有表演。"


def task_bounds(lines, shot):
    start = None
    for i, L in enumerate(lines):
        if L.startswith("TASKS[%d] = dict(" % shot):
            start = i
            break
    if start is None:
        return None, None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("TASKS[") or lines[j].startswith("def "):
            end = j
            break
    return start, end


def fix_file(path, shots, apply_):
    lines = open(path, encoding="utf-8").read().split("\n")
    changes = []
    for shot in shots:
        st, en = task_bounds(lines, shot)
        if st is None:
            print("  镜 %d 未找到" % shot)
            continue
        gi = None
        for k in range(st, en):
            if GUARD in lines[k]:
                gi = k
                break
        if gi is None:
            print("  镜 %d 内无禁令行（可能已内联）" % shot)
            continue
        prev = lines[gi - 1]
        if not prev.rstrip().endswith(SUF):
            print("  镜 %d 上一行结尾异常：%r" % (shot, prev[-16:]))
            continue
        if "★" in prev:
            print("  镜 %d 上一行已含禁令，跳过" % shot)
            continue
        body = prev.rstrip()[:-len(SUF)]
        if body.endswith("。"):
            body = body[:-1] + "；"
        lines[gi - 1] = body + GUARD + BUFFER + SUF
        del lines[gi]
        changes.append(shot)
    if changes and apply_:
        shutil.copy2(path, path + ".inline.bak")
        open(path, "w", encoding="utf-8", newline="").write("\n".join(lines))
    return changes


def main():
    apply_ = "--apply" in sys.argv
    want = [int(a) for a in sys.argv[1:] if a.isdigit()]
    by_file = {}
    for shot, f in sorted(TARGETS.items()):
        if want and shot not in want:
            continue
        by_file.setdefault(f, []).append(shot)
    total = []
    for f, shots in by_file.items():
        p = os.path.join(ROOT, "OUTPUT", f)
        print("== %s  镜 %s" % (f, shots))
        ch = fix_file(p, shots, apply_)
        for s in ch:
            print("   镜 %-4d -> 禁令内联入画面段" % s)
        total += ch
    print("-" * 60)
    print("共 %d 镜%s" % (len(total),
                         "（已落盘）" if apply_ else "（预览，加 --apply）"))


if __name__ == "__main__":
    main()
