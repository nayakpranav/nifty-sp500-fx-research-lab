from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from src.config import Config, NIFTY, SP, FX, EURUSD
from src.currency import convert_levels
from src.data_sources import provenance
from src.reporting import ResearchLab
from src.validation import validate_series


def synthetic_lab(root=Path('.')):
    """Explicit synthetic test data; never a production data fallback."""
    dates = pd.bdate_range('1999-06-30','2026-10-02')
    rng=np.random.default_rng(42)
    noise=rng.normal(0,.008,(len(dates),4))
    increments=noise + np.array([.00048,.00036,.00011,.000015])
    values=np.exp(np.cumsum(increments,axis=0))*[100,100,45,1.05]
    raw={key:pd.Series(values[:,i],index=dates,name=key) for i,key in enumerate((NIFTY,SP,FX,EURUSD))}
    metadata={NIFTY:dict(index_name='NIFTY 50 Total Return Index',currency='INR',return_type='total_return'),
        SP:dict(index_name='S&P 500 Total Return',currency='USD',return_type='total_return',ticker='^SP500TR'),
        FX:dict(currency='INR',units='INR per USD',base='USD',quote='INR',ticker='DEXINUS'),
        EURUSD:dict(currency='USD',units='USD per EUR',base='EUR',quote='USD',ticker='DEXUSEU',direction_evidence='U.S. Dollars to One Euro')}
    for key,meta in metadata.items():
        meta.update(source='Synthetic QA fixture',source_url='https://example.com/synthetic',identity_evidence='synthetic',
            retrieval_timestamp='2026-10-07T00:00:00Z',cache_status='synthetic test only',sha256='test-fixture')
    daily=convert_levels(pd.DataFrame(raw))
    audit=pd.DataFrame({key:dates for key in raw},index=dates)
    validation=pd.concat([validate_series(raw[k],metadata[k],now='2026-10-07') for k in raw],ignore_index=True)
    lab=ResearchLab(daily,audit,metadata,validation,Config(root=root))
    lab.provenance=provenance(raw,metadata)
    return lab


@pytest.fixture(scope='session')
def lab(tmp_path_factory):
    return synthetic_lab(tmp_path_factory.mktemp('lab'))
