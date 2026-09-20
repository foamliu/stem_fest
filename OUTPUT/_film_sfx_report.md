# 《如愿·看见》音效生产报告

- 运行时刻：2026-09-20 21:51:07
- 工具：`stable_audio_3_sfx`（Stable Audio 3 Medium）· `woosh_sfx`（Sony Woosh DFlow）
- 产物目录：`OUTPUT/sfx/film/`

> ⚠️ **caption 是 LAION 音效描述模型的回读**，只描述"听到了什么音色、像什么来源"。
> 判收口径：**它说得对不对**，不看 ComfyUI 报没报 success。

| ID | 镜 | 音效 | 工具 | 时长 | 耗时 | 产物 | sound_caption 回读 |
|---|:--:|---|:--:|:--:|:--:|---|---|
| SFX-01 | 5 | 纸飞机被夹住的轻响 | `stable_audio_3_sfx` | 2.0s | — | `SFX-01_paper_snap_00001.mp3` | ⏭ 本次跳过（已有产物） |
| SFX-02 | 17 | 轻微「滴」声 | `stable_audio_3_sfx` | 1.5s | 807.8s | `SFX-02_device_beep_00001.mp3` | 00. The audio contains a continuous, high-pitched electronic tone, resembling a sine wave or a test signal. |
| SFX-03 | 117,122 | 轻微电子音（全息屏） | `stable_audio_3_sfx` | 2.0s | 337.6s | `SFX-03_holo_chime_00001.mp3` | The audio features a distinct, high-pitched, and sustained electronic tone. The sound is pure and consistent in pitch and volume, resembling a sine wave or a similar synthesized sound. This is an electronic sound effect, |
| SFX-04 | 110 | 心跳声，一声 | `stable_audio_3_sfx` | 2.0s | 650.9s | `SFX-04_heartbeat_00001.mp3` | A distinct, high-pitched, sustained tone, characteristic of a siren or an alarm. The sound is a siren or an alarm, indicating an emergency or warning. |
| SFX-05 | 120 | 键盘声，一声 | `stable_audio_3_sfx` | 1.5s | 452.2s | `SFX-05_key_once_00001.mp3` | start, end with a thud. The audio contains the characteristic sound of a stapler being used. The initial thud is the staple being flipped, and the final thud is the staple being placed down. |
| SFX-06 | 121 | 键盘声渐起 | `stable_audio_3_sfx` | 4.0s | 461.4s | `SFX-06_key_rising_00001.mp3` | The audio features a distinct, sharp clicking sound, followed by a brief, high-pitched whirring or buzzing noise. The clicking is singular and clear, while the whirring is short and continuous. This sound event is charac |
| SFX-07 | 50 | 稻叶拨动声 | `stable_audio_3_sfx` | 3.0s | 717.4s | `SFX-07_rice_leaf_00001.mp3` | The audio contains a distinct rustling sound. It is a dry, crinkling noise, consistent with the movement of paper or plastic. The sound is relatively close to the microphone. The audio likely captures the sound of someon |
| SFX-08 | 83 | 座位轻响 | `stable_audio_3_sfx` | 2.0s | 455.4s | `SFX-08_seat_creak_00001.mp3` | The audio begins with a distinct, sharp click, immediately followed by a brief, high-pitched whirring sound that quickly fades. The whirring sound then abruptly ceases. The combination of a click and a whirring sound sug |
| SFX-09 | 23 | 轻笑声 | `woosh_sfx` | 2.0s | 778.2s | `SFX-09_soft_laugh_00001.mp3` | The audio features a distinct, sharp, and somewhat metallic click sound. This sound is characteristic of a switch being activated or a small mechanical action, such as a button being pressed or a switch being activated. |
| SFX-10 | 4 | 风声（纸飞机掠过校园） | `stable_audio_3_sfx` | 6.0s | 799.5s | `SFX-10_wind_open_air_00001.mp3` | The audio features a distinct whooshing sound, followed by a low rumble. The whooshing sound is continuous and consistent, suggesting a large object moving at high speed. The rumble is deep and resonant. The audio likely |
| SFX-11 | 19,27 | 风声＋铁锹声（战壕） | `stable_audio_3_sfx` | 8.0s | 525.0s | `SFX-11_trench_wind_shovel_00001.mp3` | The audio contains a distinct sound of a vehicle passing by. The sound begins with a low rumble, quickly escalating into a higher-pitched whine, then diminishing as the vehicle moves away. The sound is relatively close a |
| SFX-12 | 47,52,64,106 | 稻田蝉鸣与风吹稻浪 | `stable_audio_3_sfx` | 12.0s | 576.5s | `SFX-12_rice_cicada_bed_00001.mp3` | The audio features a continuous, high-pitched whirring sound, consistent with a rapidly spinning motor or fan. The sound is steady and has a mechanical quality. This is likely the sound of a vacuum cleaner in operation,  |
| SFX-13 | 18 | 蝉鸣骤停 | `stable_audio_3_sfx` | 4.0s | 458.6s | `SFX-13_cicada_stop_00001.mp3` | The audio contains a high-pitched, sustained tone. The tone is constant and unwavering, with no discernible variations in pitch or volume. The sound is very clean and clear. The audio is a recording of a pure tone, likel |
| SFX-14 | 75,91 | 高铁低频轰响 | `stable_audio_3_sfx` | 10.0s | 902.4s | ❌ None |  |
| SFX-15 | 79 | 车轮与铁轨的节奏声 | `stable_audio_3_sfx` | 8.0s | 475.9s | `SFX-15_rail_rhythm_00001.mp3` | The audio features a vehicle, likely a car, accelerating rapidly. The engine noise is prominent, with a distinct high-pitched whine and a rapid increase in RPM. The sound is consistent with a car speeding up. The audio c |
| SFX-16 | 102,104 | 高铁到站环境底噪 | `stable_audio_3_sfx` | 8.0s | 289.2s | `SFX-16_platform_stop_00001.mp3` | The audio features the distinct sound of a vehicle, specifically a car, passing by. The sound includes the engine noise, tire noise, and the whooshing sound of wind. The recording is relatively clear, capturing the sound |

