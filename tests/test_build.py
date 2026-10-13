import sqlite3

import pandas as pd
import pytest

from etl.build import build_models, load
from etl.generate import END, generate
from etl.validate import DataQualityError, assert_clean, run_checks


@pytest.fixture(scope="module")
def conn():
    tables = generate(n_employees=3000, n_reqs=500, n_recruiters=12, seed=5)
    db = sqlite3.connect(":memory:")
    load(db, tables, END.strftime("%Y-%m-%d"))
    build_models(db)
    yield db
    db.close()


def q(conn, sql):
    return pd.read_sql_query(sql, conn)


# --- data quality -----------------------------------------------------------------

def test_generated_data_passes_blocking_checks(conn):
    assert_clean(run_checks(conn))


def test_checks_catch_bad_dates(conn):
    conn.execute("SAVEPOINT bad")
    conn.execute("UPDATE applications SET offer_date = '1999-01-01' "
                 "WHERE application_id = (SELECT MIN(application_id) FROM applications "
                 "WHERE offer_date IS NOT NULL)")
    with pytest.raises(DataQualityError, match="stages out of order"):
        assert_clean(run_checks(conn))
    conn.execute("ROLLBACK TO bad")


def test_schema_blocks_orphans(conn):
    # Foreign keys reject orphans at write time; the orphan checks are a second line
    # of defence for loads that bypass the constraint (e.g. bulk imports with FKs off).
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        conn.execute("UPDATE applications SET req_id = 999999 WHERE application_id = 1")


def test_orphan_check_detects_fk_bypass():
    db = sqlite3.connect(":memory:")
    tables = generate(n_employees=200, n_reqs=20, n_recruiters=3, seed=9)
    load(db, tables, END.strftime("%Y-%m-%d"))
    db.execute("PRAGMA foreign_keys = OFF")
    db.execute("UPDATE applications SET req_id = 999999 WHERE application_id = 1")
    results = {r["check"]: r for r in run_checks(db)}
    assert results["applications: orphan req_id"]["failed_rows"] == 1


# --- models -------------------------------------------------------------------------

def test_funnel_is_monotonic(conn):
    f = q(conn, "SELECT * FROM vw_funnel_by_source")
    assert (f["applied"] >= f["screened"]).all()
    assert (f["screened"] >= f["interviewed"]).all()
    assert (f["interviewed"] >= f["offered"]).all()
    assert (f["offered"] >= f["hired"]).all()


def test_referrals_convert_best(conn):
    f = q(conn, "SELECT source FROM vw_funnel_by_source ORDER BY pct_apply_to_hire DESC LIMIT 1")
    assert f["source"][0] == "Referral"


def test_engineering_bottleneck_is_interview_stage(conn):
    b = q(conn, "SELECT stage FROM vw_stage_dwell WHERE dept_name = 'Engineering' AND is_bottleneck = 1")
    assert list(b["stage"]) == ["Screen → Interview"]


def test_median_between_min_and_p90(conn):
    t = q(conn, "SELECT * FROM vw_time_to_hire_by_dept")
    assert (t["median_days_to_fill"] <= t["p90_days_to_fill"]).all()
    assert t["pct_within_sla"].between(0, 100).all()


def test_attrition_headcount_reconciles(conn):
    # Headcount at the start of the latest month equals active employees hired before it.
    latest = q(conn, "SELECT MAX(month_start) AS m FROM vw_attrition_monthly")["m"][0]
    from_view = q(conn, f"SELECT SUM(headcount_start) AS n FROM vw_attrition_monthly "
                        f"WHERE month_start = '{latest}'")["n"][0]
    direct = q(conn, f"SELECT COUNT(*) AS n FROM employees WHERE hire_date <= '{latest}' "
                     f"AND (termination_date IS NULL OR termination_date >= '{latest}')")["n"][0]
    assert from_view == direct


def test_retention_risk_scores_active_only(conn):
    r = q(conn, "SELECT * FROM vw_retention_risk")
    active = q(conn, "SELECT COUNT(*) AS n FROM employees WHERE termination_date IS NULL")["n"][0]
    assert len(r) == active
    assert r["risk_score"].between(0, 100).all()
    assert set(r["risk_band"]) <= {"Low", "Medium", "High"}


def test_workforce_plan_covers_every_department(conn):
    p = q(conn, "SELECT * FROM vw_workforce_plan")
    assert len(p) == q(conn, "SELECT COUNT(*) AS n FROM departments")["n"][0]
    assert (p["expected_exits_next_q"] >= 0).all()
