# -*- coding: utf-8 -*-
"""把 `storyboard.md` 的 126 镜排成「四格漫画」页（每格一镜 + 台词气泡），A4 可打印。

★ 设计要点
  1. **内容唯一出处 = `storyboard.md`**（README 铁律：每个事实只写一处）。
     本脚本**逐镜表解析**镜号/时长/画面/运镜/景别/台词音效，
     **不复制、不硬编码任何台词** —— 改台词后重跑本脚本即自动同步。
     三类屏幕文字（镜 117 字幕 / 镜 122 片名 / 镜 46·74·105 日记字）
     也从「画面」列与「黑屏字幕内容」节**正则提取**，并在解析报告里回显核对。
  2. **画面来源 = 已验收的镜头产物**，不重新生成图像。
     取用口径**与 `_concat_video.py` 一致**（同 `RANGES` 幕区间 + 同 `_bak_`/`_rejected` 排除
     + 同幕内取 mtime 最新）⇒ **漫画里的每一格就是成片里那一镜**，不会串片。
     帧 = `ffprobe 时长 × --at`（默认 0.5，即镜中），抽一次缓存到 `OUTPUT/comic/frames/`。
  3. **排版 = 每页 4 格（2×2）**，一镜一格，顺序与成片一致（1→126）。
     · `--paper=a4l`（默认，横版）：1056×608 源帧按 16:9 恰好填满格内画面区，零浪费；
     · `--paper=a4p`（竖版）：源帧两侧以**自身模糊镜像延展**补满（不裁切、不丢画面）。
     两种版式都出 —— 横版最省纸、竖版更像连环画小册子。
  4. **气泡**：`说话人：台词` → 白底圆角气泡 + 指向说话方向的尖角；
     `音效/音乐/歌词` → 格内底部小字条（不占气泡）；
     `日记字/屏幕字幕/黑屏字幕` → 米色方框（旁白框），与气泡区分。
     ⚠️ 台词过长时**自动降字号**（`--bubble-min` 下限）并在清单里报 `overflow`，
     宁可字小也不裁字。
  5. **300 dpi 打印母版**：A4 横 3508×2480 / 竖 2480×3508。
     帧从 1056 宽放大到 ≈1622 宽（1.54×）⇒ 放大时补一次轻度 USM 锐化（印刷下不发糊）。
  6. `--grade` 印刷调色：`soft`（默认，饱和 +8% / 对比 +5%）｜`none`（完全忠实原片）｜
     `comic`（更漫画：饱和 +25% / 对比 +12% / 轻量色阶化）。
  7. 产出（`OUTPUT/comic/`，**产物不入库**；本脚本入库）：
     `pages_a4l/page_01.png …`、`pages_a4p/…`、`ruyuan_A4_landscape.pdf`、
     `ruyuan_A4_portrait.pdf`、`_comic_manifest.md`（清单 + 解析报告）。

用法：
    py -3.10 OUTPUT/_make_comic.py --check           # 只解析 + 报告，不出图（闸门）
    py -3.10 OUTPUT/_make_comic.py                   # 出横版 + 竖版（默认）
    py -3.10 OUTPUT/_make_comic.py --paper=a4l       # 只出横版
    py -3.10 OUTPUT/_make_comic.py --paper=a4p       # 只出竖版
    py -3.10 OUTPUT/_make_comic.py --shots=1-12      # 只做前 12 镜（试排）
    py -3.10 OUTPUT/_make_comic.py --only=6,39,116   # 只做指定镜（排查排版）
    py -3.10 OUTPUT/_make_comic.py --no-cover --no-pdf
    py -3.10 OUTPUT/_make_comic.py --grade=none --at=0.6 --force-frames

参数速查：
    --paper=a4l|a4p|both  版式（默认 both）
    --dpi=300             打印分辨率（改它会同时缩放页面与字号）
    --at=0.5              抽帧位置（0~1，占镜头时长比例）
    --shots=A-B           只做该镜号区间
    --only=N,M,...        只做这些镜号
    --bubble-min=26       气泡最小字号（低于它就报 overflow）
    --with-desc           格下附「画面」描述（默认只留 镜号·幕·景别·运镜）
    --keep-acts           每幕单独起新页（默认连续排版，不浪费纸）
"""

import argparse
import glob
import io
import os
import re
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

# ★ 沿用 `_concat_video.py` 的做法：Windows 控制台默认 GBK，打印 ★/✅ 会抛 UnicodeEncodeError
for _s in ("stdout", "stderr"):
    try:
        getattr(sys, _s).reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SB_MD = os.path.join(ROOT, "storyboard.md")
OUT = os.path.join(ROOT, "OUTPUT", "comic")
FRAMES = os.path.join(OUT, "frames")
# ★ 清单（.md）放 **OUTPUT/ 顶层**：`OUTPUT/*` 被 gitignore、只回收顶层 `*.py` / `*.md`，
#   放 `comic/` 里就入库不了 —— 与 `_audio_report.md` / `_film_sfx_report.md` 同一口径。
MANIFEST = os.path.join(ROOT, "OUTPUT", "_comic_manifest.md")
# ★ 幕后篇（单页四格）的**唯一出处**：页标题 / 4 格的图·标签·台词都在这里，
#   脚本只负责解析与排版（口径同 storyboard：内容与代码分离）。
SHEET_MD = os.path.join(ROOT, "OUTPUT", "_comic_making.md")

# ★ 镜号区间 → 幕目录的**权威映射**：与 `_concat_video.py` 的 `RANGES` 必须一致。
#   跨幕重号（106-126 vs 1-9）靠它消歧，见 `_concat_video.py` 的同名注释。
RANGES = {
    "01_paper_plane":    (1, 9),
    "03_classroom_day":  (10, 18),
    "06_trench":         (19, 46),
    "07_rice_field":     (47, 74),
    "08_train_dining":   (75, 105),
    "05_classroom_night": (106, 126),
}
ACT_OF = {}   # 镜号 → 幕目录，见 build_act_map()

# ─────────────────────────────── ① 解析 storyboard.md ───────────────────────────────

# 说话人（★ 与逐镜表 `台词/音效` 列里的写法一致；长名在前，避免 `战士` 抢走 `年轻战士`）
SPEAKERS = ["年轻战士", "志愿军战士", "张书扬", "徐畅景", "刘思齐", "刘思成",
            "黄继光", "袁隆平", "钟南山", "小女孩", "妈妈", "战士"]
# 非台词的「音轨标注」→ 格内小字条
AV_TAGS = {"音效": "sfx", "音乐": "music", "歌词": "lyrics"}

_SPLIT_RE = re.compile(
    r"(音效|音乐|歌词|" + "|".join(sorted(SPEAKERS, key=len, reverse=True)) + r")\s*[：:]")


def _clean(t):
    """去掉制作标注与强调标记 —— 漫画上只要「读得出来的那句话」。"""
    if not t:
        return ""
    t = t.replace("**", "")
    t = re.sub(r"[（(]\s*后期\s*[)）]", "", t)      # 「（后期）」是音效铺位标注，不是台词
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _rstrip_punct(t):
    return re.sub(r"[。．.，,、；;！!？?…\s]+$", "", t or "")


def parse_storyboard(path):
    """把 `storyboard.md` 解析成 {shot_no: {...}} + 主题句 / 幕结构 / 黑屏字幕 / 版权标注。

    ★ 只认**逐镜表**的行：`| 镜号 | 时长 | 画面 | 运镜 | 景别 | 台词音效 | 参考图提示 |`
      （恰好 7 列、第 1 列纯数字、第 2 列 `<数字>s`）—— 其它对照表不会被误收。
    """
    lines = open(path, encoding="utf-8").read().splitlines()

    shots, acts, theme, cards, credits = {}, [], None, [], []
    last_card_open = False
    for ln in lines:
        s = ln.strip()
        if s.startswith("|") and s.endswith("|"):
            parts = [c.strip() for c in s.strip("|").split("|")]
            # ── 逐镜表 ──
            if (len(parts) == 7 and re.fullmatch(r"\d+", parts[0])
                    and re.fullmatch(r"\d+s", parts[1])):
                n = int(parts[0])
                shots[n] = {"n": n, "dur": int(parts[1][:-1]),
                            "pic": _clean(parts[2]), "cam": _clean(parts[3]),
                            "size": _clean(parts[4]), "av": parts[5],
                            "ref": _clean(parts[6])}
                continue
            # ── 幕结构表（`| 序幕一：纸飞机 | 1–9 | 9 | 35 s |`）──
            if (len(parts) == 4 and re.fullmatch(r"\d+\s*[–\-]\s*\d+", parts[1])
                    and re.fullmatch(r"\d+", parts[2])):
                lo, hi = [int(x) for x in re.split(r"[–\-]", parts[1])]
                acts.append({"name": _clean(parts[0]), "lo": lo, "hi": hi,
                             "count": int(parts[2]), "dur": parts[3]})
                continue
            if len(parts) == 2 and "主题" in parts[0]:
                theme = _clean(parts[1])
            continue
        # ── 黑屏字幕内容节 ──
        m = re.match(r"^\*\*(第一行|第二行|第三行)[：:]\*\*\s*(.+)$", s)
        if m:
            cards.append(_clean(m.group(2)))
            continue
        if re.match(r"^\*\*最后一行[^*]*\*\*\s*$", s):
            last_card_open = True
            continue
        if last_card_open:
            if not s:
                continue                      # ★ 空行不关闭（原文「最后一行」下面是空行再正文）
            if s.startswith(">"):
                last_card_open = False
            else:
                cards.append(_clean(s))
        # ── 音乐版权标注（`> 序幕音乐：…` / `> 尾声歌曲：…`）──
        m = re.match(r"^>\s*(序幕音乐|尾声歌曲)[：:]\s*(.+)$", s)
        if m:
            credits.append("%s：%s" % (m.group(1), _clean(m.group(2))))

    if len(shots) != 126:
        raise SystemExit("!! 逐镜表解析异常：拿到 %d 镜（应为 126）—— 先查 storyboard.md 表格式"
                         % len(shots))
    miss = [n for n in range(1, 127) if n not in shots]
    if miss:
        raise SystemExit("!! 逐镜表缺号：%s" % miss)
    return shots, acts, theme, cards, credits


