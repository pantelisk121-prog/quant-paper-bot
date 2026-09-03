import pandas as pd
import numpy as np
import os

def calculate_metrics():
    print("========================================")
    print("      QUANT PORTFOLIO METRICS EVAL      ")
    print("========================================\n")

    # 1. Evaluate Trade Logs
    if os.path.exists('paper_trades.csv'):
        trades_df = pd.read_csv('paper_trades.csv')
        if not trades_df.empty and 'pnl' in trades_df.columns:
            # Filter only EXIT actions to calculate closed trade PnL
            exits = trades_df[trades_df['action'].str.contains('EXIT', na=False)]
            if not exits.empty:
                pnl = exits['pnl']
                wins = pnl[pnl > 0]
                losses = pnl[pnl < 0]

                win_rate = (len(wins) / len(pnl)) * 100
                gross_win = wins.sum()
                gross_loss = abs(losses.sum())
                profit_factor = gross_win / gross_loss if gross_loss > 0 else np.nan

                print(f"Total Trades Completed: {len(pnl)}")
                print(f"Win Rate:               {win_rate:.2f}%")
                print(f"Profit Factor:          {profit_factor:.2f if not np.isnan(profit_factor) else 'N/A (No losses)'}")
            else:
                print("Trade Log Status:       Trades opened, but no closed trades recorded yet.")
        else:
            print("Trade Log Status:       File exists, but no closed trades recorded yet.")
    else:
        print("Trade Log Status:       No trades recorded yet (paper_trades.csv pending first entry).")

    print("\n----------------------------------------")

    # 2. Evaluate Daily Equity Curve
    if os.path.exists('daily_performance.csv'):
        perf_df = pd.read_csv('daily_performance.csv')
        
        possible_cols = ['total_equity', 'portfolio_value', 'equity', 'total_value', 'Portfolio_Value']
        equity_col = next((col for col in possible_cols if col in perf_df.columns), None)
        
        if equity_col and len(perf_df) > 1:
            equity = perf_df[equity_col]
            daily_returns = equity.pct_change().dropna()

            peak = equity.cummax()
            drawdown = (equity - peak) / peak
            max_dd = drawdown.min() * 100

            daily_rf = (1 + 0.04)**(1/252) - 1
            excess_returns = daily_returns - daily_rf
            sharpe = (excess_returns.mean() / excess_returns.std()) * np.sqrt(252) if excess_returns.std() > 0 else 0.0

            print(f"Daily Snapshots Logged: {len(perf_df)}")
            print(f"Max Drawdown:           {max_dd:.2f}%")
            print(f"Annualized Sharpe:      {sharpe:.2f}")
        elif equity_col and len(perf_df) <= 1:
            print("Daily Performance:      1 snapshot recorded. Need >= 2 days to compute returns.")
        else:
            print(f"Daily Performance:      Logged columns found: {list(perf_df.columns)}")

        # --- Z-SCORE TRACKING LOGIC ---
        if 'z_hd_low' in perf_df.columns and 'z_wmt_tgt' in perf_df.columns:
            latest_hd_low = perf_df['z_hd_low'].iloc[-1]
            latest_wmt_tgt = perf_df['z_wmt_tgt'].iloc[-1]

            print("\n--- Latest Rolling Z-Scores ---")
            print(f"  HD / LOW  Z-Score: {latest_hd_low:+.2f}")
            print(f"  WMT / TGT Z-Score: {latest_wmt_tgt:+.2f}")

            if abs(latest_hd_low) >= 1.50 or abs(latest_wmt_tgt) >= 1.50:
                print("  ⚠️ ALERT: A pair is within 0.25 Z of the ±1.75 entry threshold!")
    else:
        print("Daily Performance:      daily_performance.csv not found.")

    print("========================================")

if __name__ == "__main__":
    calculate_metrics()
