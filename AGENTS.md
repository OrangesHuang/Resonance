# ETF 国家队监控系统 — Agent 开发规范与量化推演流程

> 本文件是 opencode 在本项目中的行为准则：代码开发规范 + 金融量化算法推演方法论。

## 1. 核心铁律：300 行硬限制

- 任何单个源代码文件（`.py`, `.tsx`, `.ts`）**严禁超过 300 行**。
- 接近 250 行时必须拆分。
- 例外：`package.json`、`tsconfig.json` 等配置文件。

## 2. 后端架构 (Python FastAPI)

- **分层结构**：`fetch/` → `analysis/` → `store/` → `api/`，禁止跨层调用。
  - `fetch/` 只做 HTTP 请求与原始数据解析，无业务逻辑、不碰 store。
  - `analysis/` 纯函数，无 I/O 副作用。
  - `store/` 封装所有 SQLite 操作，参数化查询。
  - `api/` 仅做请求解析和响应格式化。
  - `scheduler/` 编排任务：`data_jobs.py` 任务实现（带进度回调）、`tasks.py` 定时任务、`job_registry.py` 注册（标签/独占/默认参数）、`rebuild.py` 一键重建流水线。
  - `main.py` 仅做 app 组装，不写业务。
- **任务参数规范**：时间范围优先用 `start_date`/`end_date`（`YYYY-MM-DD`），`days` 仅为无日期时的回退；新增任务需在 `job_registry.py` 注册 defaults 并在 `api/data.py` 校验。

## 3. 前端架构 (React + TypeScript)

- 页面组件放 `pages/`，可复用 UI 放 `components/`。
- 数据获取统一通过 `api/client.ts` + React Query hooks，禁止在组件内直接 `fetch()`。
- 图表使用 ECharts，按需引入。
- **ECharts 性能**：数据驱动的 option 必须 `useMemo` 缓存；缩放/拖动类交互不得每帧重建 option（用 `dispatchAction` 同步外部变化，事件回调防抖）。
- **ECharts merge 语义**：条件性标记（`markPoint`/`markLine`/`markArea`）必须**始终定义为对象**、数据为空数组即清除——用 `undefined` 表示"清除"在 merge 模式下会导致旧数据残留（如切换 ETF 后旧买卖点残留）。

## 4. 编码规范

- Python: type hints、snake_case、常量 UPPER_SNAKE_CASE、函数 < 50 行。
- TypeScript: strict mode、函数组件 + hooks、禁止 any（除 ECharts option）。
- 魔法数字必须提取为命名常量（策略参数放策略文件级常量，系统参数放 `config.py`）。
- 网络请求必须设置 timeout，失败优雅降级（返回空，不抛异常）。
- Git commit 用中文 conventional 格式：`feat:` / `fix:` / `docs:` / `perf:` / `revert:`。

## 5. 数据与拉取规范（防远端封禁）

- **新鲜度判断**：拉取前先查库，已覆盖目标交易日则跳过远端（参考 `job_backfill_etf_daily` 的 skip 与"已是最新"提示）。
- **内存 TTL 缓存**：`KLINE_CACHE_TTL_SEC` 内重复调用不触网；失败也冷却（`KLINE_FAIL_COOLDOWN_SEC`），防止失败重试风暴。
- **批量限速**：相邻请求加间隔（`FETCH_SLEEP_SEC`），连续失败暂停（`SHARES_FAIL_PAUSE_SEC`），空结果重试（`SHARES_RETRY`）。
- **upsert 不得用 NULL 覆盖已有值**：新数据缺字段时用 `COALESCE(excluded.x, 原值)`（参考 `daily_repo.upsert_daily`，曾因回填日度清空全部份额）。
- **按标的补齐粒度**：份额等回填只写缺失的 ETF，不影响其他标的（`_missing_share_etfs`）。
- **边拉边写**：逐日任务每拉到一天立即入库（`on_row` 回调），中断不丢已拉数据；重跑自动跳过已完成日期。
- **非交易日不拉取**：回溯跳过周末，目标日期用 `get_last_trading_day`。
- 手动刷新接口限速（`REFRESH_MIN_INTERVAL_SEC`）。

## 6. 量化策略开发规范

- 每只 ETF 独立策略文件：`analysis/strategy_<后缀>.py`，含 `<CODE>_CODE` 常量；在 `api/resonance.py` 的 `/trades` 中按代码特判接入（K线类策略需注入 `_tp`/`_mp` 分位数据）。
- 所有阈值/窗口/冷却期为文件级 UPPER_SNAKE_CASE 常量，附注释说明依据。
- 策略输出结构固定：`{code, trades, metrics, holding}`；`trades` 每项含 `date/action/price/reason`，reason 写明触发路径。
- 文件 docstring 必须写明：核心认知（资产特征）、历史教训（买太早/卖太早/假反弹的实际案例）、算法结构。
- 回测用真实库数据跑全历史（`scripts/backtest.py` 或内联脚本），核对每轮买卖点与收益，并检查"买入后 10 日最大回撤"。

## 7. 金融量化算法推演流程（核心方法论）

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
7. **接入与同步**：`resonance.py` 特判接入 → 前端共振图自动生效；策略文件 docstring 与文档保持同步。

## 8. 运行与验证

```bash
./start.sh                        # 一键启动前后端（自动建 venv/装依赖/镜像探测）
cd frontend && npm run build      # 前端验证: tsc + vite build
python3 -m py_compile <file>      # 后端语法验证
python3 scripts/backtest.py       # 策略回测
```

- 数据回填入口：前端「数据管理」页（日期区间 + 强制重拉开关），优先于脚本。
- 数据库：`~/.etf-monitor/etf_monitor.db`（`ETF_MONITOR_HOME` 可覆盖）。
