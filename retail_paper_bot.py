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
VIX_MAX = 30.0             # Liquidate pairs and rotate 100% into SPY above this level
VIX_REENTRY = 25.0         # Exit SPY and resume pairs trading once VIX cools to/below this level
SLIPPAGE = 0.0005          # 0.05% friction
LOOKBACK = 60
INITIAL_CAPITAL = 10000.0  # Matches 10,000 USD baseline
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
                if 'cash' not in state:
                    state['cash'] = INITIAL_CAPITAL
                if 'positions' not in state:
                    state['positions'] = {}
                return state
        except Exception:
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
                    print(f"  [LIVE INTRADAY FIX] {ticker_symbol}: Injected {today_str} close = {live_px:.2f} (from 5m feed)")
                else:
                    last_bar_date = intra_dates[-1]
                    live_px = float(intra_close.iloc[-1])
                    s.loc[last_bar_date] = live_px
                    print(f"  [LIVE INTRADAY FIX] {ticker_symbol}: Injected {last_bar_date} close = {live_px:.2f}")
        except Exception as e:
            print(f"  [WARN] Intraday fallback failed for {ticker_symbol}: {e}")

        # Secondary fallback using fast_info.last_price
        if today_str not in s.index:
            try:
                fast_px = float(t.fast_info['last_price'])
                if fast_px > 0:
                    s.loc[today_str] = fast_px
                    print(f"  [FAST_INFO FIX] {ticker_symbol}: Injected {today_str} close = {fast_px:.2f}")
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
    print(f"  [DATA CHECK] {stock1}: {p1_val:.2f} USD -- {stock2}: {p2_val:.2f} USD (Bar Date: {latest_bar_date})")

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


def close_pair_position(state, pair_name, prices_log, action):
    """Fully close an open pair position, credit realized PnL to cash, and log the trade."""
    pos = state['positions'][pair_name]
    s1, s2, p1, p2 = prices_log[pair_name]

    exit_val1 = (pos['qty1'] * p1) * (1 - SLIPPAGE if pos['qty1'] > 0 else 1 + SLIPPAGE)
    exit_val2 = (pos['qty2'] * p2) * (1 - SLIPPAGE if pos['qty2'] > 0 else 1 + SLIPPAGE)
    total_exit_val = exit_val1 + exit_val2

    entry_val = (pos['qty1'] * pos['entry_price1']) + (pos['qty2'] * pos['entry_price2'])
    pnl = total_exit_val - entry_val

    state['cash'] += total_exit_val
    log_trade(pair_name, action, s1, s2, pos['qty1'], pos['qty2'], p1, p2, pnl)
    del state['positions'][pair_name]
    return pnl


def compute_total_equity(state, prices_log, spy_price):
    """Compute mark-to-market equity across cash, open pairs, and any SPY safe-haven position."""
    equity = float(state['cash'])
    for pair_name in PAIR_NAMES:
        if pair_name in state['positions'] and isinstance(state['positions'][pair_name], dict) and pair_name in prices_log:
            pos = state['positions'][pair_name]
            _, _, p1, p2 = prices_log[pair_name]
            equity += (pos['qty1'] * p1) + (pos['qty2'] * p2)

    if 'SPY_POS' in state['positions'] and isinstance(state['positions']['SPY_POS'], dict):
        equity += state['positions']['SPY_POS']['qty'] * spy_price

    return equity


