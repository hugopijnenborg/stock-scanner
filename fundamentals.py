from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import math
import yfinance as yf


def _num(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def _latest(stmt, names):
    for name in names:
        if name in stmt.index:
            s = stmt.loc[name].dropna()
            if len(s):
                return _num(s.iloc[0])
    return None


def _growth(stmt, names):
    for name in names:
        if name in stmt.index:
            s = stmt.loc[name].dropna()
            if len(s) >= 2 and s.iloc[1] != 0:
                return _num((s.iloc[0] / s.iloc[1]) - 1)
    return None


def _one(ticker: str) -> dict:
    out = {"fundamental_score": None}
    try:
        t = yf.Ticker(ticker)
        inc = t.income_stmt
        bal = t.balance_sheet
        cf = t.cashflow
        revenue = _latest(inc, ["Total Revenue", "Operating Revenue"])
        net_income = _latest(inc, ["Net Income", "Net Income Common Stockholders"])
        eps = _latest(inc, ["Diluted EPS", "Basic EPS"])
        ebit = _latest(inc, ["EBIT", "Operating Income"])
        gross_profit = _latest(inc, ["Gross Profit"])
        equity = _latest(bal, ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"])
        debt = _latest(bal, ["Total Debt", "Long Term Debt And Capital Lease Obligation"])
        cash = _latest(bal, ["Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents"])
        fcf = _latest(cf, ["Free Cash Flow"])
        if fcf is None:
            op_cf = _latest(cf, ["Operating Cash Flow", "Total Cash From Operating Activities"])
            capex = _latest(cf, ["Capital Expenditure", "Capital Expenditure Reported"])
            if op_cf is not None and capex is not None:
                fcf = op_cf + capex if capex < 0 else op_cf - capex
        revenue_growth = _growth(inc, ["Total Revenue", "Operating Revenue"])
        eps_growth = _growth(inc, ["Diluted EPS", "Basic EPS"])
        fcf_growth = _growth(cf, ["Free Cash Flow"])
        net_margin = net_income / revenue if revenue else None
        gross_margin = gross_profit / revenue if revenue else None
        roe = net_income / equity if equity else None
        debt_equity = debt / equity if equity else None
        try:
            info = t.info
        except Exception:
            info = {}
        pe = _num(info.get("trailingPE"))
        forward_pe = _num(info.get("forwardPE"))
        peg = _num(info.get("pegRatio"))
        market_cap = _num(info.get("marketCap"))
        out.update({
            "revenue": revenue, "revenue_growth": revenue_growth, "eps": eps,
            "eps_growth": eps_growth, "net_margin": net_margin, "gross_margin": gross_margin,
            "fcf": fcf, "fcf_growth": fcf_growth, "roe": roe,
            "debt_equity": debt_equity, "cash": cash, "pe": pe,
            "forward_pe": forward_pe, "peg": peg, "market_cap": market_cap,
        })
        points = 0.0
        max_points = 0.0
        def add(condition, weight):
            nonlocal points, max_points
            if condition is not None:
                max_points += weight
                if condition:
                    points += weight
        add(revenue_growth is not None and revenue_growth > 0.10, 20)
        add(eps_growth is not None and eps_growth > 0.10, 15)
        add(net_margin is not None and net_margin > 0.10, 15)
        add(fcf is not None and fcf > 0, 15)
        add(fcf_growth is not None and fcf_growth > 0, 10)
        add(roe is not None and roe > 0.15, 10)
        add(debt_equity is not None and debt_equity < 1.0, 5)
        add(eps is not None and eps > 0, 5)
        add(pe is not None and 0 < pe < 50, 5)
        out["fundamental_score"] = round(100 * points / max_points, 1) if max_points else None
    except Exception as exc:
        out["fundamental_error"] = str(exc)[:120]
    return {"ticker": ticker, **out}


def download_fundamentals(tickers: list[str], workers: int = 8) -> dict[str, dict]:
    results = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_one, ticker): ticker for ticker in tickers}
        for future in as_completed(futures):
            row = future.result()
            results[row["ticker"]] = row
    return results
