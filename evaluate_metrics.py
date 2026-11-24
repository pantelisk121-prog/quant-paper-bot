import pandas as pd
import numpy as np
import json
import os
from datetime import datetime

TRADES_FILE = 'paper_trades.csv'
PERF_FILE = 'daily_performance.csv'
STATE_FILE = 'portfolio_state.json'
METRICS_MD_FILE = 'METRICS.md'
INITIAL_CAPITAL = 10000.0


def parse_date(date_str):
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(str(date_str).strip(), fmt)
        except ValueError:
            continue
    return None


def load_state_positions():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                return state.get('positions', {})
        except Exception:
            pass
    return {}


def is_single_leg_trade(pair, s2):
    return pair == 'SPY_HEDGE' or str(s2).strip().upper() in ('CASH', '', 'NAN', 'NONE')


def calculate_metrics():
    print("========================================")
    print("      QUANT PORTFOLIO METRICS EVAL      ")
    print("========================================\n")

    closed_trades = []
    open_trades = {}
    state_positions = load_state_positions()

    if os.path.exists(TRADES_FILE):
        trades_df = pd.read_csv(TRADES_FILE)
        if not trades_df.empty and 'action' in trades_df.columns:
            for _, row in trades_df.iterrows():
                pair = str(row.get('pair', ''))
                action = str(row.get('action', '')).strip()
                date_str = str(row.get('date', ''))
                s1 = str(row.get('stock1', ''))
                s2 = str(row.get('stock2', ''))
                qty1 = float(row.get('qty1', 0.0))
                qty2 = float(row.get('qty2', 0.0))
                p1 = float(row.get('price1', 0.0))
                p2 = float(row.get('price2', 0.0))
                pnl = float(row.get('pnl', 0.0))

                if action.startswith('ENTRY'):
                    open_trades[pair] = {
                        'pair': pair,
                        'action': action,
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
                    single_leg = is_single_leg_trade(pair, s2)

                    if entry_info:
                        entry_dt = parse_date(entry_info['entry_date'])
                        close_dt = parse_date(date_str)
                        days_held = max(0, (close_dt.date() - entry_dt.date()).days) if (entry_dt and close_dt) else 'N/A'
                        entry_date_clean = entry_dt.strftime('%Y-%m-%d') if entry_dt else entry_info['entry_date']
                        entry_p1 = entry_info['entry_p1']
                        entry_p2 = entry_info['entry_p2']
                        cap_deployed = abs(qty1 * entry_p1) if single_leg else (abs(qty1 * entry_p1) + abs(qty2 * entry_p2))
                    else:
                        days_held = 'N/A'
                        entry_date_clean = 'N/A'
                        entry_p1, entry_p2 = p1, p2
                        cap_deployed = abs(qty1 * p1) if single_leg else (abs(qty1 * p1) + abs(qty2 * p2))

                    close_dt = parse_date(date_str)
                    close_date_clean = close_dt.strftime('%Y-%m-%d') if close_dt else date_str
                    ret_pct = (pnl / cap_deployed * 100.0) if cap_deployed > 0 else 0.0

                    if single_leg:
                        direction = f"Long {s1} (VIX Safe Haven)"
                        entry_prices_str = f"${entry_p1:.2f}"
                        exit_prices_str = f"${p1:.2f}"
                    else:
                        direction = f"Short {s1} / Long {s2}" if qty1 < 0 else f"Long {s1} / Short {s2}"
                        entry_prices_str = f"${entry_p1:.2f} / ${entry_p2:.2f}"
                        exit_prices_str = f"${p1:.2f} / ${p2:.2f}"

                    outcome = "WIN" if pnl > 0 else ("LOSS" if pnl < 0 else "FLAT")

                    closed_trades.append({
                        'trade_num': len(closed_trades) + 1,
                        'pair': pair.replace('_', ' '),
                        'direction': direction,
                        'entry_date': entry_date_clean,
                        'close_date': close_date_clean,
                        'days_held': days_held,
                        'exit_type': action.replace('EXIT ', '').strip('()'),
                        'entry_prices': entry_prices_str,
                        'exit_prices': exit_prices_str,
                        'pnl': pnl,
                        'ret_pct': ret_pct,
                        'outcome': outcome
                    })

                    if 'EXIT' in action and pair in open_trades:
                        del open_trades[pair]
                    elif 'REBALANCE' in action and pair in open_trades:
                        open_trades[pair]['qty1'] -= qty1
                        open_trades[pair]['qty2'] -= qty2

    # Sync open trade market entry dates with portfolio_state.json (handles weekend backfills cleanly)
    spy_state = state_positions.get('SPY_POS')
    if isinstance(spy_state, dict) and float(spy_state.get('qty', 0.0)) > 0:
        if 'SPY_HEDGE' in open_trades:
            if spy_state.get('entry_date'):
                open_trades['SPY_HEDGE']['entry_date'] = spy_state['entry_date']
        else:
            open_trades['SPY_HEDGE'] = {
                'pair': 'SPY_HEDGE',
                'action': 'ENTRY (VIX Safe Haven)',
                'stock1': 'SPY',
                'stock2': 'CASH',
                'entry_date': spy_state.get('entry_date', 'N/A'),
                'qty1': float(spy_state.get('qty', 0.0)),
                'qty2': 0.0,
                'entry_p1': float(spy_state.get('entry_price', 0.0)),
                'entry_p2': 0.0
            }

    for pair_key, info in open_trades.items():
        if pair_key in state_positions and isinstance(state_positions[pair_key], dict):
            if state_positions[pair_key].get('entry_date'):
                info['entry_date'] = state_positions[pair_key]['entry_date']

    total_closed = len(closed_trades)
    total_realized_pnl = 0.0
    if total_closed > 0:
        pnl_series = pd.Series([t['pnl'] for t in closed_trades])
        wins = pnl_series[pnl_series > 0]
        losses = pnl_series[pnl_series < 0]

        total_realized_pnl = float(pnl_series.sum())
        win_rate_str = f"{(len(wins) / total_closed) * 100:.2f}%"
        gross_win = wins.sum()
        gross_loss = abs(losses.sum())
        pf_str = f"{gross_win / gross_loss:.2f}" if gross_loss > 0 else "N/A (No losses)"
        total_realized_pnl_str = f"${total_realized_pnl:+,.2f}"
        avg_pnl_str = f"${pnl_series.mean():+,.2f}"

        valid_days = [t['days_held'] for t in closed_trades if isinstance(t['days_held'], int)]
        avg_hold_str = f"{np.mean(valid_days):.1f} days" if valid_days else "N/A"
    else:
        win_rate_str = "N/A (0 closed)"
        pf_str = "N/A (0 closed)"
        total_realized_pnl_str = "$0.00"
        avg_pnl_str = "N/A"
        avg_hold_str = "N/A"

    snapshots_count = 0
    curr_eq = INITIAL_CAPITAL
    current_equity_str = f"${INITIAL_CAPITAL:,.2f}"
    cum_return_str = "0.00%"
    cagr_str = "0.00%"
    cagr_note = "Annualized return (252-day trading basis)"
    unrealized_pnl_str = "$0.00"
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
            curr_eq = float(equity.iloc[-1])
            current_equity_str = f"${curr_eq:,.2f}"

            cum_ret = ((curr_eq - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100.0
            cum_return_str = f"{cum_ret:+.2f}%"

            if curr_eq > 0:
                cagr = ((curr_eq / INITIAL_CAPITAL) ** (252.0 / snapshots_count) - 1.0) * 100.0
                cagr_str = f"{cagr:+.2f}%"
                cagr_note = f"Annualized over {snapshots_count} active trading days (252-day basis)"

            unrealized_pnl = (curr_eq - INITIAL_CAPITAL - total_realized_pnl) if open_trades else 0.0
            unrealized_pnl_str = f"${unrealized_pnl:+,.2f}"

            if snapshots_count > 1:
                daily_returns = equity.pct_change().dropna()
                peak = equity.cummax()
                drawdown = (equity - peak) / peak
                max_dd = drawdown.min() * 100.0
                max_dd_str = f"{max_dd:.2f}%"

                daily_rf = (1 + 0.04) ** (1 / 252) - 1
                excess_returns = daily_returns - daily_rf
                sharpe = (excess_returns.mean() / excess_returns.std()) * np.sqrt(252) if excess_returns.std() > 0 else 0.0
                sharpe_str = f"{sharpe:.2f}"

        if not perf_df.empty:
            if 'date' in perf_df.columns:
                latest_date_str = str(perf_df['date'].iloc[-1])
            if 'z_hd_low' in perf_df.columns:
                latest_hd_low_str = f"{float(perf_df['z_hd_low'].iloc[-1]):+.4f}"
            if 'z_wmt_tgt' in perf_df.columns:
                latest_wmt_tgt_str = f"{float(perf_df['z_wmt_tgt'].iloc[-1]):+.4f}"
            if 'vix' in perf_df.columns:
                latest_vix_str = f"{float(perf_df['vix'].iloc[-1]):.2f}"

    md_lines = [
        "# Quantitative Portfolio Performance & Trade Log",
        f"*Last Updated: `{latest_date_str}`*\n",
        "## 1. Overall Portfolio & Strategy Statistics",
        "| Metric | Value | Notes |",
        "| :--- | :--- | :--- |",
        f"| **Starting Capital** | `${INITIAL_CAPITAL:,.2f}` | Baseline paper-trading allocation |",
        f"| **Current Total Equity** | `{current_equity_str}` | Mark-to-market portfolio value |",
        f"| **Cumulative Return** | `{cum_return_str}` | Net return including open positions & slippage |",
        f"| **Annualized Return (CAGR)** | `{cagr_str}` | {cagr_note} |",
        f"| **Max Drawdown** | `{max_dd_str}` | Largest peak-to-trough equity decline |",
        f"| **Annualized Sharpe Ratio** | `{sharpe_str}` | Risk-adjusted return (4.0% risk-free benchmark) |",
        f"| **Daily Snapshots Logged** | `{snapshots_count}` | Trading days tracked in `daily_performance.csv` |",
        f"| **Total Closed Trades** | `{total_closed}` | Completed round-trip trades (including trims & hedges) |",
        f"| **Win Rate** | `{win_rate_str}` | Percentage of closed trades with net profit > $0 |",
        f"| **Profit Factor** | `{pf_str}` | Gross realized profits divided by gross losses |",
        f"| **Total Realized PnL** | `{total_realized_pnl_str}` | Cumulative profit/loss from closed trades |",
        f"| **Current Unrealized PnL** | `{unrealized_pnl_str}` | Mark-to-market open profit/loss across active positions |",
        f"| **Average PnL per Trade** | `{avg_pnl_str}` | Mean realized profit/loss per closed trade |",
        f"| **Average Hold Duration** | `{avg_hold_str}` | Mean calendar days from entry to exit |",
        f"| **Latest Z-Scores (HD/LOW \\| WMT/TGT)** | `{latest_hd_low_str}` \\| `{latest_wmt_tgt_str}` | Entry: `±1.75` \\| Exit: `±0.50` \\| Stop: `±4.00` |",
        f"| **Latest VIX (Regime Filter)** | `{latest_vix_str}` | Rotates to `SPY` above `30.00`; resumes pairs at `<= 25.00` |",
        "\n---\n",
        "## 2. Individual Closed Trades Log (By Close Date)",
        "| Trade # | Pair / Asset | Direction | Entry Date | Closed Date | Days Held | Exit Signal | Entry Price(s) | Exit Price(s) | Realized PnL ($) | Return (%) | Outcome |",
        "| :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
    ]

    if closed_trades:
        for t in closed_trades:
            md_lines.append(
                f"| {t['trade_num']} | **{t['pair']}** | {t['direction']} | `{t['entry_date']}` | "
                f"`{t['close_date']}` | {t['days_held']} | {t['exit_type']} | {t['entry_prices']} | "
                f"{t['exit_prices']} | **${t['pnl']:+,.2f}** | `{t['ret_pct']:+.2f}%` | **{t['outcome']}** |"
            )
    else:
        md_lines.append(
            "| — | *No closed trades yet* | — | — | — | — | *Waiting for active trade to hit ±0.50 Z-exit* | — | — | `$0.00` | `0.00%` | `PENDING` |"
        )

    md_lines.extend([
        "\n---\n",
        "## 3. Currently Open Positions",
        "| Pair / Asset | Direction | Entry Date | Days Open | Shares | Entry Price(s) | Current Status |",
        "| :---: | :--- | :---: | :---: | :---: | :---: | :---: |"
    ])

    ref_dt = parse_date(latest_date_str) or datetime.now()

    if open_trades:
        for pair, info in open_trades.items():
            s1, s2 = info['stock1'], info['stock2']
            q1, q2 = info['qty1'], info['qty2']
            ep1, ep2 = info['entry_p1'], info['entry_p2']
            single_leg = is_single_leg_trade(pair, s2)

            entry_dt = parse_date(info['entry_date'])
            e_date = entry_dt.strftime('%Y-%m-%d') if entry_dt else info['entry_date']
            days_open = max(0, (ref_dt.date() - entry_dt.date()).days) if entry_dt else 'N/A'

            if single_leg:
                label = pair.replace('_', ' ')
                direction = f"Long {s1} (VIX Safe Haven)"
                shares_str = f"`{q1:.4f}` {s1}"
                entry_price_str = f"${ep1:.2f}"
                status_str = "**OPEN (VIX Safe Haven)**"
            else:
                label = pair.replace('_', ' / ')
                direction = f"Short {s1} / Long {s2}" if q1 < 0 else f"Long {s1} / Short {s2}"
                shares_str = f"`{q1:.4f}` / `{q2:.4f}`"
                entry_price_str = f"${ep1:.2f} / ${ep2:.2f}"
                status_str = "**OPEN (Active)**"

            md_lines.append(
                f"| **{label}** | {direction} | `{e_date}` | {days_open} | {shares_str} | "
                f"{entry_price_str} | {status_str} |"
            )
    else:
        md_lines.append("| — | *No open positions* | — | — | — | — | `FLAT (100% Cash)` |")

    with open(METRICS_MD_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_lines) + '\n')

    print('\n'.join(md_lines))
    print(f"\n[SUCCESS] Markdown tables written to {METRICS_MD_FILE}")


if __name__ == "__main__":
    calculate_metrics()
