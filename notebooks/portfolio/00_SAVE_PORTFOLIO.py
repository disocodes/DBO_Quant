# Databricks notebook source
# MAGIC %md
# MAGIC # Portfolio — Save or Update Holdings
# MAGIC Use this notebook when you want DBO_Quant to track a portfolio by `portfolio_id`. The saved portfolio can then be used by Monte Carlo, NVIDIA GPU optimization/rebalancing, and OpenBB views.

# COMMAND ----------
from datetime import date, datetime, timezone
import json, uuid
import numpy as np
import pandas as pd
current_catalog=spark.sql('SELECT current_catalog() c').first()['c']
for n,d in [('catalog',current_catalog),('schema','openbb_quant'),('portfolio_id',''),('portfolio_name','My Portfolio'),('base_currency','USD'),('weights_json','{"SPY":0.4,"QQQ":0.2,"IEF":0.25,"GLD":0.15}'),('as_of_date',str(date.today()))]: dbutils.widgets.text(n,d)
CATALOG=dbutils.widgets.get('catalog').strip(); SCHEMA=dbutils.widgets.get('schema').strip(); PORTFOLIO_ID=dbutils.widgets.get('portfolio_id').strip() or str(uuid.uuid4()); NAME=dbutils.widgets.get('portfolio_name').strip(); BASE=dbutils.widgets.get('base_currency').strip().upper(); AS_OF=pd.Timestamp(dbutils.widgets.get('as_of_date')).date(); WEIGHTS=pd.Series(json.loads(dbutils.widgets.get('weights_json')),dtype=float)
if not NAME: raise ValueError('portfolio_name is required')
if WEIGHTS.empty or WEIGHTS.isna().any(): raise ValueError('weights_json must contain valid numeric weights')
if abs(float(WEIGHTS.sum())-1.0)>1e-6: raise ValueError(f'Portfolio weights must sum to 1.0; received {WEIGHTS.sum():.6f}')

# COMMAND ----------
existing=spark.table(f'{CATALOG}.{SCHEMA}.portfolio_definitions').where(f"portfolio_id = '{PORTFOLIO_ID}'").count()
if existing==0:
    now=datetime.now(timezone.utc).replace(tzinfo=None)
    spark.createDataFrame(pd.DataFrame([{'portfolio_id':PORTFOLIO_ID,'portfolio_name':NAME,'description':'','base_currency':BASE,'created_at':now,'metadata_json':'{}'}])).write.mode('append').saveAsTable(f'{CATALOG}.{SCHEMA}.portfolio_definitions')

# Replace this portfolio's holdings snapshot for the selected as-of date.
spark.sql(f"DELETE FROM `{CATALOG}`.`{SCHEMA}`.`portfolio_holdings` WHERE portfolio_id = '{PORTFOLIO_ID}' AND as_of_date = DATE('{AS_OF}')")
now=datetime.now(timezone.utc).replace(tzinfo=None)
rows=[{'portfolio_id':PORTFOLIO_ID,'as_of_date':AS_OF,'symbol':str(symbol).upper(),'weight':float(weight),'quantity':np.nan,'market_value':np.nan,'source':'manual_notebook','ingested_at':now} for symbol,weight in WEIGHTS.items()]
spark.createDataFrame(pd.DataFrame(rows)).write.mode('append').saveAsTable(f'{CATALOG}.{SCHEMA}.portfolio_holdings')

# COMMAND ----------
print('PORTFOLIO SAVED')
print('portfolio_id =',PORTFOLIO_ID)
display(spark.table(f'{CATALOG}.{SCHEMA}.portfolio_holdings').where(f"portfolio_id = '{PORTFOLIO_ID}'").orderBy('as_of_date','symbol'))
print('\nNEXT → notebooks/portfolio/02_MONTE_CARLO.py for simulation, or the optional NVIDIA GPU notebook for optimization/rebalancing.')