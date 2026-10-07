# NIFTY 50 × S&P 500 × FX Research Lab

A dark institutional Streamlit research dashboard comparing dividend-reinvested **NIFTY 50 Total Return Index** and **S&P 500 Total Return** across **INR, USD and EUR investor lenses**. Deterministic interpretation explains performance, FX contribution, holding-period consistency and risk. This extends the original engine rather than replacing its calculations.

## Canonical fair comparison

The default comparison begins **exactly 30 June 1999**. Earlier S&P history is retained only as source provenance. The end is the latest validated common valuation cutoff across all four primitive sources. A user may choose a later research subrange; the app fails closed if the canonical start is unavailable.

## Workflow

**Open app → Run Analysis → Use dashboard.** Market histories are retrieved and validated automatically. Refresh live data updates providers. No CSV maintenance, uploads or notebook workflow is required.

## Live sources and verified FX direction

| Primitive | Provider | Units / role |
|---|---|---|
| NIFTY 50 TRI | NSE Indices total-return endpoint | INR native equity total return |
| S&P 500 TR | Yahoo Finance `^SP500TR` | USD native equity total return |
| USD/INR | Federal Reserve / FRED `DEXINUS` | INR per USD |
| EUR/USD | Federal Reserve / FRED `DEXUSEU` | USD per EUR |

DEXUSEU's **Units** metadata is verified programmatically as **U.S. Dollars to One Euro** before download. Wrong or missing evidence stops retrieval; the code never guesses or silently inverts direction. Provider metadata and daily positive/finite observations are validated, and runtime caches are checksum protected. Required data are refreshed dynamically; failed retrieval never silently substitutes a price index or stale upload.

## Investor lenses and exact conversion

- **INR-based investor:** NIFTY in native INR vs S&P translated to INR.
- **USD-based investor:** NIFTY translated to USD vs S&P in native USD.
- **EUR-based investor:** both investments translated into EUR. The NIFTY flow is EUR savings → INR → Indian equity → EUR wealth.

With `USDINR = INR/USD` and `EURUSD = USD/EUR`:

```text
EURINR = USDINR × EURUSD
SP_INR = SP_USD × USDINR
NIFTY_USD = NIFTY_INR ÷ USDINR
NIFTY_EUR = NIFTY_INR ÷ EURINR
SP_EUR = SP_USD ÷ EURUSD
```

The return identities and exact log attribution are checked numerically to `1e-10`. Arithmetic CAGR gaps are labelled separately from exact annual log contributions. The foreign-investor interpretation calculates the local equity CAGR needed to match the home-currency S&P return on the observed FX path.

## Dashboard and preserved research depth

Ten tabs cover Overview, Wealth, Annual Returns, Rolling Returns, Outperformance, Currency, Risk & Drawdowns, Robustness, Methodology and Export. The midnight navy theme, explicit currency labels, solid/dashed traces, blue-to-dark-to-amber heatmaps, five untruncated headline cards and secondary investor strip are shared with the standalone report. Each view includes plain-language help and contextual glossary terms.

The engine retains normalized wealth, calendar/YTD returns, trailing CAGR, 1/3/5/7/10/15/20-year calendar-offset rolling CAGR, excess distributions, historical win fractions, start-year holding matrices, endpoint sensitivity, FX attribution/regimes, risk metrics, drawdown episodes, monthly/daily correlations, non-overlapping windows and paired moving-block bootstrap. A new stacked **1Y/3Y/5Y/10Y** figure shows both comparable investments in the selected currency without a spaghetti chart.

### Investor Journey and current-data explanations

The Investor Lens describes the currency in which the investor earns/saves and ultimately measures wealth. Overview's **Investor Journey** follows equal selected starting capital through both markets, including the actual starting currency conversion, native index growth and final conversion home. INR investors compare `INR → NIFTY → INR` with `INR → USD → S&P → USD → INR`; USD investors compare native S&P with translated NIFTY; EUR investors translate both routes back to euros. Intermediate conversion routing is not a third investment.

