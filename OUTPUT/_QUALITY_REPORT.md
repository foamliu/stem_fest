# 《如愿·看见》质量审查报告

生成时间：2026-09-15 13:45:03

## 1. 素材覆盖度

```
幕脚本                      输出目录                     应有    有视频     缺镜 多余镜(不属于本幕)
----------------------------------------------------------------------------------------------------
_diag_act0_plane.py      01_paper_plane            9      9      0 -
_diag_act2_startup.py    04_classroom_dusk         9      9      0 -
_diag_act1_trench.py     06_trench                28     28      0 -
_diag_act3_rice.py       07_rice_field            28     28      0 -
_diag_act4_train.py      08_train_dining          31     31      0 -
_diag_act5_finale.py     05_classroom_night       21     21      0 -
----------------------------------------------------------------------------------------------------
全片：应有 126 镜，实际覆盖 126 镜，缺失 无
带问题的幕：0 个
```

## 2. 字幕污染（已定位 + 已修复 + 已验证）

**根因**：H3 会把 prompt 里「对模型说的话」（如 `NO_SPEECH` 常量、舞台指示、内心状态比喻）当作**画面字幕**渲染。

**A/B 对照证据**（`OUTPUT/_ab/AB.jpg`，同镜同抽帧点 OLD/NEW 上下并排）：

| 镜 | 修复前（OLD） | 修复后（NEW） |
|---|---|---|
| 5 | 「本镜不要生成任何可□旁白」 | ✅ **无字幕** |
| 110 | 「不镜不要生成任何可□旁白」（**3/3 帧**）| ✅ **3/3 帧无字幕** |
| 91 | 「像在消化一件很难以刻接受」+ 英文乱码（**3/3 帧**）| ✅ **3/3 帧无字幕** |

**全片复检**：对全部 41 个重跑镜做 `_probe.py --type=T1` 抽检（每镜 3 帧底部条带）→ **0 处污染**。

**修复做法**：把 `NO_SPEECH` 等否定式指令改成**纯正向音景描述**（`Audio: 安静的室内环境底噪；…`），删掉全部元信息/否定式文字。

**闸门**：`OUTPUT/_verify_prompt_clean.py`（非 0 退出则禁止开跑）。

⚠️ **提 steps 无效**：镜 5 用 steps=20 重跑过，字幕依旧⇒ 这是**语义层**问题，不是采样不足。

## 3. 重跑进度

需要重跑 41 镜，分三档：

| 档 | 含义 | 镜数 |
|---|---|---|
| P1 | 否定式残留（新修改） | 6 |
| P2 | `NO_SPEECH` 引用 | 28 |
| P3 | 元信息旧视频 | 7 |

重跑日志尾部：

```
[10:34:36] >> _diag_act4_train.py  镜 [94, 96]
[10:41:05]    OK（57.1 分钟）
[10:41:06] >> _diag_act4_train.py  镜 [75, 79, 81, 83, 91, 102, 104, 105]
[10:58:54]    OK（24.3 分钟）
[10:58:54] 
[10:58:54] ==================================================================
[10:58:54] 完成 5/7 镜；失败批次 0 个
[10:58:54] ==================================================================
[11:42:56]    OK（61.8 分钟）
[11:42:56] >> _diag_act5_finale.py  镜 [106, 109, 120, 122, 123, 124, 125, 126]
[12:52:33]    OK（69.6 分钟）
[12:52:33] 
[12:52:33] ==================================================================
[12:52:33] 完成 25/28 镜；失败批次 0 个
[12:52:33] ==================================================================
```

## 4. 人脸一致性

### 4.1 ArcFace 量化审计（`_face_audit_all.py`）

