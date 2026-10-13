-- Workforce planning: is hiring keeping up with expected exits next quarter?
-- expected_exits_next_q = active headcount * TTM attrition / 4
-- capacity_next_q       = open reqs that historical fill time says will close within 90 days
DROP VIEW IF EXISTS vw_workforce_plan;
CREATE VIEW vw_workforce_plan AS
WITH snapshot AS (
    SELECT value AS as_of FROM params WHERE key = 'snapshot_date'
),
headcount AS (
    SELECT d.dept_name, COUNT(*) AS active_headcount
    FROM employees e JOIN departments d USING (dept_id)
    WHERE e.termination_date IS NULL
    GROUP BY d.dept_name
),
open_reqs AS (
    SELECT d.dept_name,
           COUNT(*) AS open_reqs,
           AVG(julianday(s.as_of) - julianday(r.opened_date)) AS avg_open_age_days
    FROM requisitions r
    JOIN departments d USING (dept_id)
    CROSS JOIN snapshot s
    WHERE r.status = 'Open'
    GROUP BY d.dept_name
),
fill_rate AS (
    SELECT dept_name, AVG(days_to_fill <= 90) AS p_fill_90d FROM vw_time_to_hire GROUP BY dept_name
)
SELECT
    h.dept_name,
    h.active_headcount,
    a.attrition_pct_ttm,
    ROUND(h.active_headcount * a.attrition_pct_ttm / 100.0 / 4, 0)       AS expected_exits_next_q,
    COALESCE(o.open_reqs, 0)                                              AS open_reqs,
    ROUND(o.avg_open_age_days, 0)                                         AS avg_open_req_age_days,
    ROUND(COALESCE(o.open_reqs, 0) * f.p_fill_90d, 0)                     AS expected_fills_next_q,
    ROUND(COALESCE(o.open_reqs, 0) * f.p_fill_90d
          - h.active_headcount * a.attrition_pct_ttm / 100.0 / 4, 0)      AS net_capacity_gap
FROM headcount h
JOIN vw_attrition_ttm a USING (dept_name)
LEFT JOIN open_reqs o USING (dept_name)
LEFT JOIN fill_rate f USING (dept_name)
ORDER BY net_capacity_gap;
