"""Shared midnight palette and Plotly defaults; no calculation logic."""
from pathlib import Path
from textwrap import wrap
from .config import NIFTY, SP, FX, SP_INR, NIFTY_USD, EURUSD, EURINR, NIFTY_EUR, SP_EUR

TOKENS = dict(background="#060913", sidebar="#070C1B", panel="#0B1223", raised="#10192D",
              border="#263757", text="#F7FBFF", muted="#AAB6CA", blue="#3AA7FF",
              mint="#25E0A3", red="#FF6B5A", amber="#FF9F43", yellow="#FFD84D",
              violet="#A78BFA", pink="#F472B6")
SERIES_COLORS = {NIFTY: TOKENS["blue"], SP: TOKENS["mint"], SP_INR: TOKENS["amber"],
                 NIFTY_USD: TOKENS["violet"], NIFTY_EUR: TOKENS["yellow"], SP_EUR: TOKENS["pink"],
                 FX: TOKENS["violet"], EURUSD: TOKENS["mint"], EURINR: TOKENS["amber"]}
LINE_DASHES = {NIFTY: "solid", NIFTY_USD: "solid", NIFTY_EUR: "solid", SP: "dash", SP_INR: "dash", SP_EUR: "dash"}
HEATMAP_SCALE = [[0, "#2464A0"], [0.5, TOKENS["raised"]], [1, "#A86013"]]


def css():
    variables = ":root{" + "".join(f"--{k}:{v};" for k, v in TOKENS.items()) + "}"
    return variables + (Path(__file__).resolve().parents[1] / "assets/dashboard.css").read_text(encoding="utf-8")


def plotly_layout(fig, title, ytitle="", height=560):
    title = '<br>'.join(wrap(title, width=42, break_long_words=False))
    fig.update_layout(template="plotly_dark", paper_bgcolor=TOKENS["panel"], plot_bgcolor=TOKENS["panel"],
        title=dict(text=title, x=0.025, xanchor="left", y=.985, yanchor="top", automargin=True, font=dict(size=16)),
        font=dict(family="Inter, Segoe UI, Arial, sans-serif", size=13, color=TOKENS["text"]),
        height=height, margin=dict(l=65, r=30, t=135, b=65), hovermode="x unified",
        hoverlabel=dict(bgcolor=TOKENS["raised"], font_color=TOKENS["text"], bordercolor=TOKENS["border"]),
        legend=dict(orientation="h", y=1.04, yanchor="bottom", x=0, font=dict(size=11), bgcolor=TOKENS["panel"]))
    fig.update_xaxes(showgrid=False, automargin=True, color=TOKENS["muted"])
    fig.update_yaxes(gridcolor=TOKENS["border"], zerolinecolor=TOKENS["muted"], automargin=True, color=TOKENS["muted"])
    if ytitle:
        fig.update_yaxes(title_text=ytitle)
    return fig
