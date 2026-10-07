import numpy as np
import pandas as pd
import pytest
from src.config import NIFTY, SP, FX, EURINR, EURUSD
from src.lenses import LENSES, lens_pair, home_currency
from src.investor_journey import investor_journey, lens_definition
from src.interpretation import build_tab_interpretations, outperformance_interpretation
from src.presentation import investor_journey_html, primary_kpis_html, source_badge


@pytest.mark.parametrize('lens',LENSES)
def test_journey_routes_account_for_actual_exchange_rates_and_capital(lab,lens):
    r=lab.analyze(perspective=lens)
    j=investor_journey(r,lens,10000)
    scaled=investor_journey(r,lens,100000)
    home=home_currency(lens)
    initial,final=r['daily'].iloc[0],r['daily'].iloc[-1]
    buy={'INR':(10000,10000/initial[FX]),'USD':(10000*initial[FX],10000),
         'EUR':(10000*initial[EURINR],10000*initial[EURUSD])}[home]
    sell={'INR':(1.,final[FX]),'USD':(1/final[FX],1.),'EUR':(1/final[EURINR],1/final[EURUSD])}[home]
    for i,(route,key,converted) in enumerate(zip(j['routes'],(NIFTY,SP),lens_pair(lens))):
        assert route.initial_native==pytest.approx(buy[i])
        assert route.final_native==pytest.approx(buy[i]*final[key]/initial[key])
        assert route.final_home==pytest.approx(route.final_native*sell[i])
        assert route.final_home==pytest.approx(10000*final[converted]/initial[converted])
        assert scaled['routes'][i].final_home==pytest.approx(route.final_home*10)
        assert scaled['routes'][i].home_cagr==route.home_cagr
        assert scaled['routes'][i].native_cagr==route.native_cagr
        assert np.log1p(route.home_cagr)==pytest.approx(np.log1p(route.native_cagr)+route.fx_log,abs=1e-14)
        assert route.steps[0]==f'{home} savings' and route.steps[-1]==f'{home} wealth'
    assert j['wealth_difference']==pytest.approx(j['routes'][0].final_home-j['routes'][1].final_home)
    assert j['percentage_wealth_difference']==pytest.approx(j['wealth_difference']/j['routes'][1].final_home)
    assert j['absolute_wealth_difference']==abs(j['wealth_difference'])
    assert 'economic home currency' in j['definition']
    markup=investor_journey_html(r,lens,10000)
    assert 'Investor Journey' in markup and '10,000' in markup and lens_definition(lens) in markup.replace('&#x27;',"'")


@pytest.mark.parametrize('lens',LENSES)
def test_risk_and_correlation_interpretation_use_the_selected_pair(lab,lens):
    r=lab.analyze(perspective=lens,include_ytd=True)
    cards=build_tab_interpretations(r,10,lens,10000,True)
    a,b=lens_pair(lens)
    corr=r['rolling_correlations'][36][f'{a} vs {b}'].dropna()
    text=cards['correlation'][0].text
    assert f'{corr.iloc[-1]:.3f}' in text
    for value in [corr.median(),corr.min(),corr.max()]:
        assert f'{value:.3f}' in text
    assert 'Correlation does not tell us which market performed better' in text
    vol=r['risk'].loc[[a,b],'Annualized_volatility']
    text=cards['volatility'][0].text
    assert f'{vol.iloc[0]:.2%}' in text and f'{vol.iloc[1]:.2%}' in text
    assert f'{abs(vol.iloc[0]-vol.iloc[1])*100:.2f} pp' in text
    assert 'instability of the return path, not the level of return' in text
    assert 'not future prediction intervals' in cards['Robustness'][0].text
    assert 'YTD is included' in cards['Annual Returns'][0].text
    assert 'descriptive historical statistics, not probabilities' in cards['Annual Returns'][0].text
    assert 'Native INR and USD CAGRs are measured in different units' in cards['Wealth'][0].text


def test_outperformance_counts_and_long_horizon_warning(lab):
    r=lab.analyze(perspective=LENSES[2])
    for horizon in [10,25]:
        row=r['probability'].loc[horizon]
        card=outperformance_interpretation(r,horizon,LENSES[2])
        assert f'{int(row.Windows):,}' in card.text and f'{row.SP_wins:.1%}' in card.text
        assert f'{row.NIFTY_wins:.1%}' in card.text and f'{row.Ties:.1%}' in card.text
        assert f'{row.Mean_advantage*100:+.2f} pp' in card.text
        assert f'{row.Median_advantage*100:+.2f} pp' in card.text
        assert ('Limited independent long-horizon evidence' in card.text)==(horizon==25)
        assert card.caution==(horizon==25)
    assert 'No complete 30-year windows' in outperformance_interpretation(r,30,LENSES[2]).text
    no_sp=r.copy()
    no_sp['probability']=r['probability'].copy()
    no_sp['probability'].loc[25,['SP_wins','NIFTY_wins']]=[0,1]
    assert 'NIFTY produced the higher home-currency CAGR in all observed windows' in outperformance_interpretation(no_sp,25,LENSES[2]).text
    magnitude=r.copy()
    magnitude['probability']=r['probability'].copy()
    magnitude['probability'].loc[10,['SP_wins','NIFTY_wins','Mean_advantage']]=[.6,.4,-.01]
    assert 'S&P won more than half the windows but had negative mean excess CAGR' in outperformance_interpretation(magnitude,10,LENSES[2]).text


def test_complete_dates_unknown_lens_and_invalid_capital_fail_closed(lab):
    r=lab.analyze(perspective=LENSES[0])
    markup=primary_kpis_html(r)
    assert '30 Jun 1999' in markup and '02 Oct 2026' in markup
    for capital in [0,-100,np.nan,np.inf]:
        with pytest.raises(ValueError):investor_journey(r,LENSES[0],capital)
    with pytest.raises(ValueError,match='Unknown investor lens'):investor_journey(r,'JPY-based investor')


def test_short_sample_reports_unavailable_correlation_and_windows(lab):
    r=lab.analyze(start='2025-01-01',perspective=LENSES[1])
    cards=build_tab_interpretations(r,10,LENSES[1],10000,False)
    assert cards['correlation'][0].highlight=='Insufficient history'
    assert cards['Rolling Returns'][0].highlight=='Insufficient history'
    assert 'YTD is excluded' in cards['Annual Returns'][0].text


def test_source_notes_are_distinguished_from_failures_and_real_warnings(lab):
    original=lab.validation
    try:
        lab.validation=pd.DataFrame([dict(series=FX,check='provider absent observations',status='WARNING')])
        assert source_badge(lab,FX,'2026-10-02',now='2026-10-07')==('Validated · data-quality notes','note')
        assert 'stale source warning' in source_badge(lab,FX,'2025-01-01',now='2026-10-07')[0]
        lab.validation.loc[0,'check']='extreme daily moves'
        assert source_badge(lab,FX,'2026-10-02',now='2026-10-07')[1]=='warning'
        lab.validation.loc[0,'status']='FAIL'
        assert source_badge(lab,FX,'2026-10-02',now='2026-10-07')==('Validation failed','error')
    finally:
        lab.validation=original
