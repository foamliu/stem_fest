# -*- coding: utf-8 -*-
"""字幕泄漏镜 prompt 批量「去泄漏化」改写器（A 方案）。

★ 配方来自镜 7 的成功实测（README §6.6「镜 7 重跑后的实测结论」）
    旧片 8/8 帧泄漏 → 新片 0/8 帧干净，四处改动：

    R1  删掉画面段全部 `**加粗**` 标记（`**` 会被 H3 当画面文字画出来）
    R2  画面段的加粗强调改写成自然陈述句（语义保留、标记消失）
    R3  ★ 画面段末尾**追加显式禁令**：
        「★ 全画面不得出现任何可读的文字、字幕或符号。」
        —— 这一句是「你少自恋了」也一并消失的关键（压制整段写字倾向）
    R4  `Audio:` 段**台词原文保留**（H3 靠它生成口型与环境音，删了就哑了），
        但把**直接引号**去掉（引号是放大器：含引号组泄漏率 50% vs 无引号 9.3%）

★ 用法
    py -3.10 OUTPUT/_delleak_prompt.py --dry      # 只看改写结果（不改文件）
    py -3.10 OUTPUT/_delleak_prompt.py --apply    # 就地改写 6 个幕脚本（自动备份 .bak）
    py -3.10 OUTPUT/_delleak_prompt.py --verify   # 校验：所有画面段已无 ** 且含禁令
"""
import io
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")

# 目标镜 → (幕脚本, 需要重写的画面段原文片段, 改写后)
# 只动「画面段」，Audio 段单独处理（见 fix_audio）
LEAK_SHOTS = {
    14: ("_diag_act2_startup.py", "_diag_act2_startup.py"),
    21: ("_diag_act1_trench.py", "_diag_act1_trench.py"),
    36: ("_diag_act1_trench.py", "_diag_act1_trench.py"),
    77: ("_diag_act4_train.py", "_diag_act4_train.py"),
    85: ("_diag_act4_train.py", "_diag_act4_train.py"),
    86: ("_diag_act4_train.py", "_diag_act4_train.py"),
    88: ("_diag_act4_train.py", "_diag_act4_train.py"),
    112: ("_diag_act5_finale.py", "_diag_act5_finale.py"),
}

BAN = "★ 全画面不得出现任何可读的文字、字幕或符号。"

# ── 逐镜的画面段替换（R1+R2+R3） ────────────────────────────────
# key = 镜号, value = [(旧文本, 新文本), ...]  在 TASKS[n] 块内做精确替换
EDITS = {
    14: [(
        '"**身后和身旁还站着另外三位同学，他们安静看着、不说话，只入画一部分**；"',
        '"身后和身旁还站着另外三位同学，他们安静看着、不说话，只入画一部分；"',
    )],
    21: [],  # 画面段本无 `**`，只需追加禁令
    36: [(
        '一位穿着偏大军绿色立领军装的年轻小战士（**不戴领章**）、',
        '一位穿着偏大军绿色立领军装的年轻小战士（不戴领章）、',
    )],
    77: [(
        '"**身后和身旁还站着另外三位同学，他们只入画一部分**；"',
        '"身后和身旁还站着另外三位同学，他们只入画一部分；"',
    )],
    85: [(
        '"（**女生的细框眼镜必须保留**）；"',
        '"（女生的细框眼镜必须保留）；"',
    )],
    86: [],
    88: [],
    112: [(
        '"**身后和身旁还站着另外三位同学，他们只入画一部分**；"',
        '"身后和身旁还站着另外三位同学，他们只入画一部分；"',
    )],
}

# ── Audio 段去引号（R4） ─────────────────────────────────────
AUDIO_FIX = {
    112: ('男生轻声说：他问我们……“咱们国家现在啥样了”。',
          '男生轻声说：他问我们……咱们国家现在啥样了。'),
}


def find_block(src, n):
    """返回 (start, end) —— TASKS[n] = dict( … ) 的字符区间。"""
    m = re.search(r"TASKS\[%d\]\s*=\s*dict\(" % n, src)
    if not m:
        return None
    nxt = re.search(r"\nTASKS\[|\n# ──", src[m.end():])
    end = m.end() + nxt.start() if nxt else len(src)
    return m.start(), end


def insert_ban(src, n):
    """R3：在画面段末（Audio: 之前）插入禁令。返回 (新源码, 是否已存在)。"""
    rng = find_block(src, n)
    if not rng:
        return src, False
    s, e = rng
    block = src[s:e]
    if "不得出现任何可读的文字" in block:
        return src, True
    # 找 Audio: 前的最后一个 `+ LIGHT + "...。"` 结构，在其后插入
    idx = block.find('"Audio:')
    if idx < 0:
        return src, False
    before, after = block[:idx], block[idx:]
    # 插到 `+ LIGHT + "。` 那句的末尾之后
    m = list(re.finditer(r'\+ LIGHT \+ "([^"]*)', before))
    if m:
        pos = before.find('"，', m[-1].start())
        # 更稳：找 LIGHT 那句的结束引号
        seg = before[m[-1].start():]
        q = seg.find('"')
        if q >= 0:
            q2 = seg.find('"', q + 1)
            if q2 >= 0:
                ins = m[-1].start() + q2 + 1
                before = before[:ins] + "\n        " + '"' + BAN + '"' + before[ins:]
    return src[:s] + before + after + src[e:], False


