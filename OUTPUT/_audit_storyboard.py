# -*- coding: utf-8 -*-
"""★ 全片「分镜一致性」审核：把生产脚本的 TASKS 与 storyboard 逐条比对，输出审核报告。

为什么要这个工具
    `_visual_review.py` 只出拼图（给人看），不产出**可判定的一致性结论**。
    本工具把 storyboard 的**结构化列**（时长 / 景别 / 运镜 / 台词 / 参考图）
    与脚本 `TASKS` 里的 `prompt` + `dur` + `refs` 逐条对齐，
    给出「✅一致 / ⚠️存疑 / 🔴漂移」三档判定 + 可执行修复建议。

六类校验（对应 storyboard 的六条硬约束）
    A. 时长：`TASKS[n].dur` 经 H3 量化（frames=17k+5 @24fps）后应等于 storyboard 时长
    B. 景别：storyboard「景别」列关键词须在 prompt 里，且**不得出现其他景别词**
    C. 运镜：storyboard「运镜」列须落在 prompt 里（允许同义词映射）
    D. 台词：storyboard 台词的净字须出现在 prompt 的 Audio 段
    E. 参考图：storyboard 要求的人数/角色应能从 refs 文件名推出
    F. 文字风险：prompt 里不得有 `**加粗**`、残留「（后期）」

用法：
    py -3.10 OUTPUT/_audit_storyboard.py                # 全 126 镜
    py -3.10 OUTPUT/_audit_storyboard.py --shots=14,21,36
    py -3.10 OUTPUT/_audit_storyboard.py --only-drift   # 只列 🔴 漂移
"""
import importlib.util
import math
import os
import re
import sys

ROOT = r"E:\code\stem_fest"
OUT = os.path.join(ROOT, "OUTPUT")
SB = os.path.join(ROOT, "storyboard.md")

SCRIPTS = [
    "_diag_act0_plane.py", "_diag_act2_startup.py", "_diag_act1_trench.py",
    "_diag_act3_rice.py", "_diag_act4_train.py", "_diag_act5_finale.py",
]

# storyboard「景别」列关键词（互斥：同一镜只用一个主景别）
ALL_SIZES = ["远景", "全景", "中近景", "中景", "近景", "特写"]

# storyboard「运镜」列 → prompt 允许的同义写法
MOVE_SYN = {
    "固定": ["固定", "静止", "机位不动", "三脚架"],
    "缓推": ["缓推", "缓慢推近", "推近", "dolly in"],
    "缓拉": ["缓拉", "缓慢拉远", "拉远", "后拉", "dolly out"],
    "缓慢横移": ["缓慢横移", "缓慢横向移动", "横移", "lateral"],
    "横摇": ["横摇", "横摇扫", "横摇扫过"],
    "横移": ["横移", "横向移动"],
    "跟移": ["跟移", "跟随", "跟拍"],
    "手持轻微": ["手持轻微", "手持"],
    "上摇": ["上摇", "向上摇"],
    "下摇": ["下摇", "向下摇"],
    "航拍跟拍": ["航拍", "跟拍", "掠过"],
    "缓推到手部": ["缓推", "推近", "到手部", "手部"],
    "缓推跟手": ["缓推", "跟手", "推近"],
    "跟移入窗": ["跟移", "入窗", "飞入"],
    "固定双人": ["固定", "双人"],
    "缓推双人": ["缓推", "双人"],
    "缓推到手部": ["缓推", "推近", "手部"],
    "缓慢横移（跟着窗外夜景）": ["缓慢横移", "横移"],
    "固定（转场留白）": ["固定"],
    "固定（三帧依次闪过）": ["固定"],
    "固定（定格收束）": ["固定"],
    "固定（黑屏字幕）": ["固定"],
    "固定（字幕淡出）": ["固定"],
    "跟移，随后定格": ["跟移", "定格"],
    "跟移，随后缓拉": ["跟移", "缓拉"],
    "缓推，白光吞没画面": ["缓推", "白光"],
    "缓推，照片弹出时轻微一顿": ["缓推"],
    "缓推，夹手瞬间轻微一震": ["缓推"],
    "缓推跟手指（跟全息屏上的点触）": ["缓推", "点触", "手指"],
    "手持轻微，跟她视线横摇": ["手持", "横摇"],
    "手持轻微（跟步）": ["手持"],
    "手持轻微（炮响时晃动）": ["手持"],
    "手持轻微（车厢到站时晃动）": ["手持"],
    "固定，甩手时轻微跟随": ["固定"],
    "固定，轻微跟随": ["固定"],
    "固定，轻微下摇": ["固定", "下摇"],
    "固定，轻微下摇跟手": ["固定", "下摇"],
    "固定，轻微后拉": ["固定", "背后"],
    "固定，轻微横移": ["固定", "横移"],
    "固定，轻微横摇": ["固定", "横摇"],
    "固定，轻微上摇": ["固定", "上摇"],
    "固定，轻微手持呼吸感": ["固定", "手持"],
    "固定，轻微推近": ["固定", "推近"],
    "航拍跟拍（跟随纸飞机持续向前，掠过校园）": ["航拍", "跟拍", "掠过"],
    "跟移（跟随主体移动）": ["跟移", "跟随"],
}

