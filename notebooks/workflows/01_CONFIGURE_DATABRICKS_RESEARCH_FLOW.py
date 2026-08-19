# Databricks notebook source
# MAGIC %md
# MAGIC # Configure Databricks-Native Research Flow
# MAGIC Create/update the primary DBO_Quant Lakeflow Job for a built-in or custom strategy.
# MAGIC
# MAGIC Default compute flow:
# MAGIC
# MAGIC `refresh data → selected strategy → Monte Carlo baseline → portfolio optimization (CPU) → Monte Carlo optimized allocation → Unity Catalog`
# MAGIC
# MAGIC AI/BI dashboards read the persisted results directly, so UI redeployment is **disabled by default**. Enable it only when dashboard/App code has changed. OpenBB deployment remains a separate optional compatibility path.

# COMMAND ----------
# MAGIC %pip install -q --upgrade "databricks-sdk>=0.74,<1"

# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
import json
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.jobs import JobSettings

for name,default in [
    ('job_name','DBO Quant Databricks Research Flow'),
    ('repo_workspace_root',''),
    ('strategy_notebook','notebooks/backtests/02_INVERSE_VOLATILITY.py'),
    ('strategy_parameters_json','{}'),
    ('include_ingest','true'),
    ('include_monte_carlo','true'),
    ('include_optimization','true'),
    ('include_research_ui_deploy','false'),
    ('research_app_name','dbo-quant-research'),
    ('sql_warehouse_id',''),
    ('dashboard_name','DBO_Quant Research'),
    ('cron_expression',''),
    ('timezone_id','Australia/Perth'),
    ('max_concurrent_runs','1'),
]:
    dbutils.widgets.text(name,default)

JOB_NAME=dbutils.widgets.get('job_name').strip()
ROOT=dbutils.widgets.get('repo_workspace_root').strip().rstrip('/')
STRATEGY=dbutils.widgets.get('strategy_notebook').strip().lstrip('/')
STRATEGY_PARAMS=json.loads(dbutils.widgets.get('strategy_parameters_json') or '{}')
INCLUDE_INGEST=dbutils.widgets.get('include_ingest').lower()=='true'
INCLUDE_MC=dbutils.widgets.get('include_monte_carlo').lower()=='true'
INCLUDE_OPT=dbutils.widgets.get('include_optimization').lower()=='true'
INCLUDE_UI=dbutils.widgets.get('include_research_ui_deploy').lower()=='true'
RESEARCH_APP=dbutils.widgets.get('research_app_name').strip() or 'dbo-quant-research'
WAREHOUSE_ID=dbutils.widgets.get('sql_warehouse_id').strip()
DASHBOARD_NAME=dbutils.widgets.get('dashboard_name').strip() or 'DBO_Quant Research'
CRON=dbutils.widgets.get('cron_expression').strip()
TIMEZONE=dbutils.widgets.get('timezone_id').strip() or 'Australia/Perth'
MAX_CONCURRENT=int(dbutils.widgets.get('max_concurrent_runs'))

if not ROOT or not ROOT.startswith('/Workspace/'):
    raise ValueError('repo_workspace_root must be the absolute /Workspace/... path of the cloned DBO_Quant repository')
if not JOB_NAME:
    raise ValueError('job_name is required')
if not isinstance(STRATEGY_PARAMS,dict):
    raise ValueError('strategy_parameters_json must be a JSON object')
if INCLUDE_UI and not WAREHOUSE_ID:
    raise ValueError('sql_warehouse_id is required when include_research_ui_deploy=true')


def notebook_path(relative:str)->str:
    return f"{ROOT}/{relative.lstrip('/')}"


def notebook_task(task_key,relative,*,depends_on=None,base_parameters=None):
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

if INCLUDE_UI:
    tasks.append(notebook_task(
        'deploy_databricks_research_ui',
        'notebooks/platform/05_DEPLOY_DATABRICKS_RESEARCH.py',
        depends_on=previous,
        base_parameters={
            'repo_workspace_root':ROOT,
            'research_app_name':RESEARCH_APP,
            'sql_warehouse_id':WAREHOUSE_ID,
            'dashboard_name':DASHBOARD_NAME,
            'publish_dashboard':'true',
            'deploy_research_app':'true',
        },
    ))
    previous=['deploy_databricks_research_ui']

settings={
    'name':JOB_NAME,
    'max_concurrent_runs':MAX_CONCURRENT,
    'tasks':tasks,
    'tags':{'project':'DBO_Quant','workflow':'databricks_native_research'},
}
if CRON:
    settings['schedule']={
        'quartz_cron_expression':CRON,
        'timezone_id':TIMEZONE,
        'pause_status':'UNPAUSED',
    }

print('JOB PLAN')
print(json.dumps(settings,indent=2))

w=WorkspaceClient()
job_settings=JobSettings.from_dict(settings)
existing=list(w.jobs.list(name=JOB_NAME))
exact=[j for j in existing if j.settings and (j.settings.name or '').casefold()==JOB_NAME.casefold()]
if len(exact)>1:
    raise RuntimeError(f'Multiple Jobs named {JOB_NAME!r} exist: '+', '.join(str(j.job_id) for j in exact))
if exact:
    job_id=int(exact[0].job_id)
    w.jobs.reset(job_id=job_id,new_settings=job_settings)
    action='UPDATED'
else:
    created=w.jobs.create(**job_settings.as_shallow_dict())
    job_id=int(created.job_id)
    action='CREATED'

print('\nJOB',action)
print('job_id =',job_id)
print('job_name =',JOB_NAME)
print('schedule =',CRON or 'manual Run now')
print('CPU optimizer default = optimization/portfolio_optimization/portfolio_config.toml -> execution.solver = "cpu"')
print('Databricks Research UI deployment included =',INCLUDE_UI)
print('AI/BI dashboard reads new persisted runs without redeployment = true')
print('OpenBB = optional compatibility path')
