# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
完整开发规范（代码分层 / 三槽位策略工作流 / 量化推演方法论 / 检查框架 / 生产部署）见 AGENTS.md；本文档只给快速上手指南。

## Quick start

```bash
./start.sh                                 # 一键: 建 .venv、装依赖、同时起前后端
./start.sh --foreground                    # 前台运行（交互终端下默认 nohup 后台化，日志 nohup.out）
pkill -f 'uvicorn main:app.*--port 8001'   # 停止后台服务
./start-prod.sh [--daemon|--skip-build]    # 生产: 前端构建 dist 由后端单进程托管
# 手动:
cd backend && python3 -m uvicorn main:app --port 8001   # API :8001
cd frontend && npm run dev                              # UI :5174（/api 代理到 8001）
```

- 数据库 `~/.etf-monitor/etf_monitor.db`（`ETF_MONITOR_HOME` 覆盖）。空库首次启动只回填情绪，ETF 日度需在「数据管理」页点「一键重建」。
- `start.sh` 会 kill 8001/5174 端口并清 `__pycache__`：不要并发跑多个实例。`nohup.out` 是运行日志（可达数 MB），排查用 `tail`，不要整体读取。

## Build, lint, test（提交前必须全过）

```bash
cd backend && ruff check . && ruff format --check . && mypy .
cd backend && pytest -q                      # 全量单测
cd backend && pytest tests/test_zz.py -q     # 单文件（pytest.ini 已设 pythonpath=.）
cd frontend && npm run lint                  # eslint，0 error（react-refresh warning 容忍）
cd frontend && npm run build                 # = tsc && vite build（无独立 typecheck 脚本）
cd frontend && npx tsc --noEmit              # 仅类型检查
python3 scripts/backtest_portfolio.py        # 组合回测（用真实库数据）
```

工具配置的**有意容忍项，勿"顺手修"**：ruff 忽略 `DTZ005/DTZ007`（中国市场 naive datetime 约定）与 `BLE001`（第三方库宽异常）；eslint 显式关闭 `react-hooks/set-state-in-effect`、`react-hooks/refs`（React 18 合法模式）；tsc 开启 `noUnusedLocals/noUnusedParameters`（未用变量会让 build 失败）。

## Architecture

**Backend**（Python 3.9+，FastAPI，SQLite WAL）— 严格单向分层，
按前端页面领域聚合目录（页面私有逻辑进领域目录，跨页共用下沉 base/）:

```
base/fetch → 领域 analysis → base/store → 领域 api
                     ↑
              base/scheduler（编排层，允许依赖领域 analysis 的计算函数）
              main.py（仅 app 组装）
```

- `base/config.py` — 全部可调常量（ETF 清单/阈值/窗口/调度时间/限流参数）。
- `base/fetch/` — HTTP 请求与原始数据解析（kline / realtime / shares / sentiment / calendar / adjust_factor / turnover_official / supply）。无业务逻辑。
- `base/analysis/` — 纯函数零 I/O：`sentiment/core.py`（分位数/情绪分区）、`strategy/`（每只 ETF 独立策略 + `router.py` 分派 + `metrics.py` 共用轮次指标）、`shares_adjust.py`。
- **策略三槽位**（`router.py` 三个注册表，`compute_trades(version=)` 取 `stable|beta|band`）：STABLE 覆盖全部 ETF（未注册走 `_run_default` 通用多指标共振）；BETA 手动注册才有，前端按钮由 `/trades/versions` 驱动自动禁用；BAND 为独立波段槽位。**每次改 Beta 必跑 `python3 scripts/compare_strategy_versions.py <code>`**（退出码 0=通过 / 1=漏笔 / 2=跑输），验收门槛与升降级流程见 AGENTS.md §7。
- 领域目录：`resonance/`（core 五灯判定 / composite 综合概率 V2 门控 / factors 份额因子 / intraday 盘中信号 / evidence* 逐指标证据）、`portfolio/`（simulator 等权满仓调度）、`supply/`（一级退出监测：解禁/减持/IPO 纯函数聚合）。
- `base/store/` — 全部 SQLite 访问（`database.py` 连接/建表/迁移 + 各表 repo），参数化查询；含 supply 表 `unlock_events` / `reduction_events` / `ipo_events` / `supply_meta`。
- **ETF 清单动态化**：`etfs` 表为真源（`etf_repo.py`：CRUD/覆盖统计/`purge_code_data`），`config.ETFS` 仅是运行时镜像——增删后 `load_into_config()` **原地 clear/update**（绝不重新绑定），约 15 个 `from base.config import ETFS` 的模块自动感知；首启 `seed_from_config()` 把配置播种入库。镜像必须留在 config（叶子层），因 `base/fetch` 不允许 import `base/store`。管理接口在 `base/api/etf_manage.py`（`/api/etfs` 增删查+代码校验），510300/589680 为 `PROTECTED_ETFS` 不可删。
- `base/api/` — 跨页共用接口（etf / sentiment / static）；领域 api（resonance / portfolio / supply 的 `api.py`）+ 其余页面接口在 `api/`。
- `base/scheduler/` — APScheduler 定时任务 + 后台任务引擎：`tasks.py`（注册层，阻塞任务经 `asyncio.to_thread` 派发，勿在事件循环上做同步网络 I/O）、`intraday_tasks.py` / `daily_tasks.py`（任务实现）、`state.py`（共享内存缓存）、`job_manager.py`（引擎+进度）、`job_registry.py`（任务元信息；新任务必须在此注册并在 `api/data.py` 校验参数）、`etf_daily_jobs.py` / `shares_jobs.py`（份额逐日写入核心在 `shares_fill.py`）/ `sentiment_jobs.py` / `supply_jobs.py` / `share_adjust_jobs.py`、`etf_backfill_job.py`（单标的五阶段回填，动态添加后的初始化）、`calendar_slots.py`（数据槽位台账：交易日历即填充槽）、`rebuild.py`（一键重建流水线）、`recalc.py`、`time_guard.py`（交易时段守卫）。
- `main.py` — App 组装（lifespan/CORS/路由注册/静态托管），仅组装无业务逻辑。

