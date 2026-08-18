"""
Minimal Databricks App / OpenBB Workspace backend.

The FastAPI instance starts as the installed OpenBB ODP REST API, then this file
adds Databricks `/api/quant/*` routes. Launching it with `openbb-api --app app.py` lets
openbb-platform-api generate Workspace widgets from the combined OpenAPI schema.
No hand-maintained widgets.json is required.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Optional

# Configure OpenBB provider credentials before importing the ODP REST app.
def _configure_openbb_credentials_from_environment() -> None:
    mapping = {
        "FMP_API_KEY": "fmp_api_key",
        "FRED_API_KEY": "fred_api_key",
        "INTRINIO_API_KEY": "intrinio_api_key",
        "TIINGO_TOKEN": "tiingo_token",
        "BENZINGA_API_KEY": "benzinga_api_key",
    }
    credentials = {obb_name: os.environ[env_name] for env_name, obb_name in mapping.items() if os.environ.get(env_name)}
    if not credentials:
        return
    root = Path.home() / ".openbb_platform"
    root.mkdir(parents=True, exist_ok=True)
    path = root / "user_settings.json"
    existing: dict[str, Any] = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text())
        except Exception:
            existing = {}
    existing.setdefault("credentials", {}).update(credentials)
    path.write_text(json.dumps(existing, indent=2))


_configure_openbb_credentials_from_environment()

from openbb_core.api.rest_api import app  # noqa: E402
from openbb_platform_api.utils.widgets import build_json  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
from databricks import sql  # noqa: E402
from databricks.sdk import WorkspaceClient  # noqa: E402
from databricks.sdk.core import Config  # noqa: E402

CATALOG = os.getenv("FINANCE_CATALOG", "main")
SCHEMA = os.getenv("FINANCE_SCHEMA", "openbb_quant")
WAREHOUSE_ID = os.getenv("DATABRICKS_WAREHOUSE_ID", "")
BACKTEST_JOB_ID = os.getenv("BACKTEST_JOB_ID", "")
MONTE_CARLO_JOB_ID = os.getenv("MONTE_CARLO_JOB_ID", "")
COMPARISON_JOB_ID = os.getenv("COMPARISON_JOB_ID", "")

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
for _identifier in (CATALOG, SCHEMA):
    if not _IDENTIFIER.match(_identifier):
        raise RuntimeError(f"Unsafe catalog/schema identifier: {_identifier!r}")

cfg = Config()
workspace = WorkspaceClient(config=cfg)

_allowed_origins = [x.strip() for x in os.getenv("OPENBB_ALLOWED_ORIGINS", "https://pro.openbb.co").split(",") if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=_allowed_origins,allow_credentials=True,allow_methods=["GET","POST","OPTIONS"],allow_headers=["*"])


def fq(table: str) -> str:
    if not _IDENTIFIER.match(table): raise ValueError("Unsafe table name")
    return f"`{CATALOG}`.`{SCHEMA}`.`{table}`"


def _connection():
    if not WAREHOUSE_ID: raise HTTPException(status_code=503,detail="DATABRICKS_WAREHOUSE_ID is not configured")
    hostname=cfg.host.replace("https://","").replace("http://","").rstrip("/")
    return sql.connect(server_hostname=hostname,http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",credentials_provider=lambda:cfg.authenticate,_use_arrow_native_complex_types=False)


def query_records(statement: str, parameters: Optional[list[Any]] = None) -> list[dict[str, Any]]:
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(statement,parameters or [])
            cols=[c[0] for c in cur.description] if cur.description else []
            rows=cur.fetchall()
    out=[]
    for row in rows:
        rec={}
        for key,value in zip(cols,row):
            if hasattr(value,"isoformat"): value=value.isoformat()
            rec[key]=value
        out.append(rec)
    return out


class JobTriggerResponse(BaseModel):
    run_id:int
    job_id:int
    state:str="SUBMITTED"

class BacktestJobRequest(BaseModel):
    portfolio_id:Optional[str]=None
    strategy_name:str=Field(default="inverse_volatility")
    symbols:list[str]=Field(default_factory=lambda:["SPY","QQQ","IEF","GLD"])
    start_date:str="2015-01-01"
    end_date:Optional[str]=None
    benchmark_symbol:str="SPY"
    rebalance:str="monthly"
    initial_capital:float=100000.0
    fee_bps:float=5.0
    slippage_bps:float=2.0
    risk_free_rate:float=0.0
    long_only:bool=True
    gross_leverage_limit:float=1.0
    parameters:dict[str,Any]=Field(default_factory=dict)

class MonteCarloJobRequest(BaseModel):
    portfolio_id:Optional[str]=None
    symbols:list[str]=Field(default_factory=lambda:["SPY","IEF","GLD"])
    weights:list[float]=Field(default_factory=lambda:[0.6,0.3,0.1])
    history_start:str="2010-01-01"
    horizon_days:int=2520
    n_simulations:int=10000
    method:str="historical_bootstrap"
    initial_value:float=100000.0
    seed:int=42
    block_size:int=5
    sample_path_count:int=50
    rebalance_every_days:int=Field(default=21,ge=0,description="1=daily, ~21=monthly, ~63=quarterly, 252=annual, 0=buy-and-hold drift")

class PortfolioComparisonJobRequest(BaseModel):
    run_ids:list[str]=Field(default_factory=list,description="Strategy run IDs to compare")
    comparison_name:str="Strategy Comparison"
    member_names:list[str]=Field(default_factory=list,description="Optional labels matching run_ids order")


def _strip_databricks_api_prefix(value: Any) -> Any:
    if isinstance(value,dict): return {k:_strip_databricks_api_prefix(v) for k,v in value.items()}
    if isinstance(value,list): return [_strip_databricks_api_prefix(v) for v in value]
    if isinstance(value,str) and value.startswith("/api/"): return value[len("/api/"):]
    return value


def _workspace_widget_definitions() -> dict[str,Any]:
    openapi=app.openapi()
    try: definitions=build_json(openapi,["/api/widgets.json","/api/apps.json"])
    except TypeError: definitions=build_json(openapi)
    return _strip_databricks_api_prefix(definitions)

@app.get("/api/widgets.json",include_in_schema=False)
def api_widgets_json()->dict[str,Any]: return _workspace_widget_definitions()

@app.get("/api/apps.json",include_in_schema=False)
def api_apps_json()->list[dict[str,Any]]: return []

@app.get("/api/quant/health",openapi_extra={"widget_config":{"exclude":True}})
def quant_health()->dict:
    return {"status":"ok","architecture":"OpenBB ODP + Databricks lakehouse/serving/jobs + OpenBB Workspace","catalog":CATALOG,"schema":SCHEMA}

@app.get("/api/quant/backtests/runs",openapi_extra={"widget_config":{"name":"Strategy Runs","category":"Quant Research","form_endpoint":"/api/quant/jobs/backtest"}})
def strategy_runs(limit:int=100)->list[dict]:
    return query_records(f"SELECT * FROM {fq('strategy_runs')} ORDER BY created_at DESC LIMIT {max(1,min(limit,1000))}")

@app.get("/api/quant/backtests/metrics",openapi_extra={"widget_config":{"name":"Backtest Metrics","category":"Quant Research"}})
def backtest_metrics(run_id:str)->list[dict]:
    return query_records(f"SELECT metric_name, metric_value, metric_text FROM {fq('strategy_metrics')} WHERE run_id = ? ORDER BY metric_name",[run_id])

@app.get("/api/quant/backtests/equity-curve",openapi_extra={"widget_config":{"type":"chart","name":"Backtest Equity Curve","category":"Quant Research"}})
def backtest_equity_curve(run_id:str)->dict:
    rows=query_records(f"SELECT date, wealth, benchmark_wealth, drawdown FROM {fq('strategy_daily')} WHERE run_id = ? ORDER BY date",[run_id])
    if not rows: raise HTTPException(status_code=404,detail="run_id not found")
    x=[r["date"] for r in rows]
    traces=[{"type":"scatter","mode":"lines","name":"Strategy","x":x,"y":[r["wealth"] for r in rows],"yaxis":"y"}]
    if any(r.get("benchmark_wealth") is not None for r in rows): traces.append({"type":"scatter","mode":"lines","name":"Benchmark","x":x,"y":[r.get("benchmark_wealth") for r in rows],"yaxis":"y"})
    traces.append({"type":"scatter","mode":"lines","name":"Drawdown","x":x,"y":[r["drawdown"] for r in rows],"yaxis":"y2"})
    return {"data":traces,"layout":{"title":"Backtest Equity Curve","xaxis":{"title":"Date"},"yaxis":{"title":"Portfolio Value"},"yaxis2":{"title":"Drawdown","overlaying":"y","side":"right","tickformat":".0%"},"legend":{"orientation":"h"}}}

@app.get("/api/quant/portfolio/comparison-runs",openapi_extra={"widget_config":{"name":"Portfolio Comparison Runs","category":"Portfolio Lab","form_endpoint":"/api/quant/jobs/portfolio-comparison"}})
def portfolio_comparison_runs(limit:int=100)->list[dict]:
    return query_records(f"SELECT * FROM {fq('portfolio_comparison_runs')} ORDER BY created_at DESC LIMIT {max(1,min(limit,1000))}")

@app.get("/api/quant/portfolio/comparison",openapi_extra={"widget_config":{"name":"Portfolio Comparison","category":"Portfolio Lab"}})
def portfolio_comparison(comparison_id:str)->list[dict]:
    return query_records(f"SELECT member_name, metric_name, metric_value, metric_text FROM {fq('portfolio_comparison_metrics')} WHERE comparison_id = ? ORDER BY member_name, metric_name",[comparison_id])

@app.get("/api/quant/portfolio/comparison-curve",openapi_extra={"widget_config":{"type":"chart","name":"Portfolio Comparison Curves","category":"Portfolio Lab"}})
def portfolio_comparison_curve(comparison_id:str)->dict:
    rows=query_records(f"SELECT date, member_name, wealth FROM {fq('portfolio_comparison_daily')} WHERE comparison_id = ? ORDER BY date, member_name",[comparison_id])
    if not rows: raise HTTPException(status_code=404,detail="comparison_id not found")
    names=sorted({r["member_name"] for r in rows})
    data=[]
    for name in names:
        subset=[r for r in rows if r["member_name"]==name]
        data.append({"type":"scatter","mode":"lines","name":name,"x":[r["date"] for r in subset],"y":[r["wealth"] for r in subset]})
    return {"data":data,"layout":{"title":"Portfolio Comparison","xaxis":{"title":"Date"},"yaxis":{"title":"Portfolio Value"}}}

@app.get("/api/quant/monte-carlo/runs",openapi_extra={"widget_config":{"name":"Monte Carlo Runs","category":"Portfolio Lab","form_endpoint":"/api/quant/jobs/monte-carlo"}})
def monte_carlo_runs(limit:int=100)->list[dict]:
    return query_records(f"SELECT * FROM {fq('monte_carlo_runs')} ORDER BY created_at DESC LIMIT {max(1,min(limit,1000))}")

@app.get("/api/quant/monte-carlo/fan-chart",openapi_extra={"widget_config":{"type":"chart","name":"Monte Carlo Fan Chart","category":"Portfolio Lab"}})
def monte_carlo_fan_chart(mc_run_id:str)->dict:
    rows=query_records(f"SELECT day, p05, p25, p50, p75, p95 FROM {fq('monte_carlo_percentiles')} WHERE mc_run_id = ? ORDER BY day",[mc_run_id])
    if not rows: raise HTTPException(status_code=404,detail="mc_run_id not found")
    x=[r["day"] for r in rows]
    data=[
        {"type":"scatter","mode":"lines","name":"P95","x":x,"y":[r["p95"] for r in rows],"line":{"width":0}},
        {"type":"scatter","mode":"lines","name":"P05-P95","x":x,"y":[r["p05"] for r in rows],"fill":"tonexty","line":{"width":0}},
        {"type":"scatter","mode":"lines","name":"P75","x":x,"y":[r["p75"] for r in rows],"line":{"width":0}},
        {"type":"scatter","mode":"lines","name":"P25-P75","x":x,"y":[r["p25"] for r in rows],"fill":"tonexty","line":{"width":0}},
        {"type":"scatter","mode":"lines","name":"Median","x":x,"y":[r["p50"] for r in rows]},
    ]
    return {"data":data,"layout":{"title":"Monte Carlo Portfolio Value","xaxis":{"title":"Trading Day"},"yaxis":{"title":"Portfolio Value"}}}

@app.get("/api/quant/monte-carlo/sample-paths",openapi_extra={"widget_config":{"type":"chart","name":"Monte Carlo Sample Paths","category":"Portfolio Lab"}})
def monte_carlo_sample_paths(mc_run_id:str,limit_paths:int=20)->dict:
    limit_paths=max(1,min(limit_paths,50))
    paths=query_records(f"SELECT DISTINCT path_id FROM {fq('monte_carlo_sample_paths')} WHERE mc_run_id = ? ORDER BY path_id LIMIT {limit_paths}",[mc_run_id])
    if not paths: raise HTTPException(status_code=404,detail="mc_run_id sample paths not found")
    ids=[r['path_id'] for r in paths]
    placeholders=','.join(['?']*len(ids))
    rows=query_records(f"SELECT day, path_id, value FROM {fq('monte_carlo_sample_paths')} WHERE mc_run_id = ? AND path_id IN ({placeholders}) ORDER BY day, path_id",[mc_run_id,*ids])
    data=[]
    for path_id in ids:
        subset=[r for r in rows if r['path_id']==path_id]
        data.append({"type":"scatter","mode":"lines","name":path_id,"x":[r['day'] for r in subset],"y":[r['value'] for r in subset],"line":{"width":1}})
    return {"data":data,"layout":{"title":"Monte Carlo Sample Paths","xaxis":{"title":"Trading Day"},"yaxis":{"title":"Portfolio Value"},"showlegend":False}}

@app.get("/api/quant/optimization/runs",openapi_extra={"widget_config":{"name":"Optimization Runs","category":"Portfolio Lab"}})
def optimization_runs(limit:int=100)->list[dict]:
    return query_records(f"SELECT * FROM {fq('optimization_runs')} ORDER BY created_at DESC LIMIT {max(1,min(limit,1000))}")

@app.get("/api/quant/optimization/efficient-frontier",openapi_extra={"widget_config":{"type":"chart","name":"Efficient Frontier","category":"Portfolio Lab"}})
def efficient_frontier(optimization_run_id:str)->dict:
    rows=query_records(f"SELECT point_id, expected_return, volatility, cvar, sharpe, risk_aversion FROM {fq('efficient_frontier')} WHERE optimization_run_id = ? ORDER BY point_id",[optimization_run_id])
    if not rows: raise HTTPException(status_code=404,detail="optimization_run_id not found")
    return {"data":[{"type":"scatter","mode":"lines+markers","name":"Efficient Frontier","x":[r['volatility'] for r in rows],"y":[r['expected_return'] for r in rows],"text":[f"Sharpe={r.get('sharpe')} | Risk aversion={r.get('risk_aversion')}" for r in rows]}],"layout":{"title":"Efficient Frontier","xaxis":{"title":"Volatility","tickformat":".1%"},"yaxis":{"title":"Expected Return","tickformat":".1%"}}}

@app.get("/api/quant/optimization/allocations",openapi_extra={"widget_config":{"name":"Optimal Allocations","category":"Portfolio Lab"}})
def optimal_allocations(optimization_run_id:str,portfolio_label:Optional[str]=None)->list[dict]:
    if portfolio_label:
        return query_records(f"SELECT * FROM {fq('optimal_allocations')} WHERE optimization_run_id = ? AND portfolio_label = ? ORDER BY ABS(weight) DESC",[optimization_run_id,portfolio_label])
    return query_records(f"SELECT * FROM {fq('optimal_allocations')} WHERE optimization_run_id = ? ORDER BY portfolio_label, ABS(weight) DESC",[optimization_run_id])

@app.get("/api/quant/features/latest",openapi_extra={"widget_config":{"name":"Latest Quant Features","category":"Quant Research"}})
def latest_features(symbol:Optional[str]=None,limit:int=100)->list[dict]:
    limit=max(1,min(limit,1000))
    if symbol: return query_records(f"SELECT * FROM {fq('equity_features_latest')} WHERE symbol = ? LIMIT {limit}",[symbol.upper()])
    return query_records(f"SELECT * FROM {fq('equity_features_latest')} ORDER BY symbol LIMIT {limit}")

@app.get("/api/quant/models/predictions",openapi_extra={"widget_config":{"name":"Model Predictions","category":"Quant Research"}})
def model_predictions(model_name:Optional[str]=None,symbol:Optional[str]=None,limit:int=200)->list[dict]:
    clauses=[];params=[]
    if model_name: clauses.append("model_name = ?");params.append(model_name)
    if symbol: clauses.append("symbol = ?");params.append(symbol.upper())
    where=f" WHERE {' AND '.join(clauses)}" if clauses else ""
    return query_records(f"SELECT * FROM {fq('model_predictions')}{where} ORDER BY prediction_timestamp DESC LIMIT {max(1,min(limit,2000))}",params)

@app.post("/api/quant/jobs/backtest",response_model=JobTriggerResponse)
def run_backtest_job(request:BacktestJobRequest)->JobTriggerResponse:
    if not BACKTEST_JOB_ID: raise HTTPException(status_code=503,detail="BACKTEST_JOB_ID is not configured")
    params={"catalog":CATALOG,"schema":SCHEMA,"strategy_name":request.strategy_name,"portfolio_id":request.portfolio_id or "","symbols":','.join(request.symbols),"start_date":request.start_date,"end_date":request.end_date or "","benchmark_symbol":request.benchmark_symbol,"rebalance":request.rebalance,"initial_capital":str(request.initial_capital),"fee_bps":str(request.fee_bps),"slippage_bps":str(request.slippage_bps),"risk_free_rate":str(request.risk_free_rate),"long_only":str(request.long_only).lower(),"gross_leverage_limit":str(request.gross_leverage_limit),"parameters_json":json.dumps(request.parameters)}
    response=workspace.jobs.run_now(job_id=int(BACKTEST_JOB_ID),job_parameters=params)
    return JobTriggerResponse(run_id=int(response.run_id),job_id=int(BACKTEST_JOB_ID))

@app.post("/api/quant/jobs/monte-carlo",response_model=JobTriggerResponse)
def run_monte_carlo_job(request:MonteCarloJobRequest)->JobTriggerResponse:
    if not MONTE_CARLO_JOB_ID: raise HTTPException(status_code=503,detail="MONTE_CARLO_JOB_ID is not configured")
    params={"catalog":CATALOG,"schema":SCHEMA,"portfolio_id":request.portfolio_id or "","symbols":','.join(request.symbols),"weights":','.join(str(x) for x in request.weights),"history_start":request.history_start,"horizon_days":str(request.horizon_days),"n_simulations":str(request.n_simulations),"method":request.method,"initial_value":str(request.initial_value),"seed":str(request.seed),"block_size":str(request.block_size),"sample_path_count":str(request.sample_path_count),"rebalance_every_days":str(request.rebalance_every_days)}
    response=workspace.jobs.run_now(job_id=int(MONTE_CARLO_JOB_ID),job_parameters=params)
    return JobTriggerResponse(run_id=int(response.run_id),job_id=int(MONTE_CARLO_JOB_ID))

@app.post("/api/quant/jobs/portfolio-comparison",response_model=JobTriggerResponse)
def run_portfolio_comparison_job(request:PortfolioComparisonJobRequest)->JobTriggerResponse:
    if not COMPARISON_JOB_ID: raise HTTPException(status_code=503,detail="COMPARISON_JOB_ID is not configured")
    if len(request.run_ids)<2: raise HTTPException(status_code=422,detail="At least two run_ids are required")
    if request.member_names and len(request.member_names)!=len(request.run_ids): raise HTTPException(status_code=422,detail="member_names must be empty or match run_ids length")
    params={"catalog":CATALOG,"schema":SCHEMA,"run_ids":','.join(request.run_ids),"member_names":','.join(request.member_names),"comparison_name":request.comparison_name}
    response=workspace.jobs.run_now(job_id=int(COMPARISON_JOB_ID),job_parameters=params)
    return JobTriggerResponse(run_id=int(response.run_id),job_id=int(COMPARISON_JOB_ID))
