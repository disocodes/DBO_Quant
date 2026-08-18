from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from pyspark.sql import functions as F

MARKER_TABLE = "dbo_quant_project_config"


def discover_location_spark(spark, *, catalog: str | None = None, schema: str | None = None) -> tuple[str, str]:
    if catalog and schema:
        spark.table(f"`{catalog}`.`{schema}`.`{MARKER_TABLE}`").limit(1).collect()
        return catalog, schema
    rows = spark.sql(
        f"""
        SELECT table_catalog, table_schema
        FROM system.information_schema.tables
        WHERE table_name = '{MARKER_TABLE}'
          AND table_schema <> 'information_schema'
        ORDER BY table_catalog, table_schema
        """
    ).collect()
    unique = sorted(set((str(r[0]), str(r[1])) for r in rows))
    if not unique:
        raise RuntimeError("No DBO_Quant deployment marker found. Run notebooks/00_SETUP.py first.")
    if len(unique) > 1:
        choices = ", ".join(f"{c}.{s}" for c, s in unique)
        raise RuntimeError(f"Multiple DBO_Quant deployments found: {choices}. Supply catalog/schema explicitly.")
    return unique[0]


def load_inputs_spark(spark, *, catalog: str, schema: str, portfolio_id: str = "", symbols: list[str] | None = None):
    current_weights = None
    if portfolio_id:
        holdings = spark.table(f"{catalog}.{schema}.portfolio_holdings").where(F.col("portfolio_id") == portfolio_id)
        latest = holdings.agg(F.max("as_of_date").alias("d")).first()["d"]
        if latest is None:
            raise ValueError(f"No holdings found for portfolio_id={portfolio_id!r}")
        pdf = holdings.where(F.col("as_of_date") == latest).select("symbol", "weight").toPandas()
        current_weights = pd.Series(dict(zip(pdf.symbol, pdf.weight)), dtype=float)
        current_weights = current_weights / current_weights.sum()
        universe = list(current_weights.index)
    else:
        universe = [s.strip().upper() for s in (symbols or []) if s.strip()]
    if not universe:
        raise ValueError("Set portfolio_id or symbols in portfolio_config.toml")

    prices = (
        spark.table(f"{catalog}.{schema}.prices_daily")
        .where(F.col("symbol").isin(universe))
        .select("date", "symbol", F.coalesce("adjusted_close", "close").alias("price"))
        .toPandas()
    )
    if prices.empty:
        raise ValueError("No matching prices found. Run notebooks/01_INGEST_DATA.py first.")
    wide = prices.pivot_table(index="date", columns="symbol", values="price", aggfunc="last").sort_index()
    wide.index = pd.to_datetime(wide.index)
    wide = wide.reindex(columns=universe).ffill().dropna(axis=1)
    if len(wide) < 60:
        raise ValueError("Need at least 60 usable price rows")
    return wide, current_weights


def _finite(value):
    try:
        f = float(value)
        return f if math.isfinite(f) else None
    except Exception:
        return None


