# -*- coding: utf-8 -*-
"""
A股市场情绪日报 —— 数据抓取（阶段一：纯抓取，写 .cache/）
数据源（均为免费、可在海外 GitHub Actions runner 访问的东财 datacenter）：
  1. 东方财富 datacenter  RPT_DAILYBILLBOARD_DETAILSNEW  → 全市场龙虎榜
  2. 同花顺 zx.10jqka     getharden                      → 当日强势股 + 题材归因 reason（best-effort）
  3. 东方财富 datacenter  RPT_VALUEANALYSIS_DET          → 指定日全市场个股收盘/涨跌幅/所属行业
  4. 东方财富 datacenter  RPT_VALUEINDUSTRY_DET          → 一级行业板块清单（可靠，不依赖 push2）
说明：行业板块「官方日K真实涨跌幅」为可选增强，由 fetch_klines.py 负责（push2 不可达时回退 computed）。
      本脚本只产出 4 个缓存（lhb/ths/snap/boards），聚合与行业涨跌幅计算在 finalize.py 完成。
用法：python fetch_data.py [YYYY-MM-DD]   或设环境变量 REPORT_DATE
"""
import json, time, random, sys, io, os
from collections import defaultdict
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATE = os.environ.get("REPORT_DATE") or (sys.argv[1] if len(sys.argv) > 1 else "2026-07-24")
DATE_C = DATE.replace("-", "")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"

EM_SESSION = requests.Session()
EM_SESSION.headers.update({"User-Agent": UA})
EM_MIN_INTERVAL = 1.0
_em_last = [0.0]


def em_get(url, params=None, headers=None, timeout=20, retries=4, **kw):
    """东财统一入口：串行限流 + 会话复用 + 断连重试，避免被风控封 IP"""
    global EM_SESSION
    last_err = None
    for att in range(retries):
        wait = EM_MIN_INTERVAL - (time.time() - _em_last[0])
        if wait > 0:
            time.sleep(wait + random.uniform(0.05, 0.35))
        try:
            r = EM_SESSION.get(url, params=params, headers=headers, timeout=timeout, **kw)
            _em_last[0] = time.time()
            if r.status_code == 200:
                return r
            last_err = f"HTTP {r.status_code}"
        except Exception as e:
            last_err = repr(e)[:120]
            EM_SESSION = requests.Session()          # 断连后重建会话
            EM_SESSION.headers.update({"User-Agent": UA})
        _em_last[0] = time.time()
        time.sleep(1.2 * (att + 1) + random.uniform(0.2, 0.8))
    raise RuntimeError(f"em_get 失败({retries}次): {url} | {last_err}")


CACHE_DIR = ".cache"


