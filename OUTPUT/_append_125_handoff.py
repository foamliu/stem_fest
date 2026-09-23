# -*- coding: utf-8 -*-
"""向 _RERUN_HANDOFF.md 追加「镜 125 修复」小节（幂等：已存在则跳过）。"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOC = ROOT / "OUTPUT" / "_RERUN_HANDOFF.md"
MARK = "## 九、镜 125（三帧历史人物闪回）脸部错误修复"

SECTION = """

---

{mark}（2026-09-21 晚）

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
""".format(mark=MARK)


def main() -> int:
    t = DOC.read_text(encoding="utf-8")
    if MARK in t:
        print("[skip] 已存在该小节")
        return 0
    DOC.write_text(t.rstrip("\n") + SECTION, encoding="utf-8")
    print("[ok] 已追加，文档现 %d 行" % len(DOC.read_text(encoding="utf-8").splitlines()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
