# -*- coding: utf-8 -*-
"""
可选增强：抓取东财行业板块「官方日K真实涨跌幅」(push2his)。
- 仅在 push2/push2his 可达时有效；不可达时【快速退出】，不影响主流程(finalize 回退 computed)。
- 命中后写入 .cache/klines_{DATE}.json（key=板块 bk），finalize.py 检测到即升级为 official 口径。
用法：python fetch_klines.py [YYYY-MM-DD]
"""
import json, time, random, sys, io, os
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATE = os.environ.get("REPORT_DATE") or (sys.argv[1] if len(sys.argv) > 1 else "2026-07-24")
DATE_C = DATE.replace("-", "")
CACHE_DIR = ".cache"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

S = requests.Session()
S.headers.update({"User-Agent": UA})
_last = [0.0]


def em_get(url, params=None, headers=None, timeout=20, retries=3):
    """push2his 专用：限流 + 断连重建；失败抛异常由调用方决定降级。"""
    global S
    last_err = None
    for att in range(retries):
        w = 1.0 - (time.time() - _last[0])
        if w > 0:
            time.sleep(w + random.uniform(0.05, 0.3))
        try:
            r = S.get(url, params=params, headers=headers, timeout=timeout)
            _last[0] = time.time()
            if r.status_code == 200:
                return r
            last_err = f"HTTP {r.status_code}"
        except Exception as e:
            last_err = repr(e)[:120]
            S = requests.Session()
            S.headers.update({"User-Agent": UA})
        _last[0] = time.time()
        time.sleep(1.0 * (att + 1))
    raise RuntimeError(f"em_get 失败({retries}次): {last_err}")


def main():
    bpath = os.path.join(CACHE_DIR, f"boards_{DATE_C}.json")
    if not os.path.exists(bpath):
        print("! 未找到 boards 缓存，请先运行 fetch_data.py", flush=True)
        return
    boards = json.load(open(bpath, encoding="utf-8"))
    kurl = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    beg = int(DATE_C) - 10
    kpath = os.path.join(CACHE_DIR, f"klines_{DATE_C}.json")
    kcache = json.load(open(kpath, encoding="utf-8")) if os.path.exists(kpath) else {}

    def one(bk):
        kp = {"secid": f"90.{bk}", "klt": "101", "fqt": "1",
              "fields1": "f1,f2,f3,f4,f5,f6",
              "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
              "beg": str(beg), "end": DATE_C}
        rr = em_get(kurl, params=kp,
                    headers={"User-Agent": UA, "Referer": "https://quote.eastmoney.com/"})
        data = rr.json().get("data") or {}
        for k in (data.get("klines") or []):
            p = k.split(",")
            if p[0] == DATE:
                return p
        return None

    # 探测首板：不可达则快速退出（避免 127 块逐个重试浪费时间）
    print(f"[klines] 探测 push2his 可达性 ({boards[0]['bk']} {boards[0]['name']}) ...", flush=True)
    try:
        hit = one(boards[0]["bk"])
    except Exception as e:
        print(f"! push2/push2his 不可达，跳过官方K线(将用 computed 回退): {e!r}", flush=True)
        return
    if hit is None:
        print(f"! 首板无 {DATE} K线，跳过", flush=True)
        return
    kcache[boards[0]["bk"]] = hit

    print(f"[klines] push2his 可达，抓取 {len(boards)} 个板块 ...", flush=True)
    for i, it in enumerate(boards[1:], 2):
        bk = it["bk"]
        if bk in kcache:
            continue
        try:
            h = one(bk)
        except Exception as e:
            print(f"  ! {bk} {it['name']} 失败: {e!r}", flush=True)
            continue
        if h is None:
            print(f"  ! {bk} {it['name']} 无 {DATE} K线", flush=True)
            continue
        kcache[bk] = h
        if i % 20 == 0:
            json.dump(kcache, open(kpath, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"  ... {i}/{len(boards)}", flush=True)

    json.dump(kcache, open(kpath, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"[klines] 完成：{len(kcache)}/{len(boards)} 个板块官方K线已缓存 → {kpath}")


if __name__ == "__main__":
    main()
