# -*- coding: utf-8 -*-
"""全片 prompt `**` 审计 —— 找出「画面段仍残留 Markdown 加粗」的镜。

★ 为什么要审计（README §6.6）
    `**` 会被 H3 当画面文字画出来（镜 7 实测画面出现 `** 也不抬`）。
    `**` 只用于**给 Agent 自己看**的语义强调，H3 并不需要 ⇒ 只增泄漏面。
    ⇒ 全片画面段应**零 `**`**。

★ 区分两类 `**`
    ① **画面段内的 `**`** = 真风险（会被画）        → 应清除
    ② **注释 / 日志里的 `**`** = 无害（不进 prompt） → 忽略

用法
    py -3.10 OUTPUT/_audit_stars.py            # 汇总：每镜画面段 `**` 数
    py -3.10 OUTPUT/_audit_stars.py --list     # 列出所有残留原文
"""
import importlib.util as u
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")
sys.path.insert(0, OUT)

SCRIPTS = ["_diag_act0_plane.py", "_diag_act1_trench.py", "_diag_act2_startup.py",
           "_diag_act3_rice.py", "_diag_act4_train.py", "_diag_act5_finale.py"]

# ★ 白名单：画面里**有意要出现文字**的镜 —— 这里的 `**` 是"要 H3 把字写出来"，
#   属于 README §6.9「要让字被看见」的**正例**，不是缺陷，不算风险。
KEEP_TEXT_SHOTS = {
    79: "手里的文件印刷字（观众要读得到那行标题）",
    117: "全息屏幕字幕「科技要为人民服务。」",
    122: "屏幕「如愿·看见」",
}



def load(fn):
    p = os.path.join(OUT, fn)
    s = u.spec_from_file_location("_a_" + fn.replace(".", "_"), p)
    m = u.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def visible(prompt):
    """画面段 = Audio: 之前的部分。"""
    i = prompt.find("Audio:")
    return prompt[:i] if i >= 0 else prompt


def main():
    show = "--list" in sys.argv
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    total, bad = 0, []
    print("=" * 84)
    print("全片 prompt `**` 审计 —— 只看**画面段**（Audio: 之前）")
    print("=" * 84)
    print("%-8s %-6s %-8s  %s" % ("幕脚本", "镜", "画面段**数", "示例"))
    print("-" * 84)
    for fn in SCRIPTS:
        try:
            m = load(fn)
        except Exception as e:
            print("%-8s 加载失败：%r" % (fn, e))
            continue
        for n in sorted(getattr(m, "TASKS", {})):
            t = m.TASKS[n]["prompt"]
            v = visible(t)
            c = v.count("**")
            total += 1
            if c:
                bad.append((fn, n, c, v))
                idx = v.find("**")
                print("%-22s %-5d %-11d %s" % (fn, n, c, v[idx:idx + 46]))
    print("-" * 84)
    whitelisted = [n for _, n, _, _ in bad if n in KEEP_TEXT_SHOTS]
    real = [(f, n, c, v) for f, n, c, v in bad if n not in KEEP_TEXT_SHOTS]
    print("共审计 %d 镜，其中**画面段含 `**`** 的：%d 镜" % (total, len(bad)))
    if whitelisted:
        print("\n  ✅ 白名单（有意要画面文字，**保留**）：")
        for n in whitelisted:
            print("     镜 %-3d —— %s" % (n, KEEP_TEXT_SHOTS[n]))
    if not real:
        print("\n✅ 除白名单外**全部干净** —— 画面段零 `**`，无 Markdown 泄漏风险。")
    else:
        print("\n🔴 仍有 %d 镜需清理（用 `_strip_stars.py` 或 `_delleak_prompt.py`）："
              % len(real))
        print("   " + ", ".join("镜%d" % n for _, n, _, _ in real))
        if show:
            print()
            for fn, n, c, v in real:
                print("─" * 84)
                print("[%s 镜 %d]  画面段 `**` × %d" % (fn, n, c))
                for seg in v.split("**")[1::2]:
                    print("   · **%s**" % seg[:70])
    return 0 if not real else 1



if __name__ == "__main__":
    sys.exit(main())
