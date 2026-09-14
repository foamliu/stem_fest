# 全片 126 镜生成 · 运行状态

**启动时间**：2026-09-14 07:23
**编排器**：`OUTPUT/_run_all_acts.py`（严格串行，跑完一幕才启下一幕）
**状态文件**：`OUTPUT/_run_all_state.txt`（每幕切换/结束追加一行）
**逐幕日志**：`OUTPUT/_run_act<N>.log`（N = act0/act1/act2/act3/act4/act5）

## 监控命令

```powershell
# ★ 一键看板（产出数 / 规格核对 / 时长量化 / 片长合计）
py -3.10 OUTPUT/_progress.py

# 主生成进度
Get-Content OUTPUT/_run_all_state.txt -Encoding UTF8 -Tail 20

# 收尾补跑进度
Get-Content OUTPUT/_finalize_state.txt -Encoding UTF8 -Tail 20

# 各幕异常扫描
foreach($n in 'act0','act2','act1','act3','act4','act5'){
  $f="OUTPUT/_run_$n.log"
  if(Test-Path $f){ $ok=(Get-Content $f -Encoding UTF8 | Select-String '\[OK\]').Count
    $bad=(Get-Content $f -Encoding UTF8 | Select-String 'SUSPECT|\[X\]|MISSING_REF|SUBMIT_FAIL|NO_OUTPUT|TIMEOUT').Count
    "$n : OK=$ok 异常=$bad" }
}

# 抽帧目视巡检（给几个镜号）
py -3.10 OUTPUT/_grab_frames.py 1 4 19 47 75 99

# 队列与进程（§6.1 #8 纪律）
py -3.10 -c "import json,urllib.request;q=json.load(urllib.request.urlopen('http://127.0.0.1:8188/queue'));print(len(q['queue_running']),len(q['queue_pending']))"
```

## 幕序与镜号

| 顺序 | 幕 | 镜号 | 镜数 | 脚本 | steps |
|:--:|:--:|:--:|:--:|---|:--:|
| 1 | 序幕一 纸飞机 | 1–9 | 9 | `_diag_act0_plane.py` | 10 |
| 2 | 序幕二 启动 | 10–18 | 9 | `_diag_act2_startup.py` | 20 |
| 3 | 第一幕 上甘岭 | 19–46 | 28 | `_diag_act1_trench.py` | 10 |
| 4 | 第二幕 禾下乘凉 | 47–74 | 28 | `_diag_act3_rice.py` | 10 |
| 5 | 第三幕 餐车 | 75–105 | 31 | `_diag_act4_train.py` | 10 |
| 6 | 尾声 归来与揭晓 | 106–126 | 21 | `_diag_act5_finale.py` | 10 |

**合计 126 镜**，预计 13–16 小时。

## 跑完后必做

1. **镜 19 / 39 / 45 / 4 / 5 / 75 / 104 建议 20 步补跑**（环境/运镜剧变镜）：
   ```powershell
   py -3.10 OUTPUT/_diag_act1_trench.py --steps=20 19 39 45
   py -3.10 OUTPUT/_diag_act0_plane.py  --steps=20 4 5
   py -3.10 OUTPUT/_diag_act4_train.py  --steps=20 75 104
   ```
2. **镜 123–126 可降到 4 步提速**（纯字幕 / 静帧 / 定格）：
   ```powershell
   py -3.10 OUTPUT/_diag_act5_finale.py --steps=4 123 124 125 126
   ```
3. **台词人耳验收**（或 `qwen3_asr` 转写核对）—— 尤其长台词镜 39/60/97/99/116/118
4. **钟南山镜（79–105）检查「新华网」水印有无被画进画面**
