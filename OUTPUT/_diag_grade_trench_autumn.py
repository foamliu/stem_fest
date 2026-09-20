# -*- coding: utf-8 -*-
"""战壕场景图 · 深秋调色（v02 → v04）：把「灰绿阴天」调成「深秋枯黄、有太阳」。

★ 起因（用户复审第一幕《上甘岭》）：
    场景图 `trench_wide_v02.png` 是 2026-09-12 生成的调色锁定版，画面特征为
      · 天空**灰白发闷**、没有任何太阳方向感（漫射阴天）
      · 前景**湿泥 + 水洼反光**（像雨后，不是「干冷的深秋」）
      · 壕壁野草**枯枝发暗**、整体偏**灰绿**（mean RGB ≈ 100.7 / 109.1 / 87.7，R−B 仅 12.9）
    而修正后的 prompt（`_diag_act1_trench.py` 的 LIGHT）要求：
      · 白天有太阳、光线偏硬、从侧上方斜射
      · 草木枯黄、地面是干硬的黄褐色土地、没有积水与水洼
    文字与参考图冲突时 H3 倾向照抄参考图（README §6.10.3 锚点冲突）⇒ 必须让**图**也变秋。
    **镜 21 实测出的「绿油油的夏天」就是这个冲突的直接后果。**

★ 本脚本做什么（纯数值调色，不重生成 ⇒ 不改变构图/道具/壕形，只改色温与明暗）
    1. **暖化**（秋色）：R 增益 ↑、B 增益 ↓，把灰绿推向枯黄褐
    2. **加反差**（硬光）：先扣黑白场再拉 gamma，模拟斜射硬光的明暗对比
    3. **提亮高光**（太阳感）：S 形曲线轻提上段，天空不再发闷
    4. **降饱和下半部**（去绿）：对绿色通道做定向抽色，压掉「鲜绿」

★ 为什么用「调色」而不是「重跑 z_image_turbo_t2i」
    · v02 的**构图与道具**（沙袋、弹药箱、铁锹、搪瓷缸、坑道纵深）已经过用户确认，
      重生成会有构图漂移风险，还会连带 28 个镜的参考一致性返工；
    · 幕内一致性优先：**同一张图微调**比「换一张新图」对 R2V 的角色/空间锁定更安全。

用法：
    py -3.10 OUTPUT/_diag_grade_trench_autumn.py --dry     # 只看参数与预估色偏
    py -3.10 OUTPUT/_diag_grade_trench_autumn.py           # 生成 v04 + 四图对比联系表
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
from PIL import Image

ROOT = r"E:\code\stem_fest"
SCENE_DIR = os.path.join(ROOT, "ASSETS", "SCENES", "06_trench")
SRC = os.path.join(SCENE_DIR, "trench_wide_v02.png")
DST = os.path.join(SCENE_DIR, "trench_wide_v04.png")
SHEET = os.path.join(ROOT, "OUTPUT", "_trench_autumn_compare.png")
REPORT = os.path.join(ROOT, "OUTPUT", "_trench_autumn_grade.json")

# ── 调色参数（唯一定义处，改这里即可）──────────────────────────
# ★ 2026-09-20 v03 → v04 二次增益：
#   v03 数值达标（R-B 26.8 / G/R 1.007），但**画面下半部亮度只有 66/62/41** ——
#   「白天有太阳、斜射硬光」的文字在图上落不下来，土壁仍显灰闷。
#   故再提一档：R 增益与 gamma 下压提中段、高光提亮加到 0.12，
#   区域实测（`_check_trench_regions.py` 分 SKY/GND 两块）：地面亮度 56→**64**（+8）、
#   天空 R-B +7→**+18.5**（暖灰而非冷蓝）；全图 R-B 26.8→24.4（同属暖调，v04 更亮）。
#   仍保持「构图/道具/壕形零改动」—— 纯数值，不重生成。
# 暖化增益：秋色 = 红↑ 蓝↓（与 v02 的灰绿相反）
GAIN = (1.050, 1.000, 0.985)
# 黑白场（先扣掉，拉开层次）；0 = 不动，0.016 = 扣掉最暗 1.6%
BLACK, WHITE = 0.014, 0.978
# 中间调 gamma：<1 提亮中段（模拟硬光下的反射光）
GAMMA = 0.900
# 定向抽绿：对「绿占主导」的像素降饱和，压掉鲜绿草丛
GREEN_PULL = 0.70
# 高光提亮强度（太阳感），0 = 关闭
HILIGHT = 0.120


def apply_grade(rgb):
    """rgb: float32 HxWx3 in 0..1 → 调色后的同形状数组。"""
    a = rgb.copy()

    # ① 暖化
    a *= np.array(GAIN, dtype=np.float32)

    # ② 黑白场
    a = (a - BLACK) / (WHITE - BLACK)

    # ③ gamma（提中段）
    a = np.clip(a, 0.0, None) ** GAMMA

    # ④ 定向抽绿：g 明显高于 r 与 b 的像素 = 鲜绿植被 → 降饱和
    #    （只有「绿主导」的像素被动；土黄/沙袋 r>g 不受影响）
    g = a[:, :, 1]
    dom = np.clip((g - np.maximum(a[:, :, 0], a[:, :, 2])) * 6.0, 0.0, 1.0)
    lum = a.mean(axis=2, keepdims=True)
    a = a * (1.0 - dom[:, :, None] * GREEN_PULL) + lum * dom[:, :, None] * GREEN_PULL
    # 抽绿后再补一点暖色，避免抽成灰
    a *= np.array([1.018, 1.0, 0.986], dtype=np.float32)

    # ⑤ 高光提亮（太阳感，S 形上段）
    a = np.clip(a, 0.0, None)
    a = a + HILIGHT * (a ** 2.2)

    return np.clip(a, 0.0, 1.0)


def stats(rgb):
    f = rgb.reshape(-1, 3)
    return {
        "mean": [round(float(x), 2) for x in f.mean(0) * 255],
        "std": [round(float(x), 2) for x in f.std(0) * 255],
        "r_minus_b": round(float((f[:, 0].mean() - f[:, 2].mean()) * 255), 2),
        "g_over_r": round(float(f[:, 1].mean() / max(f[:, 0].mean(), 1e-6)), 4),
    }


def main():
    dry = "--dry" in sys.argv
    for p in (SRC,):
        if not os.path.exists(p):
            print("[X] 找不到 %s" % p)
            sys.exit(2)

    im = Image.open(SRC).convert("RGB")
    src = np.asarray(im, dtype=np.float32) / 255.0
    out = apply_grade(src)

    s0, s1 = stats(src), stats(out)
    print("源图   %s  %s" % (im.size, SRC))
    print("  暖化前 mean RGB=%s  std=%s  R-B=%s  G/R=%s"
          % (s0["mean"], s0["std"], s0["r_minus_b"], s0["g_over_r"]))
    print("  暖化后 mean RGB=%s  std=%s  R-B=%s  G/R=%s"
          % (s1["mean"], s1["std"], s1["r_minus_b"], s1["g_over_r"]))
    print("  目标：R-B 由 ~13 升到 ≥ 22（灰绿→枯黄褐）；G/R 由 ~1.083 降到 ≤ 1.045（去绿）")

    ok_rb = s1["r_minus_b"] >= 22
    ok_gr = s1["g_over_r"] <= 1.045
    print("  闸门：R-B ≥ 22 → %s ；G/R ≤ 1.045 → %s"
          % ("PASS" if ok_rb else "FAIL", "PASS" if ok_gr else "FAIL"))
    if not (ok_rb and ok_gr):
        print("[!] 调色未达标：调整顶部 GAIN / GREEN_PULL 后重跑")

    if dry:
        print("\n（--dry：不写文件）")
        return

    Image.fromarray((out * 255.0 + 0.5).astype(np.uint8)).save(DST)
    print("\n[OK] 写出 %s" % DST)

    # 四图对比联系表：v01 / v02 / v03 / v04 横排
    tiles = []
    for name in ("trench_wide_v01.png", "trench_wide_v02.png",
                 "trench_wide_v03.png", "trench_wide_v04.png"):
        p = os.path.join(SCENE_DIR, name)
        if os.path.exists(p):
            tiles.append(Image.open(p).convert("RGB").resize((640, 360)))
    if tiles:
        sheet = Image.new("RGB", (640 * len(tiles), 360))
        for i, t in enumerate(tiles):
            sheet.paste(t, (640 * i, 0))
        sheet.save(SHEET)
        print("[OK] 对比联系表（v01 | v02 | v03 | v04）：%s" % SHEET)

    rep = {
        "src": SRC, "dst": DST,
        "gain": list(GAIN), "black": BLACK, "white": WHITE,
        "gamma": GAMMA, "green_pull": GREEN_PULL, "hilight": HILIGHT,
        "before": s0, "after": s1,
        "gate": {"r_minus_b>=22": ok_rb, "g_over_r<=1.045": ok_gr},
    }
    io.open(REPORT, "w", encoding="utf-8", newline="\n").write(
        json.dumps(rep, ensure_ascii=False, indent=2))
    print("[OK] 报告：%s" % REPORT)


if __name__ == "__main__":
    main()
