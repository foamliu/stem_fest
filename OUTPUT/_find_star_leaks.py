# -*- coding: utf-8 -*-
"""精确找出**真 prompt 里**残留的 Markdown `**`（排除脚本注释与文档字符串）。

★ 为什么要区分：`_diag_*.py` 的**注释**里大量使用 `**加粗**` 作语义强调，
  这是给人看的、不进 prompt，**无害**。真正有害的只有**字符串字面量里**的 `**`
  （README §6.6：`**` 会被 H3 当画面文字画出来，实测镜 7 出过 `** 也不抬`）。

★ 做法：用 importlib 真正加载脚本 → 取 `TASKS[n]['prompt']` → 在这些**最终字符串**里找。
   这比 grep 源码可靠（grep 无法区分注释与字符串）。

用法：py -3.10 OUTPUT/_find_star_leaks.py
"""
import importlib.util
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = [
    "_diag_act0_plane.py", "_diag_act2_startup.py", "_diag_act1_trench.py",
    "_diag_act3_rice.py", "_diag_act4_train.py", "_diag_act5_finale.py",
]

hits = []
for s in SCRIPTS:
    path = os.path.join(ROOT, "OUTPUT", s)
    if not os.path.exists(path):
        print("!! 缺脚本 %s" % s)
        continue
    name = "mod_" + s.replace(".py", "")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        print("!! %s 加载失败：%r" % (s, e))
        continue
    for n, t in sorted(getattr(mod, "TASKS", {}).items()):
        p = t.get("prompt", "")
        if "**" in p:
            hits.append((s, n, p.count("**"), t.get("slug", "")))

print("=" * 70)
if not hits:
    print("✅ 真 prompt 里零 `**` 残留（全部 6 幕）")
else:
    print("🔴 发现 %d 处真 prompt `**` 残留：" % len(hits))
    for s, n, c, slug in hits:
        print("   镜 %-4d %s  ×%d  (%s)" % (n, slug, c, s))

# ── 附加闸门：其它常见泄漏标记（README §6.6 / §6.10.8）──
#   ⚠️ 判据必须用**strip_late_audio 之后**的 prompt，不能用源码里的原始串。
#      实测：源码里有 `（后期）` 的镜（96-103 / 107-118 等）在**运行时**会被
#      `strip_late_audio()` 整句剔除 ⇒ 最终 prompt 里是 0 处（镜 104 已实证）。
#      若改成拿源码串判，会误报十几镜 —— 这正是"筛查器口径必须与真实链路一致"。
#   ⇒ 本闸门只查**不该被 strip 掉**的标记：`**` / `__` / `<br>`。
#      需要检查 `（后期）` 是否真被 strip 掉，另见 `_dump_shot.py` 的输出复核。
EXTRA = [("**", "Markdown 加粗"), ("__", "Markdown 下划线加粗"),
         ("<br>", "HTML 换行标签"), ("（注：", "残留注记"),
         ("（说明：", "残留说明")]
extra_hits = []
for s in SCRIPTS:
    path = os.path.join(ROOT, "OUTPUT", s)
    if not os.path.exists(path):
        continue
    name = "mod_" + s.replace(".py", "")
    mod = sys.modules.get(name)
    if mod is None:
        continue
    for n, t in sorted(getattr(mod, "TASKS", {}).items()):
        # ★ 必须过一遍 strip_late_audio，与真实链路一致
        p = t.get("prompt", "")
        fn = getattr(mod, "strip_late_audio", None)
        if callable(fn):
            try:
                p = fn(p)
            except Exception:
                pass
        for tok, desc in EXTRA:
            if tok in p:
                extra_hits.append((s, n, tok, desc))

print()
if not extra_hits:
    print("✅ 附加闸门：strip 后的真 prompt 里零泄漏标记")
else:
    print("🔴 附加闸门命中 %d 处：" % len(extra_hits))
    for s, n, tok, desc in extra_hits:
        print("   镜 %-4d  %-8s %s  (%s)" % (n, tok, desc, s))

sys.exit(1 if (hits or extra_hits) else 0)
