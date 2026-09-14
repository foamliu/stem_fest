# -*- coding: utf-8 -*-
"""开跑前总盘点：3 个缺幕脚本所需的全部参考图是否齐备。"""
import os

ROOT = r"E:\code\stem_fest"
G = os.path.join(ROOT, "ASSETS", "CHARACTERS", "_group")

NEED = [
    # 序幕一（镜 1-9）
    ("序幕一", "girl_mother_hero_v01.png"),
    ("序幕一", "four_students_hero_v02.png"),
    ("序幕一", "liu_siqi_zhang_shuyang_xu_changjing_hero_v01.png"),
    # 第三幕（镜 75-105）
    ("第三幕", "four_students_hero_v02.png"),
    ("第三幕", "four_students_zhong_nanshan_hero_v01.png"),
    ("第三幕", "liu_siqi_zhong_nanshan_hero_v01.png"),
    ("第三幕", "liu_sicheng_zhong_nanshan_hero_v01.png"),
    ("第三幕", "xu_changjing_zhong_nanshan_hero_v01.png"),
    ("第三幕", "zhang_shuyang_zhong_nanshan_hero_v01.png"),
    ("第三幕", "liu_sicheng_liu_siqi_hero_v01.png"),
    ("第三幕", "solo_zhong_nanshan_hero_v01.png"),
    # 尾声（镜 106-126）
    ("尾声", "four_students_hero_v02.png"),
    ("尾声", "liu_sicheng_zhang_shuyang_hero_v01.png"),
]

print("=== 合影 / 多人参考图 ===")
seen, miss = set(), []
for act, name in NEED:
    if name in seen:
        continue
    seen.add(name)
    ok = os.path.isfile(os.path.join(G, name))
    print("  %s  %-48s %s" % ("OK " if ok else "缺! ", name, act))
    if not ok:
        miss.append(name)

print()
print("=== 场景图 ===")
for d, f in [("01_school_gate", "school_gate_wide_v02.png"),
             ("02_campus", "campus_wide_v01.png"),
             ("03_classroom_day", "classroom_day_wide_v01.png"),
             ("08_train_dining", "train_dining_wide_v01.png"),
             ("05_classroom_night", "classroom_night_wide_v01.png")]:
    p = os.path.join(ROOT, "ASSETS", "SCENES", d, f)
    ok = os.path.isfile(p)
    print("  %s  %s/%s" % ("OK " if ok else "缺! ", d, f))
    if not ok:
        miss.append(f)

print()
print("=== 道具图 ===")
for d, f in [("01_paper_plane", "paper_plane_hero_v01.png"),
             ("07_mask", "mask_hero_v02.png"),
             ("08_laptop", "laptop_hero_v03.png"),
             ("03_holo_screen", "holo_screen_hero_v01.png"),
             ("04_rice_plant", "rice_plant_hero_v01.png"),
             ("05_rice_ear", "rice_ear_hero_v01.png"),
             ("09_photo_huang_jiguang", "photo_huang_jiguang_hero_v02.png")]:
    p = os.path.join(ROOT, "ASSETS", "PROPS", d, f)
    ok = os.path.isfile(p)
    print("  %s  %s/%s" % ("OK " if ok else "缺! ", d, f))
    if not ok:
        miss.append(f)

print()
print("结论：%s" % ("全部齐备，可以开跑" if not miss else "缺 %d 项：%s" % (len(miss), miss)))
