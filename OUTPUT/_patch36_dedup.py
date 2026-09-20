# -*- coding: utf-8 -*-
"""镜 36 去重：开场段与 `GUARD_SOLDIER_WINTER` 出现了**同一段衣服描述**。

问题
    `_patch36_head.py` 在开场加了「三位战士的立领军装都是志愿军形制：立领平整、
    领口是与衣身同色的素净棉布、领口没有任何附加布块，双肩只有与衣身同色的护肩棉布」，
    而 `GUARD_SOLDIER_WINTER` 里也有「军装的标识形制是志愿军样式：立领平整、
    领口是素净的同色棉布、双肩只有一整块同色护肩布…」⇒ **同义重复两遍**。

为什么必须去重（README §6.10.14 / 镜 36 v8 教训）
    H3 的注意力是**有限预算**。重复内容不会"加强"，只会**挤占**别的指令
    （上一轮 `LIGHT_WARM` 就是为了把被 `GUARD_SOLDIER_WINTER` 挤掉的光照抢回来）。
    因此服装锚点**只保留一处**（常量里那份，19 镜共用、口径统一），
    开场只留「三人身份 + 动作」，不加形制描述。

修法
    把 `_patch36_head.py` 加进去的那两行（衣服形制）删掉；
    开场恢复为「三人身份」一句，形制统一由 `GUARD_SOLDIER_WINTER` 承载。

用法
    py -3.10 OUTPUT/_patch36_dedup.py --dry
    py -3.10 OUTPUT/_patch36_dedup.py
"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "OUTPUT", "_diag_act1_trench.py")

OLD = (
    '        "一位穿军绿色立领军装戴红星军帽的年轻战士，与稍远处另一名志愿军战士，"\n'
    '        "三位战士的立领军装都是志愿军形制：立领平整、领口是与衣身同色的素净棉布、"\n'
    '        "领口没有任何附加布块，双肩只有与衣身同色的护肩棉布，"\n'
    '        "蹲在同一段交通壕里、处于同一光照环境、画面是一个完整连续的空间："\n'
)

NEW = (
    '        "一位穿军绿色立领军装戴红星军帽的年轻战士，与稍远处另一名志愿军战士，"\n'
    '        "蹲在同一段交通壕里、处于同一光照环境、画面是一个完整连续的空间："\n'
)


def main():
    txt = io.open(SRC, encoding="utf-8").read()
    n = txt.count(OLD)
    print("重复段出现次数：%d" % n)
    if n != 1:
        print("!! 预期恰好 1 次，实际 %d 次 —— 中止" % n)
        return 2
    if "--dry" in sys.argv:
        print("\n【将删除的内容】")
        print(OLD)
        print("（--dry：未写入）")
        return 0
    io.open(SRC, "w", encoding="utf-8", newline="\n").write(txt.replace(OLD, NEW))
    print("\n✅ 已去重（形制描述只保留在 GUARD_SOLDIER_WINTER）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
