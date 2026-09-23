# 《如愿·看见》音效生产与铺位报告

- 更新时刻：**2026-09-21**（本次补 SFX-17 / SFX-18，并完成全片铺位 → 成片）
- 工具：`stable_audio_3_sfx`（Stable Audio 3 Medium）· `woosh_sfx`（Sony Woosh DFlow）
- 素材目录：`OUTPUT/sfx/film/`　铺位脚本：`OUTPUT/_mix_sfx.py`　客观画像：`OUTPUT/_diag_sfx_profile.py`
- **铺位规格唯一出处**：`storyboard.md` §音效铺位

## 1. 素材清单与**客观画像**（判据主证据）

口径（`_diag_sfx_profile.py`）：**整体**=整段 RMS dBFS；**静音**=<−45 dB 的 50 ms 窗占比；
**占空**=>−45 dB 的窗占比；**低/中/高**= <250 Hz / 250–4k / >4k 的能量占比；
**质心**=谱质心 Hz；**4Hz**=音节速率段调制能量占比；**crest**=波峰因数 dB。

| 文件 | 时长 | 整体 | 峰值 | 静音 | 占空 | 低 | 中 | 高 | 质心Hz | 4Hz | crest |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SFX-01_paper_snap_00001 | 2.04 | −35.1 | −3.0 | 90% | 10% | 23% | 49% | 28% | 3051 | 0.162 | 32.1 |
| SFX-02_device_beep_00001 | 1.49 | −36.1 | −15.0 | 93% | 7% | 13% | 86% | 1% | 2499 | 0.056 | 21.1 |
| SFX-03_holo_chime_00001 | 2.04 | −20.9 | −3.7 | 55% | 45% | 0% | 100% | 0% | 1174 | 0.001 | 17.3 |
| SFX-04_heartbeat_00001 | 2.04 | −18.6 | 0.8 | 60% | 40% | 100% | 0% | 0% | 23 | 0.032 | 19.4 |
| SFX-05_key_once_00001 | 1.49 | −33.1 | −2.3 | 83% | 17% | 31% | 49% | 20% | 2079 | 0.036 | **30.8** |
| SFX-06_key_rising_00001 | 3.99 | −37.5 | −6.3 | 62% | 38% | 21% | 52% | 28% | 2963 | 0.115 | **31.2** |
| SFX-07_rice_leaf_00001 | 2.97 | −37.6 | −8.6 | 66% | 34% | 1% | 19% | 80% | 5057 | 0.007 | 29.0 |
| SFX-08_seat_creak_00001 | 2.04 | −23.9 | 1.0 | 45% | 55% | 73% | 25% | 2% | 401 | 0.056 | 24.9 |
| SFX-09_soft_laugh_00001 | 1.99 | −31.1 | −14.0 | 82% | 18% | 96% | 4% | 0% | 217 | 0.039 | 17.1 |
| SFX-10_wind_open_air_00001 | 6.04 | −23.8 | −6.3 | 31% | 69% | 94% | 6% | 0% | 66 | 0.034 | 17.5 |
| SFX-11_trench_wind_shovel_00001 | 7.99 | −34.3 | −4.3 | 13% | 87% | 50% | 39% | 10% | 1356 | 0.038 | 30.0 |
| SFX-12_rice_cicada_bed_00001 | 11.98 | −26.3 | −10.4 | 13% | 87% | 5% | 27% | 69% | 4616 | 0.000 | 15.9 |
| SFX-13_cicada_stop_00001 | 3.99 | −28.6 | −14.3 | 42% | 58% | 0% | 50% | 50% | 4090 | 0.018 | 14.2 |
| SFX-14_hsr_rumble_00002 | 10.03 | −14.9 | −2.1 | 1% | 99% | 99% | 1% | 0% | 70 | 0.005 | 12.9 |
| SFX-14b_hsr_interior_00001 | 10.03 | −14.0 | −2.0 | 8% | 92% | 100% | 0% | 0% | 71 | 0.004 | 12.0 |
| **SFX-14c_hsr_woosh_00001**（采用） | 9.99 | −20.2 | −7.7 | 0% | 100% | 72% | 28% | 0% | 175 | 0.003 | 12.5 |
| SFX-15_rail_rhythm_00001 | 7.99 | −25.5 | −4.9 | 19% | 81% | 52% | 48% | 0% | 445 | 0.009 | 20.6 |
| SFX-16_platform_stop_00001 | 7.99 | −17.7 | 0.6 | 21% | 79% | 6% | **91%** | 3% | 1110 | 0.005 | 18.2 |
| ~~SFX-17_classroom_chatter_00001~~（**废**） | 3.99 | **−44.9** | −17.8 | **63%** | 37% | 43% | 34% | 23% | 2000 | 0.023 | 27.1 |
| **SFX-17_classroom_chatter_00002**（采用） | 5.02 | −32.8 | −17.7 | 11% | 89% | 13% | **86%** | 1% | 606 | 0.006 | 15.1 |
| SFX-17b_classroom_chatter_woosh_00001（备选） | 4.99 | −29.4 | −11.9 | 0% | 100% | 19% | 81% | 0% | 655 | 0.008 | 17.5 |
| **SFX-18_typing_stop_00001**（采用） | 2.97 | −37.5 | −5.8 | 68% | 32% | 28% | 54% | 18% | 2542 | 0.048 | **31.7** |

