"""Academic PDF and self-contained research HTML from one findings object.

ReportLab and Agg matplotlib work on Community Cloud without a browser.
Rendering is invoked lazily by the Export tab, never by Run Analysis.
"""
from base64 import b64encode
from html import escape
from io import BytesIO
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib import dates as mdates
from .lenses import lens_pair
from .labels import display_label
from .html_report import METHODOLOGY
from .glossary import GLOSSARY
from .interpretation import build_tab_interpretations

TITLE = 'NIFTY 50 vs S&P 500: Total Returns, Currency Translation and Historical Investor Outcomes'
LIMITATIONS = ('Historical index returns are not implementable fund returns. Taxes, brokerage, fund expenses, '
    'tracking error, FX conversion charges and remittance fees are excluded. Indian and US closes are asynchronous. '
    'FX observations can lag equity observations; bounded as-of values are past observations, not simultaneous executable prices. '
    'Selected dates, endpoint sensitivity and currency paths affect conclusions. Rolling windows overlap, disjoint windows '
    'can share persistent conditions, and long horizons leave few distinct experiences. Crossovers and six-month persistence '
    'are descriptive conventions, not established statistical breaks. Bootstrap requires a stationarity approximation, '
    'cannot capture unobserved future regimes and does not provide guaranteed predictions. No personal investment recommendation is made.')
FRAMEWORK = ('The analysis asks which investment generated greater terminal home-currency wealth, which led most frequently '
    'across historical holding periods, whether translation changed the native-return ranking, and what volatility and drawdowns '
    'accompanied those outcomes. Terminal wealth, win frequency, mean excess and median excess answer different questions. '
    'Every paired excess return means S&P minus NIFTY in the same home currency.')


