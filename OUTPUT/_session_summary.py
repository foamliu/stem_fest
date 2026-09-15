# -*- coding: utf-8 -*-
"""生成《本轮工作总结》 —— 12h 自主执行的结果固化（纯 CPU，可反复重跑）。

与 `_make_report.py` 的分工
    `_make_report.py`   → **素材质检报告**（覆盖度/人脸/成片指标），面向"片子好不好"
    本脚本              → **工作总结**，面向"这轮干了什么、还有什么没干"

用法
    py -3.10 OUTPUT/_session_summary.py
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")


def main():
    L = []
    L.append("# 《如愿·看见》本轮工作总结")
    L.append("")
    L.append("生成时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    L.append("")
    L.append("## 一、本轮解决的问题（3 类画面文字缺陷，性质完全不同）")
    L.append("")
    L.append("| # | 缺陷 | 成因 | 覆盖 | 状态 |")
    L.append("|:-:|---|---|---|---|")
    L.append("| 1 | **prompt 元信息污染** | prompt 里写了"
             "「本镜不要生成任何…」「像在消化…」这类**对模型说的话** |"
             " 41 镜需重跑 | ✅ **已修 + 已 A/B 验证** |")
    L.append("| 2 | **台词被渲染成字幕** | `Audio:` 段写**具体台词原文**，"
             "H3 分不清\"要它念\"与\"要它显示\" | 风险面 **80 镜（63%）**，"
             "**实际泄漏 9 镜（7%）** | 🔴 **已逐条溯源，待决策** |")
    L.append("| 3 | **中文长句乱码** | H3 想写中文但写错（纯字幕屏最不稳）|"
             " 2 镜（123/124）| ✅ **已用 ffmpeg 后期烧字** |")
    L.append("")
    L.append("## 二、已完成的工作")
    L.append("")
    L.append("### 1. 41 镜重跑（0 失败）")
    L.append("")
    L.append("| 批次 | 含义 | 镜数 | 状态 |")
    L.append("|---|---|---|:--:|")
    L.append("| P1 | 否定式残留新修 | 6 | ✅ |")
    L.append("| P2 | `NO_SPEECH` 引用 | 28 | ✅ |")
    L.append("| P3 | 元信息旧视频 | 7 | ✅ |")
    L.append("| | **合计** | **41** | ✅ |")
    L.append("")
    L.append("### 2. 字幕污染修复验证（A/B 铁证）")
    L.append("")
    L.append("| 镜 | 修复前 | 修复后 |")
    L.append("|---|---|---|")
    L.append("| 5 | 「本镜不要生成任何可□旁白」| ✅ 无字幕 |")
    L.append("| 110 | 「不镜不要生成任何可□旁白」（3/3 帧）| ✅ 3/3 帧无字幕 |")
    L.append("| 91 | 「像在消化一件很难以刻接受」+ 英文乱码（3/3 帧）| ✅ 3/3 帧无字幕 |")
    L.append("")
    L.append("### 3. 成片重拼 + 体检")
    L.append("")
    L.append("- `OUTPUT/full_cut.mp4` 重拼（无损 `-c copy`）："
             "**1056×608 h264 + aac 32000Hz 2ch，593.0 s，101.3 MB，126 镜**")
    L.append("- 成片 24 帧量化抽检（`_check_final.py`）：**0 可疑帧**")
    L.append("- 音轨：mean −18.0 dB / max 0.0 dB，与视频时长对齐 ✅")
    L.append("")
    L.append("### 4. 新增工具（9 个）")
    L.append("")
    for name, what in [
        ("_coverage.py", "逐幕覆盖度体检（含权威「幕脚本→目录」表）"),
        ("_extract_frames.py", "全片抽帧（给 `_face_identity.py` 用）"),
        ("_face_audit_all.py", "人脸审计（**加脸高门限**，避免小脸误报）"),
        ("_face_rank.py", "人脸排名法（替代失效的绝对阈值）"),
        ("_face_tri.py", "帧/引用图/候选图**竖向三联**，人眼判硬特征"),
        ("_resume_rerun.py", "接管续跑（搬 ComfyUI 产物回项目 + 补跑）"),
        ("_burn_cards.py", "纯字幕屏**后期烧字**（H3 中文乱码的解法）"),
        ("_check_final.py", "成片抽检（亮度/对比度量化 + 拼图）"),
        ("_scan_subtitles.py", "全片**下部带**扫描台词泄漏（T1 扫不到）"),
        ("_line_risk.py", "列「Audio 含台词原文」的风险面"),
        ("_trace_leak.py", "**泄漏字幕溯源**（比对泄漏文字与 prompt 各段）"),
        ("_fix_line_pos.py", "风险镜清单 + 改写建议"),
        ("_cmp_prompt.py", "泄漏镜 vs 干净镜的写法对照"),
        ("_session_summary.py", "本总结（可重跑）"),
    ]:
        L.append("- `%s` —— %s" % (name, what))
    L.append("")
    L.append("## 三、方法论收获（已写入 README §6）")
    L.append("")
    L.append("| 收获 | 要点 |")
    L.append("|---|---|")
    L.append("| §6.4 修复已 A/B 验证 | 改 prompt 能修元信息污染；**提 steps 无效** |")
    L.append("| §6.5 人脸度量的陷阱 | ArcFace 绝对阈值**跨域失效**"
             "（本尊 0.28 vs 他人 0.25）；脸 <250px 不可判；**靠读图判硬特征** |")
    L.append("| §6.6 台词泄漏 | 风险面 **63%** 但**实际只 7%**（9 镜）；"
             "泄漏文字**逐条溯源**确认 8/9 来自 `Audio:` 段、1 例来自**画面段加粗**；"
             "位置在中部（**T1 扫不到，要 `_scan_subtitles.py`**）|")
    L.append("| §6.7 中文乱码 | H3 **多数能写对**中文（含长句）；"
             "**纯黑底白字的字幕屏最不稳** ⇒ 改后期烧字 |")
    L.append("| 读图铁律 | 条带图只能答\"有没有\"；判崩坏必须**全帧** |")
    L.append("")
    L.append("## 四、尚未处理 / 建议下一步")
    L.append("")
    L.append("| # | 事项 | 建议 | 成本 |")
    L.append("|:-:|---|---|:--:|")
    L.append("| 1 | **9 镜台词泄漏**（7/14/21/36/77/85/86/88/112）|"
             "先看整体观感；若要消，改 prompt 措辞（不写原文）重跑，"
             "或 `delogo` 遮罩 | 中 |")
    L.append("| 2 | 镜 49/66（刘思齐）face cos 偏低 | 参考图是**三视图全身照**"
             "`liu_siqi_hero_v01.png`（脸约 100px）⇒ 换 `liu_siqi_closeup_v02_16x9.png` 重跑 | 低 |")
    L.append("| 3 | 战壕戏军装臂章混用「青天白日旗」| 史实应为志愿军（五角星）；"
             "H3 训练数据里的中国军装混淆 ⇒ 需 prompt 明确或后期修 | 中 |")
    L.append("| 4 | 成片 593 s（计划 492 s）| H3 时长量化向上取整所致；"
             "如需精确得逐镜 trim | 低 |")
    L.append("| 5 | 镜 95 校服印花「育才系系」| AI 幻觉装饰文字，视觉无害；可不管 | — |")
    L.append("")
    txt = "\n".join(L)
    print(txt)
    p = os.path.join(OUT, "_SESSION_SUMMARY.md")
    open(p, "w", encoding="utf-8").write(txt)
    print("\n→ %s（%.1f KB）" % (p, os.path.getsize(p) / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
