from __future__ import annotations

import json
import os
import re
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from databricks import sql
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config

st.set_page_config(page_title="DBO_Quant Research", page_icon="📈", layout="wide")

CATALOG = os.getenv("FINANCE_CATALOG", "workspace")
SCHEMA = os.getenv("FINANCE_SCHEMA", "openbb_quant")
WAREHOUSE_ID = os.getenv("DATABRICKS_WAREHOUSE_ID", "")
BACKTEST_JOB_ID = os.getenv("BACKTEST_JOB_ID", "")
MONTE_CARLO_JOB_ID = os.getenv("MONTE_CARLO_JOB_ID", "")
COMPARISON_JOB_ID = os.getenv("COMPARISON_JOB_ID", "")
OPTIMIZATION_JOB_ID = os.getenv("OPTIMIZATION_JOB_ID", "")

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
if not _IDENTIFIER.match(CATALOG) or not _IDENTIFIER.match(SCHEMA):
    raise RuntimeError("Unsafe FINANCE_CATALOG/FINANCE_SCHEMA identifier")

cfg = Config()
w = WorkspaceClient(config=cfg)


def fq(table: str) -> str:
    if not _IDENTIFIER.match(table):
        raise ValueError("Unsafe table name")
    return f"`{CATALOG}`.`{SCHEMA}`.`{table}`"


def sql_connection():
    if not WAREHOUSE_ID:
        raise RuntimeError("DATABRICKS_WAREHOUSE_ID is not configured")
    hostname = cfg.host.replace("https://", "").replace("http://", "").rstrip("/")
    return sql.connect(
        server_hostname=hostname,
        http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
        credentials_provider=lambda: cfg.authenticate,
        _use_arrow_native_complex_types=False,
    )


@st.cache_data(ttl=45, show_spinner=False)
def query_df(statement: str, parameters: tuple[Any, ...] = ()) -> pd.DataFrame:
    with sql_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(statement, list(parameters))
            rows = cur.fetchall()
            columns = [c[0] for c in cur.description] if cur.description else []
    return pd.DataFrame(rows, columns=columns)


def job_ready(job_id: str) -> bool:
    return bool(str(job_id).strip())


def run_job(job_id: str, params: dict[str, Any]) -> int:
    if not job_ready(job_id):
        raise RuntimeError("The selected Lakeflow Job ID is not configured for this App")
    normalized = {str(k): str(v) for k, v in params.items()}
    response = w.jobs.run_now(job_id=int(job_id), job_parameters=normalized)
    query_df.clear()
    return int(response.run_id)


def pct(value: Any) -> str:
    try:
        return f"{float(value):.2%}"
    except Exception:
        return "—"


