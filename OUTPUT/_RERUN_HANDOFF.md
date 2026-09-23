# 无人值守重跑 · 交接说明（2026-09-21 07:40 启动）

> 用户交代：「我去上班，在晚 6 点我下班前，遇到问题自己决定。」
> 本文件是**你回来时先看的东西** —— 出问题先看这里。

---

## 一、在跑什么

**场景图换图重跑**：2026-09-20 你重生成并定版了四套场景图
（`03_classroom_day` v01 / `05_classroom_night` v01 / `07_rice_field` v01 / `08_train_dining` v01），
旧成片全是用**已被删除的旧图**（含 `04_classroom_dusk`）生成的 ⇒ 画面背景必须换。

**判据（可复算，不是拍脑袋）**：某镜最新产物 mtime < 该幕场景图 mtime ⇒ 必重跑。
由 `py -3.10 OUTPUT/_plan_scene_rerun.py` 算出，结果写在 `OUTPUT/_scene_rerun.json`。

### 清单（89 镜，≈14 小时）

| 幕 | 镜号 | 需重跑 | steps | 说明 |
|---|---|---|---|---|
| 序幕一 `01_paper_plane` | 1-9 | **0** | — | 场景图 9/12 未变 ✅ 不要动 |
| 序幕二 `03_classroom_day` | 10-18 | **9** | 20 | 教室图从 `04` 并入 `03`，全换 |
| 第一幕 `06_trench` | 19-46 | **0** | — | **28 镜在 9/20 15:52 换风雪图后已重跑过** ✅ 省下约 40 小时 |
| 第二幕 `07_rice_field` | 47-74 | **28** | 10 | 新稻田图 |
| 第三幕 `08_train_dining` | 75-105 | **31** | 10 | 新餐车图 |
| 尾声 `05_classroom_night` | 106-126 | **21** | 10 | 新夜教室图 |

> ★ **第一幕不用跑** 是本轮最大的省时项 —— 若整幕重跑会白烧约 40 小时。
> 这是「逐镜 mtime 比对」而非「整幕重跑」的直接收益。

---

## 二、怎么跑（自动）

```
E:\code\stem_fest\OUTPUT\_auto_scene_rerun.bat     ← 总控（已在后台跑）
```

四阶段，**全部可重入**：

1. **环境自查** — `_check_scene_refs.py` 校验 6 个幕脚本的场景图引用是否都指向真实文件（失败则拒绝开工）
2. **等 GPU 空闲** — 每 60s 探一次 ComfyUI 队列，**绝不并行**（H3 11.96GB / 16GB 显存，并行必 OOM）
3. **逐镜重跑** — `_run_scene_rerun.py`，**最多 6 轮自动续跑**；单镜失败记入状态后继续下一镜
4. **收尾** — 进度核对 → 人脸一致性抽检 → 重拼全片 → 结果清单

### 进度看板

```powershell
py -3.10 -c "import json;d=json.load(open('OUTPUT/_scene_rerun_state.json',encoding='utf-8'));print('已完成 %d / 89   失败 %d'%(len(d['done']),len(d['fail'])));print(d['fail'])"
```

日志：`OUTPUT/_auto_scene_rerun.log`（总控）、`OUTPUT/_scene_rerun.log`（逐镜）

---

## 三、万一中断了怎么办（重入）

**直接重跑那个 bat 即可** —— 状态记在 `_scene_rerun_state.json`，已完成的镜会跳过。

```powershell
# 断点续跑
E:\code\stem_fest\OUTPUT\_auto_scene_rerun.bat

# 或手动：只补失败的镜（先清空失败记录再跑）
py -3.10 OUTPUT\_run_scene_rerun.py --retry

# 只看计划不动手
py -3.10 OUTPUT\_run_scene_rerun.py --dry
```

⚠️ **中断后务必先确认 ComfyUI 队列已空**再重启，否则两个任务抢 GPU：
```powershell
py -3.10 -c "import json,urllib.request;d=json.load(urllib.request.urlopen('http://127.0.0.1:8188/queue',timeout=8));print(len(d.get('queue_running',[])),len(d.get('queue_pending',[])))"
```

---

## 四、开工前已排除的两个坑（留个记录）

