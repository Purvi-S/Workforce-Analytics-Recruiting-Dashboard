"""Data-quality checks run against the loaded database before any model is built.

Each check is a SQL query that returns the number of offending rows. A check with
severity "error" blocks the build; "warn" is reported but doesn't block.
The idea: dashboards are only trusted if the numbers underneath are checked
every run, and the check results are visible to the people reading them.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Check:
    name: str
    sql: str
    severity: str = "error"


CHECKS = [
    # --- uniqueness / referential integrity ---
    Check("employees: duplicate employee_id",
          "SELECT COUNT(*) - COUNT(DISTINCT employee_id) FROM employees"),
    Check("applications: orphan req_id",
          "SELECT COUNT(*) FROM applications a LEFT JOIN requisitions r USING (req_id) "
          "WHERE r.req_id IS NULL"),
    Check("requisitions: orphan recruiter_id",
          "SELECT COUNT(*) FROM requisitions r LEFT JOIN recruiters c USING (recruiter_id) "
          "WHERE c.recruiter_id IS NULL"),
    # --- date logic ---
    Check("employees: termination before hire",
          "SELECT COUNT(*) FROM employees WHERE termination_date < hire_date"),
    Check("employees: promotion outside employment",
          "SELECT COUNT(*) FROM employees WHERE last_promotion_date < hire_date "
          "OR last_promotion_date > COALESCE(termination_date, '9999-12-31')"),
    Check("requisitions: filled before opened",
          "SELECT COUNT(*) FROM requisitions WHERE filled_date < opened_date"),
    Check("requisitions: filled status without fill date",
          "SELECT COUNT(*) FROM requisitions WHERE (status = 'Filled') != (filled_date IS NOT NULL)"),
    Check("applications: stages out of order",
          "SELECT COUNT(*) FROM applications WHERE screen_date < applied_date "
          "OR interview_date < screen_date OR offer_date < interview_date OR hire_date < offer_date"),
    Check("applications: stage skipped",
          "SELECT COUNT(*) FROM applications WHERE (interview_date IS NOT NULL AND screen_date IS NULL) "
          "OR (offer_date IS NOT NULL AND interview_date IS NULL) "
          "OR (hire_date IS NOT NULL AND offer_date IS NULL)"),
    Check("any table: dates after snapshot",
          "SELECT (SELECT COUNT(*) FROM employees WHERE hire_date > (SELECT value FROM params "
          "WHERE key='snapshot_date')) + (SELECT COUNT(*) FROM applications WHERE hire_date > "
          "(SELECT value FROM params WHERE key='snapshot_date'))"),
    # --- completeness / plausibility (warn only) ---
    Check("requisitions: open longer than 365 days",
          "SELECT COUNT(*) FROM requisitions WHERE status = 'Open' AND julianday((SELECT value "
          "FROM params WHERE key='snapshot_date')) - julianday(opened_date) > 365", "warn"),
    Check("employees: missing engagement score",
          "SELECT COUNT(*) FROM employees WHERE engagement_score IS NULL", "warn"),
]


def run_checks(conn: sqlite3.Connection) -> list[dict]:
    results = []
    for check in CHECKS:
        failures = conn.execute(check.sql).fetchone()[0] or 0
        results.append(
            {
                "check": check.name,
                "severity": check.severity,
                "failed_rows": int(failures),
                "status": "pass" if failures == 0 else ("fail" if check.severity == "error" else "warn"),
            }
        )
    return results


class DataQualityError(RuntimeError):
    pass


def assert_clean(results: list[dict]) -> None:
    failed = [r for r in results if r["status"] == "fail"]
    if failed:
        lines = "\n".join(f"  - {r['check']}: {r['failed_rows']} rows" for r in failed)
        raise DataQualityError(f"{len(failed)} blocking data-quality check(s) failed:\n{lines}")