def cached(name, fn):
    """分步缓存，避免重跑时重复请求"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    p = os.path.join(CACHE_DIR, f"{name}_{DATE_C}.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            print(f"      (读取缓存 {p})", flush=True)
            return json.load(f)
    v = fn()
    with open(p, "w", encoding="utf-8") as f:
        json.dump(v, f, ensure_ascii=False)
    return v


def em_datacenter(report, filter_str, page_size=500, page=1, sort_cols="", sort_types="-1"):
    params = {
        "reportName": report, "columns": "ALL", "filter": filter_str,
        "pageNumber": str(page), "pageSize": str(page_size),
        "sortColumns": sort_cols, "sortTypes": sort_types,
        "source": "WEB", "client": "WEB",
    }
    r = em_get(DATACENTER_URL, params=params,
               headers={"Referer": "https://data.eastmoney.com/"})
    d = r.json()
    res = d.get("result") or {}
    return res.get("data") or [], res.get("pages") or 0, res.get("count") or 0


# ────────────────────────────── 1. 全市场龙虎榜 ──────────────────────────────
def fetch_lhb(date):
    print(f"[1/4] 抓取全市场龙虎榜 {date} ...", flush=True)
    rows, pages, count = em_datacenter(
        "RPT_DAILYBILLBOARD_DETAILSNEW",
        f"(TRADE_DATE>='{date}')(TRADE_DATE<='{date}')",
        page_size=500, sort_cols="BILLBOARD_NET_AMT", sort_types="-1")
    recs = []
    for r in rows:
        recs.append({
            "code": r.get("SECURITY_CODE", ""),
            "name": r.get("SECURITY_NAME_ABBR", ""),
            "close": r.get("CLOSE_PRICE") or 0,
            "change_pct": round(float(r.get("CHANGE_RATE") or 0), 2),
            "net_buy": float(r.get("BILLBOARD_NET_AMT") or 0),
            "buy_amt": float(r.get("BILLBOARD_BUY_AMT") or 0),
            "sell_amt": float(r.get("BILLBOARD_SELL_AMT") or 0),
            "deal_amt": float(r.get("BILLBOARD_DEAL_AMT") or 0),
            "amount": float(r.get("ACCUM_AMOUNT") or 0),
            "turnover_pct": round(float(r.get("TURNOVERRATE") or 0), 2),
            "deal_ratio": round(float(r.get("DEAL_AMOUNT_RATIO") or 0), 2),
            "reason": r.get("EXPLANATION", ""),
            "explain": r.get("EXPLAIN", ""),
            "free_cap": float(r.get("FREE_MARKET_CAP") or 0),
            "market": r.get("SECUCODE", "")[-2:],
            "d1": r.get("D1_CLOSE_ADJCHRATE"),
            "d5": r.get("D5_CLOSE_ADJCHRATE"),
        })
    print(f"      → {len(recs)} 条记录 (接口 count={count})", flush=True)
    return recs


# ─────────────────────── 2. 同花顺强势股 + 题材归因（best-effort） ────────────────────────
def fetch_ths(date):
    print(f"[2/4] 抓取同花顺当日强势股题材归因 {date} ...", flush=True)
    url = (f"http://zx.10jqka.com.cn/event/api/getharden/"
           f"date/{date}/orderby/date/orderway/desc/charset/GBK/")
    r = requests.get(url, headers={"User-Agent": UA}, timeout=15)
    d = r.json()
    if d.get("errocode", 0) != 0:
        raise RuntimeError(f"同花顺热点错误: {d.get('errormsg')}")
    rows = d.get("data") or []
    out = []
    for x in rows:
        tags = [t.strip() for t in str(x.get("reason") or "").split("+") if t.strip()]
        out.append({
            "code": x.get("code", ""),
            "name": x.get("name", ""),
            "close": float(x.get("close") or 0),
            "change_pct": round(float(x.get("zhangfu") or 0), 2),
            "turnover_pct": round(float(x.get("huanshou") or 0), 2),
            "amount": float(x.get("chengjiaoe") or 0),
            "big_order": float(x.get("ddejingliang") or 0),
            "reason": x.get("reason", ""),
            "tags": tags,
            "market": x.get("market", ""),
        })
    print(f"      → {len(out)} 只强势股", flush=True)
    return out


# ───────────────── 3. 指定日全市场个股涨跌幅 + 所属行业 ─────────────────
def fetch_market_snapshot(date):
    print(f"[3/4] 抓取 {date} 全市场个股快照(分页) ...", flush=True)
    all_rows, page = [], 1
    while True:
        rows, pages, count = em_datacenter(
            "RPT_VALUEANALYSIS_DET", f"(TRADE_DATE='{date}')",
            page_size=500, page=page, sort_cols="TOTAL_MARKET_CAP", sort_types="-1")
        if not rows:
            break
        all_rows.extend(rows)
        print(f"      page {page}/{(count // 500) + 1} +{len(rows)} (累计 {len(all_rows)}/{count})", flush=True)
        if len(all_rows) >= count or page > 20:
            break
        page += 1
    snap = {}
    for r in all_rows:
        code = r.get("SECURITY_CODE", "")
        if not code:
            continue
        snap[code] = {
            "code": code,
            "name": r.get("SECURITY_NAME_ABBR", ""),
            "close": r.get("CLOSE_PRICE") or 0,
            "change_pct": round(float(r.get("CHANGE_RATE") or 0), 2),
            "board_name": r.get("BOARD_NAME", ""),
            "board_code": str(r.get("ORIGINALCODE") or ""),
            "mcap": float(r.get("TOTAL_MARKET_CAP") or 0),
            "pe_ttm": r.get("PE_TTM"),
        }
    print(f"      → 全市场 {len(snap)} 只", flush=True)
    return snap


# ─────────────────── 4. 一级行业板块清单（datacenter，可靠） ───────────────────
def fetch_boards(date):
    print(f"[4/4] 抓取东财一级行业板块清单(datacenter RPT_VALUEINDUSTRY_DET) {date} ...", flush=True)
    rows, pages, count = em_datacenter(
        "RPT_VALUEINDUSTRY_DET", f"(TRADE_DATE='{date}')",
        page_size=300, sort_cols="", sort_types="-1")
    out = []
    for r in rows:
        oc = str(r.get("ORIGINALCODE") or "").strip()
        if not oc:
            continue
        out.append({
            "bk": "BK" + oc.zfill(4),
            "name": r.get("BOARD_NAME", ""),
            "board_code": oc,
            "num": r.get("NUM") or 0,
            "loss": r.get("LOSS_COUNT") or 0,
        })
    out.sort(key=lambda x: x["name"])
    print(f"      → {len(out)} 个行业板块", flush=True)
    return out


def main():
    t0 = time.time()
    lhb = cached("lhb", lambda: fetch_lhb(DATE))
    # 同花顺为 best-effort：海外 runner 若不可达，题材板块置空，不影响其余数据
    try:
        ths = cached("ths", lambda: fetch_ths(DATE))
    except Exception as e:
        print(f"! 同花顺抓取失败，题材板块将为空（其余数据正常）: {e!r}", flush=True)
        ths = []
    snap = cached("snap", lambda: fetch_market_snapshot(DATE))
    boards = cached("boards", lambda: fetch_boards(DATE))
    print("=" * 60)
    print(f"抓取完成 用时 {time.time()-t0:.0f}s")
    print(f"  龙虎榜 {len(lhb)} 条 | 强势股 {len(ths)} 只 | 全市场 {len(snap)} 只 | 行业 {len(boards)} 个")
    print("  缓存已写入 .cache/ ，下一步运行 finalize.py 聚合。")


if __name__ == "__main__":
    main()
