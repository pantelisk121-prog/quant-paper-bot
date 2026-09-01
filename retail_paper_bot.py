import os
import json
import datetime
import pandas as pd
import numpy as np
import yfinance as yf
import statsmodels.api as sm
from statsmodels.regression.rolling import RollingOLS

# ==========================================
# CONFIGURATION & PARAMETERS
# ==========================================
INITIAL_CAPITAL = 10000.0  # Starting virtual capital ($10,000)
TRANSACTION_COST = 0.0005   # 5 bps (0.05%) slippage/fee per trade
RISK_FREE_RATE = 0.045      # 4.5% yield on idle cash

STATE_FILE = "portfolio_state.json"
TRADES_LOG = "paper_trades.csv"
PERF_LOG = "daily_performance.csv"

PAIRS = {
    1: {'y': 'HD', 'x': 'LOW', 'threshold': 1.75},
    2: {'y': 'WMT', 'x': 'TGT', 'threshold': 1.75}
}
TICKERS = ['HD', 'LOW', 'WMT', 'TGT', 'SPY', '^VIX']

# ==========================================
# RESILIENT DATA FETCHING (Yahoo + Stooq Fallback)
# ==========================================
def fetch_single_ticker(ticker):
    """Fetches historical daily close series with fallback logic to prevent IP blocks."""
    # 1. Try yfinance single ticker query
    try:
        df = yf.Ticker(ticker).history(period="6mo")
        if not df.empty and "Close" in df.columns:
            s = df["Close"]
            s.name = ticker
            return s
    except Exception:
        pass

    # 2. Fallback to Stooq free CSV data feed
    try:
        stooq_symbol = ticker.replace("^", "").lower()
        if not stooq_symbol.endswith(".us"):
            stooq_symbol += ".us"
        url = f"https://stooq.com/q/d/l/?s={stooq_symbol}&i=d"
        stooq_df = pd.read_csv(url)
        if not stooq_df.empty and "Close" in stooq_df and "Date" in stooq_df:
            stooq_df["Date"] = pd.to_datetime(stooq_df["Date"])
            stooq_df.set_index("Date", inplace=True)
            stooq_df.sort_index(inplace=True)
            s = stooq_df["Close"].tail(130)
            s.name = ticker
            return s
    except Exception:
        pass

    return pd.Series(dtype=float, name=ticker)

def load_market_data(tickers):
    """Builds composite price matrix across all tickers."""
    series_list = []
    for ticker in tickers:
        s = fetch_single_ticker(ticker)
        if not s.empty:
            series_list.append(s)
        else:
            print(f"Warning: Failed to fetch data for {ticker}")

    if not series_list:
        raise ValueError("Failed to retrieve market data for all symbols.")

    df = pd.concat(series_list, axis=1).ffill().bfill().dropna()
    if "^VIX" in df.columns:
        df = df.rename(columns={'^VIX': 'VIX'})
    return df

# ==========================================
# STATE MANAGEMENT
# ==========================================
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {
        "cash": INITIAL_CAPITAL,
        "positions": {"HD": 0.0, "LOW": 0.0, "WMT": 0.0, "TGT": 0.0, "SPY": 0.0},
        "last_run": None
    }

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=4)

# ==========================================
# QUANT ENGINE & SIGNAL CALCULATIONS
# ==========================================
def run_strategy_engine():
    print("Fetching market data...")
    data = load_market_data(TICKERS)
    current_prices = data.iloc[-1].to_dict()
    vix_current = current_prices.get('VIX', 20.0)

    window = 60
    conviction_scores = {}
    signals = {}

    for i, pair in PAIRS.items():
        y, x = pair['y'], pair['x']

        # Rolling OLS (lagged 1 day to prevent lookahead bias)
        X = sm.add_constant(data[x])
        model = RollingOLS(data[y], X, window=window).fit()
        alpha = model.params['const'].shift(1)
        beta = model.params[x].shift(1)

        spread = data[y] - (beta * data[x] + alpha)
        z_series = (spread - spread.rolling(window).mean()) / spread.rolling(window).std()
        z_current = z_series.iloc[-1]

        threshold = pair['threshold']
        if abs(z_current) > threshold:
            sig = -np.sign(z_current)
        elif abs(z_current) < 0.5:
            sig = 0.0
        else:
            sig = np.nan

        # Hard stop (|Z| > 4.0) & VIX Kill Switch (> 30)
        if abs(z_current) > 4.0 or vix_current > 30:
            sig = 0.0

        signals[i] = sig
        conviction_scores[i] = abs(z_current) if sig != 0.0 and not np.isnan(sig) else 0.0

    # SPY Hedge Signal
    if vix_current > 40:
        spy_signal = 1.0
    elif vix_current < 25:
        spy_signal = 0.0
    else:
        spy_signal = np.nan

    spy_conviction = 3.0 if spy_signal == 1.0 else 0.0

    return current_prices, signals, conviction_scores, spy_signal, spy_conviction

