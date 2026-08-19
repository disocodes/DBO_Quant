# Databricks notebook source
# MAGIC %md
# MAGIC # Platform — Enable Research App Run Controls
# MAGIC Create or reuse the four dedicated Lakeflow Jobs used by the DBO_Quant Research App, bind them to the existing App with `CAN_MANAGE_RUN`, and redeploy the App so Backtest, Monte Carlo, Compare and Optimize are enabled.
# MAGIC
# MAGIC Run `05_DEPLOY_DATABRICKS_RESEARCH.py` first. This notebook does **not** rerun platform setup or recreate Unity Catalog tables.

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Install runtime SDK

# COMMAND ----------
# MAGIC %pip install -q --upgrade "databricks-sdk>=0.74,<1"

# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Discover the existing DBO_Quant deployment

# COMMAND ----------
from pathlib import Path
import sys

repo_root=Path.cwd()
for candidate in [repo_root,*repo_root.parents]:
    if (candidate/'src'/'quant_platform').exists() and (candidate/'research_app').exists() and (candidate/'jobs').exists():
        repo_root=candidate
        break
else:
    raise RuntimeError('Could not locate the cloned DBO_Quant workspace root.')

sys.path.insert(0,str(repo_root/'src'))

from quant_platform.location import discover_with_spark
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.jobs import JobSettings

location=discover_with_spark(spark)
CATALOG,SCHEMA=location.catalog,location.schema
DETECTED_ROOT=str(repo_root).rstrip('/')

for name,default in [
    ('research_app_name','dbo-quant-research'),
    ('repo_workspace_root',DETECTED_ROOT),
    ('backtest_job_id',''),
    ('monte_carlo_job_id',''),
    ('comparison_job_id',''),
    ('optimization_job_id',''),
]:
    dbutils.widgets.text(name,default)

APP_NAME=dbutils.widgets.get('research_app_name').strip() or 'dbo-quant-research'
WORKSPACE_ROOT=dbutils.widgets.get('repo_workspace_root').strip().rstrip('/') or DETECTED_ROOT
if not WORKSPACE_ROOT.startswith('/Workspace/'):
    raise ValueError(f'repo_workspace_root must begin with /Workspace/. Got {WORKSPACE_ROOT!r}')

SOURCE_CODE_PATH=f'{WORKSPACE_ROOT}/research_app'
w=WorkspaceClient()

try:
    app=w.apps.get(name=APP_NAME)
except Exception as exc:
    raise RuntimeError(
        f'Research App {APP_NAME!r} does not exist. Run notebooks/platform/05_DEPLOY_DATABRICKS_RESEARCH.py first.'
    ) from exc

current_resources=[]
for resource in (app.resources or []):
    current_resources.append(resource.as_dict() if hasattr(resource,'as_dict') else resource)

warehouse_resource=next((r for r in current_resources if r.get('name')=='sql_warehouse'),None)
if not warehouse_resource or not (warehouse_resource.get('sql_warehouse') or {}).get('id'):
    raise RuntimeError(
        f'Research App {APP_NAME!r} has no sql_warehouse resource. Rerun 05_DEPLOY_DATABRICKS_RESEARCH.py first.'
    )

print('Namespace:',location.namespace)
print('Workspace repository:',WORKSPACE_ROOT)
print('Research App:',APP_NAME)
print('Research App source:',SOURCE_CODE_PATH)
print('SQL Warehouse:',(warehouse_resource.get('sql_warehouse') or {}).get('id'))

# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Create or reuse the dedicated Lakeflow Jobs
# MAGIC Blank Job-ID widgets mean **create or reuse the standard DBO_Quant Job by name**. Supplying an ID keeps your existing custom Job instead. Standard Jobs use notebook tasks sourced directly from this workspace Git folder and use Databricks serverless Jobs compute when the workspace supports it.

# COMMAND ----------
WORKERS={
    'backtest_job':{
        'widget':'backtest_job_id',
        'name':'DBO_Quant Research Backtest',
        'path':f'{WORKSPACE_ROOT}/jobs/backtest_worker.py',
        'env':'BACKTEST_JOB_ID',
    },
    'monte_carlo_job':{
        'widget':'monte_carlo_job_id',
        'name':'DBO_Quant Research Monte Carlo',
        'path':f'{WORKSPACE_ROOT}/jobs/monte_carlo_worker.py',
        'env':'MONTE_CARLO_JOB_ID',
    },
    'comparison_job':{
        'widget':'comparison_job_id',
        'name':'DBO_Quant Research Comparison',
        'path':f'{WORKSPACE_ROOT}/jobs/comparison_worker.py',
        'env':'COMPARISON_JOB_ID',
    },
    'optimization_job':{
        'widget':'optimization_job_id',
        'name':'DBO_Quant Research Optimization',
        'path':f'{WORKSPACE_ROOT}/notebooks/portfolio/04_PORTFOLIO_OPTIMIZATION_DATABRICKS.py',
        'env':'OPTIMIZATION_JOB_ID',
    },
}


