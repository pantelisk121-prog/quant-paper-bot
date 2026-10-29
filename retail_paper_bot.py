import yfinance as yf
import pandas as pd
import statsmodels.api as sm
import numpy as np
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

# --- STRATEGY CONFIGURATION ---
PAIRS = [('HD', 'LOW'), ('WMT', 'TGT')]
PAIR_NAMES = [f"{s1}_{s2}" for s1, s2 in PAIRS]
Z_ENTRY = 1.75
Z_EXIT = 0.50
Z_STOP = 4.0
VIX_MAX = 30.0
SLIPPAGE = 0.0005  # 0.05% friction
LOOKBACK = 60
INITIAL_CAPITAL = 10000.0  # Matches $10,000 baseline
MAX_PROFIT_HOLD_DAYS = 15  # Require pnl > 0 at Z_EXIT for first 15 calendar days
REBALANCE_MIN_Z = 2.25     # Minimum Z-score required to trim an underwater open position
MARKET_TZ = ZoneInfo("America/New_York")

# --- FILE PATHS ---
STATE_FILE = 'portfolio_state.json'
TRADES_FILE = 'paper_trades.csv'
PERF_FILE = 'daily_performance.csv'


def ny_now():
    """Always return current datetime in US Eastern Market Time (EDT/EST)."""
    return datetime.now(MARKET_TZ).replace(tzinfo=None)


def parse_date(date_str):
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(str(date_str).strip(), fmt)
        except ValueError:
            continue
    return None


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                if 'cash' not in state: state['cash'] = INITIAL_CAPITAL
                if 'positions' not in state: state['positions'] = {}
                return state
        except:
            pass
    return {
        'cash': INITIAL_CAPITAL,
        'positions': {'HD': 0.0, 'LOW': 0.0, 'WMT': 0.0, 'TGT': 0.0, 'SPY': 0.0},
        'last_run': ny_now().strftime('%Y-%m-%d %H:%M:%S')
    }


def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=4)


def log_trade(pair_name, action, stock1, stock2, qty1, qty2, price1, price2, pnl=0.0):
    trade_data = {
        'date': ny_now().strftime('%Y-%m-%d %H:%M:%S'),
        'pair': pair_name,
        'action': action,
        'stock1': stock1,
        'stock2': stock2,
        'qty1': round(float(qty1), 4),
        'qty2': round(float(qty2), 4),
        'price1': round(float(price1), 2),
        'price2': round(float(price2), 2),
        'pnl': round(float(pnl), 2)
    }
    df = pd.DataFrame([trade_data])
    if os.path.exists(TRADES_FILE):
        df.to_csv(TRADES_FILE, mode='a', header=False, index=False)
    else:
        df.to_csv(TRADES_FILE, index=False)


def fetch_single_close(ticker_symbol):
    """
    Fetch daily closes AND force-inject today's live/intraday close if Yahoo's
    daily ('1d') CDN cache is lagging behind on GitHub Actions servers.
    """
    t = yf.Ticker(ticker_symbol)
    hist = t.history(period="90d", interval="1d", auto_adjust=False)
    if hist.empty or 'Close' not in hist.columns:
        raw = yf.download(ticker_symbol, period="90d", interval="1d", progress=False, auto_adjust=False)['Close']
        s = raw.squeeze().dropna()
    else:
        s = hist['Close'].dropna()

    # Convert index to US Eastern date strings (YYYY-MM-DD)
    idx_dt = pd.to_datetime(s.index)
    if idx_dt.tz is not None:
        idx_dt = idx_dt.tz_convert(MARKET_TZ)
    s.index = idx_dt.strftime('%Y-%m-%d')
    s = s[~s.index.duplicated(keep='last')]

    today_dt = ny_now()
    today_str = today_dt.strftime('%Y-%m-%d')

    # Check if today's bar is missing OR if Yahoo duplicated yesterday's exact price
    needs_intraday = False
    if today_dt.weekday() < 5:  # Monday-Friday
        if today_str not in s.index:
            needs_intraday = True
        elif len(s) >= 2 and abs(float(s.iloc[-1]) - float(s.iloc[-2])) < 1e-6:
            needs_intraday = True

    if needs_intraday:
        try:
            # Pull un-cached 5-minute intraday bars to get today's true 4:00 PM market close
            intraday = t.history(period="5d", interval="5m", prepost=False, auto_adjust=False)
            if not intraday.empty and 'Close' in intraday.columns:
                intra_close = intraday['Close'].dropna()
                intra_idx = pd.to_datetime(intra_close.index)
                if intra_idx.tz is not None:
                    intra_idx = intra_idx.tz_convert(MARKET_TZ)
                intra_dates = intra_idx.strftime('%Y-%m-%d')
                today_bars = intra_close[intra_dates == today_str]
                if not today_bars.empty:
                    live_px = float(today_bars.iloc[-1])
                    s.loc[today_str] = live_px
                    print(f"  [LIVE INTRADAY FIX] {ticker_symbol}: Injected {today_str} close = ${live_px:.2f} (from 5m feed)")
                else:
                    last_bar_date = intra_dates[-1]
                    live_px = float(intra_close.iloc[-1])
                    s.loc[last_bar_date] = live_px
                    print(f"  [LIVE INTRADAY FIX] {ticker_symbol}: Injected {last_bar_date} close = ${live_px:.2f}")
        except Exception as e:
            print(f"  [WARN] Intraday fallback failed for {ticker_symbol}: {e}")

        # Secondary fallback using fast_info.last_price
        if today_str not in s.index:
            try:
                fast_px = float(t.fast_info['last_price'])
                if fast_px > 0:
                    s.loc[today_str] = fast_px
                    print(f"  [FAST_INFO FIX] {ticker_symbol}: Injected {today_str} close = ${fast_px:.2f}")
            except Exception:
                pass

    return s.sort_index()


