from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Any, Optional
import uuid

import numpy as np
import pandas as pd

from .metrics import performance_metrics

WeightStrategy = Callable[[pd.DataFrame, dict[str, Any]], pd.DataFrame]


@dataclass
class BacktestResult:
    run_id: str
    strategy_name: str
    daily: pd.DataFrame
    target_weights: pd.DataFrame
    effective_weights: pd.DataFrame
    metrics: dict[str, float]
    metadata: dict[str, Any] = field(default_factory=dict)


class StrategyRegistry:
    """Registry for arbitrary strategies that return target weights by date and asset."""

    def __init__(self) -> None:
        self._strategies: dict[str, WeightStrategy] = {}

    def register(self, name: str, strategy: WeightStrategy) -> None:
        if not name:
            raise ValueError("Strategy name cannot be empty")
        self._strategies[name] = strategy

    def decorator(self, name: str):
        def _wrap(fn: WeightStrategy):
            self.register(name, fn)
            return fn
        return _wrap

    def get(self, name: str) -> WeightStrategy:
        if name not in self._strategies:
            raise KeyError(f"Unknown strategy '{name}'. Available: {sorted(self._strategies)}")
        return self._strategies[name]

    def names(self) -> list[str]:
        return sorted(self._strategies)


REGISTRY = StrategyRegistry()


def _normalize_index(prices: pd.DataFrame) -> pd.DataFrame:
    p = prices.copy()
    p.index = pd.to_datetime(p.index)
    p = p.sort_index()
    p = p[~p.index.duplicated(keep="last")]
    return p.astype(float)


def _rebalance_dates(index: pd.DatetimeIndex, frequency: str) -> pd.Series:
    frequency = frequency.lower().replace("-", "_")
    s = pd.Series(False, index=index)
    if len(index) == 0:
        return s
    if frequency in {"daily", "d"}:
        s[:] = True
        return s
    if frequency in {"never", "none", "buy_and_hold", "buyhold"}:
        s.iloc[0] = True
        return s
    rule = {
        "weekly": "W-FRI",
        "w": "W-FRI",
        "monthly": "ME",
        "m": "ME",
        "quarterly": "QE",
        "q": "QE",
        "yearly": "YE",
        "annual": "YE",
        "y": "YE",
    }.get(frequency)
    if rule is None:
        raise ValueError(f"Unsupported rebalance frequency: {frequency}")
    marker = pd.Series(np.arange(len(index)), index=index)
    selected = marker.groupby(pd.Grouper(freq=rule)).tail(1).index
    s.loc[selected] = True
    s.iloc[0] = True
    return s


def _enforce_constraints(
    weights: pd.DataFrame,
    long_only: bool,
    gross_leverage_limit: float,
) -> pd.DataFrame:
    w = weights.copy().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    if long_only:
        w = w.clip(lower=0.0)
    gross = w.abs().sum(axis=1)
    scale = pd.Series(1.0, index=w.index)
    bad = gross > gross_leverage_limit
    scale.loc[bad] = gross_leverage_limit / gross.loc[bad]
    return w.mul(scale, axis=0)


