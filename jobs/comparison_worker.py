# Databricks notebook source
# MAGIC %md
# MAGIC # Quant Platform — Portfolio/Strategy Comparison Worker
# MAGIC Creates a persisted, common-period comparison across existing strategy runs.

# COMMAND ----------
import json, os, sys, uuid
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from pyspark.sql import functions as F

try:
    _here = Path(__file__).resolve()
    sys.path.insert(0, str(_here.parents[1] / "src"))
except Exception:
    pass

from quant_platform.metrics import performance_metrics

# COMMAND ----------
PARAMS = {
    "catalog": "main",
    "schema": "openbb_quant",
    "run_ids": "",
    "member_names": "",
    "comparison_name": "Strategy Comparison",
}
for k, default in PARAMS.items():
    try:
        dbutils.widgets.text(k, default)
        PARAMS[k] = dbutils.widgets.get(k)
    except Exception:
        PARAMS[k] = os.getenv(k.upper(), default)

catalog = PARAMS["catalog"]
schema = PARAMS["schema"]
run_ids = [x.strip() for x in PARAMS["run_ids"].split(",") if x.strip()]
member_names = [x.strip() for x in PARAMS["member_names"].split(",") if x.strip()]
comparison_name = PARAMS["comparison_name"] or "Strategy Comparison"

if len(run_ids) < 2:
    raise ValueError("At least two strategy run IDs are required")
if member_names and len(member_names) != len(run_ids):
    raise ValueError("member_names must be empty or match run_ids length")

# COMMAND ----------
run_meta = (
    spark.table(f"{catalog}.{schema}.strategy_runs")
    .where(F.col("run_id").isin(run_ids))
    .select("run_id", "strategy_name", "benchmark_symbol")
    .toPandas()
)
found = set(run_meta["run_id"].tolist()) if not run_meta.empty else set()
missing = [rid for rid in run_ids if rid not in found]
if missing:
    raise ValueError(f"Unknown strategy run IDs: {missing}")

if not member_names:
    counts = {}
    member_names = []
    meta_map = run_meta.set_index("run_id")["strategy_name"].to_dict()
    for rid in run_ids:
        base = str(meta_map.get(rid) or "Strategy")
        counts[base] = counts.get(base, 0) + 1
        label = base if counts[base] == 1 else f"{base} ({rid[:8]})"
        member_names.append(label)

name_by_run = dict(zip(run_ids, member_names))

# COMMAND ----------
daily_pdf = (
    spark.table(f"{catalog}.{schema}.strategy_daily")
    .where(F.col("run_id").isin(run_ids))
    .select("run_id", "date", "net_return")
    .toPandas()
)
if daily_pdf.empty:
    raise ValueError("No strategy_daily rows found for requested runs")

daily_pdf["date"] = pd.to_datetime(daily_pdf["date"])
returns = (
    daily_pdf.pivot_table(index="date", columns="run_id", values="net_return", aggfunc="last")
    .reindex(columns=run_ids)
    .sort_index()
    .dropna(how="any")
)
if len(returns) < 3:
    raise ValueError("Requested runs do not have a sufficient common comparison period")

wealth = 100_000.0 * (1.0 + returns).cumprod()
drawdowns = wealth.div(wealth.cummax()).sub(1.0)
comparison_id = str(uuid.uuid4())
now = datetime.now(timezone.utc).replace(tzinfo=None)

benchmarks = [x for x in run_meta["benchmark_symbol"].dropna().unique().tolist() if x]
benchmark_symbol = benchmarks[0] if len(benchmarks) == 1 else None

# COMMAND ----------
comparison_run = pd.DataFrame([{
    "comparison_id": comparison_id,
    "comparison_name": comparison_name,
    "benchmark_symbol": benchmark_symbol,
    "start_date": returns.index.min().date(),
    "end_date": returns.index.max().date(),
    "created_at": now,
    "metadata_json": json.dumps({"source": "strategy_runs", "run_ids": run_ids}),
}])
spark.createDataFrame(comparison_run).write.mode("append").saveAsTable(
    f"{catalog}.{schema}.portfolio_comparison_runs"
)

members = pd.DataFrame([
    {
        "comparison_id": comparison_id,
        "member_name": name_by_run[rid],
        "member_type": "strategy_run",
        "member_id": rid,
        "display_order": i,
    }
    for i, rid in enumerate(run_ids)
])
spark.createDataFrame(members).write.mode("append").saveAsTable(
    f"{catalog}.{schema}.portfolio_comparison_members"
)

metric_rows = []
daily_rows = []
for rid in run_ids:
    name = name_by_run[rid]
    r = returns[rid]
    w = wealth[rid]
    dd = drawdowns[rid]
    metrics = performance_metrics(r, wealth=w)
    metrics["ending_value"] = float(w.iloc[-1])
    for key, value in metrics.items():
        metric_rows.append({
            "comparison_id": comparison_id,
            "member_name": name,
            "metric_name": key,
            "metric_value": float(value) if value is not None and np.isfinite(value) else None,
            "metric_text": None,
        })
    for dt in returns.index:
        daily_rows.append({
            "comparison_id": comparison_id,
            "date": dt.date(),
            "member_name": name,
            "wealth": float(w.loc[dt]),
            "daily_return": float(r.loc[dt]),
            "drawdown": float(dd.loc[dt]),
        })

spark.createDataFrame(pd.DataFrame(metric_rows)).write.mode("append").saveAsTable(
    f"{catalog}.{schema}.portfolio_comparison_metrics"
)
spark.createDataFrame(pd.DataFrame(daily_rows)).write.mode("append").saveAsTable(
    f"{catalog}.{schema}.portfolio_comparison_daily"
)

print(json.dumps({
    "comparison_id": comparison_id,
    "comparison_name": comparison_name,
    "members": name_by_run,
    "start_date": str(returns.index.min().date()),
    "end_date": str(returns.index.max().date()),
}, indent=2))