def _charts(result, findings):
    """A print-friendly subset of the validated result, with shared captions."""
    a,b = lens_pair(findings.state['investor_lens'])
    home, h = findings.state['home_currency'], findings.state['horizon_years']
    daily, r = result['daily'], result['rolling'][h]
    output = []
    palette = ('#2563a6', '#d87924')

    def create(title, ylabel, xlabel='Valuation cutoff'):
        fig = Figure(figsize=(7.1, 2.6), dpi=180, facecolor='white', layout='constrained')
        FigureCanvasAgg(fig)
        ax = fig.subplots()
        ax.set_title(title, loc='left', fontsize=11, color='#112644', pad=9)
        ax.set_ylabel(ylabel, fontsize=9)
        ax.set_xlabel(xlabel, fontsize=8)
        ax.tick_params(labelsize=8)
        ax.grid(axis='y',alpha=.18)
        ax.spines[['top','right']].set_visible(False)
        return fig, ax

    def finish(fig,ax,key,caption,has_dates=True):
        if has_dates:
            ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3,maxticks=6))
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
        handles,_=ax.get_legend_handles_labels()
        if handles:
            ax.legend(loc='best',fontsize=8,frameon=False)
        buf=BytesIO()
        fig.savefig(buf,format='png',dpi=180)
        output.append(dict(key=key, image=buf.getvalue(), caption=f'Figure {len(output)+1}. {caption}'))
        fig.clear()

    fig,ax=create(f'Normalized wealth in {home}','Wealth index (start = 100)')
    for c,name,color in zip((a,b),('NIFTY 50','S&P 500'),palette):
        ax.plot(daily.index,100*daily[c]/daily[c].iloc[0],label=name,color=color,lw=1.5)
    finish(fig,ax,'wealth',f'Equal-start normalized wealth in {home}. The selected capital scales actual wealth, not CAGR. '
        'Both paths include reinvested dividends and bounded asynchronous valuations.')
    fig,ax=create(f'{h}Y rolling CAGRs in {home}','CAGR (%)','Rolling-window endpoint')
    if len(r):
        for c,name,color in zip((a,b),('NIFTY 50','S&P 500'),palette):
            ax.plot(r.index,100*r[c],label=name,color=color,lw=1.5)
    else:
        ax.text(.5,.5,'No complete windows',ha='center',transform=ax.transAxes)
    finish(fig,ax,'rolling',f'{h}Y CAGR by monthly endpoint in {home}. Each point holds from its matched Start_date; endpoints are not entry dates. Windows overlap.')
    fig,ax=create(f'{h}Y paired rolling excess in {home}','S&P minus NIFTY CAGR (pp)','Rolling-window endpoint')
    if len(r):
        ax.plot(r.index,100*(r[b]-r[a]),color=palette[1],lw=1.5)
    else:
        ax.text(.5,.5,'No complete paired windows',ha='center',transform=ax.transAxes)
    ax.axhline(0,color='#526277',lw=.8)
    finish(fig,ax,'excess',f'Positive excess favors S&P; negative favors NIFTY in {home}. Sign changes describe observed leadership reversals, not statistical breaks.')
    fig,ax=create(f'Historical win fractions in {home}','Overlapping windows (%)','Holding period (years)')
    table=pd.DataFrame(findings.horizons)
    table=table.loc[table.Windows>0]
    if len(table):
        for c,name,color in zip(('NIFTY_wins','SP_wins'),('NIFTY 50','S&P 500'),palette):
            ax.plot(table.Horizon,100*table[c],marker='o',label=name,color=color,lw=1.5)
        ax.set_xticks(table.Horizon)
    else:
        ax.text(.5,.5,'No complete standard horizons',ha='center',transform=ax.transAxes)
    ax.set_ylim(0,105)
    finish(fig,ax,'outperformance',f'Historical win fractions at all seven standard horizons in {home}; ties are omitted from the two curves, but retained in the table. No independent-trial or future probability interpretation.',False)
    fig,ax=create(f'Full-sample exact log attribution in {home}','Annual log return (log pp)','Investment')
    v=findings.values
    native=np.log1p([v['nifty_native_cagr'],v['sp_native_cagr']])*100
    fx=np.array([v['nifty_fx_log'],v['sp_fx_log']])*100
    positions=np.array([0,1])
    ax.bar(positions-.24,native,width=.23,color=palette[0],label='Native equity')
    ax.bar(positions,fx,width=.23,color=palette[1],label='FX translation')
    ax.bar(positions+.24,native+fx,width=.23,color='#112644',label='Home-currency total')
    ax.set_xticks([0,1],['NIFTY 50','S&P 500'])
    ax.axhline(0,color='#526277',lw=.8)
    finish(fig,ax,'fx',f'Exact annual log accounting in {home}: native equity plus signed FX translation equals total. Grouped bars preserve the sign of FX drag below zero; arithmetic CAGR gaps do not add exactly.',False)
    fig,ax=create(f'Historical drawdowns in {home}','Drawdown (%)')
    for c,name,color in zip((a,b),('NIFTY 50','S&P 500'),palette):
        ax.plot(daily.index,100*(daily[c]/daily[c].cummax()-1),label=name,color=color,lw=1.2)
    finish(fig,ax,'drawdowns',f'Daily-cutoff peak-to-trough losses in {home}. Recoveries may be censored at the selected endpoint. Observed losses do not bound future drawdowns.')
    return output


def _pct(value, signed=False):
    if value is None or not np.isfinite(value):
        return 'N/A'
    return f'{value:+.2%}' if signed else f'{value:.2%}'


