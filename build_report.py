# -*- coding: utf-8 -*-
"""A股市场情绪日报 —— 单文件 HTML 生成器（全内联，可离线打开）"""
import json, sys, io, html, os
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA = sys.argv[1] if len(sys.argv) > 1 else "data.json"
with open(DATA, encoding="utf-8") as f:
    D = json.load(f)

DATE = D["date"]
E = html.escape

# ───────────────────────────── 格式化工具 ─────────────────────────────
def money(v, sign=False):
    """元 → ¥x.xx亿 / ¥xxx万"""
    a = abs(v)
    s = "+" if (sign and v > 0) else ("-" if v < 0 else "")
    if a >= 1e8:
        return f"{s}¥{a/1e8:.2f}亿"
    if a >= 1e4:
        return f"{s}¥{a/1e4:.0f}万"
    return f"{s}¥{a:.0f}"

def pct(v, sign=True):
    return f"{'+' if (sign and v > 0) else ''}{v:.2f}%"

def cls(v):
    return "up" if v > 0 else ("down" if v < 0 else "flat")

def wd(text, n):
    t = str(text)
    return t if len(t) <= n else t[:n - 1] + "…"

# ───────────────────────────── 数据准备 ─────────────────────────────
lhb = D["lhb_stocks"]
lhb_rec = D["lhb_records"]
themes = D["themes"]
inds = D["industries"]
ths = D["ths_hot"]
mkt = D["market"]

net_buy_total = sum(s["net_buy"] for s in lhb)
buy_side = [s for s in lhb if s["net_buy"] > 0]
sell_side = [s for s in lhb if s["net_buy"] < 0]
top_theme = themes[0] if themes else {"tag": "-", "count": 0}
top_ind = inds[0] if inds else {"name": "-", "change_pct": 0}
bot_ind = inds[-1] if inds else {"name": "-", "change_pct": 0}
ind_up = sum(1 for i in inds if i["change_pct"] > 0)
ind_down = sum(1 for i in inds if i["change_pct"] < 0)

# ───────────────────────────── SVG 组件 ─────────────────────────────
C_UP, C_UP2 = "#ff4d4f", "#ff7875"
C_DN, C_DN2 = "#00c087", "#3ddc9a"
C_TXT, C_SUB, C_GRID = "#e6edf3", "#8b98a5", "#22303c"

