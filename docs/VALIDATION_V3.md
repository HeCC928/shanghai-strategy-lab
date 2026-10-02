# English showcase: verification record

Updated 18 September 2026. This record concerns the V3 English React/FastAPI application. Earlier Streamlit checklists are historical.

## Acceptance and numerical evidence

The user accepted Sharpe **1.48**, described as **approximately 1.5**, and maximum drawdown **19.3%** against a **25%** limit. The default case is fixed explicitly in `configs/showcase.json`; it is not whichever experiment ran most recently. No further parameter search was used to force it above 1.5.

`scripts/verify_showcase.py` independently recomputed net return, Sharpe and full-period drawdown from all 242 daily returns for each of the six featured/comparison cases. Differences from stored metrics were below 1e-10. It checked one initial capital row, date uniqueness/order, twelve complete replay months, all information cutoffs, 45 saved search attempts, 168 rolling calibration/validation trials and 84,300 source rows across 100 stocks. Every stock spans 2023-01-03–2026-06-30. Results, artifact hashes and standalone reports are in `storage/showcase/`.

The recorded rolling comparison has Sharpe 1.30424 and drawdown 13.6829%. Its monthly return/DD numbers come from the continuous final ledger, not a concatenation of freshly funded monthly portfolios. Same-pool benchmarks remain separately identified.

## Automated checks

The full suite contains 41 tests. `storage/verification-tests.xml` records the latest run. Coverage includes:

- Rolling calendar boundaries and next-session execution; one continuous capital ledger; identical schedules versus fixed rules.
- Mutation of future prices leaves earlier window selections and earlier NAV unchanged; market-risk calculations use only available history.
- Cash fallback and reductions; fractional and strict-share accounting, costs, staging, metrics and existing engine cases.
- Retained search attempts, fixed evaluation dates and forbidden cost changes during search.
- Local API request boundaries, unavailable dates, correct trade/plan links, explicit featured selection, English report/evidence exports and browser connection policy.
- A subprocess with the offline guard rejects external DNS and direct external socket connections while allowing localhost communication.

`npm run build` passes TypeScript and creates local production assets. Plotly makes the bundle approximately 4.9 MB before compression; it is bundled locally, not downloaded at launch. This is a size warning, not a build failure.

## Browser evidence

Verification used the running built application with the default offline guard enabled. Screenshots are in `docs/screenshots/v3/`.

| Requirement | Observed behavior |
|---|---|
| Correct featured default | Opening the app shows 32.3% return, 1.48 Sharpe, 19.3% drawdown, correct dates and target-period optimization label. |
| Unsaved parameters | Moving entry threshold from 2% to 2.5% retains the saved curve and displays “Parameters changed — run to update”. |
| Real new experiment | UI submission completed as `20260917T235036_8f24a0a8`; before/after curves and largest monthly change appeared. This is an interaction check, not a new selected showcase. |
| Validation | Tranche total 110% produced an English configuration error. Restoring 100% allowed calculation. |
| Cancellation | Rolling job `5718ab67627b4de0` reached the explicit cancelled state; no incomplete result became a saved experiment. |
| Monthly trade linkage | Featured July heatmap opened July's 30 actual fills. Closing trade details retained `2025-07`. |
| Three-stage explanation | Stock 600106, order O0000030: 40%/30%/30% plan, fills on July 2, 11 and 23, actual fees and slippage. Allocation-origin and later-tranche checks are separate dates. |
| Rolling navigation | Walk-Forward opens the saved twelve-month run; September selection updates the history/cutoff, candidate evidence and monthly curve. Fast playback reaches June 2026 and stops. |
| Comparison | Featured, rolling and market-filter cases display as three distinctly named series; historical incompatible periods are disabled. |
| Chart inspection | Zoom changes the axes while the saved 1.48/19.3% values remain unchanged; selecting the first search marker opens candidate 1. |
| Image export | The explicit Equity PNG endpoint renders a real 1800×1200 image from saved data; the image was opened and visually checked. The in-app browser did not expose a download event for Plotly's camera, so the explicit local endpoint is the verified fallback. |
| English and errors | Main controls, explanations, tour, reports and API errors use English. Browser console had no runtime errors during the verified path. |
| Responsive layout | 1440×900 and 1280×900 checked. At 1280, document width was 1265, with no horizontal page overflow. |

## Offline scope and delivery

The server reports `offline: true`. Its process-local audit hook blocks external DNS/socket access, new workers inherit it, and the browser's content policy allows only local connections/assets. The UI-submitted experiment above completed under this restriction. Static assets, fonts, plots, snapshots and saved results are local. No Windows-wide network adapter setting was changed, and this record does **not** claim a physical cable-disconnection test.

The archive built by `scripts/package_showcase.py` includes compiled UI, local API/engine, web dependencies, selected snapshot/results, search records, English reports, screenshots, launchers and file hashes. It excludes unrelated download caches and needs a compatible existing Python numerical environment. On this prepared machine the launcher uses FinRL directly; on a fresh machine initial installation needs a connection.

The prepared archive was extracted into a fresh independent directory and all 778 packaged file hashes were verified. Its own `start.ps1 -NoBrowser -Port 8767` started successfully with `offline: true`. Replaying the accepted configuration there produced run `20260918T001725_202ae979`: the **entire equity, fill, order, position and plan tables matched exactly**, as did every saved metric. The clone served its compiled frontend, rolling August selection, August trade filter and a real PNG export successfully. The record is `storage/showcase/bundle-verification.json`. Final packaging adds this verification record and updated documentation; unchanged tested application files are hash-checked against the extracted copy.

## Disclosed limits

- Target-period optimization and the surviving-stock observation pool limit generalization. The result is not an independent holdout or a profitability guarantee.
- Research mode omits minimum commission and transfer fees, uses fractional adjusted-price units and has incomplete historical limit/corporate-action settlement data. Strict share mode is not silently enabled.
- A 10% allocation target may drift above 10% after price changes. A 25% evaluation bound cannot prevent a future gap-driven loss.
- Declared risk comparisons retain their actual results, even when better than the accepted case. They do not replace it automatically.
- Longer alternative calibration windows and portfolio combinations were optional later research, not prerequisites for the default 12+3+1 delivery.
