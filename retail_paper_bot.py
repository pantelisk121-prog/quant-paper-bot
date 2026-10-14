import yfinance as yf
import pandas as pd
import statsmodels.api as sm
import numpy as np
import json
import os
from datetime import datetime

# --- STRATEGY CONFIGURATION ---
PAIRS = [('HD', 'LOW'), ('WMT', 'TGT')]
Z_ENTRY = 1.75
Z_EXIT = 0.50
Z_STOP = 4.0
VIX_MAX = 30.0
SLIPPAGE = 0.0005  # 0.05% friction
LOOKBACK = 60
INITIAL_CAPITAL = 10000.0  # Matches $10,000 baseline

# --- FILE PATHS ---
STATE_FILE = 'portfolio_state.json'
TRADES_FILE = 'paper_trades.csv'
PERF_FILE = 'daily_performance.csv'

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
    return {'cash': INITIAL_CAPITAL, 'positions': {}}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=4)

def log_trade(pair_name, action, stock1, stock2, qty1, qty2, price1, price2, pnl=0.0):
    trade_data = {
        'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
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

def calculate_z_score(stock1, stock2):
    data = yf.download([stock1, stock2], period="90d", progress=False)['Close']
    data = data.dropna()
    if len(data) < LOOKBACK:
        return None, None
    
    data = data.tail(LOOKBACK)
    y = data[stock1]
    X = sm.add_constant(data[stock2])
    
    model = sm.OLS(y, X).fit()
    spread = y - model.predict(X)
    
    raw_z = (spread.iloc[-1] - spread.mean()) / spread.std()
    z_score = float(np.ravel(raw_z)[0])
    
    latest_prices = {
        stock1: float(np.ravel(data[stock1].iloc[-1])[0]),
        stock2: float(np.ravel(data[stock2].iloc[-1])[0])
    }
    
    return z_score, latest_prices

def main():
    print("Fetching VIX data...")
    vix_data = yf.download('^VIX', period="5d", progress=False)['Close']
    vix = float(np.ravel(vix_data.dropna())[-1])
    
    print(f"Current VIX (Fear Factor): {vix:.2f}")
    if vix > VIX_MAX:
        print("VIX circuit breaker triggered (>30). Halting trading operations.")
        return

    state = load_state()
    z_scores_log = {}
    prices_log = {}
    new_entries = []
    
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
        
        if pair_name in state['positions']:
            pos = state['positions'][pair_name]
            val1 = pos['qty1'] * p1
            val2 = pos['qty2'] * p2
            
            if abs(z) <= Z_EXIT or abs(z) >= Z_STOP:
                action = 'EXIT (Take Profit)' if abs(z) <= Z_EXIT else 'EXIT (Stop Loss)'
                print(f"  -> {action} Triggered for {pair_name}")
                
                exit_val1 = val1 * (1 - SLIPPAGE if pos['qty1'] > 0 else 1 + SLIPPAGE)
                exit_val2 = val2 * (1 - SLIPPAGE if pos['qty2'] > 0 else 1 + SLIPPAGE)
                total_exit_val = exit_val1 + exit_val2
                
                entry_val = (pos['qty1'] * pos['entry_price1']) + (pos['qty2'] * pos['entry_price2'])
                pnl = total_exit_val - entry_val
                
                state['cash'] += total_exit_val
                log_trade(pair_name, action, s1, s2, pos['qty1'], pos['qty2'], p1, p2, pnl)
                del state['positions'][pair_name]
        else:
            if abs(z) >= Z_ENTRY and abs(z) < Z_STOP:
                new_entries.append(pair_name)

    # --- PASS 2: PROCESS ENTRIES & DYNAMIC CONVICTION ALLOCATION ---
    if new_entries:
        active_pairs = list(state['positions'].keys()) + new_entries
        total_z = sum(abs(z_scores_log[p]) for p in active_pairs)
        
        # If an existing pair is already open at 100%, trim it proportionally to free capital for the 2nd pair
        for open_pair in list(state['positions'].keys()):
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
                
                state['cash'] += total_exit_val
                pos['qty1'] *= keep_ratio
                pos['qty2'] *= keep_ratio
                pos['weight'] = target_weight
                log_trade(open_pair, 'REBALANCE (Trim)', s1, s2, closed_qty1, closed_qty2, p1, p2, pnl)

        # Calculate current total equity available to size new entries
        current_equity = state['cash']
        for open_pair, pos in state['positions'].items():
            _, _, op1, op2 = prices_log[open_pair]
            current_equity += (pos['qty1'] * op1) + (pos['qty2'] * op2)

        # Open new pair entries with conviction-weighted capital (100% if single pair, Z-weighted if two pairs)
        for pair_name in new_entries:
            s1, s2, p1, p2 = prices_log[pair_name]
            z = z_scores_log[pair_name]
            target_weight = abs(z) / total_z
            allocation = current_equity * target_weight
            
            print(f"  -> ENTRY Triggered for {pair_name} (Allocation: {target_weight*100:.1f}% | ${allocation:,.2f})")
            
            if z > 0:
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
                'weight': target_weight
            }
            log_trade(pair_name, 'ENTRY', s1, s2, qty1, qty2, entry_p1, entry_p2, 0.0)

    print("==================================================\n")

    # Calculate final end-of-day mark-to-market portfolio value
    portfolio_value = state['cash']
    for open_pair, pos in state['positions'].items():
        if open_pair in prices_log:
            _, _, p1, p2 = prices_log[open_pair]
            portfolio_value += (pos['qty1'] * p1) + (pos['qty2'] * p2)

    save_state(state)
    
    # Extract current share quantities for logging (0.0 if not holding)
    hd_shares = state['positions'].get('HD_LOW', {}).get('qty1', 0.0)
    low_shares = state['positions'].get('HD_LOW', {}).get('qty2', 0.0)
    wmt_shares = state['positions'].get('WMT_TGT', {}).get('qty1', 0.0)
    tgt_shares = state['positions'].get('WMT_TGT', {}).get('qty2', 0.0)
    spy_shares = 0.0

    # --- LOG DAILY PERFORMANCE ---
    log_entry = {
        'date': datetime.now().strftime('%Y-%m-%d'),
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
    
    print(f"Daily execution complete. Total Portfolio Value: ${portfolio_value:,.2f}")

if __name__ == "__main__":
    main()