def run_backtest(
    prices: pd.DataFrame,
    strategy: str | WeightStrategy,
    params: Optional[dict[str, Any]] = None,
    *,
    rebalance: str = "monthly",
    initial_capital: float = 100_000.0,
    fee_bps: float = 0.0,
    slippage_bps: float = 0.0,
    risk_free_rate: float = 0.0,
    benchmark_prices: Optional[pd.Series] = None,
    long_only: bool = True,
    gross_leverage_limit: float = 1.0,
    metadata: Optional[dict[str, Any]] = None,
) -> BacktestResult:
    """
    Backtest any strategy that produces target weights.

    A strategy is evaluated on the price history and returns desired asset weights. Only
    scheduled rebalance rows become portfolio decisions. A decision made with date ``t``
    information executes on the next observed trading date, preventing same-bar look-ahead.

    Between rebalances, holdings are *not* reset to the target. Asset weights drift with
    realized returns, so ``rebalance="buy_and_hold"`` is a true buy-and-hold simulation
    and monthly/quarterly strategies only trade on their scheduled dates. Residual net
    capital is treated as zero-return cash. Point-in-time correctness of fundamental/model
    inputs remains the caller's responsibility.
    """
    p = _normalize_index(prices).dropna(how="all")
    if p.shape[1] == 0 or len(p) < 3:
        raise ValueError("Need at least one asset and three price observations")
    if initial_capital <= 0:
        raise ValueError("initial_capital must be positive")
    if gross_leverage_limit <= 0:
        raise ValueError("gross_leverage_limit must be positive")
    params = dict(params or {})

    if isinstance(strategy, str):
        strategy_name = strategy
        fn = REGISTRY.get(strategy)
    else:
        strategy_name = getattr(strategy, "__name__", "custom_strategy")
        fn = strategy

    raw = fn(p.copy(), params)
    if not isinstance(raw, pd.DataFrame):
        raise TypeError("A strategy must return a pandas DataFrame of target weights")
    raw = raw.reindex(index=p.index, columns=p.columns)
    constrained = _enforce_constraints(raw, long_only, gross_leverage_limit)

    rebalance_mask = _rebalance_dates(p.index, rebalance)
    decision_targets = constrained.where(rebalance_mask, np.nan)
    target = decision_targets.ffill().fillna(0.0)
    execution_targets = decision_targets.shift(1)

    asset_returns = p.pct_change(fill_method=None).fillna(0.0)
    one_way_cost_rate = (fee_bps + slippage_bps) / 10_000.0

    effective = pd.DataFrame(0.0, index=p.index, columns=p.columns)
    gross_return = pd.Series(0.0, index=p.index, dtype=float)
    trading_cost = pd.Series(0.0, index=p.index, dtype=float)
    net_return = pd.Series(0.0, index=p.index, dtype=float)
    turnover = pd.Series(0.0, index=p.index, dtype=float)
    wealth = pd.Series(index=p.index, dtype=float)
    trading_cost_dollars = pd.Series(0.0, index=p.index, dtype=float)

    end_weights = pd.Series(0.0, index=p.columns, dtype=float)
    portfolio_value = float(initial_capital)

    for dt in p.index:
        start_weights = end_weights.copy()
        execute = execution_targets.loc[dt]
        if execute.notna().any():
            desired = execute.fillna(0.0).astype(float)
            turnover.loc[dt] = float((desired - start_weights).abs().sum())
            start_weights = desired

        effective.loc[dt] = start_weights
        cost_rate = float(turnover.loc[dt] * one_way_cost_rate)
        trading_cost.loc[dt] = cost_rate
        trading_cost_dollars.loc[dt] = portfolio_value * cost_rate

        r = asset_returns.loc[dt].fillna(0.0).astype(float)
        gross = float((start_weights * r).sum())
        net = gross - cost_rate
        growth = 1.0 + net
        if not np.isfinite(growth) or growth <= 0:
            raise ValueError(f"Portfolio value became non-positive on {dt.date()}")

        gross_return.loc[dt] = gross
        net_return.loc[dt] = net
        portfolio_value *= growth
        wealth.loc[dt] = portfolio_value

        end_weights = start_weights.mul(1.0 + r).div(growth)
        end_weights = end_weights.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    drawdown = wealth / wealth.cummax() - 1.0

    benchmark_returns = None
    benchmark_wealth = None
    if benchmark_prices is not None:
        bp = pd.Series(benchmark_prices).copy()
        bp.index = pd.to_datetime(bp.index)
        bp = bp.sort_index().reindex(p.index).ffill()
        benchmark_returns = bp.pct_change(fill_method=None).fillna(0.0)
        benchmark_wealth = initial_capital * (1.0 + benchmark_returns).cumprod()

    metrics = performance_metrics(
        net_return,
        wealth=wealth,
        benchmark_returns=benchmark_returns,
        risk_free_rate=risk_free_rate,
    )
    metrics.update(
        {
            "initial_capital": float(initial_capital),
            "ending_value": float(wealth.iloc[-1]),
            "average_daily_turnover": float(turnover.mean()),
            "total_trading_cost": float(trading_cost_dollars.sum()),
        }
    )

    daily = pd.DataFrame(
        {
            "gross_return": gross_return,
            "trading_cost_return": trading_cost,
            "net_return": net_return,
            "wealth": wealth,
            "drawdown": drawdown,
            "turnover": turnover,
        }
    )
    if benchmark_returns is not None:
        daily["benchmark_return"] = benchmark_returns
        daily["benchmark_wealth"] = benchmark_wealth

    return BacktestResult(
        run_id=str(uuid.uuid4()),
        strategy_name=strategy_name,
        daily=daily,
        target_weights=target,
        effective_weights=effective,
        metrics=metrics,
        metadata={
            "params": params,
            "rebalance": rebalance,
            "implementation_lag_observations": 1,
            "weight_drift_between_rebalances": True,
            "cash_return_assumption": 0.0,
            **(metadata or {}),
        },
    )


