"""Tabbed Streamlit interface for the NIFTY/S&P/INR Research Lab."""

from pathlib import Path
import html
import pandas as pd
import streamlit as st

from .app_service import (
    COMPARISON_START, build_lab, csv_bundle_bytes, dataframe_csv_bytes,
    excel_bytes, figure_bundle_bytes, kpis, source_status, trimmed_result,
)
from .config import HORIZONS, NIFTY, SP, FX, SP_INR, NIFTY_USD
from .reporting import research_summary
from .rolling import excess_summary
from .visualizations import figure_set

ROOT = Path(__file__).resolve().parents[1]


@st.cache_resource(ttl="6h", show_spinner=False, scope="session")
def _lab(root, refresh_generation=0):
    return build_lab(root, force_refresh=refresh_generation > 0)


def _css():
    path = ROOT / "assets/dashboard.css"
    if path.exists():
        st.markdown(f"<style>{path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def _hero(lab=None):
    pills = ""
    if lab is not None:
        parts = []
        for _, row in source_status(lab).iterrows():
            label = {NIFTY: "NIFTY 50 TRI", SP: "S&P 500 TR", FX: "USD/INR"}.get(row.Series, row.Series)
            parts.append(f'<span class="status-pill"><span class="status-dot"></span>{html.escape(label)} · {row.Last_date}</span>')
        pills = '<div class="status-strip">' + "".join(parts) + "</div>"
    st.markdown(f"""
    <div class="hero">
      <div class="hero-kicker">Quantitative market research</div>
      <div class="hero-title">NIFTY 50 × S&P 500 × INR</div>
      <div class="hero-sub">Total-return comparison with currency attribution, rolling holding periods,
      drawdowns, risk diagnostics and robustness testing. Both equity series begin on exactly 30 June 1999.</div>
      {pills}
    </div>""", unsafe_allow_html=True)


def _plot(fig, key):
    st.plotly_chart(fig, use_container_width=True, key=key, config={"displaylogo": False, "responsive": True})


def _pct_table(frame, percent_cols=None, height=360):
    if frame is None or frame.empty:
        st.info("No observations are available for this view.")
        return
    display = frame.copy()
    percent_cols = percent_cols or []
    config = {}
    for c in percent_cols:
        if c in display and pd.api.types.is_numeric_dtype(display[c]):
            display[c] = display[c] * 100
            config[c] = st.column_config.NumberColumn(format="%.2f%%")
    st.dataframe(display, use_container_width=True, height=height, column_config=config)


def _controls(lab):
    st.sidebar.markdown("### Analysis controls")
    horizon = st.sidebar.select_slider("Rolling horizon", options=list(HORIZONS), value=10, format_func=lambda x: f"{x}Y")
    perspective = st.sidebar.radio("Investor perspective", ["Indian investor", "US investor"])
    capital = st.sidebar.selectbox("Starting wealth", [100, 10_000, 100_000])
    log_scale = st.sidebar.toggle("Logarithmic wealth scale", True)
    include_ytd = st.sidebar.toggle("Include current partial year", True)
    with st.sidebar.expander("Date range"):
        start = st.date_input("Start", COMPARISON_START.date(), min_value=COMPARISON_START.date(), max_value=lab.daily.index[-1].date())
        end = st.date_input("End", lab.daily.index[-1].date(), min_value=COMPARISON_START.date(), max_value=lab.daily.index[-1].date())
    return horizon, perspective, capital, log_scale, include_ytd, start, end


def _landing():
    _hero()
    a, b = st.columns([1.3, 1])
    with a:
        st.markdown("### One-click research workflow")
        st.write("Run the analysis once. The application retrieves and validates all market data in the backend, aligns the common sample, and opens the full tabbed research dashboard.")
        st.info("No CSV upload, ZIP upload, notebook cells, or manual data maintenance.")
    with b:
        st.markdown("### Live sources")
        st.write("NIFTY 50 TRI — NSE Indices")
        st.write("S&P 500 Total Return — Yahoo ^SP500TR")
        st.write("USD/INR — FRED DEXINUS")


def run_app():
    st.set_page_config(page_title="NIFTY 50 × S&P 500 × INR", layout="wide", initial_sidebar_state="expanded")
    _css()
    st.session_state.setdefault("refresh_generation", 0)
    st.session_state.setdefault("analysis_ready", False)

    if not st.session_state.analysis_ready:
        _landing()
        if st.sidebar.button("Run Analysis", type="primary", use_container_width=True):
            st.session_state.analysis_ready = True
            st.rerun()
        return

    try:
        with st.spinner("Retrieving and validating live market data..."):
            lab = _lab(str(ROOT), st.session_state.refresh_generation)
    except Exception as exc:
        _hero()
        st.error("The live market-data pipeline could not start.")
        st.code(str(exc), language=None)
        if st.button("Retry"):
            st.session_state.refresh_generation += 1
            _lab.clear()
            st.rerun()
        return

    _hero(lab)
    if st.sidebar.button("Refresh live data", use_container_width=True):
        st.session_state.refresh_generation += 1
        _lab.clear()
        st.session_state.pop("bootstrap_result", None)
        st.rerun()

    horizon, perspective, capital, log_scale, include_ytd, start, end = _controls(lab)
    try:
        result = trimmed_result(lab, start, end, include_ytd)
    except Exception as exc:
        st.error(str(exc))
        return

    selected = (NIFTY, SP_INR, SP) if perspective == "Indian investor" else (NIFTY_USD, SP, NIFTY)

    def figs(names):
        return figure_set(
            result, lab, horizon=horizon, perspective=perspective, selected=selected,
            capital=capital, log=log_scale, only=set(names),
        )

    tabs = st.tabs(
        ["Overview", "Wealth", "Annual Returns", "Rolling Returns", "Outperformance",
         "Currency", "Risk & Drawdowns", "Robustness", "Methodology", "Export"],
        key="research_tabs", on_change="rerun",
    )

    if tabs[0].open:
        with tabs[0]:
            x = kpis(result, capital)
            c = st.columns(4)
            c[0].metric("Common sample", f"{x['start']} → {x['end']}")
            c[1].metric("NIFTY CAGR", f"{x['nifty_cagr']:.2%}", f"Ending value {x['nifty_wealth']:,.0f}")
            c[2].metric("S&P INR CAGR", f"{x['sp_inr_cagr']:.2%}", f"Ending value {x['sp_inr_wealth']:,.0f}")
            c[3].metric("INR depreciation CAGR", f"{x['fx_cagr']:.2%}")
            _plot(figs(["wealth"])["wealth"], "overview_wealth")
            st.code(research_summary(result, horizon, perspective), language=None)

    elif tabs[1].open:
        with tabs[1]:
            st.markdown("### Equal-start growth of wealth")
            st.caption("Both equity indices use the identical selected starting cutoff. Pre-30-Jun-1999 S&P history is excluded.")
            _plot(figs(["wealth"])["wealth"], "wealth")

    elif tabs[2].open:
        with tabs[2]:
            st.markdown("### Calendar-year returns")
            _plot(figs(["annual"])["annual"], "annual")
            annual = result["annual"]
            _pct_table(annual, [c for c in [NIFTY, SP, FX, SP_INR, NIFTY_USD] if c in annual])

    elif tabs[3].open:
        with tabs[3]:
            f = figs(["rolling", "excess", "distributions"])
            _plot(f["rolling"], "rolling")
            e = excess_summary(result["rolling"][horizon], perspective)
            a = st.columns(4)
            a[0].metric("S&P win rate", f"{e['SP_wins']:.1%}")
            a[1].metric("NIFTY win rate", f"{e['NIFTY_wins']:.1%}")
            a[2].metric("Median S&P advantage", f"{e['Median_advantage']*100:.2f} pp")
            a[3].metric("Windows", f"{int(e['Windows']):,}")
            _plot(f["excess"], "excess")
            _plot(f["distributions"], "distributions")
            summary = result["rolling_summaries"][horizon]
            _pct_table(summary, [c for c in summary.columns if c != "Windows"])

    elif tabs[4].open:
        with tabs[4]:
            f = figs(["probability", "holding_matrix", "endpoints"])
            _plot(f["probability"], "probability")
            _plot(f["holding_matrix"], "holding")
            _plot(f["endpoints"], "endpoints")

    elif tabs[5].open:
        with tabs[5]:
            f = figs(["fx_attribution", "fx_rolling"])
            _plot(f["fx_attribution"], "fxannual")
            _plot(f["fx_rolling"], "fxrolling")
            st.markdown("### Rupee depreciation / appreciation table")
            st.dataframe(result["fx_annual"], use_container_width=True)

    elif tabs[6].open:
        with tabs[6]:
            f = figs(["drawdowns", "volatility", "correlation"])
            _plot(f["drawdowns"], "drawdowns")
            _plot(f["volatility"], "volatility")
            _plot(f["correlation"], "correlation")
            st.markdown("### Risk metrics")
            st.dataframe(result["risk"], use_container_width=True)

    elif tabs[7].open:
        with tabs[7]:
            st.markdown(f"### Non-overlapping {horizon}-year windows")
            st.dataframe(result["nonoverlap"][horizon], use_container_width=True)
            st.markdown("### Paired moving-block bootstrap")
            if st.button("Run 5,000-replication bootstrap"):
                with st.spinner("Running bootstrap..."):
                    ci, _, meta = lab.bootstrap(
                        result, horizon, frequency="monthly", block_length=12,
                        replications=5000, seed=42, perspective=perspective,
                    )
                    st.session_state.bootstrap_result = (ci, meta, horizon, perspective)
            cached = st.session_state.get("bootstrap_result")
            if cached and cached[2:] == (horizon, perspective):
                st.dataframe(cached[0], use_container_width=True)
                st.caption(cached[1].get("caveat", ""))

    elif tabs[8].open:
        with tabs[8]:
            st.markdown("### Data provenance")
            st.dataframe(source_status(lab), use_container_width=True)
            st.markdown("### Validation")
            st.dataframe(lab.validation, use_container_width=True)
            error = max(abs(float(v)) for v in lab.identity_errors.values())
            st.success(f"Currency identities pass; maximum numerical error {error:.3g}.")
            st.markdown(f"""
### Methodological boundary
- Comparison begins exactly **{COMPARISON_START.date()}** for both equity indices.
- Common end is the latest validated common cutoff.
- Total return is compared with total return; price-index substitutes are prohibited.
- USD/INR is INR per USD, so a rise represents INR depreciation.
- Overlapping long-horizon windows are descriptive; robustness uses non-overlapping windows and moving-block bootstrap.
""")

    elif tabs[9].open:
        with tabs[9]:
            st.markdown("### Download research outputs")
            cached = st.session_state.get("bootstrap_result")
            bootstrap = cached[0] if cached else None
            st.download_button("Complete Excel workbook", excel_bytes(result, lab, bootstrap), "nifty_sp500_fx_research.xlsx")
            st.download_button("All tables — CSV ZIP", csv_bundle_bytes(result, lab, bootstrap), "nifty_sp500_fx_tables.zip", "application/zip")
            st.download_button("Annual returns CSV", dataframe_csv_bytes(result["annual"]), "annual_returns.csv", "text/csv")
            if st.button("Prepare interactive figure archive"):
                all_figs = figs([
                    "wealth", "annual", "rolling", "excess", "distributions", "probability",
                    "holding_matrix", "endpoints", "fx_attribution", "fx_rolling",
                    "drawdowns", "volatility", "correlation",
                ])
                st.session_state.figure_zip = figure_bundle_bytes(all_figs)
            if "figure_zip" in st.session_state:
                st.download_button("Interactive figures — HTML ZIP", st.session_state.figure_zip, "nifty_sp500_fx_figures.zip", "application/zip")
