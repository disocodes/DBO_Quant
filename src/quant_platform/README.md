# quant_platform

A small, owned weight-based research engine. Strategies return **target portfolio weights** indexed by date. The engine applies rebalance rules, a one-observation implementation lag, leverage/long-only constraints, transaction costs, and produces a common backtest result schema.

Built-in examples are intentionally varied (buy-and-hold, trend, time-series momentum, cross-sectional momentum, mean reversion, inverse-volatility, dual momentum). They are examples, not the limits of the engine. Factor scores and ML predictions can be turned into weights with `factor_or_model_strategy` or a custom callback.