## 2. 判收口径修订：`sound_caption` **不可靠**（2026-09-21 实测）

本节原铁律是"必须 `sound_caption` 回读验收"。实测该模型**认不出具体来源**：

| 文件 | sound_caption 回读 | 事实 | 判定 |
|---|---|---|---|
| `SFX-12_rice_cicada_bed`（**已采纳**的蝉鸣/稻浪底噪） | *"continuous high-pitched whirring … **vacuum cleaner**"* | 蝉鸣+稻浪 | ❌ **模型错** |
| `SFX-17_..._00001` | *"a **vehicle** … passing by … brief period of silence"* | 首版确实太稀疏（静音 63%、−44.9 dB） | ⚠️ 偶然说中 |
| `SFX-17_..._00002` | *"contains **speech**, but unintelligible … muffled"* | 群杂 | ✅ 对 |
| `SFX-18_typing_stop` | *"high-pitched abrasive **scraping** … machinery"* | 键盘敲击（crest 31.7 同已采纳的键盘） | ❌ 模型错 |

⇒ **新口径**：回读只当**线索**；判据 = **客观画像 + 与已采纳同族素材对比 + 听感复核**。
本机可复算的画像脚本：`py -3.10 OUTPUT/_diag_sfx_profile.py [SFX-17 ...]`。

## 3. 本次补跑的两条（原 16 条清单里缺失）

逐镜表里写了 `音效：` 但**没有对应素材**的两处，现已补齐：

| ID | 镜 | 意图 | 工具 | seed | 时长 | 判定依据 |
|:--:|:--:|---|:--:|:--:|:--:|---|
| SFX-17 | 9 | 教室群杂 | `stable_audio_3_sfx` | 9203 | 5.0 s | 中频 **86%**、静音 11%、crest 15.1（同到站底噪一族）+ 回读"muffled speech" ⇒ **采纳**（首版 seed 9201 因 −44.9 dB / 静音 63% 判废） |
| SFX-18 | 109 | 键盘声突然停住 | `stable_audio_3_sfx` | 9202 | 3.0 s | crest **31.7** ≈ 已采纳 SFX-05/06（30.8/31.2）+ 静音 68%（"敲完停住"本就该后半静） ⇒ **采纳** |

prompt 全文（照抄用）：

```
SFX-17  quiet junior high classroom ambience, a few students chatting softly and indistinctly in the background, chairs shifting, paper rustling, low level room tone, no music
        （二版改写）continuous steady ambience of a busy middle school classroom, several students murmuring and chatting softly at a constant level throughout, chairs scraping occasionally, steady room tone, even loudness from start to end, no music, no single loud event
SFX-17b students talking quietly in a classroom, several muffled voices chatting at the same time, continuous low background chatter, no music     （woosh dflow）
SFX-18  fast typing on a laptop keyboard that stops abruptly and completely, then only a quiet room tone remains, close-up recording, no music
```

## 4. 铺位与成片（本次落地）

| 项 | 值 |
|---|---|
| 脚本 | `py -3.10 OUTPUT/_mix_sfx.py`（`--list` / `--dry-run` / `--film= --out=` 可叠在 BGM 版上） |
| 铺位 | **25 条**（bed 13 / point 12），全部满足"段长 = min(音效时长, 本镜剩余)" |
| 电平 | 按**实测响度归一化**：bed → **−34 LUFS**、point → **−27 LUFS**（素材源响度差 30 dB） |
| 产物 | `full_cut_sfx.mp4`（音效，I = −12.7 / Peak −0.7）；`full_cut_bgm_sfx.mp4`（**BGM+音效**，I = −13.2 / Peak −0.8） |
| 验收 | 画面 MD5 与母版**逐字节一致**；台词延迟 −4.98 ms / 相关 0.9978；音效层只在铺位窗口（对照窗口 ≈ −49 dB） |

## 5. 仍未做的三类（**不属于音效模型**，storyboard 已定）

| 类型 | 镜 | 该用什么 | 状态 |
|---|:--:|---|:--:|
| 播报语音（可辨识词句） | 81, 102 | `qwen3_tts`（写死播报词 + 固定 speaker/seed） | ⏳ 未做 |
| 音乐动机（口琴/竹笛/钢琴/轻快音乐） | 3, 4, 45, 73, 104 | `ace_step_t2audio`（或现成音源） | ⏳ 未做 |
| 寂静 | 111, 113, 119 | 留白（**不要生成**） | ✅ 已是目标状态 |