CH = {"张书扬": "zhang", "刘思齐": "siqi", "刘思成": "sicheng",
      "徐畅景": "xu", "黄继光": "huang", "袁隆平": "yuan",
      "钟南山": "zhong", "小女孩": "girl", "妈妈": "mother",
      "小战士": "soldier", "战士": "soldier", "全场": "four"}


def parse_storyboard():
    """→ {镜号: dict(dur, scene, move, size, line, ref)}

    ⚠️ **必须 `newline=""`**：storyboard.md 是 CRLF。若用默认的通用换行模式，
    Python 会把 `\\r\\n` 一并当换行，`splitlines()` 切出的片段仍可能残留
    不可见的 `\\r`，混进台词比对串后**每一句都匹配失败**
    （曾因此假报 107 镜「台词漂移」，实际全片零漂移）。
    """
    sb = {}
    raw = open(SB, encoding="utf-8", newline="").read()
    for L in raw.split("\n"):
        L = L.rstrip("\r")
        if not L.startswith("| "):
            continue
        c = [x.strip() for x in L.strip().strip("|").split("|")]
        if len(c) < 7:
            continue
        if not (re.fullmatch(r"\d+", c[0]) and re.fullmatch(r"\d+s", c[1])):
            continue
        n = int(c[0])
        sb[n] = dict(dur=int(c[1][:-1]), scene=c[2], move=c[3],
                     size=c[4], line=c[5], ref=c[6])
    return sb


def parse_tasks():
    """→ {镜号: dict(slug,dur,seed,prompt,refs,script)}"""
    sys.path.insert(0, OUT)
    tasks = {}
    for fn in SCRIPTS:
        p = os.path.join(OUT, fn)
        spec = importlib.util.spec_from_file_location(fn[:-3], p)
        m = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(m)
        except SystemExit:
            pass
        except Exception as e:
            print("  [X] %s 载入失败：%s" % (fn, e))
            continue
        T = getattr(m, "TASKS", {})
        strip = getattr(m, "strip_late_audio", None)
        for n, t in T.items():
            prompt = t.get("prompt", "")
            if strip:
                prompt = strip(prompt)      # ★ 校验「真 prompt」
            tasks[n] = dict(slug=t.get("slug", ""), dur=t.get("dur"),
                            seed=t.get("seed"), prompt=prompt,
                            refs=[t.get("ref1"), t.get("ref2")],
                            script=fn)
    return tasks


