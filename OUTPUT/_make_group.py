# -*- coding: utf-8 -*-
"""合影参考图拼版脚本 —— 「裁人 → 并排拼版 → 直接入库」，**不经过任何图生图**。

★ 2026-09-14 定案（用户实测结论）：
    LongCat 转过的合影**有些身份失真**，所以**不再用图生图合成合影**。
    拼版图（plate）**本身就是成品参考图**，直接入库喂 R2V 即可。

输入：`OUTPUT/group_ref/crops/<角色名>.png`（由定妆照裁出的单人图，无背景）
输出：`ASSETS/CHARACTERS/_group/<slug>_hero_v01.png`

台账（组合 ↔ 镜号）唯一权威：`README.md` §4.2。
逐镜清单：`python OUTPUT/_diag_cast_per_char.py` → `OUTPUT/_cast_per_char.txt`。

用法：
    py -3.10 OUTPUT/_make_group.py --list              # 列出所有组合与产物路径（默认）
    py -3.10 OUTPUT/_make_group.py --all               # 生成全部组合
    py -3.10 OUTPUT/_make_group.py liu_siqi_zhong_nanshan   # 只生成指定组合
    py -3.10 OUTPUT/_make_group.py --force --all       # 覆盖已存在的产物
"""
import argparse
import os
import subprocess
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CROPS = os.path.join(ROOT, "OUTPUT", "group_ref", "crops")
GROUP = os.path.join(ROOT, "ASSETS", "CHARACTERS", "_group")

# 组合 → 中文角色名（顺序 = 从左到右的站位；说话人居左）
COMBOS = {
    # ── 四小强 ──
    "four_students": ["张书扬", "刘思齐", "刘思成", "徐畅景"],
    "liu_sicheng_liu_siqi": ["刘思成", "刘思齐"],
    "liu_sicheng_zhang_shuyang": ["刘思成", "张书扬"],
    "zhang_shuyang_xu_changjing": ["张书扬", "徐畅景"],
    "liu_siqi_zhang_shuyang": ["刘思齐", "张书扬"],
    "liu_siqi_zhang_shuyang_xu_changjing": ["刘思齐", "张书扬", "徐畅景"],
    # ── 四小强 + 穿越对象 ──
    "four_students_huang_jiguang": ["黄继光", "刘思齐", "刘思成", "张书扬", "徐畅景"],
    "four_students_yuan_longping": ["袁隆平", "刘思齐", "刘思成", "张书扬", "徐畅景"],
    "four_students_zhong_nanshan": ["钟南山", "刘思齐", "刘思成", "张书扬", "徐畅景"],
    # ── 单人对话（穿越对象）──
    "liu_siqi_huang_jiguang": ["刘思齐", "黄继光"],
    "liu_sicheng_huang_jiguang": ["刘思成", "黄继光"],
    "zhang_shuyang_huang_jiguang": ["张书扬", "黄继光"],
    "liu_siqi_yuan_longping": ["刘思齐", "袁隆平"],
    "liu_sicheng_yuan_longping": ["刘思成", "袁隆平"],
    "zhang_shuyang_yuan_longping": ["张书扬", "袁隆平"],
    "xu_changjing_yuan_longping": ["徐畅景", "袁隆平"],
    "liu_siqi_zhong_nanshan": ["刘思齐", "钟南山"],
    # ★ 2026-09-14：下面两张以前走 LongCat、做坏了；现在由本脚本拼版直接入库
    "liu_sicheng_zhong_nanshan": ["刘思成", "钟南山"],
    "xu_changjing_zhong_nanshan": ["徐畅景", "钟南山"],
    "zhang_shuyang_zhong_nanshan": ["张书扬", "钟南山"],
    # ── 含配角 ──
    "young_soldier_soldiers_huang_jiguang": ["小战士", "战士群演", "黄继光"],
    "soldiers_huang_jiguang": ["战士群演", "黄继光"],
    "xu_changjing_soldiers_huang_jiguang": ["徐畅景", "战士群演", "黄继光"],
    "four_students_soldiers": ["刘思齐", "刘思成", "张书扬", "徐畅景", "战士群演"],
    "liu_sicheng_young_soldier_soldiers": ["刘思成", "小战士", "战士群演"],
    # ── 序幕一 ──
    "girl_mother": ["小女孩", "妈妈"],
}

