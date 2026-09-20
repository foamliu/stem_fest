# -*- coding: utf-8 -*-
"""黄继光 50 式冬装改图 · 多图工作流直跑（2026-09-20）。

为什么不用 MCP 的 `image_edit_longcat`：它是**单图输入**（工作流里只有 1 个
`LoadImage` → `ImageScaleToTotalPixels`），模型看不到 50 式军装参考图，
只能靠文字瞎编 —— 实测两轮都"关了帽徽又画出帽徽"。

本脚本改跑 `workflows/image_edit_longcat_2ref.json`（节点 `201`/`203` 两张图
一起进 `TextEncodeQwenImageEditPlus`），并把**布局基准图设为参考拼版本身**
⇒ 输出就是"定妆照 × 目标服装"的中间态，再靠 prompt 描述"单张全身正视图"
把它往单张全身照方向拉（注意：Qwen-Image-Edit 对"重新排版"类指令较弱，
一次不成需要后续用独立 T2I/换装重做，详见 README §6.10.17）。

用法：
    py -3.10 OUTPUT/_run_hj_50shi.py --tag v03 [--seed 20261022]
        [--guidance 4.5] [--steps 50] [--cfg 4.5] [--megapixels 1.0]
        [--plate in/plate.png] [--target in/hj_crop.png]
        [--negative "..."] [--prompt-file path]
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMFY = "http://127.0.0.1:8188"
WF = os.path.join(ROOT, "workflows", "image_edit_longcat_2ref.json")
OUT_DIR = os.path.join(ROOT, "OUTPUT", "uniform_50shi")

sys.path.insert(0, os.path.join(ROOT, "OUTPUT"))
from _hj50_prompts import NEGATIVE, PROMPTS  # noqa: E402

DEFAULT_PROMPT = PROMPTS["full_body"]
DEFAULT_NEGATIVE = NEGATIVE


def upload(local_path, target_name):
    """上传到 ComfyUI input（multipart，overwrite=true 覆盖同名旧文件）。"""
    with open(local_path, "rb") as f:
        data = f.read()
    boundary = "----hj" + uuid.uuid4().hex
    body = b""
    body += ("--%s\r\n" % boundary).encode()
    body += ('Content-Disposition: form-data; name="image"; filename="%s"\r\n'
             % target_name).encode()
    body += b"Content-Type: image/png\r\n\r\n"
    body += data + b"\r\n"
    body += ("--%s\r\n" % boundary).encode()
    body += b'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n'
    body += ("--%s--\r\n" % boundary).encode()

    req = urllib.request.Request(
        COMFY + "/upload/image", data=body,
        headers={"Content-Type": "multipart/form-data; boundary=%s" % boundary})
    with urllib.request.urlopen(req, timeout=180) as r:
        info = json.loads(r.read().decode("utf-8"))
    sub = info.get("subfolder") or ""
    name = info.get("name")
    return "%s/%s" % (sub, name) if sub else name


def post(path, payload):
    req = urllib.request.Request(
        COMFY + path, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def get(path):
    with urllib.request.urlopen(COMFY + path, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def wait_done(prompt_id, timeout=2400):
    t0 = time.time()
    while time.time() - t0 < timeout:
        h = get("/history/%s" % prompt_id)
        if prompt_id in h:
            return h[prompt_id]
        time.sleep(3)
    raise TimeoutError("等待超时 %ds" % timeout)


def download(filename, subfolder, dst_dir):
    q = urllib.parse.urlencode({"filename": filename,
                                "subfolder": subfolder or "", "type": "output"})
    with urllib.request.urlopen("%s/view?%s" % (COMFY, q), timeout=300) as r, \
            open(os.path.join(dst_dir, filename), "wb") as f:
        f.write(r.read())
    return os.path.join(dst_dir, filename)


def build(args):
    """按参数组装工作流 dict（不提交）。"""
    plate = args.plate if os.path.isabs(args.plate) else os.path.join(OUT_DIR, args.plate)
    target = args.target if os.path.isabs(args.target) else os.path.join(OUT_DIR, args.target)
    for p in (plate, target, WF):
        if not os.path.isfile(p):
            raise SystemExit("[X] 缺文件：%s" % p)

    n_plate = upload(plate, "mcp_hj50_plate.png")
    n_target = upload(target, "mcp_hj50_target.png")
    print("上传：%s -> %s" % (os.path.basename(plate), n_plate))
    print("上传：%s -> %s" % (os.path.basename(target), n_target))

    with open(WF, encoding="utf-8") as f:
        wf = json.load(f)
    wf["201"]["inputs"]["image"] = n_plate   # 图1（同时是布局基准）
    wf["202"]["inputs"]["image"] = n_plate
    wf["203"]["inputs"]["image"] = n_target  # 图2
    wf["204"]["inputs"]["prompt"] = args.prompt
    wf["206"]["inputs"]["prompt"] = args.negative.strip()
    wf["207"]["inputs"]["guidance"] = args.guidance
    wf["208"]["inputs"]["guidance"] = args.guidance
    wf["212"]["inputs"]["megapixels"] = args.megapixels
    wf["214"]["inputs"].update(seed=args.seed, steps=args.steps, cfg=args.cfg)
    wf["217"]["class_type"] = "SaveImage"
    wf["217"]["inputs"] = {"images": ["216", 0], "filename_prefix": args.prefix}
    return wf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="v03")
    ap.add_argument("--seed", type=int, default=-1)
    ap.add_argument("--guidance", type=float, default=4.5)
    ap.add_argument("--steps", type=int, default=50)
    ap.add_argument("--cfg", type=float, default=4.5)
    ap.add_argument("--megapixels", type=float, default=1.0)
    ap.add_argument("--plate", default="in/plate.png")
    ap.add_argument("--target", default="in/hj_crop.png")
    ap.add_argument("--prompt", default=DEFAULT_PROMPT)
    ap.add_argument("--prompt-file")
    ap.add_argument("--negative", default=DEFAULT_NEGATIVE)
    ap.add_argument("--prefix")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.prompt_file:
        with open(args.prompt_file, encoding="utf-8") as f:
            args.prompt = f.read().strip()
    if args.seed < 0:
        args.seed = int(time.time()) % 100000000
    args.prefix = args.prefix or ("uniform_50shi/hj_50shi_%s" % args.tag)

    print("seed=%d guidance=%.2f steps=%d cfg=%.2f megapixels=%.2f"
          % (args.seed, args.guidance, args.steps, args.cfg, args.megapixels))
    print("prefix=%s" % args.prefix)
    if args.dry_run:
        print("[dry-run] 只校验文件与参数，不提交")
        p = args.plate if os.path.isabs(args.plate) else os.path.join(OUT_DIR, args.plate)
        t = args.target if os.path.isabs(args.target) else os.path.join(OUT_DIR, args.target)
        for q in (p, t, WF):
            print("  %s  %s" % ("OK " if os.path.isfile(q) else "MISS", q))
        return 0

    wf = build(args)
    res = post("/prompt", {"prompt": wf, "client_id": uuid.uuid4().hex})
    pid = res.get("prompt_id")
    if not pid:
        print("[X] 提交失败：%s" % json.dumps(res, ensure_ascii=False)[:900])
        return 1
    print("prompt_id=%s  等待出图…" % pid)

    hist = wait_done(pid)
    print("status=%s" % hist.get("status", {}).get("status_str"))
    dsts = []
    for node_out in hist.get("outputs", {}).values():
        for im in node_out.get("images", []):
            dsts.append(download(im["filename"], im.get("subfolder", ""), OUT_DIR))
    for d in dsts:
        print("出图 -> %s  (%.1f KB)" % (d, os.path.getsize(d) / 1024.0))
    if not dsts:
        print("[X] 无产物：%s"
              % json.dumps(hist.get("outputs", {}), ensure_ascii=False)[:1200])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
