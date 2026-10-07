"""Small escaped HTML components shared between Streamlit and offline export."""
from html import escape
import pandas as pd
from .app_service import kpis
from .interpretation import lens_statistics
from .labels import display_label
from .lenses import home_currency, currency_symbol


def info_html(text):
    return f'<div class="section-note">{escape(text)}</div>'


def hero_html(lab=None):
    pills = []
    if lab is not None:
        warnings = set(lab.validation.loc[lab.validation.status == "WARNING", "series"])
        for _, row in lab.provenance.iterrows():
            stale = (pd.Timestamp.now(tz="UTC").date() - pd.Timestamp(row.Last_date).date()).days > lab.config.stale_days
            warning = row.Series in warnings or stale
            status = " · check source warnings" if warning else " · validated"
            pills.append(f'<span class="status-pill"><span class="status-dot {"warning" if warning else ""}"></span>{escape(display_label(row.Series))} · {pd.Timestamp(row.Last_date):%d %b %Y}{status}</span>')
    return ('<div class="hero"><div class="hero-kicker">Quantitative market research</div>'
        '<div class="hero-title">NIFTY 50 × S&amp;P 500 × FX</div>'
        '<div class="hero-sub">Cross-market total-return research across INR, USD and EUR investor perspectives. '
        'Fair comparison from 30 June 1999; reinvested dividends, dynamic FX translation and holding-period evidence.</div>'
        '<div class="status-strip">' + ''.join(pills) + '</div></div>')


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
