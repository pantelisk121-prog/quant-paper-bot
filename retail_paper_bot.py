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
INITIAL_CAPITAL = 100000.0

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
    # Fetch 90 days to guarantee at least 60 valid trading days
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
    latest_prices = data.iloc[-1]
    
    return z_score, latest_prices

def main():
    print("Fetching VIX data...")
    vix_df = yf.download('^VIX', period="5d", progress=False)
    vix_raw =The error message `TypeError: unsupported format string passed to Series.__format__` reveals exactly what caused the crash. 

When your code asked `yfinance` to download the VIX data, recent changes in the `yfinance` library occasionally cause it to return the data as a Pandas `Series` (or a DataFrame) instead of a simple number. When Python reached `print(f"Current VIX: {vix:.2f}")`, it didn't know how to apply the `:.2f` (two decimal places) formatting rule to an entire Pandas object, so it crashed.

To make the script bulletproof, we need to explicitly force the `vix` value—and all your stock prices and Z-scores—to convert into a standard Python `float` before trying to print or log them.

### Updated `retail_paper_bot.py`

Go to **Code** $\rightarrow$ `retail_paper_bot.py` $\rightarrow$ **Edit (pencil icon)**, delete everything inside, and replace it with this fully updated version. I added `float()` and `np.ravel()` logic throughout to ensure this formatting error never happens again, no matter what shape the data comes back in.

```python
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
INITIAL_CAPITAL = 100000.0

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
    # Fetch 90 days to guarantee at least 60 valid trading days
    data = yf.download([stock1, stock2], period="90d", progress=False)['Close']
    data = data.dropna()
    if len(data) < LOOKBACK:
        return None, None
    
    data = data.tail(LOOKBACK)
    y = data[stock1]
    X = sm.add_constant(data[stock2])
    
    model = sm.OLS(y, X).fit()
    spread = y - model.predict(X)
    
    # np.ravel flattens any Pandas object, [0] gets the first element, float() standardizes it
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
    
    # Safely extract standard float to prevent Series.__format__ TypeError
    vix = float(np.ravel(vix_data.dropna())[-1])
    
    print(f"Current VIX: {vix:.2f}")
    if vix > VIX_MAX:
        print("VIX circuit breaker triggered (>30). Halting trading operations.")
        return

    state = load_state()
    portfolio_value = state['cash']
    z_scores_log = {}
    
    print("\n==================================================")
    print("             DAILY PAIR Z-SCORE MONITOR           ")
    print("==================================================")
    
    for s1, s2 in PAIRS:
        pair_name = f"{s1}_{s2}"
        z, latest_prices = calculate_z_score(s1, s2)
        if z is None:
            continue
            
        z_scores_log[pair_name] = z
        p1 = latest_prices[s1]
        p2 = latest_prices[s2]
        
        print(f"  {s1} / {s2} Z-Score: {z:+.2f}  |  Target: ±{Z_ENTRY}  (Dist: {abs(Z_ENTRY - abs(z)):.2f})")
        
        # --- EXIT LOGIC ---
        if pair_name in state['positions']:
            pos = state['positions'][pair_name]
            val1 = pos['qty1'] * p1
            val2 = pos['qty2'] * p2
            pos_value = val1 + val2
            portfolio_value += pos_value
            
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
                
        # --- ENTRY LOGIC ---
        else:
            if abs(z) >= Z_ENTRY and abs(z) < Z_STOP:
                print(f"  -> ENTRY Triggered for {pair_name}")
                allocation = INITIAL_CAPITAL * 0.40  # 40% per pair
                
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
                    'entry_price2': entry_p2
                }
                portfolio_value += (qty1 * p1 + qty2 * p2)
                log_trade(pair_name, 'ENTRY', s1, s2, qty1, qty2, entry_p1, entry_p2, 0.0)
    
    print("==================================================\n")

    save_state(state)
    
    # --- LOG DAILY PERFORMANCE ---
    log_entry = {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'total_equity': round(float(portfolio_value), 2),
        'cash': round(float(state['cash']), 2),
        'z_hd_low': round(float(z_scores_log.get('HD_LOW', 0.0)), 4),
        'z_wmt_tgt': round(float(z_scores_log.get('WMT_TGT', 0.0)), 4)
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
