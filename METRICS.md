# Quantitative Portfolio Performance & Trade Log
*Last Updated: `2026-10-21`*

## 1. Overall Portfolio & Strategy Statistics
| Metric | Value | Notes |
| :--- | :--- | :--- |
| **Starting Capital** | `$10,000.00` | Baseline paper-trading allocation |
| **Current Total Equity** | `$9,824.92` | Mark-to-market portfolio value |
| **Cumulative Return** | `-1.75%` | Net return including open positions & slippage |
| **Max Drawdown** | `-1.79%` | Largest peak-to-trough equity decline |
| **Annualized Sharpe Ratio** | `-4.05` | Risk-adjusted return (4.0% risk-free benchmark) |
| **Daily Snapshots Logged** | `40` | Trading days tracked in `daily_performance.csv` |
| **Total Closed Trades** | `1` | Completed round-trip pair trades |
| **Win Rate** | `0.00%` | Percentage of closed trades with net profit > $0 |
| **Profit Factor** | `0.00` | Gross realized profits divided by gross losses |
| **Total Realized PnL** | `$-91.38` | Cumulative profit/loss from closed trades |
| **Average PnL per Trade** | `$-91.38` | Mean realized profit/loss per closed trade |
| **Average Hold Duration** | `7.0 days` | Mean calendar days from entry to exit |
| **Latest Z-Scores (HD/LOW \| WMT/TGT)** | `+1.9773` \| `+1.8072` | Entry: `±1.75` \| Exit: `±0.50` \| Stop: `±4.00` |
| **Latest VIX (Regime Filter)** | `16.67` | Circuit breaker halts trading above `30.00` |

---

## 2. Individual Closed Trades Log (By Close Date)
| Trade # | Pair | Direction | Entry Date | Closed Date | Days Held | Exit Signal | Entry Prices (S1 / S2) | Exit Prices (S1 / S2) | Realized PnL ($) | Return (%) | Outcome |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | **WMT / TGT** | Short WMT / Long TGT | `2026-10-14` | `2026-10-21` | 7 | REBALANCE (Trim | $116.10 /$155.39 | $117.80 /$152.38 | **$-91.38** | `-1.75%` | **LOSS** |

---

## 3. Currently Open Positions
| Pair | Direction | Entry Date | Shares (S1 / S2) | Entry Prices (S1 / S2) | Current Status |
| :---: | :--- | :---: | :---: | :---: | :---: |
| **WMT / TGT** | Short WMT / Long TGT | `2026-10-14` | `-20.5648` / `15.3656` | $116.10 /$155.39 | **OPEN (Active)** |
| **HD / LOW** | Short HD / Long LOW | `2026-10-21` | `-8.1766` / `13.0547` | $313.98 /$196.66 | **OPEN (Active)** |