def create_or_update_standard_job(spec):
    settings={
        'name':spec['name'],
        'max_concurrent_runs':4,
        'tasks':[
            {
                'task_key':'run',
                'notebook_task':{
                    'notebook_path':spec['path'],
                    'source':'WORKSPACE',
                },
            }
        ],
        'tags':{
            'project':'DBO_Quant',
            'purpose':'research_app_worker',
        },
    }
    job_settings=JobSettings.from_dict(settings)
    matches=list(w.jobs.list(name=spec['name']))
    exact=[j for j in matches if j.settings and (j.settings.name or '').casefold()==spec['name'].casefold()]
    if len(exact)>1:
        ids=', '.join(str(j.job_id) for j in exact)
        raise RuntimeError(f"Multiple Jobs named {spec['name']!r} exist ({ids}). Rename/delete duplicates before continuing.")
    if exact:
        job_id=int(exact[0].job_id)
        w.jobs.reset(job_id=job_id,new_settings=job_settings)
        return job_id,'UPDATED'
    created=w.jobs.create(**job_settings.as_shallow_dict())
    return int(created.job_id),'CREATED'


JOB_IDS={}
job_rows=[]
for resource_name,spec in WORKERS.items():
    supplied=dbutils.widgets.get(spec['widget']).strip()
    if supplied:
        try:
            existing_job=w.jobs.get(job_id=int(supplied))
        except Exception as exc:
            raise RuntimeError(f"{spec['widget']}={supplied!r} is not a readable Lakeflow Job") from exc
        job_id=int(supplied)
        action='SUPPLIED'
        job_name=(existing_job.settings.name if existing_job.settings else '') or spec['name']
    else:
        job_id,action=create_or_update_standard_job(spec)
        job_name=spec['name']
    JOB_IDS[resource_name]=str(job_id)
    job_rows.append((resource_name,job_id,job_name,action,spec['path']))

display(spark.createDataFrame(job_rows,['app_resource','job_id','job_name','action','notebook_path']))

# COMMAND ----------
# MAGIC %md
# MAGIC ## 4. Bind Jobs to the Research App
# MAGIC Each Job is attached as an App resource with `CAN_MANAGE_RUN`. This permits the App service principal to trigger and cancel runs without permission to edit the Job definition.

# COMMAND ----------
managed=set(WORKERS.keys())
resources=[r for r in current_resources if r.get('name') not in managed]
for resource_name,spec in WORKERS.items():
    resources.append({
        'name':resource_name,
        'description':f"DBO_Quant {resource_name.replace('_',' ')}",
        'job':{
            'id':JOB_IDS[resource_name],
            'permission':'CAN_MANAGE_RUN',
        },
    })

w.api_client.do('PATCH',f'/api/2.0/apps/{APP_NAME}',body={'resources':resources})
app=w.apps.get(name=APP_NAME)
print('Configured App resources:',[r.get('name') for r in resources])

# COMMAND ----------
# MAGIC %md
# MAGIC ## 5. Redeploy the Research App with Job bindings
# MAGIC The App receives the Job IDs from its Databricks App resources. No Job ID is hard-coded in source code.

# COMMAND ----------
env_vars=[
    {'name':'DATABRICKS_WAREHOUSE_ID','value_from':'sql_warehouse'},
    {'name':'FINANCE_CATALOG','value':CATALOG},
    {'name':'FINANCE_SCHEMA','value':SCHEMA},
]
for resource_name,spec in WORKERS.items():
    env_vars.append({'name':spec['env'],'value_from':resource_name})

deployment=w.api_client.do(
    'POST',
    f'/api/2.0/apps/{APP_NAME}/deployments',
    body={
        'source_code_path':SOURCE_CODE_PATH,
        'mode':'SNAPSHOT',
        'env_vars':env_vars,
    },
)

app=w.apps.get(name=APP_NAME)
print('APP DEPLOYMENT REQUESTED')
print('app_url =',str(app.url or ''))
print('workspace source =',SOURCE_CODE_PATH)
print('Git source = NONE')
print('Backtest Job ID =',JOB_IDS['backtest_job'])
print('Monte Carlo Job ID =',JOB_IDS['monte_carlo_job'])
print('Comparison Job ID =',JOB_IDS['comparison_job'])
print('Optimization Job ID =',JOB_IDS['optimization_job'])
print('deployment =',deployment)

try:
    dbutils.jobs.taskValues.set(key='backtest_job_id',value=JOB_IDS['backtest_job'])
    dbutils.jobs.taskValues.set(key='monte_carlo_job_id',value=JOB_IDS['monte_carlo_job'])
    dbutils.jobs.taskValues.set(key='comparison_job_id',value=JOB_IDS['comparison_job'])
    dbutils.jobs.taskValues.set(key='optimization_job_id',value=JOB_IDS['optimization_job'])
except Exception:
    pass

print('\nRESEARCH APP RUN CONTROLS CONFIGURED')
print('After the App deployment reaches RUNNING, refresh the Research App.')
print('Expected sidebar: Backtest ✅ | Monte Carlo ✅ | Comparison ✅ | Optimization ✅')
print('CPU optimizer default = unchanged')
