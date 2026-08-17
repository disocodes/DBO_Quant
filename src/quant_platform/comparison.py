from __future__ import annotations

from typing import Mapping
import pandas as pd

from .engine import BacktestResult


def compare_backtests(results: Mapping[str, BacktestResult]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return metrics table, wealth curves and return correlations."""
    if not results:
        raise ValueError("At least one backtest result is required")
    metrics = pd.DataFrame({name: result.metrics for name, result in results.items()}).T
    wealth = pd.concat({name: result.daily["wealth"] for name, result in results.items()}, axis=1).sort_index()
    rets = pd.concat({name: result.daily["net_return"] for name, result in results.items()}, axis=1).sort_index()
    corr = rets.corr()
    return metrics, wealth, corr
