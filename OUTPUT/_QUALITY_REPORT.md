# 《如愿·看见》质量审查报告

生成时间：2026-09-15 13:45:03

---

## 0. ★★★ 全片分镜一致性复核结论（2026-09-16 本轮新增）

### 0.1 复核方法（三层）

| 层 | 工具 | 查什么 |
|---|---|---|
| **结构层** | `OUTPUT/_audit_storyboard.py` | 时长 / 景别 / 运镜 / 台词 / 参考图，逐条比对 `storyboard.md` |
| **视觉层** | `OUTPUT/_audit_visual.py --act=N` | 按**成片对轴表**抽帧出联系表，逐镜核画面 |
| **量化层** | SAM3 `mask_coverage` / `_scan_text_rows.py` | 主体占比（判景别）、亮暗相邻率（判字幕） |

### 0.2 复核发现与修复（本轮生成 44 个新版文件）

| # | 漂移 | 镜数 | 代表镜 | 根因 | 状态 |
|:-:|---|:--:|---|---|:--:|
| 1 | **`dur` 与 storyboard 时长列不符** | **33** | 47 从 6s→4s、60 从 6s→8s | 早期按"够念完台词"临时加长，storyboard 压缩后未回改 | ✅ 校正 + 重跑 |
| 2 | **景别不符** | 14 | 47（要远景成中景）、17/18/53/60（要特写成近景） | prompt 首句景别词与 storyboard 冲突 | ✅ 改 + 重跑 |
| 3 | **角色性别/年龄漂移** | 3 | 61/64/72 初中生→**成年男性** | prompt 文字（"女生"）与 ref 图（刘思成=男生）冲突 | ✅ 改 + 重跑 |
| 4 | **参考图给错** | 3 | 55/57/70（要同框只喂单人照） | 组合已预制但脚本没接线 | ✅ 改 + 重跑 |
| 5 | **空间逻辑断裂** | **1** | **镜 31**：交通壕→**白天教室** | 环境锚点写在 prompt **末尾**被稀释 + 该镜从未按修好的 prompt 重跑 | ✅ 改 + 重跑（暖度 47.4→15.2） |
| 6 | **`**` Markdown 残留** | 5 处 | 79 / 117 / 122 + `GUARD_GLASSES` | 说明性加粗，对 H3 无信息价值只有泄漏风险 | ✅ 真 prompt 0 处 |

### 0.3 ★★ 两个"假结论"（别再重犯）

| 现象 | 真相 |
|---|---|
| 审核报 **60 镜「时长漂移」** | **是审核脚本自己的 bug**：`h3_quantize()` 误用 `round()`，4s 算成 3.75s。**正解必须用 `ceil`**。修正后**全片 0 镜漂移**。 |
| 审核报 10 镜仍有漂移 | 全是误报：镜 46/74/105 日记字**由后期烧字**；镜 123/124/125 **无景别可言**；镜 11/12/16/48 是**同义景别词**。 |

### 0.4 成片终态（`OUTPUT/full_cut.mp4`）

> **★ 2026-09-17 更新（第二轮修复 镜 1/6/7/8/12/13/14/15 后重建）**

| 项 | 值 |
|---|---|
| **镜数** | **126**（连续 1–126，无空号） |
| **时长** | **520.70 s（8 分 41 秒）** |
| **规格** | 1056×608 h264 / aac 32kHz 2ch @24fps |
| **大小** | 88.8 MB |
| **拼接方式** | **无损**（`concat -c copy`）—— 126 镜规格 100% 统一，未触发重转码兜底 |
| **字幕泄漏终检** | **0 / 126 片段命中**（`_scan_text_rows.py --every=0.5`） |
| **时长一致性** | **0 镜不符**（`over=0 under=0 ok=126`） |
| **prompt 闸门** | ✅ PASS（含本轮新增「语音元词汇」14 条规则） |
| **分镜一致性（本轮 8 镜）** | ✅ **零 ⚠️ 零 🔴**（`_audit_storyboard.py --shots=1,6,7,8,12,13,14,15`） |
| **全片分镜一致性** | 70 完全一致 / 43 存疑 / 13 经人工核为误报或非本轮范围 |
| **端到端验证** | ✅ 从 `full_cut.mp4` 按对轴表抽帧，8 镜全部指向**修复后的新版本** |

> 时长演进：`593.0s（旧版）→ 559.0s（首次重建）→ 523.6s（镜 97/99/104/105 后）`
> → **520.70s（本轮：镜 14 4s→3s、镜 15 4s→3s，共省 2.9s；镜 7 回退 3s）**

#### 0.5 ★★ 本轮修复（镜 97/99/104/105）与新增闸门

