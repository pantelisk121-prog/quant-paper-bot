# Quantitative Portfolio Performance & Trade Log
*Last Updated: `2026-11-23`*

## 1. Overall Portfolio & Strategy Statistics
| Metric | Value | Notes |
| :--- | :--- | :--- |
| **Starting Capital** | `$10,000.00` | Baseline paper-trading allocation |
| **Current Total Equity** | `$10,311.24` | Mark-to-market portfolio value |
| **Cumulative Return** | `+3.11%` | Net return including open positions & slippage |
| **Max Drawdown** | `-4.16%` | Largest peak-to-trough equity decline |
| **Annualized Sharpe Ratio** | `0.71` | Risk-adjusted return (4.0% risk-free benchmark) |
| **Daily Snapshots Logged** | `63` | Trading days tracked in `daily_performance.csv` |
| **Total Closed Trades** | `3` | Completed round-trip pair trades |
| **Win Rate** | `33.33%` | Percentage of closed trades with net profit > $0 |
| **Profit Factor** | `0.24` | Gross realized profits divided by gross losses |
| **Total Realized PnL** | `$-147.52` | Cumulative profit/loss from closed trades |
| **Average PnL per Trade** | `$-49.17` | Mean realized profit/loss per closed trade |
| **Average Hold Duration** | `23.3 days` | Mean calendar days from entry to exit |
| **Latest Z-Scores (HD/LOW \| WMT/TGT)** | `-0.6508` \| `+1.1204` | Entry: `±1.75` \| Exit: `±0.50` \| Stop: `±4.00` |
| **Latest VIX (Regime Filter)** | `26.62` | Circuit breaker halts trading above `30.00` |

---

## 2. Individual Closed Trades Log (By Close Date)
| Trade # | Pair | Direction | Entry Date | Closed Date | Days Held | Exit Signal | Entry Prices (S1 / S2) | Exit Prices (S1 / S2) | Realized PnL ($) | Return (%) | Outcome |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | **WMT / TGT** | Short WMT / Long TGT | `2026-10-14` | `2026-11-10` | 27 | REBALANCE (Trim | $116.10 /$155.39 | $125.55 /$161.78 | **$-108.03** | `-2.07%` | **LOSS** |
| 2 | **HD / LOW** | Long HD / Short LOW | `2026-11-10` | `2026-11-16` | 6 | Take Profit | $351.18 /$231.75 | $347.51 /$224.93 | **$+46.19** | `+0.90%` | **WIN** |
| 3 | **WMT / TGT** | Short WMT / Long TGT | `2026-10-14` | `2026-11-20` | 37 | VIX Circuit Breaker | $116.10 /$155.39 | $127.95 /$165.83 | **$-85.68** | `-1.80%` | **LOSS** |

---

## 3. Currently Open Positions
| Pair | Direction | Entry Date | Shares (S1 / S2) | Entry Prices (S1 / S2) | Current Status |
| :---: | :--- | :---: | :---: | :---: | :---: |
| — | *No open positions* | — | — | — | `FLAT (100% Cash)` |
