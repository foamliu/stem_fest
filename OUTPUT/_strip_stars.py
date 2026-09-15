# -*- coding: utf-8 -*-
"""全片画面段 `**` 批量清理（去泄漏化，第二轮：非泄漏镜的预防性清理）。

★ 依据（README §6.6）
    `**` 会被 H3 当画面文字画出来（镜 7 实测 `** 也不抬`），是**概率放大器**：
    全片 62/126 镜画面段含 `**`，实测泄漏 9 镜（≈14% 命中）。
    ⇒ 既然改 prompt 已被证有效（镜 7：8 帧泄漏 → 8 帧干净），
      就应把**画面段的 `**` 全清掉**，把泄漏面压到最低。

★ 不动的两类（白名单）
    A. **有意要画面出现文字**的镜 —— 这些 `**` 是"要 H3 把字写出来"：
       镜 79（请让她看清文件上的字）、镜 117（屏幕字幕「科技要为人民服务。」）、
       镜 122（屏幕「如愿·看见」）。
       ⚠️ 这类**必须保留 `**` 甚至加强**，正是 README §6.9「要让字被看见」的正例。
    B. **画面段没有 `**`** 的镜（本来就干净）。

★ 处理方式：`**X**` → `X`（去标记保语义）
    与镜 7 的成功配方一致：加粗只是给 Agent 看的语义强调，H3 不需要。

用法
    py -3.10 OUTPUT/_strip_stars.py --dry      # 预览（不改）
    py -3.10 OUTPUT/_strip_stars.py --apply    # 就地清理（自动备份）
"""
import io
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")

SCRIPTS = ["_diag_act0_plane.py", "_diag_act1_trench.py", "_diag_act2_startup.py",
           "_diag_act3_rice.py", "_diag_act4_train.py", "_diag_act5_finale.py"]

# ★ 白名单：画面里**有意要出现文字**的镜 —— 保留 `**`（甚至应加强）
KEEP_TEXT_SHOTS = {79, 117, 122}


def find_block(src, n):
    m = re.search(r"TASKS\[%d\]\s*=\s*dict\(" % n, src)
    if not m:
        return None
    nxt = re.search(r"\nTASKS\[|\n# ──", src[m.end():])
    end = m.end() + nxt.start() if nxt else len(src)
    return m.start(), end


def list_tasks(src):
    return [int(m.group(1)) for m in re.finditer(r"TASKS\[(\d+)\]\s*=\s*dict\(", src)]


def clean_source(src, keep):
    """返回 (新源码, [(镜号, 清除条数), ...])。

    ★ 关键：只清 **Audio: 之前** 的 `**`（画面段）。
      `Audio:` 段的台词**不加粗**（本片脚本惯例），所以影响面可控；
      但若某镜 Audio 段真含 `**`，也一并清（对 H3 同样有害）。
    """
    report = []
    for n in list_tasks(src):
        if n in keep:
            report.append((n, 0, "白名单·保留"))
            continue
        rng = find_block(src, n)
        if not rng:
            continue
        s, e = rng
        blk = src[s:e]
        cnt = blk.count("**")
        if not cnt:
            continue
        # `**X**` → `X`；夹在 `**` 之间的内容原样保留
        new = re.sub(r"\*\*(.+?)\*\*", r"\1", blk, flags=re.S)
        # 兜底：清掉落单的 `**`
        new = new.replace("**", "")
        src = src[:s] + new + src[e:]
        report.append((n, cnt // 2, "已清理"))
    return src, report


def main():
    dry = "--dry" in sys.argv or "--apply" not in sys.argv
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    print("=" * 80)
    print("全片画面段 `**` 清理（白名单保留：镜 %s）"
          % ", ".join(str(x) for x in sorted(KEEP_TEXT_SHOTS)))
    print("模式：%s" % ("DRY-RUN（不改文件）" if dry else "APPLY（就地清理）"))
    print("=" * 80)

    tot = 0
    for fn in SCRIPTS:
        p = os.path.join(OUT, fn)
        src = open(p, encoding="utf-8").read()
        orig = src
        src, rep = clean_source(src, KEEP_TEXT_SHOTS)
        changed = [(n, c, tag) for n, c, tag in rep if c]
        kept = [n for n, c, tag in rep if tag.startswith("白名单")]
        if kept:
            print("\n[%s]  白名单跳过（有意要画面文字）：镜 %s"
                  % (fn, ", ".join(str(x) for x in kept)))
        if not changed:
            continue
        print("\n[%s]  清理 %d 镜，共 %d 处 `**`"
              % (fn, len(changed), sum(c for _, c, _ in changed)))
        print("       镜号：" + ", ".join(str(n) for n, _, _ in changed))
        tot += sum(c for _, c, _ in changed)
        if not dry:
            bak = p + ".stars.bak"
            if not os.path.exists(bak):
                shutil.copy2(p, bak)
            open(p, "w", encoding="utf-8", newline="").write(src)
            print("       ✅ 已写入（备份 %s）" % os.path.basename(bak))

    print("\n" + "=" * 80)
    print("合计清除 %d 处 `**`" % tot)
    if dry:
        print("⚠️ DRY-RUN。确认后用 --apply 生效，再跑 _audit_stars.py 复核。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
