# Databricks notebook source
# MAGIC %md
# MAGIC # 01 — Ingest Market Data with OpenBB ODP
# MAGIC Load historical market data through OpenBB, normalize it into the DBO_Quant price schema, and upsert it into Unity Catalog.
# MAGIC
# MAGIC **Prerequisite:** `00_SETUP.py`. The canonical DBO_Quant catalog/schema is discovered automatically from setup.

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Install OpenBB Ingestion Packages
# MAGIC Install the pinned OpenBB core and YFinance provider required by this notebook on fresh Databricks serverless sessions.

# COMMAND ----------
# MAGIC %pip install -q "openbb==4.7.2" "openbb-yfinance==1.6.3"

# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Restart Python
# MAGIC Restart the Python process so the newly installed OpenBB packages are available before imports run.

# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Load OpenBB and DBO_Quant Helpers
# MAGIC Import OpenBB, Delta Lake utilities, data-processing libraries, and canonical DBO_Quant namespace discovery.

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
# MAGIC %md
# MAGIC ## 4. Configure the Data Request
# MAGIC Discover the canonical Unity Catalog namespace and configure the OpenBB provider, symbols, and historical date range to ingest.

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
# MAGIC %md
# MAGIC ## 5. Fetch, Normalize, and Upsert Prices
# MAGIC Retrieve each symbol through OpenBB ODP, normalize provider-specific fields to the DBO_Quant schema, and merge the rows into `prices_daily` without duplicating existing dates.

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
# MAGIC %md
# MAGIC ## 6. Verify Ingested Coverage
# MAGIC Summarize the stored date coverage by symbol and confirm the ingestion step is complete before strategy research begins.

# COMMAND ----------
summary=(spark.table(f"{CATALOG}.{SCHEMA}.prices_daily").where(f"provider='{PROVIDER}'").groupBy("symbol").agg({"date":"min"}).withColumnRenamed("min(date)","first_date"))
display(summary)
print("\nDATA INGESTION COMPLETE")
print("NEXT → choose a strategy notebook under notebooks/backtests/")