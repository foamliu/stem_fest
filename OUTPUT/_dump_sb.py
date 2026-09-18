# -*- coding: utf-8 -*-
"""把 storyboard.md 的逐镜表解析成结构化清单，供逐镜核对。

用法：
    py -3.10 OUTPUT/_dump_sb.py                  # 全 126 镜，写到 OUTPUT/_sb_shots.txt
    py -3.10 OUTPUT/_dump_sb.py --rows=1,6,7     # 控制台打印指定镜
"""
from __future__ import annotations
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SB = os.path.join(ROOT, "storyboard.md")


def parse():
    """返回 {shot: {dur, scene, move, size, audio, ref, raw}}"""
    txt = io.open(SB, encoding="utf-8").read()
    shots = {}
    for line in txt.split("\n"):
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 6:
            continue
        if not cells[0].isdigit():
            continue
        n = int(cells[0])
        if not (1 <= n <= 126):
            continue
        dur = cells[1]
        m = re.match(r"^(\d+)", dur)
        shots[n] = {
            "dur": int(m.group(1)) if m else None,
            "scene": cells[2],
            "move": cells[3],
            "size": cells[4],
            "audio": cells[5],
            "ref": cells[6] if len(cells) > 6 else "",
            "raw": s,
        }
    return shots


def net_line(audio: str) -> str:
    """从 `音效：` 列里抽出**净台词**（去掉 说话人/音效/音乐/歌词 标注）。"""
    a = audio
    for tag in ("音效：", "音乐：", "歌词："):
        i = a.find(tag)
        if i >= 0:
            a = a[:i]
    m = re.search(r"说话人：", a)
    if m:
        a = a[m.end():]
    else:
        # `张书扬：xxx` 形式
        m2 = re.match(r"^[\u4e00-\u9fa5]{2,4}：", a)
        if m2:
            a = a[m2.end():]
    return a.strip()


def main():
    rows = None
    for x in sys.argv[1:]:
        if x.startswith("--rows="):
            rows = [int(i) for i in x.split("=", 1)[1].split(",") if i.strip()]
    shots = parse()
    if rows:
        out = []
        for n in rows:
            s = shots.get(n)
            if not s:
                out.append("镜 %d  <未在 storyboard 中找到>" % n)
                continue
            out.append("镜 %-3d %2ss | %s | %s | %s\n        台词: %r\n        ref : %s" % (
                n, s["dur"], s["size"], s["move"], s["scene"][:40],
                net_line(s["audio"]), s["ref"]))
        print("\n".join(out))
        return 0

    dest = os.path.join(HERE, "_sb_shots.txt")
    with io.open(dest, "w", encoding="utf-8") as f:
        f.write("%-5s %-4s %-6s %-28s %s\n" % ("镜号", "时长", "说话人", "净台词", "景别"))
        f.write("-" * 100 + "\n")
        n_with = 0
        for n in sorted(shots):
            s = shots[n]
            ln = net_line(s["audio"])
            who = ""
            m = re.search(r"([\u4e00-\u9fa5]{2,4})：", s["audio"])
            if m:
                who = m.group(1)
            if ln:
                n_with += 1
            f.write("%-5d %-4s %-6s %-28s %s\n" % (n, s["dur"], who, ln or "（无台词）", s["size"]))
        f.write("-" * 100 + "\n")
        f.write("共 %d 镜，其中有台词 %d 镜\n" % (len(shots), n_with))
    print("镜数=%d 有台词=%d -> %s" % (len(shots), n_with, dest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
