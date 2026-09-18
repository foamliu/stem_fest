# -*- coding: utf-8 -*-
"""批量 ASR 逐镜验收 —— 把每个镜头的音轨转写出来，与 storyboard 台词逐字比对。

★ 为什么必须做
    文字闸门只能挡"我们写进 prompt 的污染"，**挡不住 H3 自己加话**
    （前导乱音 / 把指令念出来 / 换人说话 / 多余语气词）。
    只有把成片音频回读成文字，才能发现"说了不该说的话"。

判定口径（去标点后宽松包含）
    match  净台词核心字完整出现在 ASR 文本里，且几乎无多余字     → 通过
    extra  核心字都在，但 ASR 里多出 ≥4 个明显不属于本镜的字      → 疑似多余语音
    miss   核心字缺失（念错 / 没念完 / 换了词）                   → 需重跑
    silent 近静音（本镜本应有台词）                               → 根本没开口
    TODO   还没有 ASR 结果（用 MCP 工具跑完后落缓存）

用法：
    py -3.10 OUTPUT/_audit_asr.py                       # 汇总（读缓存）
    py -3.10 OUTPUT/_audit_asr.py --shots=1,6,19-46      # 只看指定镜
    py -3.10 OUTPUT/_audit_asr.py --emit=OUTPUT/_asr_queue.txt   # 生成待跑队列
    py -3.10 OUTPUT/_audit_asr.py --put=7 --text=你少自恋了。     # 写缓存
    py -3.10 OUTPUT/_audit_asr.py --redo                 # 忽略已有缓存
"""
from __future__ import annotations
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(HERE, "_asr_cache")
DIRS = ["01_paper_plane", "04_classroom_dusk", "06_trench",
        "07_rice_field", "08_train_dining", "05_classroom_night"]

sys.path.insert(0, HERE)
from _dump_sb import parse, net_line  # noqa: E402


def newest_per_shot():
    """每个镜号取 mtime 最新的 mp4（与 _concat_video.py 口径一致）。"""
    best = {}
    for d in DIRS:
        p = os.path.join(HERE, d, "video")
        if not os.path.isdir(p):
            continue
        for f in os.listdir(p):
            m = re.match(r"^(\d{1,3})_.*\.mp4$", f)
            if not m:
                continue
            n = int(m.group(1))
            fp = os.path.join(p, f)
            if n not in best or os.path.getmtime(fp) > os.path.getmtime(best[n]):
                best[n] = fp
    return best


DIG = {"0": "零", "1": "一", "2": "二", "3": "三", "4": "四",
       "5": "五", "6": "六", "7": "七", "8": "八", "9": "九"}


