# A股情绪日报 · 龙虎榜 / 题材热点 / 行业轮动

每个交易日收盘后自动生成的 A股「龙虎榜 + 题材热点 + 行业轮动」市场情绪日报。
单文件 HTML（资源全内联，可离线打开），暗色盘面复盘风，数据均来自真实公开接口，**无模拟数据**。

- 顶部概览：上榜家数、龙虎榜净买入合计、当日最热题材、领涨/领跌行业、全市场涨跌家数
- 内联 SVG 图：题材热度条形图、行业涨跌双向榜、全市场涨跌分布、龙虎榜净买入排名
- 明细表：龙虎榜全量、题材热度、同花顺强势股归因、127 个行业板块全景（带搜索/排序）
- 颜色约定：红涨 / 绿跌（A股惯例）；金额单位 ¥ 亿 / 万

## 数据来源（全部免费、可在海外 GitHub Actions runner 访问）

| 数据 | 接口 | 说明 |
|------|------|------|
| 龙虎榜 | 东方财富 datacenter `RPT_DAILYBILLBOARD_DETAILSNEW` | 全市场上榜股票，按股票去重合并多原因 |
| 题材热点 | 同花顺 `zx.10jqka.com.cn` `getharden` | 当日强势股 `reason` 题材归因，按「+」拆分词频 |
| 行业清单 | 东方财富 datacenter `RPT_VALUEINDUSTRY_DET` | 127 个一级行业（可靠，不依赖行情 push2） |
| 个股/行业归属 | 东方财富 datacenter `RPT_VALUEANALYSIS_DET` | 当日全市场约 5500 只个股收盘涨跌幅 + 行业归属 |

**行业涨跌幅口径**：优先取东财行业板块指数当日日K官方值（`fetch_klines.py`，push2 可达时自动启用）；
不可达时回退为「该板块成分股当日收盘涨跌幅按总市值加权」计算（computed）。两者方向/排序一致，
绝对值偏差约 0.1~0.2 个百分点。报告内已用虚线框标注当前口径。

## 管道（三个阶段，算法与已交付报告一致）

```
fetch_data.py  →  finalize.py  →  build_report.py
 (写 .cache/)     (聚合→data.json)   (data.json→output/*.html)
```

- `fetch_data.py`：抓取龙虎榜 / 同花顺 / 全市场个股 / 行业清单，写入 `.cache/`
- `fetch_klines.py`（**可选**）：抓行业官方日K，push2 不可达时快速跳过，不影响主流程
- `finalize.py`：聚合去重、题材词频、行业涨跌幅计算（official/computed）→ `data.json`
- `build_report.py`：`data.json` → 单文件 HTML
- `make_report.py`：本地一键跑完上面三步（省事用这个）

本地运行示例：
```bash
pip install -r requirements.txt
python make_report.py 2026-07-24      # 不传日期则默认 2026-07-24
```

## 部署到 GitHub（自动每日更新）

### 1. 建仓库 + 首次推送
把本目录推到一个 GitHub 仓库（用你提供的 PAT，仓库名建议 `a-share-sentiment-daily`）。
首次推送后，Actions 会在每个交易日北京时间 16:30 自动跑。

### 2. 开启 GitHub Pages（让报告有网址可看）
仓库 → **Settings → Pages → Build and deployment → Source: Deploy from a branch**
→ Branch 选 `main`，目录选 `/ (root)` → Save。
稍等一两分钟，访问 `https://<用户名>.github.io/<仓库名>/` 即可看到 `index.html`（始终是最新一期）。

> 工作流用内置 `GITHUB_TOKEN` 提交，**无需**把 PAT 放进仓库 Secrets。
> PAT 只在「建仓库 + 首次推送」时用一次。

### 3. 手动触发 / 调试
仓库 → **Actions → A股情绪日报 · 每日更新 → Run workflow** 可手动跑一次（含指定日期则需改 workflow 或本地跑）。

## 注意事项 / 已知风险
- **同花顺接口**：海外 runner 偶发不可达。脚本已做 best-effort 降级——若某日同花顺失败，题材板块为空，
  其余数据（龙虎榜 / 行业）正常，报告照常生成。首次自动运行后请留意 Actions 日志确认。
- **非交易日**：cron 仅周一至周五；若遇国内节假日（周一至周五中的休市日），东财返回空数据，
  工作流检测到样本过少会自动跳过本次提交，不会产生空报告。
- **时区**：cron 按 UTC 调度，工作流内用 `TZ=Asia/Shanghai` 计算「今天」的交易日期。
- **行业加权口径**：当 push2 不可达时使用 computed 回退（与已交付报告一致）；若某日 runner 能连 push2，
  会自动升级为官方日K口径，排序不变、精度更高。

## 文件结构
```
fetch_data.py          数据抓取（阶段一）
fetch_klines.py        行业官方日K（可选增强）
finalize.py            聚合 → data.json（阶段二）
build_report.py        data.json → 单文件 HTML（阶段三）
make_report.py         本地一键生成
requirements.txt       Python 依赖
.github/workflows/daily.yml   每日自动更新
```
