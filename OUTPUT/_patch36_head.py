# -*- coding: utf-8 -*-
"""镜 36 开场人物描述改写：把「不戴领章」的**半否定式**补丁升级为**正向衣服描述**。

问题（v8 读图铁证）
    开场第一句原是
        「一位穿着偏大军绿色立领军装的年轻小战士（不戴领章）、
          一位穿军绿色立领军装戴红星军帽的年轻战士」
    只有小战士带「不戴领章」括号，另一位**完全没约束** ⇒ v8 里**两人都长出红领章**。
    根因：「军绿色立领军装」在 H3 训练数据里默认指向 **1955 式解放军军官服**
    （该制服**有**领章与肩章）—— 参考图也偏那个时代，锚点双双指向错误形制。

修法
    ① 把「（不戴领章）」这种**半否定括号**（H3 对括号里的否定不敏感，
       且否定词写在括号里等于把「领章」这个词植入了画面）改为
       **正向描述衣服具体长什么样**：立领、领口是与衣身同色的素净棉布；
    ② 给**两位战士都加**上同样的正向限定，不留空位；
    ③ 保留「立领军装」这个用户/史实已确认的形制词，不推翻原有设定。

用法
    py -3.10 OUTPUT/_patch36_head.py --dry
    py -3.10 OUTPUT/_patch36_head.py
"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "OUTPUT", "_diag_act1_trench.py")

OLD = (
    '        "CUT 1: 中景三人镜头，一位穿着偏大军绿色立领军装的年轻小战士（不戴领章）、"\n'
    '        "一位穿军绿色立领军装戴红星军帽的年轻战士，与稍远处另一名志愿军战士，"\n'
)

NEW = (
    '        "CUT 1: 中景三人镜头，一位穿着偏大军绿色立领军装的年轻小战士，"\n'
    '        "一位穿军绿色立领军装戴红星军帽的年轻战士，与稍远处另一名志愿军战士，"\n'
    '        "三位战士的立领军装都是志愿军形制：立领平整、领口是与衣身同色的素净棉布、"\n'
    '        "领口没有任何附加布块，双肩只有与衣身同色的护肩棉布，"\n'
)


def main():
    txt = io.open(SRC, encoding="utf-8").read()
    n = txt.count(OLD)
    print("目标段出现次数：%d" % n)
    if n != 1:
        print("!! 预期恰好 1 次，实际 %d 次 —— 中止" % n)
        return 2
    if "--dry" in sys.argv:
        i = txt.index(OLD)
        print("\n【命中位置】")
        print(txt[i:i + len(OLD)])
        print("（--dry：未写入）")
        return 0
    io.open(SRC, "w", encoding="utf-8", newline="\n").write(txt.replace(OLD, NEW))
    print("\n✅ 已改写镜 36 开场人物描述")
    return 0


if __name__ == "__main__":
    sys.exit(main())
