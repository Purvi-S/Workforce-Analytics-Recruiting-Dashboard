-- Time to fill per filled requisition, with SLA status.
-- Feeds: time-to-hire trend, % within SLA, dept comparison.
DROP VIEW IF EXISTS vw_time_to_hire;
CREATE VIEW vw_time_to_hire AS
SELECT
    r.req_id,
    d.dept_name,
    r.level,
    r.recruiter_id,
    r.opened_date,
    r.filled_date,
    strftime('%Y-%m', r.filled_date)                                  AS fill_month,
    CAST(julianday(r.filled_date) - julianday(r.opened_date) AS INT)  AS days_to_fill,
    r.target_fill_days,
    CASE
        WHEN julianday(r.filled_date) - julianday(r.opened_date) <= r.target_fill_days THEN 1
        ELSE 0
    END                                                               AS within_sla
FROM requisitions r
JOIN departments d USING (dept_id)
WHERE r.status = 'Filled';

-- Department summary with median and p90 (SQLite has no PERCENTILE_CONT,
-- so rank within each department and pick the matching row).
DROP VIEW IF EXISTS vw_time_to_hire_by_dept;
CREATE VIEW vw_time_to_hire_by_dept AS
WITH ranked AS (
    SELECT
        dept_name,
        days_to_fill,
        within_sla,
        ROW_NUMBER() OVER (PARTITION BY dept_name ORDER BY days_to_fill) AS rn,
        COUNT(*)     OVER (PARTITION BY dept_name)                       AS n
    FROM vw_time_to_hire
)
SELECT
    dept_name,
    MAX(n)                                                     AS reqs_filled,
    ROUND(AVG(days_to_fill), 1)                                AS avg_days_to_fill,
    MAX(CASE WHEN rn = (n + 1) / 2 THEN days_to_fill END)      AS median_days_to_fill,
    MAX(CASE WHEN rn = CAST(0.9 * n AS INT) THEN days_to_fill END) AS p90_days_to_fill,
    ROUND(100.0 * AVG(within_sla), 1)                          AS pct_within_sla
FROM ranked
GROUP BY dept_name
ORDER BY median_days_to_fill DESC;
