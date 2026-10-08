from pathlib import Path
from streamlit.testing.v1 import AppTest
from src.glossary import TABS
from src.lenses import LENSES
from src import streamlit_ui as ui


def test_landing_run_transition_three_lenses_all_tabs_and_direct_export(lab,monkeypatch):
    monkeypatch.setattr(ui,'_lab',lambda *args:lab)
    at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'streamlit_app.py'),default_timeout=180).run()
    assert not at.exception
    assert [b.label for b in at.sidebar.button]==['Run Analysis']
    at.sidebar.button[0].click().run()
    assert not at.exception
    assert [t.label for t in at.tabs]==list(TABS)
    assert list(at.radio[0].options)==list(LENSES)
    markup=''.join(x.value for x in at.markdown)
    assert 'primary-grid' in markup and '30 Jun 1999' in markup and '02 Oct 2026' in markup
    assert 'USD native' in markup and 'What this means' in markup
    assert 'Investor Journey' in markup and 'economic home currency' in markup
    assert len(at.code)==0
    # tabs expose their label in session state even before the test API supports clicking them.
    for lens in LENSES:
        at.radio[0].set_value(lens).run()
        assert not at.exception
        at.session_state['research_tabs']='Overview'
        at.run()
        assert 'Investor Journey' in ''.join(x.value for x in at.markdown)
        at.selectbox[0].set_value(10000).run()
        assert '10,000' in ''.join(x.value for x in at.markdown)
        for tab in TABS:
            at.session_state['research_tabs']=tab
            at.run()
            assert not at.exception, (lens,tab,[e.message for e in at.exception])
        assert any(d.label=='Download Full Interactive HTML Dashboard' for d in at.get('download_button'))
        assert any(d.label=='Download Quantitative Research Report (PDF)' for d in at.get('download_button'))
        assert any(d.label=='Download Research Interpretation Report (HTML)' for d in at.get('download_button'))
        assert 'Bootstrap not run for this state' in ''.join(x.value for x in at.markdown)
        assert all('Prepare' not in b.label for b in at.button)
    # A changed date range must not export obsolete bootstrap results.
    at.session_state['bootstrap_result']={'key':('obsolete',),'ci':'PRIVATE_OLD_MARKER','meta':{}}
    at.date_input[0].set_value('2024-01-01').run()
    assert not at.exception


def test_live_failure_is_visible_and_retry_available(monkeypatch):
    def fail(*args):raise ValueError('Provider verification failed')
    monkeypatch.setattr(ui,'_lab',fail)
    at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'streamlit_app.py')).run()
    at.sidebar.button[0].click().run()
    assert not at.exception and at.error
    assert any(b.label=='Retry live retrieval' for b in at.button)
