from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / 'data'
DATA_DIR.mkdir(exist_ok=True)

UNIVERSE_URL = 'https://stockanalysis.com/list/biggest-companies/'
UNIVERSE_SIZE = 1000
DEFAULT_START = '2024-01-01'
DEFAULT_END = None
BENCHMARKS = ['SPY', 'QQQ', '^VIX']
MIN_PRICE = 5.0
MIN_AVG_DOLLAR_VOLUME = 5_000_000