def open_pair_position(state, pair_name, prices_log, z_score, allocation_weight, current_equity, market_date_str):
    """Open a dollar-neutral pair position sized to allocation_weight * current_equity."""
    s1, s2, p1, p2 = prices_log[pair_name]
    allocation = current_equity * allocation_weight

    print(f"  -> ENTRY Triggered for {pair_name} (Allocation: {allocation_weight*100:.1f}% -- {allocation:,.2f} USD)")

    if z_score > 0:
        w1, w2 = -0.5, 0.5  # Short s1, Long s2
    else:
        w1, w2 = 0.5, -0.5  # Long s1, Short s2

    alloc1, alloc2 = allocation * w1, allocation * w2
    entry_p1 = p1 * (1 + SLIPPAGE if w1 > 0 else 1 - SLIPPAGE)
    entry_p2 = p2 * (1 + SLIPPAGE if w2 > 0 else 1 - SLIPPAGE)

    qty1 = alloc1 / entry_p1
    qty2 = alloc2 / entry_p2

    cost = (qty1 * entry_p1) + (qty2 * entry_p2)
    state['cash'] -= cost

    state['positions'][pair_name] = {
        'qty1': qty1,
        'qty2': qty2,
        'entry_price1': entry_p1,
        'entry_price2': entry_p2,
        'weight': allocation_weight,
        'entry_date': market_date_str
    }
    log_trade(pair_name, 'ENTRY', s1, s2, qty1, qty2, entry_p1, entry_p2, 0.0)