def num(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "—"


def money(value: Any) -> str:
    try:
        return f"${float(value):,.0f}"
    except Exception:
        return "—"


def latest_metric_map(run_id: str) -> dict[str, Any]:
    if not run_id:
        return {}
    df = query_df(
        f"SELECT metric_name, metric_value, metric_text FROM {fq('strategy_metrics')} WHERE run_id = ?",
        (run_id,),
    )
    return {str(r.metric_name): r.metric_value if pd.notna(r.metric_value) else r.metric_text for r in df.itertuples()}


def section_header(title: str, subtitle: str = "") -> None:
    st.subheader(title)
    if subtitle:
        st.caption(subtitle)


st.title("DBO_Quant Research")
st.caption(f"Databricks-native research console · {CATALOG}.{SCHEMA} · CPU optimization is the project default")

try:
    with sql_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_user()")
            current_user = cur.fetchone()[0]
    st.sidebar.success(f"SQL connected as {current_user}")
except Exception as exc:
    st.sidebar.error(f"SQL unavailable: {exc}")

st.sidebar.markdown("### Research controls")
st.sidebar.caption("Dashboards and this App read the same Unity Catalog result tables. Job buttons are enabled only when the corresponding Job resource/ID is configured.")
st.sidebar.write("Backtest job", "✅" if job_ready(BACKTEST_JOB_ID) else "—")
st.sidebar.write("Monte Carlo job", "✅" if job_ready(MONTE_CARLO_JOB_ID) else "—")
st.sidebar.write("Comparison job", "✅" if job_ready(COMPARISON_JOB_ID) else "—")
st.sidebar.write("Optimization job", "✅" if job_ready(OPTIMIZATION_JOB_ID) else "—")

pages = st.tabs(["Overview", "Strategy Lab", "Portfolio Lab", "Risk & Monte Carlo", "Models & Signals", "Run Research"])

with pages[0]:
    section_header("Research Overview", "Latest persisted strategy, optimization, Monte Carlo, portfolio and model activity")
    recent_runs = query_df(f"SELECT * FROM {fq('strategy_runs')} ORDER BY created_at DESC LIMIT 50")
    latest_run_id = str(recent_runs.iloc[0]["run_id"]) if not recent_runs.empty else ""
    metrics = latest_metric_map(latest_run_id)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("CAGR", pct(metrics.get("cagr")))
    c2.metric("Sharpe", num(metrics.get("sharpe")))
    c3.metric("Volatility", pct(metrics.get("annualized_volatility")))
    c4.metric("Max drawdown", pct(metrics.get("max_drawdown")))
    c5.metric("Total return", pct(metrics.get("total_return")))

    if latest_run_id:
        curve = query_df(
            f"SELECT date, wealth, benchmark_wealth, drawdown FROM {fq('strategy_daily')} WHERE run_id = ? ORDER BY date",
            (latest_run_id,),
        )
        if not curve.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=curve["date"], y=curve["wealth"], name="Strategy"))
            if curve["benchmark_wealth"].notna().any():
                fig.add_trace(go.Scatter(x=curve["date"], y=curve["benchmark_wealth"], name="Benchmark"))
            fig.update_layout(title=f"Latest strategy run · {latest_run_id}", xaxis_title="Date", yaxis_title="Portfolio value", height=420)
            st.plotly_chart(fig, use_container_width=True)

    left, right = st.columns(2)
    with left:
        st.markdown("#### Recent strategy runs")
        st.dataframe(recent_runs, use_container_width=True, hide_index=True)
    with right:
        optim = query_df(f"SELECT * FROM {fq('optimization_runs')} ORDER BY created_at DESC LIMIT 20")
        st.markdown("#### Recent optimization runs")
        st.dataframe(optim, use_container_width=True, hide_index=True)

with pages[1]:
    section_header("Strategy Lab", "Inspect one backtest as a complete research presentation")
    runs = query_df(f"SELECT run_id, strategy_name, benchmark_symbol, start_date, end_date, status, created_at FROM {fq('strategy_runs')} ORDER BY created_at DESC LIMIT 500")
    if runs.empty:
        st.info("No strategy runs are persisted yet.")
    else:
        labels = {f"{r.strategy_name} · {r.run_id} · {r.created_at}": str(r.run_id) for r in runs.itertuples()}
        selected_label = st.selectbox("Strategy run", list(labels.keys()))
        selected = labels[selected_label]
        metrics = latest_metric_map(selected)
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("CAGR", pct(metrics.get("cagr")))
        c2.metric("Sharpe", num(metrics.get("sharpe")))
        c3.metric("Sortino", num(metrics.get("sortino")))
        c4.metric("Volatility", pct(metrics.get("annualized_volatility")))
        c5.metric("Max DD", pct(metrics.get("max_drawdown")))
        c6.metric("Win rate", pct(metrics.get("win_rate")))
        daily = query_df(f"SELECT * FROM {fq('strategy_daily')} WHERE run_id = ? ORDER BY date", (selected,))
        if not daily.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=daily.date, y=daily.wealth, name="Strategy"))
            if daily.benchmark_wealth.notna().any():
                fig.add_trace(go.Scatter(x=daily.date, y=daily.benchmark_wealth, name="Benchmark"))
            fig.update_layout(title="Portfolio vs benchmark", height=420)
            st.plotly_chart(fig, use_container_width=True)
            d1, d2 = st.columns(2)
            with d1:
                dd = px.area(daily, x="date", y="drawdown", title="Drawdown")
                st.plotly_chart(dd, use_container_width=True)
            with d2:
                turn = px.line(daily, x="date", y="turnover", title="Turnover")
                st.plotly_chart(turn, use_container_width=True)
        holdings = query_df(f"SELECT date, symbol, target_weight, effective_weight FROM {fq('strategy_holdings')} WHERE run_id = ? ORDER BY date DESC, ABS(effective_weight) DESC", (selected,))
        if not holdings.empty:
            latest_date = holdings["date"].max()
            latest_holdings = holdings[holdings["date"] == latest_date]
            allocation = px.bar(latest_holdings, x="symbol", y="effective_weight", title=f"Latest allocation · {latest_date}")
            st.plotly_chart(allocation, use_container_width=True)
            st.dataframe(holdings, use_container_width=True, hide_index=True)