def parse_av(shot, cards):
    """把 `台词/音效` 列拆成 气泡 / 音效条 / 旁白框。

    ★ 三类文字的判据（都能在 storyboard 里找到原样出处，不做人工改写）：
      · `说话人：台词`      → 气泡（一句里可以换人，如镜 39「…。黄继光：说好了。」）
      · `音效/音乐/歌词：…` → 格内底部小字条（不占气泡）
      · `日记字 / 屏幕字幕 / 黑屏字幕` → 米色旁白框
    """
    raw = shot["av"]
    out = {"bubbles": [], "sfx": [], "music": [], "lyrics": [],
           "narration": None, "nlabel": None}

    for src, lab, pat in ((raw, "【日记】", r"日记字\s*[：:]\s*(.+)$"),
                          (shot["pic"], "【屏幕字幕】", r"字幕\s*[：:]\s*(.+)$"),
                          (shot["pic"], "【屏幕字幕】", r"屏幕亮起\s*[“\"](.+?)[”\"]")):
        m = re.search(pat, src)
        if m:
            out["narration"] = _clean(m.group(1)).strip("“”\"' ")
            out["nlabel"] = lab
            break
    if shot["n"] == 123 and len(cards) >= 3:                    # 三行字幕逐行浮现
        out["narration"], out["nlabel"] = "\n".join(cards[:3]), "【黑屏字幕】"
    elif shot["n"] == 124 and len(cards) >= 5:                  # 最后一行字幕
        out["narration"], out["nlabel"] = "\n".join(cards[3:5]), "【献词】"
    if out["nlabel"] == "【日记】":                              # 整格都是旁白
        raw = re.sub(r"^.*?日记字\s*[：:]", "", raw)

    parts = _SPLIT_RE.split(raw)
    pre = parts[0]
    pairs = [(parts[i], parts[i + 1]) for i in range(1, len(parts) - 1, 2)]
    if _clean(pre) and not out["narration"]:
        out["narration"], out["nlabel"] = _clean(pre), "【旁白】"
    for label, text in pairs:
        t = _clean(text)
        if not t:
            continue
        if label in AV_TAGS:
            key = AV_TAGS[label]
            out[key].append(_rstrip_punct(t) if key == "sfx" else t)
        else:
            out["bubbles"].append((label, t))
    return out



# ─────────────────────────── ② 镜头产物定位 + 抽帧 ───────────────────────────

def build_act_map(storyboard_acts):
    """镜号 → 幕目录（用 `RANGES` 的区间反查；区间外报错而不是静默就近）。"""
    for d, (lo, hi) in RANGES.items():
        for n in range(lo, hi + 1):
            ACT_OF[n] = d
    return ACT_OF


def collect_sources(upto=126):
    """收集「采用版」镜头产物 —— 口径**完全对齐** `_concat_video.py`。

    · 只扫 6 个幕目录的 `video/*.mp4`；
    · 排除 `_bak_*`、`*_delogo/temporal/split.mp4`；
    · 镜号必须落在该幕的 `RANGES` 区间内（跨幕重号的结构性保证）；
    · 同一镜号取 **mtime 最新**（= 最后一次生成的采用版）。
    """
    found = {}
    for d, (lo, hi) in RANGES.items():
        for f in glob.glob(os.path.join(ROOT, "OUTPUT", d, "video", "*.mp4")):
            base = os.path.basename(f)
            if base.startswith("_bak_") or re.search(r"_(delogo|temporal|split)\.mp4$", base):
                continue
            m = re.match(r"(\d+)_", base)
            if not m:
                continue
            n = int(m.group(1))
            if not (lo <= n <= hi) or n > upto:
                continue
            if n not in found or os.path.getmtime(f) > os.path.getmtime(found[n]):
                found[n] = f
    return found


def probe_dur(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", path],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def get_frame(shot_no, src, at, force=False):
    """抽一帧（默认镜中 50%）缓存到 `OUTPUT/comic/frames/NNN.png`。

    ★ 用 PNG 而不是 JPEG：源片已是 H3 有损产物，抽帧再上一次 JPEG 会**双重损失**，
      而这一帧后面还要放大 1.54× 印到纸上。
    """
    dst = os.path.join(FRAMES, "%03d.png" % shot_no)
    if os.path.exists(dst) and not force:
        return dst
    t = max(0.0, probe_dur(src) * at)
    os.makedirs(FRAMES, exist_ok=True)
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "%.3f" % t, "-i", src,
                        "-frames:v", "1", dst], capture_output=True, text=True)
    if not os.path.exists(dst) or os.path.getsize(dst) < 1024:
        # 兜底：有些容器 seek 到接近片尾会抽不到帧 → 回到首帧
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-frames:v", "1", dst],
                       capture_output=True, text=True)
    if not os.path.exists(dst):
        raise SystemExit("!! 抽帧失败：镜 %d ← %s\n%s" % (shot_no, src, r.stderr[-500:]))
    return dst


# ─────────────────────────── ③ 印刷调色 / 排版参数 ───────────────────────────

def grade(im, mode):
    """印刷调色。`none` 完全忠实原片；`soft` 只做轻微提升（默认）；`comic` 更漫画化。"""
    if mode == "none":
        return im
    from PIL import ImageEnhance
    if mode == "soft":
        im = ImageEnhance.Color(im).enhance(1.08)
        im = ImageEnhance.Contrast(im).enhance(1.05)
        return im
    im = ImageEnhance.Color(im).enhance(1.25)
    im = ImageEnhance.Contrast(im).enhance(1.12)
    im = ImageEnhance.Sharpness(im).enhance(1.3)
    return im.point(lambda v: min(255, max(0, int((v / 255.0) ** 0.92 * 255))))


def paper_layout(paper, dpi):
    """返回该版式的版面尺寸（含全部留白/字号），单位像素。

    ★ 横版（a4l）是**最优版式**：源帧 1056×608 = 1.737，横向 2 列时格内画面区
      1621×931 = 1.741 —— 只裁掉 0.25%，等于**原样铺满**；
      竖版（a4p）格内画面区是 1115×1439，源帧按宽铺满只有 642 高，
      ⇒ 用**自身模糊镜像**补满（不裁切、不丢画面），像一张镶在纸上的人民画报。
    """
    k = dpi / 300.0
    if paper == "a4l":
        W, H = int(3508 * k), int(2480 * k)
        base = dict(margin=int(96 * k), gap=int(46 * k), header=int(150 * k),
                    footer=int(74 * k), caption=int(64 * k), border=int(7 * k))
        base.update(paper=paper, W=W, H=H, col=2, row=2)
    else:
        W, H = int(2480 * k), int(3508 * k)
        base = dict(margin=int(90 * k), gap=int(42 * k), header=int(142 * k),
                    footer=int(70 * k), caption=int(86 * k), border=int(7 * k))
        base.update(paper=paper, W=W, H=H, col=2, row=2)
    L = base
    L["content_x0"] = L["margin"]
    L["content_x1"] = L["W"] - L["margin"]
    L["content_y0"] = L["margin"] + L["header"]
    L["content_y1"] = L["H"] - L["margin"] - L["footer"]
    L["panel_w"] = (L["content_x1"] - L["content_x0"] - L["gap"] * (L["col"] - 1)) // L["col"]
    L["panel_h"] = (L["content_y1"] - L["content_y0"] - L["gap"] * (L["row"] - 1)) // L["row"]
    L["img_w"] = L["panel_w"] - 2 * L["border"]
    L["img_h"] = L["panel_h"] - 2 * L["border"] - L["caption"]
    # 字号（基线 300 dpi）
    L["fs_title"] = int(56 * k)
    L["fs_sub"] = int(30 * k)
    L["fs_shot"] = int(40 * k)
    L["fs_cap"] = int(36 * k)
    L["fs_audio"] = int(30 * k)
    L["fs_bubble_max"] = int(56 * k)
    L["fs_bubble_min"] = int(26 * k)
    L["fs_narr"] = int(36 * k)
    L["pad"] = int(26 * k)
    L["tail"] = int(34 * k)                  # 气泡尖角长度
    L["ow"] = max(3, int(5 * k))          # 气泡描边
    return L


