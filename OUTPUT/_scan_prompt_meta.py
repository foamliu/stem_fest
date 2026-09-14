# -*- coding: utf-8 -*-
"""扫描所有幕级脚本的 prompt，找出**可能被 H3 当字幕画进画面**的写法。

已知事故（2026-09-14 镜 91）：
   prompt 里的舞台指示「像在消化一件很难立刻接受的事」被 H3 渲染成**画面底部字幕**。
   根因：把"演员内心状态/镜头用意"这类**元信息**写进了画面描述，
   模型无法表演"像在消化…"，只能选择"把这句话显示出来"。

规则（写 prompt 时必须遵守）：
   ✅ 只写**摄影机拍得到的**：人物动作、表情、景别、光线、环境
   ❌ 不写**元信息**：像在…/仿佛…/意在…/暗示…/显得…/说明…/表达…/暗示观众…
   ❌ 不写**镜头用意**：这是情绪高点 / 留白 / 转场 / 观众要读到…
   ❌ 不写**编号与说明**：镜 88 / 本镜 / 该镜

本脚本只**报告**，不改文件。
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = ["_diag_act0_plane.py", "_diag_act2_startup.py", "_diag_act1_trench.py",
           "_diag_act3_rice.py", "_diag_act4_train.py", "_diag_act5_finale.py"]

# 高危词（会把"用意/内心"暴露给模型 → 易变字幕）
PATTERNS = [
    (r"像在[^，。；]{2,20}", "比喻式内心状态"),
    (r"仿佛[^，。；]{2,20}", "比喻式内心状态"),
    (r"像是[^，。；]{2,20}", "比喻式内心状态"),
    (r"显得[^，。；]{2,20}", "主观评价"),
    (r"说明[^，。；]{2,20}", "镜头用意"),
    (r"表达[^，。；]{2,20}", "镜头用意"),
    (r"暗示[^，。；]{2,20}", "镜头用意"),
    (r"意在[^，。；]{2,20}", "镜头用意"),
    (r"观众要?读到[^，。；]{0,20}", "镜头用意"),
    (r"是一?个?情绪[高点落点][^，。；]{0,20}", "镜头用意"),
    # ⚠️ 「本镜」在 NO_SPEECH 文案里是**合法**用法（"本镜不要生成任何…语音"），
    #    所以只在**不出现在 NO_SPEECH 句中**时才算高危
    (r"(?<!【)本镜(?!不要生成)", "镜头编号指代"),
    (r"该镜|这一镜", "镜头编号指代"),
]


def main():
    total = 0
    for f in SCRIPTS:
        p = os.path.join(ROOT, "OUTPUT", f)
        if not os.path.isfile(p):
            continue
        src = io.open(p, encoding="utf-8").read()
        # 只在 TASKS 段里扫（跳过文件头注释，那里可以随便写）
        i = src.find("TASKS = {}")
        body = src[i:] if i > 0 else src
        hits = []
        for m in re.finditer(r'TASKS\[(\d+)\] = dict\(', body):
            start = m.start()
            nxt = body.find("TASKS[", m.end())
            blk = body[start: nxt if nxt > 0 else len(body)]
            for pat, why in PATTERNS:
                for mm in re.finditer(pat, blk):
                    hits.append((int(m.group(1)), why, mm.group(0)[:40]))
        if hits:
            print("[%s] %d 处高危写法：" % (f, len(hits)))
            for n, why, txt in hits:
                print("   镜 %-3d  %-14s  %s" % (n, why, txt))
            total += len(hits)
    print()
    print("合计 %d 处（报告完毕，未改文件）" % total)


if __name__ == "__main__":
    main()
