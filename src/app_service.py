"""Application service layer for the Streamlit deployment.

This module intentionally reuses the validated research engine.  It owns only
application orchestration: source refresh, the fixed fair-comparison boundary,
and download serialization.
"""

from __future__ import annotations

from dataclasses import replace
from io import BytesIO
from pathlib import Path
import zipfile

import pandas as pd

from .config import Config, NIFTY, SP, FX, SP_INR, NIFTY_USD
from .data_sources import load_sources, provenance
from .reporting import ResearchLab, tables_for_export
from .transforms import align_daily
from .validation import DataError

COMPARISON_START = pd.Timestamp("1999-06-30")


def build_lab(root: str | Path, *, force_refresh: bool = False) -> ResearchLab:
    """Load, refresh, validate and align all market data for the web app.

    The public dashboard always begins on 30 June 1999.  The S&P 500 and FX
    histories may extend further back, but those earlier observations are kept
    only as source provenance and never enter the fair comparison.
    """
    root = Path(root).resolve()
    config = Config(root=root, force_refresh=force_refresh, include_ytd=True).prepare()
    raw, metadata, validation = load_sources(config)
    daily, audit = align_daily(raw, config.asof_tolerance_days)

    if COMPARISON_START not in daily.index:
        raise DataError(
            "Fair-comparison invariant failed: 30 June 1999 is not a validated "
            "common valuation cutoff across NIFTY TRI, S&P 500 TR, USD/INR and EUR/USD. "
            "The application will not silently move the requested start date."
        )

    daily = daily.loc[COMPARISON_START:].copy()
    audit = audit.loc[COMPARISON_START:].copy()
    if daily.index[0] != COMPARISON_START:
        raise DataError("Comparison sample did not begin exactly on 30 June 1999.")

    lab = ResearchLab(daily, audit, metadata, validation, config)
    lab.provenance = provenance(raw, metadata)
    lab.comparison_start = COMPARISON_START
    lab.save_processed()
    return lab


def source_status(lab: ResearchLab) -> pd.DataFrame:
    """Compact status table for the dashboard header and methodology tab."""
    frame = lab.provenance.copy()
    frame["Comparison_start"] = COMPARISON_START.date()
    frame["Included_from"] = [
        max(pd.Timestamp(x), COMPARISON_START).date() for x in frame["First_date"]
    ]
    return frame


def kpis(result: dict, capital: float = 100.0) -> dict[str, float | str]:
    """Headline equal-start wealth and CAGR metrics from the selected sample."""
    daily = result["daily"]
    years = (daily.index[-1] - daily.index[0]).days / 365.2425

    def growth(name: str) -> float:
        return float(capital * daily[name].iloc[-1] / daily[name].iloc[0])

    def cagr(name: str) -> float:
        return float((daily[name].iloc[-1] / daily[name].iloc[0]) ** (1 / years) - 1)

    return {
        "start": str(daily.index[0].date()),
        "end": str(daily.index[-1].date()),
        "years": years,
        "nifty_wealth": growth(NIFTY),
        "sp_inr_wealth": growth(SP_INR),
        "sp_usd_wealth": growth(SP),
        "nifty_cagr": cagr(NIFTY),
        "sp_inr_cagr": cagr(SP_INR),
        "sp_usd_cagr": cagr(SP),
        "fx_cagr": cagr(FX),
    }


def dataframe_csv_bytes(frame: pd.DataFrame) -> bytes:
    """Serialize a table exactly as displayed without mutating numeric values."""
    return frame.to_csv(index=True, float_format="%.10g").encode("utf-8")


def excel_bytes(result: dict, lab: ResearchLab, bootstrap=None) -> bytes:
    """Build the complete workbook in memory for Streamlit download."""
    tables = tables_for_export(result, lab, bootstrap=bootstrap)
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        for name, table in tables.items():
            table.to_excel(writer, sheet_name=name[:31])
            ws = writer.sheets[name[:31]]
            ws.freeze_panes = "B2"
            ws.auto_filter.ref = ws.dimensions
    out.seek(0)
    return out.read()


def csv_bundle_bytes(result: dict, lab: ResearchLab, bootstrap=None) -> bytes:
    """Create a ZIP containing all analytical tables as CSV files."""
    tables = tables_for_export(result, lab, bootstrap=bootstrap)
    out = BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, table in tables.items():
            zf.writestr(
                f"{name}.csv",
                table.to_csv(index=True, float_format="%.10g").encode("utf-8"),
            )
    out.seek(0)
    return out.read()


def trimmed_result(lab: ResearchLab, start, end, include_ytd=True, perspective="INR-based investor"):
    """Validated user-selected subrange; never permits pre-TRI observations."""
    start = max(pd.Timestamp(start), COMPARISON_START)
    end = min(pd.Timestamp(end), lab.daily.index[-1])
    if start >= end:
        raise ValueError("The selected range must contain at least two valuation dates.")
    return lab.analyze(start=start, end=end, include_ytd=include_ytd, perspective=perspective)


def figure_bundle_bytes(figures: dict) -> bytes:
    """Bundle self-contained interactive HTML figures for download."""
    out = BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, fig in figures.items():
            html = fig.to_html(full_html=True, include_plotlyjs=True)
            zf.writestr(f"{name}.html", html.encode("utf-8"))
    out.seek(0)
    return out.read()
