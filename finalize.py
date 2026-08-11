# -*- coding: utf-8 -*-
"""汇总缓存 → data.json（行业涨跌幅优先用东财板块官方日K，缺失则用成分股市值加权回退）"""
import json, os, sys, io, time
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
DATE = sys.argv[1] if len(sys.argv) > 1 else "2026-07-24"
DC = DATE.replace("-", "")
C = ".cache"

load = lambda n: json.load(open(os.path.join(C, f"{n}_{DC}.json"), encoding="utf-8"))
lhb = load("lhb"); ths = load("ths"); snap = load("snap"); boards = load("boards")
kpath = os.path.join(C, f"klines_{DC}.json")
kc = json.load(open(kpath, encoding="utf-8")) if os.path.exists(kpath) else {}
print(f"官方板块日K缓存: {len(kc)}/{len(boards)}")

# ── 行业聚合 ──
# 重要：东财 RPT_VALUEANALYSIS_DET 的 ORIGINALCODE 字段并非每日都有（部分交易日为 None），
# 不能依赖它把个股归到行业，否则行业榜会整块为空。改用快照里的 BOARD_NAME（行业名）与行业
# 清单匹配——该字段稳定，且与 RPT_VALUEINDUSTRY_DET 的 BOARD_NAME 完全一致（已验证 1500/1500 命中）。
def _norm(n):
    return (n or "").strip().replace("Ⅱ", "").replace(" ", "")

by_name, by_name_n = defaultdict(list), defaultdict(list)
for s in snap.values():
    bn = (s.get("board_name") or "").strip()
    if bn:
        by_name[bn].append(s)
        by_name_n[_norm(bn)].append(s)

inds = []
for b in boards:
    nb = b["name"].strip()
    ms = by_name.get(nb) or by_name_n.get(_norm(nb)) or []
    if not ms:
        continue
    hit = kc.get(b["bk"])
    if hit:
        chg, amount, turnover, src = float(hit[8]), float(hit[6]), float(hit[10]), "official"
    else:
        den = sum(m["mcap"] for m in ms) or 1
        chg = sum(m["change_pct"] * m["mcap"] for m in ms) / den
        amount, turnover, src = 0.0, 0.0, "computed"
    leader = max(ms, key=lambda m: m["change_pct"])
    laggard = min(ms, key=lambda m: m["change_pct"])
    inds.append({
        "bk": b["bk"], "name": b["name"].replace("Ⅱ", ""),
        "change_pct": round(chg, 2), "src": src,
        "amount": amount, "turnover_pct": turnover,
        "mcap": sum(m["mcap"] for m in ms),
        "member_count": len(ms),
        "up": sum(1 for m in ms if m["change_pct"] > 0),
        "down": sum(1 for m in ms if m["change_pct"] < 0),
        "flat": sum(1 for m in ms if m["change_pct"] == 0),
        "limit_up_cnt": sum(1 for m in ms if m["change_pct"] >= 9.8),
        "leader": leader["name"], "leader_code": leader["code"], "leader_change": leader["change_pct"],
        "laggard": laggard["name"], "laggard_change": laggard["change_pct"],
    })
inds.sort(key=lambda x: -x["change_pct"])

# ── 题材词频 ──
tag_stocks = defaultdict(list)
for s in ths:
    for t in s["tags"]:
        tag_stocks[t].append({"code": s["code"], "name": s["name"], "change_pct": s["change_pct"]})
themes = [{"tag": k, "count": len(v), "stocks": sorted(v, key=lambda x: -x["change_pct"])}
          for k, v in tag_stocks.items()]
themes.sort(key=lambda x: (-x["count"], x["tag"]))

# ── 龙虎榜去重合并 ──
merged = {}
for r in lhb:
    c = r["code"]
    if c not in merged:
        merged[c] = dict(r); merged[c]["reasons"] = [r["reason"]]
    else:
        merged[c]["reasons"].append(r["reason"])
        if abs(r["net_buy"]) > abs(merged[c]["net_buy"]):
            for k in ("net_buy", "buy_amt", "sell_amt", "deal_amt", "deal_ratio"):
                merged[c][k] = r[k]
lhb_stocks = sorted(merged.values(), key=lambda x: -x["net_buy"])
for s in lhb_stocks:
    i = snap.get(s["code"])
    s["industry"] = (i["board_name"].replace("Ⅱ", "") if i else "")
    s["reason_all"] = " / ".join(dict.fromkeys(s["reasons"]))
for s in ths:
    i = snap.get(s["code"])
    s["industry"] = (i["board_name"].replace("Ⅱ", "") if i else "")

alls = list(snap.values())
mkt = {"total": len(alls),
       "up": sum(1 for s in alls if s["change_pct"] > 0),
       "down": sum(1 for s in alls if s["change_pct"] < 0),
       "flat": sum(1 for s in alls if s["change_pct"] == 0),
       "limit_up": sum(1 for s in alls if s["change_pct"] >= 9.8),
       "limit_down": sum(1 for s in alls if s["change_pct"] <= -9.8)}

out = {"date": DATE, "generated_at": time.strftime("%Y-%m-%d %H:%M"),
       "ind_src": "official" if len(kc) >= len(boards) * 0.9 else ("mixed" if kc else "computed"),
       "ind_official_cnt": sum(1 for i in inds if i["src"] == "official"),
       "market": mkt, "lhb_records": lhb, "lhb_stocks": lhb_stocks,
       "ths_hot": ths, "themes": themes, "industries": inds}
json.dump(out, open("data.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print(f"龙虎榜 {len(lhb)} 条 / 去重 {len(lhb_stocks)} 只 | 强势股 {len(ths)} | 题材 {len(themes)} | 行业 {len(inds)}")
print(f"全市场 {mkt['total']}: 涨{mkt['up']} 跌{mkt['down']} 平{mkt['flat']} 涨停{mkt['limit_up']} 跌停{mkt['limit_down']}")
print("TOP题材:", [(t['tag'], t['count']) for t in themes[:8]])
print("领涨行业:", [(i['name'], i['change_pct'], i['src']) for i in inds[:5]])
print("领跌行业:", [(i['name'], i['change_pct'], i['src']) for i in inds[-5:]])
print("净买入合计: %.2f 亿" % (sum(s['net_buy'] for s in lhb_stocks) / 1e8))
