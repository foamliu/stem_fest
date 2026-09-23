# -*- coding: utf-8 -*-
"""清理「旧剧本时代」的作废视频产物（2026-09-13 及以前）。

背景：剧本多次改版，此前所有 mp4 的镜号/台词都已过时。
2026-09-14 起由 `_run_all_acts.py` 串行重跑全片 126 镜。

安全策略（★ 保守，宁可少删）：
  · 只处理**今天之前**（mtime < 今天 00:00）的 mp4
  · 只处理已知的 3 个旧产物目录
  · 删除前列清单并保留一份 manifest
  · **不碰**今天新生成的产物

用法：
    py -3.10 OUTPUT/_clean_old_videos.py --list    # 只列，不删（默认）
    py -3.10 OUTPUT/_clean_old_videos.py --delete  # 真删
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRS = ["01_paper_plane", "03_classroom_day", "06_trench", "07_rice_field"]
MANIFEST = os.path.join(ROOT, "OUTPUT", "_cleaned_old_videos.txt")


def today_start():
    t = time.localtime()
    return time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1))


def main():
    do_del = "--delete" in sys.argv
    cutoff = today_start()
    rows = []
    for d in DIRS:
        vdir = os.path.join(ROOT, "OUTPUT", d, "video")
        if not os.path.isdir(vdir):
            continue
        for fn in sorted(os.listdir(vdir)):
            p = os.path.join(vdir, fn)
            if not os.path.isfile(p) or not fn.lower().endswith(".mp4"):
                continue
            m = os.path.getmtime(p)
            if m < cutoff:
                rows.append((p, os.path.getsize(p), time.strftime("%Y-%m-%d %H:%M", time.localtime(m))))

    print("=== 旧产物（今天之前）共 %d 个 ===" % len(rows))
    for p, sz, ts in rows:
        print("  %-12s %7.1f KB  %s  %s" % (
            os.path.relpath(p, ROOT), sz / 1024.0, ts, "")[:150])

    if not do_del:
        print("\n（--list 模式，未删除。要删加 --delete）")
        return

    with open(MANIFEST, "w", encoding="utf-8") as f:
        f.write("# 2026-09-14 清理的旧剧本产物（已删）\n")
        for p, sz, ts in rows:
            f.write("%s\t%d\t%s\n" % (os.path.relpath(p, ROOT), sz, ts))
            os.remove(p)
    print("\n已删除 %d 个，清单存于 %s" % (len(rows), os.path.relpath(MANIFEST, ROOT)))


if __name__ == "__main__":
    main()
