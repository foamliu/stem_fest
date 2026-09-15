# -*- coding: utf-8 -*-
"""序幕二《启动》视频批量生成（镜 10-21）—— 跳过首帧，直接「人物参考图 + 场景图」喂 H3 R2V。

台词与镜号严格取自 `storyboard.md` §序幕二：启动（约 45 秒，八（1）班教室，傍晚 6 点天还亮）。

路线（与序幕一一致，README §7）：
  · 有角色的镜 → `video_minimax_h3_r2v`
      ref_image_1 = 角色/合影参考图 → `<Picture 1>`
      ref_image_2 = `SCENES/04_classroom_dusk/classroom_dusk_wide_v01.png` → `<Picture 2>`
        （傍晚 6 点教室，**暖金色天光 + 蓝紫冷光**）

★ 参考图纪律（2026-09-13 修正 —— 用户反馈「说话时背景没人了」）：
  **多人场景（同一空间）里的「单人说话镜」，参考图不能只给说话人一张脸** ——
  H3 只能从参考图认识「画面里有谁」，只给一个人 ⇒ 其余人凭空消失、变成一个人对着空教室说话。
  ⇒ **统一改喂四小强合影 `four_students_hero_v02.png`**，prompt 里写明
    「**身后和身旁还站着另外三位同学，他们安静看着、不说话，只入画一部分**」。
  仅「面部特写（close-up）」镜例外 —— 特写下旁人本就不该入画。

⚠️ 命名说明（2026-09-13 删「Ouch 梗」后重排）：
  旧镜 18、19（Ouch 第一次 / 张书扬学她）已删除，**全片 131 镜 → 129 镜**，
  旧 20-131 整体前移 2 位。本幕由 11 镜变为 **9 镜（10-18）**。
  映射表见 `OUTPUT/_renumber_after_ouch.py`（旧号 → 新号）。

★ 本幕的关键戏剧点：
  · 镜 16 是「科技之星」旧事收尾（张书扬吃瘪，不解释）
  · 镜 18 白光吞没教室 = 转场到第一幕

⚠️ steps 选择（README §7「steps 选择」表）：
   ★ 2026-09-13 用户指令：**本幕用 steps=20 重做**（含镜 10）—— 属"加步数追求质量"的重跑，
     接受 ≈18–26 分钟/条（0.6MP）。默认值已改为 **20**。

用法：
    py -3.10 OUTPUT/_diag_act2_startup.py --dry                 # 只看任务清单
    py -3.10 OUTPUT/_diag_act2_startup.py                      # 全量（steps=20）
    py -3.10 OUTPUT/_diag_act2_startup.py 10 11                 # 指定镜
"""
import json
import os
import re
import subprocess
import sys
import time
import shutil
import urllib.request

ROOT = r"E:\code\stem_fest"
COMFY = "http://127.0.0.1:8188"
COMFY_OUT = r"E:\code\ComfyUI\output"
COMFY_IN = r"E:\code\ComfyUI\input"
WORKFLOW_DIR = os.path.join(ROOT, "workflows")
OUT_ROOT = os.path.join(ROOT, "OUTPUT", "04_classroom_dusk", "video")
REPORT = os.path.join(ROOT, "OUTPUT", "_act2_startup_report.txt")
CLIENT_ID = "act2v_startup"

FRAMES = os.path.join(ROOT, "ASSETS", "CHARACTERS")
SCENES = os.path.join(ROOT, "ASSETS", "SCENES")

WF_R2V = "video_minimax_h3_r2v.json"
WF_T2V = "video_minimax_h3_t2v.json"

# 序幕二统一光线基调（storyboard：傍晚 6 点，天还亮着，暖金色天光 + 蓝紫冷光）
LIGHT = (
    "八（1）班教室，6 月底傍晚 6 点、天还亮着；暖金色天光从右侧窗户斜射进来，"
    "与全息设备发出的蓝紫色冷光交叠，画面是暖金与蓝紫的对比色调、层次分明"
)

SCENE = os.path.join(SCENES, "04_classroom_dusk", "classroom_dusk_wide_v01.png")

