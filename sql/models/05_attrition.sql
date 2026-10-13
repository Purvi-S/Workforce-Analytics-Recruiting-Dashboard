-- Monthly headcount and attrition by department.
-- Uses a recursive month spine so months with zero exits still appear.
DROP VIEW IF EXISTS vw_attrition_monthly;
CREATE VIEW vw_attrition_monthly AS
WITH RECURSIVE months(month_start) AS (
    SELECT '2021-01-01'
    UNION ALL
    SELECT date(month_start, '+1 month') FROM months
    WHERE month_start < (SELECT value FROM params WHERE key = 'snapshot_month')
),
grid AS (
    SELECT m.month_start, date(m.month_start, '+1 month', '-1 day') AS month_end, d.dept_id, d.dept_name
    FROM months m CROSS JOIN departments d
)
SELECT
    g.month_start,
    g.dept_name,
    SUM(e.hire_date <= g.month_start
        AND (e.termination_date IS NULL OR e.termination_date >= g.month_start)) AS headcount_start,
    SUM(e.termination_date BETWEEN g.month_start AND g.month_end)                AS exits,
    SUM(e.termination_date BETWEEN g.month_start AND g.month_end
        AND e.termination_type = 'Voluntary')                                    AS voluntary_exits,
    ROUND(100.0 * SUM(e.termination_date BETWEEN g.month_start AND g.month_end)
          / NULLIF(SUM(e.hire_date <= g.month_start
                   AND (e.termination_date IS NULL OR e.termination_date >= g.month_start)), 0), 2)
                                                                                 AS monthly_attrition_pct
FROM grid g
LEFT JOIN employees e ON e.dept_id = g.dept_id
GROUP BY g.month_start, g.dept_name;

-- Trailing-12-month attrition per department (annualized turnover).
DROP VIEW IF EXISTS vw_attrition_ttm;
CREATE VIEW vw_attrition_ttm AS
SELECT
    dept_name,
    SUM(exits)                                         AS exits_ttm,
    SUM(voluntary_exits)                               AS voluntary_exits_ttm,
    ROUND(AVG(headcount_start), 0)                     AS avg_headcount,
    ROUND(100.0 * SUM(exits) / AVG(headcount_start), 1) AS attrition_pct_ttm
FROM vw_attrition_monthly
WHERE month_start > date((SELECT value FROM params WHERE key = 'snapshot_month'), '-12 months')
GROUP BY dept_name
ORDER BY attrition_pct_ttm DESC;
