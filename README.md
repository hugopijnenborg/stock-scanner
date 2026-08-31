# Stock Scanner

Scanner for the top 1,000 US-listed companies, designed to detect market setups similar to the trader's historical entries.

## Strategy research approach

The trader-chat analysis identified a recurring structure:

**strong or high-conviction company + abnormal downside move + short-term dislocation + elevated selling/volume + proximity to support + suitable market context**.

The scanner therefore does not treat RSI or MACD as standalone buy triggers. It combines price dislocation, momentum, volatility, volume, support, drawdown, relative strength and market context.

The model also keeps separate concepts for:

- Technical Opportunity: how unusual the current dislocation is.
- Setup type: rebound, quality pullback or cyclical/high-beta.
- Reversal Trigger: evidence that selling pressure may be exhausting.
- Fundamental/Street Confirmation: reserved for historical fundamentals, analyst revisions and professional positioning once a reliable data source is connected.

The trader's stated behavior also matters for the research design: starter positions, adds during further weakness, partial profit taking after mean reversion and maintaining liquidity. These are not treated as one single entry signal.

## Important research controls

The trader's reported percentage gains are not used as ground truth because many are measured from an average cost and the chat naturally contains reporting/selection bias.

For each historical entry, the research engine should calculate future outcomes itself:

- return after 1, 3, 5, 10 and 20 trading days
- maximum favorable excursion
- maximum adverse excursion
- time to +5%, +10% and +20%

It should also create matched non-entry observations from other stocks on the same dates. This allows us to measure which features actually distinguish trader entries from ordinary market weakness.

## Current architecture

- `universe.py`: current 1,000-stock universe.
- `data.py`: daily market data.
- `indicators.py`: causal technical features.
- `trader_data.csv`: seed of confirmed/reported trader entries.
- `model.py`: transparent v0.1 setup scoring.
- `scanner.py`: scans and ranks opportunities.
- `backtest.py`: historical outcome evaluation.
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
python main.py scan --output scan_results.csv
python main.py backtest --output backtest_results.csv
```

GitHub Actions can run both without a local Python installation.

## Next research layer

The next implementation step is calibration against the positive trader entries and matched negative controls. The provisional weights must be replaced or adjusted only after out-of-sample testing. Fundamental/Street confirmation will then be added as a separate data layer rather than fabricated from technical indicators.

The project is for research and paper testing, not financial advice.
