# Power BI report

The `.pbix` isn't committed: it's binary and wouldn't diff. These steps rebuild it from the exported CSVs in a few minutes.

1. Run `python -m etl.build`. This writes CSVs to `output/powerbi/`.
2. Power BI Desktop → **Get Data → Text/CSV** → import every file in `output/powerbi/`.
3. Add a Date table: **Modeling → New table** → `Date = CALENDARAUTO()`, then mark it as a date table.
4. Create the relationships listed at the top of [`measures.dax`](measures.dax).
5. Create a `_Measures` table and paste in the measures.

## Pages

| Page | Visuals | Key measures |
|---|---|---|
| **Recruiting overview** | KPI cards, monthly time-to-fill line, dept bar with SLA % | Median Days to Fill, % Within SLA, Days to Fill vs Prior Year |
| **Funnel** | Funnel visual by stage, source matrix with conditional formatting | Apply-to-Hire %, Applicants per Hire, Offer Accept % |
| **Bottlenecks** | Stage-dwell heatmap (dept × stage), bottleneck card | Bottleneck Stage |
| **Recruiters** | Leaderboard table, scatter (reqs filled vs avg days), quarter slicer | Reqs Filled, Avg Days to Fill |
| **Retention** | Attrition trend by dept, risk-band donut, at-risk employee table | Attrition % (TTM), % High Risk, Voluntary Share % |
| **Workforce plan** | Expected exits vs fills by dept, capacity-gap bars | Capacity Gap, Capacity Gap Color |
| **Data health** | Check results table, status card | DQ Status |

The **Data health** page is deliberate. People trust a dashboard when they can see that the numbers under it were checked on this refresh.
