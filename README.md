# NIFTY 50 × S&P 500 × INR Research Lab

Interactive Streamlit research dashboard comparing the **NIFTY 50 Total Return Index** and **S&P 500 Total Return Index** from an Indian-investor perspective, with explicit USD/INR attribution, rolling holding-period analysis, risk diagnostics and statistical robustness checks.

## Canonical comparison

The primary comparison begins exactly on **30 June 1999** for both equity indices. Earlier S&P 500 history is deliberately excluded from comparative calculations. The end date is determined dynamically from the latest validated common observation across NIFTY TRI, S&P 500 TR and USD/INR.

## Normal workflow

1. Open the deployed Streamlit application.
2. Click **Run Analysis**.
3. Use the tabs.

There is no CSV upload, ZIP upload, Colab notebook, dependency-install step or manual market-data maintenance.

## Live data architecture

| Series | Source | Role |
|---|---|---|
| NIFTY 50 Total Return Index | NSE Indices | Indian equity total return in INR |
| S&P 500 Total Return | Yahoo Finance ^SP500TR | US equity total return in USD |
| USD/INR | Federal Reserve / FRED DEXINUS | INR per USD |

On first execution the app retrieves the full required histories directly from the providers. The running Streamlit container creates a validated local runtime cache and refreshes it when the source is behind the current date or when **Refresh live data** is pressed.

The application never silently substitutes the NIFTY price index (^NSEI) or S&P 500 price index (^GSPC).

## Dashboard

The application contains ten lazy-loaded tabs:

- **Overview** — common sample, headline CAGRs, ending wealth and research summary.
- **Wealth** — equal-start normalized wealth comparison.
- **Annual Returns** — calendar-year heatmap and table.
- **Rolling Returns** — 1/3/5/7/10/15/20-year rolling CAGR, excess returns and distributions.
- **Outperformance** — win probability, start-year × holding-period matrix and endpoint sensitivity.
- **Currency** — USD equity return and INR currency contribution.
- **Risk & Drawdowns** — drawdowns, risk metrics, volatility and correlations.
- **Robustness** — non-overlapping windows and on-demand 5,000-replication moving-block bootstrap.
- **Methodology** — source provenance, validation and methodological boundaries.
- **Export** — XLSX, CSV and interactive HTML figure downloads.

## Methodology

For an Indian investor:

1 + R(S&P, INR) = (1 + R(S&P, USD)) × (1 + R(USD/INR))

The engine validates this identity numerically. Log returns are used for exactly additive currency attribution.

India, the United States and FX markets have different holidays and closing times. Alignment therefore uses bounded backward-as-of observations and never fills an earlier research cutoff with a future observation.

Rolling CAGR uses calendar offsets rather than assuming 252 × years trading observations. Overlapping long-horizon windows are descriptive, not treated as independent observations. Robustness analysis includes non-overlapping windows and paired moving-block bootstrap inference.

## Run locally

python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run streamlit_app.py

## Streamlit Community Cloud

Deploy with:

- Repository: nayakpranav/nifty-sp500-fx-research-lab
- Branch: main
- Main file: streamlit_app.py
- Python: 3.12

No application secrets are required by the current public market-data sources.

## Scope

This application is historical research, not an investment-advice or forecasting engine. It does not model taxes, fund expense ratios, tracking error, remittance costs or investor-specific tax treatment.
