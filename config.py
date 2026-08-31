from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# StockAnalysis currently exposes the US-listed market-cap ranking here.
UNIVERSE_URL = "https://stockanalysis.com/list/biggest-companies/"
UNIVERSE_SIZE = 1000

DEFAULT_START = "2024-01-01"
DEFAULT_END = None
BENCHMARKS = ["SPY", "QQQ", "^VIX"]

MIN_PRICE = 5.0
MIN_AVG_DOLLAR_VOLUME = 5_000_000

# Provisional v0.1 weights. These are intentionally explicit and will be
# calibrated against the trader entries and a negative control set.
REBOUND_WEIGHTS = {
    "drawdown_5d": 0.20,
    "drawdown_20d": 0.10,
    "rsi_14": 0.10,
    "z_score": 0.15,
    "volume_ratio": 0.10,
    "bollinger_pct": 0.10,
    "distance_sma20": 0.05,
    "distance_sma50": 0.05,
    "relative_strength_20d": 0.10,
    "market_regime": 0.05,
}

QUALITY_WEIGHTS = {
    "drawdown_20d": 0.20,
    "distance_52w_high": 0.10,
    "distance_sma200": 0.10,
    "relative_strength_20d": 0.10,
    "rsi_14": 0.10,
    "z_score": 0.10,
    "volume_ratio": 0.05,
    "market_regime": 0.05,
    "fundamental_placeholder": 0.20,
}

CYCLICAL_WEIGHTS = {
    "drawdown_5d": 0.15,
    "drawdown_20d": 0.10,
    "rsi_14": 0.10,
    "atr_pct": 0.15,
    "volume_ratio": 0.15,
    "z_score": 0.10,
    "relative_strength_20d": 0.10,
    "bollinger_pct": 0.10,
    "market_regime": 0.05,
}
