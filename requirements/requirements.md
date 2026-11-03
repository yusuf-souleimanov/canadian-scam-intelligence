# CAFC Fraud KPI Scorecard: Requirements

## Purpose

A one-page scorecard showing how much Canadians report losing to fraud, who loses money, and which
scams to prioritise. It is built in Tableau Public from the CAFC open dataset.

## Audience

A bank fraud-strategy team deciding which scams to prioritise.

## Business requirements

1. **BR1:** See the size of reported fraud losses in Canada.
2. **BR2:** See how many people lose money, and what a typical loss looks like.
3. **BR3:** Identify the scam type causing the most losses, so controls can target it.
4. **BR4:** See how much of the loss falls on victims aged 60+, to judge whether seniors need a specific counter-approach.

## Scope

- **Source:** `data/raw/cafc.csv`, the CAFC Fraud Reporting System open dataset (open.canada.ca), 350,361 reports.
- **Period:** January 2, 2021 to September 29, 2025.
- **Population:** reports where Country = Canada (266,553 rows).
- **Out of scope:** fraud never reported to the CAFC, real-time data, and individual victim details.

## KPIs

Full definitions, source columns and transformation rules are in
[kpi_source_to_target_mapping.xlsx](kpi_source_to_target_mapping.xlsx). The baseline values below were
computed in Python from the validated data and are the numbers the Tableau scorecard must match.

| # | KPI | Meets | Target field | Baseline (full period) | Must be shown with |
|---|---|---|---|---|---|
| 1 | Total reported losses | BR1 | `total_loss` | $2,083,045,679.94 | "Lower bound": up to $473,017,653.07 more in Not Specified country rows |
| 2 | Victims with losses | BR2 | `victims_with_loss` | 58,494 | |
| 3 | Median loss per victim | BR2 | `median_loss` | $2,500.00 | |
| 4 | Top scam type by loss | BR3 | `top_scam_type` | Investment / crypto, $1,072,820,884.84 (53.7% of mapped losses) | Note that $84,131,279.19 in unmapped categories is excluded |
| 5 | % of losses from victims 60+ | BR4 | `senior_loss_share` | 45.6% of losses with a known age | `unknown_age_loss_share`: 23.7% of losses have no known age |

## Data quality rules

Each rule is checked by `validation/validate_cafc.py`. Details are in `validation/validation_log.md`.

- Row count and loss total must reconcile between the raw file and the cleaned data, to the cent.
- No duplicate report IDs, no unreadable or negative losses, and no dates outside the expected period.
- Placeholder values (Not Specified, Not Available, Unknown and others) are treated as unknown, never as real categories.
- Any KPI affected by unknowns shows the unknown share next to it.

## Refresh

Refresh on each new CAFC data release:

1. Replace `data/raw/cafc.csv` with the new file.
2. Rebuild the cleaned data (`load(rebuild=True)` in `intel/trends.py`).
3. Run `validation/validate_cafc.py` and confirm 0 FAIL.
4. Refresh the Tableau extract.
5. Check that the scorecard values match the Python values.

## Limitations

- Only a small share of fraud is reported to the CAFC, so the figures show direction and mix, not true totals.
- Total losses are a lower bound, because Not Specified country rows are excluded.
- 29.9% of reports have no victim age, so the 60+ share covers known ages only.
