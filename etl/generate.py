"""Generate a synthetic HR + recruiting dataset (no real people).

Default size: ~20K employees, ~3K requisitions, ~230K applications (250K+ rows total).
Patterns are built in on purpose so the SQL models have something to find:
  * Engineering's onsite-interview stage is slow (a hiring bottleneck).
  * Referrals convert far better than job boards.
  * Recruiter workload and skill vary.
  * Attrition rises with time-since-promotion and low engagement, and
    Customer Support has the highest turnover.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DEPARTMENTS = {
    # name: (headcount share, base attrition/yr, interview-stage slowdown in days)
    "Engineering": (0.32, 0.12, 18),
    "Sales": (0.18, 0.20, 4),
    "Customer Support": (0.16, 0.32, 2),
    "Marketing": (0.08, 0.15, 5),
    "Finance": (0.07, 0.10, 6),
    "Operations": (0.12, 0.17, 3),
    "People": (0.07, 0.13, 4),
}
SOURCES = {
    # name: (share of applicants, relative pass-through multiplier)
    "Referral": (0.08, 2.6),
    "LinkedIn": (0.34, 1.0),
    "Job Board": (0.30, 0.6),
    "Careers Site": (0.18, 1.1),
    "Agency": (0.06, 1.5),
    "University": (0.04, 0.9),
}
LEVELS = ["L1", "L2", "L3", "L4", "L5", "L6"]
START = pd.Timestamp("2021-01-01")
END = pd.Timestamp("2026-09-30")


def _days(rng, mean, size, shape=2.0):
    return np.maximum(1, rng.gamma(shape, mean / shape, size)).round().astype(int)


def generate(n_employees: int = 20000, n_reqs: int = 3000, n_recruiters: int = 40, seed: int = 11):
    rng = np.random.default_rng(seed)
    dept_names = list(DEPARTMENTS)

    departments = pd.DataFrame({"dept_id": range(1, len(dept_names) + 1), "dept_name": dept_names})
    dept_id = dict(zip(dept_names, departments["dept_id"], strict=True))

    # --- recruiters ---------------------------------------------------------
    recruiters = pd.DataFrame(
        {
            "recruiter_id": range(1, n_recruiters + 1),
            "recruiter_name": [f"Recruiter {i:02d}" for i in range(1, n_recruiters + 1)],
            "team": rng.choice(["Tech", "GTM", "Corporate"], n_recruiters, p=[0.45, 0.35, 0.2]),
            "start_date": START + pd.to_timedelta(rng.integers(0, 1200, n_recruiters), "D"),
        }
    )
    skill = rng.normal(1.0, 0.18, n_recruiters).clip(0.6, 1.5)  # latent: faster + better closes

    # --- employees ----------------------------------------------------------
    shares = np.array([v[0] for v in DEPARTMENTS.values()])
    emp_dept = rng.choice(dept_names, n_employees, p=shares / shares.sum())
    hire = START - pd.Timedelta(days=365 * 4) + pd.to_timedelta(
        rng.integers(0, (END - START).days + 365 * 4, n_employees), "D"
    )
    level_idx = rng.choice(len(LEVELS), n_employees, p=[0.22, 0.28, 0.24, 0.15, 0.08, 0.03])
    engagement = rng.normal(3.7, 0.7, n_employees).clip(1, 5).round(1)
    rating = rng.choice([1, 2, 3, 4, 5], n_employees, p=[0.03, 0.12, 0.5, 0.27, 0.08])
    months_since_promo = rng.integers(0, 60, n_employees)

    base = np.array([DEPARTMENTS[d][1] for d in emp_dept])
    hazard = base * (1 + 0.025 * np.maximum(0, months_since_promo - 18)) * (1 + (3.7 - engagement) * 0.45)
    hazard *= np.where(rating <= 2, 1.6, 1.0)
    tenure_to_exit = rng.exponential(365 / np.clip(hazard, 0.02, 3))
    term = hire + pd.to_timedelta(tenure_to_exit.round(), "D")
    term = pd.Series(term).where(term <= END)

    employees = pd.DataFrame(
        {
            "employee_id": range(100001, 100001 + n_employees),
            "dept_id": [dept_id[d] for d in emp_dept],
            "level": np.array(LEVELS)[level_idx],
            "hire_date": hire,
            "termination_date": term,
            "termination_type": np.where(
                term.notna(), rng.choice(["Voluntary", "Involuntary"], n_employees, p=[0.82, 0.18]), None
            ),
            "performance_rating": rating,
            "engagement_score": engagement,
            "last_promotion_date": hire + pd.to_timedelta(
                np.maximum(0, ((END - hire).days.to_numpy() - months_since_promo * 30)), "D"
            ),
        }
    )
    # Promotion can't happen after termination or before hire.
    employees["last_promotion_date"] = employees["last_promotion_date"].clip(
        lower=employees["hire_date"]
    )
    has_term = employees["termination_date"].notna()
    employees.loc[has_term, "last_promotion_date"] = employees.loc[
        has_term, ["last_promotion_date", "termination_date"]
    ].min(axis=1)

    # --- requisitions -------------------------------------------------------
    req_dept = rng.choice(dept_names, n_reqs, p=shares / shares.sum())
    opened = START + pd.to_timedelta(rng.integers(0, (END - START).days - 30, n_reqs), "D")
    req_recruiter = rng.integers(1, n_recruiters + 1, n_reqs)
    requisitions = pd.DataFrame(
        {
            "req_id": range(5001, 5001 + n_reqs),
            "dept_id": [dept_id[d] for d in req_dept],
            "recruiter_id": req_recruiter,
            "level": rng.choice(LEVELS[:5], n_reqs, p=[0.2, 0.3, 0.27, 0.16, 0.07]),
            "opened_date": opened,
            "target_fill_days": np.where(np.isin(req_dept, ["Engineering"]), 60, 45),
        }
    )

    # --- applications -------------------------------------------------------
    per_req = rng.poisson(75, n_reqs) + 5
    a_req = np.repeat(np.arange(n_reqs), per_req)
    n_apps = len(a_req)
    src_names = list(SOURCES)
    src_p = np.array([v[0] for v in SOURCES.values()])
    a_src = rng.choice(src_names, n_apps, p=src_p / src_p.sum())
    src_mult = np.array([SOURCES[s][1] for s in a_src])
    r_skill = skill[req_recruiter[a_req] - 1]
    a_dept = req_dept[a_req]
    slow = np.array([DEPARTMENTS[d][2] for d in a_dept])

    applied = opened.to_numpy()[a_req] + pd.to_timedelta(_days(rng, 12, n_apps), "D").to_numpy()
    p_screen = np.clip(0.28 * src_mult, 0, 0.95)
    p_interview = np.clip(0.38 * src_mult**0.5 * r_skill, 0, 0.95)
    p_offer = np.clip(0.22 * r_skill, 0, 0.9)
    p_accept = np.clip(0.78 * r_skill**0.5, 0, 0.97)

    screened = rng.random(n_apps) < p_screen
    interviewed = screened & (rng.random(n_apps) < p_interview)
    offered = interviewed & (rng.random(n_apps) < p_offer)
    accepted = offered & (rng.random(n_apps) < p_accept)

    def step(prev, mask, mean):
        out = pd.Series(pd.NaT, index=range(n_apps), dtype="datetime64[ns]")
        delta = pd.to_timedelta(_days(rng, mean, n_apps), "D").to_numpy()
        out[mask] = (pd.Series(prev) + delta)[mask]
        return out

    screen_dt = step(applied, screened, 6 / r_skill)
    interview_dt = step(screen_dt, interviewed, (8 + slow) / r_skill)
    offer_dt = step(interview_dt, offered, 5 + slow * 0.3)
    hire_dt = step(offer_dt, accepted, 14)

    stage = np.select(
        [accepted, offered, interviewed, screened], ["Hired", "Offer", "Interview", "Screen"], "Applied"
    )
    applications = pd.DataFrame(
        {
            "application_id": range(1, n_apps + 1),
            "req_id": requisitions["req_id"].to_numpy()[a_req],
            "candidate_id": rng.integers(1, int(n_apps * 0.85), n_apps),
            "source": a_src,
            "applied_date": applied,
            "screen_date": screen_dt,
            "interview_date": interview_dt,
            "offer_date": offer_dt,
            "hire_date": hire_dt,
            "furthest_stage": stage,
            "offer_declined": offered & ~accepted,
        }
    )
    # Data after the snapshot date can't exist yet.
    for col in ["screen_date", "interview_date", "offer_date", "hire_date"]:
        applications.loc[applications[col] > END, col] = pd.NaT

    # A requisition can have several openings; it counts as filled at its first hire.
    hires = applications.dropna(subset=["hire_date"]).groupby("req_id")["hire_date"]
    requisitions["openings"] = requisitions["req_id"].map(hires.count()).fillna(0).clip(lower=1)
    requisitions["openings"] = requisitions["openings"].astype(int)
    requisitions["filled_date"] = requisitions["req_id"].map(hires.min())
    requisitions["status"] = np.where(requisitions["filled_date"].notna(), "Filled", "Open")
    # Unfilled reqs older than ~6 months are closed out by the business, not left open forever.
    age_days = (END - requisitions["opened_date"]).dt.days
    stale = (requisitions["status"] == "Open") & (age_days > rng.integers(120, 240, n_reqs))
    requisitions.loc[stale, "status"] = "Cancelled"

    return {
        "departments": departments,
        "recruiters": recruiters,
        "employees": employees,
        "requisitions": requisitions,
        "applications": applications,
    }


if __name__ == "__main__":
    tables = generate()
    for name, df in tables.items():
        print(f"{name:13s} {len(df):>8,}")
    print(f"{'total':13s} {sum(len(d) for d in tables.values()):>8,}")
