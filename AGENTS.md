# ETF 买卖分析系统 — 开发规范与量化推演流程

> 本文件是本项目（QoderCN / opencode 等任何 Agent）的行为准则：代码开发规范 + 金融量化算法推演方法论。
> 所有新增/修改代码必须符合本规范；与本规范冲突的旧代码，修改时一并修正。

## 0. 快速上手（Agent 必读）

命令在对应子目录执行（`backend/`、`frontend/`）。

```bash
./start.sh                  # 一键启动前后端；交互终端下自动 nohup 后台化（日志 nohup.out）
./start.sh --foreground     # 前台运行（退出时统一清理）
# 停止后台服务: pkill -f 'uvicorn main:app.*--port 8001'
./start-prod.sh [--daemon|--skip-build]   # 生产: 前端构建 dist 由后端单进程托管
# 手动: cd backend && python3 -m uvicorn main:app --port 8001   (API :8001)
#       cd frontend && npm run dev                              (UI :5174, /api 代理到 :8001)
```

检查框架（提交前必须全过，见第 5 节）：

```bash
cd backend && ruff check . && ruff format --check . && mypy .
cd backend && pytest -q                        # 全量测试
cd backend && pytest tests/test_zz.py -q       # 单文件（pytest.ini 已设 pythonpath=.）
cd frontend && npm run lint                    # eslint，0 error（react-refresh warning 属容忍）
cd frontend && npm run build                   # = tsc && vite build（无独立 typecheck 脚本）
cd frontend && npx tsc --noEmit                # 仅类型检查
python3 scripts/backtest_portfolio.py          # 组合回测验证
```

- 数据库：`~/.etf-monitor/etf_monitor.db`（`ETF_MONITOR_HOME` 覆盖）；空库首次启动只回填情绪，ETF 日度需在「数据管理」页点「一键重建」。
- `./start.sh` 会先 `kill -9` 8001/5174 端口并删 `__pycache__`：不要并发跑多个实例。
- `nohup.out` 是运行日志（已 gitignore，可达数 MB）：排查用 `tail`，**不要整体读取**。
- 工具配置的**有意容忍项，勿"顺手修"**：
  - ruff：`target=py39, line-length=120`，故意 `ignore DTZ005/DTZ007`（中国市场 naive datetime 约定）与 `BLE001`（第三方库宽异常）。
  - mypy：对 `akshare/requests/apscheduler/fastapi/pydantic` 忽略缺失 stubs。
  - eslint：`react-hooks/set-state-in-effect`、`react-hooks/refs` 显式关闭（React 18 合法模式），勿重新开启。
  - tsc 开启 `noUnusedLocals/noUnusedParameters`：未用变量会让 `npm run build` 失败。
- `cli/resonance.py` / `cli/band.py` 已与 `base/` 重构脱节（import 仍是 `from config`/`from store...`；`band.py` 另有 py3.9 f-string 语法错误），当前不可用，勿据此判断数据问题。
- 方法论/数据文档：`docs/strategy_algorithms.md`、`docs/data_lineage.md`、`docs/algorithm_technical.md`、根目录《量化买卖规律发现方法论与可靠性评估.md》（`scripts/event_study.py` 的方法论依据）。

## 1. 核心铁律

1. **单文件 ≤ 300 行**：任何源码文件（`.py` / `.ts` / `.tsx`）严禁超过 300 行；接近 250 行时必须拆分。
   例外：`package.json`、`tsconfig.json`、`ruff.toml` 等纯配置文件。
   存量超标文件（`base/store/daily_repo.py`、`pages/Resonance.tsx`、`pages/DataManage.tsx`、`components/sentiment/SentimentLineChart.tsx`、`components/resonance/ResonanceHeatmap.tsx`）改动时顺手拆分，禁止继续往里堆逻辑。
2. **按领域组织目录**：代码按领域放对应目录，禁止在无关目录或根目录散落新文件；新增领域先建目录，禁止在已有大文件里堆功能。
3. **提交前必须通过代码检查框架**：后端 ruff + mypy，前端 tsc + eslint（见第 5 节）。

## 2. 目录结构（按页面领域聚合）

### 2.1 后端 `backend/`（页面领域目录 + 共用 base）

按前端页面划分领域目录，一个页面领域一个文件夹（含该页面的 `api` 与 `analysis`）；多个页面共用的功能全部下沉 `base/`。

