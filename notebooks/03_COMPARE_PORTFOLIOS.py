# Databricks notebook source
# MAGIC %md
# MAGIC # 03 — Compare Backtests / Portfolios
# MAGIC **Prerequisite:** at least two completed runs from 02_BACKTEST. Enter their run IDs as a comma-separated list.

# COMMAND ----------
from datetime import datetime, timezone
import json, uuid
import pandas as pd, numpy as np
current_catalog=spark.sql("SELECT current_catalog() c").first()["c"]
for n,d in [("catalog",current_catalog),("schema","openbb_quant"),("run_ids",""),("comparison_name","Research comparison")]: dbutils.widgets.text(n,d)
CATALOG=dbutils.widgets.get("catalog"); SCHEMA=dbutils.widgets.get("schema"); RUN_IDS=[x.strip() for x in dbutils.widgets.get("run_ids").split(",") if x.strip()]
if len(RUN_IDS)<2: raise ValueError("Provide at least two strategy run IDs from 02_BACKTEST.py")

# COMMAND ----------
runs=spark.table(f"{CATALOG}.{SCHEMA}.strategy_runs").where("run_id IN ({})".format(",".join([f"'{x}'" for x in RUN_IDS]))).toPandas()
if len(runs)<2: raise RuntimeError("Could not find at least two requested run IDs")
daily=spark.table(f"{CATALOG}.{SCHEMA}.strategy_daily").where("run_id IN ({})".format(",".join([f"'{x}'" for x in RUN_IDS]))).toPandas()
metrics=spark.table(f"{CATALOG}.{SCHEMA}.strategy_metrics").where("run_id IN ({})".format(",".join([f"'{x}'" for x in RUN_IDS]))).toPandas()
labels=dict(zip(runs.run_id,runs.strategy_name))
metric_view=metrics.pivot_table(index="metric_name",columns="run_id",values="metric_value",aggfunc="last").rename(columns=labels)
display(metric_view.reset_index())
curve=daily.pivot_table(index="date",columns="run_id",values="wealth",aggfunc="last").rename(columns=labels)
display(curve.tail(30).reset_index())

# COMMAND ----------
comparison_id=str(uuid.uuid4()); now=datetime.now(timezone.utc).replace(tzinfo=None); name=dbutils.widgets.get("comparison_name")
start=pd.to_datetime(daily.date).min().date(); end=pd.to_datetime(daily.date).max().date(); benchmark=str(runs.benchmark_symbol.dropna().iloc[0]) if runs.benchmark_symbol.notna().any() else ""
spark.createDataFrame(pd.DataFrame([{"comparison_id":comparison_id,"comparison_name":name,"benchmark_symbol":benchmark,"start_date":start,"end_date":end,"created_at":now,"metadata_json":json.dumps({"run_ids":RUN_IDS})}])).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.portfolio_comparison_runs")
members=[]; metric_rows=[]; daily_rows=[]
for i,rid in enumerate(RUN_IDS):
    label=labels.get(rid,rid); members.append({"comparison_id":comparison_id,"member_name":label,"member_type":"strategy_run","member_id":rid,"display_order":i})
    for _,r in metrics[metrics.run_id==rid].iterrows(): metric_rows.append({"comparison_id":comparison_id,"member_name":label,"metric_name":r.metric_name,"metric_value":None if pd.isna(r.metric_value) else float(r.metric_value),"metric_text":""})
    for _,r in daily[daily.run_id==rid].iterrows(): daily_rows.append({"comparison_id":comparison_id,"date":pd.to_datetime(r.date).date(),"member_name":label,"wealth":float(r.wealth),"daily_return":float(r.net_return),"drawdown":float(r.drawdown)})
spark.createDataFrame(pd.DataFrame(members)).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.portfolio_comparison_members")
spark.createDataFrame(pd.DataFrame(metric_rows)).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.portfolio_comparison_metrics")
spark.createDataFrame(pd.DataFrame(daily_rows)).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.portfolio_comparison_daily")
print("COMPARISON SAVED:",comparison_id)
print("NEXT → run 04_MONTE_CARLO.py, or skip to 05_SERVING.py if research outputs are sufficient")