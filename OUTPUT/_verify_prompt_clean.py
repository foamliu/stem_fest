# -*- coding: utf-8 -*-
"""校验：幕脚本里**实际会送给 H3 的 prompt**是否还含污染文本。

背景
    2026-09-15 视觉检查铁证：H3 会把 prompt 里的**指令/元信息**渲染成画面字幕：
      · 镜 5 底部「本镜不要生成任何可语午白」  ← NO_SPEECH 常量
      · 镜 19 底部「全镜高适」                  ← 同一常量幻觉
      · 镜 91 中部「像在消化一件很难立刻接受」  ← 舞台指示
    因此必须校验**拼接后的最终 prompt**（含 + CONST 展开），而不是源码文本。

与 _scan_hazard.py 的区别
    _scan_hazard.py 是**扫描器**（列清单，含注释误报）。
    本脚本是**闸门**（gate）：只检查拼接后的真 prompt，非零退出即禁止开跑。
    规则更严：任何「本镜/该镜/不要生成/只允许/若画面」出现在真 prompt 里就 FAIL。

用法：
    py -3.10 OUTPUT/_verify_prompt_clean.py
    py -3.10 OUTPUT/_verify_prompt_clean.py --show=5
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")
SCRIPTS = ["_diag_act0_plane.py", "_diag_act1_trench.py", "_diag_act2_startup.py",
           "_diag_act3_rice.py", "_diag_act4_train.py", "_diag_act5_finale.py"]

# 出现在**真 prompt** 里即为污染（这些是"对模型说的话"，不是"对画面的描述"）
BANNED = [
    (r"本镜头?[^。；\n]{0,30}", "本镜指代"),
    (r"该镜[^。；\n]{0,30}", "该镜指代"),
    (r"此镜[^。；\n]{0,30}", "此镜指代"),
    (r"不要生成[^。；\n]{0,30}", "否定式指令"),
    (r"只允许[^。；\n]{0,30}", "否定式指令"),
    (r"若画面[^。；\n]{0,30}", "条件指令"),
    (r"不要把它念[^。；\n]{0,20}", "否定式指令"),
    (r"画面里不能少人", "否定式指令"),
    (r"没有说任何话", "否定式声明"),
    (r"没有任何台词", "否定式声明"),
    (r"像在[^。；\n]{0,30}", "内心状态"),
    (r"像是在[^。；\n]{0,30}", "内心状态"),
    (r"仿佛在[^。；\n]{0,30}", "内心状态"),
    # ★ 2026-09-16 新增：抽象情绪短语（"…的笃定/释然/坦然…"）
    #   镜 99 事故 —— prompt 画面描述里写「只有一种走过来的笃定」，
    #   H3 把它**当成台词念了出来**（ASR 实得"体育竞技不能成就一走过来的笃定"）。
    #   根因：抽象"…的X"短语紧邻 Audio 台词区、且以"的"结尾像话术 → 被归入语音流。
    #   规则：画面描述里凡出现「一种…的X」「带着…的X」这类抽象情绪名词化写法即 FAIL，
    #        应改写为具体可拍的行为（如"目光平稳、神情克制、没有炫耀的意思"）。
    (r"一种[^；。\n]{0,12}的(笃定|释然|坦然|沉重|克制|温柔|坚定|悲悯|沧桑|心事|回忆感)", "抽象情绪名词化"),
    (r"带着[^；。\n]{0,12}的(笃定|释然|坦然|沉重|克制|温柔|坚定|悲悯|沧桑|心事|回忆感)", "抽象情绪名词化"),
    (r"有一种[^；。\n]{0,12}的(笃定|释然|坦然|沉重|克制|温柔|坚定|悲悯|沧桑|心事|回忆感)", "抽象情绪名词化"),
    # ★ 2026-09-16 新增：阿拉伯数字读音陷阱
    #   镜 97 事故 —— prompt 写「打破过全国 400 米栏纪录」，H3 念成「四十米栏」。
    #   根因：阿拉伯数字 + 空格分写，H3 按逐位/近似读法处理，丢掉了百位。
    #   规则：台词里凡出现 3 位以上阿拉伯数字（年份/记录/数量）一律应为中文数字。
    #   只查 **Audio 段之后**（台词区），画面描述里的数字无读音问题。
    (r"(?<=说：)[^\n]*\d{3,}", "阿拉伯数字台词（须改中文数字）"),
    (r"(?<=问：)[^\n]*\d{3,}", "阿拉伯数字台词（须改中文数字）"),
    (r"(?<=嘱咐：)[^\n]*\d{3,}", "阿拉伯数字台词（须改中文数字）"),
    # ★ 2026-09-17 新增：**「关于语音的元词汇」**（ONLY_THIS_LINE 初版事故）
    #   事故：为了压"前边合成多余语音"，初版写了
    #     「全程只有这一个说话人的声音，只有上面这一句台词，…没有其他任何人声、
    #       没有第二个人说话、没有旁白、没有念白、没有背景人声对白。」
    #   ⇒ H3 **把这段"对模型说的话"当台词念了出来**（ASR 实得）：
    #       镜 7「你少自恋了，**只有上面这一句台词**」
    #       镜 13「你少说两句就不会。**只有上一句抬口**」
    #       镜 15「你输在轻敌，**全程只有这个外死的**」
    #   与 §4.4 旧版 NO_SPEECH 被渲染成画面字幕**是同源错误**。
    #   规则：真 prompt 里**不得出现任何"关于语音本身"的元词汇** ——
    #   提"台词/对白/人声/旁白/念白/语音/说话声"本身就在提示 H3
    #   "这里有一段话要说"，它会自己补一句出来。
    #   正解 = **纯正向音景**：只描述"有什么环境声"，不提"语音"二字。
    (r"第二个人说话", "语音元词汇"),
    (r"没有旁白", "语音元词汇"),
    (r"没有念白", "语音元词汇"),
    (r"背景人声对白", "语音元词汇"),
    (r"只有这[一二]句台词", "语音元词汇"),
    (r"只有上面这一句", "语音元词汇"),
    (r"没有其他任何人声", "语音元词汇"),
    (r"不要生成[^。；\n]{0,20}(人声|语音|对白|台词)", "语音元词汇"),
    # ★ 2026-09-17 追加（镜 7 v2 实锤）：**"开口/说话人"这类动词与名词也是语音元词汇**
    #   镜 7 v2 用位置锚点写了「画面最右边那位男生是唯一的说话人：…全程只有他一个人开口」，
    #   ASR 实得「你少自恋了。**全程只有他一个人开口**」—— 被念出来了。
    #   而同批用「照 <Picture 1> 的那位」句式的镜 13/14 **零污染**。
    #   ⇒ 规律：**"关于谁在说话"的元陈述会被念；"谁长什么样 + 正在念这句"的物理描述不会**。
    #   正解句式：`画面里正在念出这句台词的人就是这一位（严格照 <Picture 1> 长相与发型）；`
    #   配合"旁人"的写法：`他们看着他、嘴唇始终闭合，只入画一部分；`
    (r"唯一的说话人", "语音元词汇"),
    (r"只有[他她]一个人开口", "语音元词汇"),
    (r"只有[他她]一个人说话", "语音元词汇"),
    (r"都没有开口", "语音元词汇"),
    (r"不说话[，,]", "语音元词汇"),
    (r"唯一开口", "语音元词汇"),
]


def expand(txt, path):
    """把 6 个幕脚本的 TASKS[N] prompt 拼接成最终字符串（展开 + CONST）。"""
    consts = {}
    for m in re.finditer(r'^([A-Z][A-Z0-9_]{2,})\s*=\s*\(([^)]*)\)', txt, re.M | re.S):
        consts[m.group(1)] = "".join(re.findall(r'"([^"]*)"', m.group(2)))
    for m in re.finditer(r'^([A-Z][A-Z0-9_]{2,})\s*=\s*"([^"]*)"', txt, re.M):
        consts[m.group(1)] = m.group(2)

    out = {}
    for m in re.finditer(r"^TASKS\[(\d+)\]\s*=\s*dict\(", txt, re.M):
        n = int(m.group(1))
        i = m.end()
        depth, start = 1, i
        while i < len(txt) and depth:
            if txt[i] == "(":
                depth += 1
            elif txt[i] == ")":
                depth -= 1
            i += 1
        body = txt[start:i]
        pm = re.search(r"prompt\s*=\s*\(", body, re.S)
        if not pm:
            out[n] = ""
            continue
        j = pm.end()
        d2, s2 = 1, j
        while j < len(body) and d2:
            if body[j] == "(":
                d2 += 1
            elif body[j] == ")":
                d2 -= 1
            j += 1
        seg = body[s2:j]
        buf = []
        for t in re.split(r"\+|\n", seg):
            t = t.strip()
            if not t:
                continue
            lit = re.findall(r'"([^"]*)"', t)
            if lit:
                buf.append("".join(lit))
            elif t in consts:
                buf.append(consts[t])
        out[n] = "".join(buf)
    return out


def main():
    show = None
    for a in sys.argv[1:]:
        if a.startswith("--show="):
            show = int(a.split("=", 1)[1])

    allp = {}
    for s in SCRIPTS:
        p = os.path.join(OUT, s)
        if os.path.exists(p):
            for n, t in expand(open(p, encoding="utf-8").read(), p).items():
                allp[n] = (s, t)

    if show:
        s, t = allp.get(show, ("?", ""))
        print("=== 镜 %d（%s）真 prompt ===" % (show, s))
        print(t)
        return 0

    bad = {}
    for n in sorted(allp):
        s, t = allp[n]
        for pat, name in BANNED:
            for m in re.finditer(pat, t):
                f = m.group(0).strip()
                if len(f) >= 3:
                    bad.setdefault(n, []).append((name, f))

    print("校验 %d 镜的真 prompt（已展开常量）" % len(allp))
    if not bad:
        print("\n✅ PASS —— 无污染文本，可以开跑")
        return 0
    print("\n❌ FAIL —— %d 镜仍含污染文本：\n" % len(bad))
    for n in sorted(bad):
        print("  镜 %d (%s)" % (n, allp[n][0]))
        seen = set()
        for name, f in bad[n]:
            if f in seen:
                continue
            seen.add(f)
            print("      [%s] %s" % (name, f[:90]))
    return 1


if __name__ == "__main__":
    sys.exit(main())
