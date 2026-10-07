"""Exact currency conversion and additive log attribution."""

import numpy as np
import pandas as pd
from .config import NIFTY, SP, FX, SP_INR, NIFTY_USD


def convert_levels(levels: pd.DataFrame) -> pd.DataFrame:
    """USDINR means INR per USD; raw products are rebased for display."""
    result = levels.copy()
    result[SP_INR] = result[SP] * result[FX]
    result[NIFTY_USD] = result[NIFTY] / result[FX]
    return result


def validate_identities(levels):
    """Check both period gross-return identities and log attribution numerically."""
    r = levels.pct_change(fill_method=None).dropna()
    if r.empty:
        raise ValueError("At least two complete observations are required.")
    errors = {
        "SP_INR_gross": np.max(np.abs(1 + r[SP_INR] - (1 + r[SP]) * (1 + r[FX]))),
        "NIFTY_USD_gross": np.max(
            np.abs(1 + r[NIFTY_USD] - (1 + r[NIFTY]) / (1 + r[FX]))
        ),
        "SP_INR_log": np.max(
            np.abs(np.log1p(r[SP_INR]) - np.log1p(r[SP]) - np.log1p(r[FX]))
        ),
    }
    if max(errors.values()) > 1e-10:
        raise ValueError("Currency identities failed: " + str(errors))
    return errors


def attribution(returns: pd.DataFrame) -> pd.DataFrame:
    """Arithmetic FX marginal effect includes interaction; logs add exactly."""
    out = returns[[SP, FX, SP_INR, NIFTY]].copy()
    out["Equity_log"] = np.log1p(out[SP])
    out["Currency_log"] = np.log1p(out[FX])
    out["Total_log"] = np.log1p(out[SP_INR])
    out["Interaction"] = out[SP] * out[FX]
    out["Currency_marginal_arithmetic"] = (1 + out[SP]) * out[FX]
    out["INR_move"] = np.where(
        out[FX] > 0,
        "INR depreciated (USD strengthened)",
        np.where(out[FX] < 0, "INR appreciated (USD weakened)", "Unchanged"),
    )
    return out
