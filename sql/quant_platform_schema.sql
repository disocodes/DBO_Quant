-- Replace {{CATALOG}} and {{SCHEMA}} before execution, or use the setup notebook.
-- {{CATALOG}} must already exist.
CREATE SCHEMA IF NOT EXISTS {{CATALOG}}.{{SCHEMA}};

CREATE TABLE IF NOT EXISTS {{CATALOG}}.{{SCHEMA}}.prices_daily (
  symbol STRING NOT NULL,
  date DATE NOT NULL,
  open DOUBLE,
  high DOUBLE,
  low DOUBLE,
  close DOUBLE,
  adjusted_close DOUBLE,
  volume DOUBLE,
  provider STRING,
  currency STRING,
  exchange STRING,
  ingested_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{CATALOG}}.{{SCHEMA}}.factor_snapshots (
  symbol STRING NOT NULL,
  as_of_date DATE NOT NULL,
  available_at TIMESTAMP NOT NULL,
  factor_name STRING NOT NULL,
  factor_value DOUBLE,
  source STRING,
  metadata_json STRING,
  ingested_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{CATALOG}}.{{SCHEMA}}.equity_features_latest (
  symbol STRING NOT NULL,
  feature_timestamp TIMESTAMP NOT NULL,
  return_1m DOUBLE,
  return_3m DOUBLE,
  return_6m DOUBLE,
  return_12m DOUBLE,
  volatility_63d DOUBLE,
  sma_50_ratio DOUBLE,
  sma_200_ratio DOUBLE,
  rsi_14 DOUBLE,
  source STRING,
  updated_at TIMESTAMP,
  CONSTRAINT equity_features_latest_pk PRIMARY KEY (symbol)
) USING DELTA
TBLPROPERTIES (delta.enableChangeDataFeed = true);

