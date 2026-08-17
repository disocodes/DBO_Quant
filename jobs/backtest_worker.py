# Databricks notebook source
# MAGIC %md
# MAGIC # Quant Platform — Backtest Worker
# MAGIC This notebook is intended to be configured as a Databricks Job. The OpenBB/Databricks App can call the Job with parameters.

# COMMAND ----------
import json, os, sys
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from pyspark.sql import functions as F

# If this source file is imported as part of the supplied folder/repo, make ../src importable.
try:
    _here = Path(__file__).resolve()
    sys.path.insert(0, str(_here.parents[1] / "src"))
except Exception:
    pass

from quant_platform import REGISTRY, factor_or_model_strategy, run_backtest

# COMMAND ----------
PARAMS = {
    "catalog": "main",
    "schema": "openbb_quant",
    "strategy_name": "inverse_volatility",
    "portfolio_id": "",
    "symbols": "SPY,QQQ,IEF,GLD",
    "start_date": "2015-01-01",
    "end_date": "",
    "benchmark_symbol": "SPY",
    "rebalance": "monthly",
    "initial_capital": "100000",
    "fee_bps": "5",
    "slippage_bps": "2",
    "risk_free_rate": "0",
    "long_only": "true",
    "gross_leverage_limit": "1.0",
    "parameters_json": "{}",
}
for k, default in PARAMS.items():
    try:
        dbutils.widgets.text(k, default)
        PARAMS[k] = dbutils.widgets.get(k)
    except Exception:
        PARAMS[k] = os.getenv(k.upper(), default)

catalog = PARAMS["catalog"]
schema = PARAMS["schema"]
strategy_name = PARAMS["strategy_name"]
portfolio_id = PARAMS["portfolio_id"].strip() or None
symbols = [s.strip().upper() for s in PARAMS["symbols"].split(",") if s.strip()]
start_date = PARAMS["start_date"]
end_date = PARAMS["end_date"] or None
benchmark_symbol = PARAMS["benchmark_symbol"].strip().upper() or None
rebalance = PARAMS["rebalance"]
initial_capital = float(PARAMS["initial_capital"])
fee_bps = float(PARAMS["fee_bps"])
slippage_bps = float(PARAMS["slippage_bps"])
risk_free_rate = float(PARAMS["risk_free_rate"])
long_only = str(PARAMS["long_only"]).strip().lower() in {"1", "true", "yes", "y"}
gross_leverage_limit = float(PARAMS["gross_leverage_limit"])
strategy_params = json.loads(PARAMS["parameters_json"] or "{}")

# A saved portfolio can define the research universe. For fixed allocation / true
# buy-and-hold runs, its latest stored weights become the target allocation unless
# explicit strategy weights were supplied in parameters_json.
portfolio_as_of_date = None
if portfolio_id:
    holdings_sdf = (
        spark.table(f"{catalog}.{schema}.portfolio_holdings")
        .where(F.col("portfolio_id") == portfolio_id)
        .where(F.col("weight").isNotNull())
    )
    latest = holdings_sdf.agg(F.max("as_of_date").alias("as_of_date")).first()["as_of_date"]
    if latest is None:
        raise ValueError(f"No weighted holdings found for portfolio_id={portfolio_id!r}")
    holdings_pdf = (holdings_sdf.where(F.col("as_of_date") == latest)
                    .select("symbol", "weight").toPandas())
    if holdings_pdf.empty:
        raise ValueError(f"No holdings found for portfolio_id={portfolio_id!r} at {latest}")
    symbols = [str(x).upper() for x in holdings_pdf["symbol"].tolist()]
    portfolio_as_of_date = str(latest)
    if strategy_name in {"fixed_allocation", "buy_and_hold"} and "weights" not in strategy_params:
        strategy_params["weights"] = {str(r.symbol).upper(): float(r.weight) for r in holdings_pdf.itertuples()}


def fq(table):
    return f"`{catalog}`.`{schema}`.`{table}`"

