from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

UNIVERSE_URL = "https://stockanalysis.com/list/biggest-companies/"
UNIVERSE_SIZE = 1000

DEFAULT_START = "2024-01-01"
DEFAULT_END = None
BENCHMARKS = ["SPY", "QQQ", "^VIX"]

MIN_PRICE = 5.0
MIN_AVG_DOLLAR_VOLUME = 5_000_000

TECHNICAL_WEIGHTS = {
    "drawdown_recent": 0.15,
    "rsi": 0.15,
    "ma_dislocation": 0.10,
    "recent_selloff": 0.15,
    "volume_capitulation": 0.10,
    "support": 0.10,
    "market": 0.05,
    "sector": 0.05,
}

REBOUND_WEIGHTS = {
    "drawdown_5d": 0.15,
    "drawdown_20d": 0.10,
    "rsi_14": 0.15,
    "z_score": 0.10,
    "volume_ratio": 0.10,
    "bollinger_pct": 0.10,
    "distance_sma20": 0.05,
    "distance_sma50": 0.05,
    "support": 0.10,
    "intraday_reversal": 0.05,
    "relative_strength_20d": 0.05,
}

QUALITY_WEIGHTS = {
    "distance_52w_high": 0.15,
    "distance_sma200": 0.10,
    "drawdown_20d": 0.10,
    "relative_strength_20d": 0.10,
    "rsi_14": 0.10,
    "z_score": 0.10,
    "volume_ratio": 0.05,
    "support": 0.10,
    "market_regime": 0.05,
    "fundamental_placeholder": 0.15,
}

CYCLICAL_WEIGHTS = {
    "drawdown_5d": 0.15,
    "drawdown_20d": 0.10,
    "rsi_14": 0.10,
    "atr_pct": 0.15,
    "volume_ratio": 0.15,
    "z_score": 0.10,
    "relative_strength_20d": 0.10,
    "bollinger_pct": 0.05,
    "intraday_reversal": 0.05,
    "market_regime": 0.05,
}

# 80+ is the only actual buy-alert threshold.
ALERT_THRESHOLD = 80.0
STRONG_ALERT_THRESHOLD = 85.0
EXCEPTIONAL_ALERT_THRESHOLD = 90.0

# WATCH is an early-warning state, not an alert. The final watch logic
# requires a 70-79.9 score plus a hard recent selloff.
WATCH_THRESHOLD = 70.0
