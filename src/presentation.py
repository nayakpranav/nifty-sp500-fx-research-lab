"""Small escaped HTML components shared between Streamlit and offline export."""
from html import escape
import pandas as pd
from .app_service import kpis
from .interpretation import lens_statistics
from .labels import display_label
from .lenses import home_currency, currency_symbol
from .investor_journey import investor_journey


def info_html(text):
    return f'<div class="section-note">{escape(text)}</div>'


def hero_html(lab=None):
    pills = []
    if lab is not None:
        for _, row in lab.provenance.iterrows():
            status, severity = source_badge(lab, row.Series, row.Last_date)
            pills.append(f'<span class="status-pill"><span class="status-dot {severity}"></span>{escape(display_label(row.Series))} · {pd.Timestamp(row.Last_date):%d %b %Y} · {escape(status)}</span>')
    return ('<div class="hero"><div class="hero-kicker">Quantitative market research</div>'
        '<div class="hero-title">NIFTY 50 × S&amp;P 500 × FX</div>'
        '<div class="hero-sub">Cross-market total-return research across INR, USD and EUR investor perspectives. '
        'Fair comparison from 30 June 1999; reinvested dividends, dynamic FX translation and holding-period evidence.</div>'
        '<div class="status-strip">' + ''.join(pills) + '</div></div>')


def source_badge(lab, series, last_date, now=None):
    checks = lab.validation.loc[lab.validation.series == series]
    if (checks.status == 'FAIL').any():
        return 'Validation failed', 'error'
    age = (pd.Timestamp(now or pd.Timestamp.now(tz='UTC')).date()-pd.Timestamp(last_date).date()).days
    warnings = set(checks.loc[checks.status == 'WARNING','check'])
    if age > lab.config.stale_days or 'stale final observation' in warnings:
        return 'Validated · stale source warning', 'warning'
    benign = {'provider absent observations', 'session gaps', 'history'}
    if warnings-benign:
        return 'Validated · review quality warnings', 'warning'
    if warnings:
        return 'Validated · data-quality notes', 'note'
    return 'Validated', ''


def card_html(label, value, note="", sample=False):
    rendered = value if sample else escape(str(value))
    return (f'<div class="kpi-card"><div class="kpi-label">{escape(label)}</div>'
        f'<div class="kpi-value {"sample-range" if sample else ""}">{rendered}</div>'
        f'<div class="kpi-note">{escape(note)}</div></div>')


def primary_kpis_html(result):
    x = kpis(result)
    sample = f'<span>{pd.Timestamp(x["start"]):%d %b %Y}</span><span class="arrow">→</span><span>{pd.Timestamp(x["end"]):%d %b %Y}</span>'
    cards = [card_html("Common Sample", sample, f"{x['years']:.2f} years · same valuation cutoffs", True),
        card_html("NIFTY 50 TRI CAGR · INR", f"{x['nifty_cagr']:.2%}", "Total Return Index · reinvested dividends"),
        card_html("S&P 500 TR CAGR · USD native", f"{x['sp_usd_cagr']:.2%}", "Native US equity total return"),
        card_html("S&P 500 TR CAGR · INR-adjusted", f"{x['sp_inr_cagr']:.2%}", "US equity growth translated to rupees"),
        card_html("USD/INR CAGR · INR depreciation", f"{x['fx_cagr']:.2%}", "INR per USD · positive means INR depreciation")]
    return '<div class="kpi-grid primary-grid">' + ''.join(cards) + '</div>'


def lens_kpis_html(result, perspective, capital=100):
    s = lens_statistics(result, perspective, capital)
    home, symbol = home_currency(perspective), currency_symbol(perspective)
    return f'<div class="section-kicker">{home} Investor Lens</div><div class="kpi-grid secondary-grid">' + ''.join([
        card_html(f"NIFTY CAGR · {home}", f"{s['nifty_cagr']:.2%}"),
        card_html(f"S&P CAGR · {home}", f"{s['sp_cagr']:.2%}"),
        card_html("FX drag / tailwind", f"{s['fx_log']*100:+.2f} log pp", f"Exact annual log contribution · {'S&P' if home == 'INR' else 'NIFTY'}"),
        card_html(f"{symbol}{capital:,.0f} ending wealth · NIFTY", f"{symbol}{s['nifty_wealth']:,.2f}"),
        card_html(f"{symbol}{capital:,.0f} ending wealth · S&P", f"{symbol}{s['sp_wealth']:,.2f}")]) + '</div>'


