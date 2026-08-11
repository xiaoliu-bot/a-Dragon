# -*- coding: utf-8 -*-
"""
本地一键生成报告（取数 → 聚合 → 出 HTML）。
CI 用分步 workflow（可在 fetch_data 与 finalize 之间插入可选的 fetch_klines）；
本地想省事就直接跑这个。行业涨跌幅默认 computed 口径（与已交付报告一致）。
用法：python make_report.py [YYYY-MM-DD]
"""
import sys, subprocess

DATE = sys.argv[1] if len(sys.argv) > 1 else "2026-07-24"
PY = sys.executable

# fetch_data / finalize 吃日期；build_report 吃 data.json（默认即 data.json）
STEPS = [("fetch_data.py", DATE), ("finalize.py", DATE), ("build_report.py", "data.json")]
for step, arg in STEPS:
    print(f"\n>>> {step} {arg}")
    rc = subprocess.run([PY, step, arg]).returncode
    if rc != 0:
        print(f"! {step} 失败（退出码 {rc}）")
        sys.exit(rc)

print("\n完成 ✅ 报告在 output/ 目录（output/A股市场情绪日报_%s.html）" % DATE)
