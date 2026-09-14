# -*- coding: utf-8 -*-
"""序幕一《纸飞机》视频批量生成（镜 1-9）—— 跳过首帧，直接「人物参考图 + 场景图」喂 H3 R2V。

⚠️ 命名说明（与 README §2 的 scene 序号对齐）：
   本片「序幕一」对应 scene 目录 `01_school_gate` / `02_campus` / `03_classroom_day`，
   脚本名用 `act0_plane`。全片映射：

       序幕一《纸飞机》  镜 1-9    → 01/02/03 场景   ← ★ 本脚本
       序幕二《启动》    镜 10-18  → 04_classroom_dusk  (_diag_act2_startup.py)
       第一幕《上甘岭》  镜 19-46  → 06_trench          (_diag_act1_trench.py)
       第二幕《禾下乘凉》镜 47-74  → 07_rice_field      (_diag_act3_rice.py)
       第三幕《餐车》    镜 75-105 → 08_train_dining    (_diag_act4_train.py)
       尾声《归来与揭晓》镜 106-126→ 05_classroom_night (_diag_act5_finale.py)

台词与镜号严格取自 `storyboard.md` §序幕一：纸飞机（6 月底下午，阳光明媚）。

★ 本幕的三个硬约束（storyboard 明写「不得压缩 / 不得删改」）：
  · 镜 4 从 5s 延长到 **7s**，是为**展示校园**（科技节片子的核心功能）——
    需依次掠过操场 / 林荫道 / 花坛 / 教学楼四地点，每地 1.5-2s。航拍跟拍 ⇒ **steps=20**
  · 镜 6 从 2.33s 延长到 **5s**，台词含「是不是隔壁班暗恋我的？」—— 建立张书扬性格
  · 镜 1/4/5 为**上汇实验学校展示镜**（校牌 / 校园四地点 / 窗外校园一角）—— 不得压缩

⚠️ steps：本幕默认 **20**（航拍跟拍、飞入窗户等画面剧变镜）；静态/对话镜可 `--steps=10` 提速。

⚠️ 音频（README §4.4）：镜 3/4 的「音乐（后期）」会被 strip_late_audio() 剔除；
   镜 4/5/9 无台词 ⇒ 挂 NO_SPEECH 防 H3 幻觉人声（实测镜 4 会出「啊」、镜 5 出整句胡话）。

用法：
    py -3.10 OUTPUT/_diag_act0_plane.py --dry           # 只看任务清单
    py -3.10 OUTPUT/_diag_act0_plane.py --steps=20      # 全量（默认 20）
    py -3.10 OUTPUT/_diag_act0_plane.py --steps=10 2 3  # 指定镜
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = r"E:\code\stem_fest"
COMFY = "http://127.0.0.1:8188"
COMFY_OUT = r"E:\code\ComfyUI\output"
COMFY_IN = r"E:\code\ComfyUI\input"
WORKFLOW_DIR = os.path.join(ROOT, "workflows")
OUT_ROOT = os.path.join(ROOT, "OUTPUT", "01_paper_plane", "video")
REPORT = os.path.join(ROOT, "OUTPUT", "_act0_plane_report.txt")
CLIENT_ID = "act0v_plane"

FRAMES = os.path.join(ROOT, "ASSETS", "CHARACTERS")
SCENES = os.path.join(ROOT, "ASSETS", "SCENES")
PROPS = os.path.join(ROOT, "ASSETS", "PROPS")

WF_R2V = "video_minimax_h3_r2v.json"
WF_T2V = "video_minimax_h3_t2v.json"

# 序幕一统一光线基调（storyboard：6 月底下午、阳光明媚、高饱和暖调）
LIGHT = (
    "6 月底的下午，阳光明媚、空气通透，高饱和暖调，"
    "光线从画面侧上方斜射，人物脸上有柔和的暖光与自然的浅阴影"
)

SCENE_GATE = os.path.join(SCENES, "01_school_gate", "school_gate_wide_v02.png")
SCENE_CAMPUS = os.path.join(SCENES, "02_campus", "campus_wide_v01.png")
SCENE_CLASS = os.path.join(SCENES, "03_classroom_day", "classroom_day_wide_v01.png")

# ── 角色参考图 ────────────────────────────────────────────
P_GIRL = os.path.join(FRAMES, "_extras", "09_girl", "girl_hero_v01.png")
P_MOTHER = os.path.join(FRAMES, "_extras", "10_mother", "mother_hero_v01.png")

# ── 合影参考图（R2V 硬前提；一律用不带标签的 hero_v01）──
G_FOUR = os.path.join(FRAMES, "_group", "four_students_hero_v02.png")
G_GIRL_MOTHER = os.path.join(FRAMES, "_group", "girl_mother_hero_v01.png")
G_SIQI_ZHANG_XU = os.path.join(FRAMES, "_group", "liu_siqi_zhang_shuyang_xu_changjing_hero_v01.png")

# ── 道具参考图 ────────────────────────────────────────────
P_PLANE = os.path.join(PROPS, "01_paper_plane", "paper_plane_hero_v01.png")

# 无台词镜的通用禁语音后缀（README §4.4）
# ★ 2026-09-15 视觉检查修复：旧版是**否定式指令**（「本镜不要生成任何…」），
# H3 无法区分「对模型说的话」与「台词」，会把指令本身渲染成画面字幕
# （已实锤：镜 5 底部出现「本镜不要生成任何可语午白」）。
# 新版改为**纯正向音景描述**：只说「有什么声音」，不说「不要什么声音」。
# 音景本身不含可读词句 ⇒ 既满足音频生成，又不可能被当成台词。
NO_SPEECH = (
    "Audio: 安静的室内环境底噪；轻微的衣料摩擦声与呼吸声；"
    "远处传来模糊的人群杂音，听不清任何词句。"
)

# ★ 音频三层分工（README §4.4）：带「（后期）」的音效不进 H3 prompt
LATE_MARK = "（后期）"


def strip_late_audio(text):
    """把「…（后期）」这类后期音效从句子里剔除，只留 L1 台词给 H3。"""
    import re as _re
    out = []
    for sent in _re.split(r"(?<=[；。])|\n", text):
        if LATE_MARK in sent:
            continue
        out.append(sent)
    return "".join(out).strip()


TASKS = {}

# ── 镜 1 校门口：小女孩 + 妈妈（序幕一开篇；★ 校园展示镜）──
TASKS[1] = dict(
    slug="girl_mother_at_school_gate", seed=9101,
    ref1=G_GIRL_MOTHER, ref2=SCENE_GATE, dur=3.0,
    prompt=(
        "CUT 1: 全景镜头。一位三十多岁的母亲牵着五岁小女孩的手，站在学校大门口前，"
        "小女孩仰头看着校门上的校牌、眼睛亮亮的，母亲低头含笑看着她；"
        "校牌清晰可见、完整入画；"
        "两人的面貌、发型与服装严格照 <Picture 1>（**不要改变长相与年龄**）；"
        "背景是 <Picture 2> 那所学校正门口的实景；"
        + LIGHT + "。固定机位，只留轻微手持呼吸感。\n"
        "Audio: 校门口的环境音，微风、远处隐约的校园喧闹声（后期）；"
        "小女孩仰头、清脆地说：妈妈，这个学校好漂亮！"
    ),
)

# ── 镜 2 妈妈低头看她（近景）──
TASKS[2] = dict(
    slug="mother_looking_at_girl", seed=9102,
    ref1=G_GIRL_MOTHER, ref2=SCENE_GATE, dur=4.0,
    prompt=(
        "CUT 1: 近景镜头。母亲笑着低下头看身边的小女孩，眼神温柔；"
        "小女孩在画面里只入画一部分（侧脸或后脑勺），**不要让她消失**；"
        "两人的面貌、发型与服装严格照 <Picture 1>（**不要改变长相与年龄**）；"
        "背景是 <Picture 2> 那所学校正门口的实景、略微虚化；"
        + LIGHT + "。固定机位。\n"
        "Audio: 校门口环境音（后期）；母亲温和地说：那你明年就可以来这儿读书了。"
    ),
)

# ── 镜 3 甩纸飞机（中景）──
TASKS[3] = dict(
    slug="girl_throwing_paper_plane", seed=9103,
    ref1=G_GIRL_MOTHER, ref2=P_PLANE, dur=3.0,
    prompt=(
        "CUT 1: 中景镜头。小女孩右手捏着一架白色纸飞机，先凑到嘴边哈了一口气，"
        "然后手臂用力向前一甩，把纸飞机朝校门方向掷出去，动作干脆、表情兴奋；"
        "母亲站在她身旁看着、含笑**（不要让她消失）**；纸飞机的形态照 <Picture 2>；"
        "人物的面貌、发型与服装严格照 <Picture 1>（**不要改变长相与年龄**）；"
        + LIGHT + "。固定机位，甩手瞬间镜头轻微跟随。\n"
        "Audio: 纸飞机出手时的破风声（后期）；"
        "小女孩用力喊：飞喽——！"
    ),
)

# ── 镜 4 航拍跟拍纸飞机掠过校园（★ 校园展示镜，7s，T2V）──
TASKS[4] = dict(
    slug="paper_plane_over_campus", seed=9104,
    ref1=None, ref2=None, dur=7.0,
    prompt=(
        "CUT 1: 远景航拍跟拍镜头，画面前景是一架正在滑翔的白色纸飞机，"
        "镜头一路跟随它向前飞过学校校园：先掠过操场（**有学生在上体育课**），"
        "再穿过林荫道（**树影斑驳、阳光透过树叶**），接着掠过花坛（**花正开着**），"
        "最后飞向一栋教学楼四楼的窗口。四个地点依次呈现、每个约 1.5-2 秒，"
        "让观众看清校园的操场、林荫道、花坛与教学楼；"
        + LIGHT + "。镜头持续向前推进，画面持续变化、运动感强。\n"
        + NO_SPEECH
    ),
)

# ── 镜 5 纸飞机飞入教室被捏住（全景；窗外可见校园）──
TASKS[5] = dict(
    slug="zhang_shuyang_catches_plane", seed=9105,
    ref1=G_FOUR, ref2=SCENE_CLASS, dur=4.0,
    prompt=(
        "CUT 1: 全景镜头。一架白色纸飞机从教室的窗户飞进来，**窗外可见校园的一角（操场与树）**；"
        "窗内一位初中男生迅速伸出两根手指，在纸飞机掠过时把它稳稳捏住；"
        "**教室里另外三位同学都在画面里，安静地看着这一幕**；"
        "四人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那间午后的教室：米色课桌椅、蓝色墙报、明亮的窗户；"
        + LIGHT + "。镜头跟移着纸飞机从窗口进入教室，最后停在男生指间。\n"
        + NO_SPEECH
    ),
)

# ── 镜 6 张书扬举起纸飞机（★ 建立性格，5s）──
TASKS[6] = dict(
    slug="zhang_shuyang_shows_plane", seed=9106,
    ref1=G_FOUR, ref2=SCENE_CLASS, dur=5.0,
    prompt=(
        "CUT 1: 中近景镜头。一位初中男生用两根手指捏着白色纸飞机举到眼前，"
        "手腕左右晃了晃、头微微一歪、挑起一边眉毛，眼神在教室里扫了一圈、嘴角挂着得意又挑衅的笑；"
        "**身后和身旁还站着另外三位同学，他们看着他、不说话，只入画一部分**；"
        "四人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那间午后的教室，明亮的自然光；"
        + LIGHT + "。镜头轻微向前缓推（slow dolly in）。\n"
        "Audio: 教室午后的安静底噪（后期）；"
        "男生举着纸飞机、得意地问：谁扔的？是不是隔壁班暗恋我的？"
    ),
)

# ── 镜 7 刘思齐看书 / 徐畅景看他一眼（三人合影，镜 7） ──
TASKS[7] = dict(
    slug="xu_changjing_liu_siqi_glance", seed=9107,
    ref1=G_SIQI_ZHANG_XU, ref2=SCENE_CLASS, dur=3.0,
    prompt=(
        "CUT 1: 中景三人镜头，三人处于同一光照环境、是一个完整连续的空间："
        "左边一位戴细框眼镜的女生低头看书、**头也不抬**；"
        "中间那位男生举着纸飞机；右边一位男生侧过头，看了举纸飞机的男生一眼，"
        "表情是淡淡的不以为然；"
        "三人的面貌、发型、眼镜与服装严格照 <Picture 1>（**细框眼镜必须保留**）；"
        "背景是 <Picture 2> 那间午后的教室；"
        + LIGHT + "。固定机位，镜头轻微横移。\n"
        "Audio: 教室底噪、书页翻动声（后期）；"
        "右边的男生淡淡地说：你少自恋了。"
    ),
)

# ── 镜 8 刘思成拿过纸飞机放在桌角（中近景）──
TASKS[8] = dict(
    slug="liu_sicheng_takes_plane", seed=9108,
    ref1=G_FOUR, ref2=SCENE_CLASS, dur=3.0,
    prompt=(
        "CUT 1: 中近景镜头。一位戴细框眼镜的初中女生伸出手，把男生手里的纸飞机拿过来，"
        "随手放在课桌角上，动作自然；"
        "**身后和身旁还站着另外三位同学，他们看着她、只入画一部分**；"
        "四人的面貌、发型、眼镜与服装严格照 <Picture 1>（**细框眼镜必须保留**）；"
        "背景是 <Picture 2> 那间午后的教室；"
        + LIGHT + "。固定机位，镜头轻微下摇跟着她的手。\n"
        "Audio: 教室底噪、纸张轻响（后期）；"
        "女生说：别闹了别闹了，继续。"
    ),
)

# ── 镜 9 四人继续讨论（全景，序幕一收束）──
TASKS[9] = dict(
    slug="four_students_discussing", seed=9109,
    ref1=G_FOUR, ref2=SCENE_CLASS, dur=3.0,
    prompt=(
        "CUT 1: 全景镜头。四位初中生围在课桌旁继续讨论，"
        "有人低头翻书、有人比划着说话、有人靠在桌边听，纸飞机静静躺在桌角；"
        "四人都完整入画、处于同一个连续空间、四人之间的间距均匀；"
        "四人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那间午后的教室：米色课桌椅、蓝色墙报、明亮的窗户；"
        + LIGHT + "。镜头缓慢向后拉（slow dolly out），收束到四人。\n"
        + NO_SPEECH
    ),
)



# ────────────────────────────────────────────────────────────── ComfyUI 基础
def _api(path, payload=None):
    url = COMFY + path
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def load_workflow(name):
    with open(os.path.join(WORKFLOW_DIR, name), "r", encoding="utf-8") as f:
        return json.load(f)


def safe_name(path):
    """input 里用 ASCII 名（LESSONS #9）。"""
    return "act0v_" + re.sub(r"[^0-9A-Za-z_.-]", "_", os.path.basename(path))


