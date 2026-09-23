# -*- coding: utf-8 -*-
"""04_classroom_dusk → 03_classroom_day 输出目录迁移（2026-09-21）。

背景：用户指令 —— 「故事的开始就是在现实世界的下午 6 点，本来就是 dust，
      没必要分三个场景，过于的冗余」。
      故 `ASSETS/SCENES/04_classroom_dusk/` 已**物理删除**，
      序幕二（镜 10-18）的场景图改用 `03_classroom_day/classroom_day_wide_v01.png`。

本脚本做的事（**幂等，可反复跑**）：
  1. `OUTPUT/04_classroom_dusk/` → `OUTPUT/03_classroom_day/`
     · 目标不存在 → 整目录移动（保时间戳）
     · 目标已存在 → 逐文件移动，**同名不覆盖**，冲突文件改名加 `_from_dusk` 后缀并打印
  2. 顺带把散在 `OUTPUT/` 根下的 `_face_ledger_04_classroom_dusk.json` 改名成
     `_face_ledger_03_classroom_day.json`（内容一字不动 —— 它记录的是**已验收的历史产物**，
     改名只是让它和产物目录同名，便于检索）

★ 纪律：产物**一律不删**（镜 10-18 已拍完验收过，是历史证据）。
  本轮重跑会把新片写进 `OUTPUT/03_classroom_day/video/`，与旧产物同名时由
  各诊断脚本自己的 `shutil.copy2` 覆盖 —— 那时才产生新版本。

用法：
    py -3.10 OUTPUT/_migrate_04_to_03.py --dry     # 只看会做什么
    py -3.10 OUTPUT/_migrate_04_to_03.py           # 真做
"""
import os
import shutil
import sys

ROOT = r"E:\code\stem_fest"
OUT = os.path.join(ROOT, "OUTPUT")

SRC_DIR = os.path.join(OUT, "04_classroom_dusk")
DST_DIR = os.path.join(OUT, "03_classroom_day")

SRC_LEDGER = os.path.join(OUT, "_face_ledger_04_classroom_dusk.json")
DST_LEDGER = os.path.join(OUT, "_face_ledger_03_classroom_day.json")


def main():
    dry = "--dry" in sys.argv[1:]
    tag = "[DRY] " if dry else ""

    if not os.path.isdir(SRC_DIR):
        print("%s源目录不存在：%s" % (tag, SRC_DIR))
        print("%s→ 无需迁移（已迁过 / 从未存在）" % tag)
    else:
        n_files = 0
        n_conflict = 0
        for cur, dirs, files in os.walk(SRC_DIR):
            rel = os.path.relpath(cur, SRC_DIR)
            tgt_dir = DST_DIR if rel == "." else os.path.join(DST_DIR, rel)
            if not dry:
                os.makedirs(tgt_dir, exist_ok=True)
            for fn in files:
                src = os.path.join(cur, fn)
                dst = os.path.join(tgt_dir, fn)
                if os.path.exists(dst):
                    stem, ext = os.path.splitext(fn)
                    dst = os.path.join(tgt_dir, stem + "_from_dusk" + ext)
                    n_conflict += 1
                    print("%s[冲突改名] %s → %s" % (tag, fn, os.path.basename(dst)))
                else:
                    print("%s[移动] %s" % (tag, os.path.join(rel, fn)))
                if not dry:
                    shutil.move(src, dst)
                n_files += 1
        print("%s共 %d 个文件（其中同名冲突改名 %d 个）" % (tag, n_files, n_conflict))
        if not dry:
            # 清掉（此时应为空的）残留目录树
            for cur, dirs, files in os.walk(SRC_DIR, topdown=False):
                if not os.listdir(cur):
                    os.rmdir(cur)
            if os.path.isdir(SRC_DIR):
                print("⚠️ 源目录仍有残留（非空），请手工检查：%s" % SRC_DIR)
            else:
                print("源目录已清空移除：%s" % SRC_DIR)

    # ── 台账改名 ─────────────────────────────────────────
    if os.path.exists(SRC_LEDGER):
        if os.path.exists(DST_LEDGER):
            print("%s[跳过] 目标台账已存在：%s" % (tag, os.path.basename(DST_LEDGER)))
        else:
            print("%s[改名] %s → %s" % (tag, os.path.basename(SRC_LEDGER),
                                       os.path.basename(DST_LEDGER)))
            if not dry:
                shutil.move(SRC_LEDGER, DST_LEDGER)
    else:
        print("%s台账不在源位置（可能已改名）：%s" % (tag, os.path.basename(SRC_LEDGER)))

    print("%s完成。" % tag)


if __name__ == "__main__":
    main()