```
backend/
├── base/            # 共用功能（多页面领域共用）
│   ├── config.py    # 系统级命名常量（ETF 清单/阈值/窗口/调度/限流）
│   ├── fetch/       # HTTP 请求与原始数据解析（kline/realtime/shares/sentiment/calendar/adjust_factor/turnover_official）
│   ├── store/       # 全部 SQLite 操作（参数化查询；database 连接建表迁移 + 各表 repo）
│   ├── scheduler/   # 任务编排（tasks/daily_tasks/intraday_tasks/job_manager/job_registry/
│   │                #   scheduled_defs/rebuild/recalc/time_guard/state + 各回填 jobs + calendar_slots）
│   ├── analysis/    # 共用纯函数计算
│   │   ├── sentiment/   # 市场情绪（共振页 + 情绪页共用）
│   │   ├── strategy/    # 各 ETF 专属买卖点（共振页 + 组合回测共用）
│   │   └── shares_adjust.py  # 份额复权
│   └── api/         # 共用接口（etf.py 列表/K线/刷新、sentiment.py 情绪概览、static.py 静态托管）
├── resonance/       # 多指标共振页面领域
│   ├── analysis/    # core.py 共振计算、evidence*.py 日级证据、composite.py 综合概率、factors.py 份额因子、intraday.py 盘中信号
│   └── api.py       # /api/resonance 路由（overview/day/trades）
├── portfolio/       # 组合回测页面领域
│   ├── analysis/    # simulator.py 净值模拟（纯函数）
│   └── api.py       # /api/portfolio 路由（backtest，买卖点复用 base/analysis/strategy）
├── api/             # 其余页面接口（calendar/data/realtime/signals/stats，迁移完成前暂存）
└── tests/           # pytest 单测（策略/信号/组合/份额复权）

# 顶层: cli/（外部 Agent 读库出口，见第 0 节失效说明）、scripts/（直跑脚本）、docs/（算法/数据血缘文档）
# 注意: K线对比页(EtfDetail/KlineCompare)无专属后端代码,
# 其数据源(/etf/list、/etf/{code}/history、/resonance/trades)均为跨页面共用, 已在 base/api/etf.py 与共振领域
```

规则：

- 新增页面领域：建 `<领域>/` 目录（`analysis/` + `api.py`），从 `api/` 迁入专属代码；共用代码留在/迁入 `base/`。
- 依赖方向：`base/fetch/ → 领域 analysis → base/store → 领域 api`，严禁反向引用；`base/scheduler/` 为编排层，允许依赖各领域 `analysis` 的计算函数（如共振信号回填任务调 `resonance.analysis.composite`）。
- 策略按标的拆文件：`base/analysis/strategy/<后缀>.py`，统一经 `base/analysis/strategy/router.py` 分派。
- 新任务必须在 `base/scheduler/job_registry.py` 注册（标签/独占/默认参数）并在 `api/data.py` 校验参数；定时任务另在 `scheduled_defs.py` 登记。
- 时间范围参数统一 `start_date`/`end_date`（`YYYY-MM-DD`），`days` 仅作无日期时的回退；日期在 akshare 边界转 `YYYYMMDD`。
- `scripts/` 为直跑脚本：靠 `sys.path.insert` 注入 `backend/`，部分带 `# ruff: noqa` / `# mypy: ignore-errors`，不要纳入包内引用。

### 2.2 前端 `frontend/src/`（按功能域聚合）

| 目录 | 职责 |
|---|---|
| `pages/` | 路由页面组件（每页一文件，超 300 行拆子组件） |
| `components/common/` | 跨域通用（`Layout`、`EtfSelector`、`chartZoom` 缩放工具） |
| `components/resonance/` | 共振页（`ResonanceChart/Heatmap/Lights/EvidencePanel/MethodNote`、`klineOption`/`macdOption`/`emaOverlay`） |
| `components/monitor/` | 大盘监控（`EtfSignalGrid`、`SignalCard`） |
| `components/kline/` | K线/对比图（`KlineChart`、`CompareKline`、`SignalHistoryChart`、`RangeStatsPanel` 及 option 构建、区间统计/标记工具） |
| `components/portfolio/` | 组合回测（`PortfolioChart`、`TradePopups`） |
| `components/sentiment/` | 市场情绪（`SentimentLineChart`） |
| `components/calendar/` | 交易日历（`MiniMonth`） |
| `components/data/` | 数据管理（`JobsPanel`、`SchedulerPanel`、`SourceCard`、`FlowSteps`、`RecalcCard`） |
| `hooks/` | React Query 数据 hooks + 图表联动（`useChartSync`、`useAxisPointerBridge`）、`useLocalStorage`/`usePinnedEtfs` 等 |
| `utils/` | 通用工具（`calendar`、`idbCache` 前端历史缓存） |
| `api/` | `client.ts`（全部 HTTP 封装）+ `types.ts`（`types/*.ts` 按领域拆分后的聚合出口） |

