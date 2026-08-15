# ETF 买卖分析系统 — 开发规范与量化推演流程

> 本文件是本项目（QoderCN / opencode 等任何 Agent）的行为准则：代码开发规范 + 金融量化算法推演方法论。
> 所有新增/修改代码必须符合本规范；与本规范冲突的旧代码，修改时一并修正。

## 1. 核心铁律

1. **单文件 ≤ 300 行**：任何源码文件（`.py` / `.ts` / `.tsx`）严禁超过 300 行；接近 250 行时必须拆分。
   例外：`package.json`、`tsconfig.json`、`ruff.toml` 等纯配置文件。
2. **按领域组织目录**：代码按领域放对应目录，禁止在无关目录或根目录散落新文件；新增领域先建目录，禁止在已有大文件里堆功能。
3. **提交前必须通过代码检查框架**：后端 ruff + mypy，前端 tsc + eslint（见第 5 节）。

## 2. 目录结构（按页面领域聚合）

### 2.1 后端 `backend/`（页面领域目录 + 共用 base）

按前端页面划分领域目录，一个页面领域一个文件夹（含该页面的 `api` 与 `analysis`）；多个页面共用的功能全部下沉 `base/`。

```
backend/
├── base/            # 共用功能（多页面领域共用）
│   ├── config.py    # 系统级命名常量
│   ├── fetch/       # HTTP 请求与原始数据解析
│   ├── store/       # 全部 SQLite 操作（参数化查询）
│   ├── scheduler/   # 任务编排（data_jobs/tasks/job_registry/rebuild、etf_daily_jobs/shares_jobs 回填）
│   ├── analysis/    # 共用纯函数计算
│   │   ├── sentiment/   # 市场情绪（共振页 + 情绪页共用）
│   │   └── strategy/    # 各 ETF 专属买卖点（共振页 + 组合回测共用）
│   └── api/         # 共用接口（etf.py 列表/K线/刷新、sentiment.py 情绪概览）
├── resonance/       # 多指标共振页面领域
│   ├── analysis/    # core.py 共振计算、evidence.py 日级证据、composite.py 综合概率、factors.py 份额因子、intraday.py 盘中信号
│   └── api.py       # /api/resonance 路由（overview/day/trades）
├── portfolio/       # 组合回测页面领域
│   ├── analysis/    # simulator.py 净值模拟（纯函数）
│   └── api.py       # /api/portfolio 路由（backtest，买卖点复用 base/analysis/strategy）
├── api/             # 其余页面接口（calendar/data/realtime/signals/stats，迁移完成前暂存）

# 注意: K线对比页(EtfDetail/KlineCompare)无专属后端代码,
# 其数据源(/etf/list、/etf/{code}/history、/resonance/trades)均为跨页面共用, 已在 base/api/etf.py 与共振领域
```

规则：

- 新增页面领域：建 `<领域>/` 目录（`analysis/` + `api.py`），从 `api/` 迁入专属代码；共用代码留在/迁入 `base/`。
- 依赖方向：`base/fetch/ → 领域 analysis → base/store → 领域 api`，严禁反向引用；`base/scheduler/` 为编排层，允许依赖各领域 `analysis` 的计算函数（如共振信号回填任务调 `resonance.analysis.composite`）。
- 策略按标的拆文件：`base/analysis/strategy/<后缀>.py`，统一经 `base/analysis/strategy/router.py` 分派。
- 新任务必须在 `base/scheduler/job_registry.py` 注册（标签/独占/默认参数）并在 `api/data.py` 校验参数。
- 时间范围参数统一 `start_date`/`end_date`（`YYYY-MM-DD`），`days` 仅作无日期时的回退。

### 2.2 前端 `frontend/src/`（按功能域聚合）

| 目录 | 职责 |
|---|---|
| `pages/` | 路由页面组件（每页一文件，超 300 行拆子组件） |
| `components/common/` | 跨域通用（`Layout`、`EtfSelector`、`chartZoom` 缩放工具） |
| `components/resonance/` | 共振页（`ResonanceChart/Heatmap/Lights/EvidencePanel/MethodNote`、K线 option 构建） |
| `components/monitor/` | 大盘监控（`EtfSignalGrid`、`SignalCard`） |
| `components/kline/` | K线/对比图（`KlineChart`、`CompareKline`、`SignalHistoryChart` 及 option 构建、区间统计/标记工具） |
| `components/portfolio/` | 组合回测（`PortfolioChart`、`TradePopups`） |
| `components/sentiment/` | 市场情绪（`SentimentLineChart`） |
| `components/calendar/` | 交易日历（`MiniMonth`） |
| `components/data/` | 数据管理（`JobsPanel`、`SchedulerPanel`、`SourceCard`） |
| `hooks/` | 业务 hooks（数据请求、状态逻辑） |
| `api/` | `client.ts`（全部 HTTP 封装）+ `types.ts`（全部类型定义） |