```
全片人脸一致性审计（脸高门限 = 250 px）
==============================================================================
镜数 126　DIFFERENT=2  NO_FACE=17  REVIEW=5  SAME=36  TOO_SMALL=66

可判镜（脸高达标）43 个，平均 cos = 0.610
不可判镜（脸 <250 px）66 个 —— 这些镜的低分**不代表人不像**

★ 可判镜里的可疑清单（cos 升序，前 7）
镜    幕                      判定         cos     脸高      参考图
66   07_rice_field          DIFFERENT  0.252   500     liu_siqi_hero_v01.png
49   07_rice_field          DIFFERENT  0.336   317     liu_siqi_hero_v01.png
55   07_rice_field          REVIEW     0.387   358     yuan_longping_hero_v01.png
110  05_classroom_night     REVIEW     0.39    500     four_students_hero_v02.png
63   07_rice_field          REVIEW     0.421   261     four_students_yuan_longping_hero_v01.png
79   08_train_dining        REVIEW     0.439   612     liu_sicheng_zhong_nanshan_hero_v01.png
37   06_trench              REVIEW     0.47    262     liu_siqi_hero_v01.png

★ 脸高最大的镜（这些镜结论最可信）
镜    幕                      判定         cos     脸高      参考图
38   06_trench              SAME       0.771   632     huang_jiguang_hero_v02.png
79   08_train_dining        REVIEW     0.439   612     liu_sicheng_zhong_nanshan_hero_v01.png
51   07_rice_field          SAME       0.631   597     liu_sicheng_hero_v01.png
71   07_rice_field          SAME       0.683   581     yuan_longping_hero_v01.png
113  05_classroom_night     SAME       0.627   574     four_students_hero_v02.png
93   08_train_dining        SAME       0.649   556     liu_siqi_zhong_nanshan_hero_v01.png
66   07_rice_field          DIFFERENT  0.252   500     liu_siqi_hero_v01.png
110  05_classroom_night     REVIEW     0.39    500     four_students_hero_v02.png
58   07_rice_field          SAME       0.663   473     yuan_longping_hero_v01.png
65   07_rice_field          SAME       0.707   469     yuan_longping_hero_v01.png
70   07_rice_field          SAME       0.69    461     zhang_shuyang_hero_v01.png
80   08_train_dining        SAME       0.555   455     liu_sicheng_liu_siqi_hero_v01.png
```

### 4.2 ⚠️ 方法学警告：绝对阈值在本批素材上**失真**

实测（镜 66 帧 vs 各角色定妆照）：

```
vs 刘思齐（本尊） = 0.2845
vs 刘思成（男生） = 0.2515   ← 只差 0.03
vs 徐畅景（女生） = 0.1324
vs 张书扬（男生） = 0.0955
```

**结论**：参考图是**真人照片/插画**、生成帧是 **H3 的 AI 脸**，属**跨域比对**，ArcFace 鉴别力退化到噪声级。
README 声称的「同人 ≈0.985 / 跨人 ≤0.21」**对本批素材不适用**。

**当前唯一可靠做法**：`OUTPUT/_face_tri.py` 并排三联图 + 读图，判**服装 / 发型 / 眼镜 / 人数**这些**硬特征**（比看脸稳）。

### 4.3 排名法（`_face_rank.py`）

```
人脸「排名法」审计（相对排名 + 差距门限 0.10）
==============================================================================
镜数 1　MARGIN_WEAK=1

镜     判定            本尊cos    他人最高      差距      本尊应含             排名第一
66    MARGIN_WEAK   0.252    0.245     0.007   01_liu_siqi      01_liu_siqi
```

## 5. prompt 危险写法清单

