"""Deterministic narratives from calculated statistics, shared by UI and report."""
from dataclasses import dataclass
import numpy as np
from .config import NIFTY, SP, FX, EURINR, EURUSD
from .lenses import lens_pair, canonical_lens, home_currency, currency_symbol
from .rolling import excess_summary
from .labels import display_label


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


def outperformance_interpretation(result, horizon, perspective):
    """Describe any observed point without treating overlapping trials as independent."""
    home = home_currency(perspective)
    daily = result['daily']
    years = (daily.index[-1]-daily.index[0]).days/365.2425
    p = result['probability']
    if horizon not in p.index or not p.loc[horizon, 'Windows']:
        return InterpretationCard('Historical outperformance', 'Insufficient history',
            f'No complete {horizon}-year windows are available in this selected sample. No win fraction is estimated.')
    row = p.loc[horizon]
    text = (f'At a {horizon}-year holding period, the S&P exceeded NIFTY in {row.SP_wins:.1%} of {int(row.Windows):,} '
        f'historical overlapping monthly windows under the {home} investor lens. NIFTY won {row.NIFTY_wins:.1%}; ties were {row.Ties:.1%}. '
        f'Mean S&P minus NIFTY excess CAGR was {row.Mean_advantage*100:+.2f} pp; the median was {row.Median_advantage*100:+.2f} pp. ')
    if row.NIFTY_wins == 1 or row.SP_wins == 1:
        leader = 'NIFTY' if row.NIFTY_wins == 1 else 'S&P'
        text += f'{leader} produced the higher home-currency CAGR in all observed windows at this horizon. '
    if row.SP_wins > .5 and row.Mean_advantage < 0:
        text += 'S&P won more than half the windows but had negative mean excess CAGR: the win fraction counts outcomes, while the mean also reflects the size of advantages and losses. '
    elif row.NIFTY_wins > .5 and row.Mean_advantage > 0:
        text += 'NIFTY won more than half the windows but S&P had positive mean excess CAGR: the win fraction counts outcomes, while the mean also reflects the size of advantages and losses. '
    limited = horizon > years * .5
    if limited:
        text += (f'Limited independent long-horizon evidence: {horizon} years is {horizon/years:.0%} of the {years:.2f}-year sample. '
            'These windows overlap heavily; their count does not represent that many independent observations, and all observed wins are not a forecast of future outperformance. ')
    text += 'Historical win fractions are descriptive, not future probabilities. Overlapping windows share data and are not independent trials.'
    return InterpretationCard(f'{horizon}Y historical outperformance', f'{int(row.Windows):,} windows · S&P wins {row.SP_wins:.1%}', text, limited)


