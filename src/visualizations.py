"""Interactive dark Plotly figures, always explicit about investor currency."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from .config import NIFTY, SP, FX, SP_INR, EURUSD, EURINR
from .transforms import normalize
from .metrics import drawdowns
from .statistics import rolling_volatility
from .lenses import lens_pair, home_currency
from .labels import DISPLAY_LABELS as LABELS, display_label
from .theme import SERIES_COLORS as COLORS, LINE_DASHES, TOKENS, HEATMAP_SCALE, plotly_layout


def _line(x, y, name, percent=True, showlegend=True):
    return go.Scatter(x=x, y=y, mode="lines", name=display_label(name), legendgroup=name,
        showlegend=showlegend, line=dict(color=COLORS.get(name, TOKENS['blue']), width=2.6,
        dash=LINE_DASHES.get(name, 'solid')),
        hovertemplate=('%{x|%d %b %Y}<br>%{y:.2%}' if percent else '%{x|%d %b %Y}<br>%{y:,.2f}') + '<extra>%{fullData.name}</extra>')


def _heatmap(frame, title, percent_points=False, dates=None):
    if frame.empty:
        fig = plotly_layout(go.Figure(), title)
        fig.add_annotation(text="Insufficient history for this selection", showarrow=False)
        return fig
    z = frame.to_numpy(dtype=float) * 100
    finite = z[np.isfinite(z)]
    limit = max(abs(finite).max(), .1) if len(finite) else .1
    # Dense endpoint matrices use rounded cell labels; hover retains exact values.
    label_format = '.0f' if len(frame.columns) > 12 else '+.1f'
    text = np.array([[format(v,label_format) if np.isfinite(v) else '' for v in row] for row in z])
    fig = go.Figure(go.Heatmap(z=z, x=[display_label(c) for c in frame.columns], y=[display_label(i) for i in frame.index],
        zmid=0, zmin=-limit, zmax=limit, colorscale=HEATMAP_SCALE,
        text=text, texttemplate="%{text}", textfont=dict(color=TOKENS['text'], size=12),
        colorbar=dict(title='pp' if percent_points else '%'), customdata=dates,
        hovertemplate='%{y} · %{x}<br>%{z:+.2f}' + (' pp' if percent_points else '%') +
            ('<br>%{customdata}' if dates is not None else '') + '<extra></extra>'))
    fig.update_yaxes(autorange='reversed')
    fig.update_xaxes(tickangle=-35 if len(frame.columns) > 12 else 0)
    return plotly_layout(fig, title, height=max(480, 26 * len(frame) + 220))


def _wealth(result, selected, capital, log, perspective):
    wealth = normalize(result['daily'][list(selected)], capital)
    fig = go.Figure([_line(wealth.index, wealth[c], c, False) for c in selected])
    if log:
        fig.update_yaxes(type='log', tickformat=',.0f')
    return plotly_layout(fig, f'Equal-start total-return wealth · {home_currency(perspective)} lens', f'Wealth from {capital:,.0f}')


def _annual(result, perspective):
    cols = list(dict.fromkeys((*lens_pair(perspective), NIFTY, SP, SP_INR, FX, EURUSD, EURINR)))
    # Years down the page keep numeric cells legible at ordinary laptop widths.
    fig = _heatmap(result['annual'][cols], f'Calendar-year total returns · {home_currency(perspective)} lens')
    fig.update_xaxes(tickmode='array',tickvals=[display_label(c) for c in cols],
        ticktext=[display_label(c).replace(' (','<br>(') for c in cols])
    return fig


def _rolling(result, horizon, perspective):
    r = result['rolling'][horizon]
    fig = go.Figure([_line(r.index, r[c], c) for c in lens_pair(perspective)])
    fig.update_yaxes(tickformat='.1%')
    if r.empty:
        fig.add_annotation(text='Insufficient history for complete holding windows', showarrow=False)
    return plotly_layout(fig, f'{horizon}-year rolling CAGR · {home_currency(perspective)}', 'CAGR')


def _multi_horizon(result, perspective):
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=.055,
        subplot_titles=[f'{h}-year rolling CAGR' for h in (1, 3, 5, 10)])
    for row, h in enumerate((1, 3, 5, 10), 1):
        r = result['rolling'][h]
        for c in lens_pair(perspective):
            fig.add_trace(_line(r.index, r[c], c, showlegend=row == 1), row=row, col=1)
        fig.update_yaxes(tickformat='.0%', title_text='CAGR', row=row, col=1)
        if r.empty:
            fig.add_annotation(text='Insufficient history', showarrow=False, row=row, col=1)
    fig = plotly_layout(fig, f'Holding-period comparison · {home_currency(perspective)}', height=1000)
    fig.update_layout(legend=dict(y=1.07))
    return fig


def _excess(result, horizon, perspective):
    nifty, sp = lens_pair(perspective)
    r = result['rolling'][horizon]
    d = r[sp] - r[nifty]
    fig = go.Figure()
    for series, values, title in [(sp, d.clip(lower=0), 'S&P advantage'), (nifty, d.clip(upper=0), 'NIFTY advantage')]:
        fig.add_trace(go.Scatter(x=d.index, y=values, fill='tozeroy', name=title,
            line=dict(color=COLORS[series], dash=LINE_DASHES[series]),
            hovertemplate='%{x|%d %b %Y}<br>%{y:.2%}<extra>%{fullData.name}</extra>'))
    fig.update_yaxes(tickformat='.1%')
    return plotly_layout(fig, f'{horizon}-year excess CAGR · {home_currency(perspective)}', 'S&P − NIFTY')


def _distribution(result, horizon, perspective):
    r = result['rolling'][horizon]
    fig = go.Figure([go.Histogram(x=r[c], name=LABELS[c], histnorm='probability density', opacity=.65,
        marker_color=COLORS[c], nbinsx=35) for c in lens_pair(perspective)])
    fig.update_layout(barmode='overlay')
    fig.update_xaxes(tickformat='.1%')
    return plotly_layout(fig, f'{horizon}-year CAGR distribution · {home_currency(perspective)}', 'Density')


def _probability(result, perspective):
    p = result['probability']
    fig = go.Figure(go.Scatter(x=p.index, y=p['SP_wins'] if len(p) else [], mode='lines+markers',
        name=f'S&P wins · {home_currency(perspective)}', line=dict(color=COLORS[lens_pair(perspective)[1]], width=2.6),
        hovertemplate='%{x} years<br>%{y:.1%} historical win fraction<extra></extra>'))
    fig.add_hline(y=.5, line_dash='dot', line_color=TOKENS['muted'])
    fig.update_xaxes(title_text='Holding period · years')
    fig.update_yaxes(tickformat='.0%', range=[0,1])
    return plotly_layout(fig, f'Historical S&P win fraction vs NIFTY · {home_currency(perspective)}', 'Historical fraction')


def _matrix(detail, col, title, perspective):
    if detail.empty:
        return _heatmap(pd.DataFrame(), title)
    p = detail.pivot(index='Start_year', columns=col, values='Difference')
    if col == 'Horizon':
        p = p.reindex(sorted(p.columns, key=lambda x: int(x[:-1])), axis=1)
    audit = detail.assign(Dates=detail.Start_date.dt.strftime('%d %b %Y') + ' → ' + detail.End_date.dt.strftime('%d %b %Y'))
    dates = audit.pivot(index='Start_year', columns=col, values='Dates').reindex(index=p.index, columns=p.columns).fillna('').to_numpy()
    return _heatmap(p, f'{title} · S&P − NIFTY CAGR in {home_currency(perspective)}', True, dates)


def _fx(result, perspective, horizon=None):
    frames = result['lens_fx_annual'] if horizon is None else result['lens_fx_rolling'][horizon]
    fig = make_subplots(rows=len(frames), cols=1, shared_xaxes=True, vertical_spacing=.18 if len(frames)>1 else 0,
        subplot_titles=[display_label(c) for c in frames])
    for row, (asset, frame) in enumerate(frames.items(), 1):
        fields = [('Equity_log', 'Native equity', TOKENS['blue']), ('Currency_log', 'FX contribution', TOKENS['amber'])]
        if horizon is not None:
            fields.append(('Total_log', 'Home-currency total', COLORS[asset]))
        for field, name, color in fields:
            if horizon is None:
                trace = go.Bar(x=frame.index, y=frame[field], name=name, marker_color=color,
                    legendgroup=field, showlegend=row==1, hovertemplate='%{x}<br>%{y:.3%} log return<extra>%{fullData.name}</extra>')
            else:
                trace = go.Scatter(x=frame.index, y=frame[field], name=name, legendgroup=field, showlegend=row==1,
                    line=dict(color=color,width=2.5,dash='dash' if field=='Currency_log' else 'solid'),
                    hovertemplate='%{x|%d %b %Y}<br>%{y:.3%} annual log return<extra>%{fullData.name}</extra>')
            fig.add_trace(trace, row=row, col=1)
        fig.update_yaxes(tickformat='.1%', title_text='Log return', row=row, col=1)
    fig.update_layout(barmode='relative')
    title = 'Calendar-year' if horizon is None else f'{horizon}-year annualized'
    return plotly_layout(fig, f'{title} exact log attribution · {home_currency(perspective)}', height=550 if len(frames)==1 else 820)


def _drawdowns(result, perspective):
    d = drawdowns(result['daily'][list(lens_pair(perspective))])
    fig = go.Figure([_line(d.index, d[c], c) for c in d])
    fig.update_yaxes(tickformat='.0%')
    return plotly_layout(fig, f'Historical total-return drawdowns · {home_currency(perspective)}', 'Drawdown')


def _volatility(result, years, perspective):
    v = rolling_volatility(result['daily'], years, perspective)
    fig = go.Figure([_line(v.index, v[c], c) for c in v])
    fig.update_yaxes(tickformat='.0%')
    return plotly_layout(fig, f'{years}-year rolling annualized volatility · {home_currency(perspective)}', 'Volatility')


def _correlation(result, months, perspective):
    curves = result['rolling_correlations']
    key = min(curves, key=lambda k: abs(k-months))
    a, b = lens_pair(perspective)
    series = curves[key][f'{a} vs {b}']
    fig = go.Figure(go.Scatter(x=series.index, y=series, name=f'{LABELS[a]} vs {LABELS[b]}',
        line=dict(color=TOKENS['blue'],width=2.5), hovertemplate='%{x|%d %b %Y}<br>Correlation %{y:.3f}<extra></extra>'))
    fig.update_yaxes(range=[-1,1])
    return plotly_layout(fig, f'{key}-month equity-return correlation · {home_currency(perspective)}', 'Correlation')


def figure_set(result, lab=None, horizon=10, perspective='INR-based investor', selected=None,
               capital=100, log=True, frequency='monthly', volatility_years=1, correlation_months=36, only=None):
    """Build selected figures from the same lens-specific analytical snapshot."""
    selected = selected or lens_pair(perspective)
    builders = {
        'wealth': lambda: _wealth(result, selected, capital, log, perspective),
        'annual': lambda: _annual(result, perspective), 'rolling': lambda: _rolling(result,horizon,perspective),
        'multi_horizon': lambda: _multi_horizon(result,perspective),
        'excess': lambda: _excess(result,horizon,perspective), 'distributions': lambda: _distribution(result,horizon,perspective),
        'probability': lambda: _probability(result,perspective),
        'holding_matrix': lambda: _matrix(result['holding'],'Horizon','Start year × holding period',perspective),
        'endpoints': lambda: _matrix(result['endpoints'],'End_year','Endpoint sensitivity',perspective),
        'fx_attribution': lambda: _fx(result,perspective), 'fx_rolling': lambda: _fx(result,perspective,horizon),
        'drawdowns': lambda: _drawdowns(result,perspective), 'volatility': lambda: _volatility(result,volatility_years,perspective),
        'correlation': lambda: _correlation(result,correlation_months,perspective),
    }
    return {name: builders[name]() for name in builders if only is None or name in only}