def h3_quantize(sec):
    """storyboard 秒数 → H3 实际播放秒数。

    H3 侧规则：`frames = 17k + 5`（24fps）。
    实测对照表（storyboard §时长怎么定的）：
        2s→2.33 / 3s→3.04 / 4s→4.46 / 5s→5.17 / 6s→6.58 /
        7s→7.29 / 8s→8.00 / 9s→9.42 / 10s→10.13
    ⚠️ 必须用 **ceil**（向上取整到满足时长的最小合法帧数）。
    曾错用 `round((sec*24-5)/17)`：4s 会算成 3.75s、6s 算成 5.88s、
    9s 算成 8.71s ⇒ **假报 60 镜「时长漂移」**，实际全片零漂移。
    """
    f = math.ceil(sec * 24)
    k = math.ceil((f - 5) / 17.0)
    return round((17 * k + 5) / 24.0, 2)


def net_lines(text):
    """从 storyboard 台词列抽「净台词」（去说话人前缀 / 音效 / 音乐 / 歌词）。

    ⚠️ CRLF 防护：先把 `\\r` `\\n` 清掉再切句，否则残留的不可见 `\\r`
    会让「台词是否存在」的判定全数失败。
    """
    t = text.replace("\r", "").replace("\n", "")
    t = re.sub(r"(音效|音乐|歌词)\s*：[^；。]*[；。]?", "", t)
    out = []
    for part in re.split(r"(?<=[。！？])", t):
        part = part.strip()
        if not part:
            continue
        part = re.sub(r"^(?:[^\s：:]{1,8})\s*[：:]", "", part).strip()
        part = part.strip("；;。. ")
        if part:
            out.append(part)
    return out


def _digits_to_cn(s):
    """把阿拉伯数字转成中文数字（逐位），用于台词比对。

    ★ 2026-09-19 修假漂移：`storyboard.md` 里写的是中文数字（`四人`、`两株`、
      `一株`），而脚本 prompt 里有时写阿拉伯数字（`4 人`）⇒ 朴素的子串比对
      会把**意思完全一致**的两句判成「台词漂移」。
      实测受影响的镜：28 / 48 / 76 / 90（把 4/2/1 换成中文即一致）。
    ⚠️ 只做**逐位映射**（`74` → `七四`），不做数值读法（`七十四`）——
      因为剧本里中文数字的用法是「七十四个」这种**序数/量词**混写，
      逐位映射已足够覆盖实测的漂移案例，且不会引入新的误判。
    """
    d2c = str.maketrans("0123456789", "零一二三四五六七八九")
    return s.translate(d2c)


