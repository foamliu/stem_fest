# -*- coding: utf-8 -*-
"""全片进度看板：产出数 / 异常 / 时长量化核对 / 剩余预估。"""
import glob
import json
import os
import subprocess
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRS = [("01_paper_plane", 1, 9), ("03_classroom_day", 10, 18),
        ("06_trench", 19, 46), ("07_rice_field", 47, 74),
        ("08_train_dining", 75, 105), ("05_classroom_night", 106, 126)]

# 剧本名义时长 → H3 量化后播放时长（17k+5 帧 @24fps，实测值）
QUANT = {2: 2.33, 3: 3.04, 4: 4.46, 5: 5.17, 6: 6.58, 7: 7.29, 8: 8.00, 9: 9.42, 10: 10.12}


def probe(p):
    exe = "ffprobe"
    out = subprocess.run([exe, "-v", "error", "-show_entries",
                          "format=duration:stream=width,height,codec_type,sample_rate,channels",
                          "-of", "json", p], capture_output=True, text=True)
    d = json.loads(out.stdout)
    dur = float(d["format"]["duration"])
    w = h = None
    ac = None
    for s in d["streams"]:
        if s.get("codec_type") == "video":
            w, h = s["width"], s["height"]
        if s.get("codec_type") == "audio":
            ac = "%s %sch" % (s.get("sample_rate"), s.get("channels"))
    return dur, w, h, ac


def main():
    total = 0
    allrows = []
    print("幕                        镜号       产出   状态")
    print("-" * 62)
    for d, lo, hi in DIRS:
        vd = os.path.join(ROOT, "OUTPUT", d, "video")
        files = sorted(glob.glob(os.path.join(vd, "*.mp4")))
        total += len(files)
        want = hi - lo + 1
        mark = "OK" if len(files) >= want else "跑中"
        print("%-24s %3d-%-3d  %2d/%-2d  %s" % (d, lo, hi, len(files), want, mark))
        for f in files:
            allrows.append((d, f))
    print("-" * 62)
    print("合计 %d / 126 = %.1f%%\n" % (total, total * 100.0 / 126))

    # 规格与时长核对
    bad_res, bad_ac, durs = [], [], []
    for d, f in allrows:
        dur, w, h, ac = probe(f)
        durs.append(dur)
        if (w, h) != (1056, 608):
            bad_res.append((os.path.basename(f), w, h))
        if ac != "32000 2ch":
            bad_ac.append((os.path.basename(f), ac))
    print("规格核对：分辨率异常 %d 个 %s" % (len(bad_res), bad_res[:3] if bad_res else ""))
    print("          音轨异常  %d 个 %s" % (len(bad_ac), bad_ac[:3] if bad_ac else ""))
    vals = set(round(x, 2) for x in durs)
    ok_vals = set(QUANT.values())
    off = sorted(v for v in vals if v not in ok_vals)
    print("          时长取值 %s" % sorted(vals))
    print("          非量化值 %s" % (off if off else "无（全部落在 17k+5 档）"))
    print("片长合计：%.1f s（%.1f 分）" % (sum(durs), sum(durs) / 60.0))


if __name__ == "__main__":
    main()
