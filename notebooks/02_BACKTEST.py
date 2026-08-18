# Databricks notebook source
# MAGIC %md
# MAGIC # 02 — Backtest a Strategy
# MAGIC **Prerequisites:** 00_SETUP and 01_INGEST_DATA. Choose a strategy and parameters below. Every run creates a new `run_id`. Continue to **03_COMPARE_PORTFOLIOS** or **04_MONTE_CARLO**.

# COMMAND ----------
from pathlib import Path
from datetime import datetime, timezone
import sys, json, uuid
import pandas as pd, numpy as np
from pyspark.sql import functions as F
repo_root=Path.cwd()
for c in [repo_root,*repo_root.parents]:
    if (c/"src"/"quant_platform").exists(): repo_root=c; break
sys.path.insert(0,str(repo_root/"src"))
from quant_platform import REGISTRY, run_backtest

# COMMAND ----------
current_catalog=spark.sql("SELECT current_catalog() c").first()["c"]
for name,default in [("catalog",current_catalog),("schema","openbb_quant"),("symbols","SPY,QQQ,IEF,GLD"),("benchmark","SPY"),("strategy","inverse_volatility"),("parameters_json",'{"lookback":63}'),("rebalance","monthly"),("initial_capital","100000"),("fee_bps","5"),("slippage_bps","2")]:
    dbutils.widgets.text(name,default)
CATALOG=dbutils.widgets.get("catalog"); SCHEMA=dbutils.widgets.get("schema"); SYMBOLS=[x.strip().upper() for x in dbutils.widgets.get("symbols").split(",") if x.strip()]; BENCHMARK=dbutils.widgets.get("benchmark").upper(); STRATEGY=dbutils.widgets.get("strategy"); PARAMS=json.loads(dbutils.widgets.get("parameters_json") or "{}")
if STRATEGY not in REGISTRY.names(): raise ValueError(f"Unknown strategy {STRATEGY}. Available: {REGISTRY.names()}")

# COMMAND ----------
prices=(spark.table(f"{CATALOG}.{SCHEMA}.prices_daily").where(F.col("symbol").isin(sorted(set(SYMBOLS+[BENCHMARK])))).select("date","symbol",F.coalesce("adjusted_close","close").alias("price")).toPandas())
if prices.empty: raise RuntimeError("No prices found. Run notebooks/01_INGEST_DATA.py first.")
wide=prices.pivot_table(index="date",columns="symbol",values="price",aggfunc="last").sort_index(); wide.index=pd.to_datetime(wide.index)
research=wide.reindex(columns=SYMBOLS).ffill().dropna(how="all"); benchmark=wide[BENCHMARK].reindex(research.index).ffill() if BENCHMARK in wide.columns else None
result=run_backtest(research,STRATEGY,params=PARAMS,rebalance=dbutils.widgets.get("rebalance"),initial_capital=float(dbutils.widgets.get("initial_capital")),fee_bps=float(dbutils.widgets.get("fee_bps")),slippage_bps=float(dbutils.widgets.get("slippage_bps")),benchmark_prices=benchmark,metadata={"symbols":SYMBOLS,"benchmark":BENCHMARK})
print("run_id =",result.run_id); display(pd.DataFrame([result.metrics]).T.reset_index().rename(columns={"index":"metric",0:"value"})); display(result.daily.tail(20).reset_index())

# COMMAND ----------
now=datetime.now(timezone.utc).replace(tzinfo=None)
run_row={"run_id":result.run_id,"strategy_id":"","strategy_name":STRATEGY,"benchmark_symbol":BENCHMARK,"start_date":research.index.min().date(),"end_date":research.index.max().date(),"initial_capital":float(result.metrics["initial_capital"]),"rebalance_frequency":dbutils.widgets.get("rebalance"),"fee_bps":float(dbutils.widgets.get("fee_bps")),"slippage_bps":float(dbutils.widgets.get("slippage_bps")),"parameters_json":json.dumps(PARAMS),"status":"COMPLETED","source_engine":"quant_platform.weight_engine","created_at":now,"completed_at":now,"metadata_json":json.dumps(result.metadata,default=str)}
spark.createDataFrame(pd.DataFrame([run_row])).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.strategy_runs")
daily=result.daily.reset_index(); daily.columns=["date" if c==result.daily.index.name or c=="index" else c for c in daily.columns]; daily["date"]=pd.to_datetime(daily["date"]).dt.date; daily.insert(0,"run_id",result.run_id)
for c in ["benchmark_return","benchmark_wealth"]:
    if c not in daily: daily[c]=np.nan
spark.createDataFrame(daily[["run_id","date","gross_return","trading_cost_return","net_return","wealth","drawdown","turnover","benchmark_return","benchmark_wealth"]]).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.strategy_daily")
metrics=[]
for k,v in result.metrics.items():
    try: fv=float(v); fv=fv if np.isfinite(fv) else None
    except Exception: fv=None
    metrics.append({"run_id":result.run_id,"metric_name":k,"metric_value":fv,"metric_text":""})
spark.createDataFrame(pd.DataFrame(metrics)).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.strategy_metrics")
print("\nBACKTEST SAVED:",result.run_id)
print("NEXT → 03_COMPARE_PORTFOLIOS.py to compare runs, or 04_MONTE_CARLO.py to simulate a portfolio")