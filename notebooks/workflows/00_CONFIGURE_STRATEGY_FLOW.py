# Databricks notebook source
# MAGIC %md
# MAGIC # Configure Automated Strategy Flow
# MAGIC Create or update a reusable Lakeflow Job around any DBO_Quant strategy notebook, including a copied custom strategy template.
# MAGIC
# MAGIC Default flow:
# MAGIC
# MAGIC `refresh data → selected strategy → Monte Carlo baseline → portfolio optimization (CPU) → Monte Carlo optimized allocation → persisted OpenBB results`
# MAGIC
# MAGIC The optimizer consumes the selected strategy's latest effective allocation/universe. Optional final step: redeploy the Databricks App from the same cloned DBO_Quant workspace Git folder. App deployment is disabled by default because data-only research runs do not require an App redeploy.

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Install the Databricks SDK
# MAGIC Install a current SDK version used to create, inspect, and update Lakeflow Jobs from this notebook.

# COMMAND ----------
# MAGIC %pip install -q --upgrade "databricks-sdk>=0.74,<1"

# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Restart Python
# MAGIC Restart the Python process so the upgraded Databricks SDK is available before the workflow definition is built.

# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Configure the Strategy Workflow
# MAGIC Set the Job name, repository workspace path, strategy notebook, strategy parameters, optional research stages, schedule, timezone, concurrency limit, and optional App SQL Warehouse. The same `repo_workspace_root` is reused as the Databricks App deployment source when App redeployment is enabled.

# COMMAND ----------
import json
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.jobs import JobSettings

for name,default in [
    ('job_name','DBO Quant Strategy Flow'),
    ('repo_workspace_root',''),
    ('strategy_notebook','notebooks/backtests/02_INVERSE_VOLATILITY.py'),
    ('strategy_parameters_json','{}'),
    ('include_ingest','true'),
    ('include_monte_carlo','true'),
    ('include_optimization','true'),
    ('include_app_deploy','false'),
    ('app_name','dbo-quant-api'),
    ('app_sql_warehouse_id',''),
    ('cron_expression',''),
    ('timezone_id','Australia/Perth'),
    ('max_concurrent_runs','1'),
]: dbutils.widgets.text(name,default)

JOB_NAME=dbutils.widgets.get('job_name').strip()
ROOT=dbutils.widgets.get('repo_workspace_root').strip().rstrip('/')
STRATEGY=dbutils.widgets.get('strategy_notebook').strip().lstrip('/')
STRATEGY_PARAMS=json.loads(dbutils.widgets.get('strategy_parameters_json') or '{}')
INCLUDE_INGEST=dbutils.widgets.get('include_ingest').lower()=='true'
INCLUDE_MC=dbutils.widgets.get('include_monte_carlo').lower()=='true'
INCLUDE_OPT=dbutils.widgets.get('include_optimization').lower()=='true'
INCLUDE_APP=dbutils.widgets.get('include_app_deploy').lower()=='true'
APP_NAME=dbutils.widgets.get('app_name').strip() or 'dbo-quant-api'
APP_WAREHOUSE_ID=dbutils.widgets.get('app_sql_warehouse_id').strip()
CRON=dbutils.widgets.get('cron_expression').strip()
TIMEZONE=dbutils.widgets.get('timezone_id').strip() or 'Australia/Perth'
MAX_CONCURRENT=int(dbutils.widgets.get('max_concurrent_runs'))

if not ROOT:
    raise ValueError('repo_workspace_root is required. Use the absolute Databricks workspace path of the DBO_Quant Git folder.')
if not ROOT.startswith('/Workspace/'):
    raise ValueError('repo_workspace_root must be an absolute Databricks workspace path beginning with /Workspace/.')
if not JOB_NAME:
    raise ValueError('job_name is required')
if not isinstance(STRATEGY_PARAMS,dict):
    raise ValueError('strategy_parameters_json must be a JSON object')

# COMMAND ----------
# MAGIC %md
# MAGIC ## 4. Build the Lakeflow Task Graph
# MAGIC Construct the ordered notebook tasks, dependencies, and task-value handoffs for ingestion, the selected strategy, baseline Monte Carlo, portfolio optimization, optimized Monte Carlo, and optional workspace-sourced App deployment.

# COMMAND ----------
def notebook_path(relative: str) -> str:
    return f"{ROOT}/{relative.lstrip('/')}"

def notebook_task(task_key: str, relative: str, *, depends_on=None, base_parameters=None):
    task={
        'task_key':task_key,
        'notebook_task':{
            'notebook_path':notebook_path(relative),
            'source':'WORKSPACE',
        },
    }
    if depends_on:
        task['depends_on']=[{'task_key':x} for x in depends_on]
    if base_parameters:
        task['notebook_task']['base_parameters']={str(k):str(v) for k,v in base_parameters.items()}
    return task

