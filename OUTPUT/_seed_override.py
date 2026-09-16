# -*- coding: utf-8 -*-
"""临时覆盖镜 14 的 seed 并跑一次，跑完自动还原脚本。

做法：把 act2 脚本里 `TASKS[14] = dict(... seed=9614, ...)` 的 seed
改成指定值并备份原文件 → 调用 act2 生成 → 还原。

这样不污染生产脚本常量，且每次生成的片名递增（00006/00007…），
便于事后用 `_rerun14_seeds.py --pick` 按字幕强度挑最优。

用法：py -3.10 OUTPUT/_seed_override.py --seed=9701 --steps=20
"""
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACT2 = os.path.join(ROOT, "OUTPUT", "_diag_act2_startup.py")
BAK = ACT2 + ".seedtmp.bak"


def main():
    seed = None
    steps = 20
    for a in sys.argv[1:]:
        if a.startswith("--seed="):
            seed = int(a.split("=", 1)[1])
        elif a.startswith("--steps="):
            steps = int(a.split("=", 1)[1])
    if seed is None:
        print("缺 --seed=")
        return 1

    src = open(ACT2, encoding="utf-8").read()
    # 定位 TASKS[14] 的 seed=
    m = re.search(r"(TASKS\[14\]\s*=\s*dict\(\s*\n\s*slug=\"[^\"]+\",\s*seed=)(\d+)", src)
    if not m:
        print("未找到 TASKS[14].seed")
        return 1
    old_seed = m.group(2)
    new = src[:m.start(2)] + str(seed) + src[m.end(2):]
    print("镜 14 seed %s → %d（steps=%d）" % (old_seed, seed, steps))

    shutil.copy2(ACT2, BAK)
    open(ACT2, "w", encoding="utf-8", newline="").write(new)
    try:
        r = subprocess.run(
            ["py", "-3.10", ACT2, "--steps=%d" % steps, "14"],
            cwd=ROOT, capture_output=True, text=True)
        for L in (r.stdout or "").strip().splitlines()[-14:]:
            print("  " + L)
        if r.returncode != 0:
            for L in (r.stderr or "").strip().splitlines()[-8:]:
                print("  ! " + L)
        rc = r.returncode
    finally:
        shutil.move(BAK, ACT2)          # 还原
        assert old_seed in open(ACT2, encoding="utf-8").read(), "还原失败！"
    print("（脚本已还原 seed=%s）" % old_seed)
    return rc


if __name__ == "__main__":
    sys.exit(main())
