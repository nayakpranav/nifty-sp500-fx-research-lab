"""Live market-data retrieval and verified runtime caching for Streamlit."""

from datetime import datetime, timezone
from pathlib import Path
from io import StringIO
import hashlib
import json
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import requests

from .config import REQUIRED, NIFTY, SP, FX, EURUSD, NSE_URL, NSE_API
from .fred import verify_eurusd_metadata
from .validation import DataError, validate_series, require_valid


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def _numeric(values):
    return pd.to_numeric(values.astype(str).str.replace(",", "", regex=False), errors="raise")


def parse_tri(frame, date_format=None):
    """Accept only explicitly identified total-return columns; generic Close is rejected."""
    normalized = {str(c).strip().lower().replace("_", " "): c for c in frame.columns}
    date_candidates = ["date", "index date", "historicaldate", "historical date"]
    value_candidates = [
        "total returns index", "total return index", "total returns index value",
        "totalreturnindex", "totalreturnsindex", "nifty tri inr", "nifty 50 tri",
    ]
    date_col = next((normalized[c] for c in date_candidates if c in normalized), None)
    level_col = next((normalized[c] for c in value_candidates if c in normalized), None)
    if date_col is None or level_col is None:
        raise DataError("NIFTY TRI source requires Date and Total Returns Index fields.")
    dates = pd.to_datetime(
        frame[date_col], format=date_format or "mixed", dayfirst=True, errors="raise"
    )
    dates = pd.DatetimeIndex(dates).tz_localize(None).normalize()
    return pd.Series(_numeric(frame[level_col]).to_numpy(), index=dates, name=NIFTY)


def official_tri(start="1999-06-30", end=None):
    """Fetch NIFTY 50 TRI directly from the NSE Indices total-return endpoint."""
    end = pd.Timestamp(end or datetime.now(timezone.utc).date())
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Referer": NSE_URL,
        "Content-Type": "application/json; charset=UTF-8",
    })
    session.get(NSE_URL, timeout=20).raise_for_status()
    pieces = []
    cursor = pd.Timestamp(start)
    while cursor <= end:
        stop = min(cursor + pd.DateOffset(years=1) - pd.Timedelta(days=1), end)
        payload = {
            "name": "NIFTY 50",
            "indexName": "NIFTY 50",
            "startDate": cursor.strftime("%d-%b-%Y"),
            "endDate": stop.strftime("%d-%b-%Y"),
        }
        response = session.post(NSE_API, json={"cinfo": json.dumps(payload)}, timeout=30)
        response.raise_for_status()
        decoded = response.json()
        records = decoded.get("d", decoded) if isinstance(decoded, dict) else decoded
        if isinstance(records, str):
            records = json.loads(records)
        if not isinstance(records, list) or not records:
            raise DataError(f"NSE TRI returned no records for {cursor.date()}–{stop.date()}.")
        frame = pd.DataFrame(records)
        if "Index Name" not in frame or not frame["Index Name"].astype(str).str.upper().eq("NIFTY 50").all():
            raise DataError("NSE endpoint did not establish NIFTY 50 identity.")
        piece = parse_tri(frame)
        if piece.index.has_duplicates:
            raise DataError("NSE endpoint returned duplicate TRI sessions.")
        piece = piece.sort_index()
        if piece.index.min() < cursor or piece.index.max() > stop:
            raise DataError("NSE endpoint ignored the requested date range.")
        pieces.append(piece)
        cursor = stop + pd.Timedelta(days=1)
    series = pd.concat(pieces)
    metadata = dict(
        index_name="NIFTY 50 Total Return Index",
        return_type="total_return",
        currency="INR",
        source="NSE Indices",
        source_url=NSE_URL,
        endpoint=NSE_API,
        identity_evidence="official_endpoint",
        retrieval_timestamp=timestamp(),
    )
    require_valid(validate_series(series, metadata))
    return series, metadata


# Verified against Yahoo's public ^SP500TR total-return listing, 8 October 2026.
# A dated index level is a second independent check if the volatile
# yfinance quote-summary metadata endpoint omits name/currency fields.
SP500TR_ANCHOR_DATE = pd.Timestamp("2026-10-02")
SP500TR_ANCHOR_CLOSE = 17321.99
SP500TR_ANCHOR_RELATIVE_TOLERANCE = 0.005
SP500TR_IDENTITY_URL = "https://finance.yahoo.com/quote/%5ESP500TR/history/"


