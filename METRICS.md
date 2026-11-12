# Quantitative Portfolio Performance & Trade Log
*Last Updated: `2026-11-11`*

## 1. Overall Portfolio & Strategy Statistics
| Metric | Value | Notes |
| :--- | :--- | :--- |
| **Starting Capital** | `$10,000.00` | Baseline paper-trading allocation |
| **Current Total Equity** | `$9,809.77` | Mark-to-market portfolio value |
| **Cumulative Return** | `-1.90%` | Net return including open positions & slippage |
| **Max Drawdown** | `-4.16%` | Largest peak-to-trough equity decline |
| **Annualized Sharpe Ratio** | `-1.36` | Risk-adjusted return (4.0% risk-free benchmark) |
| **Daily Snapshots Logged** | `55` | Trading days tracked in `daily_performance.csv` |
| **Total Closed Trades** | `1` | Completed round-trip pair trades |
| **Win Rate** | `0.00%` | Percentage of closed trades with net profit > $0 |
| **Profit Factor** | `0.00` | Gross realized profits divided by gross losses |
| **Total Realized PnL** | `$-108.03` | Cumulative profit/loss from closed trades |
| **Average PnL per Trade** | `$-108.03` | Mean realized profit/loss per closed trade |
| **Average Hold Duration** | `27.0 days` | Mean calendar days from entry to exit |
| **Latest Z-Scores (HD/LOW \| WMT/TGT)** | `-1.8169` \| `+2.0078` | Entry: `±1.75` \| Exit: `±0.50` \| Stop: `±4.00` |
| **Latest VIX (Regime Filter)** | `17.49` | Circuit breaker halts trading above `30.00` |

---

## 2. Individual Closed Trades Log (By Close Date)
| Trade # | Pair | Direction | Entry Date | Closed Date | Days Held | Exit Signal | Entry Prices (S1 / S2) | Exit Prices (S1 / S2) | Realized PnL ($) | Return (%) | Outcome |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | **WMT / TGT** | Short WMT / Long TGT | `2026-10-14` | `2026-11-10` | 27 | REBALANCE (Trim | $116.10 /$155.39 | $125.55 /$161.78 | **$-108.03** | `-2.07%` | **LOSS** |

---

## 3. Currently Open Positions
| Pair | Direction | Entry Date | Shares (S1 / S2) | Entry Prices (S1 / S2) | Current Status |
| :---: | :--- | :---: | :---: | :---: | :---: |
| **WMT / TGT** | Short WMT / Long TGT | `2026-10-14` | `-20.5372` / `15.3449` | $116.10 /$155.39 | **OPEN (Active)** |
| **HD / LOW** | Long HD / Short LOW | `2026-11-10` | `7.2962` / `-11.0558` | $351.18 /$231.75 | **OPEN (Active)** |
