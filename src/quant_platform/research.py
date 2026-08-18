from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

import numpy as np
import pandas as pd

from .engine import WeightStrategy, run_backtest
from .location import discover_with_spark


def load_price_matrix(spark, table: str, symbols: list[str], benchmark: str | None = None):
    """Load a wide price matrix from the canonical DBO_Quant prices table."""
    from pyspark.sql import functions as F

    wanted = sorted(set(symbols + ([benchmark] if benchmark else [])))
    pdf = (
        spark.table(table)
        .where(F.col("symbol").isin(wanted))
        .select("date", "symbol", F.coalesce("adjusted_close", "close").alias("price"))
        .toPandas()
    )
    if pdf.empty:
        raise RuntimeError("No price rows found. Run notebooks/01_INGEST_DATA.py first.")
    wide = pdf.pivot_table(index="date", columns="symbol", values="price", aggfunc="last").sort_index()
    wide.index = pd.to_datetime(wide.index)
    research = wide.reindex(columns=symbols).ffill().dropna(how="all")
    if research.empty:
        raise RuntimeError(f"No usable prices found for requested symbols: {symbols}")
    benchmark_prices = None
    if benchmark and benchmark in wide.columns:
        benchmark_prices = wide[benchmark].reindex(research.index).ffill()
    return research, benchmark_prices


def persist_backtest(spark, catalog: str, schema: str, result, *, strategy_name: str, benchmark: str,
                     symbols: list[str], params: dict[str, Any], rebalance: str,
                     fee_bps: float, slippage_bps: float, notebook_path: str = "") -> str:
    """Persist one common-engine backtest to the canonical strategy result tables."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    start_date = result.daily.index.min().date()
    end_date = result.daily.index.max().date()
    run_row = {
        "run_id": result.run_id,
        "strategy_id": "",
        "strategy_name": strategy_name,
        "benchmark_symbol": benchmark,
        "start_date": start_date,
        "end_date": end_date,
        "initial_capital": float(result.metrics["initial_capital"]),
        "rebalance_frequency": rebalance,
        "fee_bps": float(fee_bps),
        "slippage_bps": float(slippage_bps),
        "parameters_json": json.dumps(params, default=str),
        "status": "COMPLETED",
        "source_engine": "quant_platform.weight_engine",
        "created_at": now,
        "completed_at": now,
        "metadata_json": json.dumps({"symbols": symbols, "notebook": notebook_path, **result.metadata}, default=str),
    }
    spark.createDataFrame(pd.DataFrame([run_row])).write.mode("append").saveAsTable(f"{catalog}.{schema}.strategy_runs")

    daily = result.daily.reset_index()
    daily.columns = ["date" if c == result.daily.index.name or c == "index" else c for c in daily.columns]
    daily["date"] = pd.to_datetime(daily["date"]).dt.date
    daily.insert(0, "run_id", result.run_id)
    for c in ["benchmark_return", "benchmark_wealth"]:
        if c not in daily:
            daily[c] = np.nan
    daily_cols = ["run_id", "date", "gross_return", "trading_cost_return", "net_return", "wealth",
                  "drawdown", "turnover", "benchmark_return", "benchmark_wealth"]
    spark.createDataFrame(daily[daily_cols]).write.mode("append").saveAsTable(f"{catalog}.{schema}.strategy_daily")

    holdings = []
    for dt in result.target_weights.index:
        for symbol in result.target_weights.columns:
            tw = float(result.target_weights.at[dt, symbol])
            ew = float(result.effective_weights.at[dt, symbol])
            if abs(tw) > 1e-12 or abs(ew) > 1e-12:
                holdings.append({
                    "run_id": result.run_id,
                    "date": pd.Timestamp(dt).date(),
                    "symbol": symbol,
                    "target_weight": tw,
                    "effective_weight": ew,
                })
    if holdings:
        spark.createDataFrame(pd.DataFrame(holdings)).write.mode("append").saveAsTable(f"{catalog}.{schema}.strategy_holdings")

    metrics = []
    for name, value in result.metrics.items():
        try:
            numeric = float(value)
            numeric = numeric if np.isfinite(numeric) else None
        except Exception:
            numeric = None
        metrics.append({"run_id": result.run_id, "metric_name": name, "metric_value": numeric, "metric_text": ""})
    spark.createDataFrame(pd.DataFrame(metrics)).write.mode("append").saveAsTable(f"{catalog}.{schema}.strategy_metrics")

    # When invoked by a Lakeflow Job, publish the run ID for downstream tasks.
    try:
        from databricks.sdk.runtime import dbutils
        dbutils.jobs.taskValues.set(key="strategy_run_id", value=str(result.run_id))
    except Exception:
        pass
    return result.run_id


def run_research_strategy(
    spark,
    *,
    catalog: str | None = None,
    schema: str | None = None,
    symbols: list[str],
    benchmark: str,
    strategy_name: str,
    strategy: str | WeightStrategy,
    params: dict[str, Any] | None = None,
    rebalance: str = "monthly",
    initial_capital: float = 100_000.0,
    fee_bps: float = 5.0,
    slippage_bps: float = 2.0,
    notebook_path: str = "",
):
    """Common entry point used by every strategy notebook.

    The canonical namespace registered by 00_SETUP is authoritative. `catalog` and
    `schema` are retained for backward compatibility but are not used to silently
    retarget research to another deployment.
    """
    location = discover_with_spark(spark)
    catalog, schema = location.catalog, location.schema

    prices, benchmark_prices = load_price_matrix(
        spark, f"{catalog}.{schema}.prices_daily", symbols, benchmark
    )
    result = run_backtest(
        prices,
        strategy,
        params=params or {},
        rebalance=rebalance,
        initial_capital=initial_capital,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        benchmark_prices=benchmark_prices,
        metadata={"symbols": symbols, "benchmark": benchmark, "notebook": notebook_path, "namespace": location.namespace},
    )
    persist_backtest(
        spark,
        catalog,
        schema,
        result,
        strategy_name=strategy_name,
        benchmark=benchmark,
        symbols=symbols,
        params=params or {},
        rebalance=rebalance,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        notebook_path=notebook_path,
    )
    return result
