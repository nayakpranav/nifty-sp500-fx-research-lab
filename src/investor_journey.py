"""Home-currency investment accounting from the existing aligned level panel."""
from dataclasses import dataclass
import numpy as np
from .config import NIFTY, SP, FX, EURUSD, EURINR
from .interpretation import lens_statistics
from .lenses import canonical_lens, home_currency, lens_pair


@dataclass(frozen=True)
class InvestmentRoute:
    name: str
    native_currency: str
    steps: tuple
    initial_native: float
    final_native: float
    final_home: float
    native_cagr: float
    home_cagr: float
    fx_name: str
    fx_cagr: float
    fx_log: float
    fx_gap: float


def lens_definition(perspective):
    home = home_currency(perspective)
    extra = " For someone saving in Germany or elsewhere in the euro area, the final EUR outcome matters even when the Indian market's headline INR return is high." if home == "EUR" else ""
    return (f"You earn or save in {home}, invest the same starting capital in either market, and ultimately measure wealth in {home}. "
            "The Investor Lens is your economic home currency, rather than an intermediate conversion route." + extra)


def investor_journey(result, perspective, capital=100):
    lens = canonical_lens(perspective)
    if not np.isfinite(capital) or capital <= 0:
        raise ValueError("Starting capital must be positive and finite.")
    home = home_currency(lens)
    panel = result['daily']
    first, last = panel.iloc[0], panel.iloc[-1]
    stats = lens_statistics(result, lens, capital)
    rates = stats['rates']
    a, b = lens_pair(lens)
    # Native currency units purchased per one unit of home currency.
    conversions = {'INR': (1., 1. / first[FX]), 'USD': (first[FX], 1.),
                   'EUR': (first[EURINR], first[EURUSD])}[home]
    definitions = [("NIFTY 50 TRI", "INR", NIFTY, a, conversions[0],
                    None if home == 'INR' else FX if home == 'USD' else EURINR, -1),
                   ("S&P 500 Total Return", "USD", SP, b, conversions[1],
                    FX if home == 'INR' else None if home == 'USD' else EURUSD,
                    1 if home == 'INR' else -1)]
    routes = []
    for name, native, key, adjusted, conversion, fx, sign in definitions:
        initial = float(capital * conversion)
        final = float(initial * last[key] / first[key])
        ending = float(capital * last[adjusted] / first[adjusted])
        steps = (f'{home} savings', name, f'{home} wealth') if native == home else (
            f'{home} savings', f'Convert {home} → {native}', name,
            f'Convert final {native} → {home}', f'{home} wealth')
        routes.append(InvestmentRoute(name, native, steps, initial, final, ending,
            float(rates[key]), float(rates[adjusted]),
            {FX: 'USD/INR · INR per USD', EURINR: 'EUR/INR · INR per EUR', EURUSD: 'EUR/USD · USD per EUR'}.get(fx, 'No currency translation'),
            float(rates[fx]) if fx else 0., float(sign * np.log1p(rates[fx])) if fx else 0.,
            float(rates[adjusted] - rates[key])))
    delta = routes[0].final_home - routes[1].final_home
    winner = 'NIFTY 50' if delta > capital * 1e-12 else 'S&P 500' if delta < -capital * 1e-12 else 'Tie'
    return dict(lens=lens, home=home, capital=float(capital), start=panel.index[0], end=panel.index[-1],
        definition=lens_definition(lens), routes=tuple(routes), winner=winner,
        wealth_difference=float(delta), absolute_wealth_difference=float(abs(delta)),
        percentage_wealth_difference=float(delta / routes[1].final_home),
        cagr_difference=float(routes[0].home_cagr - routes[1].home_cagr))
