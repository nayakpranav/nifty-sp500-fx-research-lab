"""Interactive Plotly figures for the Streamlit dashboard."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .config import NIFTY, SP, FX, SP_INR, NIFTY_USD
from .transforms import normalize
from .metrics import drawdowns
from .statistics import rolling_volatility

COLORS = {
    NIFTY: "#1167B1",
    SP: "#667085",
    SP_INR: "#D55E00",
    NIFTY_USD: "#138A72",
    FX: "#8E5BB7",
}
LABELS = {
    NIFTY: "NIFTY 50 TRI · INR",
    SP: "S&P 500 TR · USD",
    SP_INR: "S&P 500 TR · INR",
    NIFTY_USD: "NIFTY 50 TRI · USD",
    FX: "USD/INR",
}


def _layout(fig, title, ytitle="", height=600):
    fig.update_layout(
        template="plotly_white",
        title=dict(text=title, x=0.01, xanchor="left"),
        font=dict(family="Arial, sans-serif", color="#0D1B2A"),
        height=height,
        margin=dict(l=55, r=30, t=80, b=55),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.04, x=0),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(title=ytitle, gridcolor="#E7EBF0", zerolinecolor="#B7C0CC")
    return fig


def _heatmap(frame, title, percent_points=False):
    if frame.empty:
        return _layout(go.Figure(), title)
    z = frame.to_numpy(dtype=float)
    if not percent_points:
        z = z * 100
    finite = z[np.isfinite(z)]
    limit = max(abs(finite).max(), 0.1) if len(finite) else 0.1
    fig = go.Figure(go.Heatmap(
        z=z, x=[str(c) for c in frame.columns], y=[str(i) for i in frame.index],
        zmid=0, zmin=-limit, zmax=limit,
        colorscale=[[0, "#2166AC"], [0.5, "#F7F7F7"], [1, "#B35806"]],
        colorbar=dict(title="pp" if percent_points else "%"),
        hovertemplate="%{y} · %{x}<br>%{z:.2f}<extra></extra>",
    ))
    fig.update_yaxes(autorange="reversed")
    return _layout(fig, title, height=max(520, 22 * len(frame) + 180))


def _wealth(result, selected, capital, log):
    levels = result["daily"]
    wealth = normalize(levels[list(selected)], capital)
    fig = go.Figure()
    for name in selected:
        fig.add_trace(go.Scatter(
            x=wealth.index, y=wealth[name], mode="lines", name=LABELS.get(name, name),
            line=dict(color=COLORS.get(name), width=2.3),
        ))
    if log:
        fig.update_yaxes(type="log")
    return _layout(fig, "Equal-start growth of wealth", f"Value from {capital:,.0f}")


def _annual(result):
    annual = result["annual"].select_dtypes("number")
    cols = [c for c in [NIFTY, SP, FX, SP_INR, NIFTY_USD] if c in annual]
    return _heatmap(annual[cols].T, "Calendar-year returns")


def _rolling(result, horizon, perspective):
    r = result["rolling"][horizon]
    cols = [NIFTY, SP_INR, SP] if perspective == "Indian investor" else [NIFTY_USD, SP, NIFTY]
    fig = go.Figure()
    for c in cols:
        fig.add_trace(go.Scatter(x=r.index, y=r[c], name=LABELS[c], line=dict(color=COLORS[c], width=2)))
    fig.update_yaxes(tickformat=".1%")
    return _layout(fig, f"{horizon}-year rolling CAGR", "CAGR")


def _excess(result, horizon, perspective):
    r = result["rolling"][horizon]
    a, b = (SP_INR, NIFTY) if perspective == "Indian investor" else (SP, NIFTY_USD)
    d = r[a] - r[b]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=d.index, y=d.clip(lower=0), fill="tozeroy", name="S&P advantage", line=dict(color="#D55E00")))
    fig.add_trace(go.Scatter(x=d.index, y=d.clip(upper=0), fill="tozeroy", name="NIFTY advantage", line=dict(color="#1167B1")))
    fig.update_yaxes(tickformat=".1%")
    return _layout(fig, f"{horizon}-year rolling excess CAGR", "S&P − NIFTY")


def _distribution(result, horizon, perspective):
    r = result["rolling"][horizon]
    cols = [NIFTY, SP_INR] if perspective == "Indian investor" else [NIFTY_USD, SP]
    fig = go.Figure()
    for c in cols:
        fig.add_trace(go.Histogram(
            x=r[c], name=LABELS[c], histnorm="probability density", opacity=0.55,
            marker_color=COLORS[c], nbinsx=35,
        ))
    fig.update_layout(barmode="overlay")
    fig.update_xaxes(tickformat=".1%")
    return _layout(fig, f"{horizon}-year CAGR distribution", "Density")


def _probability(result):
    p = result["probability"]
    y = p["SP_wins"] if "SP_wins" in p else p.iloc[:, 0]
    fig = go.Figure(go.Scatter(x=p.index, y=y, mode="lines+markers", line=dict(color="#D55E00", width=2.2)))
    fig.add_hline(y=0.5, line_dash="dot", line_color="#667085")
    fig.update_yaxes(tickformat=".0%", range=[0, 1])
    return _layout(fig, "Historical probability that S&P beats NIFTY", "Win probability")


def _matrix(detail, col, title):
    if detail.empty:
        return _layout(go.Figure(), title)
    p = detail.pivot(index="Start_year", columns=col, values="Difference") * 100
    return _heatmap(p, title, percent_points=True)


def _fx_attribution(result):
    f = result["fx_annual"]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=f.index, y=f["Equity_log"], name="S&P equity log return", marker_color=COLORS[SP]))
    fig.add_trace(go.Bar(x=f.index, y=f["Currency_log"], name="USD/INR log contribution", marker_color=COLORS[FX]))
    fig.update_layout(barmode="relative")
    fig.update_yaxes(tickformat=".1%")
    return _layout(fig, "Annual S&P return and currency attribution", "Log return")


def _fx_rolling(result, horizon):
    f = result["fx_rolling"][horizon]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=f.index, y=f["Equity_annual_log"], name="Equity", line=dict(color=COLORS[SP])))
    fig.add_trace(go.Scatter(x=f.index, y=f["FX_annual_log"], name="Currency", line=dict(color=COLORS[FX])))
    fig.add_trace(go.Scatter(x=f.index, y=f["Total_annual_log"], name="Total INR", line=dict(color=COLORS[SP_INR], width=2.3)))
    fig.update_yaxes(tickformat=".1%")
    return _layout(fig, f"{horizon}-year annualized log attribution", "Annualized log return")


def _drawdowns(result):
    d = drawdowns(result["daily"][[NIFTY, SP_INR, SP]])
    fig = go.Figure()
    for c in d:
        fig.add_trace(go.Scatter(x=d.index, y=d[c], name=LABELS[c], line=dict(color=COLORS[c])))
    fig.update_yaxes(tickformat=".0%")
    return _layout(fig, "Historical drawdowns", "Drawdown")


def _volatility(result, years=1):
    v = rolling_volatility(result["daily"], years)
    fig = go.Figure()
    for c in v:
        fig.add_trace(go.Scatter(x=v.index, y=v[c], name=LABELS[c], line=dict(color=COLORS[c])))
    fig.update_yaxes(tickformat=".0%")
    return _layout(fig, f"{years}-year rolling annualized volatility", "Volatility")


def _correlation(result, months=36):
    curves = result["rolling_correlations"]
    key = min(curves.keys(), key=lambda k: abs(k - months))
    frame = curves[key]
    fig = go.Figure()
    for c in frame:
        fig.add_trace(go.Scatter(x=frame.index, y=frame[c], name=c))
    fig.update_yaxes(range=[-1, 1])
    return _layout(fig, f"{key}-month rolling correlation", "Correlation")


def figure_set(
    result, lab, horizon=10, perspective="Indian investor", selected=(NIFTY, SP_INR, SP),
    capital=100, log=True, frequency="monthly", volatility_years=1,
    correlation_months=36, only=None,
):
    """Build only the requested figures so tab navigation remains responsive."""
    wanted = set(only or {
        "wealth", "annual", "rolling", "excess", "distributions", "probability",
        "holding_matrix", "endpoints", "fx_attribution", "fx_rolling",
        "drawdowns", "volatility", "correlation",
    })
    builders = {
        "wealth": lambda: _wealth(result, selected, capital, log),
        "annual": lambda: _annual(result),
        "rolling": lambda: _rolling(result, horizon, perspective),
        "excess": lambda: _excess(result, horizon, perspective),
        "distributions": lambda: _distribution(result, horizon, perspective),
        "probability": lambda: _probability(result),
        "holding_matrix": lambda: _matrix(result["holding"], "Horizon", "Start year × holding period"),
        "endpoints": lambda: _matrix(result["endpoints"], "End_year", "Endpoint sensitivity"),
        "fx_attribution": lambda: _fx_attribution(result),
        "fx_rolling": lambda: _fx_rolling(result, horizon),
        "drawdowns": lambda: _drawdowns(result),
        "volatility": lambda: _volatility(result, volatility_years),
        "correlation": lambda: _correlation(result, correlation_months),
    }
    return {name: builders[name]() for name in wanted}