def _sp500tr_identity(obj, series):
    """Validate native total-return identity without requiring quote-summary uptime.

    Yahoo's public symbol listing attests that ^SP500TR is S&P 500 (TR), USD.
    Prefer direct quote-summary metadata when available. If it is missing,
    require the *same* provider history to contain the independently published
    2026-10-02 total-return index level, and disclose the evidence downgrade.
    Explicitly contradictory provider metadata always fails closed.
    """
    try:
        info = obj.get_info() or {}
    except Exception:
        info = {}
    if not isinstance(info, dict):
        info = {}
    label = str(info.get("longName") or info.get("shortName") or "").strip()
    currency = info.get("currency")
    valid_label = "S&P 500" in label.upper() and (
        "(TR)" in label.upper() or "TOTAL RETURN" in label.upper()
    )

    # Never reinterpret a named price index or a different currency as total return.
    if label and not valid_label:
        raise DataError(
            f"^SP500TR provider returned conflicting instrument name {label!r}; "
            "the application will not substitute a price index."
        )
    if currency not in (None, "", "USD"):
        raise DataError(
            f"^SP500TR provider returned conflicting currency {currency!r}; "
            "expected USD."
        )
    if valid_label and currency == "USD":
        return label, "provider_metadata", False

    actual = series.get(SP500TR_ANCHOR_DATE, None)
    if actual is None or not np.isfinite(actual) or not np.isclose(
        float(actual), SP500TR_ANCHOR_CLOSE,
        rtol=SP500TR_ANCHOR_RELATIVE_TOLERANCE, atol=0.0
    ):
        raise DataError(
            "^SP500TR live quote-summary name/currency metadata is unavailable, "
            "and its historical levels do not match the independently verified "
            "Yahoo S&P 500 (TR), USD reference on 2026-10-02. "
            "No price-only benchmark will be substituted."
        )
    return "S&P 500 (TR)", "verified_provider_anchor", True


def yahoo_sp():
    """Retrieve S&P 500 Total Return history, rejecting price-only substitutes."""
    import yfinance as yf
    ticker = "^SP500TR"  # Only the total-return index; never ^GSPC.
    obj = yf.Ticker(ticker)

    # Read actual historical observations first. Quote-summary get_info() may
    # be empty/blocked on Streamlit Cloud even while the chart data is valid.
    history = obj.history(
        period="max", interval="1d", auto_adjust=False, back_adjust=False,
        repair=False, actions=False, keepna=True, raise_errors=True,
    )
    if history.empty or "Close" not in history:
        raise DataError("^SP500TR returned empty historical data or no Close field.")
    expected_price_fields = {"Open", "High", "Low", "Close"}
    if not expected_price_fields.issubset(history.columns):
        raise DataError("^SP500TR returned an unexpected historical OHLC schema.")
    absent = history[["Open", "High", "Low", "Close"]].isna().all(axis=1)
    series = history.loc[~absent, "Close"].copy()
    series.index = series.index.tz_localize(None).normalize()
    series.name = SP

    label, evidence, anchor_checked = _sp500tr_identity(obj, series)
    metadata = dict(
        ticker=ticker,
        index_name=label,
        source="Yahoo Finance / yfinance",
        source_url=SP500TR_IDENTITY_URL,
        identity_reference=SP500TR_IDENTITY_URL,
        identity_evidence=evidence,
        anchor_checked=anchor_checked,
        anchor_date="2026-10-02" if anchor_checked else None,
        anchor_reference_close=SP500TR_ANCHOR_CLOSE if anchor_checked else None,
        currency="USD",
        retrieval_timestamp=timestamp(),
        return_type="total_return",
        missing_source_observations=int(absent.sum()),
    )
    require_valid(validate_series(series, metadata))
    return series, metadata

def fred_fx():
    """Fetch Federal Reserve/FRED DEXINUS, quoted as INR per USD."""
    page_url = "https://fred.stlouisfed.org/series/DEXINUS"
    response = requests.get(page_url, timeout=25)
    response.raise_for_status()
    if "DEXINUS" not in response.text or "Indian Rupees to One U.S. Dollar" not in response.text:
        raise DataError("FRED DEXINUS units could not be verified.")
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXINUS&cosd=1973-01-01"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    frame = pd.read_csv(StringIO(response.text), na_values=["."])
    date_column = "observation_date" if "observation_date" in frame else "DATE"
    if "DEXINUS" not in frame or date_column not in frame:
        raise DataError("FRED returned an unexpected FX schema.")
    dates = pd.to_datetime(frame[date_column], format="%Y-%m-%d", errors="raise")
    missing = frame["DEXINUS"].isna()
    series = pd.Series(
        pd.to_numeric(frame.loc[~missing, "DEXINUS"], errors="raise").to_numpy(),
        index=pd.DatetimeIndex(dates[~missing]), name=FX,
    )
    metadata = dict(
        ticker="DEXINUS",
        index_name="Indian Rupees to U.S. Dollar Spot Exchange Rate",
        source="Federal Reserve H.10 / FRED DEXINUS",
        source_url=page_url,
        download_url=url,
        currency="INR",
        units="INR per USD",
        base="USD",
        quote="INR",
        return_type="FX",
        identity_evidence="provider_metadata",
        direction_evidence="Indian Rupees to One U.S. Dollar",
        retrieval_timestamp=timestamp(),
        missing_source_observations=int(missing.sum()),
    )
    require_valid(validate_series(series, metadata))
    return series, metadata