- 页面私有子组件就近放 `components/<域>/` 或独立组件文件，禁止在页面文件内堆全部代码。
- 图表 option 构建（数据驱动、无副作用）拆为 `<域>/xxxOption.ts` 纯函数返回 `{ option, dates }`，组件用 `useMemo` 调用并缓存。
- 数据获取统一走 `api/client.ts` + React Query hooks，禁止组件内直接 `fetch()`；新类型就近放 `api/types/<域>.ts` 并从 `types.ts` 聚合出口导出。
- 子路径部署：构建时 `VITE_APP_BASE=/resonance npm run build`，代码中经 `__APP_BASE__` 读取。

## 3. 编码规范

### 3.1 Python

- type hints 全覆盖（含返回类型）；`snake_case` 函数/变量、`UPPER_SNAKE_CASE` 常量、类 `PascalCase`。
- 函数 ≤ 50 行；单函数只做一件事。
- 魔法数字必须提取为命名常量：策略参数放策略文件级常量（附注释依据），系统参数放 `config.py`。
- 网络请求必须设置 timeout；失败优雅降级（返回空/None，不抛异常）。
- 纯函数（analysis/）不得做 I/O；docstring 写明核心认知、历史教训、算法结构（策略文件必写）。

### 3.2 TypeScript

- `strict` 模式；函数组件 + hooks；禁止 `any`（唯一例外：ECharts option 对象）。
- 类型定义集中在 `api/types/`（经 `types.ts` 聚合），禁止组件内散落重复类型。
- 网络请求统一走 `client.ts`（带超时 + 错误解析），失败时页面优雅降级。
- **ECharts 性能**：数据驱动的 option 必须 `useMemo` 缓存；缩放/拖动类交互不得每帧重建 option（用 `dispatchAction` 同步外部变化，事件回调防抖）。
- **ECharts merge 语义**：条件性标记（`markPoint`/`markLine`/`markArea`）必须**始终定义为对象**、数据为空数组即清除——用 `undefined` 表示"清除"在 merge 模式下会导致旧数据残留（如切换 ETF 后旧买卖点残留）。

## 4. 目录与文件验收

- 新建文件前先确认所属领域目录；若目标文件已接近 300 行，必须新建文件。
- 删除/合并代码时同步清理死代码：无引用的文件、端点、类型、常量必须删除（如 V2/V3/V4/V5 遗留策略清理）。
- 文档与代码同步：本文件、策略文件 docstring、前端说明文案在行为变更时同步更新。

## 5. 代码检查框架（强制）

配置项的有意容忍见第 0 节，勿擅自放开。

### 5.1 后端（Python）

| 工具 | 配置 | 强制要求 |
|---|---|---|
| ruff | `backend/ruff.toml` | lint + format 零错误 |
| mypy | `backend/mypy.ini` | 类型检查零错误 |
| pytest | `backend/tests/`（`pytest.ini` 设 `pythonpath=.`） | 关键计算逻辑（策略/信号/组合）必须有测试 |

验收命令（提交前必须通过，在 `backend/` 下执行）：

```bash
ruff check . && ruff format --check . && mypy .
pytest -q
```

### 5.2 前端（TypeScript / React）

| 工具 | 配置 | 强制要求 |
|---|---|---|
| tsc | `frontend/tsconfig.json`（strict + noUnused*） | `npm run build` 内 `tsc` 零错误 |
| eslint | `frontend/eslint.config.js` | lint 零 **error**（warning 可接受） |

验收命令（提交前必须通过，在 `frontend/` 下执行）：

