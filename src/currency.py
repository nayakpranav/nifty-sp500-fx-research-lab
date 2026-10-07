"""Exact currency conversion and additive log attribution."""

import numpy as np
import pandas as pd
from .config import NIFTY, SP, FX, SP_INR, NIFTY_USD, EURUSD, EURINR, NIFTY_EUR, SP_EUR


def convert_levels(levels: pd.DataFrame) -> pd.DataFrame:
    """USDINR means INR per USD; raw products are rebased for display."""
    result = levels.copy()
    result[SP_INR] = result[SP] * result[FX]
    result[NIFTY_USD] = result[NIFTY] / result[FX]
    if EURUSD in result:
        result[EURINR] = result[FX] * result[EURUSD]
        result[NIFTY_EUR] = result[NIFTY] / result[EURINR]
        result[SP_EUR] = result[SP] / result[EURUSD]
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
    if EURUSD in levels:
        errors.update(
            EURINR_cross=float(np.max(np.abs(levels[EURINR] / (levels[FX] * levels[EURUSD]) - 1))),
            NIFTY_EUR_gross=float(np.max(np.abs(1 + r[NIFTY_EUR] - (1 + r[NIFTY]) / (1 + r[EURINR])))),
            SP_EUR_gross=float(np.max(np.abs(1 + r[SP_EUR] - (1 + r[SP]) / (1 + r[EURUSD])))),
            NIFTY_EUR_log=float(np.max(np.abs(np.log1p(r[NIFTY_EUR]) - np.log1p(r[NIFTY]) + np.log1p(r[EURINR])))),
            SP_EUR_log=float(np.max(np.abs(np.log1p(r[SP_EUR]) - np.log1p(r[SP]) + np.log1p(r[EURUSD])))),
        )
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


def lens_attribution(returns, perspective):
    """Exact log attribution for each foreign investment in the selected lens."""
    from .lenses import home_currency
    home = home_currency(perspective)
    specs = {"INR": [(SP_INR, SP, FX, 1)], "USD": [(NIFTY_USD, NIFTY, FX, -1)],
             "EUR": [(NIFTY_EUR, NIFTY, EURINR, -1), (SP_EUR, SP, EURUSD, -1)]}
    outputs = {}
    for translated, native, fx, sign in specs[home]:
        out = returns[[native, fx, translated]].copy()
        out["Equity_log"] = np.log1p(returns[native])
        out["Currency_log"] = sign * np.log1p(returns[fx])
        out["Total_log"] = np.log1p(returns[translated])
        out["CAGR_difference"] = returns[translated] - returns[native]
        outputs[translated] = out
    return outputs