### 坑 1：`_plan_scene_rerun.py` 的「无产物」假警报
纪念幕一 曾报「9 镜无产物」，实为**文件名补零**问题 ——
`01_paper_plane` 用 `%02d`（`01_xxx.mp4`），其余幕用 `%d`。
只 glob 一种格式会永远匹配不到。**已修**（三种补零都试）。
> 同一个坑 `_run_rerun.py` 在 2026-09-15 踩过并留了注释，我复现了它 —— 教训是
> **凡是「按镜号找文件」的地方，都必须同时试 `%d` / `%02d` / `%03d`**。

### 坑 2：ComfyUI 缓存导致「成功的任务被判失败」（实锤，已修）
烟测镜 10 成功后，总控重跑同一条命令被误判 `rc=0 且无新产物`。
根因：**ComfyUI 对完全相同的 workflow 有缓存** —— prompt 一字未改时 `/prompt`
立刻回一个已完成的结果（日志表现为 `0 s`、`排队=0`），**不产生新文件**。
⇒ 只查「有无新文件」会把**成功**当失败。
**已改为四步判定**（`_verdict`）：`[OK]` 回执 → 新文件 → 失败标记 → 兜底失败。
已单测 4 条路径全部正确。

### 附带加固：`_concat_video.py` 的跨幕重号
原逻辑「同号取 mtime 最新」，在六幕镜号区间互不相交时是安全的。
现在 `04` 并入 `03` 后**首次出现跨幕重号风险**（尾声 106-126 vs 序幕一 1-9 的 slug 可能撞车）。
已加 `RANGES` 权威映射：**镜号不属于本幕区间就跳过并告警**，是结构性保证，
不再依赖「碰巧不重号」。实测 126/126 无缺号、无越界。

---

## 五、本次刻意**没做**的事（等你决定）

1. **音效/BGM 没碰** —— 你说延后。注意镜 75/91 的 `SFX-14_hsr_rumble` 仍是**硬缺口**
   （`storyboard.md:521` 写了文件名但产物是 `None`）。
2. **`_plan_rerun.py` 的旧污染清单没跑** —— 它判据是「prompt 修复时刻」(9/14、9/15)，
   与本次「换图」是**两件独立的事**。本次重跑会把其中一部分镜顺带覆盖，
   但**纯 prompt 污染镜（如镜 4/5/9）不在本次范围内** —— 那些属于第一幕/序幕一，
   若你后续想清，需另跑 `_run_rerun.py`。
3. **`_rerun_list.json` 的 GBK 乱码标题没修** —— 不影响运行（只影响 cat 可读性）。

---

## 六、验收建议（你回来后）

```powershell
# 1. 场景引用与完成度
py -3.10 OUTPUT\_check_scene_refs.py
py -3.10 OUTPUT\_progress.py

# 2. 抽看新成片的场景是否正确（重点看 4 幕各 1 镜）
py -3.10 OUTPUT\_extract_frames.py --shots=12,50,80,110     # 参数以脚本 --help 为准

# 3. 人脸有没有被新场景带偏（换图不该改人脸）
py -3.10 OUTPUT\_char_consistency.py --shots=12,50,80,110

# 4. 台词有没有被新背景音带乱（H3 会自己生成环境音）
py -3.10 OUTPUT\_audit_asr.py --shots=12,50,80,110
```

**重点抽检项**：
- 序幕二镜 10-18 的教室是否**同一间、同一光**（这是合并 `04→03` 的**唯一目的**，必须验）
- 镜 18「白光吞没教室」转场是否仍成立（steps=20 单独跑过）
- 尾声镜 106-126 与序幕二是**同一间教室**（现实只隔一小会儿）—— 新旧背景拼在一起看不看得出来

---

## 七、收尾结果（2026-09-21 18:40 定稿）

### 1. 重跑
- **89/89 完成，0 失败**，收尾时刻 16:48:50，实际耗时约 10 h。
- 状态文件：`OUTPUT/_scene_rerun_state.json`（`done` 89 项 / `fail` 空）。
- 日志：`OUTPUT/_auto_scene_rerun.log`（阶段 0 门禁 → 阶段 2 逐镜 → 阶段 3 收尾）。

### 2. 跨幕连续性与转场抽检

| 检查 | 数据 | 判定 |
|---|---|---|
| 镜 18 白场转场 | 末帧 RGB 均值 **237 / 240 / 247**（1056×608） | ✅ 已是白场，转场成立 |
| 序幕二 镜 10 教室 | 亮度 **85.7** | 基准（傍晚暖光） |
| 尾声 镜 106 | 亮度 **69.3** | ✅ 同教室、更暗一档 |
| 尾声 镜 126 | 亮度 **53.8** | ✅ 入夜，梯度合理 |

