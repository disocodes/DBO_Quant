from __future__ import annotations

from dataclasses import dataclass
import uuid

import numpy as np
import pandas as pd


@dataclass
class MonteCarloResult:
    run_id: str
    percentiles: pd.DataFrame
    sample_paths: pd.DataFrame
    terminal_values: pd.Series
    summary: dict[str, float]


def simulate_portfolio(
    asset_returns: pd.DataFrame,
    weights: pd.Series | np.ndarray,
    *,
    initial_value: float = 100_000.0,
    horizon_days: int = 252 * 10,
    n_simulations: int = 10_000,
    method: str = "historical_bootstrap",
    seed: int = 42,
    sample_path_count: int = 50,
    block_size: int = 5,
    rebalance_every_days: int = 21,
) -> MonteCarloResult:
    """
    Portfolio Visualizer-style forward simulations with portfolio-weight drift.

    Methods:
      - ``historical_bootstrap``: block-bootstraps historical multi-asset return rows,
        preserving same-day cross-asset co-movement and short stretches of serial structure.
      - ``multivariate_normal``: draws daily vectors from the historical mean/covariance.

    Rebalancing:
      - ``rebalance_every_days=1``: reset to target weights every simulated trading day.
      - ``21``: approximately monthly, ``63``: approximately quarterly, ``252``: annual.
      - ``0``: true buy-and-hold; weights drift for the entire simulation.

    The simulation is streamed by day rather than materializing a full
    ``horizon × simulations × assets`` tensor. This keeps memory bounded while still
    preserving asset-level weight drift inside every simulated path.
    """
    r = asset_returns.astype(float).replace([np.inf, -np.inf], np.nan).dropna(how="any")
    if r.empty:
        raise ValueError("asset_returns contains no complete return observations")
    if initial_value <= 0:
        raise ValueError("initial_value must be positive")
    if horizon_days < 1 or n_simulations < 1:
        raise ValueError("horizon_days and n_simulations must be positive")
    if rebalance_every_days < 0:
        raise ValueError("rebalance_every_days must be >= 0")

    if isinstance(weights, pd.Series):
        w = weights.reindex(r.columns).astype(float)
    else:
        w = pd.Series(weights, index=r.columns, dtype=float)
    if w.isna().any():
        raise ValueError("weights must be supplied for every asset")
    if abs(float(w.sum())) < 1e-12:
        raise ValueError("weights sum to zero")
    w = w / w.sum()
    target = w.to_numpy(dtype=np.float64)

    rng = np.random.default_rng(seed)
    q_levels = np.array([1, 5, 10, 25, 50, 75, 90, 95, 99], dtype=float)
    percentile_values = np.empty((horizon_days + 1, len(q_levels)), dtype=np.float64)
    percentile_values[0, :] = initial_value

    keep = min(max(1, int(sample_path_count)), n_simulations)
    sample_idx = np.linspace(0, n_simulations - 1, num=keep, dtype=int)
    sample_values = np.empty((horizon_days + 1, keep), dtype=np.float64)
    sample_values[0, :] = initial_value

    values = np.full(n_simulations, float(initial_value), dtype=np.float64)
    sim_weights = np.tile(target, (n_simulations, 1))

    method = method.lower().strip()
    hist = r.to_numpy(dtype=np.float64)
    n_obs = len(hist)
    block_size = max(1, min(int(block_size), n_obs))
    bootstrap_starts = None

    if method == "multivariate_normal":
        mu = r.mean().to_numpy(dtype=np.float64)
        cov = r.cov().to_numpy(dtype=np.float64)
    elif method != "historical_bootstrap":
        raise ValueError("method must be historical_bootstrap or multivariate_normal")

    for day in range(horizon_days):
        if day > 0 and rebalance_every_days > 0 and day % rebalance_every_days == 0:
            sim_weights[:, :] = target

        if method == "historical_bootstrap":
            offset = day % block_size
            if offset == 0 or bootstrap_starts is None:
                high = max(1, n_obs - block_size + 1)
                bootstrap_starts = rng.integers(0, high, size=n_simulations)
            row_idx = np.minimum(bootstrap_starts + offset, n_obs - 1)
            sampled = hist[row_idx, :]
        else:
            sampled = rng.multivariate_normal(mu, cov, size=n_simulations)
            sampled = np.maximum(sampled, -0.999999)

        portfolio_return = np.einsum("sa,sa->s", sim_weights, sampled)
        growth = 1.0 + portfolio_return
        if np.any(~np.isfinite(growth)) or np.any(growth <= 0):
            raise ValueError(
                "A simulated portfolio path became non-positive. Reduce leverage/volatility "
                "or use a model that cannot generate returns below -100% at the portfolio level."
            )

        values *= growth
        sim_weights = sim_weights * (1.0 + sampled) / growth[:, None]

        percentile_values[day + 1, :] = np.percentile(values, q_levels)
        sample_values[day + 1, :] = values[sample_idx]

    percentiles = pd.DataFrame(percentile_values, columns=[f"p{int(x)}" for x in q_levels])
    percentiles.index.name = "day"
    sample_paths = pd.DataFrame(sample_values, columns=[f"path_{i}" for i in range(keep)])
    sample_paths.index.name = "day"

    terminal = pd.Series(values.copy(), name="terminal_value")
    summary = {
        "initial_value": float(initial_value),
        "horizon_days": float(horizon_days),
        "n_simulations": float(n_simulations),
        "rebalance_every_days": float(rebalance_every_days),
        "median_terminal_value": float(np.median(terminal)),
        "mean_terminal_value": float(np.mean(terminal)),
        "p05_terminal_value": float(np.percentile(terminal, 5)),
        "p95_terminal_value": float(np.percentile(terminal, 95)),
        "probability_of_loss": float(np.mean(terminal < initial_value)),
    }
    return MonteCarloResult(
        run_id=str(uuid.uuid4()),
        percentiles=percentiles,
        sample_paths=sample_paths,
        terminal_values=terminal,
        summary=summary,
    )
