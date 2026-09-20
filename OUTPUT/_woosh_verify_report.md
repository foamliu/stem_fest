# Woosh 接线验收报告（2026-09-20）

- 运行时刻：2026-09-20 18:31:56

| 检查 | 结果 |
|---|---|
| ① 节点注册（WooshLoadFlow, WooshSample, WooshLoadVideo） | ✅ 全部就位 |
| ② model_name 下拉含 4 个主干 | ✅ |
| ③ woosh_sfx（T2A） | ✅ 42.6 s |
| ④ woosh_v2a（V2A） | ✅ 87.5 s |

## 产物与回读（sound_caption）

### T2A

```json
{
  "ok": true,
  "prompt_id": "78d24663-b2cc-41e0-8940-84bab599e803",
  "comfyui": "http://127.0.0.1:8188",
  "tool": "woosh_sfx",
  "workflow": "Woosh 音效生成.json",
  "model": "dflow",
  "checkpoint": "Woosh-DFlow",
  "model_type": "DFlow",
  "seed": 4242,
  "duration_sec": 2.0,
  "latent_frames": 200,
  "steps": 4,
  "cfg": 3.5,
  "subprocess": true,
  "prompt_chars": 65,
  "status": "success",
  "elapsed_sec": 42.6,
  "output_dir": "E:\\code\\stem_fest\\OUTPUT\\sfx",
  "files": [
    {
      "path": "E:\\code\\stem_fest\\OUTPUT\\sfx\\_woosh_verify_t2a_00001.mp3",
      "filename": "_woosh_verify_t2a_00001.mp3",
      "size_kb": 34.0
    }
  ]
}
```

**回读**：`The audio contains a distinct sound of paper being crumpled or rustled. The sound is sharp and brief, with a clear, crisp texture. The sound is consistent with the action of crumpling paper, matching the hint. The sound is likely from a paper bag or similar material.`

### V2A

```json
{
  "ok": true,
  "prompt_id": "6d1c111f-e8ca-4b5c-9bc3-507e40fde758",
  "comfyui": "http://127.0.0.1:8188",
  "tool": "woosh_v2a",
  "workflow": "Woosh 视频配音效.json",
  "model": "dvflow",
  "checkpoint": "Woosh-DVFlow-8s",
  "model_type": "DVFlow",
  "video_input": "E:\\code\\stem_fest\\OUTPUT\\06_trench\\video\\35_sicheng_nods_we_won_00001_.mp4",
  "seed": 5252,
  "duration_sec": 4.0,
  "latent_frames": 400,
  "steps": 4,
  "cfg": 3.5,
  "subprocess": true,
  "prompt_chars": 46,
  "status": "success",
  "elapsed_sec": 87.5,
  "output_dir": "E:\\code\\stem_fest\\OUTPUT\\sfx",
  "files": [
    {
      "path": "E:\\code\\stem_fest\\OUTPUT\\sfx\\_woosh_verify_v2a_00001.mp3",
      "filename": "_woosh_verify_v2a_00001.mp3",
      "size_kb": 56.0
    }
  ]
}
```

**回读**：`The audio contains a single, loud, and sharp vocal burst. It sounds like a shout or yell. The sound is brief and impactful. The audio contains a clear vocalization of a shout, which matches the provided hint. The loudness suggests a sudden, forceful expression.`