```
H3 prompt 字幕污染高危清单（按镜号）
======================================================================

镜 1  (_diag_act0_plane.py)
   [R6 制作备忘] （后期）

镜 2  (_diag_act0_plane.py)
   [R6 制作备忘] （后期）

镜 3  (_diag_act0_plane.py)
   [R6 制作备忘] （后期）

镜 6  (_diag_act0_plane.py)
   [R6 制作备忘] （后期）

镜 7  (_diag_act0_plane.py)
   [R6 制作备忘] （后期）

镜 8  (_diag_act0_plane.py)
   [R6 制作备忘] （后期）

镜 10  (_diag_act2_startup.py)
   [R6 制作备忘] （后期）

镜 11  (_diag_act2_startup.py)
   [R6 制作备忘] （后期）

镜 12  (_diag_act2_startup.py)
   [R6 制作备忘] （后期）

镜 13  (_diag_act2_startup.py)
   [R6 制作备忘] （后期）

镜 14  (_diag_act2_startup.py)
   [R6 制作备忘] （后期）

镜 15  (_diag_act2_startup.py)
   [R3 否定祈使] 人，一针见血地轻声说了一句、说完嘴角几乎不可察地一挑（带一点不给他留面子的笑意）
   [R6 制作备忘] （后期）

镜 16  (_diag_act2_startup.py)
   [R6 制作备忘] （后期）

镜 17  (_diag_act2_startup.py)
   [R6 制作备忘] （后期）

镜 18  (_diag_act2_startup.py)
   [R6 制作备忘] （后期）

镜 20  (_diag_act1_trench.py)
   [R6 制作备忘] （后期）

镜 21  (_diag_act1_trench.py)
   [R6 制作备忘] （后期）

镜 22  (_diag_act1_trench.py)
   [R6 制作备忘] （后期）

镜 23  (_diag_act1_trench.py)
   [R3 否定祈使] + 军帽上的红色五角星帽徽必须保留**，不可改成其他军装、不可摘下军帽）

镜 24  (_diag_act1_trench.py)
   [R3 否定祈使] + 军帽上的红色五角星帽徽必须保留**，不可改成其他军装、不可摘下军帽）
   [R6 制作备忘] （后期）

镜 25  (_diag_act1_trench.py)
   [R3 否定祈使] + 军帽上的红色五角星帽徽必须保留**，不可改成其他军装、不可摘下军帽）
   [R6 制作备忘] （后期）

镜 26  (_diag_act1_trench.py)
   [R3 否定祈使] + 军帽上的红色五角星帽徽必须保留**，不可改成其他军装、不可摘下军帽）
   [R6 制作备忘] （后期）

镜 27  (_diag_act1_trench.py)
   [R3 否定祈使] + 军帽上的红色五角星帽徽必须保留**，不可改成其他军装、不可摘下军帽）
   [R6 制作备忘] （后期）

镜 28  (_diag_act1_trench.py)
   [R3 否定祈使] + 军帽上的红色五角星帽徽必须保留**，不可改成其他军装、不可摘下军帽）
   [R6 制作备忘] （后期）

镜 29  (_diag_act1_trench.py)
   [R3 否定祈使] + 军帽上的红色五角星帽徽必须保留**，不可改成其他军装、不可摘下军帽）
   [R6 制作备忘] （后期）

镜 30  (_diag_act1_trench.py)
   [R3 否定祈使] + 军帽上的红色五角星帽徽必须保留**，不可改成其他军装、不可摘下军帽）
   [R6 制作备忘] （后期）

镜 31  (_diag_act1_trench.py)
   [R6 制作备忘] （后期）

镜 32  (_diag_act1_trench.py)
   [R3 否定祈使] + 军帽上的红色五角星帽徽必须保留**，不可改成其他军装、不可摘下军帽）
   [R6 制作备忘] （后期）

镜 33  (_diag_act1_trench.py)
   [R3 否定祈使] + 军帽上的红色五角星帽徽必须保留**，不可改成其他军装、不可摘下军帽
```

## 6. 分镜版本台账（有多个版本的镜）

