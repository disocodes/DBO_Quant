from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


def _qualified(catalog: str, schema: str, table: str) -> str:
    for value in (catalog, schema, table):
        if not value.replace("_", "").isalnum():
            raise ValueError(f"Unsafe Databricks identifier: {value!r}")
    return f"`{catalog}`.`{schema}`.`{table}`"


def connect_databricks(
    http_path: str,
    profile: Optional[str] = None,
    host: Optional[str] = None,
    auth_mode: str = "auto",
):
    """Connect to Databricks from an external machine through a SQL Warehouse."""
    from databricks import sql
    from databricks.sdk.core import Config

    mode = (auth_mode or "auto").strip().lower()
    if mode not in {"auto", "profile", "oauth"}:
        raise ValueError("auth_mode must be auto, profile, or oauth")

    if mode == "oauth" or (mode == "auto" and host and not profile):
        hostname = host.replace("https://", "").replace("http://", "").rstrip("/")
        return sql.connect(
            server_hostname=hostname,
            http_path=http_path,
            auth_type="databricks-oauth",
            _use_arrow_native_complex_types=False,
        )

    cfg = Config(profile=profile) if profile else Config()
    hostname = cfg.host.replace("https://", "").replace("http://", "").rstrip("/")
    return sql.connect(
        server_hostname=hostname,
        http_path=http_path,
        credentials_provider=lambda: cfg.authenticate,
        _use_arrow_native_complex_types=False,
    )


def load_current_portfolio(
    *,
    http_path: str,
    catalog: str,
    schema: str,
    portfolio_id: str,
    profile: Optional[str] = None,
    host: Optional[str] = None,
    auth_mode: str = "auto",
) -> pd.Series:
    table = _qualified(catalog, schema, "portfolio_holdings")
    with connect_databricks(http_path, profile, host, auth_mode) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT MAX(as_of_date) FROM {table} WHERE portfolio_id = ?", [portfolio_id])
            row = cur.fetchone()
            if not row or row[0] is None:
                raise ValueError(f"No holdings found for portfolio_id={portfolio_id!r}")
            as_of = row[0]
            cur.execute(
                f"SELECT symbol, weight FROM {table} WHERE portfolio_id = ? AND as_of_date = ? ORDER BY symbol",
                [portfolio_id, as_of],
            )
            rows = cur.fetchall()
    weights = pd.Series({str(symbol): float(weight) for symbol, weight in rows if weight is not None}, dtype=float)
    if weights.empty:
        raise ValueError("Portfolio has no weighted holdings")
    return weights / weights.sum()


def load_prices(
    *,
    http_path: str,
    catalog: str,
    schema: str,
    symbols: list[str],
    profile: Optional[str] = None,
    host: Optional[str] = None,
    auth_mode: str = "auto",
) -> pd.DataFrame:
    table = _qualified(catalog, schema, "prices_daily")
    symbols = [s.strip().upper() for s in symbols if s.strip()]
    if not symbols:
        raise ValueError("At least one symbol is required")
    placeholders = ",".join(["?"] * len(symbols))
    with connect_databricks(http_path, profile, host, auth_mode) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT date, symbol, COALESCE(adjusted_close, close) AS price FROM {table} "
                f"WHERE symbol IN ({placeholders}) ORDER BY date, symbol",
                symbols,
            )
            rows = cur.fetchall()
    if not rows:
        raise ValueError("No matching prices found in DBO_Quant. Run Databricks 01_INGEST_DATA first.")
    pdf = pd.DataFrame(rows, columns=["date", "symbol", "price"])
    wide = pdf.pivot_table(index="date", columns="symbol", values="price", aggfunc="last").sort_index()
    wide.index = pd.to_datetime(wide.index)
    wide = wide.reindex(columns=symbols).ffill().dropna(axis=1)
    if len(wide) < 60 or wide.shape[1] == 0:
        raise ValueError("Need at least 60 usable price rows and one asset after filtering")
    return wide


def require_optimization_runtime(solver: str = "cpu") -> dict:
    """Validate the Portfolio Optimization package and selected solver backend.

    cpu -> CVXPY with CLARABEL
    gpu -> CVXPY with NVIDIA cuOpt
    """
    import cvxpy as cp

    solver = str(solver).strip().lower()
    if solver not in {"cpu", "gpu"}:
        raise ValueError("solver must be 'cpu' or 'gpu'")
    if importlib.util.find_spec("portfolio_optimization") is None:
        raise RuntimeError(
            "portfolio_optimization is not importable. Install NVIDIA's portfolio-optimization package/environment first."
        )

    installed = {str(s) for s in cp.installed_solvers()}
    if solver == "cpu":
        if str(cp.CLARABEL) not in installed:
            raise RuntimeError("CPU mode requires the CVXPY CLARABEL solver.")
        return {"solver": cp.CLARABEL, "verbose": False}

    if not hasattr(cp, "CUOPT") or str(cp.CUOPT) not in installed:
        raise RuntimeError("GPU mode requires NVIDIA cuOpt to be installed and visible to CVXPY.")
    return {"solver": cp.CUOPT, "verbose": False, "solver_method": "PDLP"}


