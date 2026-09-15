# -*- coding: utf-8 -*-
"""看 ComfyUI 正在跑的任务里，禁令行与 Audio 是否分行。

用法：py -3.10 OUTPUT/_peek_queue.py
"""
import json
import sys
import urllib.request

URL = "http://127.0.0.1:8188/queue"


def main():
    try:
        q = json.load(urllib.request.urlopen(URL, timeout=8))
    except Exception as e:
        print("ERR: %s" % e)
        return 1
    items = list(q.get("queue_running") or []) + list(q.get("queue_pending") or [])
    print("running=%d pending=%d" % (len(q.get("queue_running") or []),
                                     len(q.get("queue_pending") or [])))
    for it in items:
        pr = it[2] if len(it) > 2 else {}
        for nid, node in (pr or {}).items():
            for k, v in (node.get("inputs") or {}).items():
                if isinstance(v, str) and "CUT" in v and len(v) > 80:
                    print("=== node %s .%s ===" % (nid, k))
                    print(v[-400:])
                    print("--- 检查 ---")
                    print("  粘连 '符号。Audio:'              :", "符号。Audio:" in v)
                    print("  分行 '符号。\\nAudio:'             :", "符号。\nAudio:" in v)
                    print("  ** 残留                        :", v.count("**"))
                    return 0
    print("（未捕获到长文本节点）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
