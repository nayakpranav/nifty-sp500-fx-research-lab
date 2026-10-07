"""Paired moving-block bootstrap and descriptive diversification diagnostics."""

import numpy as np
import pandas as pd
from .config import NIFTY, SP, FX, SP_INR, NIFTY_USD, DAYS_PER_YEAR
from .transforms import period_levels
from .rolling import window_indices

PAIRS = ((NIFTY, SP), (NIFTY, SP_INR), (SP, FX))


def correlations(daily):
    """Daily cutoffs are asynchronous; monthly estimates are primary."""
    daily_r = daily.pct_change(fill_method=None).dropna()
    monthly_r = period_levels(daily).pct_change(fill_method=None).dropna()
    point = pd.DataFrame(
        {"Daily_asof": daily_r.corr().stack(), "Monthly": monthly_r.corr().stack()}
    )
    curves = {}
    for n in (12, 36, 60):
        curves[n] = pd.DataFrame(
            {
                f"{a} vs {b}": monthly_r[a].rolling(n, min_periods=n).corr(monthly_r[b])
                for a, b in PAIRS
            }
        )
    return point, curves


def rolling_volatility(daily, years=1):
    """Monthly volatility, full 12H observations, annualized by √12."""
    r = period_levels(daily).pct_change(fill_method=None)
    return r[[NIFTY, SP_INR]].rolling(12 * years, min_periods=12 * years).std(
        ddof=1
    ) * np.sqrt(12)


def block_bootstrap(
    levels,
    horizon=10,
    frequency="monthly",
    block_length=12,
    replications=5000,
    seed=42,
    confidence=(0.90, 0.95),
    tolerance_days=7,
    perspective="Indian investor",
):
    """Moving blocks of paired primitive log returns; reconstruct entire paths.

    All assets/FX share resampled indices, preserving within-block serial and
    cross-asset dependence. Non-circular blocks truncate at sample end. Rebuilt
    synthetic paths use the original calendar grid, so rolling CAGR uses actual
    elapsed dates. Percentile intervals target the mean/median rolling excess,
    historical win fraction and terminal H-year CAGR difference. No iid t-test.
    Conditional on stationarity; structural regimes and small samples limit CIs.
    """
    if frequency not in ("daily", "monthly"):
        raise ValueError("Bootstrap frequency must be daily or monthly.")
    if replications < 20:
        raise ValueError(
            "At least 20 replications are required; use 5000 for research."
        )
    if any(not 0 < c < 1 for c in confidence):
        raise ValueError("Confidence levels must lie strictly between zero and one.")
    sample = period_levels(levels, frequency)
    log = np.log(sample[[NIFTY, SP, FX]]).diff().iloc[1:].to_numpy()
    n = len(log)
    if not 1 <= block_length <= n:
        raise ValueError("Block length must lie between 1 and sample return count.")
    starts, ends = window_indices(sample.index, horizon, tolerance_days)
    if len(ends) == 0:
        return (
            pd.DataFrame(),
            pd.DataFrame(),
            {"warning": "Insufficient history for selected horizon."},
        )
    years = (sample.index[ends] - sample.index[starts]).days.to_numpy() / DAYS_PER_YEAR
    primitive = (
        np.column_stack([log[:, 0], log[:, 1] + log[:, 2]])
        if perspective == "Indian investor"
        else np.column_stack([log[:, 0] - log[:, 2], log[:, 1]])
    )
    cumulative = np.vstack([np.zeros(2), primitive.cumsum(axis=0)])
    original = np.expm1((cumulative[ends] - cumulative[starts]) / years[:, None])
    delta = original[:, 1] - original[:, 0]
    estimates = [delta.mean(), np.median(delta), (delta > 1e-12).mean(), delta[-1]]
    names = [
        "Mean_excess_CAGR",
        "Median_excess_CAGR",
        "Probability_SP_wins",
        "Terminal_H_CAGR_difference",
    ]
    rng = np.random.default_rng(seed)
    simulated = np.empty((replications, 4))
    blocks = int(np.ceil(n / block_length))
    offsets = np.arange(block_length)
    for first in range(0, replications, 32):
        count = min(32, replications - first)
        origins = rng.integers(0, n - block_length + 1, size=(count, blocks))
        indices = (origins[:, :, None] + offsets).reshape(count, -1)[:, :n]
        paths = np.concatenate(
            [np.zeros((count, 1, 2)), primitive[indices].cumsum(axis=1)], axis=1
        )
        growth = np.expm1((paths[:, ends] - paths[:, starts]) / years[None, :, None])
        excess = growth[:, :, 1] - growth[:, :, 0]
        simulated[first : first + count] = np.column_stack(
            [
                excess.mean(axis=1),
                np.median(excess, axis=1),
                (excess > 1e-12).mean(axis=1),
                excess[:, -1],
            ]
        )
    rows = []
    for j, name in enumerate(names):
        for coverage in confidence:
            alpha = (1 - coverage) / 2
            low, high = np.quantile(simulated[:, j], [alpha, 1 - alpha])
            rows.append(
                dict(
                    Statistic=name,
                    Estimate=estimates[j],
                    Confidence=coverage,
                    Lower=low,
                    Upper=high,
                    Replications=replications,
                    Horizon=horizon,
                    Frequency=frequency,
                    Block_length=block_length,
                    Seed=seed,
                    Perspective=perspective,
                )
            )
    metadata = dict(
        method="paired non-circular moving blocks of primitive log returns",
        return_count=n,
        valid_windows=len(delta),
        approximate_blocks=n / block_length,
        caveat="Conditional stationarity approximation; CIs are not forecasts or causal evidence.",
        warning=(
            "Few effective blocks / long horizon: treat intervals cautiously."
            if n / block_length < 20
            or horizon > (sample.index[-1] - sample.index[0]).days / DAYS_PER_YEAR / 3
            else ""
        ),
    )
    return pd.DataFrame(rows), pd.DataFrame(simulated, columns=names), metadata


def fx_regimes(daily):
    """Monthly conditional outcomes describe co-movement, not causal FX effects."""
    r = period_levels(daily).pct_change(fill_method=None).dropna()
    groups = pd.Series(
        np.where(
            r[FX] > 0,
            "INR depreciation",
            np.where(r[FX] < 0, "INR appreciation", "Unchanged"),
        ),
        index=r.index,
    )
    rows = []
    for label in groups.unique():
        subset = r[groups == label]
        rows.append(
            dict(
                Regime=label,
                Months=len(subset),
                SP_USD_mean=subset[SP].mean(),
                FX_mean=subset[FX].mean(),
                SP_INR_mean=subset[SP_INR].mean(),
                NIFTY_mean=subset[NIFTY].mean(),
                SP_win_fraction=(subset[SP_INR] > subset[NIFTY]).mean(),
            )
        )
    return pd.DataFrame(rows)