def interpretation_html(cards):
    return '<div class="interpretation-grid">' + ''.join(
        f'<article class="interpretation-card {"caution" if c.caution else ""}"><h3>{escape(c.title)}</h3>'
        f'<div class="interpretation-number">{escape(c.highlight)}</div><p>{escape(c.text)}</p></article>' for c in cards) + '</div>'


def investor_journey_html(result, perspective, capital=100):
    j = investor_journey(result,perspective,capital)
    symbol = currency_symbol(perspective)
    def money(value,currency):
        return f'{dict(INR="₹",USD="$",EUR="€")[currency]}{value:,.2f}'
    routes = []
    for route in j['routes']:
        amounts = ([money(capital,j['home']),money(route.final_native,route.native_currency),money(route.final_home,j['home'])]
            if route.native_currency==j['home'] else [money(capital,j['home']),money(route.initial_native,route.native_currency),
                money(route.final_native,route.native_currency),money(route.final_home,j['home']),money(route.final_home,j['home'])])
        nodes = ''.join(f'<li><span>{escape(step)}</span><strong>{escape(value)}</strong></li>' for step,value in zip(route.steps,amounts))
        effect='tailwind' if route.fx_log>1e-12 else 'drag' if route.fx_log < -1e-12 else 'neutral'
        metrics = [(f'Native CAGR · {route.native_currency}',f'{route.native_cagr:.2%}'),
            (f'Home CAGR · {j["home"]}',f'{route.home_cagr:.2%}'),
            (route.fx_name,f'{route.fx_cagr:.2%} FX CAGR'),
            (f'Exact FX contribution · {effect}',f'{route.fx_log*100:+.2f} annual log pp'),
            ('Home − native CAGR gap',f'{route.fx_gap*100:+.2f} pp')]
        detail=''.join(f'<div><dt>{escape(k)}</dt><dd>{escape(v)}</dd></div>' for k,v in metrics)
        routes.append(f'<article class="journey-route"><h3>{escape(route.name)}</h3><ol class="journey-flow">{nodes}</ol><dl class="journey-metrics">{detail}</dl></article>')
    winner_text = f'{j["winner"]} finished ahead in this sample.' if j['winner']!='Tie' else 'Both investments finished at equal wealth within numerical tolerance.'
    summary=(f'Beginning with {symbol}{capital:,.0f} on {j["start"]:%d %b %Y}, an investor measuring wealth in {j["home"]} '
        f'would have ended on {j["end"]:%d %b %Y} with {symbol}{j["routes"][0].final_home:,.2f} through NIFTY '
        f'and {symbol}{j["routes"][1].final_home:,.2f} through S&P. '
        f'{winner_text} Native index growth and FX movement jointly determine the final home-currency result.')
    footer=[('Starting capital',money(capital,j['home'])),('Winner · selected sample',j['winner']),
        ('Absolute wealth difference',money(j['absolute_wealth_difference'],j['home'])),
        ('NIFTY − S&P / S&P ending wealth',f'{j["percentage_wealth_difference"]:+.2%}'),
        ('NIFTY − S&P CAGR',f'{j["cagr_difference"]*100:+.2f} pp')]
    return ('<section class="investor-journey" aria-label="Investor Journey"><div class="section-kicker">Your home-currency outcome</div>'
        '<h2>Investor Journey</h2><p>'+escape(j['definition'])+'</p><div class="journey-routes">'+''.join(routes)+'</div>'
        '<dl class="journey-summary">'+''.join(f'<div><dt>{escape(k)}</dt><dd>{escape(v)}</dd></div>' for k,v in footer)+'</dl>'
        '<p class="journey-result">'+escape(summary)+'</p><p class="journey-caution">Starting wealth scales the outcome; CAGR is unchanged. '
        'TRI = Total Return Index; TR = Total Return. Both include reinvested dividends. Historical index illustration excludes taxes, brokerage fees, bid-ask spread, tracking error, FX conversion charges and remittance fees.</p></section>')