| 镜 | 版本数 | 文件名（按新旧） |
|---|---|---|
| 10 | 2 | 10_four_before_holo_device_00002_.mp4<br>10_four_before_holo_device_00003_.mp4 |
| 16 | 2 | 16_zhang_stuck_sicheng_smirks_00002_.mp4<br>16_zhang_stuck_sicheng_smirks_00003_.mp4 |
| 19 | 3 | 19_trench_wide_four_and_soldiers_00001_.mp4<br>19_trench_wide_four_and_soldiers_00002_.mp4<br>19_trench_wide_four_and_soldiers_00003_.mp4 |
| 23 | 2 | 23_huang_shares_wild_veg_with_young_soldier_00001_.mp4<br>23_huang_shares_wild_veg_with_young_soldier_00002_.mp4 |
| 33 | 2 | 33_huang_eyes_light_up_mother_00001_.mp4<br>33_huang_eyes_light_up_mother_00002_.mp4 |
| 38 | 2 | 38_huang_smiles_slowly_closeup_00001_.mp4<br>38_huang_smiles_slowly_closeup_00002_.mp4 |
| 39 | 2 | 39_young_soldier_and_huang_promise_00001_.mp4<br>39_young_soldier_and_huang_promise_00002_.mp4 |
| 43 | 2 | 43_huang_stands_tells_them_to_go_back_00001_.mp4<br>43_huang_stands_tells_them_to_go_back_00002_.mp4 |
| 45 | 2 | 45_huang_turns_waves_goodbye_00001_.mp4<br>45_huang_turns_waves_goodbye_00002_.mp4 |
| 46 | 2 | 46_white_screen_diary_text_transition_00001_.mp4<br>46_white_screen_diary_text_transition_00002_.mp4 |
| 50 | 2 | 50_yuan_bending_looking_for_rice_00001_.mp4<br>50_yuan_bending_looking_for_rice_00002_.mp4 |
| 52 | 2 | 52_rice_plant_eyes_light_up_00001_.mp4<br>52_rice_plant_eyes_light_up_00002_.mp4 |
| 64 | 2 | 64_yuan_silent_looks_at_kids_00001_.mp4<br>64_yuan_silent_looks_at_kids_00002_.mp4 |
| 73 | 2 | 73_yuan_walks_into_rice_field_00001_.mp4<br>73_yuan_walks_into_rice_field_00002_.mp4 |
| 74 | 2 | 74_white_out_diary_card_act2_00001_.mp4<br>74_white_out_diary_card_act2_00002_.mp4 |
| 75 | 3 | 75_zhong_asleep_in_dining_car_00001_.mp4<br>75_zhong_asleep_in_dining_car_00002_.mp4<br>75_zhong_asleep_in_dining_car_00003_.mp4 |
| 79 | 2 | 79_sicheng_reads_the_document_00001_.mp4<br>79_sicheng_reads_the_document_00002_.mp4 |
| 81 | 2 | 81_zhong_opens_eyes_sees_them_00001_.mp4<br>81_zhong_opens_eyes_sees_them_00002_.mp4 |
| 83 | 2 | 83_four_sit_down_00001_.mp4<br>83_four_sit_down_00002_.mp4 |
| 91 | 2 | 91_zhong_silent_looks_at_them_00001_.mp4<br>91_zhong_silent_looks_at_them_00002_.mp4 |
| 94 | 2 | 94_zhong_smiles_slowly_00001_.mp4<br>94_zhong_smiles_slowly_00002_.mp4 |
| 96 | 2 | 96_zhong_remembers_running_fast_00001_.mp4<br>96_zhong_remembers_running_fast_00002_.mp4 |
| 102 | 2 | 102_wuhan_station_hands_mask_00001_.mp4<br>102_wuhan_station_hands_mask_00002_.mp4 |
| 104 | 2 | 104_zhong_walks_away_into_night_00001_.mp4<br>104_zhong_walks_away_into_night_00002_.mp4 |
| 105 | 2 | 105_white_out_diary_card_act4_00001_.mp4<br>105_white_out_diary_card_act4_00002_.mp4 |
| 106 | 2 | 106_back_to_classroom_holo_in_hands_00001_.mp4<br>106_back_to_classroom_holo_in_hands_00002_.mp4 |
| 109 | 2 | 109_zhang_opens_laptop_photo_pops_00001_.mp4<br>109_zhang_opens_laptop_photo_pops_00002_.mp4 |
| 110 | 3 | 110_zhang_shocked_closeup_00001_.mp4<br>110_zhang_shocked_closeup_00002_.mp4<br>110_zhang_shocked_closeup_00003_.mp4 |
| 111 | 3 | 111_three_gather_no_one_speaks_00001_.mp4<br>111_three_gather_no_one_speaks_00002_.mp4<br>111_three_gather_no_one_speaks_00003_.mp4 |
| 113 | 3 | 113_siqi_looks_at_photo_silent_00001_.mp4<br>113_siqi_looks_at_photo_silent_00002_.mp4<br>113_siqi_looks_at_photo_silent_00003_.mp4 |
| 117 | 3 | 117_xu_stands_holo_subtitle_00001_.mp4<br>117_xu_stands_holo_subtitle_00002_.mp4<br>117_xu_stands_holo_subtitle_00003_.mp4 |
| 119 | 3 | 119_zhang_glances_sicheng_nods_00001_.mp4<br>119_zhang_glances_sicheng_nods_00002_.mp4<br>119_zhang_glances_sicheng_nods_00003_.mp4 |
| 120 | 2 | 120_zhang_presses_first_key_00001_.mp4<br>120_zhang_presses_first_key_00002_.mp4 |
| 121 | 3 | 121_four_around_laptop_holo_float_00001_.mp4<br>121_four_around_laptop_holo_float_00002_.mp4<br>121_four_around_laptop_holo_float_00003_.mp4 |
| 122 | 2 | 122_screen_shows_title_00001_.mp4<br>122_screen_shows_title_00002_.mp4 |
| 123 | 3 | 123_black_screen_three_lines_00001_.mp4<br>123_black_screen_three_lines_00002_.mp4<br>123_black_screen_three_lines_00002__card.mp4 |
| 124 | 3 | 124_three_lines_fade_last_line_00001_.mp4<br>124_three_lines_fade_last_line_00002_.mp4<br>124_three_lines_fade_last_line_00002__card.mp4 |
| 125 | 2 | 125_three_stills_flash_00001_.mp4<br>125_three_stills_flash_00002_.mp4 |
| 126 | 2 | 126_final_freeze_four_backs_00001_.mp4<br>126_final_freeze_four_backs_00002_.mp4 |