def fred_eurusd():
    """Verify FRED DEXUSEU Units, then retrieve daily USD per EUR observations."""
    page_url = "https://fred.stlouisfed.org/series/DEXUSEU"
    response = requests.get(page_url, timeout=25)
    response.raise_for_status()
    direction = verify_eurusd_metadata(response.text)
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXUSEU&cosd=1999-01-01"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    frame = pd.read_csv(StringIO(response.text), na_values=["."])
    date_col = "observation_date" if "observation_date" in frame else "DATE"
    if "DEXUSEU" not in frame or date_col not in frame:
        raise DataError("FRED returned an unexpected DEXUSEU schema.")
    dates = pd.to_datetime(frame[date_col], format="%Y-%m-%d", errors="raise")
    missing = frame["DEXUSEU"].isna()
    series = pd.Series(pd.to_numeric(frame.loc[~missing, "DEXUSEU"], errors="raise").to_numpy(),
                       index=pd.DatetimeIndex(dates[~missing]), name=EURUSD)
    metadata = dict(direction, ticker="DEXUSEU", index_name="U.S. Dollars to Euro Spot Exchange Rate",
                    source="Federal Reserve H.10 / FRED DEXUSEU", source_url=page_url, download_url=url,
                    return_type="FX", retrieval_timestamp=timestamp(), missing_source_observations=int(missing.sum()))
    require_valid(validate_series(series, metadata))
    return series, metadata


def save_cache(series, metadata, config):
    """Persist provider observations inside the running Streamlit container."""
    path = config.root / "data/raw" / f"{series.name}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    series.to_frame().to_csv(path, index_label="Date", date_format="%Y-%m-%d", float_format="%.12g")
    metadata = dict(
        metadata,
        sha256=sha256(path),
        first_date=str(series.index.min().date()),
        last_date=str(series.index.max().date()),
        observations=len(series),
        missing=int(series.isna().sum()),
    )
    path.with_suffix(".json").write_text(json.dumps(metadata, indent=2, default=str), encoding="utf8")
    return metadata


def read_cache(name, config):
    path = config.root / "data/raw" / f"{name}.csv"
    metadata = json.loads(path.with_suffix(".json").read_text(encoding="utf8"))
    if metadata.get("sha256") != sha256(path):
        raise DataError(f"{name} runtime cache checksum mismatch.")
    series = pd.read_csv(path, index_col="Date", parse_dates=True)[name]
    require_valid(validate_series(series, metadata, stale_days=config.stale_days))
    metadata["cache_status"] = "validated runtime cache"
    return series, metadata


def _should_refresh(series, force=False):
    if force:
        return True
    today = pd.Timestamp(datetime.now(timezone.utc).date()).tz_localize(None)
    return pd.Timestamp(series.index.max()).tz_localize(None) < today


def load_sources(config, tri_csv=None, tri_metadata=None):
    """Fully dynamic source loading; no user-uploaded market-data files are required."""
    config.prepare()
    raw, metadata, errors = {}, {}, {}
    for name in REQUIRED:
        try:
            cached_path = config.root / "data/raw" / f"{name}.csv"
            if cached_path.exists() and not config.force_refresh:
                try:
                    series, meta = read_cache(name, config)
                    if not _should_refresh(series):
                        raw[name], metadata[name] = series, meta
                        continue
                except Exception:
                    pass

            if name == NIFTY:
                series, meta = official_tri()
            elif name == SP:
                series, meta = yahoo_sp()
            elif name == EURUSD:
                series, meta = fred_eurusd()
            else:
                series, meta = fred_fx()
            meta = save_cache(series, meta, config)
            meta["cache_status"] = "live provider retrieval"
            raw[name], metadata[name] = series, meta
        except Exception as exc:
            errors[name] = f"{type(exc).__name__}: {exc}"

    if errors:
        msg = "\n".join(f"{k}: {v}" for k, v in errors.items())
        raise DataError(
            msg + "\nLive market-data loading failed. No price-index substitute or stale CSV upload is used."
        )

    report = pd.concat(
        [validate_series(raw[k], metadata[k], stale_days=config.stale_days) for k in REQUIRED],
        ignore_index=True,
    )
    require_valid(report)
    return raw, metadata, report


def provenance(raw, metadata):
    rows = []
    for key, series in raw.items():
        meta = metadata[key]
        rows.append(dict(
            Series=key,
            Source=meta["source"],
            Ticker=meta.get("ticker", ""),
            First_date=series.index.min().date(),
            Last_date=series.index.max().date(),
            Observations=len(series),
            Retrieval_UTC=meta["retrieval_timestamp"],
            Cache=meta.get("cache_status", ""),
            Identity_evidence=meta["identity_evidence"],
            SHA256=meta.get("sha256", ""),
        ))
    return pd.DataFrame(rows)