CREATE TABLE IF NOT EXISTS {{CATALOG}}.{{SCHEMA}}.strategy_definitions (
  strategy_id STRING NOT NULL,
  strategy_name STRING NOT NULL,
  strategy_family STRING,
  strategy_version STRING,
  description STRING,
  parameters_json STRING,
  code_reference STRING,
  created_at TIMESTAMP,
  is_active BOOLEAN
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{CATALOG}}.{{SCHEMA}}.strategy_runs (
  run_id STRING NOT NULL,
  strategy_id STRING,
  strategy_name STRING NOT NULL,
  benchmark_symbol STRING,
  start_date DATE,
  end_date DATE,
  initial_capital DOUBLE,
  rebalance_frequency STRING,
  fee_bps DOUBLE,
  slippage_bps DOUBLE,
  parameters_json STRING,
  status STRING,
  source_engine STRING,
  created_at TIMESTAMP,
  completed_at TIMESTAMP,
  metadata_json STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{CATALOG}}.{{SCHEMA}}.strategy_daily (
  run_id STRING NOT NULL,
  date DATE NOT NULL,
  gross_return DOUBLE,
  trading_cost_return DOUBLE,
  net_return DOUBLE,
  wealth DOUBLE,
  drawdown DOUBLE,
  turnover DOUBLE,
  benchmark_return DOUBLE,
  benchmark_wealth DOUBLE
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{CATALOG}}.{{SCHEMA}}.strategy_holdings (
  run_id STRING NOT NULL,
  date DATE NOT NULL,
  symbol STRING NOT NULL,
  target_weight DOUBLE,
  effective_weight DOUBLE
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{CATALOG}}.{{SCHEMA}}.strategy_metrics (
  run_id STRING NOT NULL,
  metric_name STRING NOT NULL,
  metric_value DOUBLE,
  metric_text STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{CATALOG}}.{{SCHEMA}}.portfolio_definitions (
  portfolio_id STRING NOT NULL,
  portfolio_name STRING NOT NULL,
  description STRING,
  base_currency STRING,
  created_at TIMESTAMP,
  metadata_json STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{CATALOG}}.{{SCHEMA}}.portfolio_holdings (
  portfolio_id STRING NOT NULL,
  as_of_date DATE NOT NULL,
  symbol STRING NOT NULL,
  weight DOUBLE,
  quantity DOUBLE,
  market_value DOUBLE,
  source STRING,
  ingested_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{CATALOG}}.{{SCHEMA}}.portfolio_comparison_runs (
  comparison_id STRING NOT NULL,
  comparison_name STRING,
  benchmark_symbol STRING,
  start_date DATE,
  end_date DATE,
  created_at TIMESTAMP,
  metadata_json STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{CATALOG}}.{{SCHEMA}}.portfolio_comparison_members (
  comparison_id STRING NOT NULL,
  member_name STRING NOT NULL,
  member_type STRING NOT NULL,
  member_id STRING NOT NULL,
  display_order INT
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{CATALOG}}.{{SCHEMA}}.portfolio_comparison_metrics (
  comparison_id STRING NOT NULL,
  member_name STRING NOT NULL,
  metric_name STRING NOT NULL,
  metric_value DOUBLE,
  metric_text STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{CATALOG}}.{{SCHEMA}}.portfolio_comparison_daily (
  comparison_id STRING NOT NULL,
  date DATE NOT NULL,
  member_name STRING NOT NULL,
  wealth DOUBLE,
  daily_return DOUBLE,
  drawdown DOUBLE
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{CATALOG}}.{{SCHEMA}}.monte_carlo_runs (
  mc_run_id STRING NOT NULL,
  portfolio_id STRING,
  method STRING NOT NULL,
  initial_value DOUBLE,
  horizon_days INT,
  n_simulations INT,
  rebalance_every_days INT,
  seed BIGINT,
  parameters_json STRING,
  status STRING,
  source_engine STRING,
  created_at TIMESTAMP,
  completed_at TIMESTAMP,
  summary_json STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{CATALOG}}.{{SCHEMA}}.monte_carlo_percentiles (
  mc_run_id STRING NOT NULL,
  day INT NOT NULL,
  p01 DOUBLE,
  p05 DOUBLE,
  p10 DOUBLE,
  p25 DOUBLE,
  p50 DOUBLE,
  p75 DOUBLE,
  p90 DOUBLE,
  p95 DOUBLE,
  p99 DOUBLE
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{CATALOG}}.{{SCHEMA}}.monte_carlo_sample_paths (
  mc_run_id STRING NOT NULL,
  day INT NOT NULL,
  path_id STRING NOT NULL,
  value DOUBLE
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{CATALOG}}.{{SCHEMA}}.optimization_runs (
  optimization_run_id STRING NOT NULL,
  portfolio_id STRING,
  objective STRING,
  source_engine STRING,
  source_notebook STRING,
  status STRING,
  created_at TIMESTAMP,
  completed_at TIMESTAMP,
  metadata_json STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{CATALOG}}.{{SCHEMA}}.efficient_frontier (
  optimization_run_id STRING NOT NULL,
  point_id INT NOT NULL,
  regime STRING,
  solver STRING,
  solve_time_seconds DOUBLE,
  expected_return DOUBLE,
  cvar DOUBLE,
  objective_value DOUBLE,
  risk_aversion DOUBLE,
  variance DOUBLE,
  volatility DOUBLE,
  sharpe DOUBLE,
  metadata_json STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{CATALOG}}.{{SCHEMA}}.optimal_allocations (
  optimization_run_id STRING NOT NULL,
  portfolio_label STRING NOT NULL,
  point_id INT,
  symbol STRING NOT NULL,
  weight DOUBLE NOT NULL,
  expected_return DOUBLE,
  volatility DOUBLE,
  cvar DOUBLE,
  sharpe DOUBLE,
  metadata_json STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{CATALOG}}.{{SCHEMA}}.optimization_matrix_entries (
  optimization_run_id STRING NOT NULL,
  matrix_name STRING NOT NULL,
  row_symbol STRING NOT NULL,
  column_symbol STRING NOT NULL,
  value DOUBLE
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{CATALOG}}.{{SCHEMA}}.model_predictions (
  prediction_id STRING NOT NULL,
  model_name STRING NOT NULL,
  model_version STRING,
  symbol STRING,
  prediction_timestamp TIMESTAMP NOT NULL,
  horizon STRING,
  prediction DOUBLE,
  probability DOUBLE,
  feature_snapshot_id STRING,
  source_endpoint STRING,
  metadata_json STRING,
  ingested_at TIMESTAMP
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{CATALOG}}.{{SCHEMA}}.external_ingestion_log (
  ingestion_id STRING NOT NULL,
  source_system STRING NOT NULL,
  object_type STRING,
  object_id STRING,
  status STRING,
  row_count BIGINT,
  metadata_json STRING,
  ingested_at TIMESTAMP
) USING DELTA;