with pages[2]:
    section_header("Portfolio Lab", "Saved portfolios, optimized allocations and efficient frontiers")
    portfolios = query_df(f"SELECT * FROM {fq('portfolio_definitions')} ORDER BY created_at DESC")
    st.dataframe(portfolios, use_container_width=True, hide_index=True)
    optim_runs = query_df(f"SELECT * FROM {fq('optimization_runs')} ORDER BY created_at DESC LIMIT 200")
    if not optim_runs.empty:
        opt_id = st.selectbox("Optimization run", optim_runs["optimization_run_id"].astype(str).tolist())
        frontier = query_df(f"SELECT point_id, regime, solver, expected_return, volatility, cvar, sharpe, risk_aversion FROM {fq('efficient_frontier')} WHERE optimization_run_id = ? ORDER BY point_id", (opt_id,))
        allocations = query_df(f"SELECT portfolio_label, symbol, weight, expected_return, volatility, cvar, sharpe FROM {fq('optimal_allocations')} WHERE optimization_run_id = ? ORDER BY portfolio_label, ABS(weight) DESC", (opt_id,))
        a, b = st.columns(2)
        with a:
            if not frontier.empty:
                fig = px.scatter(frontier, x="volatility", y="expected_return", color="sharpe", hover_data=["point_id", "cvar", "risk_aversion", "solver"], title="Efficient frontier")
                st.plotly_chart(fig, use_container_width=True)
        with b:
            if not allocations.empty:
                label = st.selectbox("Allocation", allocations["portfolio_label"].drop_duplicates().astype(str).tolist())
                chosen = allocations[allocations["portfolio_label"].astype(str) == label]
                fig = px.bar(chosen, x="symbol", y="weight", title=f"Optimized allocation · {label}")
                st.plotly_chart(fig, use_container_width=True)
        st.dataframe(allocations, use_container_width=True, hide_index=True)

