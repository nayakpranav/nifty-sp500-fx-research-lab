"""Central configuration and portable project paths."""

from dataclasses import dataclass
from pathlib import Path

NIFTY = "NIFTY_TRI_INR"
SP = "SP500_TR_USD"
FX = "USDINR"
SP_INR = "SP500_TR_INR"
NIFTY_USD = "NIFTY_TRI_USD"
EURUSD = "EURUSD"
EURINR = "EURINR"
NIFTY_EUR = "NIFTY_TRI_EUR"
SP_EUR = "SP500_TR_EUR"
REQUIRED = (NIFTY, SP, FX, EURUSD)
EQUITIES = (NIFTY, SP, SP_INR, NIFTY_USD, NIFTY_EUR, SP_EUR)
HORIZONS = (1, 3, 5, 7, 10, 15, 20)
DAYS_PER_YEAR = 365.2425
NSE_URL = "https://www.niftyindices.com/reports/historical-data"
NSE_API = "https://www.niftyindices.com/BackPage/getTotalReturnIndexString"


@dataclass(frozen=True)
class Config:
    """Explicit alignment, refresh and inference choices."""

    root: Path = Path(".")
    force_refresh: bool = False
    asof_tolerance_days: int = 7
    rolling_tolerance_days: int = 7
    bootstrap_replications: int = 5000
    block_length: int = 12
    seed: int = 42
    include_ytd: bool = False
    stale_days: int = 14
    fx_source: str = "fred"
    downside_target_annual: float = 0.0

    def prepare(self):
        """Create all required directories without platform-specific paths."""
        for path in (
            "data/raw",
            "data/processed",
            "outputs/figures",
            "outputs/tables",
            "outputs/reports",
        ):
            (self.root / path).mkdir(parents=True, exist_ok=True)
        return self
