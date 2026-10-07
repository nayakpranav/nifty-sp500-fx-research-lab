"""Memoized analytical snapshots, neutral summaries and reproducible exports."""

from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
from .config import NIFTY, SP, FX, SP_INR, NIFTY_USD, HORIZONS
from .currency import attribution, validate_identities
from .transforms import period_levels, calendar_returns
from .metrics import risk_metrics, drawdown_episodes
from .rolling import (
    rolling_cagr,
    summary,
    excess_summary,
    trailing_cagr,
    matrices,
    probability_curve,
    non_overlapping,
)
from .statistics import correlations, fx_regimes


class ResearchLab:
    """Immutable input panel; cache analytic snapshots and bootstrap separately."""

    def __init__(self, daily, audit, metadata, validation, config):
        self.daily = daily.copy()
        self.audit = audit.copy()
        self.metadata = metadata
        self.validation = validation
        self.config = config
        self._cache = {}
        self.bootstrap_cache = {}
        self.identity_errors = validate_identities(daily)

    def analyze(self, start=None, end=None, include_ytd=False):
        """Cache range-dependent results; cosmetic changes never recompute them."""
        start = pd.Timestamp(start or self.daily.index[0])
        end = pd.Timestamp(end or self.daily.index[-1])
        key = (start, end, include_ytd)
        if key in self._cache:
            return self._cache[key]
        daily = self.daily.loc[start:end]
        if len(daily) < 2:
            raise ValueError("Select at least two valuation cutoffs.")
        monthly = period_levels(daily)
        if len(monthly) < 2:
            raise ValueError("Select at least two completed monthly snapshots.")
        rolling = {
            h: rolling_cagr(monthly, h, self.config.rolling_tolerance_days)
            for h in HORIZONS
        }
        annual = calendar_returns(daily, include_ytd=include_ytd)
        fx_table = attribution(annual.select_dtypes("number"))
        snapshots = period_levels(daily, "annual", include_partial=True)
        for label in fx_table.index:
            year = int(label[:4])
            loc = next(i for i, date in enumerate(snapshots.index) if date.year == year)
            fx_table.loc[label, "USDINR_start"] = snapshots.iloc[loc - 1][FX]
            fx_table.loc[label, "USDINR_end"] = snapshots.iloc[loc][FX]
        holding, endpoints = matrices(
            daily, tolerance_days=self.config.rolling_tolerance_days
        )
        corr, rolling_corr = correlations(daily)
        episodes = pd.concat(
            [drawdown_episodes(daily[c]).assign(Series=c) for c in daily.columns],
            ignore_index=True,
        )
        result = dict(
            daily=daily,
            monthly=monthly,
            annual=annual,
            rolling=rolling,
            rolling_summaries={h: summary(r) for h, r in rolling.items()},
            rolling_excess=pd.DataFrame(
                {h: excess_summary(r) for h, r in rolling.items()}
            ).T,
            trailing=trailing_cagr(daily),
            holding=holding,
            endpoints=endpoints,
            fx_annual=fx_table,
            fx_rolling={h: self._rolling_attribution(r) for h, r in rolling.items()},
            risk=risk_metrics(daily, self.config.downside_target_annual),
            drawdowns=episodes,
            probability=probability_curve(monthly),
            correlations=corr,
            rolling_correlations=rolling_corr,
            regimes=fx_regimes(daily),
            nonoverlap={h: non_overlapping(monthly, h) for h in HORIZONS},
        )
        self._cache[key] = result
        return result

    @staticmethod
    def _rolling_attribution(rolling):
        out = rolling[[SP, FX, SP_INR]].copy()
        out["Equity_annual_log"] = np.log1p(out[SP])
        out["FX_annual_log"] = np.log1p(out[FX])
        out["Total_annual_log"] = np.log1p(out[SP_INR])
        return out

    def bootstrap(self, result, horizon, **kwargs):
        from .statistics import block_bootstrap
        key = (
            result["daily"].index[0],
            result["daily"].index[-1],
            horizon,
            tuple(sorted(kwargs.items())),
        )
        if key not in self.bootstrap_cache:
            self.bootstrap_cache[key] = block_bootstrap(
                result["daily"], horizon, **kwargs
            )
        return self.bootstrap_cache[key]

    def save_processed(self):
        self.config.prepare()
        hashes = {}
        for name, frame in [
            ("daily", self.daily),
            ("source_dates", self.audit),
            ("monthly", period_levels(self.daily)),
            ("annual_levels", period_levels(self.daily, "annual")),
        ]:
            path = self.config.root / "data/processed" / f"{name}.csv"
            frame.to_csv(
                path, index_label="Date", date_format="%Y-%m-%d", float_format="%.12g"
            )
            hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest = dict(
            sources=self.metadata,
            checksums=hashes,
            common_start_date=str(self.daily.index[0].date()),
            common_end_date=str(self.daily.index[-1].date()),
            observations=len(self.daily),
            alignment="union cutoff; backward-as-of; no future observations",
            tolerance_days=self.config.asof_tolerance_days,
            identity_errors=self.identity_errors,
        )
        (self.config.root / "data/processed/manifest.json").write_text(
            json.dumps(manifest, indent=2, default=str), encoding="utf8"
        )