def _report_tables(result, f):
    v,s = f.values,f.state
    a,b=lens_pair(s['investor_lens'])
    performance=[['Investment',f'Ending wealth ({s["home_currency"]})','Home CAGR'],
        ['NIFTY 50',f'{v["nifty_wealth"]:,.2f}',_pct(v['nifty_cagr'])],
        ['S&P 500',f'{v["sp_wealth"]:,.2f}',_pct(v['sp_cagr'])]]
    horizon=[['Years','Windows','S&P wins','Ties','Mean / median excess (pp)','Disjoint']]
    for x in f.horizons:
        mean,median=x['Mean_advantage'],x['Median_advantage']
        horizon.append([str(x['Horizon']),str(int(x['Windows'])),_pct(x['SP_wins']),_pct(x['Ties']),
            f'{mean*100:+.2f} / {median*100:+.2f}' if x['Windows'] else 'N/A',str(x['Nonoverlap_windows'])])
    risk=[['Metric','NIFTY 50','S&P 500']]
    for c,title,percent in [('Annualized_volatility','Monthly annualized volatility',True),
        ('Max_drawdown','Maximum drawdown',True),('Downside_deviation','Annualized downside deviation',True),
        ('Calmar','Calmar ratio',False),('Sortino','Sortino ratio (zero target)',False),
        ('Historical_monthly_VaR05','Historical monthly 5% VaR',True),('Historical_monthly_ES05','Historical monthly 5% ES',True)]:
        vals=result['risk'].loc[[a,b],c]
        risk.append([title]+[_pct(z) if percent else f'{z:.3f}' if np.isfinite(z) else 'N/A' for z in vals])
    sources=[['Source','Latest raw observation','Used at selected endpoint']]
    for p in f.provenance:
        sources.append([display_label(p['series']),p['raw_last'],p['endpoint_observation']])
    crossing=[['Years','Reversals','Sustained runs','Latest endpoint leader']]
    for x in f.horizons:
        crossing.append([str(x['Horizon']),str(x['Reversals']) if x['Windows'] else 'N/A',
            str(x['Sustained_sequences']) if x['Windows'] else 'N/A',x['Latest_leader']])
    return dict(performance=performance,horizons=horizon,risk=risk,sources=sources,crossovers=crossing)


def _narrative(result,f):
    s=f.state
    return build_tab_interpretations(result,s['horizon_years'],s['investor_lens'],s['starting_wealth'],
        s['include_ytd'],f.bootstrap,research_findings=f)


