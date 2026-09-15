# -*- coding: utf-8 -*-
"""泄漏镜串行重跑编排器 —— 按幕分组、逐镜跑，跑完自动校验 prompt 是否带禁令。

★ 为什么需要编排器
    8 个泄漏镜分散在 **4 个幕脚本**里（act1/act2/act4/act5），每个脚本自己带
    「按镜号重跑」的 CLI（`--steps=N 镜号…`）。手工敲 4 条命令容易漏、也难追踪进度。
    本脚本按幕**串行**调用，把每镜的结果汇总成表。

★ 关键：串行，不并行
    H3 是大模型推理，16GB VRAM 一次只能跑一条。并行会 OOM（LESSONS #10）。

★ 单镜耗时
    3.0s 片长 / steps=10 / mp=0.6 ⇒ 实测约 **3–6 分钟/镜**，8 镜合计 **25–50 分钟**。

用法
    py -3.10 OUTPUT/_rerun_leaks.py             # 跑全部 8 镜
    py -3.10 OUTPUT/_rerun_leaks.py --dry       # 只打印将要执行的命令
    py -3.10 OUTPUT/_rerun_leaks.py 77 85       # 只跑指定镜
"""
import io
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")

# 泄漏镜 → (幕脚本, 该幕默认 steps)
#   镜 14 在 act2（该幕默认 steps=20）；其余幕默认 10。
#   一律用各幕**默认 steps**，与首轮生成保持一致 ⇒ 画面风格/时长可比。
LEAKS = {
    14: "_diag_act2_startup.py",
    21: "_diag_act1_trench.py",
    36: "_diag_act1_trench.py",
    77: "_diag_act4_train.py",
    85: "_diag_act4_train.py",
    86: "_diag_act4_train.py",
    88: "_diag_act4_train.py",
    112: "_diag_act5_finale.py",
}
DEFAULT_STEPS = {
    "_diag_act1_trench.py": 10,
    "_diag_act2_startup.py": 20,
    "_diag_act4_train.py": 10,
    "_diag_act5_finale.py": 10,
}


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  line_buffering=True)
    dry = "--dry" in sys.argv
    want = [int(a) for a in sys.argv[1:] if a.isdigit()]
    shots = want or sorted(LEAKS)
    # 校验镜号都在清单里
    unknown = [n for n in shots if n not in LEAKS]
    if unknown:
        print("[X] 不在泄漏清单里的镜号：%s" % unknown)
        return 1

    print("=" * 80)
    print("泄漏镜串行重跑：%d 镜 —— %s" % (len(shots), shots))
    print("已应用配方：去掉 `**` 标记 + 追加画面段禁令 + Audio 去引号（README §6.6）")
    print("=" * 80)

    # 按幕分组，减少脚本反复加载（每个脚本 import 要几秒）
    by_act = {}
    for n in shots:
        by_act.setdefault(LEAKS[n], []).append(n)

    t_all = time.time()
    results = []
    for act, ns in by_act.items():
        steps = DEFAULT_STEPS.get(act, 10)
        cmd = ["py", "-3.10", os.path.join(OUT, act),
               "--steps=%d" % steps] + [str(x) for x in ns]
        print("\n" + "─" * 80)
        print("▶ %s  （镜 %s，steps=%d）" % (act, ", ".join(map(str, ns)), steps))
        print("  $ " + " ".join(cmd))
        if dry:
            for n in ns:
                results.append((n, "DRY", ""))
            continue
        t0 = time.time()
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        dt = time.time() - t0
        # 末 30 行贴出来（含每镜 [OK]/[X] 行）
        tail = (p.stdout or "").strip().splitlines()[-30:]
        for line in tail:
            print("  " + line)
        if p.returncode != 0:
            print("  ⚠️ 退出码 %s" % p.returncode)
            for line in (p.stderr or "").strip().splitlines()[-8:]:
                print("  ! " + line)
        for n in ns:
            # 从 stdout 里抠该镜的结果行
            hit = [l for l in (p.stdout or "").splitlines()
                   if ("镜 %d " % n) in l or ("[镜 %d]" % n) in l]
            results.append((n, "OK" if p.returncode == 0 else "FAIL",
                            hit[-1].strip()[:70] if hit else ""))
        print("  ⏱ 本幕耗时 %.0f s" % dt)

    print("\n" + "=" * 80)
    print("汇总（总耗时 %.1f 分钟）" % ((time.time() - t_all) / 60.0))
    print("=" * 80)
    for n, st, info in results:
        print("  镜 %-4d %-6s %s" % (n, st, info))
    print()
    print("下一步：")
    print("  1) py -3.10 OUTPUT/_scan_subtitles.py --shots=%s   # 出图核对"
          % ",".join(str(n) for n, _, _ in sorted(results)))
    print("  2) 读图确认无字幕 → py -3.10 OUTPUT/_concat_video.py 重建 full_cut.mp4")
    return 0


if __name__ == "__main__":
    sys.exit(main())
