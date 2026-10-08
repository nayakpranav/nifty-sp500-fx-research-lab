from copy import deepcopy
from io import BytesIO
import json
import numpy as np
import pandas as pd
import pytest
from bs4 import BeautifulSoup
from pypdf import PdfReader
from src.config import NIFTY, SP, FX, EURUSD
from src.currency import convert_levels
from src.lenses import LENSES, lens_pair, home_currency
from src.research_synthesis import (build_research_findings, detect_descriptive_crossovers,
    analysis_fingerprint, BOOTSTRAP_UNAVAILABLE)
from src.research_report import build_research_pdf, build_research_html


def known_windows(delta, lens=LENSES[0], first='2010-01-31', horizon=10):
    ends=pd.date_range(first,periods=len(delta),freq='ME')
    a,b=lens_pair(lens)
    return pd.DataFrame({a:.10,b:.10+np.array(delta),
        'Start_date':ends-pd.DateOffset(years=horizon),'End_date':ends},index=ends)


@pytest.fixture
def conflict(lab):
    r=deepcopy(lab.analyze(perspective=LENSES[0]))
    # Known full-sample return ordering, maintaining exact currency identities.
    years=(r['daily'].index-r['daily'].index[0]).days.to_numpy()/365.2425
    primitive=pd.DataFrame({NIFTY:100*1.15**years,SP:100*1.08**years,
        FX:45*1.02**years,EURUSD:1.1*1.01**years},index=r['daily'].index)
    r['daily']=convert_levels(primitive)
    # S&P wins 4/5, median +1 pp, mean -1.2 pp, terminal NIFTY leads.
    r['rolling'][10]=known_windows([.01,.01,-.10,.01,.01])
    return r


def test_full_sample_and_rolling_majority_conflict(conflict):
    f=build_research_findings(conflict)
    assert f.values['nifty_cagr']>f.values['sp_cagr']
    assert f.values['sp_win_fraction']==pytest.approx(.8)
    assert f.values['endpoint_majority_disagree']
    assert 'They disagree' in f.cards[2].text
    assert 'different entry and exit dates' in f.cards[2].text


def test_median_positive_mean_negative_and_majority_magnitude(conflict):
    f=build_research_findings(conflict)
    assert f.values['median_excess_cagr']==pytest.approx(.01)
    assert f.values['mean_excess_cagr']==pytest.approx(-.012)
    assert 'have opposite signs' in f.cards[3].text
    assert 'majority leader S&P 500 differs from the mean leader NIFTY 50' in f.cards[3].text
    assert 'mixed' in f.conclusion


def test_agreement_is_explicit(conflict):
    conflict['rolling'][10]=known_windows([-.01]*8)
    f=build_research_findings(conflict)
    assert 'agree on leadership' in f.cards[2].text
    assert 'agree in sign' in f.cards[3].text


def test_known_crossover_start_and_endpoint():
    x=detect_descriptive_crossovers(known_windows([-.01,-.02,.01,.02]),LENSES[0])
    assert x['reversal_count']==1
    e=x['events'][0]
    assert e['Endpoint']==pd.Timestamp('2010-03-31')
    assert e['Investment_start']==pd.Timestamp('2000-03-31')
    assert e['Previous_endpoint']==pd.Timestamp('2010-02-28')
    assert e['From']=='NIFTY 50' and e['To']=='S&P 500'
    assert e['Before_SP_wins']==0 and e['After_SP_wins']==1
    assert e['Before_windows']==2 and e['After_windows']==2


def test_repeated_crossings_are_not_sustained():
    x=detect_descriptive_crossovers(known_windows([-.01,.01]*8),LENSES[0])
    assert x['reversal_count']==15 and x['sustained']==[]


def test_six_month_persistence():
    x=detect_descriptive_crossovers(known_windows([-.01]*6+[.01]*7),LENSES[0])
    assert [r['Consecutive_months'] for r in x['sustained']]==[6,7]
    assert [r['Leader'] for r in x['sustained']]==['NIFTY 50','S&P 500']


def test_ties_bridge_crossing_but_break_persistence():
    x=detect_descriptive_crossovers(known_windows([-.01]*3+[0,1e-13]+[.01]*3),LENSES[0])
    assert x['reversal_count']==1 and x['sustained']==[]
    assert x['events'][0]['Before_ties']==pytest.approx(2/5)


