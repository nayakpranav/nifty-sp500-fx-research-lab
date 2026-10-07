"""Bounded backward-as-of valuation; no future filling or daily inner joins."""

import numpy as np
import pandas as pd
from .config import REQUIRED
from .currency import convert_levels
from .validation import DataError


def align_daily(raw, tolerance_days=7):
    """Union of sessions within usable raw bounds, backward fill ≤ tolerance.

    Dates represent a research valuation cutoff, not simultaneously executable
    prices: Indian and US closes are asynchronous. Never backfill from the future.
    Return observation-date audit alongside levels. Unusable interior rows stay NaN.
    """
    start = max(raw[k].index.min() for k in REQUIRED)
    end = min(raw[k].index.max() for k in REQUIRED)
    if start >= end:
        raise DataError("Required series have no comparable history.")
    dates = pd.DatetimeIndex(sorted(set().union(*(s.index for s in raw.values()))))
    dates = dates[(dates >= start) & (dates <= end)]
    values, source_dates = {}, {}
    for key in REQUIRED:
        source = raw[key]
        loc = source.index.get_indexer(
            dates, method="pad", tolerance=pd.Timedelta(days=tolerance_days)
        )
        valid = loc >= 0
        values[key] = pd.Series(float("nan"), index=dates)
        values[key].iloc[valid] = source.iloc[loc[valid]].to_numpy()
        audit = pd.Series(pd.NaT, index=dates, dtype="datetime64[ns]")
        audit.iloc[valid] = source.index[loc[valid]].to_numpy()
        source_dates[key] = audit
    levels = convert_levels(pd.DataFrame(values))
    audit = pd.DataFrame(source_dates)
    usable = levels.dropna()
    if len(usable) < 2:
        raise DataError("Fewer than two bounded common valuation cutoffs.")
    levels = levels.loc[usable.index[0] : usable.index[-1]]
    audit = audit.loc[levels.index]
    if levels.isna().any().any():
        raise DataError(
            "Unfillable interior gap: upload complete sources or revise tolerance "
            "after inspection. No return will bridge an unknown gap."
        )
    levels.index.name = audit.index.name = "Date"
    return levels, audit


def period_levels(
    daily: pd.DataFrame, frequency: str = "monthly", include_partial: bool = False
) -> pd.DataFrame:
    """Final valid cutoff per calendar period; omit partial boundary periods.

    As-of daily panel retains each source's final available observation. Period
    labels are calendar month/year ends; actual daily cutoffs remain in audit.
    CAGR on these snapshots uses elapsed calendar-label days, explicitly.
    """
    if frequency == "daily":
        return daily.copy()
    if frequency not in ("monthly", "annual"):
        raise ValueError("Frequency must be daily, monthly or annual.")
    freq = "M" if frequency == "monthly" else "Y"
    group = daily.index.to_period(freq)
    out = daily.groupby(group).last()
    out.index = out.index.to_timestamp(how="end").normalize()
    start, end = daily.index[0], daily.index[-1]
    if not include_partial:
        expected_cutoffs = pd.DatetimeIndex(
            [pd.offsets.BDay().rollback(d) for d in out.index]
        )
        out = out[(expected_cutoffs <= end) & (out.index >= start)]
    elif len(out) and out.index[-1] > end:
        out.index = pd.DatetimeIndex(list(out.index[:-1]) + [end])
    return out


def calendar_returns(daily, include_ytd=False, now=None, perspective="Indian investor"):
    """Previous completed year-end to next year-end, with explicit partial labels."""
    year = period_levels(daily, "annual", include_partial=True)
    result = year.pct_change(fill_method=None).iloc[1:].copy()
    today = pd.Timestamp(now or pd.Timestamp.now(tz="UTC").date())
    final_business_cutoffs = pd.DatetimeIndex(
        [pd.offsets.BDay().rollback(pd.Timestamp(d.year, 12, 31)) for d in result.index]
    )
    complete = (final_business_cutoffs <= daily.index[-1]) & (
        result.index.year < today.year
    )
    labels = [
        str(d.year) if done else f"{d.year} YTD"
        for d, done in zip(result.index, complete)
    ]
    result.index = pd.Index(labels, name="Year")
    if not include_ytd:
        result = result.loc[complete]
    from .lenses import lens_pair, home_currency
    nifty, sp = lens_pair(perspective)

    result["Winner"] = [
        f"S&P 500 · {home_currency(perspective)}" if x > y + 1e-12 else f"NIFTY 50 · {home_currency(perspective)}" if x < y - 1e-12 else "Tie"
        for x, y in zip(result[sp], result[nifty])
    ]
    return result


def normalize(levels: pd.DataFrame, capital: float = 100.0) -> pd.DataFrame:
    """Rebase selected series to identical capital on their common first cutoff."""
    if not np.isfinite(capital) or capital <= 0 or levels.empty:
        raise ValueError("Positive capital and a nonempty sample are required.")
    return levels.div(levels.iloc[0]).mul(capital)
