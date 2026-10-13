-- Candidate funnel by source: how many reach each stage and stage-to-stage conversion.
DROP VIEW IF EXISTS vw_funnel_by_source;
CREATE VIEW vw_funnel_by_source AS
WITH counts AS (
    SELECT
        source,
        COUNT(*)                                   AS applied,
        SUM(screen_date    IS NOT NULL)            AS screened,
        SUM(interview_date IS NOT NULL)            AS interviewed,
        SUM(offer_date     IS NOT NULL)            AS offered,
        SUM(hire_date      IS NOT NULL)            AS hired
    FROM applications
    GROUP BY source
)
SELECT
    source,
    applied,
    screened,
    interviewed,
    offered,
    hired,
    ROUND(100.0 * screened    / applied, 2)              AS pct_apply_to_screen,
    ROUND(100.0 * interviewed / NULLIF(screened, 0), 2)  AS pct_screen_to_interview,
    ROUND(100.0 * offered     / NULLIF(interviewed, 0), 2) AS pct_interview_to_offer,
    ROUND(100.0 * hired       / NULLIF(offered, 0), 2)   AS pct_offer_accept,
    ROUND(100.0 * hired       / applied, 3)              AS pct_apply_to_hire,
    ROUND(1.0 * applied / NULLIF(hired, 0), 1)           AS applicants_per_hire
FROM counts
ORDER BY pct_apply_to_hire DESC;
