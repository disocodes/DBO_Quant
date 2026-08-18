# Databricks notebook source
# MAGIC %md
# MAGIC # Portfolio — Save or Update Holdings
# MAGIC Create or update a real portfolio using a persistent `portfolio_id`. The saved portfolio can be used by Monte Carlo, portfolio optimization/rebalancing, and OpenBB.

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Load the Project and Configure Portfolio Inputs
# MAGIC Discover the canonical DBO_Quant namespace and configure the portfolio identifier, name, base currency, allocation weights, and effective date.

# COMMAND ----------
from pathlib import Path
from datetime import date, datetime, timezone
import sys, json, uuid
import numpy as np
import pandas as pd

repo_root=Path.cwd()
for c in [repo_root,*repo_root.parents]:
    if (c/'src'/'quant_platform').exists(): repo_root=c; break
sys.path.insert(0,str(repo_root/'src'))
from quant_platform.location import discover_with_spark

location=discover_with_spark(spark)
CATALOG,SCHEMA=location.catalog,location.schema
print('DBO_Quant namespace:',location.namespace)

for n,d in [('portfolio_id',''),('portfolio_name','My Portfolio'),('base_currency','USD'),('weights_json','{"SPY":0.4,"QQQ":0.2,"IEF":0.25,"GLD":0.15}'),('as_of_date',str(date.today()))]: dbutils.widgets.text(n,d)
PORTFOLIO_ID=dbutils.widgets.get('portfolio_id').strip() or str(uuid.uuid4())
NAME=dbutils.widgets.get('portfolio_name').strip(); BASE=dbutils.widgets.get('base_currency').strip().upper(); AS_OF=pd.Timestamp(dbutils.widgets.get('as_of_date')).date(); WEIGHTS=pd.Series(json.loads(dbutils.widgets.get('weights_json')),dtype=float)
if not NAME: raise ValueError('portfolio_name is required')
if WEIGHTS.empty or WEIGHTS.isna().any(): raise ValueError('weights_json must contain valid numeric weights')
if abs(float(WEIGHTS.sum())-1.0)>1e-6: raise ValueError(f'Portfolio weights must sum to 1.0; received {WEIGHTS.sum():.6f}')

# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Persist the Portfolio Definition and Holdings Snapshot
# MAGIC Create the portfolio definition when it is new, replace any holdings snapshot for the same date, and append the validated allocation to Unity Catalog.

# COMMAND ----------
existing=spark.table(f'{CATALOG}.{SCHEMA}.portfolio_definitions').where(f"portfolio_id = '{PORTFOLIO_ID}'").count()
if existing==0:
    now=datetime.now(timezone.utc).replace(tzinfo=None)
    spark.createDataFrame(pd.DataFrame([{'portfolio_id':PORTFOLIO_ID,'portfolio_name':NAME,'description':'','base_currency':BASE,'created_at':now,'metadata_json':'{}'}])).write.mode('append').saveAsTable(f'{CATALOG}.{SCHEMA}.portfolio_definitions')

spark.sql(f"DELETE FROM `{CATALOG}`.`{SCHEMA}`.`portfolio_holdings` WHERE portfolio_id = '{PORTFOLIO_ID}' AND as_of_date = DATE('{AS_OF}')")
now=datetime.now(timezone.utc).replace(tzinfo=None)
rows=[{'portfolio_id':PORTFOLIO_ID,'as_of_date':AS_OF,'symbol':str(symbol).upper(),'weight':float(weight),'quantity':np.nan,'market_value':np.nan,'source':'manual_notebook','ingested_at':now} for symbol,weight in WEIGHTS.items()]
spark.createDataFrame(pd.DataFrame(rows)).write.mode('append').saveAsTable(f'{CATALOG}.{SCHEMA}.portfolio_holdings')

# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Verify the Saved Portfolio
# MAGIC Display the stored holdings and print the `portfolio_id` required by Monte Carlo and portfolio-optimization notebooks.

# COMMAND ----------
print('PORTFOLIO SAVED')
print('portfolio_id =',PORTFOLIO_ID)
display(spark.table(f'{CATALOG}.{SCHEMA}.portfolio_holdings').where(f"portfolio_id = '{PORTFOLIO_ID}'").orderBy('as_of_date','symbol'))
print('NEXT → 02_MONTE_CARLO.py for baseline risk, or 04_PORTFOLIO_OPTIMIZATION_DATABRICKS.py for optional optimization.')