def upload_image(local_path, target_name):
    """上传到 ComfyUI input；先删同名旧文件（LESSONS #6：上传不覆盖同名文件）。"""
    stale = os.path.join(COMFY_IN, target_name)
    if os.path.exists(stale):
        os.remove(stale)
    import mimetypes
    boundary = "----act0videos"
    with open(local_path, "rb") as f:
        content = f.read()
    ctype = mimetypes.guess_type(local_path)[0] or "image/png"
    body = b""
    body += ("--%s\r\n" % boundary).encode()
    body += ('Content-Disposition: form-data; name="image"; filename="%s"\r\n' % target_name).encode()
    body += ("Content-Type: %s\r\n\r\n" % ctype).encode()
    body += content + b"\r\n"
    body += ("--%s\r\n" % boundary).encode()
    body += b'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n'
    body += ("--%s--\r\n" % boundary).encode()
    req = urllib.request.Request(
        COMFY + "/upload/image", data=body,
        headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode("utf-8"))["name"]


def set_inputs(wf, class_type, **values):
    """按 class_type 注入参数（复刻 MCP 的 _set_inputs），返回命中数。"""
    hits = 0
    for node in wf.values():
        if node.get("class_type") == class_type:
            node.setdefault("inputs", {}).update(values)
            hits += 1
    return hits


