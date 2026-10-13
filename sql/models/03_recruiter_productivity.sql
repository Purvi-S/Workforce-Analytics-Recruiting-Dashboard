-- Recruiter productivity per quarter.
DROP VIEW IF EXISTS vw_recruiter_productivity;
CREATE VIEW vw_recruiter_productivity AS
WITH req_q AS (
    SELECT
        r.recruiter_id,
        strftime('%Y', r.filled_date) || '-Q' ||
            ((CAST(strftime('%m', r.filled_date) AS INT) + 2) / 3)         AS quarter,
        julianday(r.filled_date) - julianday(r.opened_date)                AS days_to_fill
    FROM requisitions r
    WHERE r.status = 'Filled'
),
offers AS (
    SELECT
        r.recruiter_id,
        strftime('%Y', a.offer_date) || '-Q' ||
            ((CAST(strftime('%m', a.offer_date) AS INT) + 2) / 3)          AS quarter,
        COUNT(*)                                                           AS offers_extended,
        SUM(a.hire_date IS NOT NULL)                                       AS offers_accepted
    FROM applications a
    JOIN requisitions r USING (req_id)
    WHERE a.offer_date IS NOT NULL
    GROUP BY 1, 2
)
SELECT
    rc.recruiter_id,
    rc.recruiter_name,
    rc.team,
    q.quarter,
    COUNT(*)                                              AS reqs_filled,
    ROUND(AVG(q.days_to_fill), 1)                         AS avg_days_to_fill,
    COALESCE(o.offers_extended, 0)                        AS offers_extended,
    ROUND(100.0 * o.offers_accepted / NULLIF(o.offers_extended, 0), 1) AS offer_accept_rate
FROM req_q q
JOIN recruiters rc USING (recruiter_id)
LEFT JOIN offers o ON o.recruiter_id = q.recruiter_id AND o.quarter = q.quarter
GROUP BY rc.recruiter_id, q.quarter;

-- All-time leaderboard, ranked within team.
DROP VIEW IF EXISTS vw_recruiter_leaderboard;
CREATE VIEW vw_recruiter_leaderboard AS
WITH totals AS (
    SELECT
        recruiter_id,
        recruiter_name,
        team,
        SUM(reqs_filled)                                       AS reqs_filled,
        ROUND(SUM(avg_days_to_fill * reqs_filled) / SUM(reqs_filled), 1) AS avg_days_to_fill,
        SUM(offers_extended)                                   AS offers_extended
    FROM vw_recruiter_productivity
    GROUP BY recruiter_id
),
open_load AS (
    SELECT recruiter_id, COUNT(*) AS open_reqs
    FROM requisitions WHERE status = 'Open'
    GROUP BY recruiter_id
)
SELECT
    t.*,
    COALESCE(ol.open_reqs, 0)                                          AS open_reqs,
    RANK() OVER (PARTITION BY t.team ORDER BY t.avg_days_to_fill)      AS speed_rank_in_team
FROM totals t
LEFT JOIN open_load ol USING (recruiter_id)
ORDER BY t.team, speed_rank_in_team;