Journey cards report native/home CAGR, FX CAGR, exact annual FX log contributions, arithmetic gaps, final wealth, winner, absolute wealth difference, signed NIFTY-minus-S&P percentage difference relative to S&P ending wealth, and CAGR difference. Capital scales wealth without changing growth rates. Shared deterministic helpers also explain the current annual extremes and winners, rolling ranges/positive fractions, outperformance counts/ties, matrix signs and endpoint dependence, drawdown dates, annualized volatility gaps and latest/median/minimum/maximum 36-month correlation.

Horizon lengths above half the selected sample trigger a prominent **limited independent long-horizon evidence** note. An adjacent-endpoint CAGR difference change of at least 2 percentage points triggers a descriptive endpoint sensitivity flag; this is a presentation heuristic, not a statistical test. Source pills distinguish validated missing-quote notes from stale/extreme-move warnings and failures; complete diagnostics remain in Methodology. Annual heatmaps are capped at 720 px; shared title/legend spacing and responsive journey components apply to both app and offline HTML. The Export view explicitly states whether matching bootstrap inference is included.

All pair-dependent statistics and bootstrap paths use the same selected currency. A common FX conversion preserves the ordering of paired equity wealth while changing absolute returns, CAGR gaps and risk; changing lenses must not manufacture a different historical winner.

## Immediately available exports

After each selected analysis state, cached downloads are ready automatically:

1. **Full Interactive HTML Dashboard** — one offline file, with Plotly embedded once, keyboard-accessible local tabs, interactive figures, interpretation, tables, glossary, provenance, methodology and selected dates/lens/horizon/YTD/display metadata. Filename: `YYYY-MM-DD_NIFTY_SP500_FX_Research_Lab.html`.
2. **Complete Excel Workbook** — analytical tables including primitive/derived daily and monthly levels, source-date audit, EUR attribution and inference if run.
3. CSV bundle ZIP, Annual Returns CSV and individual interactive figure HTML ZIP.

No preparation button is needed. The offline file requires no Streamlit server, websocket, CDN or API connection. Bootstrap is on demand; only results matching the current data, sample, horizon and lens enter exports. If it has not been run, the report states that clearly rather than inventing intervals. Technical CSV/XLSX exports retain compact series keys; human-facing tables and legends use centralized readable labels. Numeric return columns in the offline data tables use decimal fractions (`0.10 = 10%`).

## Methodological boundaries

Alignment uses a union of market sessions, bounded backward-as-of within seven calendar days, and never future-fills or bridges unknown interior gaps. Indian and US closes are asynchronous research valuations, not simultaneous executable prices. Monthly snapshots use calendar month-end labels; CAGR uses elapsed days / 365.2425. The first partial starting year is omitted; a partial terminal year is labelled YTD. Overlapping windows are descriptive and statistically dependent. Non-overlapping windows reduce overlap but retain regime dependence; moving-block intervals depend on stationarity and limited effective sample size. Sortino uses an explicit zero annual downside target, not an estimated risk-free rate.

**Taxes, fees, tracking error and remittance costs are excluded.** Historical research only, without forecasts, personalized allocation or investment recommendations.

## Run locally and test

```bash
python -m venv .venv
# Activate the virtual environment for your operating system.
pip install -r requirements-dev.txt
python -m pytest -q
streamlit run streamlit_app.py
```

CI runs quantitative regression, source-direction, report and Streamlit AppTest tests. Test fixtures are explicitly synthetic and never a production fallback. Browser acceptance additionally checks the real-data dashboard and standalone HTML at desktop and laptop widths.

## Streamlit Community Cloud

Repository: `nayakpranav/nifty-sp500-fx-research-lab`; branch: `main`; entry point: `streamlit_app.py`; Python 3.12. No application secrets are required. Deployment: https://nifty-sp500-fx-research-lab.streamlit.app/

## Module boundaries

The original source/alignment/metrics/rolling/statistics/service modules remain. `lenses.py`, `labels.py`, `theme.py`, `glossary.py`, `interpretation.py` and `presentation.py` centralize shared semantics. `fred.py` verifies EUR metadata; `html_report.py` and `assets/report.html` generate the offline snapshot. Streamlit handles controls and rendering rather than duplicating research or narrative logic.
