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
            pnl = trades_df['pnl']
            wins = pnl[pnl > 0]
            losses = pnl[pnl < 0]

            win_rate = (len(wins) / len(pnl)) * 100
            gross_win = wins.sum()
            gross_loss = abs(losses.sum())
            profit_factor = gross_win / gross_loss if gross_loss > 0 else np.nan

            print(f"Total Trades Completed: {len(pnl)}")
            print(f"Win Rate:               {win_rate:.2f}%")
            print(f"Profit Factor:          {profit_factor:.2f if not np.isnan(profit_factor) else 'N/A (No losses standard)'}")
        else:
            print("Trade Log Status:       File exists, but no closed trades recorded yet.")
    else:
        print("Trade Log Status:       No trades recorded yet (paper_trades.csv pending first entry).")

    print("\n----------------------------------------")

    # 2. Evaluate Daily Equity Curve
    if os.path.exists('daily_performance.csv'):
        perf_df = pd.read_csv('daily_performance.csv')
        if len(perf_df) > 1:
            equity = perf_df['total_equity']
            daily_returns = equity.pct_change().dropna()

            # Peak-to-trough drawdown
            peak = equity.cummax()
            drawdown = (equity - peak) / peak
            max_dd = drawdown.min() * 100

            # Annualized Sharpe Ratio (252 trading days, 4% risk-free rate)
            daily_rf = (1 + 0.04)**(1/252) - 1
            excess_returns = daily_returns - daily_rf
            sharpe = (excess_returns.mean() / excess_returns.std()) * np.sqrt(252) if excess_returns.std() > 0 else 0.0

            print(f"Daily Snapshots Logged: {len(perf_df)}")
            print(f"Max Drawdown:           {max_dd:.2f}%")
            print(f"Annualized Sharpe:      {sharpe:.2f}")
        else:
            print("Daily Performance:      Only 1 snapshot recorded. Need >= 2 days to compute returns.")
    else:
        print("Daily Performance:      daily_performance.csv not found.")

    print("========================================")

if __name__ == "__main__":
    calculate_metrics()