def build_video_wf(task, ref1_name, ref2_name, megapixels, steps, prefix):
    """复刻 MCP video_minimax_h3_r2v / t2v 的注入逻辑。"""
    n_load = 0
    if task["ref1"] is not None:
        wf = load_workflow(WF_R2V)
        set_inputs(wf, "PrimitiveStringMultiline", value=task["prompt"])
        # LoadImage 节点：按 node id 升序 → ref_image_0 / ref_image_1
        load_nodes = sorted(
            (nid for nid, n in wf.items() if n.get("class_type") == "LoadImage"),
            key=lambda x: int(x))
        if len(load_nodes) >= 1:
            wf[load_nodes[0]]["inputs"]["image"] = ref1_name
        if len(load_nodes) >= 2:
            wf[load_nodes[1]]["inputs"]["image"] = ref2_name or ref1_name
        kind = "R2V"
        n_load = len(load_nodes)
    else:
        wf = load_workflow(WF_T2V)
        set_inputs(wf, "MiniMaxH3ImageToVideo", prompt=task["prompt"])
        kind = "T2V"

    # _apply_h3_common
    set_inputs(wf, "PrimitiveFloat", value=float(task["dur"]))
    set_inputs(wf, "RandomNoise", noise_seed=task["seed"])
    set_inputs(wf, "ResolutionSelector",
               aspect_ratio="16:9 (Widescreen)", megapixels=float(megapixels))
    set_inputs(wf, "BasicScheduler", steps=int(steps))
    set_inputs(wf, "SaveVideo", filename_prefix=prefix)
    return wf, kind, n_load


