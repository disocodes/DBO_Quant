-- DBO_Quant AI/BI dashboard presentation views.
-- Replaced by notebooks/platform/05_DEPLOY_DATABRICKS_RESEARCH.py before execution.
-- {{CATALOG}} and {{SCHEMA}} must be safe Unity Catalog identifiers.

CREATE OR REPLACE VIEW {{CATALOG}}.{{SCHEMA}}.research_strategy_summary_v AS
SELECT
  r.run_id,
  r.strategy_name,
  r.benchmark_symbol,
  r.start_date,
  r.end_date,
  r.initial_capital,
  r.rebalance_frequency,
  r.fee_bps,
  r.slippage_bps,
  r.status,
  r.source_engine,
  r.created_at,
  r.completed_at,
  MAX(CASE WHEN m.metric_name = 'total_return' THEN m.metric_value END) AS total_return,
  MAX(CASE WHEN m.metric_name = 'cagr' THEN m.metric_value END) AS cagr,
  MAX(CASE WHEN m.metric_name = 'annualized_volatility' THEN m.metric_value END) AS annualized_volatility,
  MAX(CASE WHEN m.metric_name = 'sharpe' THEN m.metric_value END) AS sharpe,
  MAX(CASE WHEN m.metric_name = 'sortino' THEN m.metric_value END) AS sortino,
  MAX(CASE WHEN m.metric_name = 'max_drawdown' THEN m.metric_value END) AS max_drawdown,
  MAX(CASE WHEN m.metric_name = 'calmar' THEN m.metric_value END) AS calmar,
  MAX(CASE WHEN m.metric_name = 'var_95_daily' THEN m.metric_value END) AS var_95_daily,
  MAX(CASE WHEN m.metric_name = 'cvar_95_daily' THEN m.metric_value END) AS cvar_95_daily,
  MAX(CASE WHEN m.metric_name = 'win_rate' THEN m.metric_value END) AS win_rate,
  MAX(CASE WHEN m.metric_name = 'beta' THEN m.metric_value END) AS beta,
  MAX(CASE WHEN m.metric_name = 'alpha_annualized' THEN m.metric_value END) AS alpha_annualized
FROM {{CATALOG}}.{{SCHEMA}}.strategy_runs r
LEFT JOIN {{CATALOG}}.{{SCHEMA}}.strategy_metrics m ON r.run_id = m.run_id
GROUP BY ALL;

CREATE OR REPLACE VIEW {{CATALOG}}.{{SCHEMA}}.research_strategy_daily_v AS
SELECT
  d.run_id,
  r.strategy_name,
  r.benchmark_symbol,
  r.status,
  r.created_at,
  d.date,
  d.gross_return,
  d.trading_cost_return,
  d.net_return,
  d.wealth,
  d.drawdown,
  d.turnover,
  d.benchmark_return,
  d.benchmark_wealth
FROM {{CATALOG}}.{{SCHEMA}}.strategy_daily d
JOIN {{CATALOG}}.{{SCHEMA}}.strategy_runs r ON d.run_id = r.run_id;

CREATE OR REPLACE VIEW {{CATALOG}}.{{SCHEMA}}.research_strategy_holdings_v AS
SELECT
  h.run_id,
  r.strategy_name,
  r.created_at,
  h.date,
  h.symbol,
  h.target_weight,
  h.effective_weight
FROM {{CATALOG}}.{{SCHEMA}}.strategy_holdings h
JOIN {{CATALOG}}.{{SCHEMA}}.strategy_runs r ON h.run_id = r.run_id;

CREATE OR REPLACE VIEW {{CATALOG}}.{{SCHEMA}}.research_portfolio_holdings_v AS
SELECT
  p.portfolio_id,
  p.portfolio_name,
  p.base_currency,
  p.created_at AS portfolio_created_at,
  h.as_of_date,
  h.symbol,
  h.weight,
  h.quantity,
  h.market_value,
  h.source
FROM {{CATALOG}}.{{SCHEMA}}.portfolio_definitions p
LEFT JOIN {{CATALOG}}.{{SCHEMA}}.portfolio_holdings h ON p.portfolio_id = h.portfolio_id;

CREATE OR REPLACE VIEW {{CATALOG}}.{{SCHEMA}}.research_optimization_frontier_v AS
SELECT
  o.optimization_run_id,
  o.portfolio_id,
  o.objective,
  o.source_engine,
  o.status,
  o.created_at,
  o.completed_at,
  f.point_id,
  f.regime,
  f.solver,
  f.solve_time_seconds,
  f.expected_return,
  f.cvar,
  f.objective_value,
  f.risk_aversion,
  f.variance,
  f.volatility,
  f.sharpe
FROM {{CATALOG}}.{{SCHEMA}}.optimization_runs o
JOIN {{CATALOG}}.{{SCHEMA}}.efficient_frontier f USING (optimization_run_id);

CREATE OR REPLACE VIEW {{CATALOG}}.{{SCHEMA}}.research_optimization_allocations_v AS
SELECT
  o.optimization_run_id,
  o.portfolio_id,
  o.objective,
  o.source_engine,
  o.status,
  o.created_at,
  a.portfolio_label,
  a.point_id,
  a.symbol,
  a.weight,
  a.expected_return,
  a.volatility,
  a.cvar,
  a.sharpe
FROM {{CATALOG}}.{{SCHEMA}}.optimization_runs o
JOIN {{CATALOG}}.{{SCHEMA}}.optimal_allocations a USING (optimization_run_id);

CREATE OR REPLACE VIEW {{CATALOG}}.{{SCHEMA}}.research_monte_carlo_percentiles_v AS
SELECT
  r.mc_run_id,
  r.portfolio_id,
  r.method,
  r.initial_value,
  r.horizon_days,
  r.n_simulations,
  r.rebalance_every_days,
  r.status,
  r.created_at,
  r.completed_at,
  p.day,
  p.p01,
  p.p05,
  p.p10,
  p.p25,
  p.p50,
  p.p75,
  p.p90,
  p.p95,
  p.p99
FROM {{CATALOG}}.{{SCHEMA}}.monte_carlo_runs r
JOIN {{CATALOG}}.{{SCHEMA}}.monte_carlo_percentiles p USING (mc_run_id);

CREATE OR REPLACE VIEW {{CATALOG}}.{{SCHEMA}}.research_monte_carlo_paths_v AS
SELECT
  r.mc_run_id,
  r.portfolio_id,
  r.method,
  r.created_at,
  p.day,
  p.path_id,
  p.value
FROM {{CATALOG}}.{{SCHEMA}}.monte_carlo_runs r
JOIN {{CATALOG}}.{{SCHEMA}}.monte_carlo_sample_paths p USING (mc_run_id);

CREATE OR REPLACE VIEW {{CATALOG}}.{{SCHEMA}}.research_model_signals_v AS
SELECT
  p.prediction_id,
  p.model_name,
  p.model_version,
  p.symbol,
  p.prediction_timestamp,
  p.horizon,
  p.prediction,
  p.probability,
  p.source_endpoint,
  f.return_1m,
  f.return_3m,
  f.return_6m,
  f.return_12m,
  f.volatility_63d,
  f.sma_50_ratio,
  f.sma_200_ratio,
  f.rsi_14
FROM {{CATALOG}}.{{SCHEMA}}.model_predictions p
LEFT JOIN {{CATALOG}}.{{SCHEMA}}.equity_features_latest f ON p.symbol = f.symbol;
