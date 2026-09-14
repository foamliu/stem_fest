# -*- coding: utf-8 -*-
"""提取「镜号 → 参考图（定妆照）」映射，供人物一致性视觉比对使用。

原理
    6 个幕脚本里每个镜头的 `TASKS` 都声明了 ref1/ref2（R2V 的参考图）。
    这些就是 H3 生成该镜时所依据的「角色长相锚点」。
    把「镜号 → 参考图路径」抽出来，视觉检查时就能：
        抽该镜的帧 + 把对应定妆照并排贴在一起  =>  让视觉模型判「是不是同一个人」。

输出
    OUTPUT/_shot_refs.json    {镜号: {"slug":..., "refs":[...], "dur":..., "seed":...}}
    OUTPUT/_shot_refs.txt     人类可读清单

用法：
    py -3.10 OUTPUT/_shot_refs.py
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT")

SCRIPTS = [
    "_diag_act0_plane.py",
    "_diag_act1_trench.py",
    "_diag_act2_startup.py",
    "_diag_act3_rice.py",
    "_diag_act4_train.py",
    "_diag_act5_finale.py",
]


def parse_script(path):
    """从幕脚本里抽 TASKS[N] = dict(...) 的 ref1/ref2/slug/dur/seed。

    不 import（会触发脚本副作用），用正则逐块扫文本。
    实际写法（各幕一致）：
        G_FOUR_SOLDIERS = "ASSETS/CHARACTERS/_group/four_students_soldiers_hero_v01.png"
        TASKS[19] = dict(
            slug="...", seed=9700,
            ref1=G_FOUR_SOLDIERS, ref2=SCENE, dur=6.0,   # ← 常量名，非字面量
            prompt=(...),
        )
    ⇒ 必须先把「常量名 → 路径」表建起来，再解析 ref1/ref2。
    """
    txt = open(path, encoding="utf-8").read()

    # ① 常量表：NAME = "ASSETS/..." 或 NAME = os.path.join(...)
    consts = {}
    for m in re.finditer(r'^([A-Z][A-Z0-9_]{2,})\s*=\s*"([^"]+)"', txt, re.M):
        consts[m.group(1)] = m.group(2)
    # 也支持  NAME = os.path.join(ROOT, "ASSETS", ...) 形式
    for m in re.finditer(r'^([A-Z][A-Z0-9_]{2,})\s*=\s*os\.path\.join\(([^)]+)\)',
                         txt, re.M):
        parts = re.findall(r'"([^"]+)"', m.group(2))
        if parts and parts[0].upper() == "ROOT":
            consts[m.group(1)] = "/".join(parts[1:])
        elif parts:
            consts[m.group(1)] = "/".join(parts)

    def resolve(token):
        """把 ref 值解析成路径：字面量 / 常量名 / None。"""
        token = token.strip().strip(",")
        if token in ("None", ""):
            return None
        if token.startswith('"') and token.endswith('"'):
            return token[1:-1]
        if token in consts:
            return consts[token]
        return None

    res = {}
    for m in re.finditer(r"^TASKS\[(\d+)\]\s*=\s*dict\(", txt, re.M):
        n = int(m.group(1))
        i = m.end()
        depth, start = 1, i
        while i < len(txt) and depth:
            if txt[i] == "(":
                depth += 1
            elif txt[i] == ")":
                depth -= 1
            i += 1
        body = txt[start:i]
        slug = re.search(r'slug\s*=\s*"([^"]+)"', body)
        dur = re.search(r"dur\s*=\s*([\d.]+)", body)
        seed = re.search(r"seed\s*=\s*(\d+)", body)
        refs = []
        for key in ("ref1", "ref2"):
            r = re.search(key + r"\s*=\s*([^,\n]+)", body)
            if r:
                p = resolve(r.group(1))
                if p:
                    refs.append(p)
        res[n] = {
            "slug": slug.group(1) if slug else "?",
            "dur": float(dur.group(1)) if dur else 0.0,
            "seed": int(seed.group(1)) if seed else 0,
            "refs": refs,
            "script": os.path.basename(path),
        }
    return res


def main():
    allshots = {}
    for s in SCRIPTS:
        p = os.path.join(OUT, s)
        if not os.path.exists(p):
            print("!! 缺少 %s" % s)
            continue
        got = parse_script(p)
        print("%-24s -> %d 镜" % (s, len(got)))
        allshots.update(got)

    # 归一化参考图路径（脚本里写的是相对 ROOT）
    for n, v in allshots.items():
        norm = []
        for r in v["refs"]:
            rp = r.replace("/", os.sep)
            ap = rp if os.path.isabs(rp) else os.path.join(ROOT, rp)
            norm.append(ap)
            if not os.path.exists(ap):
                print("   !! 镜 %d 参考图不存在：%s" % (n, rp))
        v["refs"] = norm

    keys = sorted(allshots)
    print("\n合计 %d 镜（%d..%d）" % (len(keys), keys[0], keys[-1]))
    gap = [i for i in range(keys[0], keys[-1] + 1) if i not in allshots]
    print("缺号：%s" % (gap if gap else "无"))
    nref = sum(len(v["refs"]) for v in allshots.values())
    print("参考图引用总数：%d" % nref)

    with open(os.path.join(OUT, "_shot_refs.json"), "w", encoding="utf-8") as f:
        json.dump({str(k): allshots[k] for k in keys}, f,
                  ensure_ascii=False, indent=1)

    with open(os.path.join(OUT, "_shot_refs.txt"), "w", encoding="utf-8") as f:
        for n in keys:
            v = allshots[n]
            names = ", ".join(os.path.basename(r) for r in v["refs"]) or "（T2V 无角色）"
            f.write("镜 %-4d %-42s %5.1fs  refs: %s\n" % (
                n, v["slug"], v["dur"], names))
    print("输出：OUTPUT/_shot_refs.json / _shot_refs.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