tasks=[]
previous=[]
if INCLUDE_INGEST:
    tasks.append(notebook_task('refresh_market_data','notebooks/01_INGEST_DATA.py'))
    previous=['refresh_market_data']

tasks.append(notebook_task('strategy',STRATEGY,depends_on=previous,base_parameters=STRATEGY_PARAMS))
previous=['strategy']

if INCLUDE_MC:
    tasks.append(notebook_task(
        'monte_carlo_strategy',
        'notebooks/portfolio/02_MONTE_CARLO.py',
        depends_on=previous,
        base_parameters={
            'source_type':'strategy_run',
            'source_id':'{{tasks.strategy.values.strategy_run_id}}',
        },
    ))
    previous=['monte_carlo_strategy']

if INCLUDE_OPT:
    # Solver comes from optimization/portfolio_optimization/portfolio_config.toml.
    # The committed default is CPU (CVXPY + CLARABEL). The optimization universe
    # and reference weights come from the exact selected strategy run above.
    tasks.append(notebook_task(
        'portfolio_optimization',
        'notebooks/portfolio/04_PORTFOLIO_OPTIMIZATION_DATABRICKS.py',
        depends_on=previous,
        base_parameters={
            'source_type':'strategy_run',
            'source_id':'{{tasks.strategy.values.strategy_run_id}}',
        },
    ))
    previous=['portfolio_optimization']

    if INCLUDE_MC:
        tasks.append(notebook_task(
            'monte_carlo_optimized',
            'notebooks/portfolio/02_MONTE_CARLO.py',
            depends_on=previous,
            base_parameters={
                'source_type':'optimization_run',
                'source_id':'{{tasks.portfolio_optimization.values.optimization_run_id}}',
            },
        ))
        previous=['monte_carlo_optimized']

if INCLUDE_APP:
    app_parameters={
        'repo_workspace_root':ROOT,
        'app_name':APP_NAME,
    }
    if APP_WAREHOUSE_ID:
        app_parameters['sql_warehouse_id']=APP_WAREHOUSE_ID
    tasks.append(notebook_task(
        'deploy_openbb_backend',
        'notebooks/platform/04_DEPLOY_APP_AUTOMATED.py',
        depends_on=previous,
        base_parameters=app_parameters,
    ))
    previous=['deploy_openbb_backend']

settings={
    'name':JOB_NAME,
    'max_concurrent_runs':MAX_CONCURRENT,
    'tasks':tasks,
    'tags':{'project':'DBO_Quant','workflow':'strategy_research'},
}
if CRON:
    settings['schedule']={
        'quartz_cron_expression':CRON,
        'timezone_id':TIMEZONE,
        'pause_status':'UNPAUSED',
    }

print('JOB PLAN')
print(json.dumps(settings,indent=2))

# COMMAND ----------
# MAGIC %md
# MAGIC ## 5. Create or Update the Lakeflow Job
# MAGIC Use the exact `job_name` as the stable identity. Update the existing Job when exactly one match exists, create it when none exists, and reject duplicate-name ambiguity.

# COMMAND ----------
w=WorkspaceClient()
job_settings=JobSettings.from_dict(settings)
existing=list(w.jobs.list(name=JOB_NAME))
exact=[j for j in existing if j.settings and (j.settings.name or '').casefold()==JOB_NAME.casefold()]
if len(exact)>1:
    ids=', '.join(str(j.job_id) for j in exact)
    raise RuntimeError(f'Multiple Jobs named {JOB_NAME!r} already exist ({ids}). Rename or delete duplicates before continuing.')

if exact:
    job_id=int(exact[0].job_id)
    w.jobs.reset(job_id=job_id,new_settings=job_settings)
    action='UPDATED'
else:
    created=w.jobs.create(**job_settings.as_shallow_dict())
    job_id=int(created.job_id)
    action='CREATED'

print('JOB',action)
print('job_id =',job_id)
print('job_name =',JOB_NAME)
print('schedule =',CRON or 'manual Run now')
print('CPU optimizer default = optimization/portfolio_optimization/portfolio_config.toml -> execution.solver = "cpu"')
print('App deployment included =',INCLUDE_APP)
if INCLUDE_APP:
    print('App name =',APP_NAME)
    print('App SQL Warehouse =',APP_WAREHOUSE_ID or 'reuse existing sql_warehouse App resource')
print('\nRun from Workflows > Jobs, or call w.jobs.run_now(job_id=...).')

# COMMAND ----------
# MAGIC %md
# MAGIC ## 6. OpenBB Test Path
# MAGIC After a successful default run, Unity Catalog contains the strategy backtest, a Monte Carlo baseline for the strategy allocation, the CPU-default optimized allocation/frontier, and a second Monte Carlo simulation of that optimized allocation. If the DBO_Quant App is already deployed, refresh OpenBB Workspace widgets; no redeployment is required for new persisted data. If `include_app_deploy=true`, the final task snapshots `databricks_app/` from the same `repo_workspace_root` and validates/configures the App's `sql_warehouse` resource.