with pages[3]:
    section_header("Risk & Monte Carlo", "Scenario fan chart, sample paths and run metadata")
    mc_runs = query_df(f"SELECT * FROM {fq('monte_carlo_runs')} ORDER BY created_at DESC LIMIT 200")
    if mc_runs.empty:
        st.info("No Monte Carlo runs are persisted yet.")
    else:
        mc_id = st.selectbox("Monte Carlo run", mc_runs["mc_run_id"].astype(str).tolist())
        row = mc_runs[mc_runs["mc_run_id"].astype(str) == mc_id].iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Initial value", money(row.get("initial_value")))
        c2.metric("Horizon", f"{int(row.get('horizon_days', 0)):,} days")
        c3.metric("Simulations", f"{int(row.get('n_simulations', 0)):,}")
        c4.metric("Method", str(row.get("method", "—")))
        fan = query_df(f"SELECT day, p05, p25, p50, p75, p95 FROM {fq('monte_carlo_percentiles')} WHERE mc_run_id = ? ORDER BY day", (mc_id,))
        if not fan.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=fan.day, y=fan.p95, line=dict(width=0), showlegend=False))
            fig.add_trace(go.Scatter(x=fan.day, y=fan.p05, fill="tonexty", name="P05–P95", line=dict(width=0)))
            fig.add_trace(go.Scatter(x=fan.day, y=fan.p75, line=dict(width=0), showlegend=False))
            fig.add_trace(go.Scatter(x=fan.day, y=fan.p25, fill="tonexty", name="P25–P75", line=dict(width=0)))
            fig.add_trace(go.Scatter(x=fan.day, y=fan.p50, name="Median"))
            fig.update_layout(title="Monte Carlo portfolio value", xaxis_title="Trading day", yaxis_title="Portfolio value", height=440)
            st.plotly_chart(fig, use_container_width=True)
        paths = query_df(f"SELECT day, path_id, value FROM {fq('monte_carlo_sample_paths')} WHERE mc_run_id = ? ORDER BY day, path_id", (mc_id,))
        if not paths.empty:
            keep = paths["path_id"].drop_duplicates().head(20)
            paths = paths[paths["path_id"].isin(keep)]
            fig = px.line(paths, x="day", y="value", color="path_id", title="Sample paths")
            fig.update_layout(showlegend=False, height=420)
            st.plotly_chart(fig, use_container_width=True)
        st.json(json.loads(row.get("summary_json")) if row.get("summary_json") else {})

with pages[4]:
    section_header("Models & Signals", "Latest engineered features and model predictions")
    features = query_df(f"SELECT * FROM {fq('equity_features_latest')} ORDER BY symbol")
    preds = query_df(f"SELECT * FROM {fq('model_predictions')} ORDER BY prediction_timestamp DESC LIMIT 1000")
    if not features.empty:
        st.markdown("#### Latest features")
        st.dataframe(features, use_container_width=True, hide_index=True)
    if not preds.empty:
        st.markdown("#### Model predictions")
        model_names = ["All"] + preds["model_name"].dropna().astype(str).drop_duplicates().tolist()
        model_filter = st.selectbox("Model", model_names)
        shown = preds if model_filter == "All" else preds[preds["model_name"].astype(str) == model_filter]
        if "prediction" in shown and "symbol" in shown:
            latest = shown.sort_values("prediction_timestamp").groupby("symbol", as_index=False).tail(1)
            fig = px.bar(latest, x="symbol", y="prediction", title="Latest prediction by asset")
            st.plotly_chart(fig, use_container_width=True)
        st.dataframe(shown, use_container_width=True, hide_index=True)

