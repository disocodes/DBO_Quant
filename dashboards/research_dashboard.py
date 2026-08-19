"""Build the serialized Databricks AI/BI dashboard for DBO_Quant."""
from __future__ import annotations


def _text(name, text, x, y, width=12):
    return {"widget": {"name": name, "multilineTextboxSpec": {"lines": [text]}}, "position": {"x": x, "y": y, "width": width, "height": 1}}


def _counter(name, dataset, field, title, x, y, *, fmt=None):
    query_name = f"max({field})"
    value = {"fieldName": query_name, "displayName": title}
    if fmt:
        value["format"] = fmt
    return {
        "widget": {
            "name": name,
            "queries": [{"name": "main_query", "query": {"datasetName": dataset, "fields": [{"name": query_name, "expression": f"MAX(`{field}`)"}], "disaggregated": False}}],
            "spec": {"version": 2, "widgetType": "counter", "encodings": {"value": value}, "frame": {"showTitle": True, "title": title}},
        },
        "position": {"x": x, "y": y, "width": 3, "height": 3},
    }


def _line(name, dataset, x_field, y_field, title, x, y, width=6):
    return {
        "widget": {
            "name": name,
            "queries": [{"name": "main_query", "query": {"datasetName": dataset, "fields": [{"name": x_field, "expression": f"`{x_field}`"}, {"name": y_field, "expression": f"`{y_field}`"}], "disaggregated": True}}],
            "spec": {"version": 3, "widgetType": "line", "encodings": {"x": {"fieldName": x_field, "scale": {"type": "temporal"}, "displayName": x_field.replace("_", " ").title()}, "y": {"fieldName": y_field, "scale": {"type": "quantitative"}, "displayName": y_field.replace("_", " ").title()}}, "frame": {"showTitle": True, "title": title}},
        },
        "position": {"x": x, "y": y, "width": width, "height": 6},
    }


def _bar(name, dataset, category, value, title, x, y, width=6):
    return {
        "widget": {
            "name": name,
            "queries": [{"name": "main_query", "query": {"datasetName": dataset, "fields": [{"name": category, "expression": f"`{category}`"}, {"name": value, "expression": f"`{value}`"}], "disaggregated": True}}],
            "spec": {"version": 3, "widgetType": "bar", "encodings": {"x": {"fieldName": category, "scale": {"type": "categorical"}, "displayName": category.replace("_", " ").title()}, "y": {"fieldName": value, "scale": {"type": "quantitative"}, "displayName": value.replace("_", " ").title()}, "label": {"show": False}}, "frame": {"showTitle": True, "title": title}},
        },
        "position": {"x": x, "y": y, "width": width, "height": 6},
    }


def _scatter(name, dataset, x_field, y_field, title, x, y, width=6):
    return {
        "widget": {
            "name": name,
            "queries": [{"name": "main_query", "query": {"datasetName": dataset, "fields": [{"name": x_field, "expression": f"`{x_field}`"}, {"name": y_field, "expression": f"`{y_field}`"}], "disaggregated": True}}],
            "spec": {"version": 3, "widgetType": "scatter", "encodings": {"x": {"fieldName": x_field, "scale": {"type": "quantitative"}, "displayName": x_field.replace("_", " ").title()}, "y": {"fieldName": y_field, "scale": {"type": "quantitative"}, "displayName": y_field.replace("_", " ").title()}}, "frame": {"showTitle": True, "title": title}},
        },
        "position": {"x": x, "y": y, "width": width, "height": 6},
    }


def _table(name, dataset, fields, title, x, y, width=12, height=6):
    return {
        "widget": {
            "name": name,
            "queries": [{"name": "main_query", "query": {"datasetName": dataset, "fields": [{"name": field, "expression": f"`{field}`"} for field in fields], "disaggregated": True}}],
            "spec": {"version": 2, "widgetType": "table", "encodings": {"columns": [{"fieldName": field, "displayName": field.replace("_", " ").title()} for field in fields]}, "frame": {"showTitle": True, "title": title}},
        },
        "position": {"x": x, "y": y, "width": width, "height": height},
    }