# ── 角色参考图 ────────────────────────────────────────────
P_LIU_SIQI = os.path.join(FRAMES, "01_liu_siqi", "liu_siqi_hero_v01.png")
P_LIU_SICHENG = os.path.join(FRAMES, "02_liu_sicheng", "liu_sicheng_hero_v01.png")
P_XU = os.path.join(FRAMES, "03_xu_changjing", "xu_changjing_hero_v01.png")
P_ZHANG = os.path.join(FRAMES, "04_zhang_shuyang", "zhang_shuyang_hero_v01.png")
G_FOUR = os.path.join(FRAMES, "_group", "four_students_hero_v02.png")
G_SICHENG_ZHANG = os.path.join(FRAMES, "_group", "liu_sicheng_zhang_shuyang_hero_v01.png")

# ── 道具参考图（设备特写镜用 R2V + 道具图当 <Picture 1>）──
P_HOLO_DEVICE = os.path.join(ROOT, "ASSETS", "PROPS", "02_holo_device", "holo_device_hero_v01.png")
P_HOLO_SCREEN = os.path.join(ROOT, "ASSETS", "PROPS", "03_holo_screen", "holo_screen_hero_v01.png")

# 无台词镜的通用禁语音后缀（2026-09-13 按 README §4.4 重写）
NO_SPEECH = (
    "Audio: 安静的室内环境底噪；衣料摩擦声与呼吸声；"
    "远处模糊的人声杂音，听不清任何词句。"
)

# ★ 音频三层分工（README §4.4）：带「（后期）」的音效不进 H3 prompt，由 ace_step_t2audio 后期铺。
LATE_MARK = "（后期）"


def strip_late_audio(text):
    """把「…（后期）」这类后期音效从句子里剔除，只留 L1 台词给 H3。

    句子边界 = `；` `。` 或换行；含 LATE_MARK 的那句整句丢掉。

    ★ 2026-09-16 关键修复（去字幕泄漏，README §6.6b）：
      旧实现切句后 **无条件 join**，把 `\n` 段落分隔符一起吃掉 ⇒ 多行 prompt
      被压成一行，禁令句与台词**粘连**，H3 便把台词当画面字幕渲染
      （镜 14 实测：改 prompt 后 8/8 帧仍泄漏）。
      现改为 **按行处理、保留换行**：行内含 LATE_MARK 的句子才丢，`\n` 一律保留。
    """
    import re as _re
    lines = []
    for line in text.split("\n"):
        kept = [s for s in _re.split(r"(?<=[；。])", line) if LATE_MARK not in s]
        lines.append("".join(kept))
    return "\n".join(lines).strip()

TASKS = {}


TASKS[10] = dict(
    slug="four_before_holo_device", seed=9600,
    ref1=G_FOUR, ref2=SCENE, dur=6.0,
    prompt=(
        "CUT 1: 中景四人镜头。四位初中生围站在课桌旁一台银灰色全息设备前，"
        "设备上方悬浮着淡蓝色光幕；四人都看着设备，其中一人（画面左侧、戴细框眼镜的女生）"
        "正微微侧头看向另外三人，嘴唇微启、明显正在说出一句话；"
        "四人的面貌、发型、眼镜与服装严格照 <Picture 1>（戴细框眼镜的人必须保留眼镜）；"
        "背景是 <Picture 2> 那间傍晚的教室：米色课桌椅、蓝色墙报、右侧窗户；"
        + LIGHT + "。镜头轻微向前缓推（slow dolly in）。\n"
        "Audio: 教室安静底噪、窗外最后几声蝉鸣，以及全息设备低沉的电流嗡鸣（后期）；"
        "戴眼镜的女生平静地问：准备好了吗？"
    ),
)