# ★ 成片里「有意要出现」的屏幕字（storyboard 制作约定 #7 / §6.9 白名单）：
#   镜 46/74/105 白屏日记字、镜 123/124 黑屏字幕 —— 这些**不得裁切**，
#   它们的内容已原样进「米色旁白框」，裁掉画面里的反而丢信息。
CARD_SHOTS = {46, 74, 105, 123, 124}


def detect_caption(im):
    """检测**下层字幕带**里有没有烧录字幕（H3 把 `Audio:` 台词画成字幕的已知泄漏，README §6.6）。

    ★ 为什么不是「有白像素就算」：白衣服、白稻穗、雪地都会命中，实测假阳性极高
      （2026-09-23 实测：镜 48/61 的稻田纹理 124/14 行命中，肉眼核对**根本没有字幕**）。
      真正的字幕有三条**几何**特征，必须同时满足：
        ① **细段密集**：该行白色小段（run）≥8 个、白像素占 1%~20%
            —— 文字笔画是几十个小段；白衣服/白稻穗是 1~2 个大片；
        ② **低位**：成簇的行中心落在 y ≥ 0.86H —— 字幕固定在画面底部；
        ③ **上方留白**：字幕簇顶行再往上 3 行必须近乎无白
            —— 稻田/雪地那种"满屏纹理"没有这条留白。
    返回 (是否检出, 字幕带首行 y, 字幕带末行 y)。
    """
    w, h = im.size
    y0 = int(h * 0.74)
    band = im.convert("L").crop((0, y0, w, h))
    bw, bh = band.size
    mask = band.point(lambda v: 255 if v >= 228 else 0).tobytes()
    rows = []
    for y in range(bh):
        row = mask[y * bw:(y + 1) * bw]
        nw = row.count(255)
        if nw < max(6, int(bw * 0.010)) or nw > int(bw * 0.20):
            rows.append((y, nw, 0))
            continue
        runs, i = 0, 0
        while True:
            j = row.find(b"\xff", i)
            if j < 0:
                break
            runs += 1
            i = j
            while i < bw and row[i] == 255:
                i += 1
        rows.append((y, nw, runs))
    dense = [y for (y, nw, r) in rows if r >= 8]
    if not dense:
        return False, 0, 0
    # 取最下面那一簇（字幕就在最下面），簇内断行 ≤4 行
    clusters, cur = [], [dense[0]]
    for y in dense[1:]:
        if y - cur[-1] <= 4:
            cur.append(y)
        else:
            clusters.append(cur)
            cur = [y]
    clusters.append(cur)
    top, bot = clusters[-1][0], clusters[-1][-1]
    center = y0 + (top + bot) / 2.0
    if not (12 <= len(clusters[-1]) and 18 <= (bot - top) <= 60):
        return False, 0, 0
    if center < 0.86 * h:
        return False, 0, 0
    # 上方留白：字幕上去 4 行必须近乎无白（≤2.5% 宽）—— 稻田/雪地那种满屏纹理没有这条
    above = [nw for (y, nw, r) in rows[max(0, top - 4):top]]
    if len(above) < 3 or max(above) > 0.025 * bw:
        return False, 0, 0
    return True, y0 + top, y0 + bot


def hide_film_caption(im, shot_no, meta):
    """检出烧录字幕 → 返回「该从哪一行起用黑边盖住」（源图 y），未检出返回 None。

    ★ 为什么是「盖黑边」而不是「裁掉」：
      storyboard 制作约定 #10 要求校园展示镜（镜 1/4/5）**不得删改** —— 直接裁帧会连带
      把画面左右各裁掉 ~4%（16:9 → 更扁），有切到校牌的风险；
      盖黑边只吃掉画面底部那一条（通常是裙摆/地面），**横向构图一个像素不动**，
      且与格下那条黑色信息条连成一片，看起来就是有意为之的「遮幅」。
    ★ 白名单镜（`CARD_SHOTS`：白屏日记字 / 黑屏字幕）不盖 —— 那是成片有意要出现的字。
    """
    if shot_no in CARD_SHOTS:
        return None
    ok, top, _ = detect_caption(im)
    if not ok:
        return None
    y = int(top - 6)
    if y < im.height * 0.75:
        meta["warn"].append("镜 %d：检出烧录字幕但覆盖会吃掉 >25%% 画高，未处理" % shot_no)
        return None
    meta["captions"].append(shot_no)
    return y


def art_y_of(art_geom, src_len, src_y):
    """源图 y → 格内画面区 y。

    · 横版 `ImageOps.fit` **只裁左右**（源 1.7368 vs 格 1.741）⇒ 纵向是精确线性映射；
    · 竖版是「模糊底 + 等比居中」⇒ 要加上居中偏移。
    """
    paper, iw, ih, fh = art_geom
    if paper == "a4l":
        return int(round(src_y / float(src_len) * ih))
    return int((ih - fh) // 2 + round(src_y / float(src_len) * fh))


_FONTS = {}
FONT_REG = "C:/Windows/Fonts/msyh.ttc"          # 微软雅黑
FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"       # 微软雅黑 Bold（气泡/标题更好认）
FONT_EMOJI = "C:/Windows/Fonts/seguiemj.ttf"    # 回退 1：emoji（🍎🌾😷）
FONT_SYMBOL = "C:/Windows/Fonts/seguisym.ttf"   # 回退 2：符号（♪ ♫ ▶）—— ★ 雅黑与 emoji 字体都没有音符
FONT_FALLBACKS = (FONT_EMOJI, FONT_SYMBOL)


def font(size, bold=True):
    key = (size, bold)
    if key not in _FONTS:
        _FONTS[key] = ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size, index=0)
    return _FONTS[key]


_NOTDEF = {}
_GLYPH = {}


def glyph_ok(f, ch):
    """该字体有没有这个字符的真字形（带缓存）。

    ★ 判据：`getmask(ch).getbbox()` 与 `.notdef`（永不出现的 U+FFFF）的 bbox 相同 ⇒ 缺字方框。
      实测（2026-09-23）：**msyh / msyhbd 既没有 emoji（🍎🌾😷）也没有音符（♪ ♫）** ——
      不加这一层，镜 123 的黑屏字幕会印成豆腐块、页脚图例的 ♪ 会印成"口"。
    """
    key = (f.path, f.size, ch)
    hit = _GLYPH.get(key)
    if hit is None:
        nk = ("nd", f.path, f.size)
        if nk not in _NOTDEF:
            _NOTDEF[nk] = f.getmask("\uFFFF").getbbox()
        try:
            hit = f.getmask(ch).getbbox() != _NOTDEF[nk]
        except Exception:
            hit = False
        _GLYPH[key] = hit
    return hit


_ORIG_TEXT = ImageDraw.ImageDraw.text


def _text_with_fallback(self, xy, text, font=None, fill=None, **kw):
    """★ 给 `ImageDraw.text` 挂一个**逐字字形回退**：缺字形换 `seguiemj` 画。

    为什么挂全局而不是逐处改：全片有 7 处绘制入口（气泡/旁白/音效条/信息条/页眉/页脚/封面），
    逐处改必然漏；挂一次，**以后新增的绘制点也自动受保护**。
    """
    if font is None or not isinstance(text, str) or not text:
        return _ORIG_TEXT(self, xy, text, font=font, fill=fill, **kw)
    if all(glyph_ok(font, c) for c in text):
        return _ORIG_TEXT(self, xy, text, font=font, fill=fill, **kw)
    x, y = xy
    for ch in text:
        if glyph_ok(font, ch):
            _ORIG_TEXT(self, (x, y), ch, font=font, fill=fill, **kw)
            x += font.getlength(ch)
            continue
        for fp in FONT_FALLBACKS:              # 回退链：emoji → 符号
            try:
                fb = ImageFont.truetype(fp, font.size, index=0)
                if glyph_ok(fb, ch):
                    _ORIG_TEXT(self, (x, y), ch, font=fb, fill=fill, **kw)
                    x += fb.getlength(ch) + max(1, int(font.size * 0.12))
                    break
            except Exception:
                continue
        else:
            x += font.getlength("　")          # 回退也缺 ⇒ 留全角空位，别把后文挤乱


ImageDraw.ImageDraw.text = _text_with_fallback


_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’\-\.:%]*|[^\s]")
# ★ 行首禁则：这些标点不能出现在一行的开头（中文排版硬规则，实测会印出「，三个人。」这种行）
_NO_LINE_START = "，。、；：！？）》」』””’…—·%"


