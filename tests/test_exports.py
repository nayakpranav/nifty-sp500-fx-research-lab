from io import BytesIO
import json
import zipfile
import re
import numpy as np
import pandas as pd
import pytest
from bs4 import BeautifulSoup
from src.html_report import build_html_report,report_filename
from src.visualizations import figure_set
from src.app_service import excel_bytes,csv_bundle_bytes,figure_bundle_bytes
from src.glossary import TABS
from src.lenses import LENSES,lens_pair
from src.labels import display_label
from src.theme import TOKENS
from src.investor_journey import lens_definition
from src.interpretation import build_tab_interpretations


@pytest.mark.parametrize('lens',LENSES)
def test_standalone_report_state_tabs_and_safe_metadata(lab,lens):
    r=lab.analyze(start='2001-01-01',include_ytd=False,perspective=lens)
    figures=figure_set(r,horizon=5,perspective=lens,capital=10000,log=False)
    lab.metadata['QA_private']={'secret_token':'PRIVATE_MARKER','local_path':'C:\\PRIVATE\\file'}
    try:
        report=build_html_report(r,lab,figures,horizon=5,perspective=lens,capital=10000,log=False,include_ytd=False,
            selected_start='2001-01-01',selected_end='2026-10-02')
    finally:
        lab.metadata.pop('QA_private')
    text=report.decode()
    soup=BeautifulSoup(text,'html.parser')
    assert [x.text for x in soup.select('[role=tab]')]==list(TABS)
    assert len(soup.select('[role=tabpanel]'))==len(TABS)
    state=json.loads(soup.select_one('#analysis-state').text)
    assert state['investor_lens']==lens and state['rolling_horizon_years']==5
    assert state['include_ytd'] is False and state['selected_start']=='2001-01-01'
    assert state['actual_start']==str(r['daily'].index[0].date())
    assert state['starting_wealth']==10000 and state['logarithmic_wealth_axis'] is False
    assert not soup.select('script[src],link[href],iframe')
    assert 'Plotly.newPlot' in text and text.count('plotly.js v')==1
    assert "modeBarButtonsToRemove:['sendChartToCloud']" in text
    assert 'addEventListener(\'click\'' in text and 'ArrowRight' in text
    assert len(soup.select('.plot-target'))==15
    assert len(soup.select('.dense-figure'))==3
    assert 'min-width:850px' in text and 'scroll the matrix horizontally' in soup.get_text()
    for prohibited in ['PRIVATE_MARKER','C:\\PRIVATE','localhost','127.0.0.1','_stcore','streamlit:8501']:
        assert prohibited not in text
    assert soup.select_one('.primary-grid').select('.kpi-card').__len__()==5
    assert len(soup.select('.interpretation-card'))>=5
    assert '1999-06-30' in text and '#060913' in text
    assert len(report)>4_000_000
    assert 'Investor Journey' in soup.get_text()
    assert lens_definition(lens) in soup.get_text()
    cards=build_tab_interpretations(r,5,lens,10000,False)
    for name in ['Wealth','Annual Returns','Rolling Returns','Outperformance','Currency','volatility','correlation','drawdowns','holding_matrix','endpoints']:
        assert cards[name][0].text in soup.get_text()
    assert 'INR-based Investor' in text and 'USD-based Investor' in text and 'EUR-based Investor' in text
    assert state['bootstrap_inference_included'] is False


def test_all_figures_dark_labels_accessible_and_multihorizon(lab):
    lens=LENSES[2]
    r=lab.analyze(perspective=lens,include_ytd=True)
    figures=figure_set(r,perspective=lens)
    pair=lens_pair(lens)
    for fig in figures.values():
        assert fig.layout.paper_bgcolor==TOKENS['panel']
        assert fig.layout.plot_bgcolor==TOKENS['panel']
        for trace in fig.data:
            assert not re.search(r'NIFTY_TRI_|SP500_TR_',str(trace.name))
    multi=figures['multi_horizon']
    assert len(multi.data)==8
    assert {t.yaxis for t in multi.data}=={'y','y2','y3','y4'}
    assert {t.name for t in multi.data}==set(map(display_label,pair))
    assert {t.line.dash for t in multi.data}=={'solid','dash'}
    heatmap=figures['annual'].data[0]
    assert '2026 YTD' in heatmap.y and heatmap.zmid==0
    assert heatmap.texttemplate=='%{text}'
    assert 650<=figures['annual'].layout.height<=720
    for key in ['wealth','rolling','multi_horizon','volatility','correlation']:
        fig=figures[key]
        assert fig.layout.title.yanchor=='top'
        assert fig.layout.legend.yanchor=='bottom' and fig.layout.legend.y==1.04
        assert fig.layout.margin.t==135
    assert 'Limited independent long-horizon evidence' in str(figures['probability'].data[0].customdata)
    for component in ['Native equity','FX contribution','Home-currency total']:
        assert len({trace.line.color for trace in figures['fx_rolling'].data if trace.name==component})==1


def test_excel_csv_figure_exports_retained_and_current(lab):
    r=lab.analyze(perspective=LENSES[2],include_ytd=True)
    workbook=pd.ExcelFile(BytesIO(excel_bytes(r,lab)))
    assert {'Daily_Levels','Source_Dates','Rolling_20Y','Nonoverlap_10Y','FX_Regimes','Home_FX_Annual_2'}.issubset(workbook.sheet_names)
    state=pd.read_excel(workbook,'Analysis_State')
    assert state.Investor_lens.iloc[0]==LENSES[2]
    with zipfile.ZipFile(BytesIO(csv_bundle_bytes(r,lab))) as archive:
        assert 'Annual_Returns.csv' in archive.namelist()
        assert b'NIFTY_TRI_EUR' in archive.read('Annual_Returns.csv')
    f=figure_set(r,perspective=LENSES[2],only=['multi_horizon'])
    with zipfile.ZipFile(BytesIO(figure_bundle_bytes(f))) as archive:
        assert archive.namelist()==['multi_horizon.html']
        assert b'Plotly.newPlot' in archive.read('multi_horizon.html')


def test_dynamic_filename():
    assert report_filename(pd.Timestamp('2026-10-07'))=='2026-10-07_NIFTY_SP500_FX_Research_Lab.html'


def test_matching_bootstrap_is_automatically_embedded_and_indicated(lab):
    lens=LENSES[2]
    r=lab.analyze(perspective=lens)
    ci,_,meta=lab.bootstrap(r,10,replications=20,perspective=lens)
    soup=BeautifulSoup(build_html_report(r,lab,figure_set(r,perspective=lens),perspective=lens,
        bootstrap=ci,bootstrap_meta=meta),'html.parser')
    assert json.loads(soup.select_one('#analysis-state').text)['bootstrap_inference_included'] is True
    assert 'Bootstrap inference included' in soup.get_text()
    assert 'Mean_excess_CAGR' in soup.get_text()
    assert 'Bootstrap has not been run for this selected sample' not in soup.get_text()
