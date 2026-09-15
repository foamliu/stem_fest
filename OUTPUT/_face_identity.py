#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""人脸身份工具：检测 → 5 点对齐 → ArcFace embedding → 余弦相似度（**纯 CPU**，不占显存）。

★ 为什么需要它
    项目验收口径里「人脸像不像定妆照」过去只能靠**肉眼**（`_char_consistency.py` 拼并排图
    交给主模型看，而 README §4.1 说明读图**不可复现**）。本工具把它变成**可复现的数值**：
      · 检出脸数 / 每张脸的 **脸高 px**（对齐 README §4.2 的 250 px 口径）
      · ArcFace embedding 的 **余弦相似度**（本机实测：同人 ≈0.99、跨人 ≤0.21）
    顺带解决两个真实问题：
      ① 参考图「脸太小」——本机实测 41 张参考图里 **18 张**缩到 1 MP 后主脸 < 250 px；
      ② 逐镜漂移排查——镜帧 vs 该镜参考图打分，挑出低分镜重跑。

模型（**本机已就位，无需下载**）
    E:\\code\\ComfyUI\\models\\insightface\\models\\
      buffalo_l   \\det_10g.onnx(SCRFD 检测) + w600k_r50.onnx(ArcFace R50)
      antelopev2  \\scrfd_10g_bnkps.onnx      + glintr100.onnx(ArcFace R100)
    E:\\code\\ComfyUI\\models\\insightface\\inswapper_128.onnx（换脸模型，本工具不用）

运行环境（★ 会自动切换解释器，别被这点卡住）
    依赖 insightface / onnxruntime / cv2 —— **只有 ComfyUI 的 venv 里有**。
    脚本检测到当前解释器缺依赖时，会用 `E:\\code\\ComfyUI\\venv\\Scripts\\python.exe`
    **自动重跑自己**；可用环境变量 `COMFYUI_VENV_PYTHON` 覆盖。

用法
    py -3.10 OUTPUT/_face_identity.py detect IMG [IMG...] [--crops DIR] [--annotate DIR]
    py -3.10 OUTPUT/_face_identity.py compare A B
    py -3.10 OUTPUT/_face_identity.py check  PATH [PATH...]        # 批量体检（打印告警）
    py -3.10 OUTPUT/_face_identity.py audit  [--glob G]... [--json OUT] [--csv OUT]
    py -3.10 OUTPUT/_face_identity.py ledger --act 06_trench [--shots 19-46] [--from-video]

常用示例
    py -3.10 OUTPUT/_face_identity.py audit --glob "ASSETS/CHARACTERS/**/*.png" ^
            --json OUTPUT/_face_audit.json --csv OUTPUT/_face_audit.csv
    py -3.10 OUTPUT/_face_identity.py ledger --act 06_trench --csv OUTPUT/_face_ledger_trench.csv