- 页面私有子组件就近放 `components/<域>/` 或独立组件文件，禁止在页面文件内堆全部代码。
- 图表 option 构建（数据驱动、无副作用）拆为 `<域>/xxxOption.ts` 纯函数返回 `{ option, dates }`，组件用 `useMemo` 调用并缓存。
- 数据获取统一走 `api/client.ts` + React Query hooks，禁止组件内直接 `fetch()`。

## 3. 编码规范

### 3.1 Python

- type hints 全覆盖（含返回类型）；`snake_case` 函数/变量、`UPPER_SNAKE_CASE` 常量、类 `PascalCase`。
- 函数 ≤ 50 行；单函数只做一件事。
- 魔法数字必须提取为命名常量：策略参数放策略文件级常量（附注释依据），系统参数放 `config.py`。
- 网络请求必须设置 timeout；失败优雅降级（返回空/None，不抛异常）。
- 纯函数（analysis/）不得做 I/O；docstring 写明核心认知、历史教训、算法结构（策略文件必写）。

### 3.2 TypeScript

- `strict` 模式；函数组件 + hooks；禁止 `any`（唯一例外：ECharts option 对象）。
- 类型定义集中在 `api/types.ts`，禁止组件内散落重复类型。
- 网络请求统一走 `client.ts`（带超时 + 错误解析），失败时页面优雅降级。
- **ECharts 性能**：数据驱动的 option 必须 `useMemo` 缓存；缩放/拖动类交互不得每帧重建 option（用 `dispatchAction` 同步外部变化，事件回调防抖）。
- **ECharts merge 语义**：条件性标记（`markPoint`/`markLine`/`markArea`）必须**始终定义为对象**、数据为空数组即清除——用 `undefined` 表示"清除"在 merge 模式下会导致旧数据残留（如切换 ETF 后旧买卖点残留）。

## 4. 目录与文件验收

- 新建文件前先确认所属领域目录；若目标文件已接近 300 行，必须新建文件。
- 删除/合并代码时同步清理死代码：无引用的文件、端点、类型、常量必须删除（如 V2/V3/V4/V5 遗留策略清理）。
- 文档与代码同步：本文件、策略文件 docstring、前端说明文案在行为变更时同步更新。

## 5. 代码检查框架（强制）

### 5.1 后端（Python）

| 工具 | 配置 | 强制要求 |
|---|---|---|
| ruff | `ruff.toml`（或 `pyproject.toml`） | lint + format 零错误 |
| mypy | `mypy.ini` | 类型检查零错误 |
| pytest | `backend/tests/` | 关键计算逻辑（策略/信号/组合）必须有测试 |

验收命令（提交前必须通过）：

```bash
cd backend
ruff check . && ruff format --check . && mypy .
pytest -q
```

### 5.2 前端（TypeScript / React）

| 工具 | 配置 | 强制要求 |
|---|---|---|
| tsc | `tsconfig.json`（strict） | `tsc --noEmit` 零错误 |
| eslint | `eslint.config.js` | lint 零错误 |

验收命令（提交前必须通过）：

```bash
cd frontend
npm run lint     # eslint . （配置后生效）
npm run build    # tsc && vite build
```

### 5.3 提交门槛

- 任何改动提交前必须通过上述对应检查；检查失败必须先修复再提交，禁止跳过（`--no-verify` 类绕过）。
- 涉及跨层/跨文件改动时，两端检查都要跑。

## 6. 数据与拉取规范（防远端封禁）

- **新鲜度判断**：拉取前先查库，已覆盖目标交易日则跳过远端（参考 `job_backfill_etf_daily` 的 skip 与"已是最新"提示）。
- **内存 TTL 缓存**：`KLINE_CACHE_TTL_SEC` 内重复调用不触网；失败也冷却（`KLINE_FAIL_COOLDOWN_SEC`），防止失败重试风暴。
- **批量限速**：相邻请求加间隔（`FETCH_SLEEP_SEC`），连续失败暂停（`SHARES_FAIL_PAUSE_SEC`），空结果重试（`SHARES_RETRY`）。
- **upsert 不得用 NULL 覆盖已有值**：新数据缺字段时用 `COALESCE(excluded.x, 原值)`（参考 `daily_repo.upsert_daily`，曾因回填日度清空全部份额）。
- **按标的补齐粒度**：份额等回填只写缺失的 ETF，不影响其他标的（`_missing_share_etfs`）。
- **边拉边写**：逐日任务每拉到一天立即入库（`on_row` 回调），中断不丢已拉数据；重跑自动跳过已完成日期。
- **渐进式分批回填**：带 `start_date` 的日度/份额回填按 `chunk_days`（默认 10）个交易日一批处理并上报进度；区间完整覆盖才跳过（`_range_covered`，后向扩展免强制重拉），逐日跳过已入库日期，重跑只补缺失段（`_seed_one_etf`）。
- **交易日历即填充槽（数据槽位台账）**：交易日历定义"哪天应该有数据"——`trade_calendar` 带四源覆盖属性（`etf_daily_ok`/`shares_ok`/`turnover_ok`/`margin_ok`），由 `refresh_calendar_slots` 刷新（三个回填任务结束时自动刷新）；数据起始日期设置（`settings.data_slot_start`）控制系统应有数据的"总量"（槽位 = 起始日至今的交易日），缺口 = 槽位−实际，由 `_missing_etf_ranges`/`backfill_missing_*` 定位补全；交易日历页按覆盖着色（绿=四源全/黄=部分/红=槽位无数据），数据管理页可调起始日期并一键刷新台账。
- **K线历史拉取**：腾讯接口单次 limit 上限约 640 根，更早历史必须用日期区间（`KLINE_URL_RANGE` + `fetch_kline(start_date=…, end_date=…)`）；前端 `KLINE_DAYS` 与 `/etf/{code}/history` 上限需同步放大才能看到更长历史。
- **非交易日不拉取**：回溯跳过周末，目标日期用 `get_last_trading_day`。
- 手动刷新接口限速（`REFRESH_MIN_INTERVAL_SEC`）。

