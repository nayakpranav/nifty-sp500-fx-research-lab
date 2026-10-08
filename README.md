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

Opening Export automatically builds and caches downloads for the selected state. Run Analysis and normal tab navigation do not render the PDF or prepare export archives.

1. **Quantitative Research Report (PDF)**: a print-friendly academic report with selectable text, six scientific figures, risk tables, shared findings, conditional conclusions, limitations and reproducibility metadata. ReportLab and matplotlib Agg run server-side without Chrome. Fonts are supplied by matplotlib.
2. **Research Interpretation Report (HTML)**: the same evidence, conclusion, figures and provenance in one self-contained dark research brief, including expandable crossover details.
3. **Full Interactive HTML Dashboard**: one offline file, with Plotly embedded once, eleven keyboard-accessible local tabs including Research Synthesis, interactive figures, interpretation, tables, glossary, provenance, methodology and selected dates/lens/horizon/YTD/display metadata. Filename: `YYYY-MM-DD_NIFTY_SP500_FX_Research_Lab.html`.
4. **Complete Excel Workbook**: analytical tables including primitive/derived daily and monthly levels, source-date audit, EUR attribution and inference if run.
5. CSV bundle ZIP, Annual Returns CSV and individual interactive figure HTML ZIP.

No preparation button is needed. The offline file requires no Streamlit server, websocket, CDN or API connection. Bootstrap is on demand; only results matching the current data, sample, horizon and lens enter exports. If it has not been run, the report states that clearly rather than inventing intervals. Technical CSV/XLSX exports retain compact series keys; human-facing tables and legends use centralized readable labels. Numeric return columns in the offline data tables use decimal fractions (`0.10 = 10%`).

### Shared synthesis and descriptive crossovers

`research_synthesis.py` extends the deterministic interpretation layer. Its structured evidence includes statistic identifiers, units, actual dates, counts, investor lens, uncertainty status and explanatory text. Streamlit, interactive HTML, research HTML and PDF consume those same findings. It reconciles endpoint versus rolling-majority leadership, mean versus median paired excess, winning frequency versus average magnitude, short versus long horizons and native versus home-currency rankings. Capital changes wealth while leaving CAGR unchanged.

Crossovers bracket observed monthly endpoint sign changes in paired S&P-minus-NIFTY CAGR. Actual matched investment starts remain separate from endpoints. The persistence convention is **six consecutive monthly endpoints** with the same leader, using the existing `1e-12` tie tolerance. Ties interrupt sustained runs but can bridge a bracketed sign change. Invalid observations and missing months reset comparisons; no crossing date is interpolated. Before/after fractions count all valid windows on each side, including ties. These are descriptive historical splits, not tests of economic regime changes. Counts, latest leaders and sustained sequences are shown for all seven standard horizons.

Optional inference is bound to a fingerprint of the selected daily panel, exact dates, lens and horizon. Changing the data or analytical selection discards stale intervals. Presentation changes to starting capital or YTD do not change the underlying returns being bootstrapped. Reports record raw provider coverage, the past observations actually used at the selected endpoint, the bounded valuation cutoff, source checksums, validation notes and generation time.

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

CI runs quantitative regression, source-direction, synthetic conflicting-evidence/crossover cases, PDF text and pagination, offline parity and Streamlit AppTest tests. Test fixtures are explicitly synthetic and never a production fallback. Browser acceptance additionally checks the real-data dashboard at desktop and mobile widths; PDF pages are rendered and visually inspected.

## Streamlit Community Cloud

Repository: `nayakpranav/nifty-sp500-fx-research-lab`; branch: `main`; entry point: `streamlit_app.py`; Python 3.12. No application secrets are required. Deployment: https://nifty-sp500-fx-research-lab.streamlit.app/

## Module boundaries

The original source/alignment/metrics/rolling/statistics/service modules remain. `lenses.py`, `labels.py`, `theme.py`, `glossary.py`, `interpretation.py` and `presentation.py` centralize shared semantics. `research_synthesis.py` supplies shared evidence and `research_report.py` renders academic PDF/HTML. `fred.py` verifies EUR metadata; `html_report.py` and `assets/report.html` generate the full interactive snapshot. Streamlit handles controls and rendering rather than duplicating research or narrative logic.
