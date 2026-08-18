"""DBO_Quant application entrypoint.

Imports the core OpenBB/Databricks API and adds saved-portfolio and portfolio-
optimization routes. openbb-platform-api discovers these routes automatically.
"""
from typing import Optional

from fastapi import HTTPException

from app import app, fq, query_records


@app.get(
    "/api/quant/portfolio/saved",
    openapi_extra={"widget_config": {"name": "Saved Portfolios", "category": "Portfolio Lab"}},
)
def saved_portfolios(limit: int = 100) -> list[dict]:
    limit = max(1, min(limit, 1000))
    return query_records(f"SELECT * FROM {fq('portfolio_definitions')} ORDER BY created_at DESC LIMIT {limit}")


@app.get(
    "/api/quant/portfolio/holdings",
    openapi_extra={"widget_config": {"name": "Portfolio Holdings", "category": "Portfolio Lab"}},
)
def saved_portfolio_holdings(portfolio_id: str) -> list[dict]:
    return query_records(
        f"""SELECT portfolio_id, as_of_date, symbol, weight, quantity, market_value, source
        FROM {fq('portfolio_holdings')}
        WHERE portfolio_id = ?
          AND as_of_date = (SELECT MAX(as_of_date) FROM {fq('portfolio_holdings')} WHERE portfolio_id = ?)
        ORDER BY weight DESC, symbol""",
        [portfolio_id, portfolio_id],
    )


@app.get(
    "/api/quant/optimization/cvar-frontier",
    openapi_extra={"widget_config": {"type": "chart", "name": "Mean-CVaR Efficient Frontier", "category": "Portfolio Lab"}},
)
def cvar_frontier(optimization_run_id: str) -> dict:
    rows = query_records(
        f"SELECT point_id, expected_return, cvar, risk_aversion FROM {fq('efficient_frontier')} WHERE optimization_run_id = ? AND cvar IS NOT NULL ORDER BY point_id",
        [optimization_run_id],
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No CVaR frontier found for optimization_run_id")
    return {
        "data": [{
            "type": "scatter",
            "mode": "lines+markers",
            "name": "Mean-CVaR Frontier",
            "x": [r["cvar"] for r in rows],
            "y": [r["expected_return"] for r in rows],
            "text": [f"Risk aversion={r.get('risk_aversion')}" for r in rows],
        }],
        "layout": {
            "title": "Mean-CVaR Efficient Frontier",
            "xaxis": {"title": "CVaR", "tickformat": ".1%"},
            "yaxis": {"title": "Expected Return", "tickformat": ".1%"},
        },
    }


@app.get(
    "/api/quant/optimization/allocation-chart",
    openapi_extra={"widget_config": {"type": "chart", "name": "Optimized Allocation", "category": "Portfolio Lab"}},
)
def optimizer_allocation_chart(optimization_run_id: str, portfolio_label: str = "selected_optimal") -> dict:
    rows = query_records(
        f"SELECT symbol, weight FROM {fq('optimal_allocations')} WHERE optimization_run_id = ? AND portfolio_label = ? ORDER BY ABS(weight) DESC",
        [optimization_run_id, portfolio_label],
    )
    if not rows:
        raise HTTPException(status_code=404, detail="allocation not found")
    return {
        "data": [{
            "type": "bar",
            "name": portfolio_label,
            "x": [r["symbol"] for r in rows],
            "y": [r["weight"] for r in rows],
        }],
        "layout": {
            "title": f"Portfolio Allocation — {portfolio_label}",
            "xaxis": {"title": "Asset"},
            "yaxis": {"title": "Weight", "tickformat": ".1%"},
        },
    }


@app.get(
    "/api/quant/optimization/backtest-metrics",
    openapi_extra={"widget_config": {"name": "Optimizer Backtest Metrics", "category": "Portfolio Lab"}},
)
def optimizer_backtest_metrics(optimization_run_id: str) -> list[dict]:
    return query_records(
        f"SELECT portfolio_name, metric_name, metric_value, metric_text FROM {fq('optimization_backtest_metrics')} WHERE optimization_run_id = ? ORDER BY portfolio_name, metric_name",
        [optimization_run_id],
    )


@app.get(
    "/api/quant/optimization/rebalance-runs",
    openapi_extra={"widget_config": {"name": "Optimizer Rebalancing Runs", "category": "Portfolio Lab"}},
)
def optimizer_rebalance_runs(optimization_run_id: Optional[str] = None, limit: int = 100) -> list[dict]:
    limit = max(1, min(limit, 1000))
    if optimization_run_id:
        return query_records(
            f"SELECT * FROM {fq('optimization_rebalance_runs')} WHERE optimization_run_id = ? ORDER BY created_at DESC LIMIT {limit}",
            [optimization_run_id],
        )
    return query_records(f"SELECT * FROM {fq('optimization_rebalance_runs')} ORDER BY created_at DESC LIMIT {limit}")


@app.get(
    "/api/quant/optimization/rebalance-events",
    openapi_extra={"widget_config": {"name": "Optimizer Rebalance Events", "category": "Portfolio Lab"}},
)
def optimizer_rebalance_events(rebalance_run_id: str) -> list[dict]:
    return query_records(
        f"SELECT event_index, event_date, event_json FROM {fq('optimization_rebalance_events')} WHERE rebalance_run_id = ? ORDER BY event_index",
        [rebalance_run_id],
    )


@app.get(
    "/api/quant/optimization/rebalance-curve",
    openapi_extra={"widget_config": {"type": "chart", "name": "Portfolio Rebalancing Value", "category": "Portfolio Lab"}},
)
def optimizer_rebalance_curve(rebalance_run_id: str) -> dict:
    rows = query_records(
        f"SELECT date, portfolio_value FROM {fq('optimization_rebalance_daily')} WHERE rebalance_run_id = ? ORDER BY date",
        [rebalance_run_id],
    )
    if not rows:
        raise HTTPException(status_code=404, detail="rebalance_run_id not found")
    return {
        "data": [{
            "type": "scatter",
            "mode": "lines",
            "name": "Rebalanced Portfolio",
            "x": [r["date"] for r in rows],
            "y": [r["portfolio_value"] for r in rows],
        }],
        "layout": {
            "title": "Portfolio Rebalancing",
            "xaxis": {"title": "Date"},
            "yaxis": {"title": "Portfolio Value"},
        },
    }