def build_dashboard() -> dict:
    percent = {"type": "number-percent", "decimalPlaces": {"type": "max", "places": 2}}
    number = {"type": "number-plain", "decimalPlaces": {"type": "max", "places": 2}}
    money = {"type": "number-currency", "currencyCode": "USD", "abbreviation": "compact", "decimalPlaces": {"type": "max", "places": 2}}

    datasets = [
        {"name": "latest_strategy", "displayName": "Latest strategy summary", "queryLines": ["SELECT * FROM research_strategy_summary_v ORDER BY created_at DESC LIMIT 1 "]},
        {"name": "recent_strategies", "displayName": "Recent strategy runs", "queryLines": ["SELECT * FROM research_strategy_summary_v ORDER BY created_at DESC LIMIT 50 "]},
        {"name": "latest_strategy_daily", "displayName": "Latest strategy daily", "queryLines": ["SELECT d.* FROM research_strategy_daily_v d JOIN (SELECT run_id FROM research_strategy_summary_v ORDER BY created_at DESC LIMIT 1) r USING (run_id) ORDER BY date "]},
        {"name": "latest_strategy_holdings", "displayName": "Latest strategy holdings", "queryLines": ["SELECT h.* FROM research_strategy_holdings_v h JOIN (SELECT run_id FROM research_strategy_summary_v ORDER BY created_at DESC LIMIT 1) r USING (run_id) QUALIFY date = MAX(date) OVER () ORDER BY ABS(effective_weight) DESC "]},
        {"name": "portfolio_holdings", "displayName": "Saved portfolio holdings", "queryLines": ["SELECT * FROM research_portfolio_holdings_v ORDER BY portfolio_created_at DESC, as_of_date DESC, ABS(weight) DESC "]},
        {"name": "latest_frontier", "displayName": "Latest optimization frontier", "queryLines": ["SELECT f.* FROM research_optimization_frontier_v f JOIN (SELECT optimization_run_id FROM optimization_runs ORDER BY created_at DESC LIMIT 1) o USING (optimization_run_id) ORDER BY point_id "]},
        {"name": "latest_allocations", "displayName": "Latest optimized allocations", "queryLines": ["SELECT a.* FROM research_optimization_allocations_v a JOIN (SELECT optimization_run_id FROM optimization_runs ORDER BY created_at DESC LIMIT 1) o USING (optimization_run_id) ORDER BY portfolio_label, ABS(weight) DESC "]},
        {"name": "latest_mc", "displayName": "Latest Monte Carlo percentiles", "queryLines": ["SELECT p.* FROM research_monte_carlo_percentiles_v p JOIN (SELECT mc_run_id FROM monte_carlo_runs ORDER BY created_at DESC LIMIT 1) r USING (mc_run_id) ORDER BY day "]},
        {"name": "recent_mc", "displayName": "Recent Monte Carlo runs", "queryLines": ["SELECT mc_run_id, portfolio_id, method, initial_value, horizon_days, n_simulations, rebalance_every_days, status, created_at, completed_at FROM monte_carlo_runs ORDER BY created_at DESC LIMIT 50 "]},
        {"name": "features", "displayName": "Latest equity features", "queryLines": ["SELECT * FROM equity_features_latest ORDER BY symbol "]},
        {"name": "signals", "displayName": "Recent model signals", "queryLines": ["SELECT * FROM research_model_signals_v ORDER BY prediction_timestamp DESC LIMIT 500 "]},
    ]

    overview = [
        _text("overview_title", "# DBO_Quant Research Overview", 0, 0),
        _text("overview_subtitle", "Latest persisted research from the DBO_Quant lakehouse. Launch experiments from the DBO_Quant Research App.", 0, 1),
        _counter("overview_cagr", "latest_strategy", "cagr", "CAGR", 0, 2, fmt=percent),
        _counter("overview_sharpe", "latest_strategy", "sharpe", "Sharpe", 3, 2, fmt=number),
        _counter("overview_vol", "latest_strategy", "annualized_volatility", "Volatility", 6, 2, fmt=percent),
        _counter("overview_dd", "latest_strategy", "max_drawdown", "Max Drawdown", 9, 2, fmt=percent),
        _line("overview_wealth", "latest_strategy_daily", "date", "wealth", "Latest Strategy Wealth", 0, 5),
        _line("overview_drawdown", "latest_strategy_daily", "date", "drawdown", "Latest Strategy Drawdown", 6, 5),
        _table("overview_runs", "recent_strategies", ["run_id", "strategy_name", "benchmark_symbol", "status", "created_at", "cagr", "sharpe", "max_drawdown"], "Recent Strategy Runs", 0, 11, height=7),
    ]

    strategy = [
        _text("strategy_title", "# Strategy Lab", 0, 0),
        _text("strategy_subtitle", "Detailed presentation of the most recently persisted backtest.", 0, 1),
        _counter("strategy_return", "latest_strategy", "total_return", "Total Return", 0, 2, fmt=percent),
        _counter("strategy_sortino", "latest_strategy", "sortino", "Sortino", 3, 2, fmt=number),
        _counter("strategy_win", "latest_strategy", "win_rate", "Win Rate", 6, 2, fmt=percent),
        _counter("strategy_calmar", "latest_strategy", "calmar", "Calmar", 9, 2, fmt=number),
        _line("strategy_net", "latest_strategy_daily", "date", "net_return", "Daily Net Return", 0, 5),
        _line("strategy_turnover", "latest_strategy_daily", "date", "turnover", "Turnover", 6, 5),
        _bar("strategy_allocation", "latest_strategy_holdings", "symbol", "effective_weight", "Latest Effective Allocation", 0, 11),
        _table("strategy_holdings", "latest_strategy_holdings", ["symbol", "target_weight", "effective_weight", "date"], "Latest Holdings", 6, 11, width=6),
    ]

    portfolio = [
        _text("portfolio_title", "# Portfolio Lab", 0, 0),
        _text("portfolio_subtitle", "Latest optimization frontier, optimized allocations and saved portfolios. CPU is the default solver.", 0, 1),
        _scatter("portfolio_frontier", "latest_frontier", "volatility", "expected_return", "Efficient Frontier", 0, 2),
        _bar("portfolio_allocation", "latest_allocations", "symbol", "weight", "Optimized Weights", 6, 2),
        _table("portfolio_frontier_detail", "latest_frontier", ["point_id", "regime", "solver", "expected_return", "volatility", "cvar", "sharpe", "risk_aversion"], "Frontier Detail", 0, 8),
        _table("portfolio_saved", "portfolio_holdings", ["portfolio_name", "as_of_date", "symbol", "weight", "market_value", "base_currency"], "Saved Portfolios", 0, 14),
    ]

    risk = [
        _text("risk_title", "# Risk & Monte Carlo", 0, 0),
        _text("risk_subtitle", "Scenario distribution from the latest persisted Monte Carlo run.", 0, 1),
        _counter("risk_initial", "latest_mc", "initial_value", "Initial Value", 0, 2, fmt=money),
        _counter("risk_simulations", "latest_mc", "n_simulations", "Simulations", 3, 2, fmt=number),
        _counter("risk_horizon", "latest_mc", "horizon_days", "Horizon Days", 6, 2, fmt=number),
        _counter("risk_rebalance", "latest_mc", "rebalance_every_days", "Rebalance Days", 9, 2, fmt=number),
        _line("risk_median", "latest_mc", "day", "p50", "Median Portfolio Value", 0, 5),
        _line("risk_tail", "latest_mc", "day", "p05", "P05 Downside Path", 6, 5),
        _table("risk_percentiles", "latest_mc", ["day", "p05", "p25", "p50", "p75", "p95"], "Monte Carlo Percentiles", 0, 11),
        _table("risk_runs", "recent_mc", ["mc_run_id", "portfolio_id", "method", "initial_value", "horizon_days", "n_simulations", "status", "created_at"], "Recent Monte Carlo Runs", 0, 17),
    ]

    models = [
        _text("models_title", "# Models & Signals", 0, 0),
        _text("models_subtitle", "Latest engineered features and model predictions persisted in Unity Catalog.", 0, 1),
        _bar("models_predictions", "signals", "symbol", "prediction", "Recent Predictions by Symbol", 0, 2),
        _bar("models_rsi", "features", "symbol", "rsi_14", "RSI 14 by Symbol", 6, 2),
        _table("models_features", "features", ["symbol", "feature_timestamp", "return_1m", "return_3m", "return_6m", "return_12m", "volatility_63d", "rsi_14"], "Latest Features", 0, 8),
        _table("models_signals", "signals", ["prediction_timestamp", "model_name", "model_version", "symbol", "horizon", "prediction", "probability"], "Recent Model Signals", 0, 14, height=7),
    ]

    pages = [
        {"name": "overview", "displayName": "Overview", "pageType": "PAGE_TYPE_CANVAS", "layoutVersion": "GRID_V1", "layout": overview},
        {"name": "strategy_lab", "displayName": "Strategy Lab", "pageType": "PAGE_TYPE_CANVAS", "layoutVersion": "GRID_V1", "layout": strategy},
        {"name": "portfolio_lab", "displayName": "Portfolio Lab", "pageType": "PAGE_TYPE_CANVAS", "layoutVersion": "GRID_V1", "layout": portfolio},
        {"name": "risk_monte_carlo", "displayName": "Risk & Monte Carlo", "pageType": "PAGE_TYPE_CANVAS", "layoutVersion": "GRID_V1", "layout": risk},
        {"name": "models_signals", "displayName": "Models & Signals", "pageType": "PAGE_TYPE_CANVAS", "layoutVersion": "GRID_V1", "layout": models},
    ]

    return {
        "datasets": datasets,
        "pages": pages,
        "uiSettings": {
            "theme": {
                "canvasBackgroundColor": {"light": "#FCFCFC", "dark": "#1F272D"},
                "widgetBackgroundColor": {"light": "#FFFFFF", "dark": "#11171C"},
                "fontColor": {"light": "#11171C", "dark": "#E8ECF0"},
                "selectionColor": {"light": "#2272B4", "dark": "#8ACAFF"},
                "visualizationColors": ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#D55E00", "#56B4E9", "#F0E442"],
                "widgetHeaderAlignment": "LEFT",
            }
        },
    }
