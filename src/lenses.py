"""Explicit home-currency pairs shared by analytics and presentation."""
from .config import NIFTY, SP, SP_INR, NIFTY_USD, NIFTY_EUR, SP_EUR

LENSES = ("INR-based investor", "USD-based investor", "EUR-based investor")
ALIASES = {"Indian investor": LENSES[0], "US investor": LENSES[1]}
PAIRS = {LENSES[0]: (NIFTY, SP_INR), LENSES[1]: (NIFTY_USD, SP),
         LENSES[2]: (NIFTY_EUR, SP_EUR)}


def canonical_lens(lens):
    value = ALIASES.get(lens, lens)
    if value not in PAIRS:
        raise ValueError(f"Unknown investor lens: {lens}")
    return value


def lens_pair(lens):
    """Return NIFTY then S&P in the same home currency; never silently default."""
    return PAIRS[canonical_lens(lens)]


def home_currency(lens):
    return canonical_lens(lens)[:3]


def currency_symbol(lens):
    return {"INR": "₹", "USD": "$", "EUR": "€"}[home_currency(lens)]
