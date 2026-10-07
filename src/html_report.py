"""Fully offline interactive snapshot: one embedded Plotly runtime, local tabs."""
from datetime import datetime
from html import escape
import json
from pathlib import Path
from zoneinfo import ZoneInfo
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup
import pandas as pd
from plotly.offline import get_plotlyjs
from plotly.utils import PlotlyJSONEncoder
from .app_service import source_status
from .glossary import TABS, EXPLANATIONS, GLOSSARY
from .labels import display_table, display_label
from .lenses import lens_pair, canonical_lens
from .interpretation import build_overview_interpretation
from .presentation import hero_html, primary_kpis_html, lens_kpis_html, interpretation_html, info_html
from .reporting import tables_for_export
from .theme import css

ASSETS = Path(__file__).resolve().parents[1] / "assets"


def report_filename(now=None):
    stamp = now or datetime.now(ZoneInfo("Europe/Berlin"))
    return f"{stamp:%Y-%m-%d}_NIFTY_SP500_FX_Research_Lab.html"


def _json(value):
    return json.dumps(value, cls=PlotlyJSONEncoder).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def table_html(frame, title=""):
    if frame is None or frame.empty:
        return info_html(f"{title}: no complete observations in this selection.")
    display = display_table(frame)
    return (f'<h3>{escape(title)}</h3>' if title else '') + '<div class="table-wrap">' + display.to_html(
        escape=True, border=0, float_format=lambda x: f"{x:,.6f}", na_rep="—") + '</div>'


METHODOLOGY = """The canonical fair comparison begins exactly 30 June 1999; a selected subrange may begin later. The end is the latest common validated cutoff across all four primitive sources. NIFTY is NSE Indices Total Return Index and S&P is Yahoo ^SP500TR; price-index substitutes are rejected. FRED DEXINUS is INR per USD. FRED DEXUSEU Units are checked programmatically as U.S. Dollars to One Euro (USD per EUR). EUR/INR = USD/INR × EUR/USD. NIFTY EUR gross return = NIFTY INR gross return ÷ EUR/INR gross return; S&P EUR gross return = S&P USD gross return ÷ EUR/USD gross return. These and the existing INR/USD identities are validated to 1e-10. Valuation uses the union of sessions, bounded backward-as-of within seven calendar days, with no future filling or unknown-gap bridging. Indian and US closes are asynchronous. CAGR uses actual elapsed days / 365.2425; monthly snapshots use calendar month-end labels. Calendar returns omit the initial partial year, and the YTD setting controls the partial terminal year. Rolling windows use calendar anniversaries with bounded tolerance. Risk uses monthly returns and daily-cutoff drawdowns; downside target is zero, not a risk-free rate. FX regimes describe co-movement, not causation. Bootstrap uses paired non-circular contiguous blocks, with stationarity, endpoint and small-sample limitations. Taxes, fees, tracking error and remittance costs are excluded. Historical research only; no allocation or investment recommendation."""


