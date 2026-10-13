"""End-to-end build: generate -> load -> validate -> build SQL models -> export for Power BI.

    python -m etl.build                       # synthetic data, default size
    python -m etl.build --db output/hr.db --export output/powerbi

Exports one CSV per reporting view plus dq_results.csv, which the Power BI
report shows on a "Data health" page so viewers can see the checks passed.
"""

from __future__ import annotations

import argparse
import sqlite3
import time
from pathlib import Path

import pandas as pd

from etl.generate import END, generate
from etl.validate import assert_clean, run_checks

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"

EXPORT_VIEWS = [
    "vw_time_to_hire",
    "vw_time_to_hire_by_dept",
    "vw_funnel_by_source",
    "vw_recruiter_productivity",
    "vw_recruiter_leaderboard",
    "vw_stage_dwell",
    "vw_attrition_monthly",
    "vw_attrition_ttm",
    "vw_retention_risk",
    "vw_retention_risk_summary",
    "vw_workforce_plan",
]


def _to_sql_ready(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime("%Y-%m-%d")
        elif df[col].dtype == bool:
            df[col] = df[col].astype(int)
    return df.astype(object).where(df.notna(), None)


def load(conn: sqlite3.Connection, tables: dict[str, pd.DataFrame], snapshot: str) -> None:
    conn.executescript((SQL_DIR / "schema.sql").read_text())
    order = ["departments", "recruiters", "employees", "requisitions", "applications"]
    for name in order:
        df = _to_sql_ready(tables[name])
        cols = ", ".join(df.columns)
        marks = ", ".join("?" for _ in df.columns)
        conn.executemany(f"INSERT INTO {name} ({cols}) VALUES ({marks})", df.itertuples(index=False))
    conn.executemany(
        "INSERT OR REPLACE INTO params VALUES (?, ?)",
        [("snapshot_date", snapshot), ("snapshot_month", snapshot[:8] + "01")],
    )
    conn.commit()


def build_models(conn: sqlite3.Connection) -> None:
    for path in sorted((SQL_DIR / "models").glob("*.sql")):
        conn.executescript(path.read_text())


def export(conn: sqlite3.Connection, out: Path, dq: list[dict]) -> dict[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    counts = {}
    for view in EXPORT_VIEWS:
        df = pd.read_sql_query(f"SELECT * FROM {view}", conn)
        df.to_csv(out / f"{view.removeprefix('vw_')}.csv", index=False)
        counts[view] = len(df)
    pd.DataFrame(dq).to_csv(out / "dq_results.csv", index=False)
    return counts


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="output/hr.db")
    parser.add_argument("--export", default="output/powerbi")
    parser.add_argument("--employees", type=int, default=20000)
    parser.add_argument("--reqs", type=int, default=3000)
    args = parser.parse_args(argv)

    t0 = time.time()
    db = Path(args.db)
    db.parent.mkdir(parents=True, exist_ok=True)
    db.unlink(missing_ok=True)

    tables = generate(n_employees=args.employees, n_reqs=args.reqs)
    total_rows = sum(len(t) for t in tables.values())

    with sqlite3.connect(db) as conn:
        load(conn, tables, END.strftime("%Y-%m-%d"))
        dq = run_checks(conn)
        for r in dq:
            print(f"  [{r['status']:4s}] {r['check']} ({r['failed_rows']})")
        assert_clean(dq)
        build_models(conn)
        counts = export(conn, Path(args.export), dq)

    print(f"\nloaded {total_rows:,} rows, built {len(counts)} views in {time.time() - t0:.1f}s")
    for view, n in counts.items():
        print(f"  {view:28s} {n:>7,} rows")


if __name__ == "__main__":
    main()
