"""Render static previews of the key report visuals for the README (docs/*.png).

    python -m etl.preview_charts
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

SRC = Path("output/powerbi")
OUT = Path("docs")
INK, MUTED, ACCENT, ALERT, GRID = "#1f2933", "#7b8794", "#2f6fdf", "#c0392b", "#e4e7eb"


def _style(ax, title: str, subtitle: str) -> None:
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold", color=INK, pad=22)
    ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=9.5, color=MUTED)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _barh(df, label, value, title, subtitle, fname, highlight=None, fmt="{:.0f}", color=ACCENT):
    df = df.sort_values(value)
    fig, ax = plt.subplots(figsize=(7.5, 3.6), dpi=150)
    colors = [ALERT if highlight and highlight(r) else color for _, r in df.iterrows()]
    bars = ax.barh(df[label], df[value], color=colors, height=0.62)
    for bar, v in zip(bars, df[value], strict=True):
        label = fmt.format(v)
        ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2,
                f" {label}" if v >= 0 else f"{label} ", va="center",
                ha="left" if v >= 0 else "right", fontsize=9, color=INK)
    if (df[value] < 0).any():
        ax.set_xlim(left=df[value].min() * 1.15)
    _style(ax, title, subtitle)
    ax.tick_params(axis="y", colors=INK)
    fig.tight_layout()
    fig.savefig(OUT / fname)
    plt.close(fig)


def main() -> None:
    OUT.mkdir(exist_ok=True)

    tth = pd.read_csv(SRC / "time_to_hire_by_dept.csv")
    _barh(tth, "dept_name", "median_days_to_fill", "Median days to fill by department",
          "Engineering is the outlier; the bottleneck view traces it to the interview stage",
          "time_to_fill.png", highlight=lambda r: r["dept_name"] == "Engineering", fmt="{:.0f} d")

    funnel = pd.read_csv(SRC / "funnel_by_source.csv")
    _barh(funnel, "source", "pct_apply_to_hire", "Applicant-to-hire conversion by source",
          "Referrals convert ~8x better than job boards", "funnel_by_source.png", fmt="{:.1f}%")

    attr = pd.read_csv(SRC / "attrition_ttm.csv")
    _barh(attr, "dept_name", "attrition_pct_ttm", "Trailing-12-month attrition",
          "Customer Support turns over more than a third of its staff each year",
          "attrition.png", highlight=lambda r: r["attrition_pct_ttm"] > 30, fmt="{:.1f}%")

    plan = pd.read_csv(SRC / "workforce_plan.csv")
    _barh(plan, "dept_name", "net_capacity_gap", "Next-quarter capacity gap (expected fills − exits)",
          "Every department is under-hiring against projected attrition", "capacity_gap.png",
          highlight=lambda r: r["net_capacity_gap"] < 0)

    print("wrote", ", ".join(p.name for p in sorted(OUT.glob("*.png"))))


if __name__ == "__main__":
    main()