def wait_for(prompt_id, timeout):
    """轮询 /history 直到出现 outputs 或 error。返回 (entry, status)。"""
    t0 = time.time()
    last = ""
    while time.time() - t0 < timeout:
        try:
            h = _api("/history/" + prompt_id)
        except Exception:
            h = {}
        entry = h.get(prompt_id)
        if entry:
            st = (entry.get("status") or {}).get("status_str")
            if (entry.get("outputs") or st == "error") and st != "running":
                return entry, (st or "done")
        try:
            q = _api("/queue")
            run = len(q.get("queue_running") or [])
            pend = len(q.get("queue_pending") or [])
            line = " ... 运行中=%d 排队=%d  %.0f s" % (run, pend, time.time() - t0)
        except Exception:
            line = " ... %.0f s" % (time.time() - t0)
        if line != last:
            print(line, flush=True)
            last = line
        time.sleep(15)
    return None, "timeout"



def probe(path):
    """用 ffprobe 实测规格（LESSONS #7：不要相信注释里的分辨率）。"""
    exe = shutil.which("ffprobe") or "ffprobe"
    try:
        out = subprocess.run(
            [exe, "-v", "error", "-show_entries",
             "format=duration:stream=index,codec_type,codec_name,width,height,sample_rate,channels",
             "-of", "json", path],
            capture_output=True, text=True, timeout=60)
        if out.returncode != 0:
            return dict(error=(out.stderr or "")[:200])
        d = json.loads(out.stdout)
        info = {"duration": round(float(d["format"]["duration"]), 2), "kb": round(
            os.path.getsize(path) / 1024.0, 1)}
        for s in d.get("streams", []):
            if s.get("codec_type") == "video":
                info["w"] = s.get("width")
                info["h"] = s.get("height")
                info["vcodec"] = s.get("codec_name")
            elif s.get("codec_type") == "audio":
                info["acodec"] = s.get("codec_name")
                info["sr"] = s.get("sample_rate")
                info["ch"] = s.get("channels")
        return info
    except Exception as e:
        return dict(error=str(e)[:200])


