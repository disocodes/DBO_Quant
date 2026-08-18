from __future__ import annotations

import numpy as np
import pandas as pd

from .workflow import (
    backtest_optimized,
    connect_databricks,
    load_current_portfolio,
    load_prices,
    optimize_and_frontier,
    require_optimization_runtime,
    run_monthly_rebalancing,
)

MARKER_TABLE = "dbo_quant_project_config"


def _resolve_external_location(
    *,
    http_path: str,
    profile: str | None,
    host: str | None,
    auth_mode: str,
    catalog: str | None,
    schema: str | None,
) -> tuple[str, str]:
    if catalog and schema:
        return catalog, schema
    with connect_databricks(http_path, profile, host, auth_mode) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT table_catalog, table_schema
                FROM system.information_schema.tables
                WHERE table_name = '{MARKER_TABLE}'
                  AND table_schema <> 'information_schema'
                ORDER BY table_catalog, table_schema
                """
            )
            rows = [(str(r[0]), str(r[1])) for r in cur.fetchall()]
    unique = sorted(set(rows))
    if not unique:
        raise RuntimeError(
            "No DBO_Quant deployment marker is visible. Run notebooks/00_SETUP.py first, "
            "or set DBO_CATALOG and DBO_SCHEMA as an explicit override."
        )
    if len(unique) > 1:
        choices = ", ".join(f"{c}.{s}" for c, s in unique)
        raise RuntimeError(
            f"Multiple DBO_Quant deployments are visible: {choices}. "
            "Set DBO_CATALOG and DBO_SCHEMA to choose one explicitly."
        )
    return unique[0]


def execute_optimization_analysis(
    *,
    prices: pd.DataFrame,
    current_weights: pd.Series | None = None,
    solver: str = "cpu",
    risk_aversion: float = 1.0,
    confidence: float = 0.95,
    num_scenarios: int = 10_000,
    frontier_points: int = 25,
    run_rebalancing: bool = False,
    transaction_cost_factor: float = 0.0,
    look_back_window: int = 126,
    look_forward_window: int = 21,
) -> dict:
    solver = solver.lower().strip()
    require_optimization_runtime(solver)
    result_row, optimal_portfolio, returns_dict, frontier_df, frontier_fig, _ = optimize_and_frontier(
        prices,
        solver=solver,
        risk_aversion=risk_aversion,
        confidence=confidence,
        num_scenarios=num_scenarios,
        frontier_points=frontier_points,
    )
    tickers = list(returns_dict["tickers"])
    optimal_weights = pd.Series(
        np.asarray(optimal_portfolio.weights, dtype=float).flatten(),
        index=tickers,
        name="optimized_weight",
    )
    backtest_results = backtest_optimized(returns_dict, optimal_portfolio, current_weights=current_weights)

    rebalance_results = None
    rebalance_dates = []
    rebalance_curve = pd.Series(dtype=float)
    if run_rebalancing:
        rebalance_results, rebalance_dates, rebalance_curve = run_monthly_rebalancing(
            prices,
            solver=solver,
            transaction_cost_factor=transaction_cost_factor,
            look_back_window=look_back_window,
            look_forward_window=look_forward_window,
        )

    return {
        "solver": solver,
        "prices": prices,
        "current_weights": current_weights,
        "optimal_weights": optimal_weights,
        "frontier": frontier_df,
        "frontier_figure": frontier_fig,
        "backtest_results": backtest_results,
        "rebalance_results": rebalance_results,
        "rebalance_dates": rebalance_dates,
        "rebalance_curve": rebalance_curve,
        "result_row": result_row,
        "optimal_portfolio": optimal_portfolio,
        "returns_dict": returns_dict,
        "optimization_run_id": None,
        "rebalance_run_id": None,
    }


def run_external_workflow(
    *,
    http_path: str,
    catalog: str | None = None,
    schema: str | None = None,
    profile: str | None = None,
    host: str | None = None,
    auth_mode: str = "auto",
    portfolio_id: str = "",
    symbols: list[str] | None = None,
    solver: str = "cpu",
    risk_aversion: float = 1.0,
    confidence: float = 0.95,
    num_scenarios: int = 10_000,
    frontier_points: int = 25,
    run_rebalancing: bool = False,
    transaction_cost_factor: float = 0.0,
    look_back_window: int = 126,
    look_forward_window: int = 21,
    push_results: bool = True,
):
    """External CPU/GPU route using a Databricks SQL Warehouse."""
    solver = solver.lower().strip()
    catalog, schema = _resolve_external_location(
        http_path=http_path,
        profile=profile,
        host=host,
        auth_mode=auth_mode,
        catalog=catalog,
        schema=schema,
    )
    print(f"DBO_Quant namespace: {catalog}.{schema}")
    print(f"Optimization solver: {solver.upper()}")

    current_weights = None
    if portfolio_id:
        current_weights = load_current_portfolio(
            http_path=http_path, catalog=catalog, schema=schema, portfolio_id=portfolio_id,
            profile=profile, host=host, auth_mode=auth_mode,
        )
        universe = list(current_weights.index)
    else:
        universe = [s.strip().upper() for s in (symbols or []) if s.strip()]
    if not universe:
        raise ValueError("Set portfolio_id or provide symbols")

    prices = load_prices(
        http_path=http_path, catalog=catalog, schema=schema, symbols=universe,
        profile=profile, host=host, auth_mode=auth_mode,
    )
    output = execute_optimization_analysis(
        prices=prices,
        current_weights=current_weights,
        solver=solver,
        risk_aversion=risk_aversion,
        confidence=confidence,
        num_scenarios=num_scenarios,
        frontier_points=frontier_points,
        run_rebalancing=run_rebalancing,
        transaction_cost_factor=transaction_cost_factor,
        look_back_window=look_back_window,
        look_forward_window=look_forward_window,
    )

    if not push_results:
        return output

    # The SQL write-back bridge is external-route infrastructure. Import it only
    # here so Databricks-native CPU/GPU runs do not require SQL connector packages.
    from nvidia_bridge import DatabricksOptimizationBridge, NvidiaAnalysisWriter

    result_row = output["result_row"]
    optimal_portfolio = output["optimal_portfolio"]
    returns_dict = output["returns_dict"]
    frontier_df = output["frontier"]
    optimal_weights = output["optimal_weights"]
    tickers = list(returns_dict["tickers"])

    bridge = DatabricksOptimizationBridge(
        http_path=http_path, catalog=catalog, schema=schema, profile=profile, host=host, auth_mode=auth_mode
    )
    writer = NvidiaAnalysisWriter(bridge)
    frontier_metrics = frontier_df.drop(columns=["weights"], errors="ignore").copy()
    source_engine = (
        "NVIDIA-AI-Blueprints/portfolio-optimization:CVXPY-CLARABEL"
        if solver == "cpu"
        else "NVIDIA-AI-Blueprints/portfolio-optimization:CVXPY-cuOpt"
    )
    optimization_run_id = bridge.push_efficient_frontier(
        frontier_metrics,
        objective="mean_cvar",
        source_engine=source_engine,
        source_notebook="optimization/portfolio_optimization/PORTFOLIO_OPTIMIZATION.ipynb",
        portfolio_id=portfolio_id or None,
        metadata={
            "solver": solver,
            "risk_aversion": risk_aversion,
            "confidence": confidence,
            "num_scenarios": num_scenarios,
            "frontier_points": frontier_points,
            "symbols": tickers,
        },
    )
    if "weights" in frontier_df.columns:
        for point_id, row in frontier_df.reset_index(drop=True).iterrows():
            weights = row["weights"]
            if isinstance(weights, dict):
                bridge.push_allocation(
                    optimization_run_id, weights, portfolio_label=f"frontier_{point_id:04d}",
                    point_id=int(point_id), expected_return=row.get("return"), cvar=row.get("CVaR"),
                    metadata={"risk_aversion": row.get("risk_aversion"), "solver": solver},
                )
    bridge.push_allocation(
        optimization_run_id,
        optimal_weights,
        portfolio_label="selected_optimal",
        expected_return=result_row.get("return") if hasattr(result_row, "get") else None,
        cvar=result_row.get("CVaR") if hasattr(result_row, "get") else None,
        metadata={"cash": float(np.asarray(optimal_portfolio.cash).squeeze()), "solver": solver},
    )
    covariance = pd.DataFrame(np.asarray(returns_dict["covariance"], dtype=float), index=tickers, columns=tickers)
    bridge.push_matrix(optimization_run_id, covariance, matrix_name="covariance")
    writer.push_backtest_metrics(optimization_run_id, output["backtest_results"])

    rebalance_run_id = None
    if run_rebalancing:
        rebalance_run_id = writer.push_rebalancing(
            optimization_run_id=optimization_run_id,
            results_dataframe=output["rebalance_results"],
            re_optimize_dates=output["rebalance_dates"],
            cumulative_portfolio_value=pd.Series(output["rebalance_curve"]),
            portfolio_id=portfolio_id or None,
            transaction_cost_factor=transaction_cost_factor,
            look_back_window=look_back_window,
            look_forward_window=look_forward_window,
        )

    output["optimization_run_id"] = optimization_run_id
    output["rebalance_run_id"] = rebalance_run_id
    output["catalog"] = catalog
    output["schema"] = schema
    return output
