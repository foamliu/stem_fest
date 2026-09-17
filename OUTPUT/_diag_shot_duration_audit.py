# -*- coding: utf-8 -*-
"""逐镜时长体检：把 storyboard.md 的「时长」列拿台词语速重新算一遍。

理由（2026-09-13）：
  H3 是 I2V / R2V —— 给了 duration 就**必然**生成那么多帧。台词只有 1-2 秒时，
  模型只能用"重复动作 / 无意义微动 / 口型空转 / 镜头漂移"填满剩余时间，
  于是出现"人在发呆、嘴在动没声、身体像被水推着漂" ⇒ **镜估越长，浪费越大、质量越差**。

本脚本只做**诊断**，不改 storyboard。

语速标定（对白，含气口）：
  4.5 字/秒 —— 常规叙事节奏（默认）
  快（张书扬）5.5 / 慢（徐畅景、钟南山、袁隆平）4.0 —— 通过 --profile 切换，
  本脚本统一用 4.5 做**保守**估计（宁可略长，避免 H3 把台词念不完而截断）。

每镜所需时长 = 净台词字数 / 语速 + 起势收势余量(0.8s)；
纯反应镜 / 空镜按内容给 2-3s。

帧数换算（取自 workflows/video_minimax_h3_r2v.json 节点 131）：
  frames = max(5, round(a*24)) + (5 - (max(5, round(a*24)) % 17)) % 17
  ⇒ 2s→56f(2.33s) 3s→73f(3.04s) 4s→107f(4.46s)
     5s→124f(5.17s) 6s→158f(6.58s) 7s→175f(7.29s) 8s→192f(8.00s)

用法： python OUTPUT/_diag_shot_duration_audit.py
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SB = os.path.join(ROOT, "storyboard.md")
OUT = os.path.join(ROOT, "OUTPUT", "_shot_duration_audit.txt")

CPS = 4.5          # 字/秒，对白保守语速
LEAD = 0.8         # 起势 + 收势 + 气口
TOL = 0.999        # 浮点容差

# ★ 偏长判定阈值（2026-09-13 二次修正）
#   旧值 1.5s 是**单一绝对阈值**，导致「擦线镜」漏网：
#   镜 12 净字 11 / 张书扬 5.5 字/秒 + 0.8 起势 + 0.8 动作 = need 3.60s，
#   现 5s ⇒ 浪费 1.40s —— 差 0.1s 没触发告警，但 5s→4s 这档压缩是**真实可兑现的**
#   （snap() 吸附整数秒后正好落到 4s，实际播放 5.17s→4.46s，省 0.71s）。
#   现改为**双判据取更严者**：waste >= OVER_ABS **或** waste/secs >= OVER_RATIO。
#   理由是 H3 的多余时长不是「免费留白」：台词念完后它会用口型空转 / 镜头漂移填满，
#   浪费 1.0s 以上即已可感知，且短镜（3s）浪费 1.0s 占比 33%，比长镜更伤。
OVER_ABS = 1.0     # 绝对浪费阈值（秒）：waste >= 1.0s ⇒ 偏长
OVER_RATIO = 0.05  # 相对浪费阈值：waste / secs >= 5% ⇒ 偏长
# ⚠️ 相对判据**只用于 4s 及以上的镜**：2~3s 的短镜本身只有一两个字的余量，
#   套 5% 会把「打赢了」这类 3 字镜头也判偏长并压到 2s，念不完且失去气口。
OVER_RATIO_MIN = 4  # 适用相对判据的最短镜长（秒）

# 屏幕文字（白屏日记字）按"阅读"算，不按"念"算
READ_CPS = 8.0


def frames_of(sec):
    """复刻工作流节点 131 的量化公式。"""
    n = max(5, round(sec * 24))
    return n + (5 - (n % 17)) % 17


def played(sec):
    """量化后实际播放时长（秒）。"""
    return frames_of(sec) / 24.0


# ★ 修正（2026-09-13）：念出来的**只有台词本身**，`说话人：` 前缀不算字数。
#   例：「刘思成：Ouch！」净字 = 1，不是 4；多人对话行有多个「名字：」前缀，全部剔除。
SPEAKER = re.compile(
    r"(?:小女孩|妈妈|张书扬|徐畅景|刘思齐|刘思成|黄继光|袁隆平|钟南山|小战士|战士|四人|旁白)[：:]\s*")


def spoken_units(text):
    """净台词字数：剔除音效/音乐/歌词提示；CJK 逐字，数字串逐位，拉丁词算 1。

    ★ 修正（2026-09-13）：旧实现「找到 `音效：` 就截断整行」，
      于是 `音效：风声突然清晰。黄继光：……未来？` 把**真台词**（2 字）一起切掉 ⇒ 净字 0，
      镜 29 因此被误判成空镜。现改为**只剥离该提示从句**（切到句末标点为止），后面的对白保留。
    """
    t = text
    t = re.sub(r"(?:音效|音乐|歌词)[：:]\s*[^。；\n]*(?:。|；)?", "", t)
    t = re.sub(r"~~", "", t)
    t = re.sub(r"[（(][^）)]*[）)]", "", t)      # 括注（音效提示等）
    t = SPEAKER.sub("", t)                       # ★ 剔除「说话人：」前缀
    n = 0
    n += len(re.findall(r"[\u4e00-\u9fff]", t))          # CJK
    n += sum(len(m) for m in re.findall(r"\d+", t))      # 数字逐位
    n += len(re.findall(r"[A-Za-z]+", t))                # 拉丁词算 1
    return n, t


# 角色语速（字/秒）—— 分镜「角色性格与定位」表：张书扬语速快；徐畅景/袁隆平/钟南山说话慢
SPEED = {
    "张书扬": 5.5,
    "徐畅景": 4.0, "袁隆平": 4.0, "钟南山": 4.0,
    "刘思齐": 4.2, "刘思成": 4.5, "黄继光": 4.3,
    "小战士": 4.5, "小女孩": 4.5, "妈妈": 4.5,
}
CPS_DEFAULT = 4.5
# 换人说话要留气口：每个额外说话人 +0.5s
SPEAKER_GAP = 0.5
# 「……」/「——」是明写的停顿
PAUSE = re.compile(r"……|——|…")


def rate_and_gaps(raw):
    """从原始台词列读出：语速（取最慢的说话人）、额外说话人数、是否有明写停顿。"""
    names = re.findall(
        r"(小女孩|妈妈|张书扬|徐畅景|刘思齐|刘思成|黄继光|袁隆平|钟南山|小战士|战士|四人|旁白)[：:]", raw)
    cps = min([SPEED.get(x, CPS_DEFAULT) for x in names] or [CPS_DEFAULT])
    return cps, max(0, len(names) - 1), bool(PAUSE.search(raw))


def parse():
    """表头驱动解析：从「| 镜号 | 时长 | 画面 | 运镜 | 台词/音效 | 参考图提示 |」按列名取，
    以后再加列也不会把索引写死。"""
    rows, act, cols = [], "", None
    with io.open(SB, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            m = re.match(r"^##\s+(.+)$", line)
            if m:
                act = m.group(1).strip()
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if cells and cells[0] == "镜号":
                cols = {name: i for i, name in enumerate(cells)}
                continue
            if not cols:
                continue
            try:
                i_no, i_dur = cols["镜号"], cols["时长"]
                i_pic, i_lin = cols["画面"], cols["台词/音效"]
                i_ref = cols["参考图提示"]
            except KeyError:
                continue
            if max(i_no, i_dur, i_pic, i_lin, i_ref) >= len(cells):
                continue
            if not re.fullmatch(r"\d+", cells[i_no]):
                continue
            if not re.fullmatch(r"(\d+)s", cells[i_dur]):
                continue
            rows.append(dict(no=int(cells[i_no]), act=act,
                             secs=int(cells[i_dur][:-1]),
                             pic=cells[i_pic], line=cells[i_lin], ref=cells[i_ref],
                             void=("~~" in line)))
    return rows


SCREEN = re.compile(r"白屏|日记字")
FIXED = re.compile(r"定格|静帧|淡出|淡入|循环|收束|黑屏|字幕|三帧|画面泛白|白屏")
# 画面里需要真实的物理动作，光念台词撑不住 —— 每个动作给 0.4s，上限 1.6s
ACTION = re.compile(r"转身|走了几步|挥手|站起|起身|坐下|递|放在|按|打开|敲下|敲|拉了|碰|拨|拔|蹲|弯腰"
                    r"|直起|抬|擦|捂|摸|摘|摊开|消失在|消失|拉开|戴好|收拢|收拾|合上|站到|往前一步"
                    r"|凑过来|凑近|侧头|摇头|点头|环顾|望向|盯|看文件"
                    r"|甩|扔|抛|举|晃|指|滑|接|拿|捏|夹住|抱|牵|握|飞入|掠过|哈|划过|弹出|亮起|浮现|轻点")


def action_allow(pic, line):
    n = len(ACTION.findall(pic or "")) + len(ACTION.findall(line or ""))
    return min(1.6, 0.4 * n)


def snap(secs):
    """把建议时长吸附到最近的整数秒，并夹在 2–10s（10s 用于长台词长镜头）。"""
    return max(2, min(MAXSEC, int(round(secs))))


def is_over(secs, need):
    """偏长判定：双判据取更严者。

    ① 绝对：`waste >= OVER_ABS`（1.0s）——任何长度都适用；
    ② 相对：`waste / secs >= OVER_RATIO`（5%）——**仅 4s 及以上**，
       避免把 2~3s 短镜的一点点余量也判成偏长（那点余量是气口，不是浪费）。
    """
    waste = secs - need
    if secs <= 0 or waste <= 0:
        return False
    if waste >= OVER_ABS:
        return True
    return secs >= OVER_RATIO_MIN and (waste / secs) >= OVER_RATIO


# 单镜时长上限（秒）：8s 是常用上限，长台词镜可放宽到 10s
MAXSEC = 10


# 人工覆盖登记表：机器按语速算出来的数**故意不用**的镜，写清理由。
# 判据仍是"每镜只做一件事"——留白/情绪高点属于创作者的决定，不是估时错误。
HOLDS = {
    4:   "航拍跟拍，画面持续剧变（README §4.2 steps=20 那一条），5s 是实测要求",
    10:  "★ 序幕二**幕首建立镜**（傍晚教室 + 全息设备 + 四人），机器按台词算 3s 太急，人工给 4s",
    16:  "纯反应拍子（被噎住），2s",
    18:  "幕末转场（按下启动键 + 白光吞没教室），机器 3s 不够铺白光，人工给 4s",
    39:  "★ 第一幕情绪高点（小战士拉手约定），8s 是刻意留白",
    45:  "英雄告别 + 口琴起的情绪高点，机器 4s 不够，人工给 5s",
    47:  "★ 第二幕**幕首建立镜**（田埂 + 蝉鸣稻浪），机器按台词算 3s 太急，人工给 4s",
    60:  "★ 袁隆平讲「见过饿倒的人」，22 字长台词的情绪镜，8s 是刻意留白",
    75:  "★ 第三幕**幕首建立镜**（餐车 + 钟南山闭眼 + 桌板文件，缓推到手部），人工给 5s",
    81:  "钟南山睁眼看见四人 —— 幕中转场静默拍，4s 留白",
    97:  "钟南山讲 400 米栏纪录，9s 长台词镜",
    99:  "钟南山「学医可以一辈子治病救人」——全片最长台词（31 字）10s",
    102: "武汉站到 + 收拾文件 + 递口罩给刘思齐，三拍动作，机器算 4s 不够",
    104: "起身 + 走向车门 + 背影消失在夜色，三拍动作且为情绪落点，人工给 5s",
    106: "★ 尾声**幕首建立镜**（回教室 + 天色已暗 + 双手托全息稻谷口罩），人工给 5s",
    109: "打开电脑 + 照片弹出 + 手停在键盘（含一顿），三拍动作 + 悬念点，人工给 6s",
    116: "★ 全片主题句之一（26 字），画面明写「摊开双手」，8s 是刻意留白",
    118: "全片主题句，画面明写「停顿一下，轻声」⇒ 机器 4s 会赶，6s",
    120: "张书扬「嘴角微扬 → 敲下第一个键」是转题点，情绪+动作两拍，人工给 5s",
    121: "★ 全片收束镜：四人围电脑 + 全息稻谷口罩悬浮，4s 留白",
    122: "屏幕亮起「如愿·看见」标题 —— 片名揭晓，6s 留白",
    123: "三行字幕逐行浮现，6s 是刻意留白",
    124: "字幕淡出 + 王菲声音进入，6s 是刻意留白",
    125: "三帧静帧依次闪过，8s 是刻意留白",
    126: "最后定格 + 歌曲副歌收束，8s 是刻意留白",
    # ── 无台词镜的「多步动作链」，公式 `2.5 + 0.4×动作数` 会低估 ──
    5:   "多步动作：纸飞机飞入窗 + 张书扬两指捏住；且是序幕一收束镜，机器算 3s 太急",
    19:  "横摇扫过整条坑道（战士整理弹药 + 挖野菜），画面内容量非单动作可比",
    23:  "分野菜 + 把好菜叶拨给小战士，两个独立动作",
    111: "「三人围过来，没人说话」——画面明写「没人说话」＝静默节拍，按公式 2s 会失去留白，人工给 3s",
    113: "「没有台词，镜头停住」——静默节拍，机器算 2s 会失去留白",
    # ── 公式建议压，但画面是「信息识别点」，压了会看不清 ──
    79:  "刘思成「看清文件上的字」是信息点（观众要读到『新型冠状病毒』），需看清时间",
    # ★ 2026-09-17 删除 HOLDS[15] 的旧依据（「刘思齐一针见血 +『哈哈』冷笑」），
    #   因为台词已按 storyboard 第 153 行改回单句「你输在轻敌。」（不再有第二句/冷笑）。
    #   但**保留人工锁定 3s**，换一个成立的理由：短句说完后的「冷场」本身是戏 ——
    #   机器按纯字数算 2s，会把刘思齐一针见血之后那个「所有人都不接话」的停顿剪掉。
    15:  "刘思齐一针见血「你输在轻敌。」（6 字）—— 机器按字数算 2s，会把说完后那个'没人接话'的冷场剪掉；3s 是刻意留白",
    # ★ 2026-09-17 新增 HOLDS[14]（**已知取舍，不是估时错误**）：
    #   机器按 17 字 ÷ 张书扬 5.5 字/秒 + 0.8s = **3.89s**，判 3s ⛔偏短 0.85s。
    #   但用户明确要求「压到 3s」（原抱怨：「给 4 秒时间过多，导致前边合成多余语音」）——
    #   根因是 H3 在**起势前的空档**里自己编语音，压时长是直接对症的手段。
    #   ⇒ 人工锁定 3s，用张书扬「语速快、爱抢话」的角色定位兜住这 0.85s。
    #   ⚠️ 验收要点：重跑后**必须 ASR 回读**，确认 17 字一字不漏、没有被吞字。
    #     若吞字 ⇒ 回调 4s 并改 seed 重跑（此时 rely on ONLY_THIS_LINE 压杂音）。
    14:  "张书扬 17 字长台词压到 3s（用户要求；机器算 3.89s 会判偏短 0.85s）—— 靠'语速快'的角色定位兜住，**验收必须 ASR 逐字核对**",
    17:  "刘思成「模型只能看，不能改历史」是全片核心规则句，需说清",
    32:  "徐畅景「大家都能吃饱。每个孩子都能上学。」两句重台词，机器算 4s 刚好，那是删「不用再打仗了」后的最终位",
    43:  "黄继光「你们该回去了」是告别起句，机器 4s 会赶",
    77:  "徐畅景「他在高铁上……看文件」含省略号停顿，机器 3s 会赶",
    # ── **沉默/静默本身就是内容**，不能按纯字数压 ──
    27:  "「黄继光沉默，看着他们的眼睛；然后平静地开口」——沉默段是戏；台词只 2 字但明写 `……` 停顿，按字数算 2s 会丢掉沉默",
}


def main():
    rows = parse()
    out = []
    w = out.append
    w("# 逐镜时长体检（storyboard.md）")
    w("")
    w("语速 **%.1f 字/秒** + 起势收势 %.1fs + 动作余量（按画面动词，上限 1.6s）。"
      % (CPS, LEAD))
    w("判定：`waste = 现时长 - 需要`；**双判据取更严者** ⇒ "
      "`waste ≥ %.1fs` **或** `waste / 现时长 ≥ %.0f%%` 判 ⚠️偏长；需要 - 现时长 > 0.5s ⇒ ⛔偏短。"
      % (OVER_ABS, OVER_RATIO * 100))
    w("「定格/静帧/黑屏/屏字/转场」为刻意留白，不判偏长。")
    w("")
    w("| 镜号 | 幕 | 现时长 | 实际播放 | 净台词字 | 需要 | 判定 | 建议 | 台词节选 |")
    w("|:--:|---|:--:|:--:|:--:|:--:|:--:|:--:|---|")

    tot_nom = tot_real = 0.0
    tot_new = 0.0
    over, under, ok = [], [], []
    for r in rows:
        no, secs, lt = r["no"], r["secs"], r["line"]
        if r["void"]:
            w("| %d | %s | %ds | — | — | — | ⛔已作废 | — | — |" % (no, r["act"][:6], secs))
            continue
        units, clean = spoken_units(lt)
        act = action_allow(r["pic"], lt)
        cps, extra_spk, has_pause = rate_and_gaps(lt)
        tot_nom += secs
        tot_real += played(secs)

        if FIXED.search(lt) or FIXED.search(r["pic"]):
            need, tag, verdict = float(secs), "✅ 留白", "留白"
        elif units == 0:
            need = min(6.0, 2.5 + act)
            verdict = "空/反应"
            # ★ 修正（2026-09-13）：无台词镜此前恒判 ✅，浪费从不进 over 列表
            #   ⇒ 镜 52「袁隆平弯腰看稻穗，汗滴进泥里」6s 只需 3.3s 却报 ✅。
            #   空镜没有台词可"念不完"，但它同样会被 H3 用漂移/空转填满，照样要压。
            waste = secs - need
            if is_over(secs, need) and no not in HOLDS:
                tag = "⚠️偏长"
            else:
                tag = "✅"
        elif units == 0 or SCREEN.search(lt):
            need = units / READ_CPS + 1.5 + act
            verdict = "屏字"
            tag = "✅"
        else:
            need = (units / cps + LEAD + act
                    + SPEAKER_GAP * extra_spk + (0.4 if has_pause else 0.0))
            verdict = "对白"
            waste = secs - need
            if no in HOLDS:
                tag = "🔒 人工锁定"
            elif is_over(secs, need):
                tag = "⚠️偏长"
            elif need - secs > 0.5:
                tag = "⛔偏短"
            else:
                tag = "✅"

        if tag == "🔒 人工锁定":
            sug = secs
            ok.append(no)
        elif tag == "⚠️偏长":
            sug = snap(need)
            # ★ 若吸附后的建议值并没真的更短（如 3s 建议 3s），这条就没有可执行意义：
            #   降级为 ✅，避免报告里出现「偏长但建议不变」的噪音条目。
            if sug >= secs:
                tag, sug = "✅", secs
                ok.append(no)
            else:
                over.append((no, secs, need, units, clean, sug))
        elif tag == "⛔偏短":
            sug = snap(need + 0.3)
            under.append((no, secs, need, units, clean, sug))
        else:
            sug = secs
            ok.append(no)
        tot_new += sug

        w("| %d | %s | %ds | %.2fs | %d | %.1fs | %s | %ss | %s |" % (
            no, r["act"][:6], secs, played(secs), units, need, tag, sug,
            clean[:24].replace("|", "/")))

    w("")
    w("## 合计")
    w("")
    w("- 名义时长（storyboard 逐镜相加，含作废行不计）：**%.0f s = %.1f 分**"
      % (tot_nom, tot_nom / 60.0))
    w("- **实际片长**（按 `frames = 17k+5` 量化后逐镜相加）：**%.0f s = %.1f 分**"
      % (tot_real, tot_real / 60.0))
    w("- 剧本各幕小标题写的是**本列「实际播放」**；片头/README 的片长也应取这个数。")
    w("- 逐镜表里的「时长」列是**名义秒数**，只作为 H3 的 `duration` 输入；")
    w("  真正的播放长度见本表「实际播放」列——两者相差 0.04–0.58 s/镜，**别拿名义值当片长**。")
    w("- 各幕小标题写的时长 vs 逐镜相加：见文末「幕级核对」")
    w("")
    w("## 幕级核对（可直接抄进各幕小标题）")
    w("")
    w("| 幕 | 名义合计 | 实际播放 | 全场占比 |")
    w("|---|:--:|:--:|:--:|")
    acts = []
    for r in rows:
        if r["void"]:
            continue
        if r["act"] not in acts:
            acts.append(r["act"])
    for k in acts:
        nom = sum(r["secs"] for r in rows if r["act"] == k and not r["void"])
        rel = sum(played(r["secs"]) for r in rows if r["act"] == k and not r["void"])
        w("| %s | %d s | **%.0f s（%.1f 分）** | %.0f%% |"
          % (k, nom, rel, rel / 60.0, rel / tot_real * 100))
    w("| **全片** | **%d s** | **%.0f s（%.1f 分）** | 100%% |"
      % (int(tot_nom), tot_real, tot_real / 60.0))
    w("")
    w("## ⚠️ 偏长 %d 镜（按语速可压掉约 %.0f s）" % (
        len(over), sum(s - n for _, s, n, _, _, _ in over)))
    w("")
    w("| 镜 | 现 → 建议 | 浪费 | 净字 | 台词 |")
    w("|:--:|:--:|:--:|:--:|---|")
    for no, secs, need, units, clean, sug in over:
        w("| %d | %ds → **%ds** | -%.1fs | %d | %s |" % (no, secs, sug, secs - need, units, clean[:32]))
    w("")
    w("## ⛔ 偏短 %d 镜（会念不完 / 被截断）" % len(under))
    w("")
    w("| 镜 | 现 → 建议 | 差额 | 净字 | 台词 |")
    w("|:--:|:--:|:--:|:--:|---|")
    for no, secs, need, units, clean, sug in under:
        w("| %d | %ds → **%ds** | +%.1fs | %d | %s |" % (no, secs, sug, need - secs, units, clean[:32]))
    w("")
    w("## 🔒 人工锁定（%d 镜，机器数故意不用）" % len(HOLDS))
    w("")
    w("| 镜 | 时长 | 理由 |")
    w("|:--:|:--:|------|")
    for no in sorted(HOLDS):
        sec = next((r["secs"] for r in rows if r["no"] == no), None)
        if sec:
            w("| %d | %ds | %s |" % (no, sec, HOLDS[no]))
    w("")
    w("## 复核结论")
    w("")
    w("- 名义合计 **%.0f s**（%.1f 分）；H3 按 `frames = 17k+5` 量化后**实际播放 %.0f s**（%.1f 分）。"
      % (tot_nom, tot_nom / 60.0, tot_real, tot_real / 60.0))
    w("- 作废/已并入他镜的行共 %d 个，**不计入合计**。"
      % sum(1 for r in rows if r["void"]))
    w("- 有效镜 %d 个（2026-09-13 删掉旧镜 18/19「Ouch 梗」后，由 131 重排为 129）。"
      % sum(1 for r in rows if not r["void"]))

    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    sys.stdout.write("written: %s\n" % OUT)
    sys.stdout.write("nominal=%.0fs real=%.0fs over=%d under=%d ok=%d\n" % (
        tot_nom, tot_real, len(over), len(under), len(ok)))


if __name__ == "__main__":
    main()