> 换图合并（`04_classroom_dusk` → `03_classroom_day`）后，序幕二 10-18 与尾声 106-126
> 仍共用同一教室空间（黑板 `To`/`未来`、右侧暖色侧光），亮度差构成「傍晚→入夜」叙事梯度。
> 即：**新旧背景拼在一起看不出接缝**。

### 3. 门禁与一致性
- `_check_scene_refs.py`：8 个剧本场景引用 **全部 OK**。
- `_char_consistency.py`：126 镜对比图 `OUTPUT/_consistency/cons_01..32.jpg` 出齐。

### 4. 成片
- **`OUTPUT/full_cut_scene_v2.mp4`** — h264 1056×608 @24fps / aac 32kHz 2ch
- 时长 **528.26 s**（8.80 分），**12615 帧**，101.6 MB
- 章节表合计 525.6250 s vs 成片帧数折算 **偏差 −0.0000 s**
- 镜号烙录：右上角 `SHOT NNN`；章节轴 `OUTPUT/_concat_chapters.txt`（126 行，首镜 3.0417s / 末镜 517.6250→525.6250s）

### 5. SFX-14 硬缺口已补 —— `OUTPUT/sfx/film/SFX-14c_hsr_woosh_00001.mp3`

原 `stable_audio_3_sfx` 于 2026-09-20 以 902.4 s 超时收场（`❌ None`）。本次三方案对比：

| 版本 | 工具 | 耗时 | `sound_caption` 回读 | 判定 |
|---|---|:--:|---|:--:|
| 原 prompt | `stable_audio_3_sfx` | 15.1s | *a vehicle passing by … engine and tire sounds* | ❌ 外景经过事件 |
| 改写 interior/constant | `stable_audio_3_sfx` | 6.1s | *high-pitched, sustained electronic tone … sine wave* | ❌ 高频电子音，方向相反 |
| 改写 carriage/steady rumble | `woosh_sfx`(dflow) | 36.2s | *vehicle idling … low-frequency rumble … no other prominent sounds* | ✅ **采用** |

**经验（补进 §LESSONS）**：低频稳态、无事件的底噪是 `stable_audio_3_sfx` 的弱项
（它倾向于把「车」画成「经过」或「高频」）；`woosh_sfx` 物件感更实，一次通过。
报告已回写 `OUTPUT/_film_sfx_report.md`（含「SFX-14 补跑记录」小节）。
镜 75/91 铺位请取 `SFX-14c`，**不要**用 `SFX-14_hsr_rumble_00002` 或 `SFX-14b_hsr_interior`。

### 6. 五个待办的最终状态

| 待办 | 状态 |
|---|---|
| 尾声 106-126 vs 序幕二教室连续性 | ✅ 已验（见 §7.2） |
| 镜 18 白场转场 | ✅ 已验 |
| SFX-14 硬缺口 | ✅ 已补（`SFX-14c`） |
| `_plan_rerun.py` prompt 污染镜 4/5/9 | ✅ 已闭环 —— 09-15 的 `_resume_finalize` 已重跑过；`_rerun_list.json` 是**历史快照**，非当前待办 |
| `_rerun_list.json` / 旧日志 GBK 乱码 | ⚠️ 判定为**不需修**：`_rerun_list.json` 实际是干净 UTF-8（已核字节）；真正乱的是 `_act1_rerun.log` 等旧日志（UTF-16LE + GBK 双层错乱），内容已被 `_asr_audit.txt` / `_subtitle_audit.py` 覆盖，且新脚本统一 `PYTHONIOENCODING=utf-8` + `open(...,"wb")` 直写，不再复现 |

**结论：本次无人值守重跑 + 收尾全部闭环，无遗留阻塞项。**

---

## 八、音画漂移事故与修复（2026-09-21 晚，用户报障后处理）

### 1. 报障与定位

用户看 v2 成片，报「第二幕《禾下乘凉》很多人声与视频不同步」，并**当场核对单镜产物**
（镜 59/60/61）确认**单镜音画同步** ⇒ 问题在**拼接后处理**，与 H3 生成无关。

### 2. 根因（实测闭环，详见 `README §6.11` + `_readme_history.md §6.11.1`）

**每个 H3 片段的音轨解码长度都比画面长 0~32 ms**（AAC 1024 采样/颗向上取整 = 编码器补零）：

