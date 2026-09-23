# -*- coding: utf-8 -*-
"""生成《如愿·看见》四格漫画「幕后篇」的 4 格画面（4 小强一起策划/制作本片）。

## 为什么这么干（设计口径）

1. **底图用「成片自己的帧」**，不用定妆照拼版：
   · 帧是 **1056×608 = 1.7368**，与漫画格内画面区 **1.741** 只差 0.25% ⇒ **零裁切**；
     定妆照/合影是 2.68 甚至 6.02 的超宽条，图生图会**等比放大成同宽高比**，进格必被裁掉三成。
   · 底图里的人 **就是成片里那四位**（同一批脸、同一套校服、同一间八（1）班教室），
     `image_edit_longcat` 只改动作与道具、不动身份 —— 这正是 README §4.3 / §6.5 的用法。
2. **两张底图**（出处写进 `_gen_meta.json`）：
   · `镜 9`  白天教室，四人并排坐课桌后 → 格 1/2
   · `镜 121` 傍晚教室，四人围着笔记本 + 世界模型全息 → 格 3/4
3. **prompt 三件事**：① 声明「same four students, same faces as the reference photo」；
   ② 只描述**动作 / 桌上道具 / 视线**；③ 显式禁令「no text, no subtitles, no watermark」
   （H3/LongCat 都会把台词画成画面字幕，见 README §6.6 —— 漫画里台词走气泡，画面里不要字）。
4. **闸门**：生成后逐张过 `face_feature`，要求 `face_count ≥ 3` 且主脸 `face_px_h ≥ 55`
   —— 「脸被改掉 / 人变少了 / 脸太小」当场发现，不靠肉眼。

用法：
    py -3.10 OUTPUT/_make_making_panels.py            # 出全部 4 格（约 6–10 分钟）
    py -3.10 OUTPUT/_make_making_panels.py 3          # 只重出第 3 格
    py -3.10 OUTPUT/_make_making_panels.py --check    # 只跑闸门（看已生成的图）
产物：
    OUTPUT/comic/making/panel_1..4.png      ← 采用版（漫画排版直接吃这四个）
    OUTPUT/comic/making/_gen/               ← 生成器原始产物（留档，便于回滚/比对）
    OUTPUT/comic/making/_gen_meta.json      ← 底图/prompt/seed/脸检结果（复现凭据）
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

# ★ 与仓库其它脚本同一条纪律（README §6.8 #7）：Windows 控制台默认 GBK，
#   打印 `⇒` / `✅` 这类字符会抛 UnicodeEncodeError 并**让脚本在最后一步崩掉**（本次实测踩到）。
for _s in ("stdout", "stderr"):
    try:
        getattr(sys, _s).reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVER = ROOT / "mcp_server" / "comfyui_mcp_server.py"
MAKING = ROOT / "OUTPUT" / "comic" / "making"
META = MAKING / "_gen_meta.json"

# ★ 两张底图（成片帧缓存，抽帧口径见 `_make_comic.py` 的 `--at`）
BASE_9 = "OUTPUT/comic/frames/009.png"
BASE_121 = "OUTPUT/comic/frames/121.png"

KEEP = ("同一位四位初中生——严格照参考照片里的这四个人，面孔与校服一个字都不要改，"
        "画面里只有这四位学生，不要出现第五个人，背景里也不要有其他人，"
        "画面里不得出现任何可读的文字、字母、数字或符号，草稿纸与黑板保持空白，"
        "写实摄影质感，16:9")

NEGATIVE = ("different faces, changed faces, extra people, a fifth student, extra person, "
            "six people, crowd, duplicate person, background students, missing person, "
            "readable text, handwriting, letters, numbers, words, chalk writing, "
            "captions, subtitles, watermark, logo, cartoon, anime, "
            "deformed hands, distorted faces")


PANELS = [
    dict(
        n=1, base=BASE_9, seed=20261031,
        tag="策划 · 选题",
        prompt=("四位学生坐在同一排课桌后，四个人一起低头看摊在桌面上的稿纸，"
                "桌面上还放着几支荧光笔和一台打开的笔记本电脑，稿纸是空白的。"
                "四个人都在看同一张稿纸，画面里只有这四位学生、"
                "人数与参考照片完全一致，不要新增人物、也不要把某个人画两遍。"
                "中景，白天教室，窗光柔和。" + KEEP),
    ),
    dict(
        n=2, base=BASE_9, seed=20261032,
        tag="分工 · 核对史实",
        prompt=("四位学生坐在同一排课桌后，四个人一起凑在同一台笔记本电脑前看屏幕，"
                "旁边黑板上贴着几张彩色便签，便签上没有字、黑板也没有写字。"
                "画面里只有这四位学生、人数与参考照片完全一致，"
                "不要新增人物、也不要把某个人画两遍。全景，白天教室。" + KEEP),
    ),
    dict(
        n=3, base=BASE_121, seed=20260925,
        tag="训练世界模型",
        prompt=("傍晚的教室，一位男生坐在打开的笔记本电脑前敲键盘，"
                "屏幕上显示蓝紫色的世界模型训练界面（代码与曲线），"
                "另外三位学生凑在旁边一起看屏幕、神情专注，"
                "笔记本电脑屏幕的冷光照在他们脸上，窗外天色已暗。" + KEEP),
    ),
    dict(
        n=4, base=BASE_121, seed=20261014,
        tag="一起看成片",
        prompt=("傍晚的教室，四位初中生围在同一台笔记本电脑前一起看刚剪好的短片，"
                "画面里只有这四个人：笔记本电脑屏幕发出明亮的蓝白光、光打在四个人脸上，"
                "四个人都在笑、有人伸手指着屏幕，桌角放着一架纸飞机。"
                "画面里不要出现悬浮的全息物体。中景，暖黄教室灯光与屏幕冷光混合。" + KEEP),
    ),
]


def load_server():
    spec = importlib.util.spec_from_file_location("comfyui_mcp_server", SERVER)
    srv = importlib.util.module_from_spec(spec)
    sys.modules["comfyui_mcp_server"] = srv
    spec.loader.exec_module(srv)
    return srv


def as_json(res):
    return json.loads(res) if isinstance(res, str) else res


def face_gate(srv, path, min_faces=3, min_px=55):
    """过 `face_feature`：人数 3~4 + 主脸够大。

    ★ 上限也有意义：本片是**四小强**，画面里冒出第 5 张脸就是缺陷
      （只查"≥3"会漏掉，实测第 1 版就多长了一个人）。
    """
    d = as_json(srv.face_feature(paths=str(path), model_name="buffalo_l", provider="CPU",
                                 include_embedding=False, reembed_px=512, wait=True))
    fj = d.get("face_json") or {}
    ims = fj.get("images") or [{}]
    im0 = ims[0] if ims else {}
    n = im0.get("face_count", 0)
    faces = sorted(im0.get("faces", []), key=lambda f: -f.get("face_px_h", 0))
    px = faces[0].get("face_px_h", 0) if faces else 0
    return dict(face_count=n, max_face_px_h=px,
                ok=(min_faces <= n <= 4 and px >= min_px))


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    only = {int(a) for a in args} if args else None
    check_only = "--check" in sys.argv
    force = "--force" in sys.argv
    srv = load_server()
    MAKING.mkdir(parents=True, exist_ok=True)
    log = json.loads(META.read_text(encoding="utf-8")) if META.exists() else {}

    for p in PANELS:
        if only and p["n"] not in only:
            continue
        dst = MAKING / ("panel_%d.png" % p["n"])
        rec = dict(n=p["n"], tag=p["tag"], base=p["base"], seed=p["seed"], prompt=p["prompt"])
        # ★ 幂等：已生成的格默认**不重出**（要重出用 --force 或指定格号），
        #   否则一次崩溃就得把已完成的那几格全部白跑一遍。
        if not check_only and not force and dst.exists():
            print("[skip] 格 %d 已存在：%s（--force 可重出）" % (p["n"], dst.name))
        elif not check_only:
            base_abs = ROOT / p["base"].replace("/", "\\")
            if not base_abs.exists():
                print("[X] 底图不存在：%s" % base_abs)
                return 2
            print("\n=== 格 %d（%s）底图 %s seed=%d" % (p["n"], p["tag"], p["base"], p["seed"]))
            res = as_json(srv.image_edit_longcat(
                prompt=p["prompt"], image=str(base_abs), negative_prompt=NEGATIVE,
                seed=p["seed"], megapixels=2.07, steps=50, guidance=4.5, cfg=4.5,
                filename_prefix="comic_making/panel%d" % p["n"],
                output_dir=str(MAKING / "_gen"), wait=True, timeout_seconds=2400))
            if not res.get("ok"):
                print("[X] 生成失败：%s" % json.dumps(res, ensure_ascii=False)[:400])
                return 2
            files = res.get("files") or []
            if not files:
                print("[X] 无产物")
                return 2
            src = pathlib.Path(files[0]["path"])
            dst.write_bytes(src.read_bytes())
            from PIL import Image
            rec.update(gen_file=str(src), used_seed=res.get("seed"),
                       size=list(Image.open(str(src)).size))
            print("[gen] %s -> %s  %s" % (src.name, dst.name, rec["size"]))
        if dst.exists():
            g = face_gate(srv, dst)
            rec["face"] = g
            print("[gate] 格 %d：人数=%d 主脸高=%.0fpx ⇒ %s"
                  % (p["n"], g["face_count"], g["max_face_px_h"],
                     "OK" if g["ok"] else "!! 需复核（人少/脸小/脸被改）"))
        log[str(p["n"])] = rec

    META.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n元数据：%s" % META)
    bad = [k for k, v in log.items() if v.get("face") and not v["face"]["ok"]]
    if bad:
        print("⚠️ 需复核的格：%s" % bad)
        return 1
    print("✅ 四格全部通过脸闸门")
    return 0


if __name__ == "__main__":
    sys.exit(main())