# ==========================================
# EXECUTION & LOGGING ENGINE
# ==========================================
def execute_paper_trading():
    today_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state = load_state()
    prices, signals, conviction_scores, spy_signal, spy_conviction = run_strategy_engine()

    portfolio_value = state['cash']
    for ticker, shares in state['positions'].items():
        portfolio_value += shares * prices.get(ticker, 0.0)

    print(f"\n--- ACCOUNT STATUS ({today_str}) ---")
    print(f"Total Portfolio Value: ${portfolio_value:,.2f}")
    print(f"Available Cash:        ${state['cash']:,.2f}")
    print(f"Current VIX Level:     {prices.get('VIX', 0.0):.2f}")

    total_conviction = sum(conviction_scores.values()) + spy_conviction
    target_dollar_alloc = {t: 0.0 for t in ['HD', 'LOW', 'WMT', 'TGT', 'SPY']}

    if total_conviction > 0:
        for i, pair in PAIRS.items():
            if conviction_scores[i] > 0:
                weight = conviction_scores[i] / total_conviction
                allocated_cash = portfolio_value * weight

                sig = signals[i]
                target_dollar_alloc[pair['y']] += sig * (allocated_cash * 0.5)
                target_dollar_alloc[pair['x']] += -sig * (allocated_cash * 0.5)

        if spy_conviction > 0:
            spy_weight = spy_conviction / total_conviction
            target_dollar_alloc['SPY'] = portfolio_value * spy_weight

    trades_executed = []
    for ticker in ['HD', 'LOW', 'WMT', 'TGT', 'SPY']:
        current_price = prices.get(ticker, 0.0)
        if current_price <= 0:
            continue
        target_dollars = target_dollar_alloc[ticker]
        target_shares = target_dollars / current_price

        current_shares = state['positions'].get(ticker, 0.0)
        share_delta = target_shares - current_shares

        if abs(share_delta) > 0.001:
            trade_cost = abs(share_delta) * current_price * TRANSACTION_COST
            capital_required = share_delta * current_price

            state['cash'] -= (capital_required + trade_cost)
            state['positions'][ticker] = target_shares

            trade_record = {
                "Timestamp": today_str,
                "Ticker": ticker,
                "Action": "BUY" if share_delta > 0 else "SELL",
                "Shares": round(share_delta, 4),
                "Price": round(current_price, 2),
                "Slippage_Fee": round(trade_cost, 4),
                "New_Position_Shares": round(target_shares, 4)
            }
            trades_executed.append(trade_record)
            print(f"ORDER FILLED: {trade_record['Action']} {abs(share_delta):.2f} shares of {ticker} @ ${current_price:.2f}")

    state['last_run'] = today_str
    save_state(state)

    if trades_executed:
        df_trades = pd.DataFrame(trades_executed)
        header = not os.path.exists(TRADES_LOG)
        df_trades.to_csv(TRADES_LOG, mode='a', index=False, header=header)

    perf_record = {
        "Date": today_str,
        "Total_Equity": round(portfolio_value, 2),
        "Cash": round(state['cash'], 2),
        "HD_Shares": round(state['positions']['HD'], 4),
        "LOW_Shares": round(state['positions']['LOW'], 4),
        "WMT_Shares": round(state['positions']['WMT'], 4),
        "TGT_Shares": round(state['positions']['TGT'], 4),
        "SPY_Shares": round(state['positions']['SPY'], 4)
    }
    df_perf = pd.DataFrame([perf_record])
    perf_header = not os.path.exists(PERF_LOG)
    df_perf.to_csv(PERF_LOG, mode='a', index=False, header=perf_header)

    print("Paper engine run complete. State updated and logged.")

if __name__ == "__main__":
    execute_paper_trading()
