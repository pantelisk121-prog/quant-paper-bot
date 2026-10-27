# Quantitative Portfolio Performance & Trade Log
*Last Updated: `2026-10-27`*

## 1. Overall Portfolio & Strategy Statistics
| Metric | Value | Notes |
| :--- | :--- | :--- |
| **Starting Capital** | `$10,000.00` | Baseline paper-trading allocation |
| **Current Total Equity** | `$9,624.02` | Mark-to-market portfolio value |
| **Cumulative Return** | `-3.76%` | Net return including open positions & slippage |
| **Max Drawdown** | `-3.76%` | Largest peak-to-trough equity decline |
| **Annualized Sharpe Ratio** | `-4.70` | Risk-adjusted return (4.0% risk-free benchmark) |
| **Daily Snapshots Logged** | `44` | Trading days tracked in `daily_performance.csv` |
| **Total Closed Trades** | `0` | Completed round-trip pair trades |
| **Win Rate** | `N/A (0 closed)` | Percentage of closed trades with net profit > $0 |
| **Profit Factor** | `N/A (0 closed)` | Gross realized profits divided by gross losses |
| **Total Realized PnL** | `$0.00` | Cumulative profit/loss from closed trades |
| **Average PnL per Trade** | `N/A` | Mean realized profit/loss per closed trade |
| **Average Hold Duration** | `N/A` | Mean calendar days from entry to exit |
| **Latest Z-Scores (HD/LOW \| WMT/TGT)** | `+1.6878` \| `+1.0581` | Entry: `±1.75` \| Exit: `±0.50` \| Stop: `±4.00` |
| **Latest VIX (Regime Filter)** | `17.52` | Circuit breaker halts trading above `30.00` |

---

## 2. Individual Closed Trades Log (By Close Date)
| Trade # | Pair | Direction | Entry Date | Closed Date | Days Held | Exit Signal | Entry Prices (S1 / S2) | Exit Prices (S1 / S2) | Realized PnL ($) | Return (%) | Outcome |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| — | *No closed trades yet* | — | — | — | — | *Waiting for active trade to hit ±0.50 Z-exit* | — | — | `$0.00` | `0.00%` | `PENDING` |

---

## 3. Currently Open Positions
| Pair | Direction | Entry Date | Shares (S1 / S2) | Entry Prices (S1 / S2) | Current Status |
| :---: | :--- | :---: | :---: | :---: | :---: |
| **WMT / TGT** | Short WMT / Long TGT | `2026-10-14` | `-43.0656` / `32.1776` | $116.10 /$155.39 | **OPEN (Active)** |
