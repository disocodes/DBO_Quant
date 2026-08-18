"""DBO_Quant application entrypoint.

Imports the core OpenBB/Databricks API and adds optional NVIDIA portfolio-analysis routes.
"""
from typing import Optional

from fastapi import HTTPException

from app import app, fq, query_records


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
    return query_records(
        f"SELECT * FROM {fq('optimization_rebalance_runs')} ORDER BY created_at DESC LIMIT {limit}"
    )


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
    openapi_extra={"widget_config": {"type": "chart", "name": "Optimizer Rebalancing Value", "category": "Portfolio Lab"}},
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
            "title": "NVIDIA cuOpt Rebalancing",
            "xaxis": {"title": "Date"},
            "yaxis": {"title": "Portfolio Value"},
        },
    }
