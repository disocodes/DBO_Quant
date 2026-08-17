# Databricks notebook source

# COMMAND ----------

# MAGIC %md

# MAGIC # Databricks + OpenBB Quant Research Platform — Final Architecture

# COMMAND ----------

# MAGIC %md

# MAGIC ## 1. Install notebook dependencies

# COMMAND ----------

%pip install -q "openbb==4.7.2" "openbb-yfinance==1.6.3" "openbb-platform-api==1.3.6" "databricks-sdk>=0.50,<1" "databricks-sql-connector>=4,<5" "databricks-feature-engineering>=0.13.0" "pandas>=2.2,<3" "numpy>=1.26" "plotly>=6,<7"

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

import subprocess
subprocess.run(["openbb-build"], check=True)
print("OpenBB ODP static assets rebuilt for installed extensions.")

# COMMAND ----------

# MAGIC %md

# MAGIC ## 2. Configuration

# COMMAND ----------

from datetime import date, datetime, timezone
import json, os, sys, uuid, math
from pathlib import Path

try:
    current_catalog = spark.sql("SELECT current_catalog() AS c").first()["c"]
except Exception:
    current_catalog = "main"

def _widget(name, default, label=None):
    try:
        dbutils.widgets.text(name, default, label or name)
    except Exception:
        pass

def _get(name, default):
    try:
        return dbutils.widgets.get(name)
    except Exception:
        return default

_widget("catalog", current_catalog, "Existing Unity Catalog catalog")
_widget("schema", "openbb_quant", "Quant platform schema")
_widget("provider", "yfinance", "OpenBB price provider")
_widget("symbols", "SPY,QQQ,IEF,GLD", "Research universe")
_widget("benchmark", "SPY", "Benchmark")
_widget("start_date", "2010-01-01", "History start")
_widget("end_date", str(date.today()), "History end")
_widget("secret_scope", "openbb", "Databricks secret scope for provider keys")
_widget("ingest_prices", "true", "Ingest/merge prices through ODP")
_widget("mc_simulations", "2000", "Monte Carlo simulations for demo")
_widget("mc_horizon_days", "1260", "Monte Carlo horizon (trading days)")
_widget("provision_model_serving", "false", "Create model serving endpoint")
_widget("uc_model_name", "", "Existing UC model name catalog.schema.model")
_widget("uc_model_version", "1", "Existing UC model version")
_widget("model_endpoint_name", "quant-expected-return", "Model Serving endpoint name")
_widget("provision_feature_serving", "false", "Create feature serving endpoint")
_widget("feature_spec_name", "", "FeatureSpec name; blank = catalog.schema.equity-feature-spec")
_widget("feature_endpoint_name", "quant-equity-features", "Feature Serving endpoint name")

CATALOG = _get("catalog", current_catalog).strip()
SCHEMA = _get("schema", "openbb_quant").strip()
PROVIDER = _get("provider", "yfinance").strip()
SYMBOLS = [x.strip().upper() for x in _get("symbols", "SPY,QQQ,IEF,GLD").split(",") if x.strip()]
BENCHMARK = _get("benchmark", "SPY").strip().upper()
START_DATE = _get("start_date", "2010-01-01")
END_DATE = _get("end_date", str(date.today()))
SECRET_SCOPE = _get("secret_scope", "openbb")

assert CATALOG and SCHEMA and SYMBOLS
print({"catalog": CATALOG, "schema": SCHEMA, "provider": PROVIDER, "symbols": SYMBOLS, "benchmark": BENCHMARK})

# COMMAND ----------

# MAGIC %md

# MAGIC ## 3. Load the checked-in arbitrary strategy engine

# COMMAND ----------

repo_root = Path.cwd()
for candidate in [repo_root, *repo_root.parents]:
    if (candidate / 'src' / 'quant_platform').exists():
        repo_root = candidate
        break
sys.path.insert(0, str(repo_root / 'src'))
from quant_platform import REGISTRY, compare_backtests, run_backtest, simulate_portfolio
print('Quant engine loaded from', repo_root / 'src' / 'quant_platform')

# COMMAND ----------

# MAGIC %md

# MAGIC ## 4. Create the canonical Unity Catalog schema

# COMMAND ----------

