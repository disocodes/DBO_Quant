# Databricks notebook source
# MAGIC %md
# MAGIC # Portfolio Analysis — Monte Carlo
# MAGIC Forward-risk analysis for an existing allocation. Monte Carlo does **not** optimize weights; it tests the range of outcomes for weights produced by a saved portfolio, a strategy backtest, a portfolio-optimization run, or an ad-hoc allocation.
# MAGIC
# MAGIC **Prerequisite:** run `00_SETUP.py` and `01_INGEST_DATA.py`.

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Load the Monte Carlo Engine and Discover the Project
# MAGIC Import the shared simulation engine, find the repository root, and resolve the canonical DBO_Quant Unity Catalog namespace.

# COMMAND ----------
from pathlib import Path
from datetime import datetime, timezone
import sys, json
import pandas as pd
from pyspark.sql import functions as F

repo_root=Path.cwd()
for c in [repo_root,*repo_root.parents]:
    if (c/'src'/'quant_platform').exists(): repo_root=c; break
sys.path.insert(0,str(repo_root/'src'))

from quant_platform import simulate_portfolio
from quant_platform.location import discover_with_spark

location=discover_with_spark(spark)
CATALOG,SCHEMA=location.catalog,location.schema
print('DBO_Quant namespace:',location.namespace)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Configure the Allocation Source and Simulation
# MAGIC Choose where portfolio weights come from and set the starting value, simulation horizon, number of paths, simulation method, and rebalancing interval.

# COMMAND ----------
# Choose one allocation source.
dbutils.widgets.dropdown('source_type','saved_portfolio',['saved_portfolio','strategy_run','optimization_run','adhoc'],'Allocation source')
dbutils.widgets.text('source_id','','portfolio_id, run_id, or optimization_run_id')
dbutils.widgets.text('symbols','SPY,QQQ,IEF,GLD','Ad-hoc symbols')
dbutils.widgets.text('weights_json','{"SPY":0.4,"QQQ":0.2,"IEF":0.25,"GLD":0.15}','Ad-hoc weights')
dbutils.widgets.text('initial_value','100000')
dbutils.widgets.text('horizon_days','1260')
dbutils.widgets.text('n_simulations','5000')
dbutils.widgets.dropdown('method','historical_bootstrap',['historical_bootstrap','multivariate_normal'])
dbutils.widgets.text('rebalance_every_days','21')

SOURCE_TYPE=dbutils.widgets.get('source_type')
SOURCE_ID=dbutils.widgets.get('source_id').strip()

# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Resolve and Validate Portfolio Weights
# MAGIC Load the requested saved portfolio, strategy allocation, optimized allocation, or ad-hoc weights, normalize them, and display the exact allocation that will be simulated.

# COMMAND ----------
def normalized(series: pd.Series) -> pd.Series:
    s=series.astype(float)
    s=s[abs(s)>1e-12]
    if s.empty or abs(float(s.sum()))<1e-12:
        raise ValueError('Allocation has no usable non-zero weights')
    return s/float(s.sum())

if SOURCE_TYPE=='saved_portfolio':
    if not SOURCE_ID: raise ValueError('Enter the saved portfolio_id in source_id')
    snapshots=spark.table(f'{CATALOG}.{SCHEMA}.portfolio_holdings').where(F.col('portfolio_id')==SOURCE_ID)
    latest=snapshots.agg(F.max('as_of_date').alias('d')).first()['d']
    if latest is None: raise ValueError(f'No holdings found for portfolio_id={SOURCE_ID}')
    pdf=snapshots.where(F.col('as_of_date')==latest).select('symbol','weight').toPandas()
    WEIGHTS=normalized(pdf.set_index('symbol')['weight'])
    source_description=f'saved portfolio {SOURCE_ID} as of {latest}'

elif SOURCE_TYPE=='strategy_run':
    if not SOURCE_ID: raise ValueError('Enter a strategy run_id in source_id')
    holdings=spark.table(f'{CATALOG}.{SCHEMA}.strategy_holdings').where(F.col('run_id')==SOURCE_ID)
    latest=holdings.agg(F.max('date').alias('d')).first()['d']
    if latest is None: raise ValueError(f'No holdings found for strategy run_id={SOURCE_ID}')
    pdf=holdings.where(F.col('date')==latest).select('symbol','effective_weight').toPandas()
    WEIGHTS=normalized(pdf.set_index('symbol')['effective_weight'])
    source_description=f'strategy run {SOURCE_ID} latest effective allocation ({latest})'

elif SOURCE_TYPE=='optimization_run':
    if not SOURCE_ID: raise ValueError('Enter an optimization_run_id in source_id')
    pdf=(spark.table(f'{CATALOG}.{SCHEMA}.optimal_allocations')
         .where((F.col('optimization_run_id')==SOURCE_ID)&(F.col('portfolio_label')=='selected_optimal'))
         .select('symbol','weight').toPandas())
    if pdf.empty: raise ValueError(f'No selected_optimal allocation found for optimization_run_id={SOURCE_ID}')
    WEIGHTS=normalized(pdf.set_index('symbol')['weight'])
    source_description=f'portfolio-optimization selected allocation {SOURCE_ID}'

