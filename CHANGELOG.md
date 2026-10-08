# Changelog

## 2026-10-07: Investor journey and final polish

- Added home-currency journey cards with actual entry/exit FX amounts, selected starting capital, native/home returns, exact FX contributions, wealth differences and winner for INR/USD/EUR.
- Added shared current-data interpretations in all analytical tabs and offline HTML, including rolling-window extremes, annual winners, long-horizon dependence, matrix signs, endpoint sensitivity, volatility, drawdown dates and 36-month correlation summaries.
- Compacted annual heatmaps to at most 720 px and separated titles, legends and subplot headings through shared defaults.
- Distinguished validated data-quality notes from stale/extreme-move warnings and failures without removing underlying diagnostics.
- Added investor-lens glossary definitions and explicit bootstrap inclusion status in exports; preserved the original sample, sources, analytical calculations and export formats.
- Added journey accounting, scaling, lens-specific risk/correlation, narrative, status and offline parity regression tests.

## 2026-10-07: Dark dashboard and investor lenses

- Added a midnight navy theme shared by Streamlit, Plotly and offline reports, responsive untruncated sample dates, five universal KPIs and a secondary home-currency strip.
- Added verified FRED DEXUSEU retrieval, EUR/INR cross-rate, NIFTY EUR and S&P EUR conversions, numerical identity checks and tests.
- Centralized INR/USD/EUR lens pairs across rolling excess, calendar winners, holding/endpoint matrices, risk views, FX attribution and paired moving-block bootstrap.
- Added deterministic performance, currency, holding-period and risk interpretation cards; contextual glossary and explanations for all ten tabs.
- Added the stacked 1Y/3Y/5Y/10Y rolling figure. Updated legends, line encodings, dark heatmaps, exact-date matrix hovers and human-readable table labels.
- Added one self-contained interactive HTML dashboard with embedded Plotly, local accessible tabs, metadata, tables, help and methodology. All exports are generated automatically and cached. Excel, CSV and individual figure archives remain available.
- Added quantitative, provider-direction, export and Streamlit AppTest regressions to CI.
- Preserved the exact 30 June 1999 default start, live-only sources, bounded backward-as-of alignment, original INR/USD identities, research horizons, FX regimes, drawdown and risk metrics, non-overlapping windows and bootstrap methodology.

Taxes, fees, remittance costs and investment recommendations remain outside scope. Runtime data are never committed.
