# Three-minute demonstration

Before presenting, double-click **Start Lab.cmd** and select **Featured case**. Keep `storage/showcase/featured-report.html` available as a standalone fallback. The five-step guided tour is also available in the app.

**0:00–0:20 · Overview**

“This is a local research workspace for Shanghai A-share trading rules. My featured case has a Sharpe ratio of 1.48, approximately 1.5, and a maximum drawdown of 19.3% over July 2025 to June 2026. I selected it through retrospective exploration, so this period is not an independent holdout test.”

Point to exact metrics, the target-period label and same-pool buy-and-hold curve.

**0:20–1:05 · Strategy Lab**

“The rule is deliberately simple: enter after the closing price crosses 2% above its 30-session moving average; exit below a negative 2% deviation. Each allocation is built in three stages: 40%, 30% and 30%. Changing a control creates a new experiment while preserving the original result.”

Move the entry threshold one step. Point to “Parameters changed — run to update”, then run. Explain the previous and new curves. If computation is slower on another machine, open a saved comparison and describe it as precomputed. Click a month to inspect executions.

**1:05–1:50 · Walk-Forward**

“The rolling comparison uses twelve months to calibrate, three to validate and one to replay. Cash, holdings and unfinished entry plans carry across boundaries. The replay month's outcome does not enter that month's parameter selection.”

Select September; show the cutoff, calibration field and validation shortlist. Step to October or play briefly, then pause. “The recorded rolling case has Sharpe 1.30 and drawdown 13.7%. It trades some return for lower historical drawdown. The overall research protocol remains retrospective.”

**1:50–2:35 · Trade Replay**

Select **Featured case**, click July in the heatmap, and open a staged buy. “Here are the signal date, next-session execution, observed indicator, planned budget and actual fills. A plan is not the same as a completed trade; every later tranche passes its checks again.”

Point to fees and slippage. “Later prices appear only as retrospective context; they were unavailable to the original signal.” Close the sidebar to retain the month selection.

**2:35–3:00 · Compare & Archive**

Compare the featured, rolling and market-filter cases. “Matching data and execution assumptions let us inspect return and risk. All search attempts are retained, including poor outcomes. Reports and logs export locally, and prepared data supports an offline presentation.”

Open the English report or export the evidence ZIP. “My contribution is an explainable FinTech product combining financial rules, reproducible experiments and an interactive decision trail.”

## Questions

- **Why does the market filter score higher?** It is a separately recorded preset comparison, not a replacement for the accepted case or evidence of future performance.
- **Is this live trading?** No. It uses adjusted-price fractional units and daily execution assumptions. Methodology explains the fee, limit-price and corporate-action gaps.
- **Why not call this independent out-of-sample evidence?** Monthly decisions use earlier information, but the overall research was examined on the target period. The labels preserve that distinction.
- **What subscription did you buy?** None. BaoStock supplied the prepared daily dataset, and indicators are computed locally.