def build_research_pdf(result, findings):
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import HexColor, white
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    # Matplotlib distributes these open fonts on every supported platform.
    fonts=Path(matplotlib.get_data_path())/'fonts/ttf'
    for name,file in [('ResearchSans','DejaVuSans.ttf'),('ResearchSansBold','DejaVuSans-Bold.ttf')]:
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name,str(fonts/file)))
    pdfmetrics.registerFontFamily('ResearchSans',normal='ResearchSans',bold='ResearchSansBold')
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='ResearchBody',fontName='ResearchSans',fontSize=9,leading=13.4,
        textColor=HexColor('#29394c'),spaceAfter=7))
    styles.add(ParagraphStyle(name='ResearchHeading',fontName='ResearchSansBold',fontSize=17,leading=22,
        textColor=HexColor('#112644'),spaceAfter=13))
    styles.add(ParagraphStyle(name='ResearchSmall',fontName='ResearchSans',fontSize=7.4,leading=10.2,
        textColor=HexColor('#526277'),spaceAfter=5,wordWrap='CJK'))
    styles.add(ParagraphStyle(name='ResearchTitle',fontName='ResearchSansBold',fontSize=25,leading=33,
        textColor=HexColor('#112644'),spaceAfter=22))
    styles.add(ParagraphStyle(name='ResearchCell',fontName='ResearchSans',fontSize=8,leading=11,
        textColor=HexColor('#29394c'),spaceAfter=0))
    s=findings.state
    plots={x['key']:x for x in _charts(result,findings)}
    tables=_report_tables(result,findings)
    narratives=_narrative(result,findings)
    story=[]
    width=487.3

    def p(text,style='ResearchBody'):
        return Paragraph(escape(str(text)).replace('\n','<br/>'),styles[style])

    def add(text,style='ResearchBody'):
        story.append(p(text,style))

    def heading(text):
        add(text,'ResearchHeading')

    def table(key,widths=None):
        cells=[[p(x,'ResearchCell') for x in row] for row in tables[key]]
        tab=Table(cells,colWidths=widths or [width/len(cells[0])]*len(cells[0]),repeatRows=1,hAlign='LEFT')
        tab.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),HexColor('#e8eef6')),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[white,HexColor('#f6f8fb')]),
            ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),
            ('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),5),
            ('BOTTOMPADDING',(0,0),(-1,-1),5),('LINEBELOW',(0,0),(-1,0),.6,HexColor('#bfcbda'))]))
        story.extend([tab,Spacer(1,12)])

    def chart(key,height=178):
        plot=plots[key]
        story.append(KeepTogether([Image(BytesIO(plot['image']),width=width,height=height),p(plot['caption'],'ResearchSmall')]))

    def page():
        story.append(PageBreak())

    add('QUANTITATIVE RESEARCH REPORT','ResearchSmall')
    add(TITLE,'ResearchTitle')
    heading(s['investor_lens'])
    add(f'Selected sample: {s["actual_start"]} to {s["actual_end"]}\nSelected holding period: {s["horizon_years"]} years\n'
        f'Starting wealth: {s["currency_symbol"]}{s["starting_wealth"]:,.0f} ({s["home_currency"]})\n'
        f'YTD: {"included" if s["include_ytd"] else "excluded"}\nGenerated UTC: {s["generated_at"]}')
    heading('Abstract')
    add(findings.cards[1].text+' '+findings.cards[2].text+' '+
        ('Matching bootstrap inference is included.' if findings.bootstrap is not None else 'The analysis is descriptive; no matching bootstrap inference was calculated.'))
    heading('1. Introduction and research motivation')
    add(findings.cards[0].text)
    heading('2. Questions and analytical framework')
    add(FRAMEWORK)
    page()
    heading('3. Data and methodology')
    add(METHODOLOGY)
    table('sources',[width*.46,width*.27,width*.27])
    add(f'Raw observation dates above are provider sessions. The selected endpoint ({s["actual_end"]}) is a bounded backward-as-of valuation cutoff. '
        f'The full validated panel ends {s["common_validated_cutoff"]}. The selected endpoint may be earlier. '
        f'As-of tolerance: {s["asof_tolerance_days"]} calendar days; rolling anniversary tolerance: {s["rolling_tolerance_days"]} days. '
        'No future observations or unknown-gap bridges are used.')
    add('CAGR = (ending level / starting level)^(365.2425 / elapsed days) − 1. Home-currency wealth = starting capital × home-currency level ratio. '
        'FX attribution uses logarithms of gross annualized returns. Each rolling observation records its actual matched investment Start_date and End_date.')
    if findings.validation_notes:
        add('Source validation notes','ResearchHeading')
        for note in findings.validation_notes:
            add(' · '.join(str(note.get(k,'')) for k in ('series','check','status','detail')),'ResearchSmall')
    else:
        add('No non-PASS source validation notes are present in this snapshot.','ResearchSmall')
    page()
    heading('4. Results: wealth and endpoint dependence')
    table('performance',[width*.34,width*.4,width*.26])
    chart('wealth')
    add(findings.cards[1].text)
    add(findings.additional_cards['Wealth'][0].text)
    add(narratives['endpoints'][0].text)
    heading('Calendar-year evidence')
    add(narratives['Annual Returns'][0].text)
    add(findings.additional_cards['Annual Returns'][0].text)
    page()
    heading('4.1 Rolling outcomes and paired excess')
    chart('rolling',155)
    chart('excess',155)
    add(findings.cards[2].text)
    add(findings.cards[3].text)
    add(findings.additional_cards['Rolling Returns'][0].text,'ResearchSmall')
    page()
    heading('4.2 Holding horizons and changing leadership')
    chart('outperformance',145)
    table('horizons',[38,57,69,52,209,62.3])
    table('crossovers',[40,65,85,297.3])
    add(findings.additional_cards['Rolling Returns'][1].text)
    add(findings.additional_cards['Outperformance'][0].text,'ResearchSmall')
    page()
    heading('4.3 Currency translation and investor outcomes')
    chart('fx',190)
    add(findings.cards[4].text)
    add(narratives['Currency'][0].text)
    heading('Economic routes')
    home=s['home_currency']
    if home=='EUR':
        add('€ → ₹ → NIFTY 50 → ₹ → €\n€ → $ → S&P 500 → $ → €')
        add('For an investor earning and saving in Germany or elsewhere in the euro area, these are euro-denominated wealth paths. Intermediate conversion currencies do not define a separate investor lens.')
    elif home=='USD':
        add('$ → ₹ → NIFTY 50 → ₹ → $\n$ → S&P 500 → $')
    else:
        add('₹ → NIFTY 50 → ₹\n₹ → $ → S&P 500 → $ → ₹')
    page()
    heading('5. Risk analysis')
    chart('drawdowns',190)
    table('risk',[width*.58,width*.21,width*.21])
    add(findings.cards[5].text)
    add(narratives['drawdowns'][0].text,'ResearchSmall')
    add(narratives['correlation'][0].text,'ResearchSmall')
    page()
    heading('6. Robustness and uncertainty')
    add(findings.cards[6].text)
    if findings.bootstrap is not None:
        tables['bootstrap']=[['Statistic','Confidence','Estimate','Lower','Upper']]
        for _,x in findings.bootstrap.iterrows():
            tables['bootstrap'].append([display_label(x.Statistic),f'{x.Confidence:.0%}',
                f'{x.Estimate*100:+.2f}',f'{x.Lower*100:+.2f}',f'{x.Upper*100:+.2f}'])
        table('bootstrap',[width*.44,width*.14,width*.14,width*.14,width*.14])
        add('Units: win fractions in percent; excess CAGRs in percentage points. Terminal_H_CAGR_difference is the last selected-H rolling endpoint, not the full-sample CAGR gap.','ResearchSmall')
    else:
        add('No confidence interval table is presented because no matching inference is available.','ResearchSmall')
    a,b=lens_pair(s['investor_lens'])
    disjoint=result['nonoverlap'][s['horizon_years']]
    tables['disjoint']=[['Investment start','Endpoint','NIFTY CAGR','S&P CAGR']]
    # At 1Y there can be 27 disjoint rows. Keep the report concise; full data stays in exports.
    disjoint_display = 3 if findings.bootstrap is not None else 6
    for _,x in disjoint.tail(disjoint_display).iterrows():
        tables['disjoint'].append([f'{x.Start_date:%Y-%m-%d}',f'{x.End_date:%Y-%m-%d}',_pct(x[a]),_pct(x[b])])
    if len(disjoint):
        heading('Disjoint holding intervals')
        table('disjoint')
        add(f'Showing the latest {min(disjoint_display,len(disjoint))} of {len(disjoint)} non-overlapping intervals. Complete intervals remain in the Excel, CSV and interactive dashboard exports.','ResearchSmall')
    add('Statistical scope','ResearchHeading')
    add('The persistence convention is six consecutive monthly endpoints with the same non-tied leader. Ties reset a sustained run; gaps or invalid values reset both run and crossover histories. '
        'All before/after win fractions retain ties in their denominators. No crossing date is interpolated. Neither a crossing nor a sustained run establishes an economic regime change. '
        'No ordinary binomial confidence interval treats rolling windows as independent. Source validation failures remain fatal in the live pipeline.')
    page()
    heading('7. Discussion')
    add(findings.additional_cards['Wealth'][0].text)
    add(findings.cards[3].text)
    add(findings.additional_cards['Rolling Returns'][1].text)
    heading('8. Conditional historical conclusion')
    add(findings.conclusion)
    heading('9. Limitations')
    add(LIMITATIONS)
    page()
    heading('10. Appendix: definitions and reproducibility')
    for key in ['CAGR','Excess CAGR','Overlapping Windows','Maximum Drawdown','Volatility','Correlation','Block Bootstrap']:
        add(f'{key}: {GLOSSARY[key]}','ResearchSmall')
    add('Analysis state','ResearchHeading')
    for key in ['selected_start','selected_end','actual_start','actual_end','common_validated_cutoff','canonical_start',
        'horizon_years','sample_years','starting_wealth','include_ytd','valuation_cutoffs','generated_at','tie_tolerance','analysis_fingerprint']:
        add(f'{key}: {s[key]}','ResearchSmall')
    add('Public source provenance','ResearchHeading')
    for source in findings.provenance:
        add(f'{display_label(source["series"])}: {source["source"]}. {source["url"]}\n'
            f'Raw coverage {source["raw_first"]} to {source["raw_last"]}; retrieved {source["retrieval_utc"]}; identity {source["identity_evidence"]}.\n'
            f'SHA256: {source["sha256"]}','ResearchSmall')
    add('The fingerprint hashes the selected daily panel together with its exact lens, dates and horizon. Source hashes identify raw provider snapshots. '
        'The repository records calculation and validation policies; full underlying tables and source-date audit are retained by the existing exports.','ResearchSmall')
    stream=BytesIO()
    doc=SimpleDocTemplate(stream,pagesize=(595.3,841.9),rightMargin=54,leftMargin=54,topMargin=49,bottomMargin=47,
        title=TITLE,author='NIFTY × S&P × FX Research Lab')

    def furniture(c,document):
        c.setFillColor(HexColor('#526277'))
        c.setFont('ResearchSans',7)
        c.drawString(54,819,'NIFTY 50 × S&P 500 × FX | Quantitative Research')
        c.drawString(54,27,f'{s["home_currency"]} lens | {s["actual_start"]} to {s["actual_end"]} | Historical evidence')
        c.drawRightString(541.3,27,f'{document.page}')
    doc.build(story,onFirstPage=furniture,onLaterPages=furniture)
    return stream.getvalue()


