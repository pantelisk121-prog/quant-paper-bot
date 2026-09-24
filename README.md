# Retail Pairs Statistical Arbitrage: Backtest & Live Execution Environment

This repository houses a mean-reversion statistical arbitrage trading framework targeting highly correlated retail equities (HD/LOW and WMT/TGT). The project spans a 5-year iterative backtested model built in Google Colab, culminating in a live, fully automated paper-trading pipeline executing daily via cloud infrastructure.

## I. Google Colab Backtest Evolution & Diagnostic Journey
The underlying strategy was developed across seven distinct iterative stages, transitioning from a basic linear model to a dynamically sized, macro-aware framework. I intentionally documented the failures and structural breaks encountered during testing to engineer robust, programmatic solutions.

* **Stage 1: Single-Pair Baseline:** Initialized a rudimentary spread model focusing exclusively on Home Depot (HD) and Lowe's (LOW), identifying the mathematical flaw of measuring returns in raw dollars-per-share rather than normalized portfolio percentages.
* **Stage 2: Realism & Friction:** Shifted to tracking the percentage growth of a normalized portfolio, introducing realistic execution fees and bid-ask slippage to identify true profitability thresholds.
* **Stage 3: The SPY Crisis Switch:** Expanded the universe and evaluated the impact of macroeconomic shocks. Noticing that the March 2020 COVID-19 crash caused broad mean-reversion failures, I implemented a Volatility Regime Filter. During extreme macro-panics, the bot halts pairs trading and reallocates capital into the SPY index to ride the broad-market rebound.
* **Stage 4: High-Efficiency Cash Yield:** Realizing that idle cash dragging on returns is a major flaw in statistical arbitrage, I integrated a high-yield automated cash sweep model on all non-deployed capital, smoothing the equity curve during periods without trade signals.
* **Stage 5: Cross-Pair Pollution (The V/MA Failure):** Attempted to introduce Visa (V) and Mastercard (MA) into the basket. Diagnostic plotting revealed that V/MA was consistently failing and draining capital away from the profitable HD/LOW pair under an equal-weight allocation model.
* **Stage 6: Dynamic Capital Allocation (The Epiphany):** To solve the capital starvation issue, I engineered a dynamic allocation model. Position sizes now scale in proportion to the severity of the Z-score divergence. While this optimized HD/LOW, V/MA continued to fail. Research revealed a fundamental structural break: Mastercard's disproportionate reliance on high-margin international cross-border travel fees caused the pair to decouple permanently during the 2020 global lockdowns. 
* **Stage 7: Production Basket & Hard Stops:** Purged V/MA from the universe entirely, relying on HD/LOW and WMT/TGT. To protect against future structural un-pairings, I implemented a hard stop-loss: if a divergence exceeds $\vert{}Z\vert{} \ge 4.0$, the bot assumes cointegration has failed and liquidates the trade. This final architecture achieved a 21.1% annualized return over 5-years.

## II. Daily Paper-Trading Pipeline
The backtested logic is currently deployed as a live, automated pipeline adapting dynamically to daily market conditions.

* **Data Ingestion:** Utilizes `yfinance` to ingest daily closing data for all primary pairs and macro indicators.
* **State Management:** Tracks daily share counts, cash balances, and total equity, logging all metrics to `daily_performance.csv`.
* **Execution Logic:** Calculates rolling 60-day Z-scores at market close. The algorithm executes automatically based on the optimized thresholds: Entry $\vert{}Z\vert{} \ge 1.75$, Exit $\vert{}Z\vert{} \le 0.50$, Stop $\vert{}Z\vert{} \ge 4.0$, and a VIX > 30 circuit breaker.
