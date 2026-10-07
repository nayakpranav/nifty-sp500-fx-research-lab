"""Deterministic narratives from calculated statistics, shared by UI and report."""
from dataclasses import dataclass
import numpy as np
from .config import NIFTY, SP, FX, EURINR, EURUSD
from .lenses import lens_pair, canonical_lens, home_currency, currency_symbol
from .rolling import excess_summary


@dataclass(frozen=True)
class InterpretationCard:
    title: str
    highlight: str
    text: str
    caution: bool = False


def lens_statistics(result, perspective, capital=100):
    daily = result["daily"]
    a, b = lens_pair(perspective)
    years = (daily.index[-1] - daily.index[0]).days / 365.2425
    growth = daily.iloc[-1] / daily.iloc[0]
    rates = growth ** (1 / years) - 1
    home = home_currency(perspective)
    target, native, fx, sign = ((b, SP, FX, 1) if home == "INR" else
                              (a, NIFTY, FX if home == "USD" else EURINR, -1))
    return dict(nifty_cagr=float(rates[a]), sp_cagr=float(rates[b]),
        nifty_wealth=float(capital * growth[a]), sp_wealth=float(capital * growth[b]),
        local_cagr=float(rates[native]), translated_cagr=float(rates[target]),
        fx_cagr=float(rates[fx]), fx_log=float(sign * np.log1p(rates[fx])),
        cagr_gap=float(rates[target] - rates[native]), fx=fx, target=target,
        nifty_required_local=float((1 + rates[b]) * (1 + rates[fx]) - 1) if home != "INR" else None,
        rates=rates)


def build_overview_interpretation(result, horizon=10, perspective="INR-based investor", capital=100):
    lens = canonical_lens(perspective)
    home = home_currency(lens)
    a, b = lens_pair(lens)
    s = lens_statistics(result, lens, capital)
    symbol = currency_symbol(lens)
    difference = s["sp_cagr"] - s["nifty_cagr"]
    leader = "S&P 500" if difference > 1e-12 else "NIFTY 50" if difference < -1e-12 else "Neither investment"
    lead_text = f"{leader} finished ahead by {abs(difference)*100:.2f} percentage points of CAGR." if abs(difference) > 1e-12 else "Their CAGRs were equal within numerical tolerance."
    daily = result["daily"]
    cards = [InterpretationCard("01 · Performance", f"{abs(difference)*100:.2f} pp CAGR gap",
        f"From {daily.index[0]:%d %b %Y} to {daily.index[-1]:%d %b %Y}, NIFTY returned {s['nifty_cagr']:.2%} annually in {home}, versus {s['sp_cagr']:.2%} for the S&P. {lead_text} "
        f"Equal {symbol}{capital:,.0f} starting amounts became {symbol}{s['nifty_wealth']:,.2f} and {symbol}{s['sp_wealth']:,.2f}, respectively.")]
    effect = "tailwind" if s["fx_log"] > 1e-12 else "drag" if s["fx_log"] < -1e-12 else "neutral effect"
    move = "depreciated" if s["fx_cagr"] > 0 else "appreciated" if s["fx_cagr"] < 0 else "was unchanged"
    if home == "INR":
        text = (f"The S&P's native USD CAGR was {s['local_cagr']:.2%}; translating back to INR gave {s['translated_cagr']:.2%}. "
                f"The rupee {move} against USD as USD/INR changed by {s['fx_cagr']:.2%} annually.")
    else:
        text = (f"{home} savings → INR → NIFTY → {home}: local INR CAGR was {s['local_cagr']:.2%}, while converting final wealth back to {home} gave {s['translated_cagr']:.2%}. "
                f"The rupee {move} against {home}; INR per {home} changed by {s['fx_cagr']:.2%} annually. "
                f"To match the S&P's {s['sp_cagr']:.2%} {home} CAGR with this FX path, NIFTY needed {s['nifty_required_local']:.2%} local INR CAGR "
                f"({(s['nifty_required_local']-s['sp_cagr'])*100:+.2f} pp above that home-currency benchmark).")
        if home == "EUR":
            sp_log = -float(np.log1p(s["rates"][EURUSD]))
            text += f" The S&P's native USD CAGR was {s['rates'][SP]:.2%}; EUR translation added {sp_log*100:+.2f} annual log percentage points."
    text += (f" The arithmetic CAGR gap is {s['cagr_gap']*100:+.2f} pp; the exact FX contribution is {s['fx_log']*100:+.2f} annual log percentage points. "
             "These are different measures; only log contributions add exactly.")
    cards.append(InterpretationCard("02 · Currency effect", f"{s['fx_log']*100:+.2f} log pp · {effect}", text))
    r = result["rolling"][horizon]
    e = excess_summary(r, lens)
    if len(r):
        holding = (f"Across {int(e.Windows):,} overlapping {horizon}-year monthly windows in {home}, S&P won {e.SP_wins:.1%}, "
            f"NIFTY won {e.NIFTY_wins:.1%}, and ties were {e.Ties:.1%}. Median CAGRs were {r[a].median():.2%} and {r[b].median():.2%} "
            f"for NIFTY and S&P; the median paired S&P advantage was {e.Median_advantage*100:+.2f} pp.")
        highlight = f"{e.SP_wins:.1%} S&P historical win fraction"
    else:
        holding = f"This sample is too short for complete {horizon}-year windows. No win fraction or holding-period conclusion is available."
        highlight = "Insufficient history"
    cards.append(InterpretationCard("03 · Holding-period consistency", highlight, holding))
    risk = result["risk"]
    cards.append(InterpretationCard("04 · Risk", f"{risk.loc[a,'Max_drawdown']:.1%} / {risk.loc[b,'Max_drawdown']:.1%} maximum drawdown",
        f"In {home}, NIFTY's deepest peak-to-trough loss was {risk.loc[a,'Max_drawdown']:.2%}, versus {risk.loc[b,'Max_drawdown']:.2%} for the S&P. "
        f"Monthly returns imply annualized volatility of {risk.loc[a,'Annualized_volatility']:.2%} and {risk.loc[b,'Annualized_volatility']:.2%}, respectively. "
        "These use converted wealth paths; exchange rates can change a foreign investor's losses and variability."))
    cards.append(InterpretationCard("Important context", "Historical evidence · no forecast",
        "Windows share observations and do not represent independent trials or future probabilities. Start dates, endpoints and FX regimes affect results. "
        "Both indices include reinvested dividends; valuations use bounded asynchronous closes. Taxes, fees, tracking error and remittance costs are excluded. This is research, not a personal allocation recommendation.", True))
    return cards
