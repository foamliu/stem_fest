
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