def evaluate(n, s, t):
    """→ list of (level, field, msg)；level ∈ {D 漂移, W 存疑}"""
    R = []
    if t is None:
        return [("D", "任务", "脚本 TASKS 里没有这一镜")]
    exp = h3_quantize(s["dur"])
    got = h3_quantize(t["dur"])
    if abs(exp - got) > 0.02:
        R.append(("D", "时长", "storyboard %ds(→%.2fs) vs 脚本 %ss(→%.2fs)"
                  % (s["dur"], exp, t["dur"], got)))

    P = t["prompt"]
    # ── B. 景别 ──
    # ★ 2026-09-17 修 false positive：`中近景` 里**包含** `近景`，
    #   朴素的 `z in P` 会把「中近景镜头」同时算成 `中近景` + `近景`，
    #   于是每一条中近景镜都误报「同镜应只一个主景别」（镜 6/8/12 等）。
    #   ⇒ 改成**最长匹配优先**：命中 `中近景` 就把它占用的字符涂掉，
    #     再在剩余文本里找别的景别词。这样 `中近景` 不再派生 `近景`，
    #     而「中近景…近景」这种**真的写了两个景别**的情况仍能被抓到。
    want = s["size"]
    masked = P
    found = []
    for z in sorted(ALL_SIZES, key=len, reverse=True):     # 长的先来
        if z in masked:
            found.append(z)
            masked = masked.replace(z, "\u3000" * len(z))  # 涂掉，避免子串再命中
    if want in found:
        others = [z for z in found if z != want]
        if others:
            R.append(("W", "景别", "主景别「%s」在，但 prompt 另有 %s（同镜应只一个主景别）"
                      % (want, "/".join(others))))
    else:
        R.append(("D", "景别", "storyboard「%s」未出现在 prompt（prompt 实为：%s）"
                  % (want, "/".join(found) if found else "未写景别")))

    # ── C. 运镜 ──
    for k in re.split(r"[，,、/（(]", s["move"]):
        k = k.strip().strip("）)")
        if not k:
            continue
        syn = MOVE_SYN.get(k, [k])
        if not any(x in P for x in syn):
            R.append(("W", "运镜", "storyboard「%s」在 prompt 找不到（试过：%s）"
                      % (k, "/".join(syn))))

    # ── D. 台词 ──
    # ⚠️ 真 prompt 结构（strip_late_audio 之后）：
    #     第 1 行 = 画面段（…；★ 禁令；LIGHT。运镜。）
    #     第 2 行起 = 台词行（**不带** `Audio:` 前缀，因为 strip 把带「（后期）」
    #                的音效句整句删掉后，`Audio:` 前缀也随之消失）
    #   因此**不能用 `split("Audio:")` 取音频段** —— 那样会取到空串、
    #   导致「每一句台词都判不存在」（曾因此假报 107 镜漂移）。
    #   正解：把**画面段之后的所有行**都当作音频/台词区。
    lines_p = P.split("\n")
    audio = "\n".join(lines_p[1:]) if len(lines_p) > 1 else P
    a_core = re.sub(r"[，。！？、…—\s\"“”‘’']", "", audio)
    # ★ 2026-09-19：数字归一化后再比（阿拉伯 ↔ 中文），修 28/48/76/90 的假漂移
    a_core_n = _digits_to_cn(a_core)
    for ln in net_lines(s["line"]):
        if not ln:
            continue
        core = re.sub(r"[，。！？、…—\s\"“”‘’']", "", ln)
        if not core:
            continue
        if core in a_core or _digits_to_cn(core) in a_core_n:
            continue
        R.append(("D", "台词", "storyboard「%s」不在台词区" % ln))

    # ── F. 画面文字风险 ──
    if "**" in P:
        R.append(("D", "文字风险", "prompt 含 Markdown `**`（会被 H3 当字写）"))
    if "（后期）" in P:
        R.append(("W", "文字风险", "prompt 含「（后期）」（strip 后仍残留）"))

    # ── G. 假漂移识别（2026-09-19 新增）──
    #   以下三类镜**画面本来就该有文字**，`_scan_text_rows.py` 必然命中，
    #   不能当作「字幕泄漏」处置（README §6.10.2 两类假漂移）：
    #     ① 白屏日记字镜（46/74/105）：白底黑字卡片 —— 字是**内容**不是泄漏
    #     ② 黑屏字幕镜：黑底白字
    #     ③ 校名牌镜（镜 1）：参考图里本来就有校名（§6.9b）
    #   ⇒ 标记出来，供人工复核时跳过；**不产生 D 级告警**。
    P_blank = re.sub(r"[\s，。；：、（）()【】★]", "", s["scene"] + s["ref"])
    if ("白屏" in P_blank) or ("黑屏" in P_blank) or ("字幕" in P_blank):
        R.append(("I", "假漂移", "白屏/黑屏字幕镜：画面文字是内容，非泄漏"))
    if ("校名" in P_blank) or ("校牌" in P_blank):
        R.append(("I", "假漂移", "校名牌镜：参考图固有文字，见 README §6.9b"))

    # ── E. 参考图 ──
    names = " ".join(os.path.basename(r).lower() for r in t["refs"] if r)
    if names:
        has_group = any(x in names for x in ("four", "group", "_all"))
        for k in CH:
            if k in s["ref"]:
                if has_group and CH[k] in ("zhang", "siqi", "sicheng", "xu"):
                    continue
                if CH[k] not in names:
                    R.append(("W", "参考图", "storyboard 要求「%s」，refs 未见（%s）"
                              % (k, names[:60])))
    return R


LEVEL_MARK = {"D": "🔴漂移", "W": "⚠️存疑", "I": "ℹ️已知假漂移"}


