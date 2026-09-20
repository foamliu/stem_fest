# -*- coding: utf-8 -*-
"""黄继光 50 式冬装 · 多图 prompt 库（2026-09-20）。

核心难点（三轮实测结论）：
  · LongCat / Qwen-Image-Edit 对**否定指令几乎无响应** —— 写"没有帽徽"反而画出帽徽；
  · 拼版里若只写"参考右边的服装"，模型会把**整张拼版当主体重绘**，
    人像被缩成中部小点（v03 实测）。所以 prompt 必须**显式交代拼版版式**：
    "这是一张 4 格拼版，第 1 格是唯一的编辑目标，2/3/4 格只是服装图鉴"。
  · 服装必须**纯正向描述**（"平整素面的帽前片" 而不是 "没有帽徽"）。

`PROMPTS` 里每个键对应一种任务：
  `full_body` —— 由拼版生成单张全身正视图（主任务）
  `cap_only`  —— 只修帽子（用 plate_cap.png，人物保持原位）
"""

# ── 主任务：拼版 → 单张全身正视图 ──
# ★ v04 实测三个必须写进 prompt 的约束：
#   ① 出了**两个人**（拼版首格是"三视图"，模型读成"要画三个人"）
#      ⇒ 显式写 "one single figure, one person only, not a contact sheet"；
#   ② 左侧留了**棋盘格残块**（透明/无内容区） ⇒ 显式写 "left side empty grey"；
#   ③ 帽子仍是**解放帽 + 红五星**（参考图是"帽+檐"正面照，模型直接照搬）
#      ⇒ 帽子描述必须**逐特征正向列举**，并强调"earflaps tied under chin"
#        （护耳系在下巴下 = 50 式冬帽最强辨识特征），且声明帽前片"plain, unmarked"。
FULL_BODY = (
    "This reference sheet has four panels arranged in one row, separated by white "
    "borders with small labels. Panel 1 (labelled \"MAN\") shows a three-view study of "
    "ONE single young Chinese soldier — those three views are the same person, not "
    "three people. Panels 2 and 3 (labelled \"CAP\") and panel 4 (labelled \"COAT\") are "
    "a uniform catalogue. The catalogue panels are reference material only; nothing "
    "from them — no borders, no labels, no checkerboard, no extra figure — may appear "
    "in the output.\n"
    "\n"
    "Output ONE single full-length frontal studio photograph of exactly one person: "
    "the soldier from panel 1, standing upright, centred, the whole figure in frame "
    "from the top of his cap to the soles of his shoes, with plain light grey seamless "
    "backdrop and empty grey floor on both sides. One figure only.\n"
    "\n"
    "He wears the 1952 Chinese People's Volunteer Army winter uniform itemised in the "
    "catalogue panels:\n"
    "· Headwear: a padded cotton winter cap in faded khaki-tan cotton. Its front panel "
    "is perfectly smooth, flat and unmarked, with no emblem and no decoration of any "
    "kind. It has a short soft cloth visor. It has two thick quilted earflaps which "
    "hang down beside his cheeks and are tied together with a cloth string knotted "
    "under his chin. It is a soft, rounded, collapsible hat — not a stiff peaked "
    "service cap.\n"
    "· Tunic: a thick faded khaki-olive cotton padded tunic with a soft high standing "
    "collar closed at the throat, a plain front placket fastened with five large dark "
    "brown round buttons, two flat chest pockets with buttoned flaps, and a matching "
    "fabric waist belt with a plain square metal buckle.\n"
    "· Legs and feet: matching padded cotton trousers gathered over dark canvas shoes.\n"
    "\n"
    "Everything is matte, worn, slightly faded and low in saturation, exactly like the "
    "aged cotton in the catalogue panels. Keep the same face, the same thick eyebrows, "
    "the same eyes, the same nose, the same mouth, the same short hairstyle and the same "
    "skin tone as the soldier in panel 1 — the face must be immediately recognisable as "
    "the same person. Photorealistic, sharp focus, soft even studio lighting."
)

# ── 只修帽子：plate_cap.png（人物头肩 + 2 张 50 式棉帽实物） ──
CAP_ONLY = (
    "This reference sheet has three panels in one row. Panel 1 (labelled \"MAN\") is the "
    "ONLY thing to be edited: a studio head-and-shoulders portrait of one young Chinese "
    "soldier. Panels 2 and 3 (labelled \"CAP\") are a hat catalogue, reference material "
    "only, and must NOT appear in the output.\n"
    "\n"
    "Keep panel 1's soldier, his pose, his three-quarter framing, his face, his "
    "eyebrows, his eyes and his skin exactly as they are, and replace only his headwear "
    "with the cap shown in the catalogue panels: a padded cotton winter cap in faded "
    "khaki-tan cotton whose front panel is completely smooth and plain, with a short "
    "soft cloth visor and two thick quilted earflaps hanging beside his cheeks and tied "
    "under his chin with a cloth string. His tunic is the same faded khaki-olive cotton "
    "padded tunic with a soft standing collar, already visible in panel 1.\n"
    "\n"
    "Photorealistic, matte worn faded cotton, low saturation, soft even studio lighting, "
    "light grey seamless backdrop, no text."
)

# 负向：只写"画质崩坏"类，**绝不写"帽徽/红色/五星"**（会反向强化）
NEGATIVE = (
    "catalogue layout, multiple panels, panel borders, grid, collage, text, letters, "
    "numbers, watermark, signature, caption, cartoon, anime, illustration, painting, "
    "deformed face, distorted face, extra person, extra limbs, duplicate head, blurry, "
    "low quality, oversaturated"
)

PROMPTS = {"full_body": FULL_BODY, "cap_only": CAP_ONLY}
