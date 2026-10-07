import numpy as np
import pandas as pd
import pytest
from src.app_service import build_lab, COMPARISON_START
from src.config import REQUIRED,NIFTY,SP,FX,EURUSD
from src.currency import convert_levels
from src.transforms import align_daily,calendar_returns,normalize
from src.lenses import LENSES,lens_pair
from src.metrics import cagr,drawdowns
from src.rolling import rolling_cagr,excess_summary,window_indices
from src.statistics import block_bootstrap
from src.interpretation import build_overview_interpretation,lens_statistics
from src.validation import DataError


@pytest.mark.parametrize('lens',LENSES)
def test_every_pair_dependent_statistic_uses_home_currency(lab,lens):
    result=lab.analyze(include_ytd=True,perspective=lens)
    a,b=lens_pair(lens)
    r=result['rolling'][10]
    assert result['probability'].loc[10,'SP_wins']==pytest.approx(excess_summary(r,lens).SP_wins)
    for table in (result['holding'],result['endpoints']):
        row=table.iloc[0]
        actual=cagr(result['daily'].loc[row.Start_date],result['daily'].loc[row.End_date],row.Start_date,row.End_date)
        assert row.Difference==pytest.approx(actual[b]-actual[a],abs=1e-14)
    np.testing.assert_allclose(result['risk'].loc[a,'Max_drawdown'],drawdowns(result['daily'][a]).min())
    first=result['annual'].iloc[0]
    assert ('S&P' if first[b]>first[a] else 'NIFTY') in first.Winner
    assert result['annual'].index[-1]=='2026 YTD'
    assert '2026 YTD' not in lab.analyze(include_ytd=False,perspective=lens)['annual'].index


@pytest.mark.parametrize('lens',LENSES)
def test_bootstrap_estimates_match_exact_paired_rolling_result(lab,lens):
    result=lab.analyze(perspective=lens)
    ci,sims,meta=block_bootstrap(result['daily'],10,replications=40,perspective=lens)
    e=excess_summary(result['rolling'][10],lens)
    for name,target in [('Mean_excess_CAGR',e.Mean_advantage),('Median_excess_CAGR',e.Median_advantage),('Probability_SP_wins',e.SP_wins)]:
        assert ci.loc[ci.Statistic==name,'Estimate'].iloc[0]==pytest.approx(target,abs=1e-12)
    repeated=block_bootstrap(result['daily'],10,replications=40,perspective=lens)[1]
    pd.testing.assert_frame_equal(sims,repeated)


def test_four_source_common_sample_and_no_future_alignment():
    dates=pd.bdate_range('1999-06-29','1999-07-12')
    raw={k:pd.Series(np.arange(len(dates))+v,index=dates,name=k) for k,v in zip(REQUIRED,[100,100,50,1])}
    raw[EURUSD]=raw[EURUSD].loc['1999-06-30':'1999-07-09']
    raw[SP]=raw[SP].drop(pd.Timestamp('1999-07-01'))
    daily,audit=align_daily(raw)
    assert daily.index[0]==COMPARISON_START
    assert daily.index[-1]==pd.Timestamp('1999-07-09')
    assert audit.loc['1999-07-01',SP]==COMPARISON_START
    assert (audit.le(pd.Series(audit.index,index=audit.index),axis=0)).all().all()


def test_unfillable_gap_rejected():
    dates=pd.bdate_range('2020-01-01','2020-03-01')
    raw={k:pd.Series(100.,index=dates,name=k) for k in REQUIRED}
    raw[EURUSD]=raw[EURUSD].drop(dates[10:25])
    with pytest.raises(DataError,match='interior gap'):align_daily(raw)


def test_public_start_is_fixed_or_fails_closed(lab,tmp_path,monkeypatch):
    raw={k:lab.daily[k] for k in REQUIRED}
    monkeypatch.setattr('src.app_service.load_sources',lambda config:(raw,lab.metadata,lab.validation))
    actual=build_lab(tmp_path)
    assert actual.daily.index[0]==COMPARISON_START
    raw[EURUSD]=raw[EURUSD].loc['1999-07-01':]
    with pytest.raises(DataError,match='30 June 1999'):build_lab(tmp_path)


def test_calendar_anniversary_leap_year_and_equal_start(lab):
    dates=pd.date_range('2019-02-28','2021-02-28',freq='ME')
    starts,ends=window_indices(dates,1)
    matches=dict(zip(dates[ends],dates[starts]))
    assert matches[pd.Timestamp('2021-02-28')]==pd.Timestamp('2020-02-29')
    np.testing.assert_allclose(normalize(lab.daily).iloc[0],100)


def test_interpretation_deterministic_lens_specific_and_exact_hurdle(lab):
    texts=[]
    for lens in LENSES:
        r=lab.analyze(perspective=lens)
        cards=build_overview_interpretation(r,10,lens)
        assert cards==build_overview_interpretation(r,10,lens)
        assert len(cards)==5 and cards[-1].caution
        texts.append(cards[1].text)
        s=lens_statistics(r,lens)
        assert np.log1p(s['translated_cagr'])==pytest.approx(np.log1p(s['local_cagr'])+s['fx_log'],abs=1e-14)
        if s['nifty_required_local'] is not None:
            assert (1+s['nifty_required_local'])/(1+s['fx_cagr'])-1==pytest.approx(s['sp_cagr'],abs=1e-14)
    assert len(set(texts))==3 and 'EUR savings → INR → NIFTY → EUR' in texts[-1]


def test_short_range_no_invented_windows(lab):
    r=lab.analyze(start='2024-01-01',perspective=LENSES[2])
    cards=build_overview_interpretation(r,20,LENSES[2])
    assert cards[2].highlight=='Insufficient history'
    assert r['rolling'][20].empty
