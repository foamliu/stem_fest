# -*- coding: utf-8 -*-
"""修复 prompt 里的「元信息写法」—— 这是把内心状态/镜头用意写进画面描述，
会被 H3 渲染成**画面字幕**（2026-09-14 镜 91 实际踩坑：
prompt 写「像在消化一件很难立刻接受的事」→ 成片底部出现同文字幕）。

修法：把「像在… / 这一镜 / 本镜 / 暗示…」等**摄影机拍不到**的写法，
改写成**可见的动作与表情**，语义不变。

★ 幂等：重复跑不会重复替换（锚点替换后即消失）。
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (文件, 原文, 改后) —— 只动元信息，不动剧情
FIXES = [
    # ── act0 镜 6 ──
    ("_diag_act0_plane.py",
     "手腕左右晃了晃、头微微一歪，表情得意又带一点挑衅、像在找是谁干的；",
     "手腕左右晃了晃、头微微一歪、挑起一边眉毛，眼神在教室里扫了一圈、"
     "嘴角挂着得意又挑衅的笑；"),

    # ── act2 镜 10 ──
    ("_diag_act2_startup.py",
     "正微微侧头看向另外三人，像在开口确认什么；",
     "正微微侧头看向另外三人，嘴唇微启、明显正在说出一句话；"),
    # ── act2 镜 16 ──
    ("_diag_act2_startup.py",
     "男生只发出一声被噎住的短促气音、没有说出台词（本镜无对白）。",
     "男生只发出一声被噎住的短促气音、没有说出台词。"),

    # ── act1 镜 33 ──
    ("_diag_act1_trench.py",
     "像是想到了很远的地方", "目光越过眼前、落在远处的地平线上"),
    # ── act1 镜 38 ──
    ("_diag_act1_trench.py",
     "像在看一个还没到的地方", "目光望着远方、眼睛微微发亮"),
    # ── act1 镜 43 ──
    ("_diag_act1_trench.py",
     "像是在送人回家", "目光一直跟着他们、手停在半空没有放下"),

    # ── act3 镜 52 ──
    ("_diag_act3_rice.py",
     "暗示盛夏稻田、阳光穿透稻叶形成斑驳光点",
     "阳光穿过稻叶、在画面里留下斑驳的光点"),

    # ── act4 镜 91（已实际出事）──
    ("_diag_act4_train.py",
     "眼神很深、表情看不出情绪，像在消化一件很难立刻接受的事；",
     "眼神很深、面无表情地沉默了几秒，喉结动了一下；"),
    # ── act4 镜 94 ──
    ("_diag_act4_train.py",
     "（**这一镜要让他露出放松的微笑**）", "（**他的表情必须是放松的微笑**）"),
    # ── act4 镜 96 ──
    ("_diag_act4_train.py",
     "神情像是想起了很久以前的事，语气带着一点怀念；",
     "目光微微放空、嘴角带着一点笑意，语气平缓；"),
    ("_diag_act4_train.py",
     "（**这一镜要让他露出带回忆感的笑**）", "（**他的表情必须是带笑意的**）"),
    # ── act4 镜 97 ──
    ("_diag_act4_train.py",
     "神情淡淡的、像在说一件很久以前的小事；",
     "神情平淡、语速不急不缓；"),

    # ── act5 镜 114 ──
    ("_diag_act5_finale.py",
     "像是顺口补了一句、语气平静但很有分量；", "语气平静、语速不快；"),
    # ── act5 镜 125 ──
    ("_diag_act5_finale.py",
     "三段定格影像在画面中依次闪过、每段约 2-3 秒，",
     "三段静止画面依次出现、每段约 2-3 秒，"),
]


def main():
    dry = "--dry" in sys.argv
    by_file = {}
    for f, a, b in FIXES:
        by_file.setdefault(f, []).append((a, b))

    total = 0
    for f, subs in by_file.items():
        p = os.path.join(ROOT, "OUTPUT", f)
        src = io.open(p, encoding="utf-8").read()
        done = 0
        for a, b in subs:
            if a in src:
                src = src.replace(a, b)
                done += 1
            else:
                print("   [跳过] %s 未命中：%s" % (f, a[:36]))
        if not dry and done:
            io.open(p, "w", encoding="utf-8").write(src)
        print("%-26s 修复 %d/%d 处" % (f, done, len(subs)))
        total += done

    print()
    print("%s合计修复 %d 处" % ("[dry] " if dry else "", total))


if __name__ == "__main__":
    main()