# 单人照也一并入库（面部特写镜的第二图位；`--all` 时一起出）
SOLO = {
    "liu_siqi": "刘思齐",
    "liu_sicheng": "刘思成",
    "xu_changjing": "徐畅景",
    "zhang_shuyang": "张书扬",
    "huang_jiguang": "黄继光",
    "yuan_longping": "袁隆平",
    "zhong_nanshan": "钟南山",
    "young_soldier": "小战士",
    "girl": "小女孩",
    "mother": "妈妈",
    "volunteer_soldiers": "战士群演",
}

HEAD_GAP = 8   # 相邻人像之间的空隙（像素）
MARGIN = 24    # 画布四周留白（像素）
BG = (24, 26, 30)  # 深灰底，避免纯黑与人物头发糊在一起
MAX_H = 1200   # 单个人像的归一化高度上限，防止超宽图

# ★ 人脸体检（2026-09-15 加）：拼完统一量一次"脸高 px"。
#   依据：README §4.2「输出画面脸高 ≥ 250 px」；参考图同理 —— 缩到 1 MP 后脸太小，
#   R2V 就没法还原长相（已实锤案例：liu_siqi_hero_v01 原图 205 px → 1 MP 后 112 px → 不像本人）。
#   实现：调 OUTPUT/_face_identity.py（跑在 ComfyUI venv，它才有 insightface）；
#   **只告警、不阻断**，可 --no-face-check 跳过。
FACE_TOOL = os.path.join(ROOT, "OUTPUT", "_face_identity.py")
FACE_MIN_PX = 250