## prompt 全文（照抄用）

**SFX-01**（镜 5，sa3，2.0s，seed 5101）

```
a single soft paper snap, two fingers pinching a paper airplane out of the air, close perspective, quiet classroom, no music
```

**SFX-02**（镜 17，sa3，1.5s，seed 5102）

```
one single short soft electronic beep, small device UI tick, close-up, quiet room, no music
```

**SFX-03**（镜 117,122，sa3，2.0s，seed 5103）

```
soft futuristic hologram chime, gentle single electronic tone, clean, sci-fi UI, no music
```

**SFX-04**（镜 110，sa3，2.0s，seed 5104）

```
one single deep heartbeat thump, close and intimate, quiet room tone, no music
```

**SFX-05**（镜 120，sa3，1.5s，seed 5105）

```
one single mechanical keyboard key press, crisp and close, quiet room, no music
```

**SFX-06**（镜 121，sa3，4.0s，seed 5106）

```
mechanical keyboard typing gradually picking up speed, several keys per second, quiet room, close perspective, no music
```

**SFX-07**（镜 50，sa3，3.0s，seed 5107）

```
hands pushing apart tall rice plant leaves, dry leaf rustle, close perspective, sunny field, no music
```

**SFX-08**（镜 83，sa3，2.0s，seed 5108）

```
train seat cushion creak and a faint metal click as someone sits down, close, no music
```

**SFX-09**（镜 23，woosh，2.0s，seed 5109）

```
a few soft quiet chuckles from one person, short, gentle, clean recording
```

**SFX-10**（镜 4，sa3，6.0s，seed 5110）

```
open air wind blowing past, medium strength, clean field recording, no music
```

**SFX-11**（镜 19,27，sa3，8.0s，seed 5111）

```
wind across a dirt trench, an occasional shovel cutting into soil, distant and open, no music
```

**SFX-12**（镜 47,52,64,106，sa3，12.0s，seed 5112）

```
summer rice field ambience, wind through dense rice leaves, loud cicadas, natural field recording, no music
```

**SFX-13**（镜 18，sa3，4.0s，seed 5113）

```
loud summer cicadas abruptly stopping into silence, hard cut, outdoor field recording, no music
```

**SFX-14**（镜 75,91，sa3，10.0s，seed 5114）

```
high speed train interior low frequency rumble and hum, constant, close perspective, no music
```

**SFX-15**（镜 79，sa3，8.0s，seed 5115）

```
train wheels rolling over rail joints in a steady rhythm, clickety-clack, close, no music
```

**SFX-16**（镜 102,104，sa3，8.0s，seed 5116）

```
high speed train slowing to a stop, brakes and rail friction fading, station ambience, no music
```