def _num2cn(numstr: str) -> str:
    """阿拉伯数字串 → 中文读法（74→七十四；1961→一九六一；2026→二零二六）。

    规则（与 H3/ASR 的实际朗读口径对齐）：
      · 4 位且像年份（19xx/20xx）→ 逐位读：一九六一
      · 2 位数值 → 数值读法：七十四
      · 其他 → 逐位读
    """
    n = int(numstr)
    if len(numstr) == 4 and (numstr.startswith("19") or numstr.startswith("20")):
        return "".join(DIG[c] for c in numstr)          # 年份逐位
    if len(numstr) <= 2:
        if n < 10:
            return DIG[numstr]
        if n == 10:
            return "十"
        if n < 20:
            return "十" + DIG[str(n % 10)]
        return DIG[str(n // 10)] + "十" + (DIG[str(n % 10)] if n % 10 else "")
    return "".join(DIG[c] for c in numstr)


def net_line_from_script(prompt: str) -> str:
    """从**幕脚本的真 prompt**里抽出净台词（右侧 of `：`，去掉后期音效句）。

    ★ 为什么以脚本为准而不是 storyboard
      全片 ASR 验收的目的有两个：
        ① **正确性** —— H3 有没有念错、漏念、多念？（对照**脚本**）
        ② **一致性** —— 脚本与 storyboard 有没有漂移？（对照 storyboard，另一个闸门管）
      若用 storyboard 当基准，会把**我们刻意改写以规避同音错**的镜（如
      `物资→补给`、`稻子→禾苗`）误判成 miss。
      ⇒ 本脚本用**脚本台词**判 ①，用 `_audit_storyboard.py` 判 ②。
    """
    i = prompt.find("Audio:")
    if i < 0:
        return ""
    aud = prompt[i + len("Audio:"):]
    # ★ 先砍掉 `ONLY_THIS_LINE` / `NO_SPEECH` 这类**音景后缀**（它们本身没有冒号，
    #   但若其文案含冒号会污染抽取；且它们属于"音景"不属于"台词"）
    for tag in ("其余是", "安静的室内环境底噪", "野外开阔地的环境底噪",
                "高铁车厢行进中", "安静教室的夜晚", "田野开阔地的环境底噪"):
        j = aud.find(tag)
        if j >= 0:
            aud = aud[:j]
    # 去掉 `（后期）` 句
    kept = [s for s in re.split(r"(?<=[；。])", aud) if "（后期）" not in s]
    aud = "".join(kept)
    # ★ 取出**所有**说话人段落（一镜内可换人说话，如镜 39/80/85），
    #   拼成"完整台词串"再判定 —— 否则只取第一句会把第二人的台词判成 miss。
    parts = re.findall(r"[：:]\s*([^：:\n]+)", aud)
    if parts:
        return net_line("".join(parts)).strip()
    return ""


def script_lines_by_shot():
    """从 6 个幕脚本里抽出每镜的**实际台词**（= 我们会喂给 H3 的那一句）。"""
    out = {}
    mods = ["_diag_act0_plane", "_diag_act1_trench", "_diag_act2_startup",
            "_diag_act3_rice", "_diag_act4_train", "_diag_act5_finale"]
    for mn in mods:
        try:
            m = __import__(mn)
        except Exception:
            continue
        for n, t in m.TASKS.items():
            ln = net_line_from_script(t.get("prompt", ""))
            if ln:
                out[n] = ln
    return out


# ★ 本轮为规避同音错而**刻意做的改写**（验收时应视为等价，不算 miss）
#   README §6.10.9 ③：H3 按发音重建台词，同音字会错 ⇒ 改句子比加拼音锚点有效。
SUBST = [
    ("物资", "补给"),        # 镜 22
    ("稻子", "禾苗"),        # 镜 57/60/70
    ("稻穗", "禾苗"),        # 镜 55（稻穗→皱穗，改禾苗）
    ("种得活不活", "能不能种活"),  # 镜 72
    ("戴好", "记得戴上"),     # 镜 103
    ("继光", "黄继光"),      # 镜 36/42（改用全名，语音上下文更强）
    ("稻穗下", "禾下"),      # 镜 70
]


def canon(s: str) -> str:
    """把"改写过的同义说法"归一成同一串，避免把刻意改写判成 miss。"""
    for a, b in SUBST:
        s = s.replace(b, a)
    return s


def core(s: str) -> str:
    """去标点 + 数字归一化 —— 用于宽松包含判定。

    ★ 2026-09-17：必须做数字归一化。storyboard 写「74年后」「1961年」「2026年」，
      ASR 一律回读成「七十四年后」「一九六一年」「二零二六年」——
      这是**朗读口径**差异，不是缺陷；不归一化会误报一大批（本轮实测误报 4 处）。
    """
    s = s or ""
    s = re.sub(r"\d+", lambda m: _num2cn(m.group()), s)
    return re.sub(r"[^\u4e00-\u9fa5A-Za-z]", "", s)


def parse_range(spec: str):
    out = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def cache_path(n):
    return os.path.join(CACHE, "shot%03d.txt" % n)


def main():
    shots_filter, emit = None, None
    put, put_text = None, None
    redo = "--redo" in sys.argv
    for a in sys.argv[1:]:
        if a.startswith("--shots="):
            shots_filter = parse_range(a.split("=", 1)[1])
        elif a.startswith("--emit="):
            emit = a.split("=", 1)[1]
        elif a.startswith("--put="):
            put = int(a.split("=", 1)[1])
        elif a.startswith("--text="):
            put_text = a.split("=", 1)[1]

    if put is not None:
        os.makedirs(CACHE, exist_ok=True)
        io.open(cache_path(put), "w", encoding="utf-8").write(put_text or "")
        print("已写缓存 shot%03d.txt = %r" % (put, put_text))
        return 0

    sb = parse()
    have = newest_per_shot()
    todo = sorted(n for n in have if 1 <= n <= 126)
    if shots_filter:
        todo = [n for n in todo if n in shots_filter]

    # ★ 只校验**已重跑**的镜：命令 `--newer=<时间>` 只检查文件 mtime 晚于该时间的镜。
    #   用途：改完 prompt 重跑后，只验收新产物，不去翻旧版的账。
    newer = None
    for a in sys.argv[1:]:
        if a.startswith("--newer="):
            newer = float(a.split("=", 1)[1].replace("h", ""))
    if newer:
        import time as _t
        cut = _t.time() - newer * 3600
        todo = [n for n in todo if os.path.getmtime(have[n]) > cut]

    items = []
    script_lines = script_lines_by_shot()
    for n in todo:
        s = sb.get(n)
        if not s:
            continue
        # ★ 以**脚本真 prompt** 的台词为准（我们可能为规避同音错而刻意改写）；
        #   脚本里查不到该镜时回退到 storyboard。
        want = script_lines.get(n) or net_line(s["audio"])
        wc = core(want)
        if not wc:
            continue                     # 无台词镜不进 ASR 队列
        items.append((n, want, wc, have[n]))

    if emit:
        dest = emit if os.path.isabs(emit) else os.path.join(ROOT, emit)
        n_todo = 0
        with io.open(dest, "w", encoding="utf-8") as f:
            for n, want, wc, fp in items:
                done = os.path.exists(cache_path(n)) and not redo
                if not done:
                    n_todo += 1
                f.write("%d\t%s\t%s\t%s\n" % (n, "DONE" if done else "TODO",
                                              os.path.relpath(fp, ROOT).replace("\\", "/"),
                                              want))
        print("已写出 ASR 队列 -> %s（共 %d 镜，待跑 %d）" % (dest, len(items), n_todo))
        return 0

    rows = []
    for n, want, wc, fp in items:
        txt = ""
        if os.path.exists(cache_path(n)) and not redo:
            txt = io.open(cache_path(n), encoding="utf-8").read().strip()
        if not txt:
            rows.append((n, "TODO", want, "", ""))
            continue
        tc = core(txt)
        wc_c = core(canon(want))
        tc_c = core(canon(txt))
        if len(tc) < 2:
            verdict = "silent"
        elif wc_c in tc_c:
            verdict = "match" if len(tc_c) <= len(wc_c) + 3 else "extra"
        else:
            verdict = "miss"
        extra = tc_c.replace(wc_c, "") if wc_c in tc_c else tc_c
        rows.append((n, verdict, want, txt, extra))

    from collections import Counter
    cnt = Counter(r[1] for r in rows)
    print("有台词镜 %d  %s" % (len(rows), dict(cnt)))
    bad = [r for r in rows if r[1] in ("extra", "miss", "silent")]
    for n, v, w, t, e in bad:
        print("\n镜 %-3d %-6s\n  storyboard: %s\n  ASR       : %s\n  多出      : %s"
              % (n, v, w, t, e[:70]))
    dest = os.path.join(HERE, "_asr_audit.txt")
    with io.open(dest, "w", encoding="utf-8") as f:
        f.write("%-5s %-7s %-32s %s\n" % ("镜号", "判定", "storyboard 净台词", "ASR 实得"))
        f.write("-" * 112 + "\n")
        for n, v, w, t, e in rows:
            f.write("%-5d %-7s %-32s %s\n" % (n, v, w, t))
        f.write("-" * 112 + "\n")
        f.write("统计：%s\n" % dict(cnt))
    print("\n明细 -> %s" % dest)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