TASKS[11] = dict(
    slug="xu_taps_holo_screen", seed=9611,
    ref1=G_FOUR, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 近景半身镜头。一位初中男生抬右手，用指尖在半空中的淡蓝色全息光幕上轻点三下；"
        "每点一下，光幕上就浮现出一个发光的坐标标记（共三个，依次亮起）；"
        "身后和身旁还站着另外三位同学，他们安静地看着光幕、不说话，只入画一部分；"
        "四人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那间傍晚的教室，暖金色天光与蓝紫冷光交叠；"
        + LIGHT + "。镜头轻微向前缓推（slow dolly in）跟着他的手指。\n"
        "Audio: 全息界面被点触的清脆电子音，三声（后期）；"
        "男生语速平稳地念出：上甘岭、安江农校、高铁餐车。"
    ),
)

TASKS[12] = dict(
    slug="zhang_slides_finger_on_screen", seed=9612,
    ref1=G_FOUR, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 近景半身镜头。一位初中男生伸出食指在半空中的淡蓝色全息光幕上随手划过，"
        "头微微歪着、表情带着一点故意找茬的狡黠和玩味；"
        "身后和身旁还站着另外三位同学，他们安静看着、不说话，只入画一部分；"
        "四人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那间傍晚的教室，暖金色天光与蓝紫冷光交叠；"
        + LIGHT + "。镜头轻微横移（slow lateral move）。\n"
        "Audio: 教室底噪与光幕的轻微电流声（后期）；男生用略带挑衅的语气问：会不会被当成间谍抓起来？"
    ),
)

TASKS[13] = dict(
    slug="xu_does_not_look_up", seed=9613,
    ref1=G_FOUR, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 近景半身镜头。一位初中男生低着头继续看手里的全息操作、头也不抬，"
        "嘴角有一点不以为然的淡漠，语气平淡地回了一句；"
        "身后和身旁还站着另外三位同学，他们安静看着、不说话，只入画一部分；"
        "四人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那间傍晚的教室，暖金色天光与蓝紫冷光交叠；"
        + LIGHT + "。镜头轻微横移（slow lateral move）。\n"
        "Audio: 教室底噪（后期）；男生头也不抬地淡淡说：你少说两句就不会。"
    ),
)

TASKS[14] = dict(
    slug="zhang_defends_himself", seed=9614,
    ref1=G_FOUR, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 近景半身镜头。一位初中男生嘴硬地找补，抬着下巴、表情有点不服气又有点心虚，"
        "一只手还搭在全息光幕边上；"
        "身后和身旁还站着另外三位同学，他们安静看着、不说话，只入画一部分；"
        "四人的面貌、发型与服装严格照 <Picture 1>；"
        "背景是 <Picture 2> 那间傍晚的教室，暖金色天光与蓝紫冷光交叠；"
        + LIGHT + "。镜头轻微向前缓推（slow dolly in）。\n"
        "★ 全画面不得出现任何可读的文字、字幕或符号。\n"
        "Audio: 教室底噪（后期）；男生嘴硬地说：我上次竞选科技之星，就输在少说了两句。"
    ),
)

TASKS[15] = dict(
    slug="liu_siqi_hits_the_mark", seed=9615,
    ref1=G_FOUR, ref2=SCENE, dur=5.0,
    prompt=(
        "CUT 1: 近景半身镜头。一位戴细框眼镜的初中女生神情冷淡，眼睛看着桌面、没有看说话的人，"
        "一针见血地轻声说了一句、说完嘴角几乎不可察地一挑（带一点不给他留面子的笑意）；"
        "身后和身旁还站着另外三位同学，他们安静看着、不说话，只入画一部分；"
        "四人的面貌、发型、眼镜与服装严格照 <Picture 1>（细框眼镜必须保留）；"
        "背景是 <Picture 2> 那间傍晚的教室，暖金色天光与蓝紫冷光交叠；"
        + LIGHT + "。镜头轻微横移（slow lateral move）。\n"
        "Audio: 教室安静底噪（后期）；女生冷淡地说：谁叫你以为自己一定赢的？哈哈。"
    ),
)