def apply_edits(src, n):
    """对该镜做 R1/R2（去 `**`）+ R4（Audio 去引号）。返回 (新源码, 日志)。

    ★ 必须在**该镜的 block 内**替换（2026-09-15 踩坑）：
      多个镜的 `**…**` 句子完全相同（例：`**身后和身旁还站着另外三位同学…**`
      在 act2 里出现 5 次、act5 里出现 5 次）。若在全文 `replace(old, new, 1)`，
      会误改**更早的镜**、而目标镜没改到 —— 表现就是"dry-run 说改了、verify 说没改"。
    """
    log = []
    rng = find_block(src, n)
    if not rng:
        return src, ["  ✗ 找不到 TASKS[%d] 块" % n]
    s, e = rng
    blk = src[s:e]

    for old, new in EDITS.get(n, []):
        if old in blk:
            blk = blk.replace(old, new, 1)
            log.append("  去掉 `**`：%s…" % old[:34])
        else:
            log.append("  ⚠️ 块内未找到画面段原文：%s…" % old[:34])

    if n in AUDIO_FIX:
        old, new = AUDIO_FIX[n]
        if old in blk:
            blk = blk.replace(old, new, 1)
            log.append("  Audio 去引号：%s…" % new[:30])
        else:
            log.append("  ⚠️ 块内未找到 Audio 原文")

    return src[:s] + blk + src[e:], log



def main():
    dry = "--dry" in sys.argv or "--apply" not in sys.argv
    verify = "--verify" in sys.argv

    files = sorted(set(v[0] for v in LEAK_SHOTS.values()))
    if verify:
        print("=" * 78)
        print("校验：各泄漏镜的画面段是否已无 `**`、且含禁令")
        print("=" * 78)
        bad = 0
        for f in files:
            p = os.path.join(OUT, f)
            src = open(p, encoding="utf-8").read()
            for n in sorted(LEAK_SHOTS):
                if LEAK_SHOTS[n][0] != f:
                    continue
                rng = find_block(src, n)
                if not rng:
                    print("  镜 %-3d  ✗ 找不到块" % n)
                    bad += 1
                    continue
                blk = src[rng[0]:rng[1]]
                # 只看画面段（Audio 之前）
                vis = blk.split('"Audio:')[0]
                stars = vis.count("**")
                has_ban = "不得出现任何可读的文字" in blk
                mark = "✅" if stars == 0 and has_ban else "❌"
                if stars or not has_ban:
                    bad += 1
                print("  镜 %-3d  %s  画面段 `**`=%d  禁令=%s"
                      % (n, mark, stars, "有" if has_ban else "无"))
        print("\n%s（%d 处待处理）" % ("全部通过 ✅" if bad == 0 else "仍有问题", bad))
        return 0 if bad == 0 else 1

    print("=" * 78)
    print("字幕泄漏镜 prompt 改写（配方：去 `**` + 加禁令 + Audio 去引号）")
    print("模式：%s" % ("DRY-RUN（不改文件）" if dry else "APPLY（就地改写）"))
    print("=" * 78)

    for f in files:
        p = os.path.join(OUT, f)
        src = open(p, encoding="utf-8").read()
        orig = src
        print("\n[%s]" % f)
        for n in sorted(LEAK_SHOTS):
            if LEAK_SHOTS[n][0] != f:
                continue
            print("  镜 %d：" % n)
            src, log = apply_edits(src, n)
            for line in log:
                print(line)
            src, existed = insert_ban(src, n)
            print("  %s追加禁令%s" % ("  " if not existed else "  ",
                                    "（已存在，跳过）" if existed else
                                    "：★ 全画面不得出现任何可读的文字、字幕或符号。"))
        if src != orig and not dry:
            bak = p + ".delleak.bak"
            if not os.path.exists(bak):
                shutil.copy2(p, bak)
            open(p, "w", encoding="utf-8", newline="").write(src)
            print("  ✅ 已写入（备份 %s）" % os.path.basename(bak))
        elif src != orig:
            print("  （dry-run：未写入）")
        else:
            print("  （无改动）")

    print()
    if dry:
        print("⚠️ 这是 dry-run。确认无误后加 --apply 真正改写，再跑 --verify。")
    else:
        print("下一步：py -3.10 OUTPUT/_delleak_prompt.py --verify")
        print("       然后重跑这 8 镜（各幕脚本带镜号）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