@pytest.mark.parametrize('gap',['nan','month'])
def test_invalid_or_missing_months_do_not_bridge_crossovers(gap):
    r=known_windows([-.01,-.01,.01,.01])
    if gap=='nan':
        r.iloc[2,r.columns.get_loc(lens_pair(LENSES[0])[1])]=np.nan
    else:
        r=r.drop(r.index[2])
    x=detect_descriptive_crossovers(r,LENSES[0])
    assert x['reversal_count']==0


def test_insufficient_long_horizon(lab):
    r=lab.analyze(start='2025-01-01',perspective=LENSES[1])
    f=build_research_findings(r,20,LENSES[1])
    assert f.values['selected_windows']==0
    assert 'No complete 20Y windows' in f.cards[2].text
    assert f.crossovers[20]['events']==[]
    assert f.crossovers[20]['latest_leader']=='Unavailable'
    assert 'not inferred' not in f.cards[2].text  # Says exactly what is unavailable.


def test_sample_length_and_nonoverlap_warning(lab):
    r=lab.analyze(perspective=LENSES[0])
    f=build_research_findings(r,20)
    text=f.additional_cards['Outperformance'][0].text
    assert 'exceeds half the sample' in text
    assert str(len(r['nonoverlap'][20]))+' disjoint' in text
    assert f.values['horizon_sample_fraction']==pytest.approx(20/f.state['sample_years'])
    assert 'no ordinary binomial' in text


@pytest.mark.parametrize('lens',LENSES)
def test_each_home_currency_and_exact_fx_accounting(lab,lens):
    r=lab.analyze(perspective=lens)
    f=build_research_findings(r,5,lens,10000,lab=lab)
    assert f.state['home_currency']==home_currency(lens)
    for asset in ['nifty','sp']:
        assert np.log1p(f.values[asset+'_cagr'])==pytest.approx(
            np.log1p(f.values[asset+'_native_cagr'])+f.values[asset+'_fx_log'],abs=1e-14)
    assert 'Germany' in f.cards[0].text if home_currency(lens)=='EUR' else 'earn or save' in f.cards[0].text
    assert len(f.provenance)==4


def test_deeper_drawdown_for_high_return_investment(conflict):
    a,b=lens_pair(LENSES[0])
    conflict['risk'].loc[[a,b],'Max_drawdown']=[-.60,-.35]
    f=build_research_findings(conflict)
    assert 'terminal-wealth leader also had the deeper drawdown' in f.cards[5].text
    assert 'co-movement, not superior returns' in f.cards[5].text


def test_currency_translation_changes_ranking(conflict):
    d=conflict['daily']
    years=(d.index-d.index[0]).days.to_numpy()/365.2425
    d=convert_levels(pd.DataFrame({NIFTY:100*1.15**years,SP:100*1.08**years,
        FX:45*1.10**years,EURUSD:1.1},index=d.index))
    conflict['daily']=d
    f=build_research_findings(conflict)
    assert f.values['currency_ranking_changed']
    assert 'Translation changed the native-return ranking' in f.cards[4].text


def test_capital_scaling_and_cagr_unchanged(conflict):
    a=build_research_findings(conflict,capital=100)
    b=build_research_findings(conflict,capital=10000)
    for name in ['nifty','sp']:
        assert b.values[name+'_wealth']==pytest.approx(a.values[name+'_wealth']*100)
        assert b.values[name+'_cagr']==a.values[name+'_cagr']


def test_bootstrap_availability_exact_state_and_staleness(lab):
    r=lab.analyze(perspective=LENSES[2])
    ci,_,meta=lab.bootstrap(r,10,replications=20,perspective=LENSES[2])
    absent=build_research_findings(r,10,LENSES[2])
    assert BOOTSTRAP_UNAVAILABLE in absent.cards[6].text
    f=build_research_findings(r,10,LENSES[2],bootstrap=ci,bootstrap_meta=meta)
    assert f.bootstrap is not None
    assert '20 replications' in f.cards[6].text and '12 monthly' in f.cards[6].text
    assert '95% percentile interval' in f.cards[6].text and 'not predictions' in f.cards[6].text
    stale=lab.analyze(start='2001-01-01',perspective=LENSES[2])
    assert build_research_findings(stale,10,LENSES[2],bootstrap=ci,bootstrap_meta=meta).bootstrap is None
    assert build_research_findings(r,5,LENSES[2],bootstrap=ci,bootstrap_meta=meta).bootstrap is None
    assert analysis_fingerprint(r,10,LENSES[2])!=analysis_fingerprint(r,5,LENSES[2])