def persist_result_spark(spark, *, catalog: str, schema: str, result: dict, portfolio_id: str = "", source_notebook: str = "notebooks/portfolio/04_NVIDIA_GPU_DATABRICKS.py", transaction_cost_factor: float = 0.0, look_back_window: int = 126, look_forward_window: int = 21):
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    frontier = result["frontier"].reset_index(drop=True)
    optimal = result["optimal_weights"]
    result_row = result["result_row"]
    returns_dict = result["returns_dict"]

    run_pdf = pd.DataFrame([{
        "optimization_run_id": run_id,
        "portfolio_id": portfolio_id or None,
        "objective": "mean_cvar",
        "source_engine": "NVIDIA-AI-Blueprints/portfolio-optimization",
        "source_notebook": source_notebook,
        "status": "COMPLETED",
        "created_at": now,
        "completed_at": now,
        "metadata_json": json.dumps({"execution_location": "databricks_gpu"}),
    }])
    spark.createDataFrame(run_pdf).write.mode("append").saveAsTable(f"{catalog}.{schema}.optimization_runs")

    frontier_rows=[]; allocation_rows=[]
    for i,row in frontier.iterrows():
        frontier_rows.append({
            "optimization_run_id":run_id,"point_id":int(i),"regime":None,"solver":"cuOpt GPU",
            "solve_time_seconds":_finite(row.get("solve time")),"expected_return":_finite(row.get("return")),
            "cvar":_finite(row.get("CVaR")),"objective_value":_finite(row.get("obj")),
            "risk_aversion":_finite(row.get("risk_aversion")),"variance":_finite(row.get("variance")),
            "volatility":_finite(row.get("volatility")),"sharpe":_finite(row.get("sharpe")),"metadata_json":"{}"})
        weights=row.get("weights")
        if isinstance(weights,dict):
            for symbol,weight in weights.items():
                allocation_rows.append({"optimization_run_id":run_id,"portfolio_label":f"frontier_{i:04d}","point_id":int(i),"symbol":str(symbol),"weight":float(weight),"expected_return":_finite(row.get("return")),"volatility":_finite(row.get("volatility")),"cvar":_finite(row.get("CVaR")),"sharpe":_finite(row.get("sharpe")),"metadata_json":"{}"})
    if frontier_rows:
        spark.createDataFrame(pd.DataFrame(frontier_rows)).write.mode("append").saveAsTable(f"{catalog}.{schema}.efficient_frontier")

    for symbol,weight in optimal.items():
        allocation_rows.append({"optimization_run_id":run_id,"portfolio_label":"selected_optimal","point_id":None,"symbol":str(symbol),"weight":float(weight),"expected_return":_finite(result_row.get("return") if hasattr(result_row,"get") else None),"volatility":None,"cvar":_finite(result_row.get("CVaR") if hasattr(result_row,"get") else None),"sharpe":None,"metadata_json":"{}"})
    if allocation_rows:
        spark.createDataFrame(pd.DataFrame(allocation_rows)).write.mode("append").saveAsTable(f"{catalog}.{schema}.optimal_allocations")

    cov = np.asarray(returns_dict["covariance"],dtype=float); tickers=list(returns_dict["tickers"])
    matrix_rows=[{"optimization_run_id":run_id,"matrix_name":"covariance","row_symbol":r,"column_symbol":c,"value":float(cov[i,j])} for i,r in enumerate(tickers) for j,c in enumerate(tickers)]
    spark.createDataFrame(pd.DataFrame(matrix_rows)).write.mode("append").saveAsTable(f"{catalog}.{schema}.optimization_matrix_entries")

    bt=result.get("backtest_results")
    bt_rows=[]
    if bt is not None and not bt.empty:
        frame=bt.reset_index() if bt.index.name or not isinstance(bt.index,pd.RangeIndex) else bt.copy()
        for i,row in frame.iterrows():
            name=str(row.get("portfolio_name",row.get("portfolio",row.get("name",f"portfolio_{i}"))))
            for col,val in row.items():
                if col in {"portfolio_name","portfolio","name"}: continue
                num=_finite(val)
                bt_rows.append({"optimization_run_id":run_id,"portfolio_name":name,"metric_name":str(col),"metric_value":num,"metric_text":"" if num is not None else str(val)})
    if bt_rows:
        spark.createDataFrame(pd.DataFrame(bt_rows)).write.mode("append").saveAsTable(f"{catalog}.{schema}.optimization_backtest_metrics")

    rebalance_run_id=None
    if result.get("rebalance_results") is not None:
        rebalance_run_id=str(uuid.uuid4())
        rr=pd.DataFrame([{"rebalance_run_id":rebalance_run_id,"optimization_run_id":run_id,"portfolio_id":portfolio_id or None,"source_engine":"NVIDIA-AI-Blueprints/portfolio-optimization","transaction_cost_factor":float(transaction_cost_factor),"look_back_window":int(look_back_window),"look_forward_window":int(look_forward_window),"created_at":now,"metadata_json":json.dumps({"execution_location":"databricks_gpu"})}])
        spark.createDataFrame(rr).write.mode("append").saveAsTable(f"{catalog}.{schema}.optimization_rebalance_runs")
        curve=pd.Series(result.get("rebalance_curve"))
        daily=[]
        for dt,val in curve.dropna().items():
            try: daily.append({"rebalance_run_id":rebalance_run_id,"date":pd.Timestamp(dt).date(),"portfolio_value":float(val)})
            except Exception: pass
        if daily: spark.createDataFrame(pd.DataFrame(daily)).write.mode("append").saveAsTable(f"{catalog}.{schema}.optimization_rebalance_daily")
    return run_id, rebalance_run_id