def build_html_report(result, lab, figures, *, horizon=10, perspective="INR-based investor", capital=100,
                      log=True, include_ytd=True, selected_start=None, selected_end=None, bootstrap=None, bootstrap_meta=None):
    lens = canonical_lens(perspective)
    if result["perspective"] != lens:
        raise ValueError("HTML lens must match its analytical snapshot.")
    daily = result["daily"]
    metadata = dict(investor_lens=lens, selected_start=str(selected_start or daily.index[0].date()),
        selected_end=str(selected_end or daily.index[-1].date()), actual_start=str(daily.index[0].date()),
        actual_end=str(daily.index[-1].date()), rolling_horizon_years=horizon, include_ytd=include_ytd,
        starting_wealth=capital, logarithmic_wealth_axis=log, canonical_start="1999-06-30",
        generated_at=datetime.now(ZoneInfo("Europe/Berlin")).isoformat(),
        fx_units="DEXINUS: INR per USD; DEXUSEU: USD per EUR; EURINR: INR per EUR",
        table_numeric_units="Returns/CAGR/log returns are decimal fractions; ratios and counts retain native units.")

    def chart(name, suffix=""):
        fig = figures[name]
        element_id = name + suffix
        spec = _json(dict(data=fig.to_plotly_json()["data"], layout=fig.to_plotly_json()["layout"]))
        return (f'<div class="figure"><div id="figure-{element_id}" class="plot-target" data-spec="spec-{element_id}" '
            f'role="group" aria-label="{escape(str(fig.layout.title.text))}"></div></div>'
            f'<script type="application/json" id="spec-{element_id}">{spec}</script>')

    narratives = build_overview_interpretation(result, horizon, lens, capital)
    a, b = lens_pair(lens)
    sections = {name: info_html(EXPLANATIONS[name]) for name in TABS}
    sections["Overview"] += primary_kpis_html(result) + lens_kpis_html(result,lens,capital) + chart("wealth","-overview") + interpretation_html(narratives)
    sections["Wealth"] += chart("wealth") + table_html(result["trailing"], "Trailing CAGR and endpoint dependence")
    sections["Annual Returns"] += chart("annual") + table_html(result["annual"], "Calendar-year returns (decimal fractions)")
    sections["Rolling Returns"] += ''.join(chart(x) for x in ("rolling", "multi_horizon", "excess", "distributions"))
    sections["Rolling Returns"] += table_html(result["rolling_summaries"][horizon].loc[[a,b]], f"{horizon}Y rolling distribution")
    sections["Outperformance"] += ''.join(chart(x) for x in ("probability", "holding_matrix", "endpoints")) + table_html(result["probability"], "Historical win fractions")
    sections["Currency"] += ''.join(chart(x) for x in ("fx_attribution", "fx_rolling")) + interpretation_html([narratives[1]])
    for asset, table in result["lens_fx_annual"].items():
        sections["Currency"] += table_html(table, f"{display_label(asset)} · exact log attribution")
    sections["Currency"] += table_html(result["fx_annual"], "Original USD/INR attribution") + table_html(result["regimes"], "USD/INR regimes · selected home-currency outcomes")
    sections["Risk & Drawdowns"] += ''.join(chart(x) for x in ("drawdowns", "volatility", "correlation"))
    sections["Risk & Drawdowns"] += table_html(result["risk"].loc[[a,b]], "Risk metrics") + table_html(result["drawdowns"][result["drawdowns"].Series.isin([a,b])], "Drawdown episodes")
    sections["Risk & Drawdowns"] += table_html(result["correlations"], "Daily as-of and monthly correlations")
    sections["Robustness"] += table_html(result["nonoverlap"][horizon][[a,b,"Start_date","End_date"]], f"Non-overlapping {horizon}Y windows")
    if bootstrap is not None:
        sections["Robustness"] += table_html(bootstrap,"Paired moving-block bootstrap") + info_html((bootstrap_meta or {}).get("caveat", "Stationarity approximation; intervals are not forecasts."))
    else:
        sections["Robustness"] += info_html("Bootstrap has not been run for this selected sample, horizon and lens. No confidence intervals are invented; run the robustness calculation in the app to include it in a new snapshot.")
    sections["Methodology"] += info_html(METHODOLOGY) + table_html(source_status(lab),"Source provenance") + table_html(lab.validation,"Validation checks")
    sections["Methodology"] += table_html(pd.DataFrame([lab.identity_errors]), "Maximum numerical identity errors")
    glossary = '<details><summary>Research glossary · all terms</summary><dl>' + ''.join(f'<dt>{escape(k)}</dt><dd>{escape(v)}</dd>' for k,v in GLOSSARY.items()) + '</dl></details>'
    sections["Methodology"] += glossary
    sections["Export"] += info_html("This HTML is a self-contained snapshot. In the app, complete Excel, CSV bundles, Annual Returns CSV and individual interactive figure HTML ZIP are immediately downloadable. The analytical tables below are embedded here for offline inspection. Numeric return columns use decimal fractions (0.10 = 10%).")
    # Do not embed arbitrary source metadata: only audited public provenance is exported to HTML.
    tables = tables_for_export(result,lab,bootstrap)
    tables["Metadata"] = source_status(lab)
    tables["Analysis_State"] = pd.DataFrame([metadata])
    for name, table in tables.items():
        sections["Export"] += '<details><summary>' + escape(display_label(name)) + '</summary>' + table_html(table) + '</details>'
    template = Environment(loader=FileSystemLoader(ASSETS), autoescape=select_autoescape(["html"])).get_template("report.html")
    document = template.render(css=Markup(css()), plotly_js=Markup(get_plotlyjs().replace("</script>", "<\\/script>")),
        metadata_json=Markup(_json(metadata)), metadata=metadata, hero=Markup(hero_html(lab)),
        panels=[dict(name=name, id=f"panel-{i}", content=Markup(sections[name])) for i,name in enumerate(TABS)])
    return document.encode("utf-8")