**Rebuild pipeline**（加权进度）：交易日历 → ETF 日度 seed → 份额回填 → 市场情绪。

**Frontend**（React 18, TypeScript strict, Vite, React Query v5, ECharts, Tailwind）:
- `pages/` — Resonance / PortfolioBacktest / PrimaryExit(一级退出监测) / EtfManage(ETF 管理: 动态增删标的+按标的回填) / Sentiment / Dashboard(导航名「ETF流向分析」) / EtfDetail / KlineCompare / TradeCalendar / DataManage / ScheduledTasks，以及「逻辑说明」知识页 Methodology(交易框架) / PolicyBackdrop / MacroLeverage / RealRate / HouseholdGov / Response。
- 知识页模式：文案数据放 `components/<域>/sections.ts`，渲染组件 `*Content.tsx`，配 `common/ArticleToc` 目录；页面文件本身只是壳（照着加新知识页即可）。
- `components/` — 按域：`common`(Layout/EtfSelector/chartZoom/ArticleParts/ArticleToc) `resonance` `monitor` `kline` `portfolio` `sentiment` `calendar` `data` `supply` + 知识页域（methodology/policy/macro/realrate/household/response）。图表 option 构建拆为纯函数（`xxxOption.ts` 返回 `{option, dates}`），组件 `useMemo` 调用。
- `api/client.ts` + `api/types.ts` — 集中 HTTP 封装与全部类型（`types.ts` 是 `types/*.ts` 的聚合出口，新增类型就近放入对应领域文件）。组件禁止直接 `fetch()`。
- `hooks/` — React Query 封装（`useResonance` `useSignals` `useSupply` `useData` `useCalendar` 等）+ 图表联动（`useChartSync` `useAxisPointerBridge`）。

**CLI**（`cli/`）— `resonance.py` / `band.py` 在 base/ 重构后已与代码脱节（import 仍是旧路径，当前不可用），勿据此判断数据问题。

## Key constraints (from AGENTS.md)

- **300-line hard cap** per source file（`.py`, `.tsx`, `.ts`）。接近 250 行必须拆分；存量超标文件改动时顺手拆。
- Python 函数 <50 行；type hints 全覆盖；snake_case；常量 UPPER_SNAKE_CASE（系统级常量 → `base/config.py`）。
- TypeScript strict；除 ECharts option 外禁止 `any`。
- **ECharts merge 语义**：条件性 markPoint/markLine/markArea 必须始终定义为对象，空数组即清除（勿用 undefined，否则切换 ETF 后旧买卖点残留）。
- 日期内部统一 `YYYY-MM-DD`，akshare 边界转 `YYYYMMDD`。时间范围参数统一 `start_date`/`end_date`，`days` 仅作无日期回退。
- 非交易日 / 缺数据 / 网络失败 → 返回空或降级结果，绝不抛异常。
- 数据拉取防封禁：先查库跳过已覆盖交易日、TTL 缓存、批量限速、失败冷却、`COALESCE` 防 NULL 覆盖、边拉边写、渐进式分批回填。
- 数据库 / 日志 / PDF / `docs/委托理财合同*` 已在 `.gitignore`（公开仓库），勿提交。

## Data flow for a new feature

1. Add fetch logic in `base/fetch/` (if new data source needed).
2. Add pure analysis: 策略 → `base/analysis/strategy/<后缀>.py` 并在 `router.py` 对应槽位注册（正式版进 `STABLE_STRATEGIES`）；其他计算 → 对应领域 `analysis/` 或 `base/analysis/`。
3. Add storage in `base/store/` (new repo or extend existing).
4. Expose via `api/` router（领域专属 → 领域 `api.py`；跨页共用 → `base/api/`）。
5. Wire scheduling: 后台任务在 `job_registry.py` 注册并在 `api/data.py` 校验参数；定时任务在 `tasks.py` 注册 + `scheduled_defs.py` 登记说明。
6. Add constants to `base/config.py`.
7. Frontend: type in `api/types/*.ts`, hook in `hooks/`, page/component in `pages/` or `components/<域>/`（超 250 行拆子组件/option 纯函数）。

## Docs & deployment

- 算法/数据文档：`docs/strategy_algorithms.md`、`docs/data_lineage.md`、`docs/algorithm_technical.md`；根目录《量化买卖规律发现方法论与可靠性评估.md》（事件研究方法论依据）、《交易操作框架.md》（= 前端「交易框架」知识页文案来源）。
- 生产部署（上传 → /ops 重新部署 → DB 增量同步三步，含 `VITE_APP_BASE=/resonance` 构建要求与停服备份纪律）见 AGENTS.md §9。
