import pandas as pd
import numpy as np
import os
from datetime import datetime

TRADES_FILE = 'paper_trades.csv'
PERF_FILE = 'daily_performance.csv'
METRICS_MD_FILE = 'METRICS.md'
INITIAL_CAPITAL = 10000.0


def parse_date(date_str):
    """Safely parse date or datetime strings from trade logs."""
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(str(date_str).strip(), fmt)
        except ValueError:
            continue
    return None


def calculate_metrics():
    print("========================================")
    print("      QUANT PORTFOLIO METRICS EVAL      ")
    print("========================================\n")

    # --- 1. PROCESS INDIVIDUAL TRADES (ENTRY -> CLOSE MATCHING) ---
    closed_trades = []
    open_trades = {}

    if os.path.exists(TRADES_FILE):
        trades_df = pd.read_csv(TRADES_FILE)
        if not trades_df.empty and 'action' in trades_df.columns:
            for _, row in trades_df.iterrows():
                pair = str(row.get('pair', ''))
                action = str(row.get('action', ''))
                date_str = str(row.get('date', ''))
                s1 = str(row.get('stock1', ''))
                s2 = str(row.get('stock2', ''))
                qty1 = float(row.get('qty1', 0.0))
                qty2 = float(row.get('qty2', 0.0))
                p1 = float(row.get('price1', 0.0))
                p2 = float(row.get('price2', 0.0))
                pnl = float(row.get('pnl', 0.0))

                if action == 'ENTRY':
                    open_trades[pair] = {
                        'pair': pair,
                        'stock1': s1,
                        'stock2': s2,
                        'entry_date': date_str,
                        'qty1': qty1,
                        'qty2': qty2,
                        'entry_p1': p1,
                        'entry_p2': p2
                    }
                elif 'EXIT' in action or 'REBALANCE' in action:
                    entry_info = open_trades.get(pair)
                    if entry_info:
                        entry_dt = parse_date(entry_info['entry_date'])
                        close_dt = parse_date(date_str)
                        days_held = (close_dt.date() - entry_dt.date()).days if (entry_dt and close_dt) else 'N/A'
                        entry_date_clean = entry_dt.strftime('%Y-%m-%d') if entry_dt else entry_info['entry_date']
                        entry_p1 = entry_info['entry_p1']
                        entry_p2 = entry_info['entry_p2']
                        cap_deployed = abs(qty1 * entry_p1) + abs(qty2 * entry_p2)
                    else:
                        days_held = 'N/A'
                        entry_date_clean = 'N/A'
                        entry_p1, entry_p2 = p1, p2
                        cap_deployed = abs(qty1 * p1) + abs(qty2 * p2)

                    close_dt = parse_date(date_str)
                    close_date_clean = close_dt.strftime('%Y-%m-%d') if close_dt else date_str
                    ret_pct = (pnl / cap_deployed * 100.0) if cap_deployed > 0 else 0.0
                    direction = f"Short {s1} / Long {s2}" if qty1 < 0 else f"Long {s1} / Short {s2}"
                    outcome = "WIN" if pnl > 0 else ("LOSS" if pnl < 0 else "FLAT")

                    closed_trades.append({
                        'trade_num': len(closed_trades) + 1,
                        'pair': pair.replace('_', ' / '),
                        'direction': direction,
                        'entry_date': entry_date_clean,
                        'close_date': close_date_clean,
                        'days_held': days_held,
                        'exit_type': action.replace('EXIT ', '').strip('()'),
                        'entry_prices': f"${entry_p1:.2f} /${entry_p2:.2f}",
                        'exit_prices': f"${p1:.2f} /${p2:.2f}",
                        'pnl': pnl,
                        'ret_pct': ret_pct,
                        'outcome': outcome
                    })

                    if 'EXIT' in action and pair in open_trades:
                        del open_trades[pair]
                    elif 'REBALANCE' in action and pair in open_trades:
                        open_trades[pair]['qty1'] -= qty1
                        open_trades[pair]['qty2'] -= qty2

    # Compute Trade-Level Summary Stats
    total_closed = len(closed_trades)
    if total_closed > 0:
        pnl_series = pd.Series([t['pnl'] for t in closed_trades])
        wins = pnl_series[pnl_series > 0]
        losses = pnl_series[pnl_series < 0]

        win_rate_str = f"{(len(wins) / total_closed) * 100:.2f}%"
        gross_win = wins.sum()
        gross_loss = abs(losses.sum())
        pf_str = f"{gross_win / gross_loss:.2f}" if gross_loss > 0 else "N/A (No losses)"
        total_realized_pnl_str = f"${pnl_series.sum():+,.2f}"
        avg_pnl_str = f"${pnl_series.mean():+,.2f}"

        valid_days = [t['days_held'] for t in closed_trades if isinstance(t['days_held'], int)]
        avg_hold_str = f"{np.mean(valid_days):.1f} days" if valid_days else "N/A"
    else:
        win_rate_str = "N/A (0 closed)"
        pf_str = "N/A (0 closed)"
        total_realized_pnl_str = "$0.00"
        avg_pnl_str = "N/A"
        avg_hold_str = "N/A"

    # --- 2. PROCESS DAILY EQUITY CURVE ---
    snapshots_count = 0
    current_equity_str = f"${INITIAL_CAPITAL:,.2f}"
    cum_return_str = "0.00%"
    max_dd_str = "0.00%"
    sharpe_str = "0.00"
    latest_hd_low_str = "N/A"
    latest_wmt_tgt_str = "N/A"
    latest_vix_str = "N/A"
    latest_date_str = "N/A"

    if os.path.exists(PERF_FILE):
        perf_df = pd.read_csv(PERF_FILE)
        snapshots_count = len(perf_df)

        possible_cols = ['total_equity', 'portfolio_value', 'equity', 'total_value', 'Portfolio_Value']
        equity_col = next((col for col in possible_cols if col in perf_df.columns), None)

        if equity_col and snapshots_count >= 1:
            equity = perf_df[equity_col].astype(float)
            curr_eq = equity.iloc[-1]
