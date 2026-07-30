# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick start

```bash
./start.sh                           # one-click: creates .venv, installs deps, starts both servers
# Or manually:
cd backend && python3 -m uvicorn main:app --port 8001   # API at :8001
cd frontend && npm run dev                               # UI at :5174
```

Database lives at `~/.etf-monitor/etf_monitor.db` (override with `ETF_MONITOR_HOME` env var).

## Architecture

**Backend** (Python 3.9+, FastAPI, SQLite WAL mode) — strict unidirectional layering:

```
fetch/  →  analysis/  →  store/  →  api/
  ↑                      ↑
scheduler/          main.py (app assembly only)
```

- `fetch/` — HTTP requests and raw-data parsing only (akshare, Tencent market APIs). No business logic.
- `analysis/` — Pure functions, zero I/O. Composite signal synthesis, factor calculation, resonance verdicts, sentiment percentiles, and four trading strategies (`strategy.py`, `strategy_div.py`, `strategy_kc.py`, `strategy_zz.py`).
- `store/` — All SQLite access: `database.py` (connection/schema/migration), plus repos for daily, realtime, sentiment, and calendar tables. Always parameterized queries.
- `api/` — FastAPI routers: request parsing and response formatting only.
- `scheduler/` — APScheduler cron jobs + background job engine (`job_manager.py`). Blocking work dispatched via `asyncio.to_thread`; progress polled through in-memory registry with `threading.Lock`. `rebuild_all` is exclusive.
- `main.py` — App assembly (lifespan, CORS, router registration). ≤50 lines.

**Rebuild data pipeline** (weighted phases for progress): trade calendar → ETF daily seed → shares backfill → sentiment.

**Frontend** (React 18, TypeScript strict, Vite, React Query v5, ECharts, Tailwind):
- `pages/` — Dashboard, Resonance, Sentiment, DataManage, EtfDetail, TradeCalendar.
- `components/` — Reusable charts, signal cards, heatmap, evidence panels.
- `api/client.ts` + `types.ts` — Centralized HTTP client. Components never call `fetch()` directly.
- `hooks/` — React Query wrappers (`useSignals`, `useResonance`, `useSentiment`, `useData`, `useCalendar`).

**CLI** (`cli/resonance.py`) — Reads the SQLite DB directly (no server needed) and outputs resonance conclusions. Used by external agents (e.g., Qoderwork) for IM notifications.

## Key constraints (from AGENTS.md)

- **300-line hard cap** per source file (`.py`, `.tsx`, `.ts`). Split when approaching 250.
- Python functions <50 lines; type hints required; snake_case; constants UPPER_SNAKE_CASE.
- TypeScript strict mode; `any` forbidden except for ECharts options.
- Magic numbers → `backend/config.py`. Every HTTP call must have a timeout and degrade gracefully.
- Dates: `YYYY-MM-DD` internally, `YYYYMMDD` at akshare boundaries.
- Non-trading-day / missing data → return empty or degraded result, never throw.

## Build, lint, test

```bash
cd frontend && npm run build    # tsc + vite build (no separate lint/test scripts)
```

There are no existing test suites or linter configurations in this project.

## Data flow for a new feature

1. Add fetch logic in `fetch/` (if new data source needed).
2. Add pure analysis in `analysis/`.
3. Add storage in `store/` (new repo or extend existing).
4. Expose via `api/` router.
5. Wire scheduling in `scheduler/` if periodic.
6. Add constants to `config.py`.
7. Frontend: type in `api/types.ts`, hook in `hooks/`, page/component in `pages/` or `components/`.
