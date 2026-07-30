# 同频 · ETF 国家队共振监控

> **同频（Resonance）**：当价格位置、份额流向、交易方向、成交额热度、融资杠杆五个指标
> 在同一方向上「共振」时，往往意味着国家队资金正在系统性进出。本项目把这种「同频」信号
> 量化、可视化，并在触发时主动预警。

一个用于监测中国「国家队」（中央汇金等）ETF 资金动向的本地化监控系统。它不预测行情，
只回答一个问题：**此刻，国家队大概率在买还是在卖？信号有多强？**

---

## 一、核心思想

### 1. 为什么看 ETF
国家队救市/护盘时，通常通过申购宽基 ETF（沪深300、上证50、中证500/1000、科创50 等）
间接入市。ETF 的**份额变化**、**量价配合**、**折溢价**是观测其动作的高信噪比窗口。

### 2. 三因子 → 五指标 → 共振
系统从三个维度刻画资金行为，再叠加两个市场情绪维度，共五个指标各亮一盏灯：

| 指标 | 维度 | 绿灯（机会/吸筹） | 红灯（风险/出货） |
|---|---|---|---|
| 价格位置 | ETF | 近 60 日区间 ≤40% 低位 | ≥70% 高位 |
| 份额流向 | ETF | 净申购（份额概率 ≥65） | 净赎回（≤30） |
| 交易方向 | ETF | 低位放量吸筹 | 高位放量出货 |
| 成交额热度 | 市场 | 两市成交额分位 ≤20（冷清） | ≥80（过热） |
| 融资杠杆 | 市场 | 融资余额分位 ≤20（冷清） | ≥80（过热） |

**判定规则**：同色灯 ≥3 盏 → 共振。
- 红灯 ≥3 → **危险共振**（出货/过热，警惕回调）
- 绿灯 ≥3 → **机会共振**（吸筹/冷清，左侧布局窗口）
- 否则 → **中性**

> 颜色遵循 A 股习惯：**红 = 涨/风险，绿 = 跌/机会**（与欧美相反）。

### 3. 设计原则
- **本地自洽**：数据、计算、存储全部在本机，不依赖任何外部 AI 或托管服务。
- **可独立重建**：一个空仓库 + 一条命令即可从零重建全量历史数据（见「一键重建」）。
- **只读分析**：系统只读取公开行情数据，不做任何交易操作。
- **优雅降级**：网络失败、非交易日、数据缺失均不抛异常，返回空或降级结果。

---

## 二、功能特性

- **盘中实时信号**：交易时段每 30 秒轮询行情，计算三因子合成概率与信号等级。
- **多指标共振**：五指标红绿灰灯 + 历史热力图，点击任意日期可看逐指标判定依据。
- **市场情绪分区**：两市成交额（MA5 平滑）与融资余额的滚动分位，划分危险/中性/安全区。
- **数据管理页**：所有数据拉取/生成收敛为后台任务 + 实时进度，支持「一键重建」全量数据。
- **定时任务**：内置 APScheduler，自动增量拉取日线、份额、情绪、交易日历。
- **CLI 出口**：`cli/resonance.py` 直接读库输出共振结论，供外部 Agent（如 Qoderwork）转 IM 通知。

---

## 三、技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.9 · FastAPI · uvicorn · APScheduler |
| 数据源 | akshare（成交额/融资/份额/交易日历）· 腾讯行情接口（K线/实时） |
| 存储 | SQLite（WAL 模式，参数化查询） |
| 前端 | React 18 · TypeScript(strict) · Vite · React Query v5 · ECharts · Tailwind |

---

## 四、系统架构

### 后端分层（严格单向依赖，禁止跨层）

```
fetch/      →  analysis/  →  store/      →  api/
HTTP与原始解析   纯函数无I/O     封装SQLite       请求解析与响应格式化
                     ↑
              scheduler/  编排定时任务，组合各层
              main.py     仅做 app 组装
```

- `fetch/`：kline / realtime / shares / sentiment / calendar，只做请求与解析。
- `analysis/`：composite（三因子合成）、factors、intraday、sentiment（分位数）、
  resonance（共振判定）、resonance_evidence（逐指标依据）。全部为纯函数。
- `store/`：database（连接/建表/迁移）+ 各表 repo。
- `api/`：signals / etf / realtime / stats / sentiment / calendar / resonance / data。
- `scheduler/`：tasks（定时任务）、job_manager（后台任务引擎）、data_jobs、rebuild、
  job_registry、time_guard（交易时段守卫）。

### 后台任务引擎
阻塞式拉取通过 `asyncio.to_thread` 丢到工作线程，事件循环保持空闲以响应进度轮询；
内存任务注册表 + `threading.Lock` 防止同任务重叠；`rebuild_all` 为独占任务。
进度以 `progress(current, total, message)` 回调贯穿慢循环。

