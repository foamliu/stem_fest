# -*- coding: utf-8 -*-
"""场景图变更 → 受影响镜重跑清单（2026-09-21）。

为什么需要它
    2026-09-20 用户**重生成并定版**了四套场景图（03 教室·傍晚 v01 / 05 教室·夜 v01 /
    07 稻田 v01 / 08 餐车 v01），第一幕 06_trench 也换了风雪版。
    而 `_plan_rerun.py` 的判据是「prompt 修复时刻」（FIX_9_14 / FIX_9_15），
    **看不到场景图换图这件事** ⇒ 清单不完整，必须另建判据。

判据（唯一、可复算）
    某镜的**最新产物 mtime < 该幕场景图的 mtime** ⇒ 该产物用的是**旧场景图** ⇒ 必须重跑。
    （H3 会照抄参考图色温与陈设，换图必然改画面。）

    反过来：产物 mtime > 场景图 mtime ⇒ 已是新图产物，跳过。

为什么不是「整幕重跑」
    第一幕 06_trench 有 30/135 个产物已晚于 9/20 15:52（换图后又跑过），
    若整幕重跑就是白烧 30 条 × 20 分钟 ≈ 10 小时。逐镜比对是**省下这 10 小时**的关键。

用法：
    py -3.10 OUTPUT/_plan_scene_rerun.py             # 打印清单 + 写 _scene_rerun.json
    py -3.10 OUTPUT/_plan_scene_rerun.py --list      # 只打印，不写文件
"""
import glob
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")

# 幕 → (输出目录, 脚本, 镜号区间, 场景图相对路径)
#   ⚠️ 镜号区间必须与 `_concat_video.py` 的 RANGES 一致
#   ⚠️ 场景图路径必须与对应 `_diag_act*.py` 里写死的 SCENE 一致
ACTS = [
    ("01_paper_plane", "_diag_act0_plane.py", (1, 9),
     ["01_school_gate/school_gate_wide_v02.png", "02_campus/campus_wide_v01.png"]),
    ("03_classroom_day", "_diag_act2_startup.py", (10, 18),
     ["03_classroom_day/classroom_day_wide_v01.png"]),
    ("06_trench", "_diag_act1_trench.py", (19, 46),
     ["06_trench/trench_wide_v04.png"]),
    ("07_rice_field", "_diag_act3_rice.py", (47, 74),
     ["07_rice_field/rice_field_wide_v01.png"]),
    ("08_train_dining", "_diag_act4_train.py", (75, 105),
     ["08_train_dining/train_dining_wide_v01.png"]),
    ("05_classroom_night", "_diag_act5_finale.py", (106, 126),
     ["05_classroom_night/classroom_night_wide_v01.png"]),
]

SCENES = os.path.join(ROOT, "ASSETS", "SCENES")


def scene_mtime(rels):
    """该幕的场景图基准时刻 = 相关场景图里**最新**的一张（取最严口径）。"""
    ts = []
    for r in rels:
        p = os.path.join(SCENES, r)
        if os.path.exists(p):
            ts.append((os.path.getmtime(p), r))
    if not ts:
        return None, None
    t, r = max(ts)
    return t, r


def newest_video(act, shot):
    """该镜在该幕目录下的最新产物（排除 _bak_ / delogo / temporal / split）。

    ⚠️ 文件名里的镜号**可能补零**：01_paper_plane 用 `%02d`，其余幕用 `%d`。
       只试一种会永远匹配不到（`_run_rerun.py` 2026-09-15 踩过同一个坑）。
    """
    vd = os.path.join(OUT, act, "video")
    best, bt = None, 0.0
    pats = ["%d_*.mp4" % shot, "%02d_*.mp4" % shot, "%03d_*.mp4" % shot]
    seen = set()
    for pat in pats:
        for f in glob.glob(os.path.join(vd, pat)):
            if f in seen:
                continue
            seen.add(f)
            b = os.path.basename(f)
            if b.startswith("_bak_") or re.search(r"_(delogo|temporal|split)\.mp4$", b):
                continue
            m = os.path.getmtime(f)
            if m > bt:
                best, bt = f, m
    return best, bt


def main():
    list_only = "--list" in sys.argv
    grand = {}
    print("=" * 96)
    print("场景图变更 → 受影响镜（判据：最新产物 mtime < 该幕场景图 mtime）")
    print("=" * 96)
    for act, script, (lo, hi), rels in ACTS:
        t, ref = scene_mtime(rels)
        if t is None:
            print("\n[%s] !! 场景图不存在：%s" % (act, rels))
            continue
        need, fresh, missing = [], [], []
        for shot in range(lo, hi + 1):
            p, mt = newest_video(act, shot)
            if p is None:
                missing.append(shot)
            elif mt < t:
                need.append(shot)
            else:
                fresh.append(shot)
        print("\n[%s]  镜 %d-%d  场景图 %s  (%s)" % (
            act, lo, hi, ref, time.strftime("%m-%d %H:%M", time.localtime(t))))
        print("   需重跑 %2d 镜：%s" % (len(need), need if need else "—"))
        print("   已新图 %2d 镜：%s" % (len(fresh), fresh if fresh else "—"))
        if missing:
            print("   ⚠️ 无产物 %d 镜：%s" % (len(missing), missing))
        grand[script] = sorted(need)

    total = sum(len(v) for v in grand.values())
    print("\n" + "=" * 96)
    print("合计需重跑 %d 镜" % total)
    est = sum((17.0 if s in ("_diag_act2_startup.py",) else 8.5) * len(v)
              for s, v in grand.items())
    print("预估机时 ≈ %.0f 分（%.1f 小时）  [act2 steps=20 按 17 分/条，其余 steps=10 按 8.5 分/条]"
          % (est, est / 60.0))
    print("=" * 96)

    if not list_only:
        p = os.path.join(OUT, "_scene_rerun.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump({k: v for k, v in grand.items() if v}, f,
                      ensure_ascii=False, indent=1)
        print("已写 %s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