def build_tab_interpretations(result, horizon=10, perspective='INR-based investor', capital=100, include_ytd=True, bootstrap=None):
    """One numerical narrative system for the app and the offline snapshot."""
    from .investor_journey import investor_journey
    journey = investor_journey(result, perspective, capital)
    home, symbol = journey['home'], currency_symbol(perspective)
    a, b = lens_pair(perspective)
    daily = result['daily']
    state = (f'{perspective} · {daily.index[0]:%d %b %Y} → {daily.index[-1]:%d %b %Y} · '
        f'{horizon}Y selected horizon · {symbol}{capital:,.0f} starting wealth · YTD {"included" if include_ytd else "excluded"}.')
    cards = dict(Overview=build_overview_interpretation(result,horizon,perspective,capital))
    n, sp = journey['routes']
    native_gap=n.native_cagr-sp.native_cagr
    home_gap=journey['cagr_difference']
    ranking = ('Translation changed the ordering relative to the two native-currency CAGRs. ' if native_gap*home_gap < 0 else
        'Translation preserved the ordering of the two native-currency CAGRs. ')
    ranking += 'Native INR and USD CAGRs are measured in different units, so that ordering alone is not a fair investor comparison or causal attribution.'
    wealth = (f'Both investments begin with {symbol}{capital:,.0f} on the same date. Under the {home} lens the curves already translate final wealth back into {home}. '
        f'NIFTY ended at {symbol}{n.final_home:,.2f}; S&P at {symbol}{sp.final_home:,.2f}. The winner was {journey["winner"]}. '
        f'NIFTY minus S&P ending wealth was {symbol}{journey["wealth_difference"]:+,.2f}, '
        f'or {journey["percentage_wealth_difference"]:+.2%} of S&P ending wealth; the CAGR difference was {home_gap*100:+.2f} pp. '
        f'{ranking} Starting capital scales wealth, while CAGR is unchanged. Taxes, brokerage fees, bid-ask spread, tracking error, FX conversion charges and remittance fees are excluded.')
    cards['Wealth']=[InterpretationCard('Equal-start wealth',f'{journey["winner"]} · selected sample',wealth)]
    annual=result['annual']
    if len(annual):
        delta=annual[b]-annual[a]
        wins_n=int((delta < -1e-12).sum()); wins_sp=int((delta > 1e-12).sum()); ties=len(delta)-wins_n-wins_sp
        text=' '.join(f'{name}: strongest period {annual[c].idxmax()} ({annual[c].max():.2%}); weakest {annual[c].idxmin()} ({annual[c].min():.2%}).' for c,name in [(a,'NIFTY'),(b,'S&P')])
        text += (f' In {home}, NIFTY won {wins_n}/{len(annual)} displayed periods ({wins_n/len(annual):.1%}), '
            f'S&P won {wins_sp}/{len(annual)} ({wins_sp/len(annual):.1%}); ties {ties}. '
            f'YTD is {"included when a partial terminal year is available" if include_ytd else "excluded"}; a YTD row is an incomplete period, not a full calendar year. '
            'Calendar-year winner counts are descriptive historical statistics, not probabilities. The first partial starting year is omitted.')
        cards['Annual Returns']=[InterpretationCard('Calendar-year evidence',f'{len(annual)} displayed periods · {home}',text)]
    else:
        cards['Annual Returns']=[InterpretationCard('Calendar-year evidence','No complete periods',
            f'No calendar-year periods are available for this selected sample. YTD is {"included" if include_ytd else "excluded"}; the first partial starting year is omitted. No annual winner count is inferred.')]
    r=result['rolling'].get(horizon)
    if r is not None and len(r):
        e=excess_summary(r,perspective)
        text=(f'A {horizon}-year rolling return repeatedly moves the starting date through history and measures every eligible {horizon}-year holding period. '
            f'Across {len(r):,} monthly windows in {home}, NIFTY median CAGR was {r[a].median():.2%}, minimum {r[a].min():.2%}, maximum {r[a].max():.2%}; '
            f'S&P median was {r[b].median():.2%}, minimum {r[b].min():.2%}, maximum {r[b].max():.2%}. '
            f'Positive-window fractions were {(r[a]>0).mean():.1%} for NIFTY and {(r[b]>0).mean():.1%} for S&P. '
            f'Median S&P minus NIFTY excess CAGR was {e.Median_advantage*100:+.2f} pp; S&P won {e.SP_wins:.1%}, NIFTY {e.NIFTY_wins:.1%}. '
            'This shows sensitivity to the investment date. Overlapping windows share data and are not independent trials or forecasts.')
        cards['Rolling Returns']=[InterpretationCard('Repeated holding periods',f'{len(r):,} overlapping {horizon}Y windows',text)]
    else:
        cards['Rolling Returns']=[InterpretationCard('Repeated holding periods','Insufficient history',f'This sample has no complete {horizon}-year rolling windows; no distribution is inferred.')]
    cards['Outperformance']=[outperformance_interpretation(result,horizon,perspective)]
    p=result['probability']
    if len(p) and p.index[-1] != horizon:
        cards['Outperformance'].append(outperformance_interpretation(result,int(p.index[-1]),perspective))
    holding=result['holding']
    cards['holding_matrix']=[InterpretationCard('How to read the holding-period matrix','Positive = S&P · negative = NIFTY',
        f'Each cell compares S&P CAGR minus NIFTY CAGR for a particular starting year and holding period in {home}. '
        f'This selection contains {len(holding):,} eligible cells. Positive values mean S&P outperformed; negative values mean NIFTY outperformed. '
        'Blank cells lack a complete holding period. The cells overlap and do not provide independent evidence.')]
    endpoints=result['endpoints']
    changes=[]
    if len(endpoints):
        for _,group in endpoints.groupby('Start_year'):
            changes.extend(group.sort_values('End_date').Difference.diff().abs().dropna().tolist())
    swing=max(changes,default=0.)
    sensitive=swing >= .02
    cards['endpoints']=[InterpretationCard('Endpoint sensitivity',f'{swing*100:.2f} pp maximum adjacent-endpoint change',
        f'This matrix shows how conclusions change when the ending year changes, for the same starting year, in {home}. '
        f'The largest change in S&P minus NIFTY CAGR across adjacent available ending years is {swing*100:.2f} pp. '
        + ('This exceeds the descriptive 2 pp sensitivity flag; the full-sample CAGR should not be treated as the only historical story. ' if sensitive else
           'This is below the descriptive 2 pp sensitivity flag; it does not establish endpoint independence. ')
        + 'Nearby endpoints share observations. Short holding periods can produce large annualized swings, and this flag is a presentation heuristic, not a statistical test.',sensitive)]
    identity={'INR':'S&P home-currency log return = US equity log return + USD/INR log movement.',
        'USD':'NIFTY home-currency log return = Indian equity log return − USD/INR log movement.',
        'EUR':'NIFTY EUR log return = NIFTY INR log return − EUR/INR log movement. S&P EUR log return = S&P USD log return − EUR/USD log movement.'}[home]
    effects=[]
    for route in journey['routes']:
        effect='helped' if route.fx_log>1e-12 else 'hurt' if route.fx_log < -1e-12 else 'had no translation effect on'
        effects.append(f'FX {effect} {route.name}: native {route.native_currency} CAGR {route.native_cagr:.2%} became {route.home_cagr:.2%} in {home}. '
            f'{route.fx_name} CAGR is {route.fx_cagr:.2%}; the exact annual FX log contribution is {route.fx_log*100:+.2f} log pp '
            f'({"tailwind" if route.fx_log>1e-12 else "drag" if route.fx_log < -1e-12 else "neutral"}). The arithmetic home-minus-native CAGR gap is {route.fx_gap*100:+.2f} pp.')
    cards['Currency']=[InterpretationCard('Exact equity + FX accounting',f'{home} outcomes · both routes',identity+' '+' '.join(effects)+
        ' The CAGR difference is intuitive but is not exactly additive. Log returns are used for attribution because equity and currency components then add exactly. Intermediate currency routing is not a third investment; transaction costs are excluded.')]
    risk=result['risk']
    va,vb=float(risk.loc[a,'Annualized_volatility']),float(risk.loc[b,'Annualized_volatility'])
    more='NIFTY' if va>vb else 'S&P' if vb>va else 'Neither investment'
    cards['volatility']=[InterpretationCard('Annualized volatility',f'{abs(va-vb)*100:.2f} pp volatility gap',
        'Annualized volatility measures how variable monthly returns were, scaled to an annual basis using the square root of 12. '
        f'It measures instability of the return path, not the level of return. In {home}, NIFTY volatility was {va:.2%}; S&P was {vb:.2%}. '
        f'{more} was more volatile; the absolute gap was {abs(va-vb)*100:.2f} pp. These are historical converted-path statistics, not a forecast of future risk.')]
    da,db=float(risk.loc[a,'Max_drawdown']),float(risk.loc[b,'Max_drawdown'])
    dates=[]
    for c,name in [(a,'NIFTY'),(b,'S&P')]:
        episodes=result['drawdowns'].loc[result['drawdowns'].Series==c]
        if len(episodes):
            row=episodes.loc[episodes.depth.idxmin()]
            recovery='unrecovered at the selected endpoint' if row.censored else f'recovered {row.recovery:%d %b %Y}'
            dates.append(f'{name}: peak {row.start:%d %b %Y}, trough {row.trough:%d %b %Y}, {recovery}.')
    deeper='NIFTY' if da<db else 'S&P' if db<da else 'Neither investment'
    cards['drawdowns']=[InterpretationCard('Maximum drawdown',f'{da:.1%} NIFTY · {db:.1%} S&P',
        'Maximum drawdown answers: what was the largest historical peak-to-trough loss? Recovery can fall outside the selected sample. '
        f'In {home}, NIFTY lost {abs(da):.2%} and S&P {abs(db):.2%} from their prior peaks. {deeper} had the deeper loss; the depth difference was {abs(da-db)*100:.2f} pp. '
        +' '.join(dates)+' These use daily asynchronous valuation cutoffs, and historical losses do not bound future drawdowns.')]
    correlations=result['rolling_correlations'][36][f'{a} vs {b}'].dropna()
    corrtext=(f'The latest observation ({correlations.index[-1]:%d %b %Y}) is {correlations.iloc[-1]:.3f}; historical median {correlations.median():.3f}, '
        f'minimum {correlations.min():.3f}, maximum {correlations.max():.3f}. Recent co-movement is '
        f'{"above" if correlations.iloc[-1]>correlations.median() else "below" if correlations.iloc[-1]<correlations.median() else "equal to"} its historical median. ' if len(correlations) else
        'Fewer than 36 complete monthly returns are available; no rolling correlation is reported. ')
    cards['correlation']=[InterpretationCard('36-month rolling correlation',f'{correlations.iloc[-1]:.3f} latest correlation' if len(correlations) else 'Insufficient history',
        f'Each point measures correlation between NIFTY and S&P monthly returns over the preceding 36 months in {home}. '
        'Near +1 means strong co-movement; near 0 means a weak linear relationship; below 0 suggests opposite movement. Correlation does not tell us which market performed better. '
        +corrtext+'The overlapping estimates describe co-movement, not causality or a guarantee of diversification.')]
    count=len(result['nonoverlap'][horizon])
    cards['Robustness']=[InterpretationCard('Why test robustness?',f'{count} non-overlapping {horizon}Y windows',
        f'Rolling windows are useful but overlap heavily. This sample offers {count} non-overlapping {horizon}-year windows, reducing shared observations. '
        'The paired block bootstrap preserves short-run market and FX dependence within blocks when estimating uncertainty. '
        f'Bootstrap inference is {"included for the current state" if bootstrap is not None else "not available until run for this state"}. '
        'Disjoint windows can still share market regimes. Bootstrap intervals are conditional uncertainty estimates, not future prediction intervals; stationarity and effective sample size matter.')]
    cards['Methodology']=[InterpretationCard('Selected research state',f'{len(daily):,} common valuation cutoffs',
        state+' Both benchmarks include reinvested dividends. Source validation and bounded backward alignment protect the fair comparison. '
        'The two markets close at different times; these are historical valuations, not simultaneous executable prices. Costs and taxes are excluded.')]
    cards['Export']=[InterpretationCard('What this snapshot contains','Bootstrap inference included' if bootstrap is not None else 'Bootstrap not run for this state',
        state+' The offline HTML contains this investor journey and the same calculated interpretations as the app. '
        +('Matching bootstrap results are included automatically.' if bootstrap is not None else 'Bootstrap results are not fabricated. Run the robustness calculation to include matching inference.'))]
    return cards