def main():
    print("Fetching VIX & SPY macro data...")
    vix_series = fetch_single_close('^VIX')
    spy_series = fetch_single_close('SPY')

    vix = float(vix_series.iloc[-1])
    spy_price = float(spy_series.iloc[-1])
    market_date_str = str(spy_series.index[-1])
    today_dt = ny_now()
    market_dt = parse_date(market_date_str) or today_dt

    print(f"Current VIX (Fear Factor): {vix:.2f} | SPY: {spy_price:.2f} USD (Market Date: {market_date_str})")

    state = load_state()
    z_scores_log = {}
    prices_log = {}

    print("\n==================================================")
    print("             DAILY PAIR Z-SCORE MONITOR           ")
    print("==================================================")

    # --- STEP 1: ALWAYS FETCH PAIR DATA & Z-SCORES FOR MONITORING / LOGGING ---
    for s1, s2 in PAIRS:
        pair_name = f"{s1}_{s2}"
        z, latest_prices = calculate_z_score(s1, s2)
        if z is None:
            continue
        z_scores_log[pair_name] = z
        prices_log[pair_name] = (s1, s2, latest_prices[s1], latest_prices[s2])
        print(f"  {s1} / {s2} Z-Score: {z:+.2f} -- Target: +/-{Z_ENTRY} (Dist: {abs(Z_ENTRY - abs(z)):.2f})")

    # --- STEP 2: VIX MACRO CIRCUIT BREAKER & HYSTERESIS SAFE HAVEN (SPY) ---
    in_spy = 'SPY_POS' in state['positions'] and isinstance(state['positions']['SPY_POS'], dict)
    allow_pair_trading = True

    if vix > VIX_MAX:
        print(f"\n  [VIX CIRCUIT BREAKER] VIX ({vix:.2f}) > {VIX_MAX:.1f}. Activating SPY Safe Haven.")
        allow_pair_trading = False

        # Liquidate all open pairs back into cash
        for pair_name in PAIR_NAMES:
            if pair_name in state['positions'] and isinstance(state['positions'][pair_name], dict) and pair_name in prices_log:
                pnl = close_pair_position(state, pair_name, prices_log, 'EXIT (VIX Circuit Breaker)')
                print(f"  -> Liquidated {pair_name} due to VIX > {VIX_MAX:.1f} (Net PnL: {pnl:+.2f} USD)")

        # Deploy 100% of cash into SPY if not already holding SPY
        if not in_spy and state['cash'] > 0:
            spy_entry_price = spy_price * (1 + SLIPPAGE)
            spy_qty = state['cash'] / spy_entry_price
            invested_cash = state['cash']
            state['cash'] = 0.0
            state['positions']['SPY_POS'] = {
                'qty': spy_qty,
                'entry_price': spy_entry_price,
                'entry_date': market_date_str
            }
            log_trade('SPY_HEDGE', 'ENTRY (VIX Safe Haven)', 'SPY', 'CASH', spy_qty, 0.0, spy_entry_price, 0.0, 0.0)
            print(f"  -> Deployed {invested_cash:,.2f} USD into SPY: {spy_qty:.4f} shares @ {spy_entry_price:.2f} USD")
            in_spy = True
        elif in_spy:
            print(f"  -> Holding SPY Safe Haven ({state['positions']['SPY_POS']['qty']:.4f} shares) while VIX > {VIX_REENTRY:.1f}.")

    elif in_spy and vix > VIX_REENTRY:
        print(f"\n  [VIX HYSTERESIS HOLD] VIX ({vix:.2f}) > {VIX_REENTRY:.1f} re-entry threshold. Holding SPY Safe Haven.")
        allow_pair_trading = False

    elif in_spy and vix <= VIX_REENTRY:
        spy_pos = state['positions']['SPY_POS']
        spy_exit_price = spy_price * (1 - SLIPPAGE)
        exit_val = spy_pos['qty'] * spy_exit_price
        entry_val = spy_pos['qty'] * spy_pos['entry_price']
        pnl = exit_val - entry_val
        state['cash'] += exit_val
        log_trade('SPY_HEDGE', 'EXIT (VIX Cooldown)', 'SPY', 'CASH', spy_pos['qty'], 0.0, spy_exit_price, 0.0, pnl)
        del state['positions']['SPY_POS']
        in_spy = False
        print(f"\n  [VIX COOLDOWN] VIX ({vix:.2f}) <= {VIX_REENTRY:.1f}. Exited SPY @ {spy_exit_price:.2f} USD (Net PnL: {pnl:+.2f} USD). Resuming pairs trading.")

    # --- STEP 3: NORMAL PAIRS TRADING (EXITS, CASH-FIRST ALLOCATION & Z-WEIGHTED REBALANCING) ---
    if allow_pair_trading:
        new_entries = []

        # PASS 1: Process Exits & Collect New Entry Candidates
        for pair_name in PAIR_NAMES:
            if pair_name not in z_scores_log:
                continue

            z = z_scores_log[pair_name]
            s1, s2, p1, p2 = prices_log[pair_name]

            if pair_name in state['positions'] and isinstance(state['positions'][pair_name], dict):
                pos = state['positions'][pair_name]
                exit_val1 = (pos['qty1'] * p1) * (1 - SLIPPAGE if pos['qty1'] > 0 else 1 + SLIPPAGE)
                exit_val2 = (pos['qty2'] * p2) * (1 - SLIPPAGE if pos['qty2'] > 0 else 1 + SLIPPAGE)
                total_exit_val = exit_val1 + exit_val2
                entry_val = (pos['qty1'] * pos['entry_price1']) + (pos['qty2'] * pos['entry_price2'])
                pnl = total_exit_val - entry_val

                entry_dt = parse_date(pos.get('entry_date', '2026-10-14'))
                days_held = (market_dt.date() - entry_dt.date()).days if entry_dt else 0

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
                            f"  -> HOLD {pair_name}: Z-Score ({z:+.2f}) <= +/-{Z_EXIT}, but Net PnL ({pnl:+.2f} USD) <= 0 "
                            f"on Day {days_held}/{MAX_PROFIT_HOLD_DAYS}. Waiting for price convergence."
                        )

                if should_exit:
                    realized_pnl = close_pair_position(state, pair_name, prices_log, action)
                    print(f"  -> {action} Triggered for {pair_name} (Day {days_held} -- Net PnL: {realized_pnl:+.2f} USD)")
            else:
                if abs(z) >= Z_ENTRY and abs(z) < Z_STOP:
                    new_entries.append(pair_name)

        open_pair_names = [
            p for p in PAIR_NAMES
            if p in state['positions'] and isinstance(state['positions'][p], dict)
        ]

        # PASS 2: Cash-First, Z-Score-Weighted Dynamic Conviction Allocation
        if new_entries:
            if not open_pair_names:
                # 100% free capital: allocate across all new entries strictly by Z-score weight
                current_equity = compute_total_equity(state, prices_log, spy_price)
                total_z = sum(abs(z_scores_log[p]) for p in new_entries)
                for pair_name in new_entries:
                    target_weight = abs(z_scores_log[pair_name]) / total_z
                    open_pair_position(
                        state, pair_name, prices_log, z_scores_log[pair_name],
                        target_weight, current_equity, market_date_str
                    )
            else:
                # One pair is already open; evaluate free cash first, then Z-score-weighted trim if needed
                open_pair = open_pair_names[0]
                cand_pair = new_entries[0]

                pos = state['positions'][open_pair]
                os1, os2, op1, op2 = prices_log[open_pair]
                open_z = abs(z_scores_log[open_pair])
                cand_z = abs(z_scores_log[cand_pair])

                current_weight_open = float(pos.get('weight', 1.0))
                free_weight = max(0.0, 1.0 - current_weight_open)

                total_z = open_z + cand_z
                target_weight_cand = cand_z / total_z
                target_weight_open = open_z / total_z

                # Exact shortfall beyond available idle cash (e.g., needs 70% - 40% cash = 30% trim)
                trim_needed_equity_pct = max(0.0, target_weight_cand - free_weight)

                est_exit1 = (pos['qty1'] * op1) * (1 - SLIPPAGE if pos['qty1'] > 0 else 1 + SLIPPAGE)
                est_exit2 = (pos['qty2'] * op2) * (1 - SLIPPAGE if pos['qty2'] > 0 else 1 + SLIPPAGE)
                entry_cost = (pos['qty1'] * pos['entry_price1']) + (pos['qty2'] * pos['entry_price2'])
                unrealized_pnl = (est_exit1 + est_exit2) - entry_cost

                cand_alloc_weight = 0.0

                if trim_needed_equity_pct <= 1e-6:
                    # Free cash completely covers the new pair's Z-score-weighted target — zero trim needed
                    cand_alloc_weight = target_weight_cand
                    print(
                        f"  -> CASH-ONLY ENTRY for {cand_pair}: Free cash ({free_weight*100:.1f}%) covers "
                        f"Z-weighted target ({target_weight_cand*100:.1f}%). {open_pair} untouched at {current_weight_open*100:.1f}%."
                    )
                else:
                    # Shortfall requires trimming open_pair; check Smart Rebalance Guard
                    trim_approved = unrealized_pnl > 0 or (cand_z >= REBALANCE_MIN_Z and cand_z > open_z)
                    if trim_approved:
                        reason = (
                            f"Open trade profitable ({unrealized_pnl:+.2f} USD)"
                            if unrealized_pnl > 0
                            else f"New abs(Z) ({cand_z:.2f}) >= {REBALANCE_MIN_Z} and > Open abs(Z) ({open_z:.2f})"
                        )
                        print(
                            f"  -> REBALANCING APPROVED for {cand_pair}: {reason}. "
                            f"Using {free_weight*100:.1f}% free cash + {trim_needed_equity_pct*100:.1f}% equity trim "
                            f"from {open_pair} for {target_weight_cand*100:.1f}% total Z-weighted allocation."
                        )

                        # Trim exact shortfall from open_pair's current weight
                        close_ratio = min(1.0, trim_needed_equity_pct / current_weight_open)
                        keep_ratio = 1.0 - close_ratio

                        closed_qty1 = pos['qty1'] * close_ratio
                        closed_qty2 = pos['qty2'] * close_ratio

                        exit_val1 = (closed_qty1 * op1) * (1 - SLIPPAGE if closed_qty1 > 0 else 1 + SLIPPAGE)
                        exit_val2 = (closed_qty2 * op2) * (1 - SLIPPAGE if closed_qty2 > 0 else 1 + SLIPPAGE)
                        total_exit_val = exit_val1 + exit_val2

                        entry_val = (closed_qty1 * pos['entry_price1']) + (closed_qty2 * pos['entry_price2'])
                        pnl = total_exit_val - entry_val

                        state['cash'] += total_exit_val
                        pos['qty1'] *= keep_ratio
                        pos['qty2'] *= keep_ratio
                        pos['weight'] = target_weight_open

                        log_trade(open_pair, 'REBALANCE (Trim)', os1, os2, closed_qty1, closed_qty2, op1, op2, pnl)
                        cand_alloc_weight = target_weight_cand
                    elif free_weight > 0.01:
                        # Trim blocked to avoid locking in a loss, but deploy idle free cash into cand_pair
                        cand_alloc_weight = free_weight
                        print(
                            f"  -> PARTIAL TRIM BLOCKED ({open_pair} underwater at {unrealized_pnl:+.2f} USD and "
                            f"{cand_pair} abs(Z)={cand_z:.2f} fails override). Deploying available {free_weight*100:.1f}% "
                            f"free cash into {cand_pair} while leaving {open_pair} untouched at {current_weight_open*100:.1f}%."
                        )
                    else:
                        print(
                            f"  -> REBALANCING BLOCKED for {cand_pair}: {open_pair} is in drawdown ({unrealized_pnl:+.2f} USD) "
                            f"with no idle cash, and {cand_pair} abs(Z) ({cand_z:.2f}) fails override "
                            f"(requires >= {REBALANCE_MIN_Z} and > {open_z:.2f}). Holding 100% in {open_pair}."
                        )

                if cand_alloc_weight > 1e-6:
                    current_equity = compute_total_equity(state, prices_log, spy_price)
                    open_pair_position(
                        state, cand_pair, prices_log, z_scores_log[cand_pair],
                        cand_alloc_weight, current_equity, market_date_str
                    )

    print("==================================================\n")

    # --- STEP 4: SYNC STATE, MARK TO MARKET & LOG DAILY PERFORMANCE ---
    hd_shares = state['positions'].get('HD_LOW', {}).get('qty1', 0.0) if isinstance(state['positions'].get('HD_LOW'), dict) else 0.0
    low_shares = state['positions'].get('HD_LOW', {}).get('qty2', 0.0) if isinstance(state['positions'].get('HD_LOW'), dict) else 0.0
    wmt_shares = state['positions'].get('WMT_TGT', {}).get('qty1', 0.0) if isinstance(state['positions'].get('WMT_TGT'), dict) else 0.0
    tgt_shares = state['positions'].get('WMT_TGT', {}).get('qty2', 0.0) if isinstance(state['positions'].get('WMT_TGT'), dict) else 0.0
    spy_shares = state['positions'].get('SPY_POS', {}).get('qty', 0.0) if isinstance(state['positions'].get('SPY_POS'), dict) else 0.0

    state['positions']['HD'] = round(float(hd_shares), 4)
    state['positions']['LOW'] = round(float(low_shares), 4)
    state['positions']['WMT'] = round(float(wmt_shares), 4)
    state['positions']['TGT'] = round(float(tgt_shares), 4)
    state['positions']['SPY'] = round(float(spy_shares), 4)
    state['last_run'] = today_dt.strftime('%Y-%m-%d %H:%M:%S')

    for pair_name in PAIR_NAMES:
        if pair_name in state['positions'] and isinstance(state['positions'][pair_name], dict):
            if 'entry_date' not in state['positions'][pair_name]:
                state['positions'][pair_name]['entry_date'] = '2026-10-14'

    portfolio_value = compute_total_equity(state, prices_log, spy_price)
    save_state(state)

    log_entry = {
        'date': market_date_str,
        'total_equity': round(float(portfolio_value), 2),
        'cash': round(float(state['cash']), 2),
        'HD_Shares': round(float(hd_shares), 4),
        'LOW_Shares': round(float(low_shares), 4),
        'WMT_Shares': round(float(wmt_shares), 4),
        'TGT_Shares': round(float(tgt_shares), 4),
        'SPY_Shares': round(float(spy_shares), 4),
        'z_hd_low': round(float(z_scores_log.get('HD_LOW', 0.0)), 4),
        'z_wmt_tgt': round(float(z_scores_log.get('WMT_TGT', 0.0)), 4),
        'vix': round(float(vix), 2)
    }

    if os.path.exists(PERF_FILE):
        perf_df = pd.read_csv(PERF_FILE)
        perf_df = pd.concat([perf_df, pd.DataFrame([log_entry])], ignore_index=True)
    else:
        perf_df = pd.DataFrame([log_entry])

    perf_df.drop_duplicates(subset=['date'], keep='last', inplace=True)
    perf_df.to_csv(PERF_FILE, index=False)

    print(f"Daily execution complete ({market_date_str}). Total Portfolio Value: {portfolio_value:,.2f} USD")


if __name__ == "__main__":
    main()
