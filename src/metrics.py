"""Date-based growth, drawdown episodes and descriptive monthly risk."""

import numpy as np
import pandas as pd
from .config import DAYS_PER_YEAR
from .transforms import period_levels, calendar_returns


def cagr(start_value, end_value, start_date, end_date):
    """Annualized growth using actual elapsed days / 365.2425."""
    years = (pd.Timestamp(end_date) - pd.Timestamp(start_date)).days / DAYS_PER_YEAR
    if (
        not np.isfinite(years)
        or years <= 0
        or not np.isfinite(np.asarray(start_value)).all()
        or not np.isfinite(np.asarray(end_value)).all()
        or np.any(np.asarray(start_value) <= 0)
        or np.any(np.asarray(end_value) <= 0)
    ):
        raise ValueError("CAGR requires positive levels and increasing dates.")
    return (end_value / start_value) ** (1 / years) - 1


def drawdowns(levels: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """Underwater fractions relative to running high-water mark."""
    return levels / levels.cummax() - 1


def drawdown_episodes(series: pd.Series) -> pd.DataFrame:
    """Disjoint peak-to-recovery episodes; open durations are right-censored."""
    high, peak = series.iloc[0], series.index[0]
    active = None
    episodes = []
    for date, value in series.items():
        if value >= high:
            if active is not None:
                active["recovery"] = date
                active["underwater_days"] = (date - active["start"]).days
                active["recovery_days"] = (date - active["trough"]).days
                active["censored"] = False
                episodes.append(active)
                active = None
            high, peak = value, date
        else:
            depth = value / high - 1
            if active is None:
                active = dict(
                    start=peak,
                    trough=date,
                    depth=depth,
                    recovery=pd.NaT,
                    drawdown_days=(date - peak).days,
                )
            if depth < active["depth"]:
                active.update(
                    trough=date, depth=depth, drawdown_days=(date - peak).days
                )
    if active is not None:
        active.update(
            underwater_days=(series.index[-1] - active["start"]).days,
            recovery_days=(series.index[-1] - active["trough"]).days,
            censored=True,
        )
        episodes.append(active)
    columns = [
        "start",
        "trough",
        "depth",
        "recovery",
        "drawdown_days",
        "underwater_days",
        "recovery_days",
        "censored",
    ]
    return (
        pd.DataFrame(episodes, columns=columns)
        .sort_values("depth")
        .reset_index(drop=True)
    )


def risk_metrics(daily: pd.DataFrame, target_annual: float = 0.0) -> pd.DataFrame:
    """Monthly risk annualized by √12; Sortino uses mean excess / downside.

    MAR is an explicit annual target (default zero), not an inferred risk-free
    rate. Historical VaR is the 5% empirical quantile; ES is the mean at/below it.
    Daily drawdowns use bounded asynchronous valuation cutoffs.
    """
    if not np.isfinite(target_annual) or target_annual <= -1:
        raise ValueError(
            "Annual downside target must be finite and greater than -100%."
        )
    monthly = period_levels(daily)
    returns = monthly.pct_change(fill_method=None).dropna()
    annual = calendar_returns(daily).select_dtypes("number")
    target_month = (1 + target_annual) ** (1 / 12) - 1
    rows = []
    for name in daily.columns:
        r = returns[name]
        dd = drawdowns(daily[name])
        episodes = drawdown_episodes(daily[name])
        downside = np.sqrt(np.mean(np.minimum(r - target_month, 0) ** 2)) * np.sqrt(12)
        growth = cagr(
            daily[name].iloc[0], daily[name].iloc[-1], daily.index[0], daily.index[-1]
        )
        var = r.quantile(0.05)
        rows.append(
            dict(
                Series=name,
                CAGR=growth,
                Annualized_volatility=r.std(ddof=1) * np.sqrt(12),
                Downside_deviation=downside,
                MAR_annual=target_annual,
                Max_drawdown=dd.min(),
                Calmar=growth / abs(dd.min()) if dd.min() < 0 else np.nan,
                Sortino=(
                    (r.mean() - target_month) * 12 / downside
                    if downside > 0
                    else np.nan
                ),
                Ulcer_index=np.sqrt(np.mean(dd**2)),
                Skewness=r.skew(),
                Excess_kurtosis=r.kurt(),
                Best_year=annual[name].max(),
                Worst_year=annual[name].min(),
                Positive_years=(annual[name] > 0).mean(),
                Positive_months=(r > 0).mean(),
                Worst_month=r.min(),
                Best_month=r.max(),
                Historical_monthly_VaR05=var,
                Historical_monthly_ES05=r[r <= var].mean(),
                Longest_underwater_days=(
                    episodes.underwater_days.max() if len(episodes) else 0
                ),
                Monthly_observations=len(r),
                Complete_years=len(annual),
            )
        )
    return pd.DataFrame(rows).set_index("Series")