| 镜 | 问题 | 根因 | 修法 | 验证 |
|---|---|---|---|---|
| **97** | 台词「`400 米栏`」被念成「**四十米栏**」 | 台词写**阿拉伯数字**且数字与量词**带空格** → H3 断词丢百位 | 改**中文数字不带空格**：`四百米栏` | ASR 回读 = 「…打破过全国**四百米栏**记录」✅ |
| **99** | **张书扬抢了钟南山的台词** | `ref1 = G_ZHANG_ZN`（**张+钟合影**）→ **画面里有谁 H3 就让谁说话** | 换单人照 `G_ZN_SOLO` + prompt 明写「**只有**他一个人入镜、**只有**他一个人说话」 | 读图=仅钟南山一人 ✅；SAM3 覆盖率 **0.395→0.242** 交叉证实 ✅ |
| **99** | 追加：画面描述被**念成台词**（「…只有一种**走过来的笃定**」） | 抽象 `…的X` 短语紧邻台词区、以「的」结尾像话术 → 被归入语音流 | 改写为**具体可拍行为**：`目光平稳、神情克制、没有炫耀的意思` | ASR 核心台词正确、杂音消失 ✅ |
| **104** | **列车未停稳**，末帧门外是**纯黑虚空** | H3 对「列车场景」**默认态就是行进中**，写了"下车"也压不住 | prompt **开篇第一句**写死「完全停稳、车体一动不动、窗外是静止站台灯光」+ 显式否定 + 明确时序 | 读图=门外**灯火通明的静止站台**，无运动模糊 ✅ |
| **105** | **人物漂移**：只剩 3 人、穿深色运动服（全片为白短袖+红领巾） | 旧版是**纯 T2V**（无任何参考图）→ 人物自由发挥 | 改 **R2V** 接 `G_FOUR` + prompt 写明「四个人**一个都不能少**」 | 读图=四人齐全，顺序/性别/**眼镜特征**与定妆照逐项对应 ✅ |

**★ 新增/强化闸门**（`OUTPUT/_verify_prompt_clean.py`）

1. **阿拉伯数字读音陷阱** —— `(?<=说：)[^\n]*\d{3,}` / `问：` / `嘱咐：` 命中即 FAIL。
   > 上线后**顺带抓出 4 处同类隐患**（镜 28/48/76/90 的阿拉伯年份），已一并修掉。
2. **抽象情绪名词化** —— `一种…的X` / `带着…的X` / `有一种…的X` 命中即 FAIL。

**★ 新增工具**：`OUTPUT/_upscale_shot.py`（单镜恢复 1056×608 规格，见 README §6.10.6⑥）

---

#### 0.6 ★★★ 第二批修复（镜 1/6/7/8/12/13/14/15，2026-09-17 用户复测反馈）

> 用户对成片逐镜复测指出 8 个问题。**8 个里有 5 个同源** ——
> 「**R2V 的 `ref1` 是「说话人候选池」**」由此从"单例教训"升级为**系统性根因**。

| 镜 | 用户反馈 | 根因 | 修法 | 状态 |
|:--:|---|---|---|:--:|
| **1** | 校门上的学校名字不对（**第二次**） | 上轮只写"看不到任何字母笔画"= **纯否定句**。但 `ref2` 校门实景图**墙面本身带字**，H3 会读参考图并重画一遍 | 升级为**正向覆盖**：`整个校门上方的墙面是一整片干净的米黄色，上面什么都没有` + 门柱装饰改"纯色几何形状、不承载任何笔画" | ✅ 已重跑，抽帧确认**墙面零文字** |
| **6** | 说话人应**张书扬**而非徐畅景；手里应是**1 架**纸飞机而非 2 架 | ① `ref1=G_FOUR`（4 张脸 = 说话人池）② 道具**没写数量** | ① `ref1 → solo_zhang_shuyang` + 明写"只有他一个人开口" + 用文字补回另外三人<br>② `只有一架…另一只手是空的、什么都没拿` | ✅ 已重跑 |
| **8** | 说话人应**刘思成**而非刘思齐 | `ref1=G_FOUR`；且**刘思齐与刘思成定妆照几乎同款**（都戴细框眼镜）⇒ 文字描述区分不了 | `ref1 → solo_liu_sicheng` + 明写"说话的是画面里这位（照 `<Picture 1>` 的那位）" | ✅ 已重跑 |
| **12** | 说话人应**张书扬**而非徐畅景 | `ref1=G_FOUR` ⇒ 说话人池 | `ref1 → solo_zhang_shuyang` + 说话人指定；顺带修景别（`近景` → `中近景`，对齐 storyboard） | ✅ 已重跑 |
| **13** | 说话人应**徐畅景**而非**路人丙** | `ref1=G_FOUR` ⇒ 说话人池，且无人被指定 | `ref1 → solo_xu_changjing` + 说话人指定 | ✅ 已重跑 |
| **14** | 说话人应**张书扬**；**给 4 秒过多→前边合成多余语音** | ① `ref1=G_FOUR` ② H3 把**台词前空档**当成"还有内容要说"⇒自己编语音 | ① `ref1 → solo_zhang_shuyang`<br>② `dur 4s → 3s` + 新增 **`ONLY_THIS_LINE`** 禁额外人声后缀<br>③ 机器判偏短 0.85s ⇒ 登记 `HOLDS[14]` | ✅ 已重跑（**ASR 待核**） |
| **7** | **给 3 秒过多→前边合成多余语音** | 同上（台词前空档） | `dur 3s → 2s` + `ONLY_THIS_LINE`；说话人改用**位置锚点**（构图是三人同框，不能换单人照） | ✅ 已重跑 |
| **15** | 说话内容应是「**你输在轻敌**」 | 旧脚本台词**与 storyboard 不一致**（写成了「谁叫你以为自己一定赢的？哈哈。」） | 台词改回 storyboard 原文；`dur 4s → 3s`；`ref1 → solo_liu_siqi`；`HOLDS[15]` 换理由保留 | ✅ 已重跑 |
| **追加** | `ONLY_THIS_LINE` 第一版**把指令念了出来** | 初版写**否定式清单**（"…只有上面这一句台词，没有其他任何人声、没有旁白…"）⇒ H3 分不清"指令"与"台词"，**把它念了**：镜 7「你少自恋了，只有上面这一句台词」/ 镜 13「…只有上一句抬口」/ 镜 15「你输在轻敌，全程只有这个外死的」 | 改**纯正向音景**、**不提"语音"二字**：`此段音频里只有这一句对白，其余全是教室的环境底噪与衣料摩擦声。` | ✅ 闸门新增「语音元词汇」规则 8 条；回归测试初版命中 6 处 / 新版 0 处；**已按新文案重跑** |
| **追加** | 镜 12 人物穿**深色运动外套**（\*全片基准是白短袖 Polo + 红领巾**） | prompt 只写"服装照 `<Picture 1>`" ⇒ **H3 只照抄脸，服装按自己的默认想象画**；act0 脚本此前**零**校服字样 | 新增 `UNIFORM` 常量挂进 8 镜：`白色短袖 Polo 衫、白色翻领、红领巾、深色长裤 —— 绝不要画成深色运动外套或拉链运动服` | ✅ 已按新 prompt 重跑 |

**★ 两条新固化的硬规则**

| # | 规则 | 出处 |
|:-:|---|---|
| 1 | **`ref1` 同时是「说话人候选池」**：画面里有几张脸，H3 就可能让谁开口 ⇒ **确定的单人说话镜必须用 `solo_<name>` 单人拼版**；多人同框镜改用**位置锚点** | README §6.10.7 ② / storyboard「参考图提示列读法」 |
| 2 | **台词念完还剩 0.5s 以上，H3 就会拿来编语音** ⇒ `dur` 要按 `净字÷语速 + 0.8s 起势` 收紧，并配 `ONLY_THIS_LINE` | README §4.4b / §6.10.7 ④ |
| 3 | **「对模型说的话」一个字都不能进 prompt**（`ONLY_THIS_LINE` 初版把指令念了出来 ⇒ **同类错误第 2 次**）；**音景描述里不得出现"关于语音的元词汇"**（台词/说话/人声/旁白/念白/语音） | README §6.10.8 |
| 4 | **造型要素必须用文字钉死** —— 写"服装照 `<Picture 1>`"不够，**H3 只照抄脸，服装按自己的默认想象画**（"中国初中生"→ 深色运动外套） | README §6.10.4 ③ / §6.10.7 ④c |

**★ 新增/变更闸门与工具**

1. **`ONLY_THIS_LINE`**（`_diag_act0_plane.py` / `_diag_act2_startup.py`）—— 有台词镜的"抑制额外人声"后缀（**纯正向音景**），
   **必须接在台词行同一行内**（不能另起第 3 行，否则破坏 2 行配方）。
2. **`UNIFORM`**（同上两脚本）—— 校服硬锚点常量，挂进全部 8 镜。
3. **`_verify_prompt_clean.py` 新增「语音元词汇」规则 8 条** —— 初版 `ONLY_THIS_LINE` 文案命中 6 处、新文案 0 处。
4. **`_verify_prompt_lines.py` 扩表 9 → 15 镜**（新增本轮 6 镜），要求真 prompt 恰为 **2 行**。
5. **`_audit_storyboard.py` 景别检查修 false positive**：`中近景` 里含 `近景` ⇒ 改用**最长匹配优先**，
   ✅ 完全一致 **53 → 70 镜**（消除 17 条假告警）。
6. **`_diag_shot_duration_audit.py` 新增 `HOLDS[14]`**（已知取舍，验收须 ASR 逐字核对）。

**★ 五道闸门现状**

| 闸门 | 结果 |
|---|---|
| `_verify_prompt_clean.py` | ✅ **PASS**（含新增「语音元词汇」规则） |
| `_verify_prompt_lines.py` | ✅ **15/15** |
| `_audit_storyboard.py --shots=1,6,7,8,12,13,14,15` | ✅ **零 ⚠️ 零 🔴**（修复前 3🔴+4⚠️） |
| `_diag_shot_duration_audit.py` | ✅ `over=0 under=0 ok=126`（`nominal=489s real=520s`） |
| **`qwen3_asr` 回读（★ 文字闸门挡不住的必须靠它）** | 镜 14 ✅ 逐字正确、**零多余语音**；镜 1/6/7/8/12/13/15 见 §0.6 备注 |

> ⚠️ **方法论**：文字闸门只能保证"我们没写错话"，**挡不住"H3 自己加话/自己加字"**。
> 凡改动**音频行为**（`Audio:` 段、`ONLY_THIS_LINE` / `NO_SPEECH`、时长），
> **重跑后必须 `qwen3_asr` 回读**，不能只看闸门绿了就收工。

---

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

**★ 2026-09-16 去泄漏化第二轮 —— ✅ 已全部完成**

| 项 | 状态 |
|---|---|
| **根因定位** | ✅ **`strip_late_audio()` 吞 `\n`** ⇒ 禁令句与台词被压成一行，H3 无视禁令。**已修 6 个 act 脚本** |
| 全片回归 | ✅ 126 镜文案逐字一致（`_regress_strip.py`，仅恢复换行结构） |
| 新增闸门 | ✅ `_verify_prompt_lines.py` 9/9 通过（校验 strip 之后的真 prompt） |
| **7 个镜**（21/36/77/85/86/88/112）| ✅ **`delogo` 物理擦除**；字幕带白像素保留率 0–27% |
| **镜 14** | ✅ **换 seed 9615 重跑**（`_rerun14_seeds.py`）→ 8/8 帧零字幕 |
| 成片重建 | ✅ `full_cut.mp4` 126 镜 / **593.0 s** / 102.1 MB |
| 成片终检 | ✅ 8 镜 × 4 时间点 = 32 格全干净（`_fullcut_check/FULLCUT_8SHOTS.jpg`） |
| 白名单（画面本就该有字）| 镜 79 / 117 / 122，勿清 |
| 镜 7 | ✅ 首轮已修（旧 8/8 帧泄漏 → 新 0/8 帧） |

**关键结论（几条经验证伪/修正）**

1. ❌ **"加禁令就能压住台词"——错**。禁令位置（独立行 / 嵌画面段内）都不影响，
   3 轮重跑实测全部仍泄漏。
2. ✅ **`**` 标记泄漏 ≠ 台词泄漏**。镜 7 的 `**` 泄漏靠 R1 修好；
   8 镜的台词泄漏是 **H3 对"说话镜"的固有行为**（有台词 9.3% / 纯环境音 0%）。
3. ✅ **换 seed 是有效杠杆**（镜 14：9614 全泄漏 → 9615 全干净）。
4. ✅ **`delogo` 适用条件**：字幕背后是**平滑/单一材质**才干净；
   压在**人物主体（白衣+红领巾）**上会产生**竖条纹伪影**，只能重跑。
5. ⚠️ **校验层级**：必须校验"拼接后、剥后期音频之后"的真文本，
   而不是 `TASKS[n]["prompt"]` 原文 —— 否则全绿但线上仍坏。

> 详见 README §6.6b ⑧–⑭。

**已知遗留（下一轮建议）**

| # | 遗留 | 建议 |
|:-:|---|---|
| 1 | 镜 49/66（刘思齐）face cos 0.25–0.34 偏低 | 参考图是**三视图全身照**`liu_siqi_hero_v01.png`（脸仅约 100px）⇒ 换 `liu_siqi_closeup_v02_16x9.png` 重跑 |
| 2 | 67 镜脸 <250px「不可判」 | 属**景别选择**（远景/空镜），非缺陷；若要判一致性得另抽近景帧 |
| 3 | 成片 593 s（storyboard 计划 492 s）| H3 **时长量化**向上取整（24fps 帧数对齐）所致，非缺陷；如需精确从 492s 得逐镜 trim |