def build_research_html(result, findings):
    """Same evidence, tables and scientific figures, with no external assets."""
    f,s=findings,findings.state
    tables=_report_tables(result,f)
    narratives=_narrative(result,f)
    charts=_charts(result,f)

    def table(key):
        rows=tables[key]
        return '<div class="table-wrap"><table><thead><tr>'+''.join(f'<th>{escape(str(x))}</th>' for x in rows[0])+'</tr></thead><tbody>'+''.join(
            '<tr>'+''.join(f'<td>{escape(str(x))}</td>' for x in row)+'</tr>' for row in rows[1:])+'</tbody></table></div>'

    def p(text):
        return f'<p>{escape(str(text))}</p>'

    def section(title,text):
        return f'<section><h2>{escape(title)}</h2>{text}</section>'

    def chart(key):
        x=next(x for x in charts if x['key']==key)
        return f'<figure><img alt="{escape(x["caption"])}" src="data:image/png;base64,{b64encode(x["image"]).decode()}"><figcaption>{escape(x["caption"])}</figcaption></figure>'

    body=section('Abstract',p(f.cards[1].text)+p(f.cards[2].text))
    body+=section('1. Introduction and research motivation',p(f.cards[0].text))
    body+=section('2. Research questions and analytical framework',p(FRAMEWORK))
    body+=section('3. Data and methodology',p(METHODOLOGY)+table('sources')+p(
        f'Raw dates are provider observations. Used observations are bounded backward-as-of values at {s["actual_end"]}; '
        f'the full common validated cutoff is {s["common_validated_cutoff"]}. These dates need not coincide.')+
        ''.join(p(' · '.join(str(x) for x in note.values())) for note in f.validation_notes))
    body+=section('4. Results',table('performance')+chart('wealth')+p(f.cards[1].text)+p(f.additional_cards['Wealth'][0].text)+
        p(narratives['Annual Returns'][0].text)+p(f.additional_cards['Annual Returns'][0].text)+p(narratives['endpoints'][0].text)+
        chart('rolling')+chart('excess')+p(f.cards[2].text)+p(f.cards[3].text)+p(f.additional_cards['Rolling Returns'][0].text)+
        chart('outperformance')+table('horizons')+table('crossovers')+p(f.additional_cards['Rolling Returns'][1].text)+
        chart('fx')+p(f.cards[4].text)+p(narratives['Currency'][0].text))
    body+=section('5. Risk analysis',chart('drawdowns')+table('risk')+p(f.cards[5].text)+p(narratives['drawdowns'][0].text)+p(narratives['correlation'][0].text))
    ci='' if f.bootstrap is None else '<div class="table-wrap">'+f.bootstrap.to_html(index=False,escape=True)+'</div>'
    body+=section('6. Robustness and uncertainty',p(f.cards[6].text)+ci+p('Bootstrap units: estimates and intervals in decimal fractions in the table; narrative excess returns use pp and win fractions use percent.'))
    body+=section('7. Discussion',p(f.additional_cards['Wealth'][0].text)+p(f.cards[3].text)+p(f.additional_cards['Rolling Returns'][1].text))
    body+=section('8. Conditional historical conclusion',p(f.conclusion))
    body+=section('9. Limitations',p(LIMITATIONS))
    body+=section('10. Appendix, glossary and reproducibility','<dl>'+''.join(f'<dt>{escape(k)}</dt><dd>{escape(v)}</dd>' for k,v in GLOSSARY.items())+'</dl>'+p(json.dumps(s,indent=2,ensure_ascii=False))+
        ''.join(p(json.dumps(x,ensure_ascii=False)) for x in f.provenance))
    for h,detail in f.crossovers.items():
        if detail['events'] or detail['sustained']:
            body+=f'<details><summary>{h}Y observed crossovers and sustained sequences</summary>'
            for key in ('events','sustained'):
                body+='<div class="table-wrap">'+pd.DataFrame(detail[key]).to_html(index=False,escape=True)+'</div>'
            body+='</details>'
    state=json.dumps(dict(state=s,values=f.values,units=f.units,conclusion=f.conclusion),default=str,ensure_ascii=False,allow_nan=False).replace('<','\\u003c')
    return ('''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Research Interpretation Report</title><style>
    *{box-sizing:border-box}body{margin:0;background:#060913;color:#dfe7f4;font:16px/1.65 system-ui,sans-serif}
    main{max-width:1050px;margin:auto;padding:44px 24px}header{padding:34px;background:linear-gradient(135deg,#152641,#0c1223);border:1px solid #293b58;border-radius:18px}
    h1{font-size:clamp(26px,4vw,40px);line-height:1.2}h2{font-size:24px;color:#98c2f3}section{margin:32px 0;padding:26px;background:#0c1223;border:1px solid #26354e;border-radius:14px}
    p,dd{overflow-wrap:anywhere}figure{margin:24px 0}img{width:100%;height:auto;border-radius:8px;background:white}figcaption{font-size:13px;color:#a8b7cd}
    table{width:100%;border-collapse:collapse;font-size:13px}td,th{padding:12px;text-align:left;border-bottom:1px solid #29374e}th{color:#98c2f3}.table-wrap{overflow:auto}
    dt{font-weight:700;color:#98c2f3}dd{margin:0 0 14px}details{padding:16px;border:1px solid #29374e;border-radius:10px;margin:12px 0}
    @media(max-width:600px){main{padding:20px 12px}section,header{padding:18px}body{font-size:15px}}
    @media print{body,section,header{background:white;color:#29394c}main{max-width:none}h2,th,dt{color:#112644}section{break-inside:avoid}figcaption{color:#526277}}
    </style></head><body><main><header><p>RESEARCH INTERPRETATION REPORT · HISTORICAL EVIDENCE</p>'''+f'<h1>{escape(TITLE)}</h1>'+p(
        f'{s["investor_lens"]} · {s["actual_start"]} to {s["actual_end"]} · {s["horizon_years"]}Y · '
        f'{s["currency_symbol"]}{s["starting_wealth"]:,.0f} starting wealth · YTD {"included" if s["include_ytd"] else "excluded"} · '
        f'Generated UTC {s["generated_at"]}')+'</header>'+body+f'<script type="application/json" id="research-evidence">{state}</script></main></body></html>').encode('utf-8')