def run_shot(shot, dry=False, megapixels=0.6, steps=20, timeout=3600):
    task = dict(TASKS[shot])
    # ★ 音频三层分工（README §4.4）：剔掉「音效：（后期）」，只把 L1 台词交给 H3
    task["prompt"] = strip_late_audio(task["prompt"])
    print("=" * 72)
    print("[镜 %d] %s | seed %d | 时长 %.0fs | %s" % (
        shot, task["slug"], task["seed"], task["dur"],
        "T2V（无角色）" if task["ref1"] is None else
        "R2V | <Picture 1> = %s" % os.path.basename(task["ref1"])))
    if dry:
        print("  ref2 = %s" % (os.path.basename(task["ref2"]) if task["ref2"] else "-"))
        print("  prompt = %s..." % task["prompt"][:70])
        return (shot, "DRY", "")

    ref1_name = ref2_name = None
    for key in ("ref1", "ref2"):
        p = task[key]
        if p is None:
            continue
        if not os.path.exists(p):
            print("  [X] 参考图不存在：%s" % p)
            return (shot, "MISSING_REF", p)
        nm = upload_image(p, safe_name(p))
        print("  %s 上传 -> %s" % (os.path.basename(p), nm))
        if key == "ref1":
            ref1_name = nm
        else:
            ref2_name = nm

    prefix = "act0vs20/%02d_%s" % (shot, task["slug"])
    wf, kind, n_load = build_video_wf(task, ref1_name, ref2_name,
                                      megapixels, steps, prefix)
    print("  注入：wf=%s kind=%s LoadImage节点=%d megapixels=%.2f steps=%d prompt字数=%d" % (
        WF_R2V if task["ref1"] is not None else WF_T2V, kind, n_load,
        megapixels, steps, len(task["prompt"])))

    t0 = time.time()
    try:
        r = _api("/prompt", {"prompt": wf, "client_id": CLIENT_ID})
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:900]
        print("  [X] 提交失败 %s\n%s" % (e.code, detail))
        return (shot, "SUBMIT_FAIL", detail[:200])
    pid = r["prompt_id"]
    print("  已提交 prompt_id=%s" % pid)

    entry, st = wait_for(pid, timeout=timeout)
    dt = time.time() - t0
    if entry is None:
        print("  [!] 等待超时（任务可能仍在跑）prompt_id=%s" % pid)
        return (shot, "TIMEOUT", pid)
    if st == "error":
        msg = json.dumps(entry.get("status", {}), ensure_ascii=False)[:600]
        print("  [X] 执行报错：%s" % msg)
        return (shot, "ERROR", msg[:200])

    files = []
    for node_out in entry.get("outputs", {}).values():
        for key in ("videos", "gifs", "images", "audio"):
            for it in node_out.get(key) or []:
                src = os.path.join(COMFY_OUT, it.get("subfolder", ""), it["filename"])
                if not os.path.exists(src):
                    continue
                dst = os.path.join(OUT_ROOT, it["filename"])
                shutil.copy2(src, dst)
                v = probe(dst)
                flag = "OK" if "error" not in v and v.get("w") else "SUSPECT"
                extra = ("%sx%s %s | %.2fs %s %sHz %sch | %.0fKB" % (
                    v.get("w"), v.get("h"), v.get("vcodec", "?"),
                    v.get("duration", -1), v.get("acodec", "无音轨"),
                    v.get("sr", "-"), v.get("ch", "-"), v.get("kb", 0))
                    ) if "error" not in v else v["error"]
                print("  [%s] %s  %s  %.0f s" % (flag, it["filename"], extra, dt))
                files.append((it["filename"], flag, extra))
    if not files:
        print("  [!] history 里没有输出文件（可能被中断）")
        return (shot, "NO_OUTPUT", pid)
    return (shot, files[0][1], "%s | %s" % (files[0][0], files[0][2]))