def main():
    args = sys.argv[1:]
    only = None
    only_drift = "--only-drift" in args
    dbg = "--debug" in args
    for a in args:
        if a.startswith("--shots="):
            only = [int(x) for x in a.split("=", 1)[1].split(",") if x.strip()]

    sb = parse_storyboard()
    tk = parse_tasks()
    if dbg:
        s = sb[1]
        p1 = tk[1]["prompt"]
        audio = p1.split("Audio:")[-1] if "Audio:" in p1 else ""
        a_core = re.sub(r"[，。！？、…—\s\"“”‘’']", "", audio)
        print("DBG storyboard.line = %r" % s["line"])
        print("DBG net_lines = %r" % net_lines(s["line"]))
        print("DBG audio_tail = %r" % audio[-80:])
        print("DBG a_core = %r" % a_core[-60:])
        for ln in net_lines(s["line"]):
            core = re.sub(r"[，。！？、…—\s\"“”‘’']", "", ln)
            print("DBG core=%r in a_core? %s" % (core, core in a_core))
        return 0
    print("storyboard 解析 %d 镜；脚本 TASKS 解析 %d 镜" % (len(sb), len(tk)))
    missing = sorted(set(sb) - set(tk))
    extra = sorted(set(tk) - set(sb))
    if missing:
        print("  ⚠️ 脚本缺镜：%s" % missing)
    if extra:
        print("  ⚠️ 脚本多镜：%s" % extra)

    keys = only if only else sorted(sb)
    rep, cnt = [], {"D": 0, "W": 0, "clean": 0, "I": 0}
    for n in keys:
        R = evaluate(n, sb[n], tk.get(n))
        # ★ I 级 = 已知假漂移（白屏/黑屏字幕镜、校名牌镜）：**不影响结论分档**，
        #   但仍列出供阅读者知道"这镜命中扫描器是预期的"。
        if any(x[0] == "D" for x in R):
            cnt["D"] += 1
        elif any(x[0] == "W" for x in R):
            cnt["W"] += 1
        else:
            cnt["clean"] += 1
        if any(x[0] == "I" for x in R):
            cnt["I"] += 1
        if R and (not only_drift or any(x[0] == "D" for x in R)):
            rep.append((n, R))

    L = ["# ★ 全片分镜一致性审核（storyboard.md ↔ 生产脚本 TASKS）", "",
         "校验：A 时长 / B 景别 / C 运镜 / D 台词 / E 参考图 / F 画面文字风险 / G 假漂移识别", "",
         "| 结论 | 镜数 |", "|---|:--:|",
         "| ✅ 完全一致 | %d |" % cnt["clean"],
         "| ⚠️ 存疑（需人工确认） | %d |" % cnt["W"],
         "| 🔴 漂移（须修复） | %d |" % cnt["D"],
         "| ℹ️ 属于已知假漂移（不计入上三档） | %d |" % cnt["I"],
         "| **合计** | **%d** |" % len(keys), ""]
    if missing:
        L += ["**脚本缺镜：** %s" % missing, ""]
    if rep:
        L += ["## 明细", ""]
        for n, R in rep:
            L.append("### 镜 %d" % n)
            L.append("")
            L.append("- storyboard：时长 %ss ｜ 景别 %s ｜ 运镜 %s"
                     % (sb[n]["dur"], sb[n]["size"], sb[n]["move"]))
            L.append("- 台词：%s" % (sb[n]["line"][:90] or "（无）"))
            for lv, f, m in R:
                L.append("- %s **%s**：%s" % (LEVEL_MARK[lv], f, m))
            L.append("")
    else:
        L += ["## 明细", "", "**无差异。**", ""]

    dst = os.path.join(OUT, "_storyboard_audit.md")
    open(dst, "w", encoding="utf-8").write("\n".join(L))
    print("\n✅ 完全一致 %d ｜ ⚠️ 存疑 %d ｜ 🔴 漂移 %d ｜ ℹ️ 已知假漂移 %d"
          % (cnt["clean"], cnt["W"], cnt["D"], cnt["I"]))
    print("   报告：%s" % dst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
