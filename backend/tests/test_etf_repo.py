"""动态 ETF 清单(etfs 表)与单标的回填的单测。

临时库: monkeypatch base.store.database.DB_PATH(该模块的 get_connection
在调用时读取模块级 DB_PATH, 因此改它即可重定向整库)。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from base.analysis.etf_naming import derive_idx_name
from base.scheduler.job_manager import JobManager
from base.store import database, etf_repo


@pytest.fixture()
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "t.db")
    database.init_db()
    return tmp_path


def _insert_daily(code: str, date: str, shares: float | None = None) -> None:
    conn = database.get_connection()
    try:
        conn.execute(
            "INSERT INTO etf_daily (date, code, name, close_price, shares_yi, composite_prob) VALUES (?,?,?,?,?,?)",
            (date, code, "X", 1.0, shares, 50.0),
        )
        conn.commit()
    finally:
        conn.close()


def _insert_realtime(code: str, ts: str) -> None:
    conn = database.get_connection()
    try:
        conn.execute("INSERT INTO etf_realtime (timestamp, code, price) VALUES (?,?,?)", (ts, code, 1.0))
        conn.commit()
    finally:
        conn.close()


def test_seed_from_config_idempotent(temp_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(etf_repo, "ETFS", {"510300": {"name": "A", "idx": "沪深300", "market": "sh"}})
    assert etf_repo.seed_from_config() == 1
    assert etf_repo.seed_from_config() == 0  # 二次播种不重复插入
    assert etf_repo.get("510300") is not None


def test_seed_does_not_overwrite_existing(temp_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    etf_repo.insert_etf("510300", "手工改名", "沪深300", "sh")
    monkeypatch.setattr(etf_repo, "ETFS", {"510300": {"name": "配置名", "idx": "沪深300", "market": "sh"}})
    etf_repo.seed_from_config()
    row = etf_repo.get("510300")
    assert row is not None and row["name"] == "手工改名"  # INSERT OR IGNORE 不覆盖


def test_load_into_config_in_place(temp_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mirror: dict = {"999999": {"name": "旧", "idx": "旧", "market": "sh"}}
    monkeypatch.setattr(etf_repo, "ETFS", mirror)
    etf_repo.insert_etf("159915", "创业板ETF", "创业板", "sz")
    n = etf_repo.load_into_config()
    assert n == 1
    assert etf_repo.ETFS is mirror  # 原地更新, 绝不重新绑定
    assert list(mirror) == ["159915"]


def test_purge_only_target_code(temp_db: Path) -> None:
    _insert_daily("159915", "2026-09-30", shares=10.0)
    _insert_daily("159915", "2026-09-29")
    _insert_daily("510300", "2026-09-30", shares=20.0)
    _insert_realtime("159915", "2026-09-30 10:00:00")
    _insert_realtime("510300", "2026-09-30 10:00:00")
    res = etf_repo.purge_code_data("159915")
    assert res == {"daily_rows": 2, "realtime_rows": 1}
    conn = database.get_connection()
    try:
        left = conn.execute("SELECT COUNT(*) FROM etf_daily WHERE code='510300'").fetchone()[0]
        rt = conn.execute("SELECT COUNT(*) FROM etf_realtime WHERE code='159915'").fetchone()[0]
    finally:
        conn.close()
    assert left == 1 and rt == 0


def test_coverage_shape(temp_db: Path) -> None:
    _insert_daily("159915", "2026-09-28")
    _insert_daily("159915", "2026-09-30", shares=10.0)
    _insert_realtime("159915", "2026-09-30 10:00:00")
    _insert_realtime("159915", "2026-09-30 10:01:00")
    cov = etf_repo.etf_coverage()["159915"]
    assert cov["first_date"] == "2026-09-28"
    assert cov["last_date"] == "2026-09-30"
    assert cov["daily_rows"] == 2
    assert cov["shares_last_date"] == "2026-09-30"
    assert cov["realtime_rows"] == 2
    assert cov["realtime_last"] == "2026-09-30 10:01:00"


def test_derive_idx_name() -> None:
    # 东财式(公司前缀)
    assert derive_idx_name("嘉实上证科创板芯片ETF") == "上证科创板芯片"
    assert derive_idx_name("华泰柏瑞沪深300ETF") == "沪深300"
    assert derive_idx_name("国泰中证全指通信设备ETF") == "中证全指通信设备"
    assert derive_idx_name("易方达中证科创创业50ETF") == "中证科创创业50"
    # 腾讯式(公司后缀)
    assert derive_idx_name("有色金属ETF南方") == "有色金属"
    assert derive_idx_name("创业板ETF易方达") == "创业板"
    assert derive_idx_name("沪深300ETF华泰柏瑞") == "沪深300"
    assert derive_idx_name("") == ""


def test_job_manager_active_codes() -> None:
    jm = JobManager()
    job_id = jm.submit("backfill_etf", {"code": "159915"})
    assert jm.active_codes() == {"159915"}
    assert jm.is_any_active({"backfill_etf_daily"}) is False
    assert jm.is_any_active({"backfill_etf"}) is True
    jm.mark_running(job_id)
    jm.finish(job_id, None, None)
    assert jm.active_codes() == set()
    assert jm.is_any_active({"backfill_etf"}) is False


def test_validate_params_code_rules() -> None:
    from api.data import _validate_params

    assert _validate_params({"code": ""}) is not None
    assert _validate_params({"code": "15991"}) is not None
    assert _validate_params({"code": "999999"}) is not None  # 不在册
    assert _validate_params({"code": "510300"}) is None


def test_backfill_etf_skips_shares_for_lof(monkeypatch: pytest.MonkeyPatch) -> None:
    """LOF 无历史份额(交易所仅最新快照): 跳过份额阶段而不是逐日空转重试。

    回归防护: 501018(南方原油 LOF) 曾因此连续失败/暂停 60s, 481 天需数小时。
    """
    import base.scheduler.etf_backfill_job as job

    monkeypatch.setattr(job, "share_data_source", lambda code, date: "lof")
    monkeypatch.setattr(job, "fetch_index_kline", lambda **kwargs: [{"date": "2026-09-30"}] * 30)
    monkeypatch.setattr(job, "_seed_one_etf", lambda *a, **k: (5, 1))
    monkeypatch.setattr(job, "get_by_code", lambda code: [{"date": "2026-09-30"}, {"date": "2024-10-14"}])
    monkeypatch.setattr(job, "job_recalc_composite", lambda *a, **k: {"updated": 5})
    monkeypatch.setattr(job, "job_refresh_calendar_slots", lambda *a, **k: None)
    called = {"shares": False}

    def fake_shares(*args, **kwargs):
        called["shares"] = True
        return {"written": 0}

    monkeypatch.setattr(job, "job_backfill_shares", fake_shares)

    res = job.job_backfill_etf(lambda *a: None, code="501018", days=60)
    assert res["shares_source"] == "lof"
    assert res["shares_written"] == 0
    assert called["shares"] is False
