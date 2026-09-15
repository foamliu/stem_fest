# -*- coding: utf-8 -*-
"""重跑进度监视器 —— 一眼看重跑到了哪一镜、还剩几镜。

配合 `_rerun_leaks.py`（后台跑）使用：后台日志只在**每幕结束时**才 flush，
所以光看日志会以为"卡住了"。本脚本直接查**ComfyUI /history 与 /queue**，
拿到真实进度。

用法
    py -3.10 OUTPUT/_watch_rerun.py            # 打印一次
    py -3.10 OUTPUT/_watch_rerun.py --loop 600 # 每 60s 打印一次，共 600s
"""
import io
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _delogo import SHOTS, newest  # noqa: E402

API = "http://127.0.0.1:8188"


def get(path):
    try:
        with urllib.request.urlopen(API + path, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"_err": str(e)[:80]}


def snapshot():
    q = get("/queue")
    run = len(q.get("queue_running") or [])
    pend = len(q.get("queue_pending") or [])
    h = get("/history")
    done = len(h) if isinstance(h, dict) else 0
    print("─" * 76)
    print("ComfyUI：运行中=%d 排队=%d ／ history 累计=%d" % (run, pend, done))
    print("%-6s %-42s %-18s %s" % ("镜", "文件（最新）", "落盘时间", "距今"))
    print("─" * 76)
    now = time.time()
    for n in sorted(SHOTS):
        act, slug, _ = SHOTS[n]
        p = newest(act, slug)
        if not p:
            print("%-6d %-42s %-18s %s" % (n, "(无)", "-", "-"))
            continue
        mt = os.path.getmtime(p)
        age = now - mt
        # 1 小时内落盘 = 本次重跑的新片
        flag = "★新" if age < 3600 else " 旧"
        print("%-6d %-42s %-18s %s"
              % (n, flag + " " + os.path.basename(p)[:38],
                 time.strftime("%m-%d %H:%M:%S", time.localtime(mt)),
                 "%.0f 分钟前" % (age / 60.0)))
    print("─" * 76)


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  line_buffering=True)
    total = 0
    if "--loop" in sys.argv:
        i = sys.argv.index("--loop")
        total = int(sys.argv[i + 1]) if i + 1 < len(sys.argv) else 600
    t0 = time.time()
    while True:
        snapshot()
        if total <= 0 or time.time() - t0 >= total:
            break
        print("... 60s 后再查（已监视 %.0fs / %ds）\n" % (time.time() - t0, total))
        time.sleep(60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
