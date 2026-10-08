"""Shared descriptive research evidence. No inference or source calculations here.

All rates come from validated snapshots or the existing investment accounting.
Crossovers concern monthly rolling endpoints, not economic regime breaks.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import numpy as np
import pandas as pd
from .config import HORIZONS, DAYS_PER_YEAR
from .interpretation import InterpretationCard
from .investor_journey import investor_journey
from .lenses import canonical_lens, lens_pair, currency_symbol
from .rolling import excess_summary
from .labels import display_label

TOLERANCE = 1e-12  # Same tie tolerance as the validated paired summaries.
PERSISTENCE_MONTHS = 6
BOOTSTRAP_UNAVAILABLE = ('Bootstrap inference was not calculated for this selected analysis state. '
                        'The findings in this report are descriptive historical results.')


def _sign(value):
    return 0 if not np.isfinite(value) or abs(value) <= TOLERANCE else 1 if value > 0 else -1


def _leader(sign):
    return 'S&P 500' if sign > 0 else 'NIFTY 50' if sign < 0 else 'Tie or no majority'


def analysis_fingerprint(result, horizon, perspective):
    """Bind optional inference to exact data, dates, horizon and economic lens."""
    daily = result['daily']
    digest = hashlib.sha256(pd.util.hash_pandas_object(daily, index=True).values.tobytes()).hexdigest()
    return f'{canonical_lens(perspective)}|{int(horizon)}|{daily.index[0].isoformat()}|{daily.index[-1].isoformat()}|{digest}'


def matching_bootstrap(result, horizon, perspective, bootstrap, meta):
    if bootstrap is None or bootstrap.empty:
        return None
    if (meta or {}).get('analysis_fingerprint') != analysis_fingerprint(result, horizon, perspective):
        return None
    if not {'Perspective', 'Horizon', 'Statistic', 'Confidence', 'Lower', 'Upper'}.issubset(bootstrap):
        return None
    if not bootstrap.Perspective.map(canonical_lens).eq(canonical_lens(perspective)).all() or not bootstrap.Horizon.eq(horizon).all():
        return None
    return bootstrap


def detect_descriptive_crossovers(rolling, perspective, persistence=PERSISTENCE_MONTHS):
    """Bracket observed sign switches, retaining actual matched Start_date.

    Ties bridge a sign switch but interrupt sustained sequences. Missing values
    and missing endpoint months reset both histories. No interpolation, gap
    bridging, significance test or assumption of independent windows is used.
    Six consecutive valid monthly endpoints is a descriptive persistence rule.
    """
    if persistence < 2:
        raise ValueError('Persistence requires at least two endpoints.')
    a, b = lens_pair(perspective)
    frame = rolling.sort_index()
    events, runs = [], []
    previous = None
    previous_month = None
    run = []
    run_sign = 0
    delta = (frame[b] - frame[a]).astype(float)
    valid = delta[np.isfinite(delta)]

    def close_run():
        if len(run) >= persistence:
            runs.append(dict(Leader=_leader(run_sign), First_endpoint=run[0][0],
                Last_endpoint=run[-1][0], First_investment_start=run[0][1],
                Last_investment_start=run[-1][1], Consecutive_months=len(run)))

    def fractions(values):
        count = len(values)
        return dict(Windows=count, SP_wins=float((values > TOLERANCE).mean()) if count else None,
            NIFTY_wins=float((values < -TOLERANCE).mean()) if count else None,
            Ties=float((values.abs() <= TOLERANCE).mean()) if count else None)

    for date, row in frame.iterrows():
        endpoint = pd.Timestamp(row.End_date) if 'End_date' in row else pd.Timestamp(date)
        start = pd.Timestamp(row.Start_date) if 'Start_date' in row else pd.NaT
        month = endpoint.to_period('M').ordinal
        if previous_month is not None and month != previous_month + 1:
            close_run()
            run, run_sign, previous = [], 0, None
        previous_month = month
        value = float(row[b] - row[a])
        if not np.isfinite(value) or pd.isna(start):
            close_run()
            run, run_sign, previous = [], 0, None
            continue
        sign = _sign(value)
        if sign and previous and previous[2] != sign:
            before, after = fractions(valid.loc[valid.index < date]), fractions(valid.loc[valid.index >= date])
            events.append(dict(Previous_endpoint=previous[0], Endpoint=endpoint,
                Investment_start=start, Previous_investment_start=previous[1],
                From=_leader(previous[2]), To=_leader(sign), Excess_CAGR=value,
                Before_windows=before['Windows'], After_windows=after['Windows'],
                Before_SP_wins=before['SP_wins'], After_SP_wins=after['SP_wins'],
                Before_NIFTY_wins=before['NIFTY_wins'], After_NIFTY_wins=after['NIFTY_wins'],
                Before_ties=before['Ties'], After_ties=after['Ties']))
        if sign:
            previous = (endpoint, start, sign)
        if sign != run_sign or not sign:
            close_run()
            run, run_sign = [], sign
        if sign:
            run.append((endpoint, start))
    close_run()
    latest = frame.iloc[-1] if len(frame) else None
    latest_value = float(latest[b] - latest[a]) if latest is not None else np.nan
    return dict(events=events, sustained=runs, reversal_count=len(events),
        latest_leader=_leader(_sign(latest_value)) if np.isfinite(latest_value) else 'Unavailable',
        latest_endpoint=pd.Timestamp(latest.End_date) if latest is not None else None,
        latest_start=pd.Timestamp(latest.Start_date) if latest is not None else None,
        valid_windows=len(valid), persistence_months=persistence, tolerance=TOLERANCE)


@dataclass(frozen=True)
class ResearchFindings:
    state: dict
    values: dict
    units: dict
    cards: tuple
    additional_cards: dict
    horizons: tuple
    crossovers: dict
    bootstrap: object
    provenance: tuple
    validation_notes: tuple

    @property
    def conclusion(self):
        return self.cards[-1].text


def build_research_findings(result, horizon=10, perspective='INR-based investor', capital=100,
                            include_ytd=None, bootstrap=None, bootstrap_meta=None, lab=None,
                            selected_start=None, selected_end=None, generated_at=None):
    lens = canonical_lens(perspective)
    if result['perspective'] != lens:
        raise ValueError('Research lens must match its analytical snapshot.')
    if include_ytd is not None and bool(include_ytd) != bool(result['include_ytd']):
        raise ValueError('YTD setting must match its analytical snapshot.')
    if horizon not in result['rolling']:
        raise ValueError('Selected horizon is not in the analytical snapshot.')
    journey = investor_journey(result, lens, capital)
    n, sp = journey['routes']
    home, symbol = journey['home'], currency_symbol(lens)
    daily = result['daily']
    years = (daily.index[-1] - daily.index[0]).days / DAYS_PER_YEAR
    state = dict(investor_lens=lens, home_currency=home, currency_symbol=symbol,
        selected_start=str(selected_start or daily.index[0].date()), selected_end=str(selected_end or daily.index[-1].date()),
        actual_start=str(daily.index[0].date()), actual_end=str(daily.index[-1].date()),
        common_validated_cutoff=str(lab.daily.index[-1].date()) if lab else str(daily.index[-1].date()),
        horizon_years=int(horizon), sample_years=years, starting_wealth=float(capital),
        include_ytd=bool(result['include_ytd']), valuation_cutoffs=len(daily),
        canonical_start='1999-06-30', generated_at=generated_at or datetime.now(timezone.utc).isoformat(),
        analysis_fingerprint=analysis_fingerprint(result, horizon, lens),
        asof_tolerance_days=lab.config.asof_tolerance_days if lab else 7,
        rolling_tolerance_days=lab.config.rolling_tolerance_days if lab else 7,
        persistence_months=PERSISTENCE_MONTHS, tie_tolerance=TOLERANCE)
    values = dict(nifty_cagr=n.home_cagr, sp_cagr=sp.home_cagr, nifty_wealth=n.final_home,
        sp_wealth=sp.final_home, full_excess_cagr=sp.home_cagr-n.home_cagr,
        native_excess_cagr=sp.native_cagr-n.native_cagr,
        nifty_native_cagr=n.native_cagr, sp_native_cagr=sp.native_cagr,
        nifty_fx_log=n.fx_log, sp_fx_log=sp.fx_log)
    full = _sign(values['full_excess_cagr'])
    rows, crossovers = [], {}
    for h in HORIZONS:
        r = result['rolling'][h]
        e = excess_summary(r, lens)
        crossovers[h] = detect_descriptive_crossovers(r, lens)
        disjoint = excess_summary(result['nonoverlap'][h], lens)
        rows.append(dict(Horizon=h, **e.to_dict(), Sample_fraction=h/years,
            Nonoverlap_windows=int(disjoint.Windows), Nonoverlap_SP_wins=disjoint.SP_wins,
            Reversals=crossovers[h]['reversal_count'], Sustained_sequences=len(crossovers[h]['sustained']),
            Latest_leader=crossovers[h]['latest_leader']))
    row = next(x for x in rows if x['Horizon'] == horizon)
    values.update(selected_windows=int(row['Windows']), sp_win_fraction=row['SP_wins'],
        nifty_win_fraction=row['NIFTY_wins'], ties=row['Ties'], mean_excess_cagr=row['Mean_advantage'],
        median_excess_cagr=row['Median_advantage'], nonoverlap_windows=row['Nonoverlap_windows'],
        horizon_sample_fraction=horizon/years)
    values['wealth_difference_nifty_minus_sp'] = n.final_home-sp.final_home
    endpoint_changes=[]
    if len(result['endpoints']):
        for _,group in result['endpoints'].groupby('Start_year'):
            endpoint_changes.extend(group.sort_values('End_date').Difference.diff().abs().dropna())
    values['endpoint_max_adjacent_change'] = float(max(endpoint_changes,default=0.))
    majority = 1 if row['SP_wins'] > .5 else -1 if row['NIFTY_wins'] > .5 else 0
    available = bool(row['Windows'])
    winner = journey['winner']
    full_text = (f'From {daily.index[0]:%d %b %Y} to {daily.index[-1]:%d %b %Y} ({years:.2f} years), '
        f'equal {symbol}{capital:,.0f} starting investments became {symbol}{n.final_home:,.2f} in NIFTY '
        f'and {symbol}{sp.final_home:,.2f} in S&P, measured in {home}. Full-sample CAGRs were '
        f'{n.home_cagr:.2%} and {sp.home_cagr:.2%}, respectively. {winner} led terminal wealth; '
        f'S&P minus NIFTY CAGR was {values["full_excess_cagr"]*100:+.2f} pp. '
        f'NIFTY minus S&P ending wealth was {symbol}{n.final_home-sp.final_home:+,.2f}.')
    if available:
        rolling_text = (f'Across {int(row["Windows"]):,} overlapping {horizon}Y windows, S&P won {row["SP_wins"]:.1%}, '
            f'NIFTY {row["NIFTY_wins"]:.1%}, with {row["Ties"]:.1%} ties. Mean paired excess CAGR was '
            f'{row["Mean_advantage"]*100:+.2f} pp and median {row["Median_advantage"]*100:+.2f} pp, always S&P minus NIFTY in {home}.')
        r=result['rolling'][horizon]
        a,b=lens_pair(lens)
        values.update(nifty_min_rolling=float(r[a].min()),nifty_max_rolling=float(r[a].max()),
            sp_min_rolling=float(r[b].min()),sp_max_rolling=float(r[b].max()))
        rolling_text += (f' NIFTY CAGRs ranged from {r[a].min():.2%} to {r[a].max():.2%}; '
            f'S&P from {r[b].min():.2%} to {r[b].max():.2%}. Across adjacent ending years at the same starting year, '
            f'the largest excess-CAGR change was {values["endpoint_max_adjacent_change"]*100:.2f} pp. Nearby endpoints share observations.')
        endpoint = (f'The full-sample winner is {winner}. '
            + (f'{_leader(majority)} is the selected rolling majority leader. ' if majority else '')
            + ('They disagree. ' if full != majority and majority else 'These measures agree on leadership. ' if full == majority else 'No investment won a strict majority of windows. ')
            + 'Terminal wealth measures one complete path; rolling frequency counts many different entry and exit dates, giving each window equal weight.')
        mean, median = _sign(row['Mean_advantage']), _sign(row['Median_advantage'])
        distribution = (f'Mean excess {row["Mean_advantage"]*100:+.2f} pp and median excess {row["Median_advantage"]*100:+.2f} pp '
            + ('have opposite signs. Large relative losses can outweigh more frequent modest wins; the median describes the middle window. ' if mean*median < 0 else
               'agree in sign. ' if mean == median else 'differ because one is at the tie tolerance. ')
            + (f'The majority leader {_leader(majority)} differs from the mean leader {_leader(mean)}. Frequency counts wins; average magnitude weights the size of wins and losses.'
               if majority and majority != mean else 'Win frequency and average magnitude do not show opposing leadership.' if majority else 'There is no strict majority leader to compare with average magnitude.'))
    else:
        rolling_text = f'No complete {horizon}Y windows are available. No rolling winner, mean, median or crossover conclusion is inferred.'
        endpoint = 'Full-sample wealth is observable, but the selected rolling comparison is unavailable.'
        distribution = 'Mean, median and win-frequency comparisons require complete paired windows.'
    crossing = crossovers[horizon]
    crossing_text = (f'{crossing["reversal_count"]} observed leadership reversals and {len(crossing["sustained"])} sustained sequences '
        f'under the descriptive rule of at least {PERSISTENCE_MONTHS} consecutive monthly endpoints with the same non-tied leader. '
        'Ties interrupt persistence; missing values and missing months reset comparisons. Crossings are bracketed observations, not exact crossing dates or evidence of economic regime changes. ')
    if crossing['events']:
        event = crossing['events'][-1]
        crossing_text += (f'The latest reversal is bracketed by endpoints {event["Previous_endpoint"]:%d %b %Y} and {event["Endpoint"]:%d %b %Y}. '
            f'The new {event["To"]} observation ending {event["Endpoint"]:%d %b %Y} belongs to an investment starting {event["Investment_start"]:%d %b %Y}, '
            f'not an investment beginning at that endpoint. S&P win fractions before/after this endpoint were '
            f'{event["Before_SP_wins"]:.1%} ({event["Before_windows"]} windows) and {event["After_SP_wins"]:.1%} ({event["After_windows"]} windows). '
            'This descriptive split uses all valid windows on each side and does not establish a statistical break. ')
    elif available:
        crossing_text += 'No observed sign reversal was identified in contiguous available months. This does not prove permanent leadership. '
    else:
        crossing_text += 'Insufficient history for crossover analysis. '
    if crossing['reversal_count'] > 1:
        crossing_text += 'Repeated reversals describe changing historical leadership, not one lasting transition. '
    if available:
        crossing_text += f'Latest observed leader: {crossing["latest_leader"]}, at endpoint {crossing["latest_endpoint"]:%d %b %Y}.'
    feasible = [x for x in rows if x['Windows']]
    if feasible:
        short, long = feasible[0], feasible[-1]
        short_sign = 1 if short['SP_wins'] > .5 else -1 if short['NIFTY_wins'] > .5 else 0
        long_sign = 1 if long['SP_wins'] > .5 else -1 if long['NIFTY_wins'] > .5 else 0
        horizon_text = (f'The shortest available horizon ({short["Horizon"]}Y) has {short["SP_wins"]:.1%} S&P wins; '
            f'the longest ({long["Horizon"]}Y) has {long["SP_wins"]:.1%}. '
            + ('Their majority leaders differ. ' if short_sign != long_sign else 'Their majority leaders agree. ')
            + ('Latest endpoint leaders differ across available horizons. ' if len({x['Latest_leader'] for x in feasible}) > 1 else
               'Latest endpoint leaders agree across available horizons. ')
            + 'Horizon choice changes which investment experiences are sampled; shorter horizons can reverse repeatedly.')
    else:
        horizon_text = 'No complete standard holding horizons are available in this date range.'
    dependence = (f'The selected {horizon}Y horizon is {horizon/years:.1%} of the {years:.2f}-year sample. '
        f'{int(row["Windows"]):,} overlapping windows reduce to {row["Nonoverlap_windows"]} disjoint windows from the selected origin. '
        + ('Limited independent long-horizon evidence: the horizon exceeds half the sample. ' if horizon/years > .5 else '')
        + 'Adjacent rolling windows share nearly their entire return histories. These counts are not independent trials; '
          'no ordinary binomial interval or p-value is appropriate. Disjoint windows can still share persistent market conditions.')
    ranking_changed = _sign(values['native_excess_cagr'])*full < 0
    currency_text = ' '.join(f'{route.name}: native {route.native_currency} CAGR {route.native_cagr:.2%}, '
        f'home {home} CAGR {route.home_cagr:.2%}, exact FX contribution {route.fx_log*100:+.2f} annual log pp '
        f'({"tailwind" if route.fx_log > TOLERANCE else "drag" if route.fx_log < -TOLERANCE else "neutral"}).'
        for route in journey['routes'])
    currency_text += (' Translation changed the native-return ranking. ' if ranking_changed else ' Translation preserved the native-return ranking. ')
    currency_text += 'Native INR and USD returns have different units; the fair investor comparison uses one home currency. Native equity log return plus FX log contribution equals home-currency log return exactly; arithmetic CAGR gaps do not add exactly.'
    a, b = lens_pair(lens)
    risk = result['risk'].loc[[a,b]]
    dn, ds = risk.Max_drawdown.tolist()
    vn, vs = risk.Annualized_volatility.tolist()
    values.update(nifty_drawdown=dn, sp_drawdown=ds, nifty_volatility=vn, sp_volatility=vs,
        currency_ranking_changed=ranking_changed, endpoint_majority_disagree=bool(available and majority and full != majority),
        mean_median_disagree=bool(available and _sign(row['Mean_advantage'])*_sign(row['Median_advantage']) < 0))
    risk_text = (f'NIFTY / S&P maximum drawdowns were {dn:.2%} / {ds:.2%}, with monthly annualized volatility '
        f'{vn:.2%} / {vs:.2%} in {home}. ')
    risk_text += ('The terminal-wealth leader also had the deeper drawdown. Higher return did not eliminate historical loss risk. '
        if (full < 0 and dn < ds) or (full > 0 and ds < dn) else
        'The terminal-wealth leader did not have the deeper drawdown; volatility and drawdown still measure different risks. ')
    corr = result['rolling_correlations'][36][f'{a} vs {b}'].dropna()
    if len(corr):
        values.update(latest_correlation=float(corr.iloc[-1]), median_correlation=float(corr.median()))
        risk_text += f'Latest 36-month correlation was {corr.iloc[-1]:.3f} ({corr.index[-1]:%d %b %Y}), versus historical median {corr.median():.3f}. '
    else:
        risk_text += 'No complete 36-month correlation estimate is available. '
    risk_text += 'Correlation describes co-movement, not superior returns, causality or guaranteed diversification. These are historical risk comparisons, not an optimized allocation.'
    ci = matching_bootstrap(result,horizon,lens,bootstrap,bootstrap_meta)
    state['bootstrap_inference_included'] = ci is not None
    robustness = dependence
    if row['Nonoverlap_windows']:
        robustness += f' S&P won {row["Nonoverlap_SP_wins"]:.1%} of the {row["Nonoverlap_windows"]} disjoint windows; the partition depends on its origin.'
    if ci is None:
        bootstrap_text = BOOTSTRAP_UNAVAILABLE
    else:
        descriptions = []
        # Show the widest reported coverage in prose; tables preserve all levels.
        for _, item in ci.loc[ci.Confidence == ci.Confidence.max()].iterrows():
            unit = '%' if item.Statistic == 'Probability_SP_wins' else 'pp'
            descriptions.append(f'{display_label(item.Statistic)}: estimate {item.Estimate*100:+.2f}{unit}, '
                f'{item.Confidence:.0%} percentile interval [{item.Lower*100:+.2f}, {item.Upper*100:+.2f}]{unit}')
        first = ci.iloc[0]
        bootstrap_text = (f'Matching paired moving-block bootstrap: {int(first.Replications):,} replications, '
            f'{int(first.Block_length)} {first.Frequency} returns per block, seed {int(first.Seed)}. '
            + '; '.join(descriptions) + '. Intervals resample paired primitive equity and FX log returns and reconstruct paths. '
            'They are conditional on stationarity and the observed sample, not predictions or guarantees. '
            + str((bootstrap_meta or {}).get('warning','')))
    robustness += ' ' + bootstrap_text
    mixed = (values['endpoint_majority_disagree'] or values['mean_median_disagree'] or ranking_changed or
        len({_sign(x['Median_advantage']) for x in feasible}) > 1)
    conclusion = (f'Historical evidence is {"mixed" if mixed else "consistent on the available return-leadership measures"} under the {home} lens. '
        f'{winner} led full-sample terminal wealth: NIFTY {symbol}{n.final_home:,.2f} ({n.home_cagr:.2%} CAGR), '
        f'S&P {symbol}{sp.final_home:,.2f} ({sp.home_cagr:.2%} CAGR). '
        + (f'Across {horizon}Y windows, S&P won {row["SP_wins"]:.1%} and NIFTY {row["NIFTY_wins"]:.1%}. '
            + ('The majority leader differs from the full-sample winner, because different entry and exit dates are measured. ' if values['endpoint_majority_disagree'] else '')
            + f'Mean / median paired excess were {row["Mean_advantage"]*100:+.2f} / {row["Median_advantage"]*100:+.2f} pp. '
            if available else rolling_text+' ')
        + ('Currency translation changed the native ranking. ' if ranking_changed else 'Currency translation preserved the native ranking. ')
        + f'FX contributions were {n.fx_log*100:+.2f} / {sp.fx_log*100:+.2f} annual log pp for NIFTY / S&P. '
        f'Maximum drawdowns were {dn:.2%} / {ds:.2%}; annualized volatility {vn:.2%} / {vs:.2%}. '
        + ('The terminal-wealth leader had the deeper drawdown. ' if (full < 0 and dn < ds) or (full > 0 and ds < dn) else '')
        + 'Results depend on sample dates, holding periods and FX paths. '
        f'The {int(row["Windows"])} rolling windows overlap; only {row["Nonoverlap_windows"]} disjoint {horizon}Y intervals fit this partition. '
        + ('Matching bootstrap intervals provide conditional uncertainty estimates. ' if ci is not None else BOOTSTRAP_UNAVAILABLE + ' ')
        + 'No future winner or personal allocation is inferred.')
    cards = (
        InterpretationCard('Research question', f'One home currency: {home}', journey['definition'] +
            ' Which investment built more wealth, how often did it lead across holding periods, and what roles did currency and risk play?'),
        InterpretationCard('Selected-sample outcome', f'{winner} · terminal wealth', full_text),
        InterpretationCard('Holding-period evidence', f'{horizon}Y · {int(row["Windows"]):,} windows', rolling_text + ' ' + endpoint),
        InterpretationCard('Reconciling the distribution', 'Mean · median · win frequency', distribution, values['mean_median_disagree']),
        InterpretationCard('Currency contribution', f'Exact log attribution · {home}', currency_text),
        InterpretationCard('Risk and diversification', 'Return and loss risk together', risk_text),
        InterpretationCard('Robustness and uncertainty', f'{row["Nonoverlap_windows"]} disjoint windows', robustness, True),
        InterpretationCard('Integrated historical conclusion', 'Conditional evidence · no forecast', conclusion, mixed))
    extra = dict(
        Overview=[InterpretationCard('The endpoint and the typical window', 'Different questions', endpoint)],
        Wealth=[InterpretationCard('Endpoint versus rolling majority', 'Compounding and frequency', endpoint)],
        **{'Annual Returns':[InterpretationCard('Yearly wins versus compounded wealth','Different weights',
            'Annual leadership and strongest or weakest years describe individual calendar periods. Winner counts weight each year equally; terminal wealth compounds all gains and losses in sequence. A majority of annual wins need not imply greater long-term wealth.')]},
        **{'Rolling Returns':[InterpretationCard('Observed crossovers',f'{crossing["reversal_count"]} reversals',crossing_text),
            InterpretationCard('Horizon sensitivity','Short versus long holding periods',horizon_text),
            InterpretationCard('Reconciling rolling statistics','Mean · median · frequency',distribution)]},
        Outperformance=[InterpretationCard('How much independent history?',f'{horizon/years:.1%} of sample',dependence,True)],
        Currency=[InterpretationCard('Ranking after translation','Home-currency comparison',currency_text)],
        drawdowns=[InterpretationCard('Return and risk tradeoff','Selected investor lens',risk_text)],
        Robustness=[InterpretationCard('Inference availability','Matching state only',bootstrap_text,ci is None)],
        Methodology=[InterpretationCard('Descriptive crossover rule',f'{PERSISTENCE_MONTHS} consecutive months',crossing_text)],
        Export=[InterpretationCard('Academic research reports','Selectable PDF · standalone HTML',
            'The PDF and research HTML combine the research question, shared numerical evidence, figures, limitations and conditional conclusion. '
            'The interactive dashboard retains all analytical tabs and reusable tables. All formats reflect the selected lens, dates, horizon, capital and YTD state.')])
    provenance, notes = [], []
    if lab is not None:
        for _, source in lab.provenance.iterrows():
            key = source.Series
            meta = lab.metadata[key]
            provenance.append(dict(series=key, source=str(source.Source), ticker=str(source.Ticker),
                url=meta.get('source_url',''), raw_first=str(source.First_date), raw_last=str(source.Last_date),
                endpoint_observation=str(pd.Timestamp(lab.audit.loc[daily.index[-1],key]).date()),
                valuation_cutoff=str(daily.index[-1].date()), retrieval_utc=str(source.Retrieval_UTC),
                identity_evidence=str(source.Identity_evidence), sha256=str(source.SHA256)))
        notes = lab.validation.loc[lab.validation.status != 'PASS'].to_dict('records')
    # Missing rolling evidence remains explicit and serializes as valid JSON null.
    values = {k:None if isinstance(v,(float,np.floating)) and not np.isfinite(v) else v for k,v in values.items()}
    units = {k:('home-currency units' if 'wealth' in k else 'decimal fraction' if 'cagr' in k or 'drawdown' in k or 'volatility' in k or 'fraction' in k or 'rolling' in k or 'change' in k or k=='ties'
        else 'annual log return' if 'fx_log' in k else 'count' if 'windows' in k else 'dimensionless') for k in values}
    return ResearchFindings(state,values,units,cards,extra,tuple(rows),crossovers,ci,tuple(provenance),tuple(notes))