def optimize_and_frontier(
    prices: pd.DataFrame,
    *,
    solver: str = "cpu",
    risk_aversion: float = 1.0,
    confidence: float = 0.95,
    num_scenarios: int = 10_000,
    frontier_points: int = 25,
):
    from portfolio_optimization import cvar_optimizer, cvar_utils, utils
    from portfolio_optimization.cvar_parameters import CvarParameters
    from portfolio_optimization.settings import KDESettings, ReturnsComputeSettings, ScenarioGenerationSettings

    solver = solver.lower().strip()
    solver_settings = require_optimization_runtime(solver)
    compute_device = "GPU" if solver == "gpu" else "CPU"

    returns_dict = utils.calculate_returns(
        prices,
        regime_dict=None,
        returns_compute_settings=ReturnsComputeSettings(
            return_type="LOG",
            returns_compute_device=compute_device,
        ),
    )
    returns_dict = cvar_utils.generate_cvar_data(
        returns_dict,
        ScenarioGenerationSettings(
            num_scen=int(num_scenarios),
            fit_type="kde",
            kde_settings=KDESettings(device=compute_device),
        ),
    )
    params = CvarParameters(
        w_min=0.0,
        w_max=1.0,
        c_min=0.0,
        c_max=0.0,
        risk_aversion=float(risk_aversion),
        confidence=float(confidence),
    )
    optimizer = cvar_optimizer.CVaR(returns_dict, params)
    result_row, optimal_portfolio = optimizer.solve_optimization_problem(
        solver_settings=solver_settings,
        print_results=False,
    )
    frontier_df, fig, ax = cvar_utils.create_efficient_frontier(
        returns_dict,
        params,
        solver_settings,
        ra_num=int(frontier_points),
        show_plot=False,
        show_discretized_portfolios=False,
        benchmark_portfolios=False,
        print_portfolio_results=False,
    )
    return result_row, optimal_portfolio, returns_dict, frontier_df, fig, ax


def backtest_optimized(
    returns_dict: dict,
    optimal_portfolio,
    current_weights: Optional[pd.Series] = None,
):
    from portfolio_optimization import backtest
    from portfolio_optimization.portfolio import Portfolio

    tickers = list(returns_dict["tickers"])
    optimized = Portfolio(
        name="Optimized Portfolio",
        tickers=tickers,
        weights=np.asarray(optimal_portfolio.weights, dtype=float).flatten(),
        cash=float(np.asarray(optimal_portfolio.cash).squeeze()),
        time_range=optimal_portfolio.time_range,
    )
    benchmarks = [
        Portfolio(
            name="Equal Weight",
            tickers=tickers,
            weights=np.ones(len(tickers)) / len(tickers),
            cash=0.0,
        )
    ]
    if current_weights is not None:
        aligned = current_weights.reindex(tickers).fillna(0.0).astype(float)
        if aligned.sum() > 0:
            aligned = aligned / aligned.sum()
            benchmarks.append(
                Portfolio(name="Current Portfolio", tickers=tickers, weights=aligned.to_numpy(), cash=0.0)
            )
    tester = backtest.portfolio_backtester(
        optimized,
        returns_dict,
        risk_free_rate=0.0,
        test_method="historical",
        benchmark_portfolios=benchmarks,
    )
    backtest_results, _ax = tester.backtest_against_benchmarks(plot_returns=False)
    return backtest_results


def run_monthly_rebalancing(
    prices: pd.DataFrame,
    *,
    solver: str = "cpu",
    transaction_cost_factor: float = 0.0,
    look_back_window: int = 126,
    look_forward_window: int = 21,
    csv_path: str = "/tmp/dbo_quant_optimization_prices.csv",
):
    from portfolio_optimization import rebalance
    from portfolio_optimization.cvar_parameters import CvarParameters
    from portfolio_optimization.settings import KDESettings, ReturnsComputeSettings, ScenarioGenerationSettings

    solver = solver.lower().strip()
    solver_settings = require_optimization_runtime(solver)
    compute_device = "GPU" if solver == "gpu" else "CPU"
    path = Path(csv_path)
    prices.to_csv(path)
    if len(prices) <= look_back_window + look_forward_window:
        raise ValueError("Not enough price history for the requested rebalancing windows")
    params = CvarParameters(
        w_min=0.0, w_max=1.0, c_min=0.0, c_max=0.0, risk_aversion=1.0, confidence=0.95
    )
    runner = rebalance.rebalance_portfolio(
        dataset_directory=str(path),
        returns_compute_settings=ReturnsComputeSettings(
            return_type="LOG",
            returns_compute_device=compute_device,
        ),
        scenario_generation_settings=ScenarioGenerationSettings(
            fit_type="kde",
            kde_settings=KDESettings(device=compute_device),
        ),
        trading_start=str(prices.index[look_back_window].date()),
        trading_end=str(prices.index[-look_forward_window].date()),
        look_forward_window=int(look_forward_window),
        look_back_window=int(look_back_window),
        cvar_params=params,
        solver_settings=solver_settings,
        re_optimize_criteria={"type": "drift_from_optimal", "threshold": 0, "norm": 1},
        print_opt_result=False,
    )
    return runner.re_optimize(
        transaction_cost_factor=float(transaction_cost_factor),
        plot_results=False,
        plot_title="DBO_Quant Portfolio Rebalancing",
    )