### 一键重建顺序（承重）
```
交易日历 → ETF 日度 seed → 份额回填（依赖 etf_daily 的交易日）→ 市场情绪
```
阶段权重 5 / 45 / 30 / 20 映射到总进度 0–100%。

---

## 五、目录结构

```
etf-monitor/
├── backend/
│   ├── main.py            # FastAPI 组装入口
│   ├── config.py          # 全部可调常量（阈值/窗口/调度时间）
│   ├── fetch/             # 数据源请求与解析
│   ├── analysis/          # 纯函数分析逻辑
│   ├── store/             # SQLite 访问层
│   ├── api/               # REST 路由
│   └── scheduler/         # 定时任务 + 后台任务引擎
├── frontend/
│   └── src/
│       ├── pages/         # Dashboard / Resonance / Sentiment / DataManage ...
│       ├── components/    # 图表与可复用 UI
│       ├── api/           # client.ts + types.ts
│       └── hooks/         # React Query hooks
├── cli/
│   ├── resonance.py       # 共振 CLI（供外部 Agent 调用）
│   └── qoderwork-prompt.md# 交给 Qoderwork 的使用说明
└── scripts/
    ├── seed_db.py         # ETF 日度历史回填（薄壳）
    └── backfill_shares.py # 份额历史回填（薄壳）
```

---

## 六、快速开始

### 一键启动（推荐）
全新克隆后，直接运行：
```bash
./start.sh
```
脚本会自动创建虚拟环境、安装前后端依赖（仅缺失时），然后同时启动后端（:8001）与前端（:5174），
退出时统一清理。首次启动会自动回填市场情绪数据；ETF 日度历史则请到前端「数据管理」页点「一键重建」。

### 环境准备（手动方式）
```bash
cd etf-monitor
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cd frontend && npm install
```

### 启动
```bash
# 后端（:8001）。首次启动会自动回填情绪数据并预加载K线，约需 1–2 分钟
cd backend && python3 -m uvicorn main:app --port 8001

# 前端（:5174，已配置 /api 代理到 :8001）
cd frontend && npm run dev
```

打开 http://localhost:5174 即可。

### 一键重建全量数据（开源首次使用）
进入前端「数据管理」页 → 配置回填深度（默认 ETF 160 / 份额 140 / 情绪 190 交易日）
→ 点「一键重建」。系统按承重顺序自动 bootstrap 全部数据，无需任何脚本或 AI 辅助。

也可命令行单独回填：
```bash
python3 scripts/seed_db.py 160          # ETF 日度
python3 scripts/backfill_shares.py 140  # 份额
```

> 数据库默认位于 `~/.etf-monitor/etf_monitor.db`，可用环境变量 `ETF_MONITOR_HOME` 覆盖。

---

## 七、CLI（供外部 Agent / IM 通知）

`cli/resonance.py` 直接读取本地数据库，**无需启动 Web 服务**：

```bash
cd etf-monitor
.venv/bin/python cli/resonance.py --all              # 全部 ETF 共振摘要
.venv/bin/python cli/resonance.py                    # 默认 510300 + 逐指标解读
.venv/bin/python cli/resonance.py --code 510500      # 指定 ETF
.venv/bin/python cli/resonance.py --date 2026-07-24  # 某日逐指标判定依据
.venv/bin/python cli/resonance.py --all --json       # 结构化 JSON
```

将 `cli/qoderwork-prompt.md` 的内容交给 Qoderwork，它即可定期巡检并在触发共振时通过 IM 通知。

---

## 八、定时任务

| 任务 | 时间 | 说明 |
|---|---|---|
| realtime_poll | 盘中每 30s | 实时信号轮询 |
| preload_kline | 周一至周五 09:00 | 预加载 K线 |
| daily_analysis | 周一至周五 15:30 | 收盘日线分析入库 |
| fetch_shares | 周一至周五 19:30 | 份额数据（交易所披露较晚） |
| fetch_sentiment | 周一至周五 16:00 | 成交额 + 融资余额 |
| sync_calendar | 每周日 20:00 | 交易日历 |
| cleanup | 每日 02:00 | 清理 7 天前实时快照 |

---

## 九、开发规范（详见 AGENTS.md）

- 单文件 ≤300 行；Python 函数 <50 行。
- 后端分层单向依赖，禁止跨层；`analysis/` 为纯函数。
- TypeScript strict，禁用 `any`（ECharts option 除外）。
- 魔法数字一律提取到 `config.py`；网络请求必须设 timeout 并优雅降级。
- 日期内部 `YYYY-MM-DD`，akshare 边界处转 `YYYYMMDD`。

---

## 十、免责声明

本项目仅用于学习与研究，所有数据来自公开渠道，输出为量化信号而非投资建议。
据此操作，风险自负。