# COMMAND ----------
all_symbols = sorted(set(symbols + ([benchmark_symbol] if benchmark_symbol else [])))
prices_sdf = (
    spark.table(f"{catalog}.{schema}.prices_daily")
    .where(F.col("symbol").isin(all_symbols))
    .where(F.col("date") >= F.lit(start_date))
)
if end_date:
    prices_sdf = prices_sdf.where(F.col("date") <= F.lit(end_date))
prices_pdf = prices_sdf.select("date", "symbol", F.coalesce("adjusted_close", "close").alias("price")).toPandas()
if prices_pdf.empty:
    raise ValueError("No price data found. Run the ODP ingestion section of the setup notebook first.")

pivot = prices_pdf.pivot_table(index="date", columns="symbol", values="price", aggfunc="last").sort_index()
pivot.index = pd.to_datetime(pivot.index)
missing = [s for s in symbols if s not in pivot.columns]
if missing:
    raise ValueError(f"Missing requested symbols in prices_daily: {missing}")
universe_prices = pivot[symbols].ffill()
benchmark_prices = pivot[benchmark_symbol].ffill() if benchmark_symbol and benchmark_symbol in pivot.columns else None

# COMMAND ----------
# Strategy selection. Built-ins come from the registry. Two adapters turn point-in-time
# factor/model scores into target weights; custom strategies can be added to src/quant_platform.
strategy_callable = strategy_name

if strategy_name == "factor_top_n":
    factor_name = strategy_params["factor_name"]
    top_n = int(strategy_params.get("top_n", 20))
    bottom_n = int(strategy_params.get("bottom_n", 0))
    long_short = bool(strategy_params.get("long_short", False))
    score_sdf = (
        spark.table(f"{catalog}.{schema}.factor_snapshots")
        .where(F.col("symbol").isin(symbols))
        .where(F.col("factor_name") == factor_name)
        .select("symbol", "available_at", "factor_value")
    )
    score_pdf = score_sdf.toPandas()
    score_pdf["available_at"] = pd.to_datetime(score_pdf["available_at"])
    score_frame = pd.DataFrame(index=universe_prices.index, columns=symbols, dtype=float)
    for symbol in symbols:
        hist = score_pdf[score_pdf.symbol == symbol].sort_values("available_at")[["available_at", "factor_value"]]
        if hist.empty:
            continue
        dates = pd.DataFrame({"date": universe_prices.index}).sort_values("date")
        aligned = pd.merge_asof(dates, hist, left_on="date", right_on="available_at", direction="backward")
        score_frame[symbol] = aligned["factor_value"].to_numpy()
    strategy_callable = lambda p, params: factor_or_model_strategy(
        p, score_frame, top_n=top_n, bottom_n=bottom_n, long_short=long_short
    )

elif strategy_name == "model_top_n":
    model_name = strategy_params["model_name"]
    horizon = strategy_params.get("horizon")
    top_n = int(strategy_params.get("top_n", 20))
    bottom_n = int(strategy_params.get("bottom_n", 0))
    long_short = bool(strategy_params.get("long_short", False))
    pred_sdf = spark.table(f"{catalog}.{schema}.model_predictions").where(
        (F.col("symbol").isin(symbols)) & (F.col("model_name") == model_name)
    )
    if horizon:
        pred_sdf = pred_sdf.where(F.col("horizon") == horizon)
    pred_pdf = pred_sdf.select("symbol", "prediction_timestamp", "prediction").toPandas()
    pred_pdf["prediction_timestamp"] = pd.to_datetime(pred_pdf["prediction_timestamp"])
    score_frame = pd.DataFrame(index=universe_prices.index, columns=symbols, dtype=float)
    for symbol in symbols:
        hist = pred_pdf[pred_pdf.symbol == symbol].sort_values("prediction_timestamp")[["prediction_timestamp", "prediction"]]
        if hist.empty:
            continue
        dates = pd.DataFrame({"date": universe_prices.index}).sort_values("date")
        aligned = pd.merge_asof(dates, hist, left_on="date", right_on="prediction_timestamp", direction="backward")
        score_frame[symbol] = aligned["prediction"].to_numpy()
    strategy_callable = lambda p, params: factor_or_model_strategy(
        p, score_frame, top_n=top_n, bottom_n=bottom_n, long_short=long_short
    )