def scores_to_weights(
    scores: pd.DataFrame,
    *,
    top_n: Optional[int] = None,
    bottom_n: int = 0,
    long_short: bool = False,
    equal_weight: bool = True,
) -> pd.DataFrame:
    """Convert factor/ML scores into cross-sectional portfolio weights."""
    scores = scores.astype(float)
    out = pd.DataFrame(0.0, index=scores.index, columns=scores.columns)
    for dt, row in scores.iterrows():
        valid = row.dropna().sort_values(ascending=False)
        if valid.empty:
            continue
        longs = valid.head(top_n or len(valid)).index
        if equal_weight:
            out.loc[dt, longs] = 1.0 / len(longs)
        else:
            vals = valid.loc[longs].clip(lower=0)
            denom = vals.sum()
            if denom > 0:
                out.loc[dt, longs] = vals / denom
        if long_short and bottom_n > 0:
            remaining = valid.drop(index=longs, errors="ignore")
            shorts = remaining.tail(min(bottom_n, len(remaining))).index
            if len(shorts):
                out.loc[dt, longs] *= 0.5
                out.loc[dt, shorts] = -0.5 / len(shorts)
    return out


def _constant_allocation_targets(prices: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    supplied = params.get("weights")
    if supplied:
        base = pd.Series({c: float(supplied.get(c, 0.0)) for c in prices.columns})
        if base.abs().sum() == 0:
            raise ValueError("Supplied weights sum to zero")
        base = base / base.abs().sum()
    else:
        base = pd.Series(1.0 / prices.shape[1], index=prices.columns)
    return pd.DataFrame(np.tile(base.values, (len(prices), 1)), index=prices.index, columns=prices.columns)


@REGISTRY.decorator("fixed_allocation")
def fixed_allocation(prices: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    """Constant target allocation; rebalance frequency controls how often drift is reset."""
    return _constant_allocation_targets(prices, params)


@REGISTRY.decorator("buy_and_hold")
def buy_and_hold(prices: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    """Constant initial allocation. Use ``rebalance='buy_and_hold'`` for no rebalancing."""
    return _constant_allocation_targets(prices, params)


@REGISTRY.decorator("moving_average_trend")
def moving_average_trend(prices: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    fast = int(params.get("fast", 50))
    slow = int(params.get("slow", 200))
    if fast >= slow:
        raise ValueError("fast must be less than slow")
    signal = (prices.rolling(fast).mean() > prices.rolling(slow).mean()).astype(float)
    denom = signal.sum(axis=1).replace(0.0, np.nan)
    return signal.div(denom, axis=0).fillna(0.0)


@REGISTRY.decorator("time_series_momentum")
def time_series_momentum(prices: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    lookback = int(params.get("lookback", 252))
    score = prices.pct_change(lookback, fill_method=None)
    signal = (score > 0).astype(float)
    denom = signal.sum(axis=1).replace(0.0, np.nan)
    return signal.div(denom, axis=0).fillna(0.0)


@REGISTRY.decorator("cross_sectional_momentum")
def cross_sectional_momentum(prices: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    lookback = int(params.get("lookback", 252))
    top_n = int(params.get("top_n", min(5, prices.shape[1])))
    score = prices.pct_change(lookback, fill_method=None)
    return scores_to_weights(score, top_n=top_n)


@REGISTRY.decorator("mean_reversion")
def mean_reversion(prices: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    lookback = int(params.get("lookback", 20))
    top_n = int(params.get("top_n", min(5, prices.shape[1])))
    score = -prices.pct_change(lookback, fill_method=None)
    return scores_to_weights(score, top_n=top_n)


@REGISTRY.decorator("inverse_volatility")
def inverse_volatility(prices: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    lookback = int(params.get("lookback", 63))
    returns = prices.pct_change(fill_method=None)
    vol = returns.rolling(lookback).std()
    inv = 1.0 / vol.replace(0.0, np.nan)
    return inv.div(inv.sum(axis=1), axis=0).fillna(0.0)


@REGISTRY.decorator("dual_momentum")
def dual_momentum(prices: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    lookback = int(params.get("lookback", 252))
    top_n = int(params.get("top_n", 1))
    score = prices.pct_change(lookback, fill_method=None)
    score = score.where(score > 0)
    return scores_to_weights(score, top_n=top_n)


def factor_or_model_strategy(
    prices: pd.DataFrame,
    score_frame: pd.DataFrame,
    *,
    top_n: int = 20,
    long_short: bool = False,
    bottom_n: int = 0,
) -> pd.DataFrame:
    """
    Adapter for point-in-time factor scores or ML model predictions.
    score_frame must be indexed by date and columns must match price symbols.
    """
    scores = score_frame.reindex(index=prices.index, columns=prices.columns)
    return scores_to_weights(scores, top_n=top_n, long_short=long_short, bottom_n=bottom_n)