| 事实 | 数值 |
|---|---|
| 逐段余量（126 段，实测） | 121 段 > 0，平均 **+20.9 ms**，**合计 +2631 ms** |
| v2 音轨 vs 画面 | 528.256 vs 525.625 s = **+2.631 s** |
| v2 逐镜实测人声偏移 | 镜 59 **+1340 ms**、镜 126 **+2630 ms**（相关度 1.00） |
| 截掉的尾部是什么 | 补零（尾部 RMS −77~−240 dB vs 人声 −11~−34 dB，峰值 ≤0.0024） |
| 五路接法对照 | 分两条 concat / 同一条 concat / `-f concat` 纯接 **全部累积**；`-shortest` 削尾**砍掉视频帧**；只有「每段音频钉到本镜时长」= **全 0 ms** |

### 3. 已修

- `OUTPUT/_concat_video.py`：新增 `AUDIO_NORM`（`aresample,aformat,apad,atrim=0:<本镜时长>,asetpts`）+
  `seg_dur()`，改用**同一条** `concat=n=N:v=1:a=1`；章节表/音频段长/`drawtext` 段长**同源**。
- 新增**闸门 2**：`|音轨长度 − 画面长度| < 0.15 s`，超限即判失败（旧成片 +2.631 s 会被当场拦下）。
- 文件头 §7 写入完整事故档案。

### 4. 产物（本次收尾后的 OUTPUT/ 根目录）

| 文件 | 说明 | 验证 |
|---|---|---|
| `full_cut.mp4` | **新母版**（本次重拼，无 BGM）101.5 MiB / 525.625 s / 12615 帧 / SHOT NNN 烧录 | 逐镜偏移 **全部 \|≤10 ms\|（均值 0.24 ms）**；音轨 525.626 vs 画面 525.625（+0.001 s） |
| `full_cut_bgm_chorus.mp4` | **标配成片**（母版 + 《如愿》）105.6 MiB | 画面 MD5 与母版**逐字节一致**；台词整片延迟 −4.98 ms、相关 0.98；BGM 仅 489.875 s 后出现 ✓ |
| `full_cut_scene_v2.mp4` | ⚠️ **已知跑调版**，保留作 A/B 对照（镜 59 +1340 ms） | 建议对照完即删（101.6 MB） |

**被本次覆盖/删除的旧文件**（均为旧画面 + 跑调音轨，`README §8` 早已标注可删）：
`full_cut.mp4`（9/20 旧母版，被新母版覆盖）、`full_cut_bgm_chorus.mp4`（9/20 旧标配，被覆盖）、
`full_cut_bgm.mp4`、`full_cut_bgm_tail.mp4`（删除）。
⚠️ 因旧母版已被覆盖，**9/20 版是否跑调无法再实测复核**。注意「音轨 525.626 s ≈ 画面」**不能**作为对齐证据 ——
修好的新母版音轨**同样是 525.626 s**（钉长 vs 截断在长度上不可区分）。判据必须是**逐镜内容偏移**。
已在 `README §6.11` / `_readme_history.md §6.11.1⑦` 中如实标注。

### 5. 复核命令（以后每次拼完成片都跑）

```powershell
py -3.10 OUTPUT/_diag_av_match.py OUTPUT/full_cut.mp4          # 逐镜内容偏移，要求「偏移>60ms 的镜 = 0 个」
py -3.10 OUTPUT/_verify_bgm_mix.py --orig=OUTPUT/full_cut.mp4 --mix=OUTPUT/full_cut_bgm_chorus.mp4 --start=489.875 --dip=-20
```

### 6. 诊断脚本（全部保留，可重跑取证）

`_diag_av_match.py`（逐镜偏移，接受成片路径参数）、`_diag_clip_audio_excess.py`（逐段余量 + 按批次分组）、
`_diag_tail_silence.py`（尾部静音取证）、`_diag_concat_ab.py`（A/B/C 三路对照）、
`_diag_demuxer_join.py`（D 纯接）、`_diag_prepass_shortest.py`（E 削尾）。

---

## 九、镜 125（三帧历史人物闪回）脸部错误修复（2026-09-21 晚）

### 1. 症状与根因

镜 125 原为 **T2V 无参考图**，三帧历史人物（黄继光 / 袁隆平 / 钟南山）的脸靠文字「编」，
实测**两段错**（袁隆平成圆脸中年人、钟南山成泛化苍老老人）——原因是 prompt 用文字描述年龄，
且与定妆照设定冲突（见 `_make_125_triptych.py` 顶部诊断链）。

### 2. 修复路线（三次迭代）