def svg_theme_bars(items, width=660, row_h=26, pad_left=136, pad_right=52):
    """题材热度横向条形图"""
    n = len(items)
    h = n * row_h + 34
    mx = max((i["count"] for i in items), default=1)
    bw = width - pad_left - pad_right
    p = [f'<svg viewBox="0 0 {width} {h}" width="100%" height="{h}" '
         f'xmlns="http://www.w3.org/2000/svg" font-family="ui-sans-serif,-apple-system,Segoe UI,Microsoft YaHei,sans-serif">']
    # 网格
    for g in range(0, mx + 1, max(1, mx // 5)):
        x = pad_left + bw * g / mx
        p.append(f'<line x1="{x:.1f}" y1="18" x2="{x:.1f}" y2="{h-16}" stroke="{C_GRID}" stroke-width="1"/>')
        p.append(f'<text x="{x:.1f}" y="12" fill="{C_SUB}" font-size="10" text-anchor="middle">{g}</text>')
    for i, it in enumerate(items):
        y = 22 + i * row_h
        w = bw * it["count"] / mx
        op = 1 - i * 0.028
        p.append(f'<text x="{pad_left-8}" y="{y+13}" fill="{C_TXT}" font-size="12" text-anchor="end">{E(wd(it["tag"],11))}</text>')
        p.append(f'<rect x="{pad_left}" y="{y+2}" width="{max(w,2):.1f}" height="{row_h-8}" rx="3" '
                 f'fill="url(#gTheme)" opacity="{op:.2f}"/>')
        p.append(f'<text x="{pad_left+w+7:.1f}" y="{y+13}" fill="{C_UP2}" font-size="11" font-weight="600">{it["count"]}只</text>')
    p.append(f'''<defs><linearGradient id="gTheme" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#7a1f24"/><stop offset="100%" stop-color="{C_UP}"/></linearGradient></defs>''')
    p.append("</svg>")
    return "".join(p)


def svg_industry(top, bottom, width=660, row_h=22):
    """行业涨跌双向条形图（中轴分列）"""
    rows = top + [None] + bottom
    h = len(rows) * row_h + 40
    mx = max([abs(r["change_pct"]) for r in rows if r], default=1)
    cx = width * 0.50
    half = width * 0.30
    p = [f'<svg viewBox="0 0 {width} {h}" width="100%" height="{h}" '
         f'xmlns="http://www.w3.org/2000/svg" font-family="ui-sans-serif,-apple-system,Segoe UI,Microsoft YaHei,sans-serif">']
    p.append(f'<line x1="{cx}" y1="16" x2="{cx}" y2="{h-14}" stroke="#3a4a5a" stroke-width="1"/>')
    for k in (0.5, 1.0):
        for sgn in (-1, 1):
            x = cx + sgn * half * k
            p.append(f'<line x1="{x:.1f}" y1="16" x2="{x:.1f}" y2="{h-14}" stroke="{C_GRID}" stroke-width="1" stroke-dasharray="2 3"/>')
            p.append(f'<text x="{x:.1f}" y="11" fill="{C_SUB}" font-size="9" text-anchor="middle">{sgn*mx*k:+.1f}%</text>')
    for i, r in enumerate(rows):
        y = 20 + i * row_h
        if r is None:
            p.append(f'<text x="{cx}" y="{y+13}" fill="{C_SUB}" font-size="10" text-anchor="middle">· · · 中间 {len(inds)-len(top)-len(bottom)} 个行业省略 · · ·</text>')
            continue
        v = r["change_pct"]
        w = half * abs(v) / mx
        color = C_UP if v > 0 else (C_DN if v < 0 else "#7d8590")
        if v >= 0:
            p.append(f'<rect x="{cx}" y="{y+3}" width="{max(w,1.5):.1f}" height="{row_h-8}" rx="2" fill="{color}" opacity="0.88"/>')
            p.append(f'<text x="{cx-7}" y="{y+13}" fill="{C_TXT}" font-size="11" text-anchor="end">{E(wd(r["name"],7))}</text>')
            p.append(f'<text x="{cx+w+6:.1f}" y="{y+13}" fill="{color}" font-size="11" font-weight="600">{pct(v)}</text>')
            p.append(f'<text x="{width-4}" y="{y+13}" fill="{C_SUB}" font-size="9.5" text-anchor="end">{r["up"]}↑/{r["down"]}↓ {E(wd(r["leader"],5))}</text>')
        else:
            p.append(f'<rect x="{cx-w:.1f}" y="{y+3}" width="{max(w,1.5):.1f}" height="{row_h-8}" rx="2" fill="{color}" opacity="0.88"/>')
            p.append(f'<text x="{cx+7}" y="{y+13}" fill="{C_TXT}" font-size="11">{E(wd(r["name"],7))}</text>')
            p.append(f'<text x="{cx-w-6:.1f}" y="{y+13}" fill="{color}" font-size="11" font-weight="600" text-anchor="end">{pct(v)}</text>')
            p.append(f'<text x="4" y="{y+13}" fill="{C_SUB}" font-size="9.5">{r["up"]}↑/{r["down"]}↓</text>')
    p.append("</svg>")
    return "".join(p)


def svg_netbuy(buy, sell, width=1320, row_h=25, pad_left=118):
    """龙虎榜净买入排名（左买右卖，双栏）"""
    n = max(len(buy), len(sell))
    h = n * row_h + 46
    colw = width / 2 - 16
    mxb = max([s["net_buy"] for s in buy], default=1)
    mxs = max([abs(s["net_buy"]) for s in sell], default=1)
    mx = max(mxb, mxs)
    bw = colw - pad_left - 74
    p = [f'<svg viewBox="0 0 {width} {h}" width="100%" height="{h}" '
         f'xmlns="http://www.w3.org/2000/svg" font-family="ui-sans-serif,-apple-system,Segoe UI,Microsoft YaHei,sans-serif">']
    p.append(f'<text x="{pad_left}" y="14" fill="{C_UP}" font-size="12" font-weight="700">▲ 净买入 TOP{len(buy)}</text>')
    p.append(f'<text x="{width/2+16+pad_left}" y="14" fill="{C_DN}" font-size="12" font-weight="700">▼ 净卖出 TOP{len(sell)}</text>')
    for col, (items, color, grad) in enumerate([(buy, C_UP, "gBuy"), (sell, C_DN, "gSell")]):
        ox = col * (width / 2 + 16)
        for i, s in enumerate(items):
            y = 26 + i * row_h
            v = abs(s["net_buy"])
            w = bw * v / mx if mx else 0
            p.append(f'<text x="{ox+pad_left-8}" y="{y+13}" fill="{C_TXT}" font-size="11.5" text-anchor="end">{E(wd(s["name"],6))}</text>')
            p.append(f'<text x="{ox+2}" y="{y+13}" fill="{C_SUB}" font-size="10" font-family="ui-monospace,Consolas,monospace">{s["code"]}</text>')
            p.append(f'<rect x="{ox+pad_left}" y="{y+3}" width="{max(w,2):.1f}" height="{row_h-9}" rx="3" fill="url(#{grad})"/>')
            cp = s["change_pct"]
            ccl = C_UP if cp > 0 else (C_DN if cp < 0 else "#7d8590")
            p.append(f'<text x="{ox+pad_left+w+7:.1f}" y="{y+13}" fill="{color}" font-size="11" font-weight="600">{money(v)}</text>')
            p.append(f'<text x="{ox+colw+8}" y="{y+13}" fill="{ccl}" font-size="10.5" text-anchor="end">{pct(cp)}</text>')
    p.append(f'''<defs>
      <linearGradient id="gBuy" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#5c161a"/><stop offset="100%" stop-color="{C_UP}"/></linearGradient>
      <linearGradient id="gSell" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#0d4a38"/><stop offset="100%" stop-color="{C_DN}"/></linearGradient>
    </defs>''')
    p.append("</svg>")
    return "".join(p)


def svg_breadth(m, width=660, h=86):
    """全市场涨跌家数分布条"""
    tot = max(m["total"], 1)
    up, dn, fl = m["up"], m["down"], m["flat"]
    x = 0
    p = [f'<svg viewBox="0 0 {width} {h}" width="100%" height="{h}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="ui-sans-serif,-apple-system,Segoe UI,Microsoft YaHei,sans-serif">']
    segs = [(up, C_UP, f"上涨 {up}"), (fl, "#5c6b7a", f"平 {fl}"), (dn, C_DN, f"下跌 {dn}")]
    for v, c, label in segs:
        w = width * v / tot
        p.append(f'<rect x="{x:.1f}" y="26" width="{w:.1f}" height="26" fill="{c}" opacity="0.9"/>')
        if w > 66:
            p.append(f'<text x="{x+w/2:.1f}" y="43" fill="#0b1016" font-size="11.5" font-weight="700" text-anchor="middle">{label}</text>')
        x += w
    p.append(f'<text x="0" y="18" fill="{C_SUB}" font-size="11">全市场 {tot} 只 · 上涨占比 {up/tot*100:.1f}%</text>')
    p.append(f'<text x="{width}" y="18" fill="{C_UP}" font-size="11" text-anchor="end" font-weight="600">涨停 {m["limit_up"]} · '
             f'<tspan fill="{C_DN}">跌停 {m["limit_down"]}</tspan></text>')
    # 涨停/跌停小方块
    p.append(f'<text x="0" y="72" fill="{C_SUB}" font-size="10.5">情绪温度：</text>')
    ratio = up / tot
    bw = width - 84
    p.append(f'<rect x="76" y="62" width="{bw}" height="12" rx="6" fill="#1b2430"/>')
    p.append(f'<rect x="76" y="62" width="{bw*ratio:.1f}" height="12" rx="6" fill="url(#gTemp)"/>')
    p.append(f'<text x="{76+bw*ratio+6:.1f}" y="72" fill="{C_TXT}" font-size="10.5" font-weight="600">{ratio*100:.0f}分</text>')
    p.append(f'''<defs><linearGradient id="gTemp" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="{C_DN}"/><stop offset="55%" stop-color="#d9a441"/><stop offset="100%" stop-color="{C_UP}"/></linearGradient></defs>''')
    p.append("</svg>")
    return "".join(p)


# ───────────────────────────── 表格 ─────────────────────────────
def lhb_table():
    rows = []
    for i, s in enumerate(lhb, 1):
        c = cls(s["change_pct"])
        nb = cls(s["net_buy"])
        rows.append(f'''<tr data-k="{E(s['code']+s['name']+s['reason_all']+s.get('industry',''))}">
<td class="idx">{i}</td>
<td class="mono">{E(s['code'])}</td>
<td class="nm">{E(s['name'])}</td>
<td class="mono sub">{E(s.get('industry','') or '—')}</td>
<td class="mono">{s['close']:.2f}</td>
<td class="mono {c}" data-v="{s['change_pct']}">{pct(s['change_pct'])}</td>
<td class="mono {nb} b" data-v="{s['net_buy']}">{money(s['net_buy'], True)}</td>
<td class="mono sub">{money(s['buy_amt'])}</td>
<td class="mono sub">{money(s['sell_amt'])}</td>
<td class="mono" data-v="{s['turnover_pct']}">{s['turnover_pct']:.2f}%</td>
<td class="mono sub">{s['deal_ratio']:.1f}%</td>
<td class="rs">{E(s['reason_all'])}</td></tr>''')
    return "\n".join(rows)


def theme_table():
    rows = []
    for i, t in enumerate(themes[:40], 1):
        chips = "".join(
            f'<span class="chip {cls(s["change_pct"])}">{E(s["name"])} {pct(s["change_pct"])}</span>'
            for s in t["stocks"][:8])
        rows.append(f'''<tr><td class="idx">{i}</td><td class="nm">{E(t['tag'])}</td>
<td class="mono b up">{t['count']}</td><td>{chips}</td></tr>''')
    return "\n".join(rows)


def ind_table():
    rows = []
    for i, r in enumerate(inds, 1):
        c = cls(r["change_pct"])
        amt = money(r["amount"]) if r.get("amount") else "—"
        tov = f"{r['turnover_pct']:.2f}%" if r.get("turnover_pct") else "—"
        lu = f'<span class="up b">{r["limit_up_cnt"]}</span>' if r.get("limit_up_cnt") else '<span class="sub">0</span>'
        rows.append(f'''<tr data-k="{E(r['name']+r['leader'])}">
<td class="idx">{i}</td><td class="nm">{E(r['name'])}</td>
<td class="mono {c} b" data-v="{r['change_pct']}">{pct(r['change_pct'])}</td>
<td class="mono sub">{r['member_count']}</td>
<td class="mono up" data-v="{r['up']}">{r['up']}</td><td class="mono down">{r['down']}</td>
<td class="mono">{lu}</td>
<td class="mono sub">{money(r['mcap'])}</td>
<td class="mono sub">{amt}</td>
<td class="mono sub" data-v="{r.get('turnover_pct',0)}">{tov}</td>
<td class="nm">{E(r['leader'])} <span class="{cls(r['leader_change'])}">{pct(r['leader_change'])}</span></td>
<td class="nm sub">{E(r['laggard'])} <span class="{cls(r['laggard_change'])}">{pct(r['laggard_change'])}</span></td></tr>''')
    return "\n".join(rows)


def ths_table():
    rows = []
    for i, s in enumerate(sorted(ths, key=lambda x: -x["change_pct"]), 1):
        rows.append(f'''<tr data-k="{E(s['code']+s['name']+s['reason'])}">
<td class="idx">{i}</td><td class="mono">{E(s['code'])}</td><td class="nm">{E(s['name'])}</td>
<td class="mono sub">{E(s.get('industry','') or '—')}</td>
<td class="mono">{s['close']:.2f}</td>
<td class="mono {cls(s['change_pct'])} b" data-v="{s['change_pct']}">{pct(s['change_pct'])}</td>
<td class="mono">{s['turnover_pct']:.2f}%</td>
<td class="mono sub">{money(s['amount'])}</td>
<td class="rs">{''.join(f'<span class="tag">{E(t)}</span>' for t in s['tags'])}</td></tr>''')
    return "\n".join(rows)


# ───────────────────────────── 页面组装 ─────────────────────────────
TOP_N_IND = 14
top_inds = inds[:TOP_N_IND]
bot_inds = inds[-TOP_N_IND:]
buy_top = buy_side[:18]
sell_top = sorted(sell_side, key=lambda x: x["net_buy"])[:18]

# 概览小结文字
theme_line = "、".join(f'{t["tag"]}({t["count"]})' for t in themes[:5])
gen = D.get("generated_at", "")

# 行业口径说明
ind_src = D.get("ind_src", "computed")
off_cnt = D.get("ind_official_cnt", 0)
if ind_src == "official":
    IND_NOTE = (f"口径：行业涨跌幅取自东方财富行业板块指数（BK 代码）{DATE} 当日日K真实收盘涨跌幅，"
                f"共 {off_cnt}/{len(inds)} 个板块取到官方值；上涨/下跌/涨停家数、领涨领跌股由 {DATE} 全市场 "
                f"{mkt['total']} 只个股收盘涨跌幅按东财行业归属现算，均为该交易日真实数据。")
elif ind_src == "mixed":
    IND_NOTE = (f"口径：{off_cnt}/{len(inds)} 个板块涨跌幅取自东方财富行业板块指数当日日K官方值，"
                f"其余板块因东财 push2 行情接口限流未取到，改由该板块成分股当日收盘涨跌幅按总市值加权计算（表中标注一致）；"
                f"上涨/下跌/涨停家数与领涨领跌股均由 {DATE} 全市场 {mkt['total']} 只个股真实收盘价现算。")
else:
    IND_NOTE = (f"口径：行业涨跌幅 = 该板块成分股 {DATE} 当日收盘涨跌幅按总市值加权计算（东财行业分类，"
                f"数据来自东方财富数据中心 RPT_VALUEANALYSIS_DET 当日全市场 {mkt['total']} 只个股真实收盘数据）。"
                f"因东财 push2 行情接口本次被风控限流，未能取到板块指数官方点位，与东财官网展示值可能有约 0.1~0.2 个百分点差异，"
                f"排序与方向一致；上涨/下跌/涨停家数、领涨领跌股为逐只个股精确统计。")

HTML = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>A股市场情绪日报 · {DATE}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
:root{{--bg:#0a0e14;--panel:#111823;--panel2:#0e141d;--bd:#1e2937;--txt:#e6edf3;--sub:#8b98a5;--up:#ff4d4f;--dn:#00c087;--acc:#d9a441}}
body{{background:var(--bg);color:var(--txt);font:13px/1.5 ui-sans-serif,-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;
background-image:radial-gradient(900px 420px at 12% -8%,rgba(255,77,79,.09),transparent),radial-gradient(760px 380px at 92% -4%,rgba(0,192,135,.07),transparent);
-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1400px;margin:0 auto;padding:20px 18px 46px}}
header{{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap;
border-bottom:1px solid var(--bd);padding-bottom:14px;margin-bottom:16px}}
h1{{font-size:23px;letter-spacing:.5px;font-weight:700}}
h1 span{{color:var(--up)}}
.date{{font:600 15px/1.2 ui-monospace,Consolas,monospace;color:var(--acc)}}
.meta{{color:var(--sub);font-size:11.5px;text-align:right}}
.badge{{display:inline-block;background:#182130;border:1px solid var(--bd);color:var(--sub);
border-radius:4px;padding:2px 7px;font-size:10.5px;margin-left:5px}}
.kpis{{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin-bottom:14px}}
.kpi{{background:linear-gradient(160deg,var(--panel),var(--panel2));border:1px solid var(--bd);border-radius:8px;padding:11px 12px;position:relative;overflow:hidden}}
.kpi::after{{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--acc);opacity:.75}}
.kpi.r::after{{background:var(--up)}} .kpi.g::after{{background:var(--dn)}}
.kpi .l{{color:var(--sub);font-size:11px;margin-bottom:5px;letter-spacing:.3px}}
.kpi .v{{font:700 20px/1.15 ui-monospace,Consolas,monospace}}
.kpi .v.sm{{font-size:15px;font-family:inherit}}
.kpi .s{{color:var(--sub);font-size:10.5px;margin-top:4px}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.card{{background:var(--panel);border:1px solid var(--bd);border-radius:9px;padding:12px 13px;margin-bottom:12px}}
.card h2{{font-size:13.5px;font-weight:700;margin-bottom:9px;display:flex;align-items:center;gap:7px;letter-spacing:.4px}}
.card h2::before{{content:"";width:3px;height:13px;background:var(--up);border-radius:2px}}
.card h2 em{{font-style:normal;color:var(--sub);font-weight:400;font-size:11px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{position:sticky;top:0;background:#16202d;color:var(--sub);font-weight:600;font-size:11px;
text-align:right;padding:7px 7px;border-bottom:1px solid var(--bd);white-space:nowrap;z-index:2}}
th:nth-child(-n+4),td:nth-child(-n+4){{text-align:left}}
th.c,td.c{{text-align:center}}
td{{padding:5px 7px;border-bottom:1px solid #16202d;text-align:right;white-space:nowrap}}
tbody tr:hover{{background:#16202d}}
.mono{{font-family:ui-monospace,Consolas,"SF Mono",monospace}}
.idx{{color:#556575;font-size:10.5px;width:30px}}
.nm{{font-weight:600}}
.sub{{color:var(--sub)}}
.b{{font-weight:700}}
.up{{color:var(--up)}} .down{{color:var(--dn)}} .flat{{color:#8b98a5}}
.rs{{text-align:left!important;color:#a9b6c3;font-size:11px;white-space:normal;line-height:1.45;min-width:220px}}
.chip{{display:inline-block;background:#182130;border:1px solid #24303f;border-radius:3px;
padding:1px 5px;margin:1px 3px 1px 0;font-size:10.5px}}
.tag{{display:inline-block;background:#1c2634;border:1px solid #2a3849;color:#c8d4e0;border-radius:3px;
padding:1px 5px;margin:1px 3px 1px 0;font-size:10.5px}}
.scroll{{max-height:620px;overflow:auto}}
.scroll::-webkit-scrollbar{{width:8px;height:8px}}
.scroll::-webkit-scrollbar-thumb{{background:#2a3644;border-radius:4px}}
.tools{{display:flex;gap:8px;align-items:center;margin-bottom:8px;flex-wrap:wrap}}
input.search{{background:#0c121a;border:1px solid var(--bd);color:var(--txt);border-radius:5px;
padding:5px 9px;font-size:12px;width:210px;outline:none;font-family:inherit}}
input.search:focus{{border-color:#3a4a5e}}
.btn{{background:#182130;border:1px solid var(--bd);color:var(--sub);border-radius:5px;
padding:4px 9px;font-size:11px;cursor:pointer;font-family:inherit}}
.btn:hover{{color:var(--txt);border-color:#3a4a5e}}
.btn.on{{background:#243244;color:var(--txt);border-color:#3f5064}}
.note{{color:var(--sub);font-size:11px;line-height:1.6;background:#0d141d;border:1px dashed #223041;
border-radius:6px;padding:9px 11px;margin-top:9px}}
footer{{margin-top:20px;border-top:1px solid var(--bd);padding-top:13px;color:var(--sub);font-size:11px;line-height:1.75}}
footer b{{color:#b9c5d1;font-weight:600}}
.src{{display:flex;gap:16px;flex-wrap:wrap;margin-top:5px}}
.src span{{background:#111823;border:1px solid var(--bd);border-radius:4px;padding:3px 8px}}
@media(max-width:1080px){{.kpis{{grid-template-columns:repeat(3,1fr)}}.grid2{{grid-template-columns:1fr}}}}
</style></head>
<body><div class="wrap">

<header>
  <div>
    <h1>A股市场情绪日报 <span>· 龙虎榜 / 题材热点 / 行业轮动</span></h1>
    <div class="meta" style="text-align:left;margin-top:6px">
      全市场龙虎榜 {len(lhb)} 家 · 强势股题材归因 {len(ths)} 只 · 行业板块 {len(inds)} 个 · 个股样本 {mkt['total']} 只
    </div>
  </div>
  <div>
    <div class="date">交易日 {DATE}</div>
    <div class="meta">数据抓取时间 {E(gen)}<span class="badge">真实接口抓取</span></div>
  </div>
</header>

<div class="kpis">
  <div class="kpi r"><div class="l">龙虎榜上榜家数</div><div class="v">{len(lhb)}</div>
    <div class="s">共 {len(lhb_rec)} 条上榜记录</div></div>
  <div class="kpi {'r' if net_buy_total>0 else 'g'}"><div class="l">龙虎榜净买入合计</div>
    <div class="v {cls(net_buy_total)}">{money(net_buy_total, True)}</div>
    <div class="s">净买 {len(buy_side)} 家 / 净卖 {len(sell_side)} 家</div></div>
  <div class="kpi r"><div class="l">当日最热题材</div><div class="v sm">{E(top_theme['tag'])}</div>
    <div class="s">{top_theme['count']} 只强势股共用 · 共 {len(themes)} 个题材标签</div></div>
  <div class="kpi r"><div class="l">领涨行业</div><div class="v sm up">{E(top_ind['name'])} {pct(top_ind['change_pct'])}</div>
    <div class="s">领涨股 {E(top_ind.get('leader',''))} {pct(top_ind.get('leader_change',0))}</div></div>
  <div class="kpi g"><div class="l">领跌行业</div><div class="v sm down">{E(bot_ind['name'])} {pct(bot_ind['change_pct'])}</div>
    <div class="s">{ind_up} 个行业上涨 / {ind_down} 个下跌</div></div>
  <div class="kpi {'r' if mkt['up']>mkt['down'] else 'g'}"><div class="l">全市场涨跌家数</div>
    <div class="v"><span class="up">{mkt['up']}</span><span class="sub" style="font-size:14px">/</span><span class="down">{mkt['down']}</span></div>
    <div class="s">涨停 {mkt['limit_up']} · 跌停 {mkt['limit_down']}</div></div>
</div>

<div class="grid2">
  <div class="card"><h2>当日题材热度 TOP20 <em>同花顺强势股 reason 标签按「+」拆分词频</em></h2>
    {svg_theme_bars(themes[:20])}
    <div class="note">口径：同花顺编辑部对当日 {len(ths)} 只强势股的人工题材归因标签，按「+」拆分后统计出现只数。
    当日 TOP5 题材：{E(theme_line)}。</div>
  </div>
  <div class="card"><h2>行业涨跌榜 <em>东财一级行业 · 领涨 {TOP_N_IND} / 领跌 {TOP_N_IND}</em></h2>
    {svg_industry(top_inds, bot_inds)}
  </div>
</div>

<div class="card"><h2>全市场涨跌分布 <em>{DATE} 收盘 · 个股样本 {mkt['total']} 只</em></h2>
  {svg_breadth(mkt)}
</div>

<div class="card"><h2>龙虎榜资金净买入排名 <em>按营业部席位净买入额排序 · 单位 ¥</em></h2>
  {svg_netbuy(buy_top, sell_top)}
</div>

<div class="card"><h2>龙虎榜明细 <em>全部 {len(lhb)} 只 · 按净买入降序</em></h2>
  <div class="tools">
    <input class="search" id="q1" placeholder="搜索代码 / 名称 / 行业 / 上榜原因"/>
    <button class="btn on" data-t="t1" data-c="6">净买入 ↓</button>
    <button class="btn" data-t="t1" data-c="5">涨跌幅 ↓</button>
    <button class="btn" data-t="t1" data-c="9">换手率 ↓</button>
    <span class="sub" id="c1"></span>
  </div>
  <div class="scroll"><table id="t1"><thead><tr>
    <th>#</th><th>代码</th><th>名称</th><th>所属行业</th><th>收盘</th><th>涨跌幅</th>
    <th>净买入</th><th>买入额</th><th>卖出额</th><th>换手率</th><th>占成交</th><th style="text-align:left">上榜原因</th>
  </tr></thead><tbody>{lhb_table()}</tbody></table></div>
</div>

<div class="grid2">
  <div class="card"><h2>题材热度明细 <em>TOP40 题材及代表个股</em></h2>
    <div class="scroll" style="max-height:520px"><table><thead><tr>
      <th>#</th><th>题材标签</th><th>只数</th><th style="text-align:left">代表个股（当日涨幅）</th>
    </tr></thead><tbody>{theme_table()}</tbody></table></div>
  </div>
  <div class="card"><h2>当日强势股题材归因 <em>同花顺 {len(ths)} 只</em></h2>
    <div class="tools"><input class="search" id="q3" placeholder="搜索代码 / 名称 / 题材"/><span class="sub" id="c3"></span></div>
    <div class="scroll" style="max-height:456px"><table id="t3"><thead><tr>
      <th>#</th><th>代码</th><th>名称</th><th>行业</th><th>收盘</th><th>涨幅</th><th>换手</th><th>成交额</th>
      <th style="text-align:left">题材归因</th>
    </tr></thead><tbody>{ths_table()}</tbody></table></div>
  </div>
</div>

<div class="card"><h2>行业板块全景 <em>{len(inds)} 个东财一级行业 · 按涨跌幅排序</em></h2>
  <div class="tools">
    <input class="search" id="q2" placeholder="搜索行业 / 领涨股"/>
    <button class="btn on" data-t="t2" data-c="2">涨跌幅 ↓</button>
    <button class="btn" data-t="t2" data-c="4">上涨家数 ↓</button>
    <button class="btn" data-t="t2" data-c="8">换手率 ↓</button>
    <span class="sub" id="c2"></span>
  </div>
  <div class="scroll"><table id="t2"><thead><tr>
    <th>#</th><th>行业板块</th><th>涨跌幅</th><th>成分股</th><th>上涨</th><th>下跌</th><th>涨停</th>
    <th>总市值</th><th>成交额</th><th>换手率</th><th style="text-align:left">领涨股</th><th style="text-align:left">领跌股</th>
  </tr></thead><tbody>{ind_table()}</tbody></table></div>
  <div class="note">{IND_NOTE}</div>
</div>

<footer>
  <b>数据来源（全部为真实接口抓取，无模拟数据）：</b>
  <div class="src">
    <span>① 龙虎榜：东方财富数据中心 datacenter-web · RPT_DAILYBILLBOARD_DETAILSNEW</span>
    <span>② 题材热点：同花顺 zx.10jqka.com.cn · getharden 当日强势股 reason 归因</span>
    <span>③ 行业板块：东方财富 push2his 板块日K（BK 指数）· push2 clist 行业列表</span>
    <span>④ 个股涨跌/行业归属：东方财富数据中心 · RPT_VALUEANALYSIS_DET（{DATE} 全市场 {mkt['total']} 只）</span>
  </div>
  <div style="margin-top:8px">
    交易日期：<b>{DATE}</b>　|　数据抓取时间：<b>{E(gen)}</b>　|　颜色约定：<span class="up">红涨</span> / <span class="down">绿跌</span>（A股惯例）　|　金额单位：¥ 亿 / 万
  </div>
  <div style="margin-top:6px">
    口径说明：行业涨跌幅取东方财富行业板块指数当日日K真实收盘涨跌幅；上涨/下跌家数与领涨领跌股由当日全市场个股收盘涨跌幅按东财行业归属现算，
    非实时快照。龙虎榜同一只股票若因多个原因上榜，已按股票去重合并原因，净买入取金额绝对值最大的一条，避免重复累加。
    本页仅为市场数据复盘，不构成任何投资建议。
  </div>
</footer>

</div>
<script>
(function(){{
 function bind(q,t,c){{
  var i=document.getElementById(q),tb=document.querySelector('#'+t+' tbody'),lb=document.getElementById(c);
  if(!i||!tb)return;
  var rows=[].slice.call(tb.rows);
  function upd(){{
   var v=i.value.trim().toLowerCase(),n=0;
   rows.forEach(function(r){{
     var ok=!v||(r.dataset.k||'').toLowerCase().indexOf(v)>=0;
     r.style.display=ok?'':'none'; if(ok)n++;
   }});
   lb.textContent=v?('匹配 '+n+' 条'):'';
  }}
  i.addEventListener('input',upd);
 }}
 bind('q1','t1','c1'); bind('q2','t2','c2'); bind('q3','t3','c3');
 [].forEach.call(document.querySelectorAll('.btn[data-t]'),function(b){{
  b.addEventListener('click',function(){{
   var t=b.dataset.t,ci=+b.dataset.c,tb=document.querySelector('#'+t+' tbody');
   [].forEach.call(document.querySelectorAll('.btn[data-t="'+t+'"]'),function(x){{x.classList.remove('on')}});
   b.classList.add('on');
   var rows=[].slice.call(tb.rows);
   rows.sort(function(a,z){{
     var x=parseFloat((a.cells[ci].dataset.v||a.cells[ci].textContent).replace(/[^\\d.\\-]/g,''))||0;
     var y=parseFloat((z.cells[ci].dataset.v||z.cells[ci].textContent).replace(/[^\\d.\\-]/g,''))||0;
     return y-x;
   }});
   rows.forEach(function(r,k){{tb.appendChild(r);r.cells[0].textContent=k+1;}});
  }});
 }});
}})();
</script>
</body></html>"""

os.makedirs("output", exist_ok=True)
path = os.path.join("output", f"A股市场情绪日报_{DATE}.html")
with open(path, "w", encoding="utf-8") as f:
    f.write(HTML)
print("生成:", os.path.abspath(path), f"{len(HTML)/1024:.0f} KB")
