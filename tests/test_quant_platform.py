import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd

from quant_platform import REGISTRY, compare_backtests, run_backtest, simulate_portfolio


def synthetic_prices(n=800):
    rng = np.random.default_rng(7)
    idx = pd.bdate_range("2020-01-01", periods=n)
    rets = rng.normal([0.0004, 0.0003, 0.0001], [0.01, 0.012, 0.004], size=(n, 3))
    px = 100 * np.cumprod(1 + rets, axis=0)
    return pd.DataFrame(px, index=idx, columns=["AAA", "BBB", "CCC"])


def test_strategy_registry_has_diverse_strategies():
    expected = {"buy_and_hold", "fixed_allocation", "moving_average_trend", "time_series_momentum", "cross_sectional_momentum", "mean_reversion", "inverse_volatility", "dual_momentum"}
    assert expected.issubset(set(REGISTRY.names()))


def test_backtest_runs_and_weights_are_lagged():
    prices = synthetic_prices()
    result = run_backtest(prices, "inverse_volatility", params={"lookback": 21}, rebalance="monthly", fee_bps=5)
    assert len(result.daily) == len(prices)
    assert result.metrics["ending_value"] > 0
    assert result.effective_weights.iloc[0].abs().sum() == 0
    assert set(result.target_weights.columns) == set(prices.columns)


def test_comparison():
    prices = synthetic_prices()
    a = run_backtest(prices, "fixed_allocation", rebalance="monthly")
    b = run_backtest(prices, "cross_sectional_momentum", params={"lookback": 63, "top_n": 1}, rebalance="monthly")
    metrics, wealth, corr = compare_backtests({"buy_hold": a, "momentum": b})
    assert metrics.shape[0] == 2
    assert wealth.shape[1] == 2
    assert corr.shape == (2, 2)


def test_monte_carlo():
    prices = synthetic_prices(500)
    returns = prices.pct_change(fill_method=None).dropna()
    mc = simulate_portfolio(returns, pd.Series([0.5, 0.3, 0.2], index=returns.columns), horizon_days=100, n_simulations=250, sample_path_count=10, rebalance_every_days=21)
    assert mc.percentiles.shape == (101, 9)
    assert mc.sample_paths.shape == (101, 10)
    assert len(mc.terminal_values) == 250
    assert 0 <= mc.summary["probability_of_loss"] <= 1


def test_buy_and_hold_weights_drift_between_rebalances():
    idx = pd.bdate_range("2025-01-01", periods=6)
    prices = pd.DataFrame({
        "A": [100, 110, 121, 133.1, 146.41, 161.051],
        "B": [100, 100, 100, 100, 100, 100],
    }, index=idx)
    result = run_backtest(
        prices,
        "buy_and_hold",
        params={"weights": {"A": 0.5, "B": 0.5}},
        rebalance="buy_and_hold",
    )
    assert result.effective_weights.iloc[0].abs().sum() == 0
    assert np.isclose(result.effective_weights.iloc[1]["A"], 0.5)
    assert result.effective_weights.iloc[3]["A"] > result.effective_weights.iloc[2]["A"] > 0.5
    assert (result.daily["turnover"] > 0).sum() == 1


def test_periodic_rebalance_trades_less_often_than_daily():
    prices = synthetic_prices(260)
    monthly = run_backtest(prices, "fixed_allocation", rebalance="monthly")
    daily = run_backtest(prices, "fixed_allocation", rebalance="daily")
    assert (monthly.daily["turnover"] > 1e-12).sum() < (daily.daily["turnover"] > 1e-12).sum()


def test_monte_carlo_rebalance_policy_changes_paths():
    prices = synthetic_prices(400)
    returns = prices.pct_change(fill_method=None).dropna()
    weights = pd.Series([0.7, 0.2, 0.1], index=returns.columns)
    daily = simulate_portfolio(returns, weights, horizon_days=80, n_simulations=120, seed=11, rebalance_every_days=1)
    buy_hold = simulate_portfolio(returns, weights, horizon_days=80, n_simulations=120, seed=11, rebalance_every_days=0)
    assert not np.allclose(daily.terminal_values.to_numpy(), buy_hold.terminal_values.to_numpy())
    assert buy_hold.summary["rebalance_every_days"] == 0
