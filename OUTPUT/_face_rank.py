# -*- coding: utf-8 -*-
"""人脸「排名法」审计 —— 用**相对排名**代替绝对阈值。

★ 为什么必须用排名法（2026-09-15 实测）
    ArcFace 在这批素材上是**跨域**比对（H3 生成的 AI 脸 vs 真人照片/插画定妆照），
    绝对阈值全部失真：
        · README 声称「同人 ≈0.985 / 跨人 ≤0.21」
        · 实测镜 66 帧：vs 刘思齐(本尊) 0.2845、vs 刘思成(**男生**) 0.2515
        ⇒ 本尊只比"另一个性别的另一个人"高 0.03，绝对阈值毫无意义。
    但**相对排序仍有效**：本尊应排第一、且与第二名有**显著差距**。

判据（本脚本）
    对每一镜，把帧与**全部角色**的代表定妆照各算一次 cos，然后：
        rank1_gap = cos(本角色第一名) - cos(非本角色最高)
        MARGIN_OK  = 本角色排第一 且 gap >= 0.10  → 人物一致**可证**
        MARGIN_WEAK= 本角色排第一 但 gap <  0.10  → **不可判**（鉴别力不足）
        MISMATCH   = 本角色**不是**第一        → **真·可疑**（要人眼复核）

用法
    py -3.10 OUTPUT/_face_rank.py --shot=66
    py -3.10 OUTPUT/_face_rank.py --all --top=25
"""
import glob
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")
ASSETS = os.path.join(ROOT, "ASSETS", "CHARACTERS")
PY = ["py", "-3.10"]
VENV = r"E:\code\ComfyUI\venv\Scripts\python.exe"

ACTS = ["01_paper_plane", "04_classroom_dusk", "06_trench", "07_rice_field",
        "08_train_dining", "05_classroom_night"]

# 角色目录 → 代表定妆照（优先 closeup/hero 里**脸最大**的那张，脚本内自动选）
CHARS = ["01_liu_siqi", "02_liu_sicheng", "03_xu_changjing",
         "04_zhang_shuyang", "05_huang_jiguang", "06_yuan_longping",
         "07_zhong_nanshan"]


def cos_between(a, b):
    """用 _face_identity.py compare 取 cosine；失败返回 None。"""
    r = subprocess.run(PY + [os.path.join("OUTPUT", "_face_identity.py"),
                             "compare", a, b],
                       cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    for L in (r.stdout or "").splitlines():
        if '"cosine"' in L:
            try:
                v = float(L.split(":")[1].strip().rstrip(","))
                return v
            except Exception:
                return None
    return None


def main():
    shot = None
    do_all = False
    top = 25
    for a in sys.argv[1:]:
        if a.startswith("--shot="):
            shot = int(a.split("=", 1)[1])
        elif a == "--all":
            do_all = True
        elif a.startswith("--top="):
            top = int(a.split("=", 1)[1])

    # 角色代表图（缓存）
    reps = {}
    for c in CHARS:
        cands = sorted(glob.glob(os.path.join(ASSETS, c, "*hero_v01.png")))
        cands += sorted(glob.glob(os.path.join(ASSETS, c, "*closeup*.png")))
        if cands:
            reps[c] = cands[0]

    frames = {}
    for a in ACTS:
        for f in glob.glob(os.path.join(OUT, a, "frames", "*.png")):
            m = re.match(r"(\d+)_", os.path.basename(f))
            if not m:
                continue                      # 跳过 mirror015 之类的非镜号文件
            frames.setdefault(int(m.group(1)), []).append(f)

    shots = sorted(frames) if do_all else [shot]
    print("用 %d 个角色代表图；待判 %d 镜" % (len(reps), len(shots)))

    rows = []
    for n in shots:
        if n is None or n not in frames:
            continue
        fr = max(frames[n], key=os.path.getmtime)
        refs = json.load(open(os.path.join(OUT, "_shot_refs.json"),
                              encoding="utf-8"))
        own = set()
        for p in (refs.get(str(n), {}).get("refs") or []):
            bn = os.path.basename(p)
            for c in CHARS:
                key = c.split("_", 1)[1]
                if key in bn:
                    own.add(c)
        sc = {}
        for c, rp in reps.items():
            sc[c] = cos_between(fr, rp)
        known = {c: v for c, v in sc.items() if v is not None}
        if not known:
            rows.append(dict(shot=n, verdict="NO_DATA"))
            continue
        own_best = max((known.get(c) or -1) for c in own) if own else None
        others = {c: v for c, v in known.items() if c not in own}
        oth_best = max(others.values()) if others else -1
        best_char = max(known, key=lambda c: known[c])
        gap = (own_best - oth_best) if own_best is not None else None
        if own_best is None:
            v = "NO_OWN_REF"
        elif best_char in own and gap is not None and gap >= 0.10:
            v = "MARGIN_OK"
        elif best_char in own:
            v = "MARGIN_WEAK"
        else:
            v = "MISMATCH"
        rows.append(dict(shot=n, verdict=v, own=sorted(own),
                         own_best=own_best, other_best=oth_best,
                         gap=gap, rank1=best_char,
                         frame=os.path.relpath(fr, ROOT), scores=known))

    cnt = {}
    for r in rows:
        cnt[r["verdict"]] = cnt.get(r["verdict"], 0) + 1
    L = ["人脸「排名法」审计（相对排名 + 差距门限 0.10）", "=" * 78,
         "镜数 %d　%s" % (len(rows),
                        "  ".join("%s=%d" % kv for kv in sorted(cnt.items()))), ""]
    L.append("%-5s %-13s %-8s %-9s %-7s %-16s %s" % (
        "镜", "判定", "本尊cos", "他人最高", "差距", "本尊应含", "排名第一"))
    show = [r for r in rows if r["verdict"] in
            ("MISMATCH", "MARGIN_WEAK", "NO_OWN_REF")]
    show += [r for r in rows if r["verdict"] == "MARGIN_OK"]
    for r in show[:max(top, 120)]:
        if r.get("own_best") is None:
            L.append("%-5s %-13s %-8s %-9s %-7s %-16s %s" % (
                r["shot"], r["verdict"], "-", "-", "-",
                ",".join(r.get("own") or []) or "-", "-"))
            continue
        L.append("%-5s %-13s %-8.3f %-9.3f %-7.3f %-16s %s" % (
            r["shot"], r["verdict"], r["own_best"], r["other_best"],
            r["gap"] or 0, ",".join(r.get("own") or []) or "-", r["rank1"]))

    txt = "\n".join(L)
    print(txt)
    open(os.path.join(OUT, "_face_rank.txt"), "w",
         encoding="utf-8").write(txt)
    json.dump(rows, open(os.path.join(OUT, "_face_rank.json"), "w",
                         encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n→ OUTPUT/_face_rank.txt / .json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
