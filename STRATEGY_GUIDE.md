# Arbitrary Strategy Guide

The platform does **not** model a strategy as a specific indicator. The common contract is:

```python
def strategy(prices: pandas.DataFrame, params: dict) -> pandas.DataFrame:
    """Return target weights indexed by date, with the same asset columns as prices."""
    return target_weights
```

`run_backtest()` then applies the same execution and analytics rules to every strategy: rebalance frequency, one-observation implementation lag, long-only/long-short constraints, gross leverage, fees, slippage, holdings, turnover, benchmark comparison, performance metrics, and common persistence. **Actual asset weights drift with realized returns between rebalance dates**; they are not silently reset each day.

## Built-in strategy families

The supplied registry includes:

- `fixed_allocation` — equal weights or explicit weights, reset only at the selected rebalance frequency
- `buy_and_hold` — the same allocation target used with `rebalance="buy_and_hold"`/`never` for a true no-rebalance portfolio
- `moving_average_trend` — example trend-following strategy, not the architecture
- `time_series_momentum`
- `cross_sectional_momentum`
- `mean_reversion`
- `inverse_volatility`
- `dual_momentum`

The production backtest worker also adds:

- `factor_top_n` — ranks point-in-time factor values from `factor_snapshots`
- `model_top_n` — ranks timestamped model predictions from `model_predictions`

## Example: explicit strategic allocation

```json
{
  "strategy_name": "fixed_allocation",
  "symbols": ["SPY", "IEF", "GLD"],
  "parameters": {
    "weights": {"SPY": 0.60, "IEF": 0.30, "GLD": 0.10}
  },
  "rebalance": "quarterly"
}
```

For a true buy-and-hold version of the same starting allocation, use `strategy_name="buy_and_hold"` with `rebalance="buy_and_hold"`.

## Example: cross-sectional momentum

```json
{
  "strategy_name": "cross_sectional_momentum",
  "symbols": ["SPY", "QQQ", "IWM", "EFA", "EEM", "IEF", "GLD"],
  "parameters": {"lookback": 252, "top_n": 3},
  "rebalance": "monthly"
}
```

## Example: fundamental factor strategy

Assume `factor_snapshots` contains `factor_name = 'quality_value_score'` with values that were actually available at each historical date:

```json
{
  "strategy_name": "factor_top_n",
  "symbols": ["... historical universe ..."],
  "parameters": {
    "factor_name": "quality_value_score",
    "top_n": 20,
    "bottom_n": 0,
    "long_short": false
  },
  "rebalance": "monthly"
}
```

## Example: long/short model portfolio

```json
{
  "strategy_name": "model_top_n",
  "symbols": ["... universe ..."],
  "long_only": false,
  "gross_leverage_limit": 1.5,
  "parameters": {
    "model_name": "expected_return_3m",
    "horizon": "3M",
    "top_n": 25,
    "bottom_n": 25,
    "long_short": true
  },
  "rebalance": "monthly"
}
```

## Adding a proprietary strategy

Register a weight generator in `src/quant_platform/engine.py` or import/register it before the worker calls `run_backtest`:

```python
from quant_platform import REGISTRY

@REGISTRY.decorator("quality_momentum_low_vol")
def quality_momentum_low_vol(prices, params):
    momentum = prices.pct_change(int(params.get("lookback", 126)))
    volatility = prices.pct_change().rolling(63).std()
    score = momentum / volatility.replace(0, float("nan"))
    ranks = score.rank(axis=1, ascending=False, method="first")
    selected = (ranks <= int(params.get("top_n", 5))).astype(float)
    return selected.div(selected.sum(axis=1), axis=0).fillna(0)
```

For fundamental/model inputs, prefer a worker adapter that constructs a point-in-time score frame and then calls `factor_or_model_strategy()`. Do not merge revised financial statements or later model predictions backward into earlier dates.

## Parameter sweeps and optimization

The engine contract is intentionally deterministic and composable. A Databricks Job can loop or parallelize over parameter combinations, run each through the same `run_backtest()` function, and persist each result as a normal `strategy_run`. This allows walk-forward validation and parameter sweeps without creating a second backtest system.

## Efficient-frontier portfolios

The NVIDIA optimizer is not forced through the strategy engine. Its frontier and allocation outputs are persisted in the canonical optimization tables. When you want to compare one selected optimizer portfolio against strategies, materialize its historical/forward return series into the common comparison format or create a strategy that consumes the chosen target-allocation schedule.

## Saved portfolios

The production backtest Job accepts `portfolio_id`. Its latest `portfolio_holdings` snapshot becomes the strategy universe. For `fixed_allocation` and `buy_and_hold`, those stored weights are also used automatically unless `parameters_json.weights` overrides them. This allows saved portfolios, model portfolios and externally produced allocations to enter the same common backtest/result schema.
