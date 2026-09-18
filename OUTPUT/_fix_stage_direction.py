# -*- coding: utf-8 -*-
"""把 Audio 段里「<表演副词>地(说|问|喊|答)：」统一降级为「说：」等中性形式。

★ 事故（2026-09-17 全片 ASR 逐镜验收）
    镜 97 的 Audio 写成 `他平静地说：一九五九年，…`
    ⇒ ASR 实得「**他平静地说：**一九五九年，…」—— 表演提示被念了出来。
    同批另外 37 镜也写了 `X地<动词>：`，只是副词较短、H3 恰好跳过。

★ 为什么必须统一
    `Audio:` 段是给 H3 的**语音内容区**。里面出现「平静地/兴奋地/小声地」这类
    **表演指示**，就是在往语音流里塞"要被念出来的词"。短副词侥幸没被念，
    长副词（`他平静地说：`）就被念了 —— 这是概率问题，不是有没有问题。

★ 正解
    · 表演提示（怎么说）→ 移到 **CUT 段的画面描述**里（H3 会用画面表现语气）
    · Audio 段只留**谁说的 + 说了什么**：`他说：<台词>`
    · 人物身份指代要保留（H3 需要知道是哪一位在说），只去掉副词

用法：
    py -3.10 OUTPUT/_fix_stage_direction.py            # 预览
    py -3.10 OUTPUT/_fix_stage_direction.py --apply    # 落盘
"""
from __future__ import annotations
import glob
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# 「<前置描述>地<动词><冒号>」——只匹配 Audio: 之后的部分
PAT = re.compile(
    r"([\u4e00-\u9fa5\u3001\uff0c]{0,14})\u5730"
    r"(\u8bf4|\u95ee|\u558a|\u7b54|\u5631\u5490|\u5ff5\u51fa|\u91cd\u590d|\u62b1\u6028|\u56de\u7b54|\u5410\u9732|\u8865\u4e86\u4e00\u53e5)"
    r"([\uff1a:]|\u4e86\u4e00\u904d[\uff1a:])"
)

# 保留的身份指代（H3 靠它认人）；命中即作为前缀保留
IDS = ("\u5c0f\u5973\u5b69", "\u6bcd\u4eb2", "\u7537\u751f", "\u5973\u751f",
       "\u5c0f\u6218\u58eb", "\u6218\u58eb", "\u957f\u8005", "\u8001\u5e74\u7537\u6027",
       "\u4ed6", "\u5979")


def keep_identity(pre: str) -> str:
    """从 `<…>地` 的前缀里挑出身份指代，丢掉表演副词。

    ★ 为什么必须**保留身份**：H3 需要知道"是谁在说"才能把口型/表情给对人；
      只写 `说：` 会让它自由发挥（可能就是另一轮"说话人漂移"）。
    ★ 为什么要**丢掉副词**：`平静地/兴奋地/小声地` 属于"怎么演"的指示，
      写进 Audio 段就是往语音流里塞词 —— 镜 97 的 `他平静地说：` 被原样念了出来。
    """
    # 0) 先剁掉表演性从句：`XX抬起头，语气随意` / `擦掉眼泪、坚定` 这类
    pre = re.sub(r"^.*?[\uff0c\u3001]", "", pre) if re.search(r"[\uff0c\u3001]", pre) else pre
    # 1) 前缀里带身份词 → 取最小可用指代
    for w in ("\u5c0f\u5973\u5b69", "\u5c0f\u6218\u58eb", "\u957f\u8005",
              "\u8001\u5e74\u7537\u6027", "\u6bcd\u4eb2", "\u7537\u751f", "\u5973\u751f",
              "\u6218\u58eb"):
        i = pre.rfind(w)
        if i >= 0:
            return pre[i:]
    # 2) 兜底：只保留"指示代词 + 名词"的最短尾巴
    m = re.search(r"([\u8fd9\u90a3][\u4e00-\u9fa5]{0,4}(?:\u7537\u751f|\u5973\u751f|\u4eba|\u5b69\u5b50))$", pre)
    if m:
        return m.group(1)
    for w in ("\u4ed6", "\u5979"):
        if pre.endswith(w):
            return w
    return ""


def tidy(pre: str) -> str:
    """把 `战士抬起头，语气随意` 这类"动作+语气"尾巴剁掉，只剩身份。"""
    ident = keep_identity(pre)
    if ident:
        return ident
    # 无身份词：整段丢（都是表演描述）
    return ""


def process(text: str, audio_only: bool = True):
    out, hits = [], []

    def repl(m):
        pre, verb, colon = m.group(1), m.group(2), m.group(3)
        ident = keep_identity(pre)
        new = ident + verb + colon
        if new != m.group(0):
            hits.append((m.group(0), new))
        return new

    if not audio_only:
        return PAT.sub(repl, text), hits

    # 只改 `Audio:` 之后、到字符串或行末为止的片段
    pieces = re.split(r"(Audio:)", text)
    for i, seg in enumerate(pieces):
        if i > 0 and pieces[i - 1] == "Audio:":
            seg = PAT.sub(repl, seg)
        out.append(seg)
    return "".join(out), hits


def main():
    apply_ = "--apply" in sys.argv
    total = 0
    for p in sorted(glob.glob(os.path.join(HERE, "_diag_act*.py"))):
        t = io.open(p, encoding="utf-8").read()
        new, hits = process(t)
        if not hits:
            continue
        print("=== %s : %d 处 ===" % (os.path.basename(p), len(hits)))
        for a, b in hits:
            print("    %-28r -> %r" % (a, b))
        total += len(hits)
        if apply_:
            io.open(p, "w", encoding="utf-8", newline="").write(new)
    print("\n共 %d 处%s" % (total, "，已落盘" if apply_ else "（预览，加 --apply 落盘）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
