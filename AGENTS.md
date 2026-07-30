# ETF 国家队监控系统 — 开发规范

## 1. 核心铁律：300行硬限制

- 任何单个源代码文件（`.py`, `.tsx`, `.ts`）**严禁超过 300 行**。
- 接近 250 行时必须拆分。
- 例外：`package.json`、`tsconfig.json` 等配置文件。

## 2. 后端架构 (Python FastAPI)

- **分层结构**：`fetch/` → `analysis/` → `store/` → `api/`，禁止跨层调用。
- `fetch/` 只做 HTTP 请求与原始数据解析，无业务逻辑。
- `analysis/` 纯函数，无 I/O 副作用。
- `store/` 封装所有 SQLite 操作，参数化查询。
- `api/` 仅做请求解析和响应格式化。
- `scheduler/` 编排定时任务，调用各层组合。
- `main.py` 仅做 app 组装，不写业务。

## 3. 前端架构 (React + TypeScript)

- 页面组件放 `pages/`，可复用 UI 放 `components/`。
- 数据获取统一通过 `api/client.ts` + React Query hooks。
- 禁止在组件内直接 `fetch()`。
- 图表使用 ECharts，按需引入。

## 4. 编码规范

- Python: type hints、snake_case、常量 UPPER_SNAKE_CASE、函数 < 50 行。
- TypeScript: strict mode、函数组件 + hooks、禁止 any（除 ECharts option）。
- 魔法数字必须提取为命名常量。
- 网络请求必须设置 timeout，失败优雅降级。

## 5. 数据规范

- 日期格式：内部 `YYYY-MM-DD`，akshare 接口 `YYYYMMDD`，边界处转换。
- ETF 代码保持字符串（`"510300"`）。
- SQLite 使用 WAL 模式，参数化查询。
- 非交易日/数据缺失不抛异常，返回空或降级。

## 6. 运行方式

```bash
# 后端
cd backend && python3 -m uvicorn main:app --port 8001

# 前端
cd frontend && npm run dev

# 回填历史
python3 scripts/seed_db.py 60
```
