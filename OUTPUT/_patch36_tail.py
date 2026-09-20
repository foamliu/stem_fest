# -*- coding: utf-8 -*-
"""镜 36 尾部文字句改写：解除「全画面禁文字」与新「布胸标」豁免的正面冲突。

问题
    `GUARD_SOLDIER_WINTER` 新增了正向锚点
        「…胸前只有左胸一处白底黑字的「中国人民志愿军」布胸标，
          该布胸标是全画面唯一可读的文字标识。」
    而镜 36 尾部仍写着（`_fix_guard_inline.py` 批量加的通用句）
        「★ 全画面不得出现任何可读的文字、字幕或符号。画面上没有任何文字、字幕或标识」
    ⇒ 同一段 prompt 里一句授权、一句全禁，H3 遇到冲突时行为不可预测；
      更糟的是这段「文字」讨论本身会提高**字幕泄漏**风险（README §6.6）。

修法
    只改镜 36 这一处尾部句：把「全禁」改成**正向枚举画面里有什么**，
    不再提「不得出现/没有任何」这类否定式，也不再纠缠「文字」话题。
    其余 125 镜的通用句**不动**（它们没有布胸标豁免，原句仍然正确）。

用法
    py -3.10 OUTPUT/_patch36_tail.py --dry
    py -3.10 OUTPUT/_patch36_tail.py
"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "OUTPUT", "_diag_act1_trench.py")

# 原文（含 Windows 写入时的 \n 两字符转义）
OLD = (
    '        + LIGHT + "。" + LIGHT_WARM + "。镜头缓慢向后拉（slow pull back）；'
    '★ 全画面不得出现任何可读的文字、字幕或符号。'
    '画面上没有任何文字、字幕或标识，人物脸上只有表演。\\n"'
)

# 新文：正向枚举「画面里有什么」+ 唯一文字元素限定为布胸标
NEW = (
    '        + LIGHT + "。" + LIGHT_WARM + "。镜头缓慢向后拉（slow pull back）；'
    '画面上的文字元素只有战士左胸那处布胸标，'
    '其余地方是干净的土壁、沙袋、军装与天空，人物脸上只有表演。\\n"'
)


def main():
    txt = io.open(SRC, encoding="utf-8").read()
    n = txt.count(OLD)
    print("目标句出现次数：%d" % n)
    if n != 1:
        print("!! 预期恰好 1 次，实际 %d 次 —— 中止，请人工核对" % n)
        return 2

    if "--dry" in sys.argv:
        print("\n【命中位置前后 120 字符】")
        i = txt.index(OLD)
        print(txt[i - 120:i + len(OLD) + 120])
        print("\n（--dry：未写入）")
        return 0

    io.open(SRC, "w", encoding="utf-8", newline="\n").write(txt.replace(OLD, NEW))
    print("\n✅ 已改写镜 36 尾部句")
    print("\n【新句】")
    print(NEW)
    return 0


if __name__ == "__main__":
    sys.exit(main())