def calculate_z_score(stock1, stock2):
    s1_series = fetch_single_close(stock1)
    s2_series = fetch_single_close(stock2)

    data = pd.DataFrame({stock1: s1_series, stock2: s2_series}).dropna()
    if len(data) < LOOKBACK:
        return None, None

    data = data.tail(LOOKBACK)
    latest_bar_date = data.index[-1]
    p1_val = float(data[stock1].iloc[-1])
    p2_val = float(data[stock2].iloc[-1])
    print(f"  [DATA CHECK] {stock1}: ${p1_val:.2f} \vert{} {stock2}:${p2_val:.2f} (Bar Date: {latest_bar_date})")

    y = data[stock1]
    X = sm.add_constant(data[stock2])

    model = sm.OLS(y, X).fit()
    spread = y - model.predict(X)

    raw_z = (spread.iloc[-1] - spread.mean()) / spread.std()
    z_score = float(np.ravel(raw_z)[0])

    latest_prices = {
        stock1: p1_val,
        stock2: p2_val
    }

    return z_score, latest_prices


def main():
    print("Fetching VIX data...")
    vix_series = fetch_single_close('^VIX')
    vix = float(vix_series.iloc[-1])
    
    print(f"Current VIX (Fear Factor): {vix:.2f}")
    if vix > VIX_MAX:
        print("VIX circuit breaker triggered (>30). Halting trading operations.")
        return

    state = load_state()
    z_scores_log = {}
    prices_log = {}
    new_entries = []
    today_dt = ny_now()
    
    print("\n==================================================")
    print("             DAILY PAIR Z-SCORE MONITOR           ")
    print("==================================================")
    
    # --- PASS 1: FETCH DATA & PROCESS EXITS FIRST ---
    for s1, s2 in PAIRS:
        pair_name = f"{s1}_{s2}"
        z, latest_prices = calculate_z_score(s1, s2)
        if z is None:
            continue
            
        z_scores_log[pair_name] = z
        prices_log[pair_name] = (s1, s2, latest_prices[s1], latest_prices[s2])
        p1, p2 = latest_prices[s1], latest_prices[s2]
        
        print(f"  {s1} / {s2} Z-Score: {z:+.2f}  |  Target: ±{Z_ENTRY}  (Dist: {abs(Z_ENTRY - abs(z)):.2f})")
        
        if pair_name in state['positions'] and isinstance(state['positions'][pair_name], dict):
            pos = state['positions'][pair_name]
            val1 = pos['qty1'] * p1
            val2 = pos['qty2'] * p2
            
            exit_val1 = val1 * (1 - SLIPPAGE if pos['qty1'] > 0 else 1 + SLIPPAGE)
            exit_val2 = val2 * (1 - SLIPPAGE if pos['qty2'] > 0 else 1 + SLIPPAGE)
            total_exit_val = exit_val1 + exit_val2
            entry_val = (pos['qty1'] * pos['entry_price1']) + (pos['qty2'] * pos['entry_price2'])
            pnl = total_exit_val - entry_val
            
            entry_dt = parse_date(pos.get('entry_date', '2026-10-14'))
            days_held = (today_dt.date() - entry_dt.date()).days if entry_dt else 0

            should_exit = False
            action = None

            if abs(z) >= Z_STOP:
                should_exit = True
                action = 'EXIT (Stop Loss)'
            elif abs(z) <= Z_EXIT:
                if pnl > 0:
                    should_exit = True
                    action = 'EXIT (Take Profit)'
                elif days_held >= MAX_PROFIT_HOLD_DAYS:
                    should_exit = True
                    action = f'EXIT (Time-Capped {days_held}d)'
                else:
                    print(
                        f"  -> HOLD {pair_name}: Z-Score ({z:+.2f}) <= ±{Z_EXIT}, but Net PnL (${pnl:+.2f}) <= $0 "
                        f"on Day {days_held}/{MAX_PROFIT_HOLD_DAYS}. Waiting for price convergence."
                    )

            if should_exit:
                print(f"  -> {action} Triggered for {pair_name} (Day {days_held} | Net PnL: ${pnl:+.2f})")
                state['cash'] += total_exit_val
                log_trade(pair_name, action, s1, s2, pos['qty1'], pos['qty2'], p1, p2, pnl)
                del state['positions'][pair_name]
        else:
            if abs(z) >= Z_ENTRY and abs(z) < Z_STOP:
                new_entries.append(pair_name)

    open_pair_names = [
        p for p in PAIR_NAMES
        if p in state['positions'] and isinstance(state['positions'][p], dict)
    ]

    # --- PASS 2: SMART REBALANCE GUARD & DYNAMIC CONVICTION ALLOCATION ---
    if new_entries and open_pair_names:
        open_pair = open_pair_names[0]
        pos = state['positions'][open_pair]
        _, _, op1, op2 = prices_log[open_pair]
        open_z = abs(z_scores_log[open_pair])

        est_exit1 = (pos['qty1'] * op1) * (1 - SLIPPAGE if pos['qty1'] > 0 else 1 + SLIPPAGE)
        est_exit2 = (pos['qty2'] * op2) * (1 - SLIPPAGE if pos['qty2'] > 0 else 1 + SLIPPAGE)
        entry_cost = (pos['qty1'] * pos['entry_price1']) + (pos['qty2'] * pos['entry_price2'])
        unrealized_pnl = (est_exit1 + est_exit2) - entry_cost

        approved_entries = []
        for cand_pair in new_entries:
            cand_z = abs(z_scores_log[cand_pair])
            if unrealized_pnl > 0 or (cand_z >= REBALANCE_MIN_Z and cand_z > open_z):
                reason = (
                    f"Open trade profitable (${unrealized_pnl:+.2f})"
                    if unrealized_pnl > 0
                    else f"New |Z| ({cand_z:.2f}) >= {REBALANCE_MIN_Z} and > Open |Z| ({open_z:.2f})"
                )
                print(f"  -> REBALANCE APPROVED for {cand_pair}: {reason}")
                approved_entries.append(cand_pair)
            else:
                print(
                    f"  -> REBALANCE BLOCKED for {cand_pair}: {open_pair} is in drawdown (${unrealized_pnl:+.2f}) "
                    f"and {cand_pair} |Z| ({cand_z:.2f}) fails override (requires |Z| >= {REBALANCE_MIN_Z} and > {open_z:.2f}). "
                    f"Holding 100% in {open_pair} to avoid locking in loss."
                )
        new_entries = approved_entries

    if new_entries:
        active_pairs = open_pair_names + new_entries
        total_z = sum(abs(z_scores_log[p]) for p in active_pairs)
        
        for open_pair in open_pair_names:
            pos = state['positions'][open_pair]
            s1, s2, p1, p2 = prices_log[open_pair]
            target_weight = abs(z_scores_log[open_pair]) / total_z
            current_weight = pos.get('weight', 1.0)
            
            if target_weight < current_weight:
                keep_ratio = target_weight / current_weight
                close_ratio = 1.0 - keep_ratio
                print(f"  -> REBALANCING {open_pair} to {target_weight*100:.1f}% conviction weight")
                
                closed_qty1 = pos['qty1'] * close_ratio
                closed_qty2 = pos['qty2'] * close_ratio
                
                exit_val1 = (closed_qty1 * p1) * (1 - SLIPPAGE if closed_qty1 > 0 else 1 + SLIPPAGE)
                exit_val2 = (closed_qty2 * p2) * (1 - SLIPPAGE if closed_qty2 > 0 else 1 + SLIPPAGE)
                total_exit_val = exit_val1 + exit_val2
                
                entry_val = (closed_qty1 * pos['entry_price1']) + (closed_qty2 * pos['entry_price2'])
                pnl = total_exit_val - entry_val