## 7. 量化策略开发规范

- 每只 ETF 独立策略文件：`base/analysis/strategy/<后缀>.py`，含 `<CODE>_CODE` 常量；在 `base/analysis/strategy/router.py` 的 `compute_trades` 中按代码分派接入（K线类策略需注入 `_tp`/`_mp` 分位数据），页面「共振买卖点」与「组合回测」共用该入口。
- 所有阈值/窗口/冷却期为文件级 UPPER_SNAKE_CASE 常量，附注释说明依据。
- 策略输出结构固定：`{code, trades, metrics, holding}`；`trades` 每项含 `date/action/price/reason`，reason 写明触发路径。
- 文件 docstring 必须写明：核心认知（资产特征）、历史教训（买太早/卖太早/假反弹的实际案例）、算法结构。
- 回测用真实库数据跑全历史（`scripts/backtest_portfolio.py` 或内联脚本），核对每轮买卖点与收益，并检查"买入后 10 日最大回撤"。

## 8. 金融量化算法推演流程（核心方法论）

为某只 ETF 设计/重构买卖点策略时，严格按以下顺序：

1. **数据先行**：读取该 ETF 完整历史（注意份额回填范围），列出全部非 NEUTRAL 信号日（日期/收盘/涨跌/量比/pp/方向/份额），并查看关键底部/顶部区段的逐日数据。
2. **识别资产特征**：波动率、暴跌集群形态（几日内几个 ACCUMULATE）、DISTRIBUTE 集群长短、份额信号强度（弱 ±0.1 亿 还是强 ±10 亿+），与已上线策略的 ETF 对比差异。
3. **复盘历史教训**：从数据中找出"买太早 / 卖太早 / 假反弹 / 卖飞"的真实案例，**每条规则必须对应至少一个历史案例**；记录案例日期与价格作为验收基准。
4. **规则设计**：
   - 买入路径化：P1 单日极端恐慌（左侧）、P2 低位孤立吸筹（下跌末期）、P3 暴跌集群右侧（等反弹确认 + 破前低作废）等；集群中禁止左侧。
   - 卖出：趋势破位（MA 深度破位）/ 双确认（次数 + 份额流出）/ 顶部观察（延迟卖出 + 破位离场），按资产特征选型。
   - 全部参数命名化；份额数据缺失历史时，份额条件须可降级（`sd is None or sd > 0`）。
5. **回测验证**：跑全历史，逐轮核对与案例一致（买入日、卖出日、收益）；检查买入后 10 日回撤 ≈ 0；保留历史赢家轮次不被破坏。
6. **防过拟合纪律**：
   - 不引入无案例支撑的规则；不为单轮最优收益调参。
   - 诚实汇报 trade-off（如横盘顶延迟卖出的 1% 代价 vs 真延迟顶的 4-7% 收益）。
   - "错过行情"是允许的，系统不追求抓住所有轮次。
7. **接入与同步**：`strategy/router.py` 分派接入 → 前端共振图自动生效；策略文件 docstring 与文档保持同步。

## 9. 运行与验证

```bash
./start.sh                        # 一键启动前后端（自动建 venv/装依赖/镜像探测）
cd backend && ruff check . && mypy . && pytest -q   # 后端检查框架
cd frontend && npm run lint && npm run build        # 前端检查框架
python3 scripts/backtest_portfolio.py  # 组合回测验证
```

- 数据回填入口：前端「数据管理」页（日期区间 + 强制重拉开关），优先于脚本。
- 数据库：`~/.etf-monitor/etf_monitor.db`（`ETF_MONITOR_HOME` 可覆盖）。
- 网络请求失败时前端必须优雅降级（空态 + 重试），禁止页面崩溃。
