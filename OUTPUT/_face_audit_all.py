# -*- coding: utf-8 -*-
"""全片人脸一致性审计（在 `_face_identity.py` 之上加**脸高门限**）。

★ 为什么必须加门限（2026-09-15 实测）
    `_face_identity.py ledger` 单幕跑出来的低分**主要是"脸太小"造成的**
    （ArcFace 在 80–230 px 的脸高上 embedding 不稳），不是"人不像"。
    序幕一实测：
        脸高 263 → cos 0.596（SAME）
        脸高 84–233 → cos 0.25–0.44（被判 DIFFERENT / REVIEW）
    脸高≥250 均值 0.596，脸高<250 均值 0.375 —— 「脸小」与「低分」强相关。
    ⇒ **脸高 < MIN_FACE_PX 的镜，结论一律降级为「不可判（脸太小）」**，
      不得直接判"人不像"，否则会误报一大片。

判级规则（本脚本）
    NO_FACE         帧里没检出脸（空镜/远景）—— 正常，不算缺陷
    TOO_SMALL       检出脸但 < 门限 ⇒ **不可判**（要判断得先重跑成近景或放大抽帧）
    SAME            cos >= 0.50 且脸高达标
    REVIEW          0.35 <= cos < 0.50 且脸高达标 → 人工复核
    DIFFERENT       cos < 0.35 且脸高达标 → 真·可疑

用法
    py -3.10 OUTPUT/_face_audit_all.py
    py -3.10 OUTPUT/_face_audit_all.py --min-face=250 --top=30
    py -3.10 OUTPUT/_face_audit_all.py --min-face=150     # 宽松档，多看些
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")
PY = ["py", "-3.10"]

ACTS = ["01_paper_plane", "03_classroom_day", "06_trench",
        "07_rice_field", "08_train_dining", "05_classroom_night"]


def main():
    min_face = 250
    top = 25
    for a in sys.argv[1:]:
        if a.startswith("--min-face="):
            min_face = int(a.split("=", 1)[1])
        elif a.startswith("--top="):
            top = int(a.split("=", 1)[1])

    rows_all = []
    for act in ACTS:
        r = subprocess.run(PY + [os.path.join("OUTPUT", "_face_identity.py"),
                                 "ledger", "--act", act, "--quiet",
                                 "--top", "0"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        jp = os.path.join(OUT, "_face_ledger_%s.json" % act)
        if not os.path.exists(jp):
            print("  %-22s !! 无 ledger（rc=%d）" % (act, r.returncode))
            continue
        d = json.load(open(jp, encoding="utf-8"))
        for x in d.get("rows") or []:
            x["act"] = act
            rows_all.append(x)
        print("  %-22s %d 镜" % (act, len(d.get("rows") or [])))

    # 重新判级（加脸高门限）
    def regrade(x):
        if x.get("cosine") is None:
            return "NO_FACE"
        h = x.get("frame_face_h") or 0
        c = x["cosine"]
        if h < min_face:
            return "TOO_SMALL"
        if c >= 0.50:
            return "SAME"
        if c >= 0.35:
            return "REVIEW"
        return "DIFFERENT"

    for x in rows_all:
        x["raw_verdict"] = x.get("verdict")
        x["verdict"] = regrade(x)

    cnt = {}
    for x in rows_all:
        cnt[x["verdict"]] = cnt.get(x["verdict"], 0) + 1

    L = []
    L.append("全片人脸一致性审计（脸高门限 = %d px）" % min_face)
    L.append("=" * 78)
    L.append("镜数 %d　%s" % (len(rows_all),
                            "  ".join("%s=%d" % kv for kv in sorted(cnt.items()))))
    L.append("")

    judgeable = [x for x in rows_all if x["verdict"] in
                 ("SAME", "REVIEW", "DIFFERENT")]
    if judgeable:
        avg = sum(x["cosine"] for x in judgeable) / len(judgeable)
        L.append("可判镜（脸高达标）%d 个，平均 cos = %.3f" % (len(judgeable), avg))
    ts = [x for x in rows_all if x["verdict"] == "TOO_SMALL"]
    if ts:
        L.append("不可判镜（脸 <%d px）%d 个 —— 这些镜的低分**不代表人不像**" % (
            min_face, len(ts)))
    L.append("")

    sus = [x for x in rows_all if x["verdict"] in ("DIFFERENT", "REVIEW")]
    sus.sort(key=lambda x: x["cosine"])
    L.append("★ 可判镜里的可疑清单（cos 升序，前 %d）" % min(top, len(sus)))
    L.append("%-4s %-22s %-10s %-7s %-7s %s" % (
        "镜", "幕", "判定", "cos", "脸高", "参考图"))
    for x in sus[:top]:
        L.append("%-4s %-22s %-10s %-7s %-7s %s" % (
            x["shot"], x["act"], x["verdict"], round(x["cosine"], 3),
            x["frame_face_h"], x.get("ref") or "-"))

    L.append("")
    L.append("★ 脸高最大的镜（这些镜结论最可信）")
    big = sorted([x for x in rows_all if x.get("cosine") is not None],
                 key=lambda x: -(x["frame_face_h"] or 0))[:top]
    L.append("%-4s %-22s %-10s %-7s %-7s %s" % (
        "镜", "幕", "判定", "cos", "脸高", "参考图"))
    for x in big:
        L.append("%-4s %-22s %-10s %-7s %-7s %s" % (
            x["shot"], x["act"], x["verdict"], round(x["cosine"], 3),
            x["frame_face_h"], x.get("ref") or "-"))

    txt = "\n".join(L)
    print("\n" + txt)
    open(os.path.join(OUT, "_face_audit_all.txt"), "w",
         encoding="utf-8").write(txt)
    json.dump(rows_all, open(os.path.join(OUT, "_face_audit_all.json"), "w",
                             encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n→ OUTPUT/_face_audit_all.txt / .json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
