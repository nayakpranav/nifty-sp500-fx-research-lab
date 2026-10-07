# NIFTY 50 × S&P 500 × INR Research Lab

A Streamlit quantitative-research application comparing the **NIFTY 50 Total Return Index** with the **S&P 500 Total Return Index** from the perspective of an Indian investor, with explicit USD/INR attribution, rolling holding-period analysis, risk diagnostics and robustness checks.

## Canonical comparison

The public dashboard deliberately starts both equity series on exactly **30 June 1999**, the beginning of the verified NIFTY 50 TRI history used by this project. Earlier S&P 500 observations remain in source provenance but are excluded from the primary comparison.

The common end date is determined automatically from the latest validated date shared by the required market series.

## Normal workflow

1. Open the deployed Streamlit app.
2. Click **Run Analysis**.
3. Use the tabs.

There is no normal CSV upload, ZIP upload, notebook execution or dependency-install step.

The app automatically:

- loads the verified baseline observations bundled in the repository;
- refreshes any source that is behind the current date;
- validates benchmark identity, currency direction and observations;
- aligns the three primitive series without using future observations;
- forces the fair comparison to start on 1999-06-30;
- calculates and caches the complete research snapshot;
- exposes tables, interactive figures, robustness analysis and downloads.

If a provider is temporarily unavailable, the application can continue from the last verified baseline and records a visible refresh warning. It never silently substitutes the NIFTY price index for NIFTY TRI.

## Market data

| Series | Primary source | Role |
|---|---|---|
| NIFTY 50 Total Return Index | NSE Indices | Indian equity total return in INR |
| S&P 500 Total Return | Yahoo Finance `^SP500TR` | US equity total return in USD |
| USD/INR | Federal Reserve / FRED `DEXINUS` | INR per USD |

The currency definition is explicit: a rising USD/INR value means INR depreciation against the US dollar.

## Dashboard tabs

- **Overview** — common sample, headline CAGRs, ending wealth and research summary.
- **Wealth** — equal-start normalized wealth comparison.
- **Annual Returns** — calendar-year heatmap and table.
- **Rolling Returns** — 1/3/5/7/10/15/20-year rolling CAGR, excess returns and distributions.
- **Outperformance** — win probability by horizon, start-year × holding-period matrix and endpoint sensitivity.
- **Currency** — USD equity return versus INR currency contribution, including exact log attribution.
- **Risk & Drawdowns** — drawdown depth/recovery, risk metrics, rolling volatility, correlations and FX regimes.
- **Robustness** — non-overlapping windows and on-demand paired moving-block bootstrap.
- **Methodology** — provenance, validation and methodological boundaries.
- **Export** — complete XLSX, CSV bundle and interactive figure bundle.

Modern Streamlit tab reruns are used so only the selected analytical view is rendered. Bootstrap inference and archive generation remain explicitly on-demand.

## Run locally

Use Python 3.12 for parity with Streamlit Community Cloud's current default deployment runtime.

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Run from the repository root so local path behavior matches Streamlit Community Cloud.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
PYTHONPATH=. python tools/streamlit_acceptance.py
```

The migration release preserves the original quantitative test suite and adds an application-backend acceptance check enforcing:

- exact 1999-06-30 comparison start;
- currency identities within numerical tolerance;
- working rolling analysis;
- selective/lazy figure construction;
- working XLSX and CSV exports.

GitHub Actions runs the test suite and compile check on pushes and pull requests.

## Streamlit Community Cloud deployment

Repository layout follows Streamlit Community Cloud conventions:

```text
.
├── streamlit_app.py
├── requirements.txt
├── .streamlit/config.toml
├── assets/dashboard.css
├── src/
├── data/raw/
├── tests/
└── tools/
```

Deployment settings:

- repository: this GitHub repository;
- branch: `main`;
- entrypoint: `streamlit_app.py`;
- Python: `3.12`.

No application secrets are required by the current public market-data sources.

## Research methodology

### Currency conversion

For an Indian investor:

```text
1 + R(S&P, INR) = (1 + R(S&P, USD)) × (1 + R(USD/INR))
```

The application validates this identity numerically. Log returns are used when an exactly additive attribution is required.

### Alignment

India, the United States and FX markets do not share identical holidays or closing times. The engine uses bounded backward-as-of alignment and never fills an earlier research cutoff with a future observation.

### Rolling returns

Rolling CAGR uses calendar offsets rather than assuming `252 × years` observations. Long-horizon overlapping windows are descriptive and are not treated as independent observations.

### Robustness

The application includes:

- endpoint sensitivity;
- starting-year sensitivity;
- non-overlapping holding windows;
- paired moving-block bootstrap inference;
- tail outcomes and sample-size disclosure.

## Limitations

The application is historical research, not an investment-advice or forecasting engine. It does not currently model taxes, transaction costs, fund expense ratios, tracking error, remittance costs or investor-specific tax treatment. India/US equity closes and the FRED FX fixing are asynchronous observations.

## Main files

- `streamlit_app.py` — Community Cloud entrypoint.
- `src/streamlit_ui.py` — tabbed web interface.
- `src/app_service.py` — Streamlit orchestration, fixed comparison start and downloads.
- `src/reporting.py` — analytical snapshot engine.
- `src/data_sources.py` — live refresh, provenance and verified cache handling.
- `src/visualizations.py` — Plotly research figures with selective lazy construction.
- `tools/streamlit_acceptance.py` — backend acceptance test for the deployed architecture.