def wrap_text(text, f, max_w):
    """按像素宽度折行：CJK 逐字断行，ASCII 单词整体不拆，**并遵守行首禁则**。"""
    out = []
    for raw in str(text).split("\n"):
        cur = ""
        for tk in _TOKEN_RE.findall(raw):
            trial = cur + tk
            if cur and f.getlength(trial) > max_w:
                if tk in _NO_LINE_START:      # 标点跟着上一行走，宁可这行超宽一点点
                    cur = trial
                    continue
                out.append(cur)
                cur = tk.lstrip()
            else:
                cur = trial
        out.append(cur)
    return out or [""]


def text_size(f, lines):
    w = max([f.getlength(s) for s in lines] or [0])
    a, d = f.getmetrics()
    lh = int((a + d) * 1.26)
    return w, lh * len(lines), lh




# ─────────────────────────── ④ 一格（panel）渲染 ───────────────────────────

BLACK = (16, 16, 18)
WHITE = (255, 255, 255)
INK = (18, 18, 20)


def make_art(im, iw, ih, paper):
    """把源帧铺进格内画面区。

    · 横版：`ImageOps.fit` 满铺 —— 源帧与格内区宽高比只差 0.25%，视觉上等于原样；
    · 竖版：**模糊延展**（自身放大高斯模糊）铺底 + 原始帧等比居中含入 ⇒ 不裁切、不丢画面。
    """
    if paper == "a4l":
        return ImageOps.fit(im.convert("RGB"), (iw, ih), Image.LANCZOS, centering=(0.5, 0.45))
    bg = ImageOps.fit(im.convert("RGB"), (iw, ih), Image.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(max(8, iw / 26.0)))
    fh = max(1, int(round(iw * im.height / float(im.width))))
    fg = im.convert("RGB").resize((iw, fh), Image.LANCZOS)
    bg.paste(fg, (0, (ih - fh) // 2))
    return bg


def sharpen_up(art, src_w):
    """放大超 1.2× 才补锐化 —— 印刷下放大的柔感靠它拉回来。"""
    if art.width / float(src_w) > 1.2:
        return art.filter(ImageFilter.UnsharpMask(radius=2, percent=62, threshold=3))
    return art


def fit_bubble(text, max_w, max_h, L):
    """给定最大宽高，从大字号往小试 —— 返回放得下的那一档（None = 真装不下）。

    ★ 宁可字小，也不裁字：台词一个字都不能丢；装不下会在清单里被点名。
    """
    for size in range(L["fs_bubble_max"], L["fs_bubble_min"] - 1, -2):
        f = font(size, True)
        lines = wrap_text(text, f, max_w - 2 * L["pad"])
        w, h, lh = text_size(f, lines)
        w = int(w) + 2 * L["pad"]
        h = int(h) + 2 * L["pad"]
        if w <= max_w and h <= max_h:
            return f, lines, w, h, lh, size
    return None


def draw_bubble(canvas, rect, f, lines, lh, L, anchor):
    """白底圆角气泡 + 尖角 —— 尖角贴在**离说话人最近的那条边**（人上 ⇒ 尖角朝下）。"""
    bx0, by0, bx1, by1 = rect
    w, h = bx1 - bx0, by1 - by0
    ow, tail, pad = L["ow"], L["tail"], L["pad"]
    M = tail + ow + 4
    layer = Image.new("RGBA", (w + 2 * M, h + 2 * M), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    r = max(8, min(int(min(w, h) * 0.24), 40))
    base = max(26, int(min(w, h) * 0.42))
    cx = min(max((bx0 + bx1) // 2, bx0 + base // 2 + 4), bx1 - base // 2 - 4)
    ax = min(max(anchor[0], bx0 + base // 2 + 4), bx1 - base // 2 - 4)
    down = (by1 <= anchor[1])                      # 气泡在说话人上方 ⇒ 尖角向下
    ey = (M + h) if down else M
    d.polygon([(cx - base // 2, ey), (cx + base // 2, ey),
               (ax, (M + h + tail) if down else (M - tail))], fill=WHITE, outline=INK)
    d.rounded_rectangle([M, M, M + w, M + h], radius=r, fill=WHITE, outline=INK, width=ow)
    # 抹掉气泡边上的那一段描边 —— 尖角与气泡连成一体（否则看着像两个图形叠着）
    d.line([(cx - base // 2 - ow, ey), (cx + base // 2 + ow, ey)], fill=WHITE, width=ow + 2)
    canvas.paste(layer, (bx0 - M, by0 - M), layer)
    d0 = ImageDraw.Draw(canvas)
    ty = by0 + pad + max(0, (h - 2 * pad - lh * len(lines)) // 2)
    for s in lines:
        d0.text((bx0 + pad, ty), s, font=f, fill=INK)
        ty += lh


def draw_narration(canvas, rect, label, text, L):
    """旁白 / 屏幕字幕 / 黑屏字幕 → 米色方框（与气泡区分，一眼认得出「不是谁在说话」）。"""
    x0, y0, x1, y1 = rect
    ow, pad = L["ow"], L["pad"]
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle([x0, y0, x1, y1], radius=max(6, pad // 2),
                        fill=(255, 248, 214), outline=INK, width=ow)
    f = font(L["fs_narr"], False)
    y = y0 + pad
    if label:
        d.text((x0 + pad, y), label, font=font(int(L["fs_narr"] * 0.86), True),
               fill=(150, 96, 20))
        y += int(L["fs_narr"] * 1.18)
    for line in wrap_text(text, f, (x1 - x0) - 2 * pad):
        d.text((x0 + pad, y), line, font=f, fill=INK)
        y += int(L["fs_narr"] * 1.32)


def render_panel(canvas, x0, y0, shot, av, im, L, opt, meta, blackout=None):
    """一格 = 一镜：画面 + 气泡 + 旁白框 + 左下音效条 + 底部信息条。"""
    bw = L["border"]
    iw, ih = L["img_w"], L["img_h"]
    ix0, iy0 = x0 + bw, y0 + bw
    art = sharpen_up(make_art(im, iw, ih, L["paper"]), im.width)
    canvas.paste(grade(art, opt.grade), (ix0, iy0))
    ax0, ay0, ax1, ay1 = ix0, iy0, ix0 + iw, iy0 + ih
    pad = L["pad"]
    if blackout:                     # 源片烧录字幕 → 用黑边盖住（与格下黑条连成遮幅）
        fh = max(1, int(round(iw * im.height / float(im.width))))
        by = art_y_of((L["paper"], iw, ih, fh), im.height, blackout)
        ImageDraw.Draw(canvas).rectangle([ax0, ay0 + by, ax1, ay1], fill=BLACK)

    # ── 音效/音乐/歌词 条（贴左下；它是「听到的」，不是「说的」，所以不进气泡）──
    audio = (["♪ " + s for s in av["sfx"]] + ["♫ " + s for s in av["music"]]
             + ["♪ " + s for s in av["lyrics"]])
    if audio:
        line = " ｜ ".join(audio)
        f = font(L["fs_audio"], False)
        txt = line
        while f.getlength(txt) > iw * 0.94 and len(txt) > 8:
            txt = txt[:-2]
        if txt != line:
            txt += "…"
        tw = f.getlength(txt)
        bh_ = int(L["fs_audio"] * 1.9)
        bx, by = int(ax0 + pad // 2), ay1 - pad // 2 - bh_
        ov = Image.new("RGBA", (int(tw) + 2 * pad // 3, bh_), (255, 255, 255, 216))
        canvas.paste(ov, (bx, by))
        ImageDraw.Draw(canvas).text((bx + pad // 3, by + int(L["fs_audio"] * 0.3)),
                                    txt, font=f, fill=(40, 40, 44))

    # ── 旁白框：贴底，先给它专属高度，气泡在上方腾挪 ──
    narr_h = 0
    if av["narration"]:
        f = font(L["fs_narr"], False)
        lines = wrap_text(av["narration"], f, iw - 3 * pad)
        narr_h = (int(L["fs_narr"] * 1.18) if av["nlabel"] else 0) \
            + int(L["fs_narr"] * 1.32) * len(lines) + 2 * pad
        lim = int(ih * 0.64)
        if narr_h > lim:
            meta["warn"].append("镜 %d：旁白框偏高（%d 字 / %d px > %d px）"
                                % (shot["n"], len(av["narration"]), narr_h, lim))
            narr_h = lim
        draw_narration(canvas, [ax0 + pad // 2, ay1 - narr_h - pad // 2,
                                ax1 - pad // 2, ay1 - pad // 2],
                       av["nlabel"], av["narration"], L)

    # ── 气泡 ──
    bub_bottom = ay1 - pad // 2 - narr_h - (int(L["fs_audio"] * 1.9) if audio else 0)
    max_w = int(iw * (0.74 if L["paper"] == "a4l" else 0.9))
    max_h = max(int((bub_bottom - ay0) * 0.5), L["fs_bubble_min"] * 3)
    anchor = (int(ax0 + iw * 0.5), int(ay0 + (bub_bottom - ay0) * 0.72))
    placed = []
    for i, (who, txt_raw) in enumerate(av["bubbles"]):
        txt = ("%s：%s" % (who, txt_raw)) if who else txt_raw
        sol = fit_bubble(txt, max_w, max_h, L)
        if not sol:
            meta["overflow"].append("镜 %d：%s（%d 字）" % (shot["n"], txt, len(txt)))
            f = font(L["fs_bubble_min"], True)
            lines = wrap_text(txt, f, max_w - 2 * pad)
            w, h, lh = text_size(f, lines)
            sol = (f, lines, int(w) + 2 * pad, int(h) + 2 * pad, lh, L["fs_bubble_min"])
        f, lines, bw_, bh_, lh, size = sol
        meta["bubble_sizes"].append(size)
        bx0 = (ax0 + pad) if (i % 2 == 0) else (ax1 - pad - bw_)
        by0 = ay0 + pad
        for _ in range(300):                      # 避让：往下滚，撞不到就停
            clash = any(not (bx0 + bw_ < px0 or bx0 > px1 or by0 + bh_ < py0 or by0 > py1)
                        for (px0, py0, px1, py1) in placed)
            if not clash or by0 + bh_ > bub_bottom:
                break
            by0 += 8
        placed.append((bx0, by0, bx0 + bw_, by0 + bh_))
        draw_bubble(canvas, (bx0, by0, bx0 + bw_, by0 + bh_), f, lines, lh, L, anchor)

    # ── 底部信息条（镜号 · 幕 · 景别 · 运镜 ＋ 时长）──
    cy0, cy1 = iy0 + ih, y0 + L["panel_h"]
    d = ImageDraw.Draw(canvas)
    d.rectangle([x0, cy0, x0 + L["panel_w"], cy1], fill=BLACK)
    head = "镜 %03d" % shot["n"]
    if shot.get("sheet"):                      # 单页/幕后篇：不用「镜 NNN」，改「格 N」
        head = "格 %d" % shot["n"]
    f_shot, f_cap = font(L["fs_shot"], True), font(L["fs_cap"], False)
    ty = cy0 + ((cy1 - cy0) - int(L["fs_shot"] * 1.25)) // 2
    d.text((x0 + pad, ty), head, font=f_shot, fill=WHITE)
    sx = int(x0 + pad + f_shot.getlength(head) + pad)
    room = L["panel_w"] - (sx - x0) - pad * 3.2
    cap_s = " · ".join(x for x in (meta["act_short"].get(shot["n"], ""),
                                   shot["size"], shot["cam"]) if x)
    if opt.with_desc:
        cap_s += " · " + shot["pic"]
    f_use = f_cap
    while f_use.getlength(cap_s) > room and f_use.size > 18:
        f_use = font(f_use.size - 2, False)
    while f_use.getlength(cap_s) > room and len(cap_s) > 12:
        cap_s = cap_s[:-2]
    d.text((sx, ty + int((L["fs_shot"] - f_use.size) * 0.62)), cap_s,
           font=f_use, fill=(212, 212, 216))
    if shot.get("dur"):
        dur = "%ds" % shot["dur"]
        d.text((x0 + L["panel_w"] - pad - f_cap.getlength(dur),
                ty + int((L["fs_shot"] - L["fs_cap"]) * 0.62)), dur,
               font=f_cap, fill=(146, 146, 152))
    d.rectangle([x0, y0, x0 + L["panel_w"] - 1, cy1 - 1], outline=INK, width=bw)




# ─────────────────────────── ⑤ 一页（4 格）与封面 ───────────────────────────

LEGEND = "气泡＝台词　♪＝音效/音乐　米色方框＝屏幕字幕/旁白"
COVER_SUB = "上汇实验学校 2026 年科技节 · 超写实真人质感短片 · 四格漫画版"


def render_page(page_shots, items, L, opt, meta, page_no, total_pages):
    """一页 = 4 格（2×2）。页眉写本页涉及的幕，页脚写图例与配乐版权。"""
    canvas = Image.new("RGB", (L["W"], L["H"]), (255, 255, 255))
    d = ImageDraw.Draw(canvas)
    k = L["W"] / 3508.0 if L["paper"] == "a4l" else L["W"] / 2480.0

    # ── 页眉 ──
    acts_here, seen = [], set()
    for s in page_shots:
        a = meta["act_full"][s]
        if a not in seen:
            seen.add(a)
            acts_here.append(a)
    f_t = font(L["fs_title"], True)
    d.text((L["content_x0"], L["margin"]), " ／ ".join(acts_here), font=f_t, fill=INK)
    pg = "第 %02d / %d 页" % (page_no, total_pages)
    f_p = font(int(L["fs_title"] * 0.72), False)
    d.text((L["content_x1"] - f_p.getlength(pg), L["margin"] + int(L["fs_title"] * 0.16)),
           pg, font=f_p, fill=(90, 90, 96))
    f_s = font(L["fs_sub"], False)
    rng = ("镜 %03d – %03d" % (page_shots[0], page_shots[-1])) if len(page_shots) > 1 \
        else ("镜 %03d" % page_shots[0])
    d.text((L["content_x0"], L["margin"] + int(L["fs_title"] * 1.28)),
           rng + " · " + COVER_SUB, font=f_s, fill=(110, 110, 116))
    right = "每格一镜 · 顺序与成片一致"
    d.text((L["content_x1"] - f_s.getlength(right), L["margin"] + int(L["fs_title"] * 1.28)),
           right, font=f_s, fill=(110, 110, 116))
    rule_y = L["content_y0"] - int(26 * k)
    d.rectangle([L["content_x0"], rule_y, L["content_x1"], rule_y + max(2, int(3 * k))], fill=INK)

    # ── 4 格 ──
    for i, shot_no in enumerate(page_shots):
        r, c = divmod(i, L["col"])
        x0 = L["content_x0"] + c * (L["panel_w"] + L["gap"])
        y0 = L["content_y0"] + r * (L["panel_h"] + L["gap"])
        it = items[shot_no]
        render_panel(canvas, x0, y0, it["shot"], it["av"], it["im"], L, opt, meta,
                     it.get("blackout"))

    # ── 页脚 ──
    fy = L["H"] - L["margin"] - L["footer"] + int(14 * k)
    f_f = font(int(L["fs_sub"] * 0.92), False)
    d.text((L["content_x0"], fy), LEGEND, font=f_f, fill=(120, 120, 126))
    cr = meta["credits_short"]
    d.text((L["content_x1"] - f_f.getlength(cr), fy), cr, font=f_f, fill=(120, 120, 126))
    return canvas


def render_cover(L, meta, opt):
    """卷头：片名 + 主题句 + 人物表 + 幕结构 + 阅读说明 + 配乐版权（口径全部照抄 storyboard）。"""
    canvas = Image.new("RGB", (L["W"], L["H"]), (255, 255, 255))
    d = ImageDraw.Draw(canvas)
    k = L["W"] / 3508.0 if L["paper"] == "a4l" else L["W"] / 2480.0
    cx = L["W"] // 2
    y = L["margin"] + int(10 * k)

    f_big = font(int(150 * k), True)
    title = "《如愿·看见》"
    d.text((cx - f_big.getlength(title) / 2, y), title, font=f_big, fill=INK)
    y += int(150 * k * 1.18)
    f_s = font(int(L["fs_sub"] * 1.15), False)
    d.text((cx - f_s.getlength(COVER_SUB) / 2, y), COVER_SUB, font=f_s, fill=(110, 110, 116))
    y += int(L["fs_sub"] * 2.1)

    # 主题句（★ 全片锚点，不得删改）
    f_t = font(int(L["fs_narr"] * 1.08), True)
    tw = min(L["content_x1"] - L["content_x0"], int(2350 * k))
    lines = wrap_text(meta["theme"], f_t, tw - 4 * L["pad"])
    bh = int(L["fs_narr"] * 1.5) * len(lines) + 2 * L["pad"]
    d.rounded_rectangle([cx - tw // 2, y, cx + tw // 2, y + bh], radius=int(14 * k),
                        fill=(255, 248, 214), outline=INK, width=L["ow"])
    ty = y + L["pad"]
    for s in lines:
        d.text((cx - f_t.getlength(s) / 2, ty), s, font=f_t, fill=INK)
        ty += int(L["fs_narr"] * 1.5)
    y += bh + int(L["pad"] * 1.6)

    # 人物表（定妆照裁成 4:5 竖幅；★ 脸朝上，所以取景偏上 0.32）
    gap = int(30 * k)
    n = max(1, len(meta["cast"]))
    pw = min(int(330 * k), (L["content_x1"] - L["content_x0"] - gap * (n - 1)) // n)
    ph = int(pw * 1.24)
    total = pw * n + gap * (n - 1)
    px = cx - total // 2
    f_n = font(int(L["fs_cap"] * 1.05), True)
    f_r = font(int(L["fs_sub"] * 0.9), False)
    for name, role, path in meta["cast"]:
        if path and os.path.exists(path):
            im = ImageOps.fit(Image.open(path).convert("RGB"), (pw, ph),
                              Image.LANCZOS, centering=(0.5, 0.32))
            canvas.paste(im, (px, y))
            d.rectangle([px, y, px + pw - 1, y + ph - 1], outline=INK, width=L["ow"])
        d.text((px, y + ph + int(8 * k)), name, font=f_n, fill=INK)
        # 身份行：折到 2 行以内；再放不下就按像素截断加省略号（★ 不许压到隔壁人像上）
        rlines = wrap_text(role, f_r, pw)[:2]
        if len(rlines) > 1 and f_r.getlength(rlines[1]) > pw:
            rlines[1] = rlines[1][:-1]
        while f_r.getlength(rlines[-1]) > pw and len(rlines[-1]) > 4:
            rlines[-1] = rlines[-1][:-1] + "…"
        ry = y + ph + int(8 * k) + int(L["fs_cap"] * 1.3)
        for s in rlines:
            d.text((px, ry), s, font=f_r, fill=(120, 120, 126))
            ry += int(L["fs_sub"] * 1.15)
        px += pw + gap
    y += ph + int(L["fs_cap"] * 1.3) + int(L["fs_sub"] * 3.2) + int(26 * k)

    # 幕结构表
    f_h = font(int(L["fs_cap"] * 1.02), True)
    f_b = font(int(L["fs_cap"] * 0.98), False)
    cols = [0, int(1050 * k), int(1700 * k), int(2140 * k)]
    d.text((L["content_x0"], y), "全片结构（%d 镜 · %s）" % (meta["n_shots"], meta["total_dur"]),
           font=f_h, fill=INK)
    y += int(L["fs_cap"] * 1.6)
    for i, c in enumerate(["幕", "镜号", "镜数", "时长"]):
        d.text((L["content_x0"] + cols[i], y), c, font=f_h, fill=(90, 90, 96))
    y += int(L["fs_cap"] * 1.35)
    for a in meta["acts"]:
        d.text((L["content_x0"] + cols[0], y), a["name"], font=f_b, fill=INK)
        d.text((L["content_x0"] + cols[1], y), "%d–%d" % (a["lo"], a["hi"]), font=f_b, fill=INK)
        d.text((L["content_x0"] + cols[2], y), str(a["count"]), font=f_b, fill=INK)
        d.text((L["content_x0"] + cols[3], y), a["dur"], font=f_b, fill=INK)
        y += int(L["fs_cap"] * 1.42)

    # 阅读说明 + 配乐版权
    y += int(20 * k)
    f_l = font(int(L["fs_sub"] * 0.98), False)
    for s in meta["howto"]:
        d.text((L["content_x0"], y), s, font=f_l, fill=(80, 80, 86))
        y += int(L["fs_sub"] * 1.44)
    y += int(8 * k)
    for s in meta["credits"]:
        d.text((L["content_x0"], y), s, font=f_l, fill=(120, 120, 126))
        y += int(L["fs_sub"] * 1.44)
    return canvas


# ─────────────────────────── ⑥ PDF / 清单 / 主流程 ───────────────────────────

def save_pdf(png_paths, out_path, dpi):
    """多页 A4 PDF：每页先转 JPEG（q92）再嵌入 —— 直接把 3508×2480 的 RGB 塞进去会变巨大。"""
    imgs = []
    for p in png_paths:
        im = Image.open(p).convert("RGB")
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=92, subsampling=0)
        buf.seek(0)
        imgs.append(Image.open(buf).copy())
    imgs[0].save(out_path, save_all=True, append_images=imgs[1:],
                 resolution=dpi, quality=92)
    return os.path.getsize(out_path) / 1048576.0


def paginate(shot_list, keep_acts, meta):
    """默认连续排版（4 镜一页，不浪费纸）；`--keep-acts` 则每幕单独起页。"""
    pages, cur = [], []
    for n in shot_list:
        if keep_acts and cur and meta["act_of"][n] != meta["act_of"][cur[-1]]:
            pages.append(cur)
            cur = []
        cur.append(n)
        if len(cur) == 4:
            pages.append(cur)
            cur = []
    if cur:
        pages.append(cur)
    return pages


def parse_roles(sb_text):
    """从 storyboard「角色性格与定位」表取四小强的「性格」短语（不另写一份人设）。"""
    roles = {}
    for ln in sb_text.splitlines():
        s = ln.strip()
        if not (s.startswith("|") and s.endswith("|")):
            continue
        p = [c.strip() for c in s.strip("|").split("|")]
        if len(p) != 5:
            continue
        name = _clean(p[0])
        if name in ("张书扬", "徐畅景", "刘思齐", "刘思成"):
            roles[name] = _clean(p[2])
    return roles


def build_meta(shots, acts, theme, credits, sb_text, cards):
    meta = {"act_short": {}, "act_full": {}, "act_of": dict(ACT_OF),
            "acts": acts, "theme": theme, "cards": cards,
            "warn": [], "overflow": [], "bubble_sizes": [], "captions": [],
            "n_shots": len(shots),
            "total_dur": "%.0f s" % sum(s["dur"] for s in shots.values()),
            "credits": list(credits) + ["仅用于校内科技节展示，非商业用途。"],
            "credits_short": "配乐：《如愿》(王菲) ／ Forrest Gump Suite (Alan Silvestri) · 校内非商业展示",
            "howto": [
                "· 一页 4 格、一格一镜：镜号 1→126，顺序与成片完全一致（每格画面取自该镜成片的一帧）。",
                "· " + LEGEND,
                "· 格下黑条：镜 号 · 幕 · 景别 · 运镜 · 时长（景别/运镜的定义见 storyboard.md）。",
                "· " + ("本册含全部 %d 镜。" % len(shots)),
            ]}
    for a in acts:
        for n in range(a["lo"], a["hi"] + 1):
            meta["act_full"][n] = a["name"]
            meta["act_short"][n] = a["name"].split("：")[0]
    roles = parse_roles(sb_text)
    G, C = (os.path.join(ROOT, "ASSETS", "CHARACTERS", "_group"),
            os.path.join(ROOT, "ASSETS", "CHARACTERS"))
    meta["cast"] = [
        ("刘思齐", "八（1）班 · " + roles.get("刘思齐", "").split("，")[0], os.path.join(G, "solo_liu_siqi_hero_v01.png")),
        ("刘思成", "八（1）班 · " + roles.get("刘思成", "").split("，")[0], os.path.join(G, "solo_liu_sicheng_hero_v01.png")),
        ("徐畅景", "八（1）班 · " + roles.get("徐畅景", "").split("，")[0], os.path.join(G, "solo_xu_changjing_hero_v01.png")),
        ("张书扬", "八（1）班 · 世界模型训练者", os.path.join(G, "solo_zhang_shuyang_hero_v01.png")),
        ("黄继光", "1952 · 上甘岭", os.path.join(G, "solo_huang_jiguang_hero_v01.png")),
        ("袁隆平", "1961 · 安江农校", os.path.join(G, "solo_yuan_longping_hero_v01.png")),
        ("钟南山", "2020 · 高铁餐车", os.path.join(G, "solo_zhong_nanshan_hero_v01.png")),
    ]
    # ★ 防漂移自检：封面/图例里出现的专有名词必须在 storyboard.md 里找得到
    for t in ("上甘岭", "安江农校", "高铁餐车", "每个孩子都能上学"):
        if t not in sb_text:
            meta["warn"].append("封面/图例用词「%s」在 storyboard.md 里找不到 —— 口径可能已变" % t)
    return meta


def write_manifest(path, meta, items, pages, plan):
    L = []
    L.append("# 四格漫画 · 印制清单与解析报告\n")
    L.append("> 由 `OUTPUT/_make_comic.py` 生成（脚本入库、产物不入库）。**本文件是产物的说明台账**，")
    L.append("> 内容全部从 `storyboard.md` 与成片镜头产物解析而来，改台词/换镜头后重跑即自动同步。\n")
    L.append("## 产出\n")
    for row in plan:
        L.append("- `%s`　%s" % (row[0], row[1]))
    L.append("")
    L.append("## 印制参数\n")
    L.append("| 项 | 值 |")
    L.append("|---|---|")
    L.append("| 镜数 | %d |" % meta["n_shots"])
    L.append("| 页数 | 每版 %d 页（含封面 %d 页） |" % (len(pages), 1 if meta["cover"] else 0))
    L.append("| 每页格数 | 4（2×2） |")
    L.append("| 抽帧位置 | 镜头时长的 %.0f%% |" % (meta["at"] * 100))
    L.append("| 调色 | %s |" % meta["grade"])
    L.append("| 主题句 | %s |" % meta["theme"])
    L.append("")
    for key, title in (("overflow", "⚠️ 气泡溢出（字号已到下限仍需截断）"),
                       ("warn", "⚠️ 其它告警")):
        L.append("## %s\n" % title)
        L.append("\n".join("- " + s for s in meta[key]) if meta[key] else "- 无")
        L.append("")
    L.append("## 源片烧录字幕（已用黑边盖住）\n")
    L.append("- 白名单镜（成片有意要出现的屏幕字，**不盖**）：%s" % sorted(CARD_SHOTS))
    L.append("- 检出并盖黑边：%s" % (meta["captions"] or "无"))
    L.append("- 判据：**细段密集（白色小段 ≥8）+ 位置低位（y ≥ 0.86H）+ 上方留白（上 4 行近乎无白）**"
             "三条同时满足；纯「有白像素就算」会把白衣服/白稻穗算进去（实测镜 48/61 假阳性）。")
    L.append("- 处理方式：**盖黑边而不是裁帧** —— 只吃掉画面底部那一条，横向构图不动，"
             "与格下黑条连成遮幅；`--no-hide-caption` 可关闭。\n")
    L.append("## 逐页目录\n")
    L.append("| 页 | 镜号 | 幕 |")
    L.append("|:--:|---|---|")
    for i, p in enumerate(pages, 1):
        L.append("| %d | %s | %s |" % (i, "%d–%d" % (p[0], p[-1]) if len(p) > 1 else str(p[0]),
                                       meta["act_short"][p[0]]))
    L.append("")
    L.append("## 逐镜清单（气泡 / 音效 / 旁白 与来源）\n")
    L.append("| 镜 | 幕 | 景别·运镜 | 气泡 | 音效·音乐·歌词 | 旁白/字幕 | 源文件 |")
    L.append("|:--:|---|---|---|---|---|---|")
    for n in sorted(items):
        it = items[n]
        av = it["av"]
        bub = "；".join("%s（%d字）" % (w, len(t)) for w, t in av["bubbles"]) or "—"
        aud = "；".join(av["sfx"] + av["music"] + av["lyrics"]) or "—"
        nar = ("%s%s" % (av["nlabel"] or "", (av["narration"] or "").replace("\n", "／"))) \
            if av["narration"] else "—"
        L.append("| %d | %s | %s · %s | %s | %s | %s | `%s` |"
                 % (n, meta["act_short"][n], it["shot"]["size"], it["shot"]["cam"],
                    bub, aud, nar, os.path.basename(it["src"])))
    L.append("")
    open(path, "w", encoding="utf-8").write("\n".join(L))
    return path


# ─────────────────────────────── ⑦ 主流程 ───────────────────────────────

def parse_making_sheet(path):
    """解析 `OUTPUT/_comic_making.md`（幕后篇的**唯一出处**：页标题 + 4 格图/标签/台词）。

    ★ 台词列沿用逐镜表同一套写法（`说话人：台词` / `音效：…`），
      所以能**直接复用 `parse_av()`** —— 气泡/音效条/旁白框的规则一个字都不用另写。
    """
    info, panels = {}, []
    for ln in open(path, encoding="utf-8").read().splitlines():
        s = ln.strip()
        if not (s.startswith("|") and s.endswith("|")):
            continue
        p = [c.strip() for c in s.strip("|").split("|")]
        if len(p) == 2 and p[0] in ("页标题", "副标题", "图源"):
            info[p[0]] = _clean(p[1])
        elif len(p) == 4 and re.fullmatch(r"\d+", p[0]) and "`" in p[1]:
            panels.append({"i": int(p[0]), "img": p[1].strip("`"),
                           "tag": _clean(p[2]), "av": p[3]})
    if len(panels) != 4:
        raise SystemExit("!! %s 的面板表应恰好 4 行（拿到 %d 行）" % (path, len(panels)))
    return info, panels


def render_sheet_page(info, panels, L, opt, meta):
    """单页四格（幕后篇）：页眉写标题，4 格**复用 `render_panel()`** —— 气泡/旁白/音效条同一套。"""
    canvas = Image.new("RGB", (L["W"], L["H"]), (255, 255, 255))
    d = ImageDraw.Draw(canvas)
    k = L["W"] / 3508.0 if L["paper"] == "a4l" else L["W"] / 2480.0
    f_t = font(L["fs_title"], True)
    d.text((L["content_x0"], L["margin"]), info.get("页标题", "幕后篇"), font=f_t, fill=INK)
    f_s = font(L["fs_sub"], False)
    d.text((L["content_x0"], L["margin"] + int(L["fs_title"] * 1.28)),
           info.get("副标题", ""), font=f_s, fill=(110, 110, 116))
    tag = info.get("页码字", "幕后篇 · 单页四格")
    d.text((L["content_x1"] - f_s.getlength(tag), L["margin"] + int(L["fs_title"] * 1.28)),
           tag, font=f_s, fill=(110, 110, 116))
    rule_y = L["content_y0"] - int(26 * k)
    d.rectangle([L["content_x0"], rule_y, L["content_x1"], rule_y + max(2, int(3 * k))], fill=INK)

    for i, p in enumerate(panels):
        r, c = divmod(i, L["col"])
        x0 = L["content_x0"] + c * (L["panel_w"] + L["gap"])
        y0 = L["content_y0"] + r * (L["panel_h"] + L["gap"])
        img = os.path.join(ROOT, p["img"].replace("/", os.sep))
        if not os.path.exists(img):
            raise SystemExit("!! 面板图不存在：%s（先跑 OUTPUT/_make_making_panels.py）" % img)
        shot = {"n": p["i"], "dur": 0, "size": p["tag"], "cam": "", "pic": "", "av": p["av"],
                "sheet": True}
        av = parse_av(shot, [])
        render_panel(canvas, x0, y0, shot, av, Image.open(img).convert("RGB"), L, opt, meta)

    fy = L["H"] - L["margin"] - L["footer"] + int(14 * k)
    f_f = font(int(L["fs_sub"] * 0.92), False)
    d.text((L["content_x0"], fy), LEGEND, font=f_f, fill=(120, 120, 126))
    note = "幕后篇 · 画面取自本片镜 9 / 镜 121 的成片帧经图生图重绘（同一批演员形象）"
    d.text((L["content_x1"] - f_f.getlength(note), fy), note, font=f_f, fill=(120, 120, 126))
    return canvas, [(p["i"], parse_av({"n": p["i"], "av": p["av"], "pic": ""}, [])) for p in panels]


def parse_range(spec, all_shots):
    s = set()
    for part in re.split(r"[,\s]+", spec.strip()):
        if not part:
            continue
        m = re.fullmatch(r"(\d+)\s*[-–~]\s*(\d+)", part)
        if m:
            s.update(range(int(m.group(1)), int(m.group(2)) + 1))
        elif part.isdigit():
            s.add(int(part))
        else:
            raise SystemExit("!! 无法理解的镜号写法：%s" % part)
    bad = sorted(x for x in s if x not in all_shots)
    if bad:
        raise SystemExit("!! 镜号不存在：%s" % bad)
    return sorted(s)


def main():
    ap = argparse.ArgumentParser(description="分镜 → A4 四格漫画（每格一镜 + 台词气泡）")
    ap.add_argument("--paper", default="both", choices=["both", "a4l", "a4p"])
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--at", type=float, default=0.5, help="抽帧位置（占镜头时长比例）")
    ap.add_argument("--grade", default="soft", choices=["soft", "none", "comic"])
    ap.add_argument("--shots", default="", help="只做该区间，如 1-12")
    ap.add_argument("--only", default="", help="只做这些镜号，如 6,39,116")
    ap.add_argument("--bubble-min", type=int, default=26, help="气泡最小字号（300dpi 基准）")
    ap.add_argument("--keep-acts", action="store_true", help="每幕单独起新页")
    ap.add_argument("--with-desc", action="store_true", help="格下附「画面」描述")
    ap.add_argument("--no-cover", action="store_true")
    ap.add_argument("--no-png", action="store_true", help="只出 PDF，不留 PNG 母版（省 ~250 MB）")
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--out", default="", help="产物目录（默认 OUTPUT/comic；试排时可指到别的目录，别覆盖正式母版）")
    ap.add_argument("--force-frames", action="store_true")
    ap.add_argument("--no-hide-caption", action="store_true",
                    help="不裁掉源片里的烧录字幕（默认自动裁；白名单镜永不裁）")
    ap.add_argument("--check", action="store_true", help="只解析 + 报告，不出图（闸门）")
    ap.add_argument("--sheet", default="", choices=["", "making"],
                    help="只出「单页四格」（making = 幕后篇，规格见 OUTPUT/_comic_making.md）")
    ap.add_argument("--sheet-md", default="", help="单页规格文件的路径（默认 OUTPUT/_comic_making.md）")
    opt = ap.parse_args()

    outdir = opt.out if os.path.isabs(opt.out) else os.path.join(ROOT, opt.out) if opt.out else OUT

    # ── ★ 单页模式（幕后篇）：只出一页四格，不碰全片 126 镜的任何产物 ──
    #    放在最前面：单页只依赖 spec（`_comic_making.md`）与 4 张面板图，
    #    连 `storyboard.md` 都不用解析 ⇒ 输出干净、跑得快。
    if opt.sheet:
        os.makedirs(outdir, exist_ok=True)
        L = paper_layout("a4l", opt.dpi)                  # 单页固定 A4 横版（用户口径）
        L["fs_bubble_min"] = max(12, int(opt.bubble_min * (opt.dpi / 300.0)))
        info, panels = parse_making_sheet(opt.sheet_md or SHEET_MD)
        meta_s = {"act_short": {p["i"]: "" for p in panels}, "warn": [], "overflow": [],
                  "bubble_sizes": [], "captions": []}
        canvas, avs = render_sheet_page(info, panels, L, opt, meta_s)
        pdir = os.path.join(outdir, "making")
        os.makedirs(pdir, exist_ok=True)
        png = os.path.join(pdir, "page_01_making.png")
        canvas.save(png)
        plan = [(os.path.relpath(png, ROOT).replace("\\", "/"),
                 "单页四格（A4 横版 %d×%d @%d dpi）" % (L["W"], L["H"], opt.dpi))]
        if not opt.no_pdf:
            pdf = os.path.join(pdir, "ruyuan_comic_making_A4_%ddpi.pdf" % opt.dpi)
            mb = save_pdf([png], pdf, opt.dpi)
            plan.append((os.path.relpath(pdf, ROOT).replace("\\", "/"),
                         "单页 PDF（1 页 / %.1f MB）" % mb))
        print("单页四格（%s）：" % (opt.sheet_md or SHEET_MD))
        print("  页眉：%s ｜ %s" % (info.get("页标题", ""), info.get("副标题", "")))
        print("  出图：%s" % os.path.relpath(png, ROOT))
        for i, av in avs:
            print("  格 %d：气泡 %s ｜ 音效 %s" % (
                i, [(w, t) for w, t in av["bubbles"]] or "—",
                "; ".join(av["sfx"] + av["music"] + av["lyrics"]) or "—"))
        print("  气泡字号：%s ｜ 告警 %d 条 ｜ 溢出 %d 条"
              % (sorted(set(meta_s["bubble_sizes"])) or "—",
                 len(meta_s["warn"]), len(meta_s["overflow"])))
        for s in meta_s["warn"] + meta_s["overflow"]:
            print("    ! " + s)
        return 0

    sb_text = open(SB_MD, encoding="utf-8").read()
    shots, acts, theme, cards, credits = parse_storyboard(SB_MD)
    os.makedirs(OUT, exist_ok=True)
    build_act_map(acts)
    meta = build_meta(shots, acts, theme, credits, sb_text, cards)
    meta.update(at=opt.at, grade=opt.grade, cover=not opt.no_cover)
    if not theme:
        meta["warn"].append("storyboard.md 里没解析到「主题」行")

    if opt.only:
        want = set(parse_range(opt.only, shots))
    elif opt.shots:
        want = set(parse_range(opt.shots, shots))
    else:
        want = set(shots)
    srcs = collect_sources()
    miss = sorted(want - set(srcs))
    if miss:
        meta["warn"].append("找不到镜头产物（这些镜出不了图）：%s" % miss)
        want -= set(miss)

    items = {}
    for n in sorted(want):
        items[n] = {"shot": shots[n], "av": parse_av(shots[n], cards),
                    "src": srcs[n], "im": None}
    pages = paginate(sorted(want), opt.keep_acts, meta)

    nb = sum(len(v["av"]["bubbles"]) for v in items.values())
    print("=" * 72)
    print("镜数：%d　页数：%d（4 格/页）　气泡：%d 个" % (len(items), len(pages), nb))
    print("无台词镜（本来无人说话，靠音效条交代）：%s"
          % ([n for n in items if not items[n]["av"]["bubbles"]] or "无"))
    print("字幕/旁白框：%s" % [(n, items[n]["av"]["nlabel"])
                               for n in items if items[n]["av"]["narration"]])
    print("有音效/音乐条的镜：%d"
          % sum(1 for n in items if items[n]["av"]["sfx"] or items[n]["av"]["music"]
                or items[n]["av"]["lyrics"]))
    print("幕结构：" + " | ".join("%s %d-%d %s" % (a["name"], a["lo"], a["hi"], a["dur"])
                                  for a in acts))
    print("主题句：%s" % theme)
    print("=" * 72)

    if opt.check:
        # ★ 闸门模式下也尽量填「烧录字幕」台账：帧已缓存就顺手检测（不新抽帧、不出图）
        for n in sorted(items):
            fp = os.path.join(FRAMES, "%03d.png" % n)
            if os.path.exists(fp):
                items[n]["blackout"] = hide_film_caption(
                    Image.open(fp).convert("RGB"), n, meta)
        print("烧录字幕（据已缓存帧）：%s" % (meta["captions"] or "无（或帧未缓存）"))
        mpath = write_manifest(MANIFEST, meta, items, pages,
                               plan=["（`--check` 模式：本次只解析、未重出图；正式产物见 `OUTPUT/comic/`）"])
        print("[check] 清单已写：%s" % os.path.relpath(mpath, ROOT))
        return 0

    os.makedirs(OUT, exist_ok=True)
    outdir = opt.out if os.path.isabs(opt.out) else os.path.join(ROOT, opt.out) if opt.out else OUT
    os.makedirs(outdir, exist_ok=True)
    for n in sorted(items):
        im = Image.open(get_frame(n, items[n]["src"], opt.at, opt.force_frames)).convert("RGB")
        items[n]["blackout"] = None if opt.no_hide_caption \
            else hide_film_caption(im, n, meta)
        items[n]["im"] = im
    print("烧录字幕：检出并盖黑边 %d 镜 %s（白名单镜 %s 不盖）"
          % (len(meta["captions"]), meta["captions"] or "无", sorted(CARD_SHOTS)))

    papers = ["a4l", "a4p"] if opt.paper == "both" else [opt.paper]
    tmpdir = os.path.join(OUT, "_tmp_pdf")
    plan = []
    print("─" * 72)
    for paper in papers:
        L = paper_layout(paper, opt.dpi)
        L["fs_bubble_min"] = max(12, int(opt.bubble_min * (opt.dpi / 300.0)))
        pdir = tmpdir if opt.no_png else os.path.join(outdir, "pages_%s" % paper)
        os.makedirs(pdir, exist_ok=True)
        pngs = []
        if not opt.no_cover:
            cover = os.path.join(pdir, "page_00_cover.png")
            render_cover(L, meta, opt).save(cover)
            pngs.append(cover)
        for i, page in enumerate(pages, 1):
            p = os.path.join(pdir, "page_%02d.png" % i)
            render_page(page, items, L, opt, meta, i, len(pages)).save(p)
            pngs.append(p)
            print("  [%s] %3d/%d 页　镜 %s" % (paper, i, len(pages),
                                              "%d–%d" % (page[0], page[-1])))
        print("  [%s] 版面 %d×%d @%ddpi　格 %d×%d　画面区 %d×%d"
              % (paper, L["W"], L["H"], opt.dpi, L["panel_w"], L["panel_h"],
                 L["img_w"], L["img_h"]))
        if not opt.no_pdf:
            pdf = os.path.join(outdir, "ruyuan_comic_%s_%ddpi.pdf" % (paper, opt.dpi))
            mb = save_pdf(pngs, pdf, opt.dpi)
            plan.append((os.path.relpath(pdf, ROOT).replace("\\", "/"),
                         "多页 A4 PDF（%d 页 / %.1f MB）" % (len(pngs), mb)))
        if not opt.no_png:
            plan.append((os.path.relpath(pdir, ROOT).replace("\\", "/") + "/page_*.png",
                         "%s 打印母版 %d 张（%d×%d @%d dpi）"
                         % (paper, len(pngs), L["W"], L["H"], opt.dpi)))
    if opt.no_png:
        shutil.rmtree(tmpdir, ignore_errors=True)

    mpath = write_manifest(MANIFEST, meta, items, pages, plan)
    sizes = sorted(meta["bubble_sizes"])
    print("-" * 72)
    if sizes:
        print("气泡字号：%d～%d（中位 %d，下限 %d）"
              % (sizes[0], sizes[-1], sizes[len(sizes) // 2], opt.bubble_min))
    print("溢出告警 %d 条　其它告警 %d 条" % (len(meta["overflow"]), len(meta["warn"])))
    for s in meta["overflow"][:12]:
        print("   ! " + s)
    for s in meta["warn"][:12]:
        print("   ! " + s)
    print("清单：%s" % os.path.relpath(mpath, ROOT))
    print("完成：%d 格 → %d 页 × %d 个版式" % (len(items), len(pages), len(papers)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

