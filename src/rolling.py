"""Calendar-offset rolling windows with explicit backward tolerance."""

import numpy as np
import pandas as pd
from .config import DAYS_PER_YEAR, NIFTY, SP_INR, HORIZONS
from .metrics import cagr


def window_indices(index, horizon, tolerance_days=7):
    """At each cutoff choose last cutoff ≤ t−H calendar years, within tolerance."""
    if horizon <= 0:
        raise ValueError("Horizon must be positive.")
    targets = pd.DatetimeIndex([d - pd.DateOffset(years=int(horizon)) for d in index])
    # Monthly snapshots use month-end anniversaries. February 28 in a
    # nonleap year must match February 29 in a leap year, never January 31.
    if len(index) and index.is_month_end.all():
        targets = targets + pd.offsets.MonthEnd(0)
    starts = index.get_indexer(
        targets, method="pad", tolerance=pd.Timedelta(days=tolerance_days)
    )
    ends = np.flatnonzero(starts >= 0)
    return starts[ends], ends


def rolling_cagr(
    levels: pd.DataFrame, horizon: int, tolerance_days: int = 7
) -> pd.DataFrame:
    """Every feasible cutoff, including actual matched window dates."""
    starts, ends = window_indices(levels.index, horizon, tolerance_days)
    out = pd.DataFrame(index=levels.index[ends], columns=levels.columns, dtype=float)
    if len(ends):
        years = (
            levels.index[ends] - levels.index[starts]
        ).days.to_numpy() / DAYS_PER_YEAR
        out.loc[:, :] = (levels.to_numpy()[ends] / levels.to_numpy()[starts]) ** (
            1 / years[:, None]
        ) - 1
    out["Start_date"] = levels.index[starts]
    out["End_date"] = levels.index[ends]
    out.index.name = "Date"
    return out


def summary(rolling: pd.DataFrame) -> pd.DataFrame:
    """Descriptive window distribution; overlapping windows are not independent."""
    numeric = rolling.select_dtypes("number")
    rows = []
    for name, r in numeric.items():
        rows.append(
            dict(
                Series=name,
                Windows=r.count(),
                Mean=r.mean(),
                Geometric_mean_CAGR=np.expm1(np.log1p(r).mean()) if len(r) else np.nan,
                Median=r.median(),
                Std=r.std(),
                Min=r.min(),
                Max=r.max(),
                P05=r.quantile(0.05),
                P10=r.quantile(0.10),
                P25=r.quantile(0.25),
                P75=r.quantile(0.75),
                P90=r.quantile(0.90),
                P95=r.quantile(0.95),
                IQR=r.quantile(0.75) - r.quantile(0.25),
                Probability_positive=(r > 0).mean(),
            )
        )
    return pd.DataFrame(rows).set_index("Series")


def excess_summary(
    rolling: pd.DataFrame, perspective: str = "Indian investor"
) -> pd.Series:
    """Paired win, loss and tie probabilities plus signed and conditional advantages."""
    from .config import SP, NIFTY_USD

    a, b = (SP_INR, NIFTY) if perspective == "Indian investor" else (SP, NIFTY_USD)
    delta = (rolling[a] - rolling[b]).dropna()
    delta = delta.mask(delta.abs() <= 1e-12, 0.0)
    return pd.Series(
        {
            "Windows": len(delta),
            "SP_wins": (delta > 0).mean(),
            "NIFTY_wins": (delta < 0).mean(),
            "Ties": (delta == 0).mean(),
            "Mean_advantage": delta.mean(),
            "Median_advantage": delta.median(),
            "SP_conditional_advantage": delta[delta > 0].mean(),
            "NIFTY_conditional_advantage": -delta[delta < 0].mean(),
            "Worst_SP_relative": delta.min(),
            "Best_SP_relative": delta.max(),
        }
    )


def probability_curve(levels, tolerance_days=7, perspective="Indian investor"):
    """Historical paired probabilities at all integer feasible holding horizons."""
    maximum = int((levels.index[-1] - levels.index[0]).days / DAYS_PER_YEAR)
    return pd.DataFrame(
        {
            h: excess_summary(rolling_cagr(levels, h, tolerance_days), perspective)
            for h in range(1, maximum + 1)
        }
    ).T.rename_axis("Horizon")


def trailing_cagr(levels, endpoint=None):
    """First available cutoff in each year to selected last available endpoint."""
    end = (
        levels.index[-1]
        if endpoint is None
        else levels.index[levels.index <= pd.Timestamp(endpoint)][-1]
    )
    sample = levels.loc[:end]
    starts = sample.groupby(sample.index.year).head(1)
    rows = []
    for date, row in starts.iterrows():
        if date >= end:
            continue
        values = cagr(row, sample.loc[end], date, end).to_dict()
        values.update(Start_year=date.year, Start_date=date, End_date=end)
        values["Difference"] = values[SP_INR] - values[NIFTY]
        rows.append(values)
    return pd.DataFrame(rows)


def matrices(levels, horizons=HORIZONS, tolerance_days=7):
    """One first cutoff per start year; hold to backward-as-of anniversary.

    Endpoint matrix holds first cutoff in a starting year to final cutoff in
    ending year. Partial terminal year is explicitly labelled with actual date.
    Full detail tables drive hover text and exports.
    """
    starts = levels.groupby(levels.index.year).head(1)
    ends = levels.groupby(levels.index.year).tail(1)
    holding_rows, endpoint_rows = [], []
    for start, initial in starts.iterrows():
        for horizon in horizons:
            target = start + pd.DateOffset(years=horizon)
            # Never shorten an unavailable full horizon to the current endpoint.
            if target > levels.index[-1]:
                continue
            i = levels.index.get_indexer(
                [target], method="pad", tolerance=pd.Timedelta(days=tolerance_days)
            )[0]
            if i < 0:
                continue
            end = levels.index[i]
            vals = cagr(initial, levels.iloc[i], start, end)
            holding_rows.append(
                dict(
                    Start_year=start.year,
                    Horizon=f"{horizon}Y",
                    Start_date=start,
                    End_date=end,
                    NIFTY=vals[NIFTY],
                    SP_INR=vals[SP_INR],
                    Difference=vals[SP_INR] - vals[NIFTY],
                )
            )
        for end, final in ends.iterrows():
            if end.year <= start.year:
                continue
            vals = cagr(initial, final, start, end)
            label = (
                str(end.year)
                if pd.offsets.BDay().rollback(pd.Timestamp(end.year, 12, 31))
                <= levels.index[-1]
                else f"{end.year} YTD"
            )
            endpoint_rows.append(
                dict(
                    Start_year=start.year,
                    End_year=label,
                    Start_date=start,
                    End_date=end,
                    NIFTY=vals[NIFTY],
                    SP_INR=vals[SP_INR],
                    Difference=vals[SP_INR] - vals[NIFTY],
                )
            )
    return pd.DataFrame(holding_rows), pd.DataFrame(endpoint_rows)


def non_overlapping(levels, horizon, phase=0, tolerance_days=7):
    """Greedy disjoint holding intervals; a shared boundary level is allowed.

    phase selects a starting cutoff, enabling sensitivity to the partition origin.
    Windows are descriptive and may still share longer-lived regime dependence.
    """
    windows = rolling_cagr(levels, horizon, tolerance_days)
    boundary = levels.index[min(phase, len(levels) - 1)]
    selected = []
    for end, row in windows.iterrows():
        if row.Start_date >= boundary:
            selected.append(end)
            boundary = end
    return windows.loc[selected]
