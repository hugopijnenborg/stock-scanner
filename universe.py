import io
import pandas as pd
import requests

from config import UNIVERSE_URL, UNIVERSE_SIZE

HEADERS = {"User-Agent": "Mozilla/5.0 stock-scanner-research"}


def _read_page(url: str) -> pd.DataFrame:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    tables = pd.read_html(io.StringIO(response.text))
    if not tables:
        raise RuntimeError(f"No stock table found on {url}")
    table = tables[0].copy()
    table.columns = [str(c).strip().lower().replace(" ", "_") for c in table.columns]
    ticker_col = next((c for c in table.columns if c in {"symbol", "ticker"}), None)
    name_col = next((c for c in table.columns if c in {"name", "company", "company_name"}), None)
    if ticker_col is None:
        raise RuntimeError(f"Could not identify ticker column. Columns: {list(table.columns)}")
    out = pd.DataFrame({"ticker": table[ticker_col].astype(str).str.upper().str.strip()})
    out["company_name"] = table[name_col].astype(str) if name_col else out["ticker"]
    return out[["ticker", "company_name"]]


def load_top_us_stocks(limit: int = UNIVERSE_SIZE) -> pd.DataFrame:
    """Load the largest U.S.-listed companies by market cap.

    StockAnalysis exposes 500 rows per page. Fetch successive pages until the
    requested universe size is reached or the source stops returning new rows.
    """
    frames = []
    seen = set()
    max_pages = max(1, (limit + 499) // 500 + 1)

    for page in range(1, max_pages + 1):
        url = UNIVERSE_URL if page == 1 else f"{UNIVERSE_URL}?p={page}"
        try:
            frame = _read_page(url)
        except Exception:
            if page == 1:
                raise
            break
        before = len(seen)
        frame = frame[~frame["ticker"].isin(seen)].copy()
        if frame.empty:
            break
        seen.update(frame["ticker"].tolist())
        frames.append(frame)
        if len(seen) >= limit or len(seen) == before:
            break

    if not frames:
        raise RuntimeError("No stocks loaded")

    out = pd.concat(frames, ignore_index=True).drop_duplicates("ticker")
    return out.head(limit).reset_index(drop=True)


if __name__ == "__main__":
    df = load_top_us_stocks()
    print(f"Loaded {len(df)} stocks")
    print(df.to_string(index=False))
