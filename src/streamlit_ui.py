"""Streamlit shell; analytical, narrative and report logic live in shared modules."""
from pathlib import Path
from contextlib import nullcontext
import hashlib
import html
import json
import pandas as pd
import streamlit as st
from .app_service import (COMPARISON_START, build_lab, csv_bundle_bytes, dataframe_csv_bytes,
    excel_bytes, figure_bundle_bytes, source_status, trimmed_result)
from .config import HORIZONS
from .glossary import TABS, EXPLANATIONS, GLOSSARY, CONTEXT_TERMS
from .html_report import build_html_report, report_filename, METHODOLOGY
from .interpretation import build_tab_interpretations, lens_statistics
from .labels import display_label, display_table
from .lenses import LENSES, lens_pair, home_currency
from .presentation import hero_html, primary_kpis_html, lens_kpis_html, interpretation_html, info_html, investor_journey_html
from .rolling import excess_summary
from .theme import css
from .visualizations import figure_set

ROOT = Path(__file__).resolve().parents[1]


@st.cache_resource(ttl='6h', show_spinner=False, scope='session')
def _lab(root, refresh_generation=0):
    return build_lab(root, force_refresh=refresh_generation > 0)


@st.cache_data(ttl='6h', max_entries=3, show_spinner=False)
def _exports(result, source_revision, horizon, perspective, capital, log_scale,
             include_ytd, start, end, _research_lab, bootstrap=None, bootstrap_meta=None):
    figures = figure_set(result, _research_lab, horizon=horizon, perspective=perspective, capital=capital, log=log_scale)
    return dict(html=build_html_report(result,_research_lab,figures,horizon=horizon,perspective=perspective,
        capital=capital,log=log_scale,include_ytd=include_ytd,selected_start=start,selected_end=end,
        bootstrap=bootstrap,bootstrap_meta=bootstrap_meta),
        excel=excel_bytes(result,_research_lab,bootstrap), csv=csv_bundle_bytes(result,_research_lab,bootstrap),
        annual=dataframe_csv_bytes(result['annual']), figures=figure_bundle_bytes(figures))


def _markup(value):
    st.markdown(value, unsafe_allow_html=True)


def _plot(fig, key):
    dense = key in ('annual','holding_matrix','endpoints')
    with st.container(key=f'matrix_{key}') if dense else nullcontext():
        st.plotly_chart(fig, width='stretch', theme=None, key=key, config={'displaylogo':False,'responsive':True,'modeBarButtonsToRemove':['sendChartToCloud']})
    if dense:
        st.caption('On narrow screens, scroll the matrix horizontally to inspect every column.')


def _table(frame, percent_cols=(), height=360):
    if frame is None or frame.empty:
        st.info('No complete observations for this selection.')
        return
    display = frame.copy()
    formats = {}
    for c in percent_cols:
        if c in display and pd.api.types.is_numeric_dtype(display[c]):
            display[c] *= 100
            formats[display_label(c)] = st.column_config.NumberColumn(format='%.2f%%')
    st.dataframe(display_table(display), width='stretch', height=min(height,max(110,len(display)*35+45)), column_config=formats)


def _glossary(terms=None):
    with st.expander('Research glossary' if terms is None else 'Help with terms in this view'):
        for term in terms or GLOSSARY:
            st.markdown(f'**{term}** — {GLOSSARY[term]}')


def _explanation(name, perspective):
    _markup(info_html(EXPLANATIONS[name]))
    st.caption(f'Investor Lens: {perspective} · comparisons use {home_currency(perspective)} unless explicitly labelled native.')
    if name in CONTEXT_TERMS:
        _glossary(CONTEXT_TERMS[name])