def face_check(paths, min_px=FACE_MIN_PX):
    """拼版产物的人脸体检（非致命）。"""
    if not paths:
        return
    print("\n[face-check] 体检 %d 张新产物（阈值：1MP 后脸高 >= %d px）…" % (len(paths), min_px))
    try:
        r = subprocess.run([sys.executable, FACE_TOOL, "check", *paths,
                            "--min-face-px", str(min_px)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    except Exception as e:
        print("[face-check] 跳过：%s" % e)
        return
    for line in (r.stdout or "").strip().splitlines():
        print("[face-check] " + line)
    if r.returncode not in (0,):
        print("[face-check] 体检异常（退出码 %s）：%s" % (r.returncode, (r.stderr or "")[-200:]))

# ★ 例外：这组**不要用拼版覆盖** —— 现行图是用户提供的宽幅真人合影（v02），质量优于拼版。
#     key = slug，value = 现行文件名（相对 _group/）。脚本对它们只报告、不写文件。
KEEP_USER_SUPPLIED = {
    "four_students": "four_students_hero_v02.png",
    "four_students_huang_jiguang": "four_students_huang_jiguang_hero_v01.png",
    "four_students_yuan_longping": "four_students_yuan_longping_hero_v01.png",
    # ⚠️ four_students_zhong_nanshan 2026-09-14 起**取消保护** —— 旧用户版里的钟南山是
    #    插画风带蓝底 + 姓名标签 + 豆包水印，已改由 `_rebuild_4zn.py` 拼版接管
    "girl_mother": "girl_mother_hero_v01.png",
    "liu_sicheng_zhang_shuyang": "liu_sicheng_zhang_shuyang_hero_v01.png",
}


def _load_crop(name):
    path = os.path.join(CROPS, name + ".png")
    if not os.path.isfile(path):
        raise FileNotFoundError("缺单人裁图：%s" % path)
    return Image.open(path).convert("RGBA")


def compose(names):
    """把多张单人裁图等高对齐、并排拼成一张。返回 PIL Image（RGB）。"""
    imgs = [_load_crop(n) for n in names]
    # 归一化高度：以最小者为准的 1.0 倍，避免放大糊掉
    target_h = min(min(im.height for im in imgs), MAX_H)
    scaled = []
    for im in imgs:
        w = max(1, int(round(im.width * target_h / im.height)))
        scaled.append(im.resize((w, target_h), Image.LANCZOS))
    w_sum = sum(im.width for im in scaled) + HEAD_GAP * (len(scaled) - 1) + MARGIN * 2
    h_sum = target_h + MARGIN * 2
    canvas = Image.new("RGB", (w_sum, h_sum), BG)
    x = MARGIN
    for im in scaled:
        canvas.paste(im, (x, MARGIN), im)
        x += im.width + HEAD_GAP
    return canvas


def main():
    ap = argparse.ArgumentParser(description="合影/单人参考图拼版入库（不经图生图）")
    ap.add_argument("slugs", nargs="*", help="组合 slug；留空视为 --list")
    ap.add_argument("--all", action="store_true", help="生成全部组合 + 全部单人图")
    ap.add_argument("--list", action="store_true", help="只列清单，不写文件")
    ap.add_argument("--force", action="store_true", help="覆盖已存在的产物")
    ap.add_argument("--no-face-check", action="store_true",
                    help="拼完不做人脸体检（默认会量脸高并告警）")
    args = ap.parse_args()

    if not os.path.isdir(CROPS):
        print("[ERROR] 找不到裁图目录：%s\n        先跑裁人步骤（见 ASSETS/README.md §3 合影做法）。" % CROPS)
        return 2
    os.makedirs(GROUP, exist_ok=True)

    if args.all:
        targets = list(COMBOS.items()) + [("solo_" + k, [v]) for k, v in SOLO.items()]
    elif args.slugs:
        targets = []
        for s in args.slugs:
            if s in COMBOS:
                targets.append((s, COMBOS[s]))
            elif s in SOLO:
                targets.append(("solo_" + s, [SOLO[s]]))
            else:
                print("[WARN] 未知 slug：%s（用 --list 看可用值）" % s)
    else:
        targets = list(COMBOS.items())

    ok = skip = keep = fail = 0
    written = []
    for slug, names in targets:
        out = os.path.join(GROUP, slug + "_hero_v01.png")
        tag = "%-38s" % slug

        # ★ 用户提供的宽幅合影优先，不被拼版覆盖
        if slug in KEEP_USER_SUPPLIED:
            cur = os.path.join(GROUP, KEEP_USER_SUPPLIED[slug])
            state = "KEEP  用户提供版在场" if os.path.isfile(cur) else "KEEP  ⚠️ 用户版缺失：" + KEEP_USER_SUPPLIED[slug]
            print("%s %s（要强制拼版请先手动删掉用户版）" % (tag, state))
            keep += 1
            continue

        if os.path.isfile(out) and not args.force and not args.list:
            print("%s SKIP 已存在（--force 覆盖）" % tag)
            skip += 1
            continue
        try:
            im = compose(names)
        except FileNotFoundError as e:
            print("%s FAIL %s" % (tag, e))
            fail += 1
            continue
        if args.list:
            print("%s LIST %sx%s  ← %s" % (tag, im.width, im.height, " + ".join(names)))
            continue
        im.save(out, "PNG", optimize=True)
        print("%s OK   %sx%s  %.2f MB  ← %s"
              % (tag, im.width, im.height,
                 os.path.getsize(out) / 1024.0 / 1024.0, " + ".join(names)))
        ok += 1
        written.append(out)

    if not args.no_face_check:
        face_check(written)

    print("\n合计：OK %d / SKIP %d / KEEP %d / FAIL %d → %s" % (ok, skip, keep, fail, GROUP))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
