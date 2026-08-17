from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def _clean_returns(returns: pd.Series) -> pd.Series:
    s = pd.Series(returns, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    return s


def annualized_return(returns: pd.Series, periods_per_year: int = TRADING_DAYS) -> float:
    r = _clean_returns(returns)
    if r.empty:
        return float("nan")
    total = float((1.0 + r).prod())
    years = len(r) / periods_per_year
    if years <= 0 or total <= 0:
        return float("nan")
    return total ** (1.0 / years) - 1.0


def annualized_volatility(returns: pd.Series, periods_per_year: int = TRADING_DAYS) -> float:
    r = _clean_returns(returns)
    if len(r) < 2:
        return float("nan")
    return float(r.std(ddof=1) * math.sqrt(periods_per_year))


def sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = TRADING_DAYS,
) -> float:
    r = _clean_returns(returns)
    if len(r) < 2:
        return float("nan")
    rf_period = (1.0 + risk_free_rate) ** (1.0 / periods_per_year) - 1.0
    excess = r - rf_period
    std = float(excess.std(ddof=1))
    if std == 0:
        return float("nan")
    return float(excess.mean() / std * math.sqrt(periods_per_year))


def sortino_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = TRADING_DAYS,
) -> float:
    r = _clean_returns(returns)
    if len(r) < 2:
        return float("nan")
    rf_period = (1.0 + risk_free_rate) ** (1.0 / periods_per_year) - 1.0
    excess = r - rf_period
    downside = excess[excess < 0]
    if downside.empty:
        return float("inf")
    downside_dev = float(np.sqrt((downside.pow(2)).mean()) * math.sqrt(periods_per_year))
    if downside_dev == 0:
        return float("nan")
    ann_excess = float(excess.mean() * periods_per_year)
    return ann_excess / downside_dev


def max_drawdown(wealth: pd.Series) -> float:
    w = pd.Series(wealth, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    if w.empty:
        return float("nan")
    dd = w / w.cummax() - 1.0
    return float(dd.min())


def historical_var(returns: pd.Series, confidence: float = 0.95) -> float:
    r = _clean_returns(returns)
    if r.empty:
        return float("nan")
    return float(-np.quantile(r, 1.0 - confidence))


def historical_cvar(returns: pd.Series, confidence: float = 0.95) -> float:
    r = _clean_returns(returns)
    if r.empty:
        return float("nan")
    q = np.quantile(r, 1.0 - confidence)
    tail = r[r <= q]
    return float(-tail.mean()) if not tail.empty else float("nan")


def beta_alpha(
    returns: pd.Series,
    benchmark_returns: Optional[pd.Series],
    periods_per_year: int = TRADING_DAYS,
) -> tuple[float, float]:
    if benchmark_returns is None:
        return float("nan"), float("nan")
    aligned = pd.concat(
        [_clean_returns(returns).rename("strategy"), _clean_returns(benchmark_returns).rename("benchmark")],
        axis=1,
        join="inner",
    ).dropna()
    if len(aligned) < 2:
        return float("nan"), float("nan")
    var_b = float(aligned["benchmark"].var(ddof=1))
    if var_b == 0:
        return float("nan"), float("nan")
    beta = float(aligned.cov().loc["strategy", "benchmark"] / var_b)
    alpha_daily = float(aligned["strategy"].mean() - beta * aligned["benchmark"].mean())
    alpha_ann = alpha_daily * periods_per_year
    return beta, alpha_ann


def performance_metrics(
    returns: pd.Series,
    wealth: Optional[pd.Series] = None,
    benchmark_returns: Optional[pd.Series] = None,
    risk_free_rate: float = 0.0,
    periods_per_year: int = TRADING_DAYS,
) -> dict[str, float]:
    r = _clean_returns(returns)
    if wealth is None:
        wealth = (1.0 + r).cumprod()
    total_return = float((1.0 + r).prod() - 1.0) if not r.empty else float("nan")
    cagr = annualized_return(r, periods_per_year)
    vol = annualized_volatility(r, periods_per_year)
    sharpe = sharpe_ratio(r, risk_free_rate, periods_per_year)
    sortino = sortino_ratio(r, risk_free_rate, periods_per_year)
    mdd = max_drawdown(wealth)
    beta, alpha = beta_alpha(r, benchmark_returns, periods_per_year)
    calmar = cagr / abs(mdd) if pd.notna(cagr) and pd.notna(mdd) and mdd != 0 else float("nan")
    win_rate = float((r > 0).mean()) if not r.empty else float("nan")
    return {
        "total_return": total_return,
        "cagr": cagr,
        "annualized_volatility": vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": mdd,
        "calmar": calmar,
        "var_95_daily": historical_var(r, 0.95),
        "cvar_95_daily": historical_cvar(r, 0.95),
        "win_rate": win_rate,
        "beta": beta,
        "alpha_annualized": alpha,
    }