@pytest.mark.parametrize('lens',LENSES)
def test_pdf_selectable_state_and_html_parity(lab,lens):
    r=lab.analyze(perspective=lens,include_ytd=True)
    f=build_research_findings(r,10,lens,10000,lab=lab,generated_at='2026-10-08T10:00:00Z')
    pdf=build_research_pdf(r,f)
    reader=PdfReader(BytesIO(pdf))
    assert 6<=len(reader.pages)<=10
    text='\n'.join(p.extract_text() for p in reader.pages)
    for required in [lens,f.state['actual_start'],f.state['actual_end'],'10,000',
        f'{f.values["nifty_cagr"]:.2%}',f'{f.values["sp_cagr"]:.2%}',
        'Full-sample CAGRs','Bootstrap inference was not calculated','Generated UTC','SHA256']:
        assert required in text
    assert '—' not in text
    soup=BeautifulSoup(build_research_html(r,f),'html.parser')
    assert not soup.select('script[src],link[href],iframe')
    assert len(soup.select('img'))==6
    state=json.loads(soup.select_one('#research-evidence').text)
    assert state['values']['sp_wealth']==pytest.approx(f.values['sp_wealth'])
    assert f.conclusion in soup.get_text()
    assert '—' not in soup.get_text()
    assert all(x['raw_last'] in soup.get_text() for x in f.provenance)


def test_report_changes_with_range_lens_and_horizon(lab):
    states=[build_research_findings(lab.analyze(start='2001-01-01',perspective=l),h,l)
        for l,h in [(LENSES[0],5),(LENSES[2],10)]]
    assert states[0].values['sp_wealth']!=states[1].values['sp_wealth']
    assert states[0].state['horizon_years']!=states[1].state['horizon_years']
    assert states[0].values['selected_windows']!=states[1].values['selected_windows']
    assert states[0].state['actual_start']=='2001-01-01'


def test_rejects_mismatched_state(lab):
    r=lab.analyze(perspective=LENSES[0])
    with pytest.raises(ValueError,match='lens must match'):
        build_research_findings(r,perspective=LENSES[2])
    with pytest.raises(ValueError,match='YTD setting'):
        build_research_findings(r,include_ytd=True)


def test_no_new_em_dashes_in_narratives(lab):
    for lens in LENSES:
        f=build_research_findings(lab.analyze(perspective=lens),perspective=lens)
        assert all('—' not in card.text for card in f.cards)
        assert all('—' not in card.text for group in f.additional_cards.values() for card in group)


@pytest.mark.parametrize('horizon',[1,20])
def test_pdf_pagination_with_matching_inference(lab,horizon):
    r=lab.analyze(perspective=LENSES[0])
    ci,_,meta=lab.bootstrap(r,horizon,replications=20,perspective=LENSES[0])
    f=build_research_findings(r,horizon,bootstrap=ci,bootstrap_meta=meta,lab=lab)
    reader=PdfReader(BytesIO(build_research_pdf(r,f)))
    assert 6<=len(reader.pages)<=10
    text=' '.join(p.extract_text() for p in reader.pages)
    assert 'Matching paired moving-block bootstrap' in text
    assert 'Bootstrap inference was not calculated' not in text


def test_pdf_with_insufficient_history(lab):
    r=lab.analyze(start='2025-01-01',perspective=LENSES[2])
    f=build_research_findings(r,20,LENSES[2],lab=lab)
    reader=PdfReader(BytesIO(build_research_pdf(r,f)))
    assert 6<=len(reader.pages)<=10
    assert 'No complete 20Y windows' in ' '.join(p.extract_text() for p in reader.pages)
    soup=BeautifulSoup(build_research_html(r,f),'html.parser')
    evidence=json.loads(soup.select_one('#research-evidence').text,parse_constant=lambda x:pytest.fail('Invalid JSON '+x))
    assert evidence['values']['mean_excess_cagr'] is None