def main():
    args = sys.argv[1:]
    dry = "--dry" in args
    args = [a for a in args if not a.startswith("--")]
    # 本幕默认 10：镜 4（航拍跟拍）/ 镜 5（飞入窗）为环境剧变镜，建议单独 --steps=20；
    # 镜 2/3/7/8/9 静态或对话镜可 --steps=4 提速
    steps = 10
    mp = 0.6
    for a in sys.argv[1:]:
        if a.startswith("--steps="):
            steps = int(a.split("=", 1)[1])
        elif a.startswith("--mp="):
            mp = float(a.split("=", 1)[1])
    shots = [int(a) for a in args] if args else sorted(TASKS)
    print(">>> steps=%d megapixels=%.2f shots=%s" % (steps, mp, shots))

    os.makedirs(OUT_ROOT, exist_ok=True)
    report = []
    for shot in shots:
        try:
            row = run_shot(shot, dry=dry, megapixels=mp, steps=steps)
        except Exception as e:
            row = (shot, "EXCEPTION", repr(e)[:200])
            print("  [X] 异常：%r" % e)
        report.append(row)
        with open(REPORT, "w", encoding="utf-8") as f:
            f.write("序幕一《纸飞机》视频片段 · 生成报告（跳过首帧，直接 R2V/T2V，镜 1-9）\n")
            f.write("输出目录：%s\n\n" % OUT_ROOT)
            for s, st, fn in report:
                f.write("镜 %-2d\t%-12s\t%s\n" % (s, st, fn))

    print("=" * 72)
    print("汇总：")
    for s, st, fn in report:
        print("  镜 %-2d  %-12s %s" % (s, st, fn))
    print("报告：%s" % REPORT)


if __name__ == "__main__":
    main()
