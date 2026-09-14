# -*- coding: utf-8 -*-
"""把 `_diag_act0_plane.py` 的 ComfyUI 基础段落（_api … main）复制到目标脚本末尾，
只替换脚本专属的标识串（CLIENT_ID / 上传前缀 / 输出前缀 / 报告标题）。

★ 为什么用生成而不是手抄：3 个新幕脚本的 plumbing 必须与已有 3 个脚本**逐字一致**
  （README §7.1「每幕一个独立脚本、互不引用」⇒ 只能复制，但人抄会漂）。
  生成方式保证 6 个脚本的 ComfyUI 注入逻辑完全相同。

用法：py -3.10 OUTPUT/_make_act_scripts.py <目标脚本> <CLIENT_ID> <上传前缀> <输出前缀> <报告标题>
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "OUTPUT", "_diag_act0_plane.py")

# 基础段的起点/终点锚点
START = "# ────────────────────────────────────────────────────────────── ComfyUI 基础"
END_MARK = 'if __name__ == "__main__":'


def extract_plumbing():
    src = io.open(SRC, encoding="utf-8").read()
    i = src.index(START)
    return src[i:]


def main():
    dst, client_id, up_prefix, out_prefix, report_title = sys.argv[1:6]
    dst_path = os.path.join(ROOT, dst) if not os.path.isabs(dst) else dst

    block = extract_plumbing()

    # 逐项替换脚本专属标识（顺序重要：先长后短，避免子串误伤）
    # 注意：CLIENT_ID / 各前缀常量定义在**文件头**，不在本基础段内 ⇒ 允许未命中
    subs = [
        ('return "act0v_" +', 'return "%s" +' % up_prefix),
        ('prefix = "act0vs20/%02d_%s"', 'prefix = "%s/%%02d_%%s"' % out_prefix),
        ('f.write("序幕一《纸飞机》视频片段 · 生成报告（跳过首帧，直接 R2V/T2V，镜 1-9）\\n")',
         'f.write("%s\\n")' % report_title),
        ('boundary = "----act0videos"', 'boundary = "----%s"' % client_id.replace("v_", "")),
    ]
    missing = []
    for a, b in subs:
        if a not in block:
            missing.append(a[:60])
            continue
        block = block.replace(a, b)
    if missing:
        raise SystemExit("以下锚点未命中，请检查基础段是否被改动：\n  " + "\n  ".join(missing))

    with io.open(dst_path, "a", encoding="utf-8") as f:
        f.write("\n" + block)

    print("已追加 plumbing -> %s" % os.path.relpath(dst_path, ROOT))
    print("  替换：CLIENT_ID=%s  上传前缀=%s  输出前缀=%s" % (client_id, up_prefix, out_prefix))


if __name__ == "__main__":
    main()
