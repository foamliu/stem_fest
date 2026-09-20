# -*- coding: utf-8 -*-
"""下载 50 式冬装**彩色**参考图（2026-09-20）。

为什么必须彩色：第一版拼版用的 `mod1/mod2.jpg` 是**黑白战地照**（战士裹白色
伪装披风），模型于是把服装画成"白披风 + 大檐帽"，帽型完全没被约束。
本次挑的候选全部是**彩色实物照**（军品店实拍 / 博物馆藏 / 复刻品），
每张对应一个明确的"结构特征槽位"，见 `SLOTS`。

用法：
    py -3.10 OUTPUT/_fetch_ref50.py            # 全部下载
    py -3.10 OUTPUT/_fetch_ref50.py cap_full uniform_full
"""
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OUTPUT", "uniform_50shi", "ref2")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# 槽位 -> [(文件名, URL), ...]（同槽位多张 = 备用，跑不通会往下试）
SLOTS = {
    # 交角/护耳棉帽：帽子必须看彩色实物，否则模型退回"解放帽 + 红五角星"
    "cap_front": [
        ("cap_front_laojunpin.jpg",
         "http://a.cdn.zhuolaoshi.cn/user/laojunpin/image/20170208/20170208182398789878.jpg"),
        ("cap_front_997788.jpg",
         "https://pic17.997788.com/_pic_search/00/31/36/46/31364697.jpg"),
    ],
    "cap_side": [
        ("cap_side_laojunpin.jpg",
         "http://a.cdn.zhuolaoshi.cn/user/laojunpin/image/20170208/20170208182375827582.jpg"),
        ("cap_side_laojunpin2.jpg",
         "http://a.cdn.zhuolaoshi.cn/user/laojunpin/image/20170208/20170208182465846584.jpg"),
    ],
    # 完整制服（上装）：需要能看清立领 + 门襟 + 大圆扣 + 四个贴袋
    "uniform_full": [
        ("uniform_full_laojunpin.jpg",
         "https://a.cdn.zhuolaoshi.cn/user/laojunpin/image/20170208/20170208084053565356.jpg"),
        ("uniform_full_laojunpin2.jpg",
         "http://a.cdn.zhuolaoshi.cn/user/laojunpin/image/20170208/2017020813290604604.jpg"),
    ],
    "uniform_set": [
        ("uniform_set_laojunpin.jpg",
         "http://a.cdn.zhuolaoshi.cn/user/laojunpin/image/20170208/20170208132942314231.jpg"),
        ("uniform_set_repro.jpg",
         "https://img.alicdn.com/imgextra/i2/2206470924736/O1CN01ng9COG1kr8VG6NC3U_!!2206470924736.jpg"),
    ],
    # 士兵着装全身照（彩色，作整体廓形参考）
    "wearer": [
        ("wearer_sina.jpg",
         "http://k.sinaimg.cn/n/sinakd2021116s/586/w598h788/20210116/"
         "687f-khstaxs7003808.jpg/w700d1q75cms.jpg"),
        ("wearer_qq.jpg", "http://inews.gtimg.com/newsapp_bt/0/14537393527/641"),
    ],
}


def fetch(url, dst):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": url})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    if len(data) < 3000:
        raise ValueError("文件过小 %d B，疑似占位图" % len(data))
    with open(dst, "wb") as f:
        f.write(data)
    return len(data)


def main():
    want = sys.argv[1:] or list(SLOTS)
    os.makedirs(OUT, exist_ok=True)
    ok = 0
    for slot in want:
        if slot not in SLOTS:
            print("SKIP 未知槽位 %s" % slot)
            continue
        for fname, url in SLOTS[slot]:
            dst = os.path.join(OUT, fname)
            try:
                n = fetch(url, dst)
                print("OK   %-14s %-28s %6.1f KB" % (slot, fname, n / 1024.0))
                ok += 1
                break
            except Exception as e:
                print("FAIL %-14s %-28s %s" % (slot, fname, str(e)[:70]))
    print("\n成功 %d / %d 槽位" % (ok, len(want)))


if __name__ == "__main__":
    main()
