# Databricks notebook source
# MAGIC %md
# MAGIC # 01 — Ingest Market Data with OpenBB ODP
# MAGIC **Prerequisite:** 00_SETUP. The canonical DBO_Quant catalog/schema is discovered automatically from setup. This notebook loads historical prices through permanent OpenBB ODP and writes them to Delta.

# COMMAND ----------
from pathlib import Path
from datetime import date, datetime, timezone
from openbb import obb
from delta.tables import DeltaTable
import pandas as pd, numpy as np
import sys
repo_root=Path.cwd()
for candidate in [repo_root,*repo_root.parents]:
    if (candidate/'src'/'quant_platform').exists(): repo_root=candidate; break
sys.path.insert(0,str(repo_root/'src'))
from quant_platform.location import discover_with_spark

# COMMAND ----------
location=discover_with_spark(spark)
CATALOG,SCHEMA=location.catalog,location.schema
print('DBO_Quant namespace:',location.namespace)
dbutils.widgets.text("provider","yfinance")
dbutils.widgets.text("symbols","SPY,QQQ,IEF,GLD")
dbutils.widgets.text("start_date","2010-01-01")
dbutils.widgets.text("end_date",str(date.today()))
PROVIDER=dbutils.widgets.get("provider").strip()
SYMBOLS=[x.strip().upper() for x in dbutils.widgets.get("symbols").split(",") if x.strip()]
START_DATE=dbutils.widgets.get("start_date"); END_DATE=dbutils.widgets.get("end_date")
try: spark.table(f"{CATALOG}.{SCHEMA}.prices_daily").limit(1).collect()
except Exception: raise RuntimeError("Setup is missing. Run notebooks/00_SETUP.py first.")

# COMMAND ----------
def first_col(df,names):
    m={str(c).lower():c for c in df.columns}
    return next((m[n.lower()] for n in names if n.lower() in m),None)

def fetch_symbol(symbol):
    raw=obb.equity.price.historical(symbol=symbol,start_date=START_DATE,end_date=END_DATE,provider=PROVIDER).to_df().reset_index()
    d=first_col(raw,["date","datetime","index"])
    if d is None: raise ValueError(f"No date column for {symbol}")
    out=pd.DataFrame({"date":pd.to_datetime(raw[d]).dt.date})
    for dest,names in {"open":["open"],"high":["high"],"low":["low"],"close":["close"],"adjusted_close":["adjusted_close","adj_close"],"volume":["volume"]}.items():
        src=first_col(raw,names); out[dest]=pd.to_numeric(raw[src],errors="coerce").astype(float) if src else np.nan
    out["symbol"]=symbol; out["provider"]=PROVIDER; out["currency"]=""; out["exchange"]=""; out["ingested_at"]=datetime.now(timezone.utc).replace(tzinfo=None)
    return out[["symbol","date","open","high","low","close","adjusted_close","volume","provider","currency","exchange","ingested_at"]]

target=DeltaTable.forName(spark,f"{CATALOG}.{SCHEMA}.prices_daily")
for symbol in SYMBOLS:
    pdf=fetch_symbol(symbol)
    sdf=spark.createDataFrame(pdf)
    (target.alias("t").merge(sdf.alias("s"),"t.symbol=s.symbol AND t.date=s.date AND t.provider=s.provider").whenMatchedUpdateAll().whenNotMatchedInsertAll().execute())
    print(f"{symbol}: {len(pdf):,} rows fetched")

# COMMAND ----------
summary=(spark.table(f"{CATALOG}.{SCHEMA}.prices_daily").where(f"provider='{PROVIDER}'").groupBy("symbol").agg({"date":"min"}).withColumnRenamed("min(date)","first_date"))
display(summary)
print("\nDATA INGESTION COMPLETE")
print("NEXT → choose a strategy notebook under notebooks/backtests/")
