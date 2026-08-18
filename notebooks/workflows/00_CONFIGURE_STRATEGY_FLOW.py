# Databricks notebook source
# MAGIC %md
# MAGIC # Configure Automated Strategy Flow
# MAGIC Create a reusable Lakeflow Job around any DBO_Quant strategy notebook, including a copied custom strategy template.
# MAGIC
# MAGIC Default flow:
# MAGIC
# MAGIC `refresh data → selected strategy → Monte Carlo baseline → portfolio optimization (CPU) → Monte Carlo optimized allocation → persisted OpenBB results`
# MAGIC
# MAGIC The optimizer consumes the selected strategy's latest effective allocation/universe. Optional final step: redeploy the Databricks App from Git so OpenBB immediately sees the latest backend code. App deployment is disabled by default.

# COMMAND ----------
# MAGIC %pip install -q --upgrade "databricks-sdk>=0.74,<1"

# COMMAND ----------
dbutils.library.restartPython()

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
CRON=dbutils.widgets.get('cron_expression').strip()
TIMEZONE=dbutils.widgets.get('timezone_id').strip() or 'Australia/Perth'
MAX_CONCURRENT=int(dbutils.widgets.get('max_concurrent_runs'))

if not ROOT:
    raise ValueError('repo_workspace_root is required. Use the absolute Databricks workspace path of the DBO_Quant Git folder.')
if not JOB_NAME:
    raise ValueError('job_name is required')
if not isinstance(STRATEGY_PARAMS,dict):
    raise ValueError('strategy_parameters_json must be a JSON object')

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
    tasks.append(notebook_task('deploy_openbb_backend','notebooks/platform/04_DEPLOY_APP_AUTOMATED.py',depends_on=previous))
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
# MAGIC ## Create the Job
# MAGIC The cell below creates the Lakeflow Job. Rerunning this notebook creates another Job with the same name; delete or rename an old Job first if you want a single definition.

# COMMAND ----------
w=WorkspaceClient()
job_settings=JobSettings.from_dict(settings)
created=w.jobs.create(**job_settings.as_shallow_dict())
print('JOB CREATED')
print('job_id =',created.job_id)
print('job_name =',JOB_NAME)
print('schedule =',CRON or 'manual Run now')
print('CPU optimizer default = optimization/portfolio_optimization/portfolio_config.toml -> execution.solver = "cpu"')
print('App deployment included =',INCLUDE_APP)
print('\nRun from Workflows > Jobs, or call w.jobs.run_now(job_id=...).')

# COMMAND ----------
# MAGIC %md
# MAGIC ## OpenBB test path
# MAGIC After a successful default run, Unity Catalog contains the strategy backtest, a Monte Carlo baseline for the strategy allocation, the CPU-default optimized allocation/frontier, and a second Monte Carlo simulation of that optimized allocation. If the DBO_Quant App is already deployed, refresh OpenBB Workspace widgets. If `include_app_deploy=true`, the final task requests a new App deployment from the repository automatically.
