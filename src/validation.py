"""Fail closed on bad observations or unverified benchmark identity."""

import numpy as np
import pandas as pd
from .config import NIFTY, SP, FX, EURUSD


class DataError(ValueError):
    """An ordinary data failure with an actionable message."""


def validate_series(series, metadata, now=None, stale_days=14):
    """Inspect raw data before sorting, dropping, filling or calculating returns."""
    rows = []

    def issue(check, severity, detail):
        rows.append(
            dict(series=series.name, check=check, status=severity, detail=detail)
        )

    name = series.name
    issue("observations", "PASS" if len(series) >= 2 else "FAIL", str(len(series)))
    absent = metadata.get("missing_source_observations", 0)
    if absent:
        issue(
            "provider absent observations",
            "WARNING",
            f"{absent} explicit missing/no-quote records; dates retained in provenance. "
            "Bounded as-of alignment applies later; populated corrupt records are not removed.",
        )
    if not isinstance(series.index, pd.DatetimeIndex):
        issue("timestamps", "FAIL", "A DatetimeIndex is required.")
        return pd.DataFrame(rows)
    for check, bad, detail in (
        ("duplicate sessions", series.index.has_duplicates, "Duplicate calendar dates"),
        ("ordering", not series.index.is_monotonic_increasing, "Dates must increase"),
        (
            "missing",
            series.isna().any() or series.index.isna().any(),
            "Missing values or dates",
        ),
        (
            "positive finite levels",
            not np.isfinite(series.to_numpy(dtype=float)).all() or (series <= 0).any(),
            "Levels must be finite and strictly positive",
        ),
    ):
        issue(check, "FAIL" if bad else "PASS", detail if bad else "Valid")
    expected_currency = "USD" if name in (SP, EURUSD) else "INR"
    issue(
        "currency",
        "PASS" if metadata.get("currency") == expected_currency else "FAIL",
        str(metadata.get("currency")),
    )
    if name in (NIFTY, SP):
        correct_name = (
            "NIFTY 50" in metadata.get("index_name", "").upper()
            if name == NIFTY
            else "S&P 500" in metadata.get("index_name", "").upper()
        )
        identity = correct_name and metadata.get("return_type") == "total_return"
        identity &= metadata.get("identity_evidence") in (
            "official_endpoint",
            "provider_metadata",
            "authoritative_csv_attestation",
            "synthetic",
        )
        identity &= metadata.get("ticker") not in ("^NSEI", "^GSPC")
        issue(
            "total-return identity",
            "PASS" if identity else "FAIL",
            metadata.get(
                "identity_evidence", "No identity evidence; price indices prohibited"
            ),
        )
        if metadata.get("identity_evidence") == "authoritative_csv_attestation":
            issue(
                "CSV provenance boundary",
                "WARNING",
                "Header, source, checksum and declaration checked; numbers cannot prove TRI identity. "
                "The uploader must retain the original official export.",
            )
    if name == FX:
        ok = metadata.get("units") == "INR per USD" and metadata.get("base") == "USD"
        ok &= metadata.get("quote") == "INR"
        issue("FX direction", "PASS" if ok else "FAIL", str(metadata.get("units")))
        issue(
            "FX magnitude",
            "PASS" if series.between(5, 250).all() else "FAIL",
            "Sanity bound 5–250 INR/USD; a reciprocal cannot pass. Not identity proof.",
        )
    if name == EURUSD:
        ok = metadata.get("units") == "USD per EUR" and metadata.get("base") == "EUR"
        ok &= metadata.get("quote") == "USD" and metadata.get("ticker") == "DEXUSEU"
        ok &= metadata.get("direction_evidence") == "U.S. Dollars to One Euro"
        issue("FX direction", "PASS" if ok else "FAIL", str(metadata.get("units")))
        issue("FX magnitude", "PASS" if series.between(0.4, 2.5).all() else "FAIL",
              "Sanity bound 0.4–2.5 USD/EUR; verified provider units establish direction.")
    if len(series) > 1:
        gaps = series.index.to_series().diff().dt.days
        issue(
            "daily frequency",
            "FAIL" if gaps.median() > 4 else "PASS",
            f"Median spacing {gaps.median():.1f} days; daily sources required",
        )
        issue(
            "long gaps",
            "WARNING" if gaps.max() > 10 else "PASS",
            f"Maximum spacing {gaps.max():.0f} days",
        )
        extreme = series.pct_change(fill_method=None).abs() > (
            0.08 if name in (FX, EURUSD) else 0.25
        )
        issue(
            "extreme daily moves",
            "WARNING" if extreme.any() else "PASS",
            f"{int(extreme.sum())} flagged; inspect before interpretation",
        )
        span = (series.index[-1] - series.index[0]).days / 365.2425
        issue(
            "history",
            "WARNING" if span < 20 else "PASS",
            f"{span:.2f} years; unavailable holding periods remain empty",
        )
        today = pd.Timestamp(now or pd.Timestamp.now(tz="UTC").date()).tz_localize(None)
        age = (today.normalize() - series.index[-1]).days
        issue(
            "stale final observation",
            "WARNING" if age > stale_days else "PASS",
            f"{age} days old",
        )
        issue(
            "future observations",
            "FAIL" if series.index[-1] > today else "PASS",
            "Source dates compared with execution date",
        )
    return pd.DataFrame(rows)


def require_valid(report):
    """Stop affected analysis on critical validation failures."""
    failures = report[report.status == "FAIL"]
    if len(failures):
        raise DataError("Validation failed:\n" + failures.to_string(index=False))