else:
    symbols=[x.strip().upper() for x in dbutils.widgets.get('symbols').split(',') if x.strip()]
    weights=pd.Series(json.loads(dbutils.widgets.get('weights_json')),dtype=float).reindex(symbols)
    if weights.isna().any(): raise ValueError('weights_json must contain every ad-hoc symbol')
    WEIGHTS=normalized(weights)
    source_description='ad-hoc allocation'

SYMBOLS=list(WEIGHTS.index)
print('Testing:',source_description)
display(WEIGHTS.rename('weight').reset_index().rename(columns={'index':'symbol'}))

# COMMAND ----------
# MAGIC %md
# MAGIC ## 4. Build Returns and Run the Simulation
# MAGIC Load historical prices for the selected assets, calculate aligned daily returns, call the shared Monte Carlo engine, and preview the resulting summary and percentile paths.

# COMMAND ----------
prices=(spark.table(f'{CATALOG}.{SCHEMA}.prices_daily')
        .where(F.col('symbol').isin(SYMBOLS))
        .select('date','symbol',F.coalesce('adjusted_close','close').alias('price'))
        .toPandas())
if prices.empty: raise RuntimeError('No prices found. Run notebooks/01_INGEST_DATA.py first.')
wide=(prices.pivot_table(index='date',columns='symbol',values='price',aggfunc='last')
      .sort_index().reindex(columns=SYMBOLS).ffill().dropna(how='any'))
returns=wide.pct_change(fill_method=None).dropna(how='any')

mc=simulate_portfolio(
    returns,WEIGHTS,
    initial_value=float(dbutils.widgets.get('initial_value')),
    horizon_days=int(dbutils.widgets.get('horizon_days')),
    n_simulations=int(dbutils.widgets.get('n_simulations')),
    method=dbutils.widgets.get('method'),
    rebalance_every_days=int(dbutils.widgets.get('rebalance_every_days')))

print(mc.summary)
display(mc.percentiles.iloc[::max(1,len(mc.percentiles)//30)].reset_index())

# COMMAND ----------
# MAGIC %md
# MAGIC ## 5. Persist Monte Carlo Results for OpenBB
# MAGIC Save the run metadata, percentile curves, and sample paths to Unity Catalog, publish the `mc_run_id` as a task value when running in a Job, and print the OpenBB handoff.

# COMMAND ----------
now=datetime.now(timezone.utc).replace(tzinfo=None)
summary=mc.summary
portfolio_id=SOURCE_ID if SOURCE_TYPE=='saved_portfolio' else ''
parameters={
    'source_type':SOURCE_TYPE,
    'source_id':SOURCE_ID,
    'source_description':source_description,
    'symbols':SYMBOLS,
    'weights':WEIGHTS.to_dict(),
}

spark.createDataFrame(pd.DataFrame([{
    'mc_run_id':mc.run_id,'portfolio_id':portfolio_id,'method':dbutils.widgets.get('method'),
    'initial_value':float(summary['initial_value']),'horizon_days':int(summary['horizon_days']),
    'n_simulations':int(summary['n_simulations']),'rebalance_every_days':int(summary['rebalance_every_days']),
    'seed':42,'parameters_json':json.dumps(parameters),'status':'COMPLETED',
    'source_engine':'quant_platform.monte_carlo','created_at':now,'completed_at':now,
    'summary_json':json.dumps(summary)}])).write.mode('append').saveAsTable(f'{CATALOG}.{SCHEMA}.monte_carlo_runs')

pct=mc.percentiles.reset_index().rename(columns={'p1':'p01','p5':'p05'})
pct.insert(0,'mc_run_id',mc.run_id)
spark.createDataFrame(pct[['mc_run_id','day','p01','p05','p10','p25','p50','p75','p90','p95','p99']]).write.mode('append').saveAsTable(f'{CATALOG}.{SCHEMA}.monte_carlo_percentiles')

paths=(mc.sample_paths.reset_index().melt(id_vars=['day'],var_name='path_id',value_name='value'))
paths.insert(0,'mc_run_id',mc.run_id)
spark.createDataFrame(paths[['mc_run_id','day','path_id','value']]).write.mode('append').saveAsTable(f'{CATALOG}.{SCHEMA}.monte_carlo_sample_paths')

try:
    dbutils.jobs.taskValues.set(key='mc_run_id', value=str(mc.run_id))
except Exception:
    pass

print('MONTE CARLO SAVED:',mc.run_id)
print('Source:',source_description)
print('OPENBB → Monte Carlo Fan Chart / Monte Carlo Sample Paths using this mc_run_id')
print('NEXT → compare another allocation, run portfolio optimization, or open notebooks/platform/02_DEPLOY_APP.py')