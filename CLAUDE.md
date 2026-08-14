# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
完整开发规范见 AGENTS.md（代码分层 / 量化策略推演流程 / 检查框架），本文档只给快速上手指南。

## Quick start

```bash
./start.sh                           # one-click: creates .venv, installs deps, starts both servers
# Or manually:
cd backend && python3 -m uvicorn main:app --port 8001   # API at :8001
cd frontend && npm run dev                               # UI at :5174
```

Database lives at `~/.etf-monitor/etf_monitor.db` (override with `ETF_MONITOR_HOME` env var).

## Architecture

**Backend** (Python 3.9+, FastAPI, SQLite WAL mode) — strict unidirectional layering,
按前端页面领域聚合目录（页面私有逻辑进领域目录，跨页共用下沉 base/）:

```
base/fetch → 领域 analysis → base/store → 领域 api
                     ↑
              base/scheduler（编排层，允许依赖领域 analysis 的计算函数）
              main.py（仅 app 组装）
```

- `base/config.py` — 全部可调常量（ETF 清单/阈值/窗口/调度时间/限流参数）。
- `base/fetch/` — HTTP 请求与原始数据解析（akshare、腾讯行情）。无业务逻辑。
- `base/analysis/` — 纯函数零 I/O：`sentiment/core.py`（分位数/情绪分区）、
  `strategy/`（每只 ETF 独立策略 + `router.py` 分派 + `metrics.py` 共用轮次指标）。
  8 个策略文件：`kc`(589680) `zz`(512100) `div`(515080) `sh50` `sc50` `kc50` `zz500_v2` `a500`；
  无专属策略的 ETF（如 510300）走 `router._run_default` 通用多指标共振。
- `resonance/analysis/` — 共振页领域：`core`(五灯判定) `composite`(综合概率 V2 门控)
  `factors`(份额因子) `intraday`(盘中信号) `evidence`+ `evidence_indicators`(逐指标证据)。
- `portfolio/analysis/` — 组合回测领域：`simulator.py` 等权满仓调度（纯函数）。
- `base/store/` — 全部 SQLite 访问（`database.py` 连接/建表/迁移 + 各表 repo），参数化查询。
- `base/api/` — 跨页共用接口（etf / sentiment）；领域 api（resonance/portfolio）+ 其余页面接口在 `api/`。
- `base/scheduler/` — APScheduler 定时任务 + 后台任务引擎：
  `tasks.py`（注册层，阻塞任务经 `asyncio.to_thread` 派发，勿在事件循环上做同步网络 I/O）、
  `intraday_tasks.py`（盘中轮询/信号入库）、`daily_tasks.py`（收盘分析/份额/情绪/日历）、
  `state.py`（共享内存缓存）、`job_manager.py`（后台任务引擎 + 进度注册表）、
  `job_registry.py`（任务元信息）、`data_jobs.py` + `sentiment_jobs.py`（回填任务实现）、
  `rebuild.py`（一键重建流水线）、`recalc.py`（重算综合概率）、`time_guard.py`（交易时段守卫）。
- `main.py` — App 组装（lifespan/CORS/路由注册/静态托管），仅组装无业务逻辑。

**Rebuild data pipeline** (weighted phases for progress): trade calendar → ETF daily seed → shares backfill → sentiment.

**Frontend** (React 18, TypeScript strict, Vite, React Query v5, ECharts, Tailwind)，按功能域聚合:
- `pages/` — Dashboard / Resonance / Sentiment / EtfDetail / KlineCompare / PortfolioBacktest / TradeCalendar / DataManage / ScheduledTasks。
- `components/` — 按域：`common`(Layout/EtfSelector/chartZoom) `resonance` `monitor` `kline` `portfolio` `sentiment` `calendar` `data`。
  图表 option 构建拆为纯函数（`xxxOption.ts` 等），组件用 `useMemo` 调用。
- `api/client.ts` + `api/types.ts` — 集中 HTTP 封装（超时 + 错误解析）与全部类型定义；
  `types.ts` 是按领域拆分的 `types/*.ts` 聚合出口，新增类型就近放入对应领域文件。
  组件禁止直接 `fetch()`。
- `hooks/` — React Query 封装（`useSignals` `useResonance` `useSentiment` `useData` `useCalendar` 等）+ 图表联动（`useChartSync` `useAxisPointerBridge`）。

**CLI** (`cli/resonance.py`) — 直读 SQLite（无需服务端）输出共振结论，供外部 Agent（Qoderwork）转 IM 通知。

## Key constraints (from AGENTS.md)

- **300-line hard cap** per source file (`.py`, `.tsx`, `.ts`). Split when approaching 250.
- Python functions <50 lines; type hints required; snake_case; constants UPPER_SNAKE_CASE (→ `base/config.py`).
- TypeScript strict mode; `any` forbidden except for ECharts options.
- **ECharts merge 语义**：条件性 markPoint/markLine/markArea 必须始终定义为对象，空数组即清除（勿用 undefined）。
- Dates: `YYYY-MM-DD` internally, `YYYYMMDD` at akshare boundaries.
- Non-trading-day / missing data / network failure → return empty or degraded result, never throw.
- 数据拉取防封禁：先查库跳过已覆盖交易日、TTL 缓存、批量限速、失败冷却、COALESCE 防 NULL 覆盖、边拉边写。

## Build, lint, test

```bash
# 后端（提交前必须全过）
cd backend && ruff check . && ruff format --check . && mypy .
cd backend && pytest -q                      # 关键计算逻辑单测（backend/tests/）

# 前端（tsc + vite build；eslint 已配置）
cd frontend && npm run lint && npm run build
```

## Data flow for a new feature

1. Add fetch logic in `base/fetch/` (if new data source needed).
2. Add pure analysis: 策略 → `base/analysis/strategy/<后缀>.py` 并在 `router.py` 分派；其他计算 → 对应领域 `analysis/` 或 `base/analysis/`。
3. Add storage in `base/store/` (new repo or extend existing).
4. Expose via `api/` router (领域专属 → 领域 `api.py`；跨页共用 → `base/api/`).
5. Wire scheduling: 后台任务在 `job_registry.py` 注册并在 `api/data.py` 校验参数；定时任务在 `tasks.py` 注册 + `scheduled_defs.py` 登记说明。
6. Add constants to `base/config.py`.
7. Frontend: type in `api/types/*.ts`, hook in `hooks/`, page/component in `pages/` or `components/<域>/`（超 250 行拆子组件/option 纯函数）。