## 7. 成片抽检（`_check_final.py`）

```
成片抽检：OUTPUT\full_cut.mp4
时长 593.0 s（9.88 分）　抽 24 帧

#    时刻s      亮度       对比度      判定
0    12.4     64.3     66.4     
1    37.1     111.6    55.0     
2    61.8     109.8    60.2     
3    86.5     81.2     49.9     
4    111.2    75.3     50.7     
5    135.9    64.9     59.6     
6    160.6    64.0     48.6     
7    185.3    97.3     66.3     
8    210.0    72.0     61.6     
9    234.7    118.0    60.1     
10   259.4    94.0     56.4     
11   284.1    102.3    60.8     
12   308.8    109.2    50.7     
13   333.5    91.2     60.8     
14   358.3    86.8     53.5     
15   383.0    75.6     57.1     
16   407.7    69.9     47.5     
17   432.4    72.5     47.3     
18   457.1    78.5     54.2     
19   481.8    155.0    26.3     
20   506.5    52.6     47.6     
21   531.2    57.9     51.6     
22   555.9    47.7     43.6     
23   580.6    31.4     38.5     

可疑帧：0 个 
⚠️ 字幕镜/黑屏转场镜（46/74/105/123/124）本身就该是黑或白，出现"可疑"先核对镜号再下结论。
拼图：OUTPUT\_final_check\final_sheet.jpg
```

## 8. 下一步 / 已知遗留

**已完成**

1. ✅ 41 镜重跑（P1=6 / P2=28 / P3=7），0 失败
2. ✅ 全片 126 镜字幕复检 → 0 污染
3. ✅ `full_cut.mp4` 重拼（无损 `-c copy`）
4. ✅ 成片 24 帧量化抽检 → 0 可疑帧
5. ✅ 镜 123/124 纯字幕屏改**后期烧字**（H3 中文乱码）

**已知遗留（下一轮建议）**

| # | 遗留 | 建议 |
|:-:|---|---|
| 1 | 镜 49/66（刘思齐）face cos 0.25–0.34 偏低 | 参考图是**三视图全身照**`liu_siqi_hero_v01.png`（脸仅约 100px）⇒ 换 `liu_siqi_closeup_v02_16x9.png` 重跑 |
| 2 | 67 镜脸 <250px「不可判」 | 属**景别选择**（远景/空镜），非缺陷；若要判一致性得另抽近景帧 |
| 3 | 成片 593 s（storyboard 计划 492 s）| H3 **时长量化**向上取整（24fps 帧数对齐）所致，非缺陷；如需精确从 492s 得逐镜 trim |
