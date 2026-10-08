"""Regression tests for Yahoo ^SP500TR quote-summary metadata outages.

The tests use only synthetic yfinance responses, not external network access.
"""
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from src.config import SP
from src.data_sources import yahoo_sp, _sp500tr_identity, SP500TR_ANCHOR_CLOSE
from src.validation import DataError, validate_series


def historical_ohlc(last_close=SP500TR_ANCHOR_CLOSE):
    dates = pd.DatetimeIndex(["2026-10-01", "2026-10-02"], tz="US/Eastern")
    return pd.DataFrame({
        "Open": [17194.28, 17329.88],
        "High": [17234.78, 17393.16],
        "Low": [17084.11, 17272.64],
        "Close": [17194.24, last_close],
    }, index=dates)


def fake_yfinance(monkeypatch, info=None, broken_info=False, close=SP500TR_ANCHOR_CLOSE):
    class Ticker:
        def __init__(self, symbol):
            assert symbol == "^SP500TR", "No S&P price-only substitution"
        def get_info(self):
            if broken_info:
                raise RuntimeError("Yahoo quote-summary temporarily unavailable")
            return info if info is not None else {}
        def history(self, **kwargs):
            assert kwargs["period"] == "max"
            assert kwargs["interval"] == "1d"
            assert kwargs["auto_adjust"] is False
            return historical_ohlc(close)
    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(Ticker=Ticker))


def test_missing_summary_fields_recovered_only_with_verified_anchor(monkeypatch):
    fake_yfinance(monkeypatch, info={})
    series, meta = yahoo_sp()
    assert series.name == SP
    assert meta["ticker"] == "^SP500TR"
    assert meta["index_name"] == "S&P 500 (TR)"
    assert meta["currency"] == "USD"
    assert meta["identity_evidence"] == "verified_provider_anchor"
    assert meta["anchor_checked"] is True
    report = validate_series(series, meta, now="2026-10-08")
    assert not (report.status == "FAIL").any()
    assert (
        (report.check == "Yahoo summary metadata")
        & (report.status == "WARNING")
    ).any()


def test_yahoo_summary_exception_also_recovers_with_anchor(monkeypatch):
    fake_yfinance(monkeypatch, broken_info=True)
    _, meta = yahoo_sp()
    assert meta["identity_evidence"] == "verified_provider_anchor"


def test_complete_provider_metadata_preserves_preferred_identity(monkeypatch):
    fake_yfinance(monkeypatch, info={"longName": "S&P 500 (TR)", "currency": "USD"})
    _, meta = yahoo_sp()
    assert meta["identity_evidence"] == "provider_metadata"
    assert meta["anchor_checked"] is False


@pytest.mark.parametrize("bad_info", [
    {"longName": "S&P 500", "currency": "USD"},
    {"longName": "S&P 500 (TR)", "currency": "EUR"},
    {"longName": "Unrelated Total Return", "currency": "USD"},
])
def test_conflicting_provider_metadata_never_overridden(monkeypatch, bad_info):
    fake_yfinance(monkeypatch, info=bad_info)
    with pytest.raises(DataError, match="conflicting"):
        yahoo_sp()


def test_missing_metadata_plus_wrong_index_level_fails_closed(monkeypatch):
    fake_yfinance(monkeypatch, info={}, close=7000.0)
    with pytest.raises(DataError, match="do not match"):
        yahoo_sp()


def test_anchor_evidence_without_checked_ticker_rejected():
    s = pd.Series([17194.24, SP500TR_ANCHOR_CLOSE],
                  index=pd.to_datetime(["2026-10-01", "2026-10-02"]), name=SP)
    meta = dict(index_name="S&P 500 (TR)", currency="USD",
                return_type="total_return", ticker="^GSPC",
                identity_evidence="verified_provider_anchor", anchor_checked=True)
    report = validate_series(s, meta, now="2026-10-08")
    assert (report.status == "FAIL").any()
