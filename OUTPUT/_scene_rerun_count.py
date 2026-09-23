# -*- coding: utf-8 -*-
"""重跑进度计数器 —— 供 `_auto_scene_rerun.bat` 的 `for /f` 解析。

为什么单独写成文件（2026-09-21 实测踩坑）
    .bat 里不能直接写 `python -c "...print('BEFORE=%d' % n)"`：
    批处理会**先行展开** `%d`（当成不存在的环境变量 ⇒ 空串），
    Python 收到的是 `print('BEFORE='%n)` ⇒ SyntaxError。
    ⇒ 凡是要在 .bat 里解析的输出，都从这里出，**输出里不含任何裸 % 号**。

用法：
    py -3.10 OUTPUT/_scene_rerun_count.py            # 只打印 done=N fail=M
    py -3.10 OUTPUT/_scene_rerun_count.py BEFORE     # 打印 BEFORE=N（给 for /f 取 tokens=2 delims==）
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "_scene_rerun_state.json")


def main():
    try:
        with open(STATE, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        d = {"done": [], "fail": {}}
    n, m = len(d.get("done") or []), len(d.get("fail") or {})
    tag = "N"
    for a in sys.argv[1:]:
        if a.strip():
            tag = a.strip().upper()
            break
    # 单行、无裸 % 号、形如 TAG=数字
    print("%s=%d" % (tag, n))
    print("done=%d fail=%d" % (n, m))
    return 0


if __name__ == "__main__":
    sys.exit(main())