```bash
npm run lint
npm run build   # tsc && vite build
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

### 三槽位策略架构（正式版 / Beta / 波段）

`base/analysis/strategy/router.py` 内三个注册表，`list_strategy_versions()` 汇总给前端控制按钮；`compute_trades(..., version=...)` 取 `"stable"|"beta"|"band"`，未注册即回退正式版：

- **STABLE_STRATEGIES（正式版）**：所有 ETF 的生产算法，给人用；未注册的走 `_run_default` 通用多指标共振。
- **BETA_STRATEGIES（Beta）**：**代码层面手动注册才有**；未注册的 ETF 无 Beta，前端 Beta 按钮自动禁用（`/api/resonance/trades/versions` 驱动）。
- **BAND_STRATEGIES（波段）**：独立于牛熊持有的波段策略槽位，同样手动注册（当前仅 512100）。

**工作流（算法优化内建验收基准）**：

1. 决定调试某 ETF → 写 beta 策略（改现文件，或新建 `<后缀>_beta.py`）→ 在 `BETA_STRATEGIES` 注册一行。
2. 页面切到该 ETF → Beta 按钮自动亮起 → 所有人可对比两版买卖点。
3. **自动比对（每次改 Beta 必跑）**：`python3 scripts/compare_strategy_versions.py <code> [--base YYYY-MM-DD]`——逐笔比对基准日（默认 2024-10-08，正式版 TRADE_START）后的买卖点，确认 Beta 未漏正式版买点且全历史累计收益 ≥ 正式版；退出码 0=通过、1=漏笔、2=Beta 跑输。
4. **验收门槛**：beta 回测必须**优于正式版**才值得发布——连自己都判断不出优于正式版，就没有发布价值。
5. 升级：beta 优于 stable → 把 beta 实现移入 STABLE 槽位、删 BETA 注册（旧正式版可存档 `<后缀>_stable.py` 或丢弃）。
6. 放弃：beta 无优势 → 直接删除注册，不留垃圾。

**当前槽位状态**（以 `router.py` 注册表与各策略文件 docstring 为唯一事实来源，收益数字均摘自代码注释）：

- 沪深300 `510300`：stable=`hs300.py` 牛熊分治（2019 起；恐慌底/强承接底/绝望底 + 牛市四路径 + 顶部确认卖，全历史约 +440%）；beta=`hs300_beta.py`（同规则数据延至 2014，验证槽位不升级）。
- 中证1000 `512100`：stable=`zz.py` 右侧量价记忆（`zz_params.TRADE_START=2019-01-01`，2026-08-16 由 beta 升级）；beta=`zz_beta.py`（延至 2006 验证）；band=`band.py` 波段 v3（2014 起，注册在 `BAND_STRATEGIES`）。
- 科创综指 `589680`：stable=`kc.py`；beta=`kc_beta.py`（高位散户顶/加速赶顶/洗盘回买）。
- 科创50 `588000`：stable=`kc50.py`（复用科创综指买卖日期）；beta=`kc50_beta.py`（独立买卖点先行，不复用科创综指）。
- 其余仅 stable：`div`(515080)、`sh50`(510050)、`sc50`(159780)、`zz500_v2`(510500)、`a500`(159352，复用 510300 买卖点)。

### 波段遗漏审计

策略设计后必须审计每轮持仓期内的"可交易波段"（顶→底回撤 ≥8% 且底→反弹 ≥8%）：若存在遗漏波段，判断是"信号缺失"（如温和顶无 DISTRIBUTE）还是"持有哲学"（趋势持有故意不做波段）。信号缺失才考虑加规则，且必须用真实案例验证不甩飞牛市主升（2024-06-26 +26.1% 类长牛）。

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
   - 统计规律用 `scripts/event_study.py` 做事件分布检验（池化全部事件 + 前向收益 + bootstrap + 参数平台），而非个案 fit。
   - 诚实汇报 trade-off（如横盘顶延迟卖出的 1% 代价 vs 真延迟顶的 4-7% 收益）。
   - "错过行情"是允许的，系统不追求抓住所有轮次。
7. **接入与同步**：`strategy/router.py` 分派接入 → 前端共振图自动生效；策略文件 docstring 与文档保持同步。

## 9. 部署与生产同步（本地开发完毕 → 线上）

生产：`47.93.237.127`（阿里云，root 免密 SSH）。代码 `/root/Resonance`（origin/main）；前端产物 `/var/www/apps/resonance`；后端 systemd `resonance.service`（uvicorn :8001）；DB `/root/.etf-monitor/etf_monitor.db`；部署中心 `/ops/`（`/root/deploy-center`，登录口令不入库）；nginx 配置由独立仓库 `ng_conf` 维护。

**本地开发完毕后，增量同步三步：**

1. **上传代码**：`git push origin main`（本机 GitHub SSH 走本地代理 `127.0.0.1:7897`，需先启动代理，否则 `Proxy connection failed`）。
2. **/ops 执行重新部署**：登录 `http://47.93.237.127/ops/` 对 `resonance` 一键部署（内部 = `git pull origin main` → `cd frontend && VITE_APP_BASE=/resonance npm run build` → rsync `dist` → `systemctl restart resonance`）。前端**必须在服务器带 `VITE_APP_BASE=/resonance` 构建**，禁止直接 scp 本地 dist（base 路径不同）。
3. **数据增量同步至生产 DB**：只同步新增/缺失标的的 `etf_daily` 行（主键 `(date, code)`，用 `INSERT OR REPLACE`，不覆盖其他标的）：
   - 本地显式列名导出 → `scp` 至服务器；
   - 服务器 `systemctl stop resonance`（WAL 模式须先停写）→ 备份 DB → 导入 → `systemctl start resonance`；
   - 验证 DB 行数与 `/api/etf/<code>/history`。
   - 或让服务器自行增量回填：`POST /api/data/jobs`（`backfill_etf_daily` / `backfill_shares` / `refresh_calendar_slots`）。

铁律：DB 永不进 git（`.gitignore` 已排除 `*.db`）；覆盖整库前必须先备份 server DB。
