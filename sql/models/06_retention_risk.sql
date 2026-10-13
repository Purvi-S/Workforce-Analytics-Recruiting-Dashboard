-- Rule-based retention risk score for active employees (0-100).
-- Each factor is weighted from what the attrition data shows drives exits:
-- time since last promotion, low engagement, low rating, and a high-turnover department.
DROP VIEW IF EXISTS vw_retention_risk;
CREATE VIEW vw_retention_risk AS
WITH snapshot AS (
    SELECT value AS as_of FROM params WHERE key = 'snapshot_date'
),
active AS (
    SELECT
        e.*,
        d.dept_name,
        (julianday(s.as_of) - julianday(e.hire_date)) / 30.4            AS tenure_months,
        (julianday(s.as_of) - julianday(e.last_promotion_date)) / 30.4  AS months_since_promo
    FROM employees e
    JOIN departments d USING (dept_id)
    CROSS JOIN snapshot s
    WHERE e.termination_date IS NULL
),
dept_rate AS (
    SELECT dept_name, attrition_pct_ttm FROM vw_attrition_ttm
),
scored AS (
    SELECT
        a.employee_id,
        a.dept_name,
        a.level,
        ROUND(a.tenure_months, 1)       AS tenure_months,
        ROUND(a.months_since_promo, 1)  AS months_since_promo,
        a.engagement_score,
        a.performance_rating,
        MIN(30, MAX(0, a.months_since_promo - 18) * 1.0)                AS promo_points,
        MIN(30, MAX(0, (3.7 - a.engagement_score)) * 20)                AS engagement_points,
        CASE WHEN a.performance_rating <= 2 THEN 15 ELSE 0 END          AS rating_points,
        MIN(15, dr.attrition_pct_ttm * 0.5)                             AS dept_points,
        CASE WHEN a.tenure_months BETWEEN 9 AND 24 THEN 10 ELSE 0 END   AS tenure_points
    FROM active a
    JOIN dept_rate dr USING (dept_name)
)
SELECT
    *,
    ROUND(promo_points + engagement_points + rating_points + dept_points + tenure_points, 1)
        AS risk_score,
    CASE
        WHEN promo_points + engagement_points + rating_points + dept_points + tenure_points >= 45 THEN 'High'
        WHEN promo_points + engagement_points + rating_points + dept_points + tenure_points >= 25 THEN 'Medium'
        ELSE 'Low'
    END AS risk_band
FROM scored;

DROP VIEW IF EXISTS vw_retention_risk_summary;
CREATE VIEW vw_retention_risk_summary AS
SELECT
    dept_name,
    COUNT(*)                                             AS active_employees,
    SUM(risk_band = 'High')                              AS high_risk,
    ROUND(100.0 * SUM(risk_band = 'High') / COUNT(*), 1) AS pct_high_risk,
    ROUND(AVG(risk_score), 1)                            AS avg_risk_score
FROM vw_retention_risk
GROUP BY dept_name
ORDER BY pct_high_risk DESC;
