-- Additional normalized tables for NVIDIA portfolio-optimization analysis.
CREATE TABLE IF NOT EXISTS {{CATALOG}}.{{SCHEMA}}.optimization_backtest_metrics (
  optimization_run_id STRING NOT NULL,
  portfolio_name STRING NOT NULL,
  metric_name STRING NOT NULL,
  metric_value DOUBLE,
  metric_text STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{CATALOG}}.{{SCHEMA}}.optimization_rebalance_runs (
  rebalance_run_id STRING NOT NULL,
  optimization_run_id STRING,
  portfolio_id STRING,
  source_engine STRING,
  transaction_cost_factor DOUBLE,
  look_back_window INT,
  look_forward_window INT,
  created_at TIMESTAMP,
  metadata_json STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{CATALOG}}.{{SCHEMA}}.optimization_rebalance_events (
  rebalance_run_id STRING NOT NULL,
  event_index INT NOT NULL,
  event_date DATE,
  event_json STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{CATALOG}}.{{SCHEMA}}.optimization_rebalance_daily (
  rebalance_run_id STRING NOT NULL,
  date DATE NOT NULL,
  portfolio_value DOUBLE
) USING DELTA;
