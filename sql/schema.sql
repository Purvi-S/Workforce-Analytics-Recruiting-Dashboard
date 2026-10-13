-- Core tables. Dates are ISO-8601 text (YYYY-MM-DD); SQLite date functions work on them directly.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS departments (
    dept_id    INTEGER PRIMARY KEY,
    dept_name  TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS recruiters (
    recruiter_id    INTEGER PRIMARY KEY,
    recruiter_name  TEXT NOT NULL,
    team            TEXT NOT NULL,
    start_date      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS employees (
    employee_id          INTEGER PRIMARY KEY,
    dept_id              INTEGER NOT NULL REFERENCES departments (dept_id),
    level                TEXT NOT NULL,
    hire_date            TEXT NOT NULL,
    termination_date     TEXT,
    termination_type     TEXT CHECK (termination_type IN ('Voluntary', 'Involuntary')),
    performance_rating   INTEGER CHECK (performance_rating BETWEEN 1 AND 5),
    engagement_score     REAL CHECK (engagement_score BETWEEN 1 AND 5),
    last_promotion_date  TEXT
);

CREATE TABLE IF NOT EXISTS requisitions (
    req_id            INTEGER PRIMARY KEY,
    dept_id           INTEGER NOT NULL REFERENCES departments (dept_id),
    recruiter_id      INTEGER NOT NULL REFERENCES recruiters (recruiter_id),
    level             TEXT NOT NULL,
    opened_date       TEXT NOT NULL,
    target_fill_days  INTEGER NOT NULL,
    openings          INTEGER NOT NULL DEFAULT 1,
    filled_date       TEXT,
    status            TEXT NOT NULL CHECK (status IN ('Open', 'Filled', 'Cancelled'))
);

CREATE TABLE IF NOT EXISTS applications (
    application_id  INTEGER PRIMARY KEY,
    req_id          INTEGER NOT NULL REFERENCES requisitions (req_id),
    candidate_id    INTEGER NOT NULL,
    source          TEXT NOT NULL,
    applied_date    TEXT NOT NULL,
    screen_date     TEXT,
    interview_date  TEXT,
    offer_date      TEXT,
    hire_date       TEXT,
    furthest_stage  TEXT NOT NULL,
    offer_declined  INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS ix_app_req      ON applications (req_id);
CREATE INDEX IF NOT EXISTS ix_app_source   ON applications (source);
CREATE INDEX IF NOT EXISTS ix_emp_dept     ON employees (dept_id);
CREATE INDEX IF NOT EXISTS ix_req_recruiter ON requisitions (recruiter_id);

-- Run parameters (snapshot date) so every model uses the same "as of" date.
CREATE TABLE IF NOT EXISTS params (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);
