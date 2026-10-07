"""One vocabulary for figures, tables, narration and human-facing exports."""
from .config import NIFTY, SP, FX, SP_INR, NIFTY_USD, EURUSD, EURINR, NIFTY_EUR, SP_EUR

DISPLAY_LABELS = {
    NIFTY: "NIFTY 50 TRI (INR · native)", SP: "S&P 500 TR (USD · native)",
    SP_INR: "S&P 500 TR (INR-adjusted)", NIFTY_USD: "NIFTY 50 TRI (USD-adjusted)",
    NIFTY_EUR: "NIFTY 50 TRI (EUR-adjusted)", SP_EUR: "S&P 500 TR (EUR-adjusted)",
    FX: "USD/INR (INR per USD)", EURUSD: "EUR/USD (USD per EUR)",
    EURINR: "EUR/INR (INR per EUR)",
    "NIFTY": "NIFTY 50 TRI CAGR · home currency", "SP_INR": "S&P 500 TR CAGR · home currency",
    "Difference": "S&P − NIFTY excess CAGR", "Winner": "Home-currency winner",
    "SP_wins": "S&P win fraction", "NIFTY_wins": "NIFTY win fraction", "Ties": "Tie fraction",
    "Equity_log": "Native equity log return", "Currency_log": "Home-currency FX log contribution",
    "Total_log": "Home-currency total log return", "FX_annual_log": "Annualized FX log contribution",
    "Equity_annual_log": "Annualized native equity log return", "Total_annual_log": "Annualized home-currency log return",
}


def display_label(value):
    return DISPLAY_LABELS.get(value, str(value).replace("_", " "))


def display_table(frame):
    """Rename a copy; quantitative values and internal keys remain untouched."""
    out = frame.copy()
    out.columns = [display_label(c) for c in out.columns]
    if getattr(out.index, "nlevels", 1) > 1:
        out.index = out.index.map(lambda row: tuple(display_label(x) for x in row))
    else:
        out.index = out.index.map(lambda x: DISPLAY_LABELS.get(x, x))
    for column in ("Series", "series"):
        if column in out:
            out[column] = out[column].map(display_label)
    return out
