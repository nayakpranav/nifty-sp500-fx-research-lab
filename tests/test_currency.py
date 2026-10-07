import numpy as np
import pandas as pd
import pytest
from src.config import NIFTY, SP, FX, EURUSD, EURINR, NIFTY_EUR, SP_EUR, SP_INR, NIFTY_USD
from src.currency import convert_levels, validate_identities, lens_attribution
from src.fred import verify_eurusd_metadata
from src.validation import DataError, validate_series
from src.lenses import LENSES, canonical_lens
from src.data_sources import fred_eurusd


def known_levels():
    return pd.DataFrame({NIFTY:[100.,120.,108.], SP:[200.,220.,264.],
        FX:[50.,60.,54.], EURUSD:[1.2,1.5,1.35]}, index=pd.bdate_range('2020-01-01',periods=3))


def test_known_cross_rate_and_both_eur_conversions():
    levels=convert_levels(known_levels())
    np.testing.assert_allclose(levels[EURINR],[60,90,72.9],rtol=1e-14)
    r=levels.pct_change().iloc[1]
    assert r[NIFTY_EUR] == pytest.approx(-.2,abs=1e-14)
    assert r[SP_EUR] == pytest.approx(-.12,abs=1e-14)
    assert max(validate_identities(levels).values()) < 1e-14


def test_existing_inr_usd_regressions():
    r=convert_levels(known_levels()).pct_change().iloc[1]
    assert r[SP_INR] == pytest.approx(.32,abs=1e-14)
    assert r[NIFTY_USD] == pytest.approx(0,abs=1e-14)
    assert 1+r[SP_INR] == pytest.approx((1+r[SP])*(1+r[FX]),abs=1e-14)
    assert 1+r[NIFTY_USD] == pytest.approx((1+r[NIFTY])/(1+r[FX]),abs=1e-14)


@pytest.mark.parametrize('lens',LENSES)
def test_exact_log_attribution(lens):
    r=convert_levels(known_levels()).pct_change().dropna()
    for frame in lens_attribution(r,lens).values():
        np.testing.assert_allclose(frame.Total_log,frame.Equity_log+frame.Currency_log,atol=1e-14)


def test_metadata_requires_actual_units_field():
    good='<h1>DEXUSEU</h1><div>Units:</div><span>U.S. Dollars to One Euro, Not Seasonally Adjusted</span>'
    assert verify_eurusd_metadata(good)['units']=='USD per EUR'
    for bad in ['DEXUSEU Units: Euros to One U.S. Dollar','DEXUSEU related series U.S. Dollars to One Euro', 'Units: U.S. Dollars to One Euro']:
        with pytest.raises(DataError): verify_eurusd_metadata(bad)


def test_fred_download_verifies_before_fetching_csv(monkeypatch):
    calls=[]
    class Response:
        def __init__(self,text):self.text=text
        def raise_for_status(self):pass
    def get(url,**kwargs):
        calls.append(url)
        return Response('DEXUSEU Units: U.S. Dollars to One Euro' if '/series/' in url else 'observation_date,DEXUSEU\n2026-10-01,1.12\n2026-10-02,1.13\n')
    monkeypatch.setattr('src.data_sources.requests.get',get)
    series,meta=fred_eurusd()
    assert len(calls)==2 and meta['base']=='EUR' and meta['quote']=='USD'
    np.testing.assert_allclose(series,[1.12,1.13])
    calls.clear()
    monkeypatch.setattr('src.data_sources.requests.get',lambda url,**kwargs:Response('DEXUSEU Units: Euro per USD'))
    with pytest.raises(DataError):fred_eurusd()


def test_metadata_inverse_rejected(lab):
    metadata=dict(lab.metadata[EURUSD],units='EUR per USD',base='USD',quote='EUR')
    report=validate_series(lab.daily[EURUSD],metadata,now='2026-10-07')
    assert 'FAIL' in report.status.values


def test_identity_corruption_detected():
    levels=convert_levels(known_levels())
    levels.iloc[1,levels.columns.get_loc(NIFTY_EUR)]*=1.001
    with pytest.raises(ValueError,match='identities failed'):validate_identities(levels)


def test_unknown_lens_is_not_silently_usd():
    with pytest.raises(ValueError):canonical_lens('JPY-based investor')