with pages[5]:
    section_header("Run Research", "Launch existing Lakeflow workers from one Databricks-native control surface")
    run_tabs = st.tabs(["Backtest", "Monte Carlo", "Compare", "Optimize"])

    with run_tabs[0]:
        with st.form("backtest_form"):
            strategy_name = st.selectbox("Strategy", ["inverse_volatility", "equal_weight", "buy_and_hold", "fixed_allocation", "factor_top_n", "model_top_n"])
            symbols = st.text_input("Symbols", "SPY,QQQ,IEF,GLD")
            start_date = st.date_input("Start date", value=pd.Timestamp("2015-01-01").date())
            benchmark = st.text_input("Benchmark", "SPY")
            rebalance = st.selectbox("Rebalance", ["monthly", "weekly", "quarterly", "annual", "daily"])
            capital = st.number_input("Initial capital", min_value=1.0, value=100000.0, step=10000.0)
            fee = st.number_input("Fee (bps)", min_value=0.0, value=5.0)
            slippage = st.number_input("Slippage (bps)", min_value=0.0, value=2.0)
            parameters_json = st.text_area("Strategy parameters JSON", "{}")
            submit = st.form_submit_button("Run backtest", disabled=not job_ready(BACKTEST_JOB_ID))
        if submit:
            try:
                parsed = json.loads(parameters_json or "{}")
                run_id = run_job(BACKTEST_JOB_ID, {"catalog": CATALOG, "schema": SCHEMA, "strategy_name": strategy_name, "symbols": symbols, "start_date": start_date.isoformat(), "benchmark_symbol": benchmark, "rebalance": rebalance, "initial_capital": capital, "fee_bps": fee, "slippage_bps": slippage, "parameters_json": json.dumps(parsed)})
                st.success(f"Backtest submitted · Lakeflow run {run_id}")
            except Exception as exc:
                st.error(str(exc))

    with run_tabs[1]:
        with st.form("mc_form"):
            mc_symbols = st.text_input("Symbols", "SPY,IEF,GLD", key="mc_symbols")
            weights = st.text_input("Weights", "0.6,0.3,0.1")
            history_start = st.date_input("History start", value=pd.Timestamp("2010-01-01").date())
            horizon = st.number_input("Horizon days", min_value=21, value=2520, step=21)
            simulations = st.number_input("Simulations", min_value=100, value=10000, step=1000)
            method = st.selectbox("Method", ["historical_bootstrap", "multivariate_normal"])
            initial = st.number_input("Initial value", min_value=1.0, value=100000.0, step=10000.0)
            submit_mc = st.form_submit_button("Run Monte Carlo", disabled=not job_ready(MONTE_CARLO_JOB_ID))
        if submit_mc:
            try:
                run_id = run_job(MONTE_CARLO_JOB_ID, {"catalog": CATALOG, "schema": SCHEMA, "symbols": mc_symbols, "weights": weights, "history_start": history_start.isoformat(), "horizon_days": horizon, "n_simulations": simulations, "method": method, "initial_value": initial})
                st.success(f"Monte Carlo submitted · Lakeflow run {run_id}")
            except Exception as exc:
                st.error(str(exc))

    with run_tabs[2]:
        with st.form("compare_form"):
            compare_ids = st.text_area("Strategy run IDs (comma separated)")
            comparison_name = st.text_input("Comparison name", "Strategy Comparison")
            submit_compare = st.form_submit_button("Compare runs", disabled=not job_ready(COMPARISON_JOB_ID))
        if submit_compare:
            ids = [x.strip() for x in compare_ids.split(",") if x.strip()]
            if len(ids) < 2:
                st.error("Enter at least two strategy run IDs")
            else:
                try:
                    run_id = run_job(COMPARISON_JOB_ID, {"catalog": CATALOG, "schema": SCHEMA, "run_ids": ",".join(ids), "comparison_name": comparison_name})
                    st.success(f"Comparison submitted · Lakeflow run {run_id}")
                except Exception as exc:
                    st.error(str(exc))

    with run_tabs[3]:
        st.info("Optimization remains CPU by default from optimization/portfolio_optimization/portfolio_config.toml. Configure OPTIMIZATION_JOB_ID to expose this button.")
        with st.form("opt_form"):
            source_type = st.selectbox("Optimization source", ["config", "strategy_run"])
            source_id = st.text_input("Strategy run ID", help="Required for strategy_run source")
            submit_opt = st.form_submit_button("Run optimization", disabled=not job_ready(OPTIMIZATION_JOB_ID))
        if submit_opt:
            if source_type == "strategy_run" and not source_id.strip():
                st.error("Strategy run ID is required")
            else:
                try:
                    run_id = run_job(OPTIMIZATION_JOB_ID, {"source_type": source_type, "source_id": source_id.strip()})
                    st.success(f"Optimization submitted · Lakeflow run {run_id}")
                except Exception as exc:
                    st.error(str(exc))