def research_summary(result, horizon=10, perspective="Indian investor"):
    r = result["rolling"][horizon]
    d = result["daily"]
    if r.empty:
        return f"{horizon}Y: insufficient history in {d.index[0].date()}–{d.index[-1].date()}. No windows invented."
    a, b = (NIFTY, SP_INR) if perspective == "Indian investor" else (NIFTY_USD, SP)
    e = excess_summary(r, perspective)
    risk = result["risk"]
    return (
        f"SAMPLE {d.index[0].date()} – {d.index[-1].date()} | {perspective} | "
        f"{horizon}Y | {len(r):,} overlapping monthly windows\n"
        f"NIFTY median CAGR {r[a].median():.2%}; S&P median CAGR {r[b].median():.2%}.\n"
        f"S&P won {e.SP_wins:.1%}; NIFTY won {e.NIFTY_wins:.1%}; ties {e.Ties:.1%}. "
        f"Paired advantage S&P − NIFTY: median {e.Median_advantage*100:.2f} pp; "
        f"mean {e.Mean_advantage*100:.2f} pp.\n"
        f"Worst {horizon}Y CAGR: NIFTY {r[a].min():.2%}; S&P {r[b].min():.2%}. "
        f"Best: NIFTY {r[a].max():.2%}; S&P {r[b].max():.2%}.\n"
        f'Maximum daily-cutoff drawdown: NIFTY {risk.loc[a,"Max_drawdown"]:.2%}; '
        f'S&P {risk.loc[b,"Max_drawdown"]:.2%}. Monthly annualized volatility: '
        f'{risk.loc[a,"Annualized_volatility"]:.2%} / {risk.loc[b,"Annualized_volatility"]:.2%}.\n'
        f"Median annualized FX log contribution: {np.log1p(r[FX]).median()*100:.2f} log percentage points.\n"
        "Window frequency weights dates, not independent investments. Currency regimes and "
        "endpoints matter; historical results do not imply future performance."
    )


def tables_for_export(result, lab, bootstrap=None):
    meta = pd.DataFrame(
        [
            dict(Series=k, **{a: str(b) for a, b in v.items()})
            for k, v in lab.metadata.items()
        ]
    )
    tables = {
        "Metadata": meta,
        "Validation": lab.validation,
        "Annual_Returns": result["annual"],
        "Trailing_CAGR": result["trailing"],
        "FX_Attribution": result["fx_annual"],
        "Risk_Metrics": result["risk"],
        "Drawdowns": result["drawdowns"],
        "Outperformance": result["probability"],
        "Holding_Matrix": result["holding"],
        "Endpoint_Matrix": result["endpoints"],
        "Correlations": result["correlations"],
        "FX_Regimes": result["regimes"],
        "Rolling_Excess": result["rolling_excess"],
    }
    for h, r in result["rolling"].items():
        tables[f"Rolling_{h}Y"] = r
        tables[f"Summary_{h}Y"] = result["rolling_summaries"][h]
        tables[f"Nonoverlap_{h}Y"] = result["nonoverlap"][h]
        tables[f"FX_Rolling_{h}Y"] = result["fx_rolling"][h]
    if bootstrap is not None:
        tables["Bootstrap"] = bootstrap
    return tables


def export_tables(tables, root=Path(".")):
    folder = Path(root) / "outputs/tables"
    folder.mkdir(parents=True, exist_ok=True)
    book = folder / "research_results.xlsx"
    with pd.ExcelWriter(book, engine="openpyxl") as writer:
        for name, table in tables.items():
            table.to_csv(folder / f"{name}.csv", float_format="%.10g")
            table.to_excel(writer, sheet_name=name[:31])
            sheet = writer.sheets[name[:31]]
            sheet.freeze_panes = "B2"
            sheet.auto_filter.ref = sheet.dimensions
            for column in sheet.columns:
                sheet.column_dimensions[column[0].column_letter].width = min(
                    42, max(14, len(str(column[0].value)) + 2)
                )
    return book