schema_path = repo_root / 'sql' / 'quant_platform_schema.sql'
SCHEMA_SQL_TEMPLATE = schema_path.read_text()
spark.sql(f"DESCRIBE CATALOG `{CATALOG}`")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{CATALOG}`.`{SCHEMA}`")
rendered = SCHEMA_SQL_TEMPLATE.replace('{{CATALOG}}', CATALOG).replace('{{SCHEMA}}', SCHEMA)
for stmt in [s.strip() for s in rendered.split(';') if s.strip()]:
    executable = '\n'.join(line for line in stmt.splitlines() if not line.strip().startswith('--')).strip()
    if executable and not executable.upper().startswith(('CREATE CATALOG','CREATE SCHEMA')):
        spark.sql(executable)
print(f'Schema ready: {CATALOG}.{SCHEMA}')

# COMMAND ----------

# MAGIC %md

# MAGIC ## 5. Configure permanent OpenBB ODP provider access

# COMMAND ----------

from openbb import obb

SECRET_TO_OBB = {
    "fmp-api-key": "fmp_api_key",
    "fred-api-key": "fred_api_key",
    "intrinio-api-key": "intrinio_api_key",
    "tiingo-token": "tiingo_token",
    "benzinga-api-key": "benzinga_api_key",
}
configured = []
for secret_name, credential_name in SECRET_TO_OBB.items():
    try:
        value = dbutils.secrets.get(SECRET_SCOPE, secret_name)
        if value:
            setattr(obb.user.credentials, credential_name, value)
            configured.append(credential_name)
    except Exception:
        pass
print("ODP loaded. Secret-backed credentials configured:", configured if configured else "none (fine for yfinance/public providers)")

# COMMAND ----------

# MAGIC %md

# MAGIC ## 6. ODP → Delta market-data ingestion

# COMMAND ----------

import numpy as np
import pandas as pd
from delta.tables import DeltaTable
from pyspark.sql import functions as F


def _first_existing(df, candidates):
    lower = {str(c).lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in lower:
            return lower[c.lower()]
    return None


def fetch_odp_price_history(symbol: str, provider: str = PROVIDER) -> pd.DataFrame:
    result = obb.equity.price.historical(symbol=symbol, start_date=START_DATE, end_date=END_DATE, provider=provider)
    df = result.to_df().reset_index()
    if df.empty:
        return df
    date_col = _first_existing(df, ["date", "datetime", "index"])
    if date_col is None:
        raise ValueError(f"Could not find date column for {symbol}: {list(df.columns)}")
    out = pd.DataFrame({"date": pd.to_datetime(df[date_col]).dt.date})
    for dest, candidates in {
        "open": ["open"], "high": ["high"], "low": ["low"], "close": ["close"],
        "adjusted_close": ["adjusted_close", "adj_close", "adjusted close"], "volume": ["volume"],
    }.items():
        src = _first_existing(df, candidates)
        out[dest] = pd.to_numeric(df[src], errors="coerce").astype(float) if src else np.nan
    out["symbol"] = symbol.upper(); out["provider"] = provider; out["currency"] = ""; out["exchange"] = ""
    out["ingested_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
    return out[["symbol", "date", "open", "high", "low", "close", "adjusted_close", "volume", "provider", "currency", "exchange", "ingested_at"]]


def merge_prices(pdf: pd.DataFrame):
    if pdf.empty:
        return 0
    sdf = spark.createDataFrame(pdf)
    target = DeltaTable.forName(spark, f"{CATALOG}.{SCHEMA}.prices_daily")
    (target.alias("t").merge(sdf.alias("s"), "t.symbol = s.symbol AND t.date = s.date AND t.provider = s.provider")
      .whenMatchedUpdateAll().whenNotMatchedInsertAll().execute())
    return len(pdf)

if _get("ingest_prices", "true").lower() == "true":
    total = 0
    for symbol in sorted(set(SYMBOLS + [BENCHMARK])):
        try:
            pdf = fetch_odp_price_history(symbol)
            count = merge_prices(pdf)
            print(f"{symbol}: merged {count:,} rows through ODP provider={PROVIDER}")
            total += count
        except Exception as exc:
            print(f"WARNING {symbol}: {type(exc).__name__}: {exc}")
    print("Total fetched/merged rows:", total)
else:
    print("Price ingestion skipped; existing Delta data will be used.")

# COMMAND ----------

# MAGIC %md

# MAGIC ## 7. Derive latest features for Feature Serving

# COMMAND ----------

def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff(); gain = delta.clip(lower=0).rolling(period).mean(); loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)

prices_pdf = (spark.table(f"{CATALOG}.{SCHEMA}.prices_daily")
    .where(F.col("symbol").isin(sorted(set(SYMBOLS + [BENCHMARK]))))
    .select("date", "symbol", F.coalesce("adjusted_close", "close").alias("price")).toPandas())
if prices_pdf.empty:
    raise ValueError("prices_daily is empty. Enable ODP ingestion or load your own price data first.")
prices_wide = prices_pdf.pivot_table(index="date", columns="symbol", values="price", aggfunc="last").sort_index()
prices_wide.index = pd.to_datetime(prices_wide.index)
feature_rows = []
for symbol in prices_wide.columns:
    s = prices_wide[symbol].dropna()
    if len(s) < 30: continue
    rets = s.pct_change(fill_method=None); latest = s.index[-1]
    feature_rows.append({
        "symbol": symbol, "feature_timestamp": latest.to_pydatetime(),
        "return_1m": float(s.pct_change(21).iloc[-1]) if len(s) > 21 else None,
        "return_3m": float(s.pct_change(63).iloc[-1]) if len(s) > 63 else None,
        "return_6m": float(s.pct_change(126).iloc[-1]) if len(s) > 126 else None,
        "return_12m": float(s.pct_change(252).iloc[-1]) if len(s) > 252 else None,
        "volatility_63d": float(rets.rolling(63).std().iloc[-1] * np.sqrt(252)) if len(s) > 63 else None,
        "sma_50_ratio": float(s.iloc[-1] / s.rolling(50).mean().iloc[-1] - 1) if len(s) > 50 else None,
        "sma_200_ratio": float(s.iloc[-1] / s.rolling(200).mean().iloc[-1] - 1) if len(s) > 200 else None,
        "rsi_14": float(_rsi(s, 14).iloc[-1]) if len(s) > 20 else None,
        "source": f"ODP:{PROVIDER}", "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
    })
features_pdf = pd.DataFrame(feature_rows)
if not features_pdf.empty:
    features_sdf = spark.createDataFrame(features_pdf)
    target = DeltaTable.forName(spark, f"{CATALOG}.{SCHEMA}.equity_features_latest")
    (target.alias("t").merge(features_sdf.alias("s"), "t.symbol = s.symbol").whenMatchedUpdateAll().whenNotMatchedInsertAll().execute())
    display(features_sdf.orderBy("symbol"))

# COMMAND ----------

# MAGIC %md

# MAGIC ## 8. Arbitrary strategy engine

# COMMAND ----------

research = prices_wide.reindex(columns=SYMBOLS).ffill().dropna(how="all")
benchmark_prices = prices_wide[BENCHMARK].reindex(research.index).ffill() if BENCHMARK in prices_wide.columns else None

def momentum_low_volatility(prices: pd.DataFrame, params: dict) -> pd.DataFrame:
    momentum_lookback = int(params.get("momentum_lookback", 126)); vol_lookback = int(params.get("vol_lookback", 63))
    top_n = int(params.get("top_n", min(2, prices.shape[1])))
    returns = prices.pct_change(fill_method=None); momentum = prices.pct_change(momentum_lookback, fill_method=None)
    vol = returns.rolling(vol_lookback).std().replace(0, np.nan); score = (momentum / vol).where(momentum > 0)
    from quant_platform.engine import scores_to_weights
    return scores_to_weights(score, top_n=top_n)
REGISTRY.register("momentum_low_volatility", momentum_low_volatility)

strategy_specs = {
    "Equal Weight Rebalanced": ("fixed_allocation", {}),
    "Inverse Volatility": ("inverse_volatility", {"lookback": 63}),
    "Cross-Sectional Momentum": ("cross_sectional_momentum", {"lookback": 126, "top_n": max(1, min(2, len(SYMBOLS)))}),
    "Momentum + Low Vol": ("momentum_low_volatility", {"momentum_lookback": 126, "vol_lookback": 63, "top_n": max(1, min(2, len(SYMBOLS)))}),
}
results = {}
for label, (strategy_name, params) in strategy_specs.items():
    results[label] = run_backtest(research, strategy_name, params=params, rebalance="monthly", initial_capital=100_000,
        fee_bps=5, slippage_bps=2, benchmark_prices=benchmark_prices, metadata={"label": label, "symbols": SYMBOLS, "benchmark": BENCHMARK})
metrics_table, wealth_curves, return_corr = compare_backtests(results)
display(metrics_table.reset_index(names="portfolio_or_strategy")); display(return_corr.reset_index(names="portfolio_or_strategy"))

# COMMAND ----------

# MAGIC %md

# MAGIC ## 9. Persist strategy runs and portfolio comparison

# COMMAND ----------

def persist_backtest(label: str, result, strategy_name: str, params: dict):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    run_pdf = pd.DataFrame([{"run_id": result.run_id, "strategy_id": "", "strategy_name": strategy_name,
        "benchmark_symbol": BENCHMARK, "start_date": research.index.min().date(), "end_date": research.index.max().date(),
        "initial_capital": float(result.metrics["initial_capital"]), "rebalance_frequency": "monthly", "fee_bps": 5.0,
        "slippage_bps": 2.0, "parameters_json": json.dumps(params), "status": "COMPLETED",
        "source_engine": "quant_platform.weight_engine", "created_at": now, "completed_at": now,
        "metadata_json": json.dumps({"label": label, **result.metadata}, default=str)}])
    spark.createDataFrame(run_pdf).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.strategy_runs")
    daily = result.daily.reset_index().rename(columns={result.daily.index.name or "index": "date"}); daily["date"] = pd.to_datetime(daily["date"]).dt.date
    daily.insert(0, "run_id", result.run_id)
    for c in ["benchmark_return", "benchmark_wealth"]:
        if c not in daily: daily[c] = np.nan
    spark.createDataFrame(daily[["run_id", "date", "gross_return", "trading_cost_return", "net_return", "wealth", "drawdown", "turnover", "benchmark_return", "benchmark_wealth"]]).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.strategy_daily")
    holdings=[]
    for dt in result.target_weights.index:
        for sym in result.target_weights.columns:
            tw=float(result.target_weights.at[dt,sym]); ew=float(result.effective_weights.at[dt,sym])
            if abs(tw)>1e-12 or abs(ew)>1e-12: holdings.append({"run_id":result.run_id,"date":dt.date(),"symbol":sym,"target_weight":tw,"effective_weight":ew})
    if holdings: spark.createDataFrame(pd.DataFrame(holdings)).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.strategy_holdings")
    metric_rows=[]
    for k,v in result.metrics.items():
        try: fv=float(v); fv=fv if np.isfinite(fv) else None
        except Exception: fv=None
        metric_rows.append({"run_id":result.run_id,"metric_name":k,"metric_value":fv,"metric_text":""})
    spark.createDataFrame(pd.DataFrame(metric_rows)).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.strategy_metrics")

for label,(strategy_name,params) in strategy_specs.items(): persist_backtest(label,results[label],strategy_name,params)

comparison_id=str(uuid.uuid4()); now=datetime.now(timezone.utc).replace(tzinfo=None); comparison_name="Demo multi-strategy comparison"
spark.createDataFrame(pd.DataFrame([{"comparison_id":comparison_id,"comparison_name":comparison_name,"benchmark_symbol":BENCHMARK,
    "start_date":research.index.min().date(),"end_date":research.index.max().date(),"created_at":now,"metadata_json":json.dumps({"members":list(results)})}])).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.portfolio_comparison_runs")
member_rows=[]; metric_rows=[]; daily_rows=[]
for i,(label,result) in enumerate(results.items()):
    member_rows.append({"comparison_id":comparison_id,"member_name":label,"member_type":"strategy_run","member_id":result.run_id,"display_order":i})
    for k,v in result.metrics.items():
        try: fv=float(v); fv=fv if np.isfinite(fv) else None
        except Exception: fv=None
        metric_rows.append({"comparison_id":comparison_id,"member_name":label,"metric_name":k,"metric_value":fv,"metric_text":""})
    for dt,row in result.daily.iterrows(): daily_rows.append({"comparison_id":comparison_id,"date":dt.date(),"member_name":label,"wealth":float(row["wealth"]),"daily_return":float(row["net_return"]),"drawdown":float(row["drawdown"])})
spark.createDataFrame(pd.DataFrame(member_rows)).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.portfolio_comparison_members")
spark.createDataFrame(pd.DataFrame(metric_rows)).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.portfolio_comparison_metrics")
spark.createDataFrame(pd.DataFrame(daily_rows)).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.portfolio_comparison_daily")
print("comparison_id =", comparison_id)

# COMMAND ----------

# MAGIC %md

# MAGIC ## 10. Monte Carlo simulation

# COMMAND ----------

mc_base=results["Inverse Volatility"]; latest_weights=mc_base.target_weights.iloc[-1].clip(lower=0)
latest_weights = latest_weights/latest_weights.sum() if latest_weights.sum()>0 else pd.Series(1.0/len(latest_weights), index=latest_weights.index)
asset_returns=research.pct_change(fill_method=None).dropna(how="any")
mc=simulate_portfolio(asset_returns,latest_weights,initial_value=100_000,horizon_days=int(_get("mc_horizon_days","1260")),
    n_simulations=int(_get("mc_simulations","2000")),method="historical_bootstrap",seed=42,sample_path_count=50,block_size=5,rebalance_every_days=21)
print(mc.summary); display(mc.percentiles.iloc[::max(1,len(mc.percentiles)//20)].reset_index())
now=datetime.now(timezone.utc).replace(tzinfo=None)
run_pdf=pd.DataFrame([{"mc_run_id":mc.run_id,"portfolio_id":"","method":"historical_bootstrap","initial_value":float(mc.summary["initial_value"]),
    "horizon_days":int(mc.summary["horizon_days"]),"n_simulations":int(mc.summary["n_simulations"]),"rebalance_every_days":int(mc.summary["rebalance_every_days"]),
    "seed":42,"parameters_json":json.dumps({"symbols":list(latest_weights.index),"weights":latest_weights.to_dict(),"block_size":5,"rebalance_every_days":21}),
    "status":"COMPLETED","source_engine":"quant_platform.monte_carlo","created_at":now,"completed_at":now,"summary_json":json.dumps(mc.summary)}])
spark.createDataFrame(run_pdf).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.monte_carlo_runs")
pct=mc.percentiles.reset_index().rename(columns={"p1":"p01","p5":"p05"}); pct.insert(0,"mc_run_id",mc.run_id)
spark.createDataFrame(pct[["mc_run_id","day","p01","p05","p10","p25","p50","p75","p90","p95","p99"]]).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.monte_carlo_percentiles")
paths=mc.sample_paths.reset_index().melt(id_vars="day",var_name="path_id",value_name="value"); paths.insert(0,"mc_run_id",mc.run_id)
spark.createDataFrame(paths[["mc_run_id","day","path_id","value"]]).write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.monte_carlo_sample_paths")
print("Monte Carlo persisted:",mc.run_id)

# COMMAND ----------

# MAGIC %md

# MAGIC ## 11. Databricks Serving — first-class, opt-in

# COMMAND ----------

if _get("provision_model_serving", "false").lower() == "true":
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.serving import EndpointCoreConfigInput, ServedEntityInput
    uc_model_name=_get("uc_model_name","").strip(); uc_model_version=_get("uc_model_version","1").strip(); endpoint_name=_get("model_endpoint_name","quant-expected-return").strip()
    if not uc_model_name: raise ValueError("Set uc_model_name to an existing catalog.schema.model before provisioning.")
    w=WorkspaceClient(); print(w.serving_endpoints.create_and_wait(name=endpoint_name,config=EndpointCoreConfigInput(served_entities=[ServedEntityInput(name=f"{endpoint_name}-entity",entity_name=uc_model_name,entity_version=uc_model_version,workload_size="Small",scale_to_zero_enabled=True)])))
else:
    print("Model Serving provisioning skipped. Use serving/model_serving_setup.py when ready.")

if _get("provision_feature_serving", "false").lower() == "true":
    print("Feature Serving requires online publication first. Use serving/feature_serving_setup.py for the explicit billable provisioning workflow.")
else:
    print("Feature Serving provisioning skipped by design; the latest feature table is ready for publication.")

# COMMAND ----------

# MAGIC %md

# MAGIC ## 12. Validation

# COMMAND ----------

table_counts=[]
for table in ["prices_daily","equity_features_latest","strategy_runs","strategy_daily","portfolio_comparison_runs","monte_carlo_runs","optimization_runs","model_predictions"]:
    table_counts.append((table,spark.table(f"{CATALOG}.{SCHEMA}.{table}").count()))
display(spark.createDataFrame(table_counts,["table","row_count"]))
print("comparison_id:",comparison_id); print("monte_carlo_run_id:",mc.run_id)
for label,result in results.items(): print(f"{label}: {result.run_id}")

# COMMAND ----------

# MAGIC %md

# MAGIC # Next: create the three Lakeflow Jobs, deploy `databricks_app/`, enable Serving as needed, and connect OpenBB Workspace to the App `/api` backend.