def _controls(lab):
    st.sidebar.markdown('### Investor Lens')
    perspective = st.sidebar.radio('Investor Lens', LENSES, label_visibility='collapsed',
        help='Choose the currency in which you ultimately measure your savings. Both investments are translated into this same home currency.')
    home = home_currency(perspective)
    st.sidebar.caption(f'You earn or save in {home} and measure final wealth in {home}. Both investments use this same home currency.')
    st.sidebar.divider()
    st.sidebar.markdown('### Holding period & display')
    horizon = st.sidebar.select_slider('Rolling horizon', options=list(HORIZONS), value=10, format_func=lambda x:f'{x}Y')
    capital = st.sidebar.selectbox('Starting wealth · home currency', [100,10_000,100_000])
    log_scale = st.sidebar.toggle('Logarithmic wealth scale', True)
    include_ytd = st.sidebar.toggle('Include current partial year (YTD)', True)
    with st.sidebar.expander('Sample dates'):
        start = st.date_input('Start', COMPARISON_START.date(), min_value=COMPARISON_START.date(),max_value=lab.daily.index[-1].date())
        end = st.date_input('End', lab.daily.index[-1].date(), min_value=COMPARISON_START.date(),max_value=lab.daily.index[-1].date())
        st.caption('The default fair sample starts exactly 30 June 1999. This control selects a later research subrange.')
    return horizon,perspective,capital,log_scale,include_ytd,start,end


def _landing():
    # Landing-only styles keep analytical views and offline exports unchanged.
    _markup(f'<style>{(ROOT / "assets" / "landing.css").read_text(encoding="utf-8")}</style>')
    _markup(hero_html())
    if st.button('Run Analysis',type='primary',key='landing_run_analysis'):
        st.session_state.analysis_ready=True
        st.rerun()
    _markup('''<div class="landing-introduction">
    <section class="landing-card landing-purpose" aria-label="Why I built this">
    <div class="hero-kicker">01 · The idea behind the lab</div><h2>Why I built this</h2>
    <p>A market can deliver excellent returns in its local currency. But if you earn and save in another currency,
    what matters is the investment's value <strong>after converting it back into your home currency.</strong></p>
    <div class="landing-euro-example"><span class="landing-example-label">🇪🇺 A euro saver in Germany or elsewhere in Europe</span>
    <p>You may send euros to India, convert EUR to INR, invest in NIFTY, and later convert your INR wealth back to EUR.
    A weaker rupee against the euro reduces that return; a stronger rupee can help. Equity growth is only part of your outcome.</p></div>
    </section>
    <section class="landing-lenses" aria-label="Three investor lenses">
    <div class="landing-section-heading"><h2>One home currency. Two investment routes.</h2>
    <p>Your investor lens is the currency in which you <strong>earn, save and ultimately measure wealth.</strong></p></div>
    <div class="landing-lens-grid">
    <article class="landing-card landing-lens"><h3><span aria-hidden="true">🇮🇳</span> INR-based investor</h3>
    <div class="landing-route-label">Indian equity</div><p class="landing-route">INR → NIFTY → INR</p>
    <div class="landing-versus">versus</div><div class="landing-route-label">US equity</div>
    <p class="landing-route landing-route-us">INR → USD → S&amp;P 500 → USD → INR</p></article>
    <article class="landing-card landing-lens"><h3><span aria-hidden="true">🇺🇸</span> USD-based investor</h3>
    <div class="landing-route-label">Indian equity</div><p class="landing-route">USD → INR → NIFTY → INR → USD</p>
    <div class="landing-versus">versus</div><div class="landing-route-label">US equity</div>
    <p class="landing-route landing-route-us">USD → S&amp;P 500 → USD</p></article>
    <article class="landing-card landing-lens"><h3><span aria-hidden="true">🇪🇺</span> EUR-based investor</h3>
    <div class="landing-route-label">Indian equity</div><p class="landing-route">EUR → INR → NIFTY → INR → EUR</p>
    <div class="landing-versus">versus</div><div class="landing-route-label">US equity</div>
    <p class="landing-route landing-route-us">EUR → USD → S&amp;P 500 → USD → EUR</p></article>
    </div></section>
    <section class="landing-explore" aria-label="What you can explore">
    <div class="landing-section-heading"><h2>What you can explore</h2><p>From the big picture to the evidence behind it.</p></div>
    <div class="landing-explore-grid">
    <article><span class="landing-explore-icon" aria-hidden="true">◈</span><h3>Overview</h3><p>Your home-currency outcome.</p></article>
    <article><span class="landing-explore-icon" aria-hidden="true">↗</span><h3>Wealth</h3><p>Follow equal starting investments.</p></article>
    <article><span class="landing-explore-icon" aria-hidden="true">▦</span><h3>Annual Returns</h3><p>Compare each year's results.</p></article>
    <article><span class="landing-explore-icon" aria-hidden="true">↻</span><h3>Rolling Returns</h3><p>Try different holding periods.</p></article>
    <article><span class="landing-explore-icon" aria-hidden="true">⇄</span><h3>Outperformance</h3><p>See historical winner frequencies.</p></article>
    <article><span class="landing-explore-icon" aria-hidden="true">⇌</span><h3>Currency</h3><p>Separate equity growth from FX.</p></article>
    <article><span class="landing-explore-icon" aria-hidden="true">⌁</span><h3>Risk &amp; Drawdowns</h3><p>Inspect losses and co-movement.</p></article>
    <article><span class="landing-explore-icon" aria-hidden="true">◇</span><h3>Robustness</h3><p>Understand uncertainty and overlap.</p></article>
    <article><span class="landing-explore-icon" aria-hidden="true">≡</span><h3>Methodology</h3><p>Inspect sources and assumptions.</p></article>
    <article><span class="landing-explore-icon" aria-hidden="true">↓</span><h3>Export</h3><p>Take the research offline.</p></article>
    </div></section>
    <footer class="landing-footer"><p>Historical market research. Taxes, fees, tracking error and remittance costs are excluded.</p>
    <!-- Add the secondary ☕ Support this project anchor here once its URL is provided. -->
    <div class="landing-support-slot"></div></footer></div>''')
    with st.expander('Verified live sources & common sample'):
        _markup('''<section class="landing-card"><h2>Equity growth + currency movement</h2>
    <div class="source-line">NIFTY 50 Total Return Index · NSE Indices</div><div class="source-line">S&amp;P 500 Total Return · Yahoo ^SP500TR</div>
    <div class="source-line">USD/INR · FRED DEXINUS · INR per USD</div><div class="source-line">EUR/USD · FRED DEXUSEU · USD per EUR</div>
    <p>30 June 1999 → latest common validated observation. TRI / TR include reinvested dividends.</p>
    <p>Market calendars are aligned using recent past observations. Each source's units and identity are checked before calculations.</p></section>''')
    _glossary(CONTEXT_TERMS['Overview'])


def run_app():
    st.set_page_config(page_title='NIFTY 50 × S&P 500 × FX',layout='wide',initial_sidebar_state='expanded')
    _markup(f'<style>{css()}</style>')
    st.sidebar.markdown('<div class="sidebar-brand">NIFTY × S&P × FX</div><div class="sidebar-note">TOTAL-RETURN RESEARCH LAB<br>INR · USD · EUR</div>', unsafe_allow_html=True)
    st.session_state.setdefault('refresh_generation',0)
    st.session_state.setdefault('analysis_ready',False)
    if not st.session_state.analysis_ready:
        st.sidebar.caption('Run the validated live-data pipeline to open the dashboard.')
        if st.sidebar.button('Run Analysis',type='primary',width='stretch'):
            st.session_state.analysis_ready=True
            st.rerun()
        _landing()
        return
    try:
        with st.spinner('Retrieving and validating live market data…'):
            lab = _lab(str(ROOT),st.session_state.refresh_generation)
    except Exception as exc:
        _markup(hero_html())
        st.error('Live market-data validation could not complete. The analysis will not substitute price indices or silently change its common sample.')
        with st.expander('Source diagnostics'):
            st.text(str(exc))
        if st.button('Retry live retrieval'):
            st.session_state.refresh_generation+=1
            _lab.clear()
            st.rerun()
        return
    _markup(hero_html(lab))
    if st.sidebar.button('Refresh live data',width='stretch'):
        st.session_state.refresh_generation+=1
        _lab.clear()
        st.session_state.pop('bootstrap_result',None)
        st.rerun()
    horizon,perspective,capital,log_scale,include_ytd,start,end = _controls(lab)
    try:
        result = trimmed_result(lab,start,end,include_ytd,perspective)
    except ValueError as exc:
        st.error(str(exc))
        return
    sample_key = (result['daily'].index[0],result['daily'].index[-1],horizon,perspective,
        hashlib.sha256(pd.util.hash_pandas_object(result['daily'],index=True).values.tobytes()).hexdigest())
    cached = st.session_state.get('bootstrap_result')
    valid_bootstrap = cached if cached and cached['key']==sample_key else None
    revision = hashlib.sha256((json.dumps(lab.metadata,sort_keys=True,default=str)+css()).encode()).hexdigest()
    with st.spinner('Building the offline research snapshot and ready-to-download exports…'):
        downloads = _exports(result,revision,horizon,perspective,capital,log_scale,include_ytd,start,end,lab,
            valid_bootstrap['ci'] if valid_bootstrap else None,valid_bootstrap['meta'] if valid_bootstrap else None)
    st.sidebar.caption('Exports ready · HTML / Excel / CSV')
    tabs = st.tabs(list(TABS),key='research_tabs',on_change='rerun')
    active = next((i for i,t in enumerate(tabs) if t.open),0)
    name = TABS[active]
    pair = list(lens_pair(perspective))
    interpretations=build_tab_interpretations(result,horizon,perspective,capital,include_ytd,
        valid_bootstrap['ci'] if valid_bootstrap else None)
    def explain(section):
        _markup(interpretation_html(interpretations[section]))
    def figs(names):
        return figure_set(result,lab,horizon=horizon,perspective=perspective,capital=capital,log=log_scale,only=names)
    with tabs[active]:
        _explanation(name,perspective)
        if active==0:
            _markup(primary_kpis_html(result))
            _markup(lens_kpis_html(result,perspective,capital))
            _markup(investor_journey_html(result,perspective,capital))
            _plot(figs(['wealth'])['wealth'],'overview_wealth')
            st.markdown('### What this means')
            explain('Overview')
        elif active==1:
            _plot(figs(['wealth'])['wealth'],'wealth')
            explain('Wealth')
            with st.expander('Trailing CAGR · endpoint dependence'):
                _table(result['trailing'],pair+['Difference'])
        elif active==2:
            _plot(figs(['annual'])['annual'],'annual')
            explain('Annual Returns')
            annual=result['annual'][pair+[c for c in result['annual'] if c not in pair]]
            _table(annual,annual.select_dtypes('number').columns)
        elif active==3:
            f=figs(['rolling','multi_horizon','excess','distributions'])
            _plot(f['rolling'],'rolling')
            explain('Rolling Returns')
            e=excess_summary(result['rolling'][horizon],perspective)
            c=st.columns(4)
            c[0].metric('S&P historical win fraction',f'{e.SP_wins:.1%}' if e.Windows else 'Unavailable')
            c[1].metric('NIFTY historical win fraction',f'{e.NIFTY_wins:.1%}' if e.Windows else 'Unavailable')
            c[2].metric('Median paired S&P advantage',f'{e.Median_advantage*100:+.2f} pp' if e.Windows else 'Unavailable')
            c[3].metric('Overlapping windows',f'{int(e.Windows):,}')
            for key in ('multi_horizon','excess','distributions'):
                _plot(f[key],key)
            summary=result['rolling_summaries'][horizon].loc[pair]
            _table(summary,[x for x in summary.columns if x!='Windows'])
        elif active==4:
            for key,fig in figs(['probability','holding_matrix','endpoints']).items():
                _plot(fig,key)
                explain('Outperformance' if key=='probability' else key)
        elif active==5:
            s=lens_statistics(result,perspective,capital)
            c=st.columns(3)
            asset='S&P' if home_currency(perspective)=='INR' else 'NIFTY'
            native='USD' if asset=='S&P' else 'INR'
            c[0].metric(f'Local {native} CAGR · {asset}',f'{s["local_cagr"]:.2%}')
            c[1].metric(f'{home_currency(perspective)}-denominated CAGR · {asset}',f'{s["translated_cagr"]:.2%}')
            c[2].metric('Exact annual FX log contribution',f'{s["fx_log"]*100:+.2f} log pp')
            explain('Currency')
            for key,fig in figs(['fx_attribution','fx_rolling']).items():
                _plot(fig,key)
            for asset,frame in result['lens_fx_annual'].items():
                st.markdown(f'### {display_label(asset)} · exact attribution')
                _table(frame,frame.columns)
            with st.expander('Original USD/INR attribution and FX regimes'):
                _table(result['fx_annual'],result['fx_annual'].columns.difference(['USDINR_start','USDINR_end']))
                _table(result['regimes'])
        elif active==6:
            for key,fig in figs(['drawdowns','volatility','correlation']).items():
                _plot(fig,key)
                explain(key)
            st.markdown('### Home-currency risk metrics')
            _table(result['risk'].loc[pair],['CAGR','Annualized_volatility','Downside_deviation','MAR_annual','Max_drawdown','Ulcer_index','Best_year','Worst_year','Positive_years','Positive_months','Worst_month','Best_month','Historical_monthly_VaR05','Historical_monthly_ES05'])
            with st.expander('Drawdown episodes and correlation tables'):
                _table(result['drawdowns'][result['drawdowns'].Series.isin(pair)],['depth'])
                _table(result['correlations'])
        elif active==7:
            explain('Robustness')
            st.markdown(f'### Non-overlapping {horizon}-year windows')
            _table(result['nonoverlap'][horizon][pair+['Start_date','End_date']],pair)
            st.caption('Partition starts at the selected sample origin; disjoint windows can still share persistent regimes.')
            st.markdown('### Paired moving-block bootstrap')
            if st.button('Run 5,000-replication bootstrap'):
                with st.spinner('Resampling paired equity and FX blocks…'):
                    ci,_,meta=lab.bootstrap(result,horizon,frequency='monthly',block_length=12,replications=5000,seed=42,perspective=perspective)
                st.session_state.bootstrap_result=dict(ci=ci,meta=meta,key=sample_key)
                st.rerun()
            if valid_bootstrap:
                _table(valid_bootstrap['ci'],['Estimate','Lower','Upper','Confidence'])
                st.caption(valid_bootstrap['meta'].get('caveat',''))
                if valid_bootstrap['meta'].get('warning'):
                    st.warning(valid_bootstrap['meta']['warning'])
            else:
                st.caption('Run the bootstrap to include its intervals in this selected-state HTML, Excel and CSV snapshot.')
        elif active==8:
            explain('Methodology')
            _markup(info_html(METHODOLOGY))
            st.markdown('### Data provenance')
            _table(source_status(lab))
            st.markdown('### Source validation')
            _table(lab.validation)
            error=max(abs(float(v)) for v in lab.identity_errors.values())
            st.success(f'Currency identities pass · maximum numerical error {error:.3g}')
            _glossary()
        elif active==9:
            explain('Export')
            st.markdown('### Download this research snapshot')
            st.caption(f'{perspective} · {result["daily"].index[0]:%d %b %Y} → {result["daily"].index[-1]:%d %b %Y} · {horizon}Y rolling horizon · YTD {"included" if include_ytd else "excluded"}')
            st.download_button('Download Full Interactive HTML Dashboard',downloads['html'],report_filename(),'text/html',type='primary',width='stretch')
            st.download_button('Complete Excel Workbook',downloads['excel'],'NIFTY_SP500_FX_Research.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',width='stretch')
            st.markdown('#### Data and individual figures')
            st.download_button('CSV bundle ZIP',downloads['csv'],'NIFTY_SP500_FX_Tables.zip','application/zip')
            st.download_button('Annual Returns CSV',downloads['annual'],'Annual_Returns.csv','text/csv')
            st.download_button('Individual Interactive Figure HTML ZIP',downloads['figures'],'NIFTY_SP500_FX_Figures.zip','application/zip')