elif strategy_name not in REGISTRY.names():
    raise ValueError(f"Unknown strategy {strategy_name!r}. Built-ins: {REGISTRY.names()}, plus factor_top_n and model_top_n")

# COMMAND ----------
result = run_backtest(
    universe_prices,
    strategy_callable,
    params=strategy_params,
    rebalance=rebalance,
    initial_capital=initial_capital,
    fee_bps=fee_bps,
    slippage_bps=slippage_bps,
    risk_free_rate=risk_free_rate,
    benchmark_prices=benchmark_prices,
    long_only=long_only,
    gross_leverage_limit=gross_leverage_limit,
    metadata={"symbols": symbols, "benchmark": benchmark_symbol, "portfolio_id": portfolio_id, "portfolio_as_of_date": portfolio_as_of_date, "worker": "backtest_worker"},
)
result.run_id, result.metrics

# COMMAND ----------
now = datetime.now(timezone.utc).replace(tzinfo=None)
run_row = pd.DataFrame([{
    "run_id": result.run_id,
    "strategy_id": "",
    "strategy_name": strategy_name,
    "benchmark_symbol": benchmark_symbol,
    "start_date": universe_prices.index.min().date(),
    "end_date": universe_prices.index.max().date(),
    "initial_capital": float(result.metrics["initial_capital"]),
    "rebalance_frequency": rebalance,
    "fee_bps": fee_bps,
    "slippage_bps": slippage_bps,
    "parameters_json": json.dumps(strategy_params),
    "status": "COMPLETED",
    "source_engine": "quant_platform.weight_engine",
    "created_at": now,
    "completed_at": now,
    "metadata_json": json.dumps(result.metadata, default=str),
}])
spark.createDataFrame(run_row).write.mode("append").saveAsTable(f"{catalog}.{schema}.strategy_runs")

# Daily results
daily = result.daily.reset_index().rename(columns={result.daily.index.name or "index": "date"})
daily["date"] = pd.to_datetime(daily["date"]).dt.date
daily.insert(0, "run_id", result.run_id)
for col in ["benchmark_return", "benchmark_wealth"]:
    if col not in daily:
        daily[col] = np.nan
cols = ["run_id", "date", "gross_return", "trading_cost_return", "net_return", "wealth", "drawdown", "turnover", "benchmark_return", "benchmark_wealth"]
spark.createDataFrame(daily[cols]).write.mode("append").saveAsTable(f"{catalog}.{schema}.strategy_daily")

# Holdings
records = []
for dt in result.target_weights.index:
    for sym in result.target_weights.columns:
        tw = result.target_weights.at[dt, sym]
        ew = result.effective_weights.at[dt, sym]
        if abs(tw) > 1e-12 or abs(ew) > 1e-12:
            records.append({"run_id": result.run_id, "date": dt.date(), "symbol": sym, "target_weight": float(tw), "effective_weight": float(ew)})
if records:
    spark.createDataFrame(pd.DataFrame(records)).write.mode("append").saveAsTable(f"{catalog}.{schema}.strategy_holdings")

metrics = pd.DataFrame([
    {"run_id": result.run_id, "metric_name": k, "metric_value": float(v) if np.isfinite(v) else None, "metric_text": None}
    for k, v in result.metrics.items()
])
spark.createDataFrame(metrics).write.mode("append").saveAsTable(f"{catalog}.{schema}.strategy_metrics")

print(json.dumps({"run_id": result.run_id, "strategy": strategy_name, "metrics": result.metrics}, indent=2, default=str))