TASKS[16] = dict(
    slug="zhang_stuck_sicheng_smirks", seed=9616,
    ref1=G_SICHENG_ZHANG, ref2=SCENE, dur=2.0,
    prompt=(
        "CUT 1: 中景双人镜头，两位初中生并排站在课桌旁、处于同一光照环境、"
        "画面是一个完整连续的空间：左边那位（男生）被噎住、张了张嘴没说出话，"
        "表情吃瘪、嘴唇动了一下就把话咽了回去；右边那位（戴细框眼镜的女生）嘴角向上扬了一下、忍着笑别过头去；"
        "两人的面貌、发型、眼镜与服装严格照 <Picture 1>（眼镜必须保留）；"
        "背景是 <Picture 2> 那间傍晚的教室，暖金色天光与蓝紫冷光交叠；"
        + LIGHT + "。镜头轻微横移（slow lateral move）。\n"
        "Audio: 教室底噪（后期）；男生只发出一声被噎住的短促气音、没有说出台词。"
        + NO_SPEECH
    ),
)

TASKS[17] = dict(
    slug="sicheng_hand_pinched", seed=9617,
    ref1=G_FOUR, ref2=SCENE, dur=3.0,
    prompt=(
        "CUT 1: 近景半身镜头。一位戴细框眼镜的初中女生把手伸向课桌上那台银灰色全息设备，"
        "手指刚碰到设备边缘就被轻轻夹了一下，她下意识地一缩手、"
        "同时把话题拉回正题，表情是「说到正事」的认真；"
        "身后和身旁还站着另外三位同学，他们安静看着、不说话，只入画一部分；"
        "四人的面貌、发型、眼镜与服装严格照 <Picture 1>（细框眼镜必须保留）；"
        "背景是 <Picture 2> 那间傍晚的教室，暖金色天光与蓝紫冷光交叠；"
        + LIGHT + "。镜头轻微向前缓推（slow dolly in）。\n"
        "Audio: 教室底噪，以及设备夹到手指的一声轻微「咔」（后期）；"
        "女生说：我查过了，只能看不能碰。"
    ),
)

TASKS[18] = dict(
    slug="sicheng_presses_start_button", seed=9621,
    ref1=G_FOUR, ref2=SCENE, dur=4.0,
    prompt=(
        "CUT 1: 近景半身镜头。一位戴细框眼镜的初中女生伸出手，"
        "按下课桌上那台银灰色全息设备中央的启动键；按键亮起，"
        "紧接着一圈刺眼的白光从设备处爆发、迅速扩散吞没整个教室 —— "
        "画面的最后，白光过曝、教室里的一切都被白色淹没；"
        "她的面貌、发型、眼镜与服装严格照 <Picture 1>（细框眼镜必须保留）；"
        "背景是 <Picture 2> 那间傍晚的教室，暖金色天光与蓝紫冷光交叠；"
        + LIGHT + "。镜头轻微向前缓推（slow dolly in），结尾被白光完全覆盖。\n"
        "Audio: 教室底噪与蝉鸣在白光亮起的瞬间戛然而止（一切声音突然静止）（后期），"
        "只剩设备的低频震动；女生平静而坚定地说：那就——出发。"
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
    return "act2v_" + re.sub(r"[^0-9A-Za-z_.-]", "_", os.path.basename(path))


def upload_image(local_path, target_name):
    """上传到 ComfyUI input；先删同名旧文件（LESSONS #6：上传不覆盖同名文件）。"""
    stale = os.path.join(COMFY_IN, target_name)
    if os.path.exists(stale):
        os.remove(stale)
    import mimetypes
    boundary = "----act1videos"
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
        # LoadImage 节点：137 → ref_image_0，139 → ref_image_1（按 node id 升序）
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


def run_shot(shot, dry=False, megapixels=0.6, steps=10, timeout=3600):
    """steps 按镜头类型选（见 README §7「steps 选择」）：
    静态/单人/对话镜 4；角色镜抽卡 10（本幕默认）；环境剧变镜（航拍/大范围运动）20。"""
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

    prefix = "act2vs20/%02d_%s" % (shot, task["slug"])
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
    # --steps=N / --mp=X 可选覆盖
    # ★ 2026-09-13 用户指令：本幕用 **20 步**重做（含镜 10 重做）
    steps = 20
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
            f.write("序幕二《启动》视频片段 · 生成报告（跳过首帧，直接 R2V，镜 10-21）\n")
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

