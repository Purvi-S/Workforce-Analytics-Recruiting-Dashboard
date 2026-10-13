-- Where do candidates wait? Average dwell time per funnel stage, by department.
-- The slowest stage per department is flagged as its bottleneck.
DROP VIEW IF EXISTS vw_stage_dwell;
CREATE VIEW vw_stage_dwell AS
WITH dwell AS (
    SELECT
        d.dept_name,
        AVG(julianday(a.screen_date)    - julianday(a.applied_date))   AS apply_to_screen,
        AVG(julianday(a.interview_date) - julianday(a.screen_date))    AS screen_to_interview,
        AVG(julianday(a.offer_date)     - julianday(a.interview_date)) AS interview_to_offer,
        AVG(julianday(a.hire_date)      - julianday(a.offer_date))     AS offer_to_start
    FROM applications a
    JOIN requisitions r USING (req_id)
    JOIN departments d ON d.dept_id = r.dept_id
    GROUP BY d.dept_name
),
long_form AS (
    SELECT dept_name, 'Apply → Screen'     AS stage, 1 AS stage_order, apply_to_screen     AS avg_days FROM dwell
    UNION ALL
    SELECT dept_name, 'Screen → Interview', 2, screen_to_interview FROM dwell
    UNION ALL
    SELECT dept_name, 'Interview → Offer',  3, interview_to_offer  FROM dwell
    UNION ALL
    SELECT dept_name, 'Offer → Start',      4, offer_to_start      FROM dwell
)
SELECT
    dept_name,
    stage,
    stage_order,
    ROUND(avg_days, 1) AS avg_days,
    CASE
        WHEN stage_order < 4
         AND avg_days = MAX(CASE WHEN stage_order < 4 THEN avg_days END)
                        OVER (PARTITION BY dept_name)
        THEN 1 ELSE 0
    END AS is_bottleneck  -- offer→start is notice period, not something recruiting controls
FROM long_form
ORDER BY dept_name, stage_order;
