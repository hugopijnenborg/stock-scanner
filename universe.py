import io
import pandas as pd
import requests

from config import UNIVERSE_URL, UNIVERSE_SIZE


def load_top_us_stocks(limit: int = UNIVERSE_SIZE) -> pd.DataFrame:
    """Load the current US stock market-cap ranking.

    StockAnalysis is used only to seed the current universe. For a proper
    historical backtest we will later store point-in-time constituents to
    remove survivorship bias.
    """
    response = requests.get(
        UNIVERSE_URL,
        headers={"User-Agent": "Mozilla/5.0 stock-scanner-research"},
        timeout=30,
    )
    response.raise_for_status()
    tables = pd.read_html(io.StringIO(response.text))
    if not tables:
        raise RuntimeError("No stock table found on the universe source")

    table = tables[0].copy()
    table.columns = [str(c).strip().lower().replace(" ", "_") for c in table.columns]

    ticker_col = next((c for c in table.columns if c in {"symbol", "ticker"}), None)
    name_col = next((c for c in table.columns if c in {"name", "company"}), None)
    if ticker_col is None:
        raise RuntimeError(f"Could not identify ticker column. Columns: {list(table.columns)}")

    out = pd.DataFrame({"ticker": table[ticker_col].astype(str).str.upper().str.strip()})
    out["company_name"] = table[name_col].astype(str) if name_col else out["ticker"]
    out = out.drop_duplicates("ticker").head(limit).reset_index(drop=True)
    return out


if __name__ == "__main__":
    df = load_top_us_stocks()
    print(df.to_string(index=False))
