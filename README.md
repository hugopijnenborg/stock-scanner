# Stock Scanner

Scanner for the top 1,000 US-listed companies, designed to detect market setups similar to the trader's historical entries.

## Current architecture

- `universe.py`: builds the current 1,000-stock universe from StockAnalysis.
- `data.py`: downloads daily market data with yfinance.
- `indicators.py`: calculates technical features without look-ahead data.
- `trader_data.csv`: seed of the known trader entries supplied in the project conversation.
- `model.py`: transparent v0.1 setup scoring. The weights are provisional and must be replaced or calibrated by the backtest.
- `scanner.py`: scans the universe and ranks opportunities.
- `backtest.py`: evaluates historical signals against future returns.
- `main.py`: CLI entry point.

## Install

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Run

```bash
python main.py universe
python main.py scan
python main.py backtest
```

The first version uses daily candles. Intraday alerts, Supabase storage and Discord notifications come after the scoring/backtest layer is validated.

## Important

The score is a research model, not financial advice. The historical trader sample is small. Do not treat the initial weights as proven predictive weights. The backtest must be used to calibrate them and a time-based holdout must remain untouched during calibration.