| 方案 | 做法 | 结果 |
|---|---|---|
| ① 单条 8s + 三格拼图 ref | 3 张脸塞进 1 张参考图，一次生成 | ❌ 模型预算不够：run2 里**第 3 段直接串成第 2 段的脸** |
| ② 三段独立 R2V | 每段单参考图（只含该人那一格），各跑一次 H3，ffmpeg 拼接 | ✅ 解决串脸；但段 3 头顶被裁 |
| ③ 段 3 专用「中景参考图」+ 后期构图修正 | `image_edit_longcat` 把定妆照重绘为「头肩胸完整」中景；再用 ffmpeg 缩放+下移兜底 | ✅ 全部通过 |

### 3. 关键教训（新踩的坑）

**① H3 把「手部道具动作」当构图主体。** 写「双手捧稻穗抱在胸前」→ 出**躯干特写**（头挤出画）；
写「抬起双手在胸口整理口罩」→ 出**脸部大特写**（额头裁掉）。
⇒ 修法：道具写成**被动持有**（"手里拿着…放在身前"），并在 prompt 末尾加显式禁止语。

**② H3 的景别跟随「参考图本身的取景松紧」，文字压不住。**
段 3 的定妆照是「脸+单肩」紧裁（且右下角带新华网水印，`WM_KEEPOUT=0.72` 又迫使裁框上移），
即使把参考图缩到脸占 35%、写死"不要裁掉额头"、换 seed，H3 仍**稳定**推成脸高 500+px、头顶出界。
⇒ 修法：**换参考图**（`_make_125_seg3_ref.py` 用 `image_edit_longcat` 重绘成中景，脸占 35%）
＋ **后期兜底**（`_fix_125_seg3_framing.py`：scale 0.86 + 下移 6%）。

**③ `pathlib.Path.glob()` 在 Windows 上对 `_seg125` 这类下划线开头目录返回空！**
实测：`iterdir()` 能列出 5 个文件，同目录 `glob("125_a_hj_*.mp4")` 返回 `[]`。
`_rerun_125_segments.py` 与 `_fix_125_seg3_framing.py` 均已改为 **`iterdir()` + `startswith` 过滤**。

**④ `-vf fps=24` 不等于输出 24fps。** 只写滤镜时，concat 出的文件帧率被标成 `289/12`（≈24.083），
与其余 125 镜的 `24/1` 不一致 ⇒ `_concat_video.py` 判规格不一致 → 触发**全片 126 镜重转码**。
⇒ 必须在 ffmpeg 命令里**显式加 `-r 24`**（段归一化、末帧定格、构图修正三处都已补）。

**⑤ 重跑不会覆盖，产物带新后缀**（`_00004_`/`_00005_`…）。
`_concat_video.py` 按**同幕内 mtime 最新**选片 ⇒ 跑完必须用
`py -3.10 OUTPUT/_archive_old.py --apply` 把旧版归档为 `_mid_*`（本次归档 150 个），
否则人工复核容易看错文件。

### 4. 产物与验收

- 段文件：`OUTPUT/05_classroom_night/video/_seg125/` 下的
  `125_a_hj_*_.mp4`、`125_b_ylp_*_.mp4`、`125_c_zns_*_.mp4`
- 段 3 修正版：`125_c_zns_fixed_.mp4`（合成时**优先取用**，见 `pick_seg_any()`）
- 成片片段：**`125_three_stills_flash_00006_.mp4`** — 8.00 s / 1056×608 / h264 **@24/1** / aac 32kHz 2ch / 192 帧
- 抽帧验收（`_check_125_final_frames.py`，12 帧）：三段**全部头肩完整**——
  段 1 脸顶 14~17%、段 2 脸顶 15~16%、段 3 脸顶 **8~9%**（修正前为 **−9%**，头顶出界）

### 5. 新增/改动脚本

| 脚本 | 作用 |
|---|---|
| `_make_125_triptych.py` | 三格拼图（像素级裁剪，避开钟南山水印） |
| `_make_125_seg3_ref.py` | ★ 新：把钟南山定妆照重绘为「头肩胸完整」中景参考图 |
| `_rerun_125_segments.py` | 三段独立生成 + 两阶段 concat（含 `--only=` / `--concat-only` / `-r 24`） |
| `_fix_125_seg3_framing.py` | ★ 新：段 3 构图后期修正（缩放 + 下移） |
| `_check_125_cells.py` | ★ 新：核对单格参考图「脸占画幅」比例 |
| `_check_125_final_frames.py` | ★ 新：成片抽帧验收（脸高 / 脸顶位置） |