"""
from __future__ import annotations

import argparse
import csv
import glob as globmod
import json
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT, "OUTPUT")
INSIGHTFACE_ROOT = r"E:\code\ComfyUI\models\insightface"
DEFAULT_VENV_PY = r"E:\code\ComfyUI\venv\Scripts\python.exe"
SHOT_REFS = os.path.join(OUTPUT_DIR, "_shot_refs.json")

DEFAULTS = dict(
    model="buffalo_l",          # buffalo_l（快、够用）/ antelopev2（R100，更强）
    same_thresh=0.5,            # >= 判为"像同一个人"（实测同人 0.985 / 跨人 <=0.21）
    review_thresh=0.35,         # 介于两者之间 = 人工复核区
    min_face_px=250,            # README §4.2 的脸高验收口径
    ref_mp=1.0,                 # 参考图换算口径：缩到 1 MP 后的脸高
)

# ══════════════════════════════════════════════════════════════════
# 解释器自举：当前解释器缺依赖时，自动改用 ComfyUI venv 的 python 重跑自己
# ══════════════════════════════════════════════════════════════════
def _runtime_ready() -> bool:
    try:
        import cv2  # noqa: F401
        import numpy  # noqa: F401
        import onnxruntime  # noqa: F401
        import insightface  # noqa: F401
        return True
    except Exception:
        return False


def _bootstrap() -> None:
    if _runtime_ready() or os.environ.get("FACE_IDENTITY_RELAUNCH") == "1":
        return
    venv_py = os.environ.get("COMFYUI_VENV_PYTHON") or DEFAULT_VENV_PY
    if not os.path.isfile(venv_py):
        sys.stderr.write(
            "[FATAL] 当前解释器缺 insightface/onnxruntime，且找不到 ComfyUI venv：\n"
            "        %s\n"
            "        解决：设置环境变量 COMFYUI_VENV_PYTHON 指向带 insightface 的 python。\n" % venv_py)
        raise SystemExit(3)
    env = dict(os.environ, FACE_IDENTITY_RELAUNCH="1")
    sys.stderr.write("[i] 当前解释器缺 insightface ⇒ 自动改用 %s\n" % venv_py)
    sys.exit(subprocess.run([venv_py, os.path.abspath(__file__), *sys.argv[1:]], env=env).returncode)


_bootstrap()

import cv2           # noqa: E402
import numpy as np   # noqa: E402
from insightface.app import FaceAnalysis  # noqa: E402

_APP_CACHE: dict = {}


def get_app(model: str = DEFAULTS["model"], det_size: int = 640):
    """加载（并缓存）FaceAnalysis；模型目录固定在 ComfyUI 的 insightface 目录。"""
    key = (model, det_size)
    if key not in _APP_CACHE:
        app = FaceAnalysis(name=model, root=INSIGHTFACE_ROOT,
                           providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=-1, det_size=(det_size, det_size))
        _APP_CACHE[key] = app
    return _APP_CACHE[key]


# ══════════════════════════════════════════════════════════════════
# 基础工具
# ══════════════════════════════════════════════════════════════════
def imread(path: str):
    """读图。cv2.imread 在 Windows 上读不了非 ASCII 路径 ⇒ 走 imdecode。"""
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError("读图失败：%s" % path)
    return img


def rel(path: str) -> str:
    try:
        return os.path.relpath(path, ROOT)
    except Exception:
        return path


def resolve(path: str) -> str:
    return path if os.path.isabs(path) else os.path.join(ROOT, path)


def is_portrait_ref(path: str) -> bool:
    """是不是"人像参考图"（定妆照 / 合影）；场景图、道具图不算。"""
    p = path.replace("\\", "/").lower()
    return "/assets/characters/" in p


def faces_of(img, app) -> list:
    """检出的人脸，按面积从大到小排序。"""
    fs = app.get(img)
    return sorted(fs, key=lambda f: -((f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1])))


def face_records(img, app) -> list:
    """每张脸的结构化记录（含"缩到 1 MP 后的脸高"换算）。"""
    h, w = img.shape[:2]
    mp = (w * h) / 1_000_000.0
    scale = (DEFAULTS["ref_mp"] / mp) ** 0.5 if mp > DEFAULTS["ref_mp"] else 1.0
    out = []
    for f in faces_of(img, app):
        x1, y1, x2, y2 = [int(v) for v in f.bbox]
        fh = y2 - y1
        out.append({
            "bbox": [x1, y1, x2, y2],
            "face_px": [x2 - x1, fh],
            "face_h_at_1mp": int(round(fh * scale)),
            "det_score": round(float(f.det_score), 3),
            "gender": int(f.gender) if f.gender is not None else None,   # 1=男 0=女（粗检）
            "age": int(f.age) if getattr(f, "age", None) is not None else None,
        })
    return out


def embeddings(img, app) -> list:
    """按人脸面积从大到小返回 L2 归一化的 512 维 ArcFace 向量。"""
    return [np.asarray(f.normed_embedding, dtype=np.float32) for f in faces_of(img, app)]


def best_cosine(emb_a: list, emb_b: list) -> tuple:
    """A 的全部脸 × B 的全部脸 取最大余弦（1:N 匹配）。返回 (分数, a_idx, b_idx)。"""
    best, ai, bi = None, None, None
    for i, ea in enumerate(emb_a):
        for j, eb in enumerate(emb_b):
            s = float(np.dot(ea, eb))
            if best is None or s > best:
                best, ai, bi = s, i, j
    return (round(best, 4) if best is not None else None), ai, bi


def verdict(score, same=DEFAULTS["same_thresh"], review=DEFAULTS["review_thresh"]) -> str:
    if score is None:
        return "NO_FACE"
    if score >= same:
        return "SAME"
    if score >= review:
        return "REVIEW"
    return "DIFFERENT"


def write_csv(path: str, rows: list) -> None:
    if not rows:
        return
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)


def write_json(path: str, obj) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def export_crops(img, faces, out_dir: str, tag: str) -> list:
    """导出 112×112 对齐人脸（ArcFace 标准输入），供人工/后续 embedding 复用。"""
    from insightface.utils import face_align
    os.makedirs(out_dir, exist_ok=True)
    files = []
    for i, f in enumerate(faces):
        crop = face_align.norm_crop(img, landmark=f.kps, image_size=112)
        p = os.path.join(out_dir, "%s_f%02d.jpg" % (tag, i))
        cv2.imwrite(p, crop)
        files.append(rel(p))
    return files


def annotate(img, faces, out_path: str) -> str:
    """画框图：框 + 序号 + 脸高 px + 检测分，方便肉眼复核。"""
    vis = img.copy()
    for i, f in enumerate(faces):
        x1, y1, x2, y2 = [int(v) for v in f.bbox]
        cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 220, 0), max(2, (y2 - y1) // 80))
        label = "#%d h=%dpx d=%.2f" % (i, y2 - y1, float(f.det_score))
        cv2.putText(vis, label, (x1, max(18, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, max(0.5, (y2 - y1) / 400.0),
                    (0, 220, 0), max(1, (y2 - y1) // 200))
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    cv2.imwrite(out_path, vis)
    return rel(out_path)


# ══════════════════════════════════════════════════════════════════
# 子命令：detect / compare / audit(check)
# ══════════════════════════════════════════════════════════════════
def cmd_detect(args) -> int:
    app = get_app(args.model)
    result = {"model": args.model, "images": []}
    for p in args.images:
        path = resolve(p)
        img = imread(path)
        h, w = img.shape[:2]
        faces = faces_of(img, app)
        rec = {
            "file": rel(path),
            "size": "%dx%d" % (w, h),
            "n_faces": len(faces),
            "faces": face_records(img, app),
        }
        if args.crops and faces:
            rec["crops"] = export_crops(img, faces, resolve(args.crops),
                                        os.path.splitext(os.path.basename(path))[0])
        if args.annotate:
            dst = os.path.join(resolve(args.annotate),
                               os.path.splitext(os.path.basename(path))[0] + "_faces.jpg")
            rec["annotated"] = annotate(img, faces, dst)
        result["images"].append(rec)
        hs = [f["face_px"][1] for f in rec["faces"]]
        print("%-48s %-10s faces=%d  face_h=%s  %s"
              % (rec["file"], rec["size"], rec["n_faces"], hs, rec.get("annotated", "")))
    if args.json:
        write_json(resolve(args.json), result)
    return 0


def cmd_compare(args) -> int:
    app = get_app(args.model)
    pa, pb = resolve(args.a), resolve(args.b)
    ia, ib = imread(pa), imread(pb)
    fa, fb = faces_of(ia, app), faces_of(ib, app)
    ea, eb = embeddings(ia, app), embeddings(ib, app)
    score, ai, bi = best_cosine(ea, eb)
    out = {
        "a": rel(pa), "b": rel(pb), "n_faces_a": len(fa), "n_faces_b": len(fb),
        "cosine": score, "verdict": verdict(score, args.same_thresh, args.review_thresh),
        "matched": {"a_index": ai, "b_index": bi},
        "faces_a": face_records(ia, app), "faces_b": face_records(ib, app),
    }
    print(json.dumps(out, ensure_ascii=False, indent=1))
    if args.json:
        write_json(resolve(args.json), out)
    return 0


def _audit_row(path: str, app) -> dict:
    img = imread(path)
    h, w = img.shape[:2]
    recs = face_records(img, app)
    hs = [r["face_px"][1] for r in recs]
    return {
        "file": rel(path),
        "size": "%dx%d" % (w, h),
        "mp": round(w * h / 1_000_000.0, 2),
        "n_faces": len(recs),
        "max_face_h": max(hs) if hs else 0,
        "min_face_h": min(hs) if hs else 0,
        "face_h_at_1mp": max([r["face_h_at_1mp"] for r in recs], default=0),
        "det_score": max([r["det_score"] for r in recs], default=None),
        "age_max": max([r["age"] for r in recs if r["age"] is not None], default=None),
        "aged_like": max([r["age"] for r in recs if r["age"] is not None], default=None),
    }


def cmd_audit(args, verbose: bool = True) -> int:
    app = get_app(args.model)
    paths = [resolve(p) for p in (args.paths or [])]
    for g in (args.globs or []):
        paths += sorted(globmod.glob(resolve(g), recursive=True))
    if not paths:
        sys.stderr.write("[ERROR] 没给路径：用 --paths 或 --glob\n")
        return 2
    t0 = time.time()
    rows = []
    for p in paths:
        try:
            rows.append(_audit_row(p, app))
        except Exception as e:
            rows.append({"file": rel(p), "error": str(e)})
    bad = [r for r in rows if not r.get("error")
           and (r["n_faces"] == 0 or r["face_h_at_1mp"] < args.min_face_px)]
    bad.sort(key=lambda r: r.get("face_h_at_1mp", -1))
    if verbose:
        print("体检 %d 张，用时 %.1fs，阈值：1MP 后脸高 >= %d px 且 >=1 张脸"
              % (len(rows), time.time() - t0, args.min_face_px))
        for r in bad:
            flag = "NO_FACE" if r["n_faces"] == 0 else "SMALL  "
            print("  %s %-50s %-10s %4.2fMP faces=%d 原%4dpx → 1MP后%4dpx"
                  % (flag, r["file"], r["size"], r["mp"], r["n_faces"],
                     r["max_face_h"], r["face_h_at_1mp"]))
        print("  ⇒ 不合格 %d / %d" % (len(bad), len(rows)))
    if args.json:
        write_json(resolve(args.json),
                   {"model": args.model, "min_face_px": args.min_face_px, "rows": rows})
    if args.csv:
        write_csv(resolve(args.csv), [r for r in rows if not r.get("error")])
    return 1 if (bad and args.strict) else 0


# ══════════════════════════════════════════════════════════════════
# 子命令：ledger（逐镜打分台账）
# ══════════════════════════════════════════════════════════════════
SHOT_RE = re.compile(r"^(\d+)_")


def _latest(files: list) -> str:
    """同一镜多版本时取最新：先比文件名里的 `_NNNNN_` 版本号，再比 mtime。"""
    def key(p):
        m = re.search(r"_(\d{5})_?\.[A-Za-z]+$", os.path.basename(p))
        return (int(m.group(1)) if m else -1, os.path.getmtime(p))
    return max(files, key=key)


def probe_duration(path: str) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return 0.0
    try:
        r = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", path], capture_output=True, text=True)
        return float((r.stdout or "").strip())
    except Exception:
        return 0.0


def extract_mid_frame(video: str, dst: str) -> str:
    """没抽过帧时用 ffmpeg 取片中点帧（兜底，不必为此重跑 ComfyUI）。"""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("系统里找不到 ffmpeg")
    dur = probe_duration(video)
    t = max(0.0, dur * 0.5) if dur > 0 else 1.0
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    subprocess.run([ffmpeg, "-y", "-v", "error", "-ss", "%.3f" % t, "-i", video,
                    "-frames:v", "1", "-q:v", "2", dst], capture_output=True)
    if not os.path.isfile(dst) or os.path.getsize(dst) == 0:
        raise RuntimeError("抽帧失败：%s" % video)
    return dst


def parse_shots(spec: str) -> list:
    """`19-46,52` → [19..46, 52]；空串 → []。"""
    out = []
    for part in (spec or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def shot_files(dirpath: str, n: int) -> list:
    """该镜的产物文件。

    兼容两种命名：帧图是**两位零填充**（`01_school_gate_...png`），
    而视频/其他产物可能是 `1_xxx.mp4` 或 `75_zhong_...mp4`。
    """
    if not os.path.isdir(dirpath):
        return []
    pat = re.compile(r"^0*%d_" % n)
    return [os.path.join(dirpath, f) for f in sorted(os.listdir(dirpath))
            if pat.match(f) and os.path.isfile(os.path.join(dirpath, f))]


def cmd_ledger(args) -> int:
    app = get_app(args.model)
    act_dir = os.path.join(OUTPUT_DIR, args.act)
    frames_dir = os.path.join(act_dir, "frames")
    video_dir = os.path.join(act_dir, "video")
    fallback_dir = os.path.join(act_dir, "frames_facecheck")
    if not os.path.isdir(act_dir):
        sys.stderr.write("[ERROR] 找不到幕目录：%s\n" % act_dir)
        return 2
    try:
        with open(SHOT_REFS, encoding="utf-8") as f:
            refs_all = json.load(f)
    except Exception as e:
        sys.stderr.write("[ERROR] 读不了 %s：%s\n（先跑 py -3.10 OUTPUT/_shot_refs.py）\n"
                         % (rel(SHOT_REFS), e))
        return 2

    if args.shots:
        shots = parse_shots(args.shots)
    else:
        found = set()
        for d in (frames_dir, video_dir):
            for p in globmod.glob(os.path.join(d, "*")):
                m = SHOT_RE.match(os.path.basename(p))
                if m:
                    found.add(int(m.group(1)))
        shots = sorted(found)
    if not shots:
        sys.stderr.write("[ERROR] %s 下没找到任何镜的产物\n" % rel(act_dir))
        return 2

    emb_cache: dict = {}

    def emb_of(path: str):
        if path not in emb_cache:
            emb_cache[path] = embeddings(imread(path), app)
        return emb_cache[path]

    rows = []
    for n in shots:
        rec = {"shot": n, "frame": "", "ref": "", "cosine": None,
               "verdict": "NO_FRAME", "frame_n_faces": 0, "frame_face_h": 0,
               "refs_checked": 0}
        cands = shot_files(frames_dir, n)
        if not cands and args.from_video:
            vids = shot_files(video_dir, n)
            if vids:
                vid = _latest(vids)
                dst = os.path.join(fallback_dir, "%d_mid.jpg" % n)
                try:
                    extract_mid_frame(vid, dst)
                    cands = [dst]
                    rec["note"] = "frame from " + os.path.basename(vid)
                except Exception as e:
                    rec["note"] = "抽帧失败：%s" % e
        if cands:
            frame = _latest(cands)
            rec["frame"] = rel(frame)
            img = imread(frame)
            frecs = face_records(img, app)
            rec["frame_n_faces"] = len(frecs)
            rec["frame_face_h"] = frecs[0]["face_px"][1] if frecs else 0
            fe = embeddings(img, app)
            if not fe:
                rec["verdict"] = "NO_FACE"
            else:
                refs = [r for r in (refs_all.get(str(n), {}).get("refs") or [])
                        if is_portrait_ref(r)]
                rec["refs_checked"] = len(refs)
                best, best_ref = None, ""
                for r in refs:
                    rp = resolve(r)
                    if not os.path.isfile(rp):
                        continue
                    s, _, _ = best_cosine(emb_of(rp), fe)
                    if s is not None and (best is None or s > best):
                        best, best_ref = s, os.path.basename(rp)
                rec["ref"] = best_ref
                rec["cosine"] = best
                # 画面里有人脸、但该镜本来就没有"人像参考图"（纯空镜/道具镜）
                # ⇒ 不算不一致，单列 NO_REF，避免误报成 NO_FACE。
                rec["verdict"] = verdict(best, args.same_thresh, args.review_thresh) \
                    if refs else "NO_REF"
        rows.append(rec)

    rows.sort(key=lambda r: (r["cosine"] is None, r["cosine"] or 1.0))
    counts: dict = {}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    if not args.quiet:
        print("幕 %s：%d 镜　%s" % (args.act, len(rows),
                                   "  ".join("%s=%d" % kv for kv in sorted(counts.items()))))
        print("最可疑 %d 镜（cosine 升序）：" % min(args.top, len(rows)))
        for r in rows[:args.top]:
            print("  镜 %-4s %-9s cos=%-7s frame_face_h=%-5s faces=%-2s ref=%s"
                  % (r["shot"], r["verdict"], r["cosine"], r["frame_face_h"],
                     r["frame_n_faces"], r["ref"]))
    if not args.no_write:
        oj = resolve(args.json or os.path.join(OUTPUT_DIR, "_face_ledger_%s.json" % args.act))
        oc = resolve(args.csv or os.path.join(OUTPUT_DIR, "_face_ledger_%s.csv" % args.act))
        write_json(oj, {"act": args.act, "model": args.model,
                        "same_thresh": args.same_thresh, "rows": rows})
        write_csv(oc, rows)
        print("→ %s / %s" % (rel(oj), rel(oc)))
    return 0


# ══════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="_face_identity.py",
        description="人脸身份工具：检测 / 对齐 / ArcFace embedding / 余弦相似度（CPU）",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)

    # 公共参数放在 parents 里 ⇒ 写在子命令**之后**也能识别
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--model", default=DEFAULTS["model"],
                        choices=["buffalo_l", "antelopev2"], help="识别模型档位")
    common.add_argument("--same-thresh", type=float, default=DEFAULTS["same_thresh"],
                        help=">= 判为同一人（默认 %.2f）" % DEFAULTS["same_thresh"])
    common.add_argument("--review-thresh", type=float, default=DEFAULTS["review_thresh"],
                        help=">= 判为人工复核区（默认 %.2f）" % DEFAULTS["review_thresh"])
    common.add_argument("--min-face-px", type=int, default=DEFAULTS["min_face_px"],
                        help="脸高验收阈值 px（默认 %d）" % DEFAULTS["min_face_px"])
    common.add_argument("--json", default=None, help="结果另存 JSON")
    common.add_argument("--csv", default=None, help="结果另存 CSV（utf-8-sig，Excel 友好）")

    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("detect", parents=[common], help="检测人脸（可导出对齐裁剪 / 标注图）")
    p.add_argument("images", nargs="+", help="图片路径（相对项目根或绝对路径）")
    p.add_argument("--crops", default=None, help="把 112×112 对齐人脸导出到该目录")
    p.add_argument("--annotate", default=None, help="把带框图导出到该目录")
    p.set_defaults(func=cmd_detect)

    p = sub.add_parser("compare", parents=[common], help="两张图的人脸相似度（1:N 取最大）")
    p.add_argument("a", help="图 A")
    p.add_argument("b", help="图 B")
    p.set_defaults(func=cmd_compare)

    for name, helptext in (("check", "批量体检并打印告警（供 _make_group.py 调用）"),
                           ("audit", "批量体检（同 check，可另存 JSON/CSV）")):
        p = sub.add_parser(name, parents=[common], help=helptext)
        p.add_argument("paths", nargs="*", help="图片路径（可多个）")
        p.add_argument("--glob", dest="globs", action="append", default=[],
                       help="通配（可重复，支持 **）")
        p.add_argument("--strict", action="store_true", help="有不合格就返回码 1")
        p.set_defaults(func=cmd_audit)

    p = sub.add_parser("ledger", parents=[common], help="逐镜打分台账（镜帧 vs 该镜参考图）")
    p.add_argument("--act", required=True, help="幕目录名，如 06_trench / 01_paper_plane")
    p.add_argument("--shots", default="", help="镜号，如 19-46,52；留空 = 扫目录")
    p.add_argument("--from-video", action="store_true", help="没抽过帧时用 ffmpeg 抽中点帧")
    p.add_argument("--top", type=int, default=15, help="打印最可疑的前 N 镜（默认 15）")
    p.add_argument("--quiet", action="store_true", help="不打印明细")
    p.add_argument("--no-write", action="store_true", help="不写 JSON/CSV")
    p.set_defaults(func=cmd_ledger)

    return ap


def main() -> int:
    try:
        # 后台 `Start-Process ... > log` 时 Python 默认块缓冲 ⇒ 进度看不到；
        # 开行缓冲后长任务（体检/台账）能实时落盘，便于轮询。
        sys.stdout.reconfigure(line_buffering=True)
        sys.stderr.reconfigure(line_buffering=True)
    except Exception:
        pass
    args = build_parser().parse_args()
    t0 = time.time()
    rc = args.func(args)
    print("[done] %.1fs" % (time.time() - t0), file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main())
