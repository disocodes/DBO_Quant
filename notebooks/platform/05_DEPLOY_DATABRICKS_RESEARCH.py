# Databricks notebook source
# MAGIC %md
# MAGIC # Platform — Deploy Databricks Research UI
# MAGIC Create/update the DBO_Quant AI/BI research dashboard and deploy the native Streamlit Research Control App from this existing cloned workspace repository.
# MAGIC
# MAGIC Primary UI after this notebook: **Databricks AI/BI + DBO_Quant Research App**. OpenBB remains optional.

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Install runtime SDK

# COMMAND ----------
# MAGIC %pip install -q --upgrade "databricks-sdk>=0.74,<1"

# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Discover project and configure deployment

# COMMAND ----------
from pathlib import Path
import json
import re
import sys
import time

repo_root=Path.cwd()
for candidate in [repo_root,*repo_root.parents]:
    if (candidate/'src'/'quant_platform').exists() and (candidate/'research_app').exists() and (candidate/'dashboards'/'research_dashboard.py').exists():
        repo_root=candidate
        break
else:
    raise RuntimeError('Could not locate the cloned DBO_Quant workspace root.')

sys.path.insert(0,str(repo_root))
sys.path.insert(0,str(repo_root/'src'))

from quant_platform.location import discover_with_spark
from dashboards.research_dashboard import build_dashboard
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.dashboards import Dashboard

location=discover_with_spark(spark)
CATALOG,SCHEMA=location.catalog,location.schema
DETECTED_ROOT=str(repo_root).rstrip('/')

for name,default in [
    ('research_app_name','dbo-quant-research'),
    ('repo_workspace_root',DETECTED_ROOT),
    ('sql_warehouse_id',''),
    ('backtest_job_id',''),
    ('monte_carlo_job_id',''),
    ('comparison_job_id',''),
    ('optimization_job_id',''),
    ('dashboard_name','DBO_Quant Research'),
    ('dashboard_parent_path',DETECTED_ROOT),
    ('publish_dashboard','true'),
    ('deploy_research_app','true'),
]:
    dbutils.widgets.text(name,default)

APP_NAME=dbutils.widgets.get('research_app_name').strip() or 'dbo-quant-research'
WORKSPACE_ROOT=dbutils.widgets.get('repo_workspace_root').strip().rstrip('/') or DETECTED_ROOT
WAREHOUSE_ID=dbutils.widgets.get('sql_warehouse_id').strip()
DASHBOARD_NAME=dbutils.widgets.get('dashboard_name').strip() or 'DBO_Quant Research'
DASHBOARD_PARENT=dbutils.widgets.get('dashboard_parent_path').strip().rstrip('/') or WORKSPACE_ROOT
PUBLISH=dbutils.widgets.get('publish_dashboard').strip().lower()=='true'
DEPLOY_APP=dbutils.widgets.get('deploy_research_app').strip().lower()=='true'
JOB_IDS={
    'backtest_job':dbutils.widgets.get('backtest_job_id').strip(),
    'monte_carlo_job':dbutils.widgets.get('monte_carlo_job_id').strip(),
    'comparison_job':dbutils.widgets.get('comparison_job_id').strip(),
    'optimization_job':dbutils.widgets.get('optimization_job_id').strip(),
}

if not WORKSPACE_ROOT.startswith('/Workspace/'):
    raise ValueError(f'repo_workspace_root must begin with /Workspace/. Got {WORKSPACE_ROOT!r}')
if not DASHBOARD_PARENT.startswith('/Workspace/'):
    raise ValueError(f'dashboard_parent_path must begin with /Workspace/. Got {DASHBOARD_PARENT!r}')
if not re.fullmatch(r'[a-z0-9-]+',APP_NAME):
    raise ValueError('research_app_name must contain only lowercase letters, numbers and hyphens')
if not WAREHOUSE_ID:
    raise ValueError('sql_warehouse_id is required for the AI/BI dashboard and Research App')

SOURCE_CODE_PATH=f'{WORKSPACE_ROOT}/research_app'
print('Namespace:',location.namespace)
print('Workspace repository:',WORKSPACE_ROOT)
print('Research App source:',SOURCE_CODE_PATH)
print('Dashboard:',DASHBOARD_NAME)
print('SQL Warehouse:',WAREHOUSE_ID)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Create dashboard presentation views
# MAGIC Render and execute the versioned SQL view definitions against the canonical DBO_Quant namespace.

# COMMAND ----------
view_sql=(repo_root/'sql'/'research_dashboard_views.sql').read_text()
identifier=lambda value:'`'+value.replace('`','``')+'`'
rendered=view_sql.replace('{{CATALOG}}',identifier(CATALOG)).replace('{{SCHEMA}}',identifier(SCHEMA))
statements=[part.strip() for part in rendered.split(';') if part.strip() and not part.lstrip().startswith('-- DBO_Quant AI/BI dashboard presentation views.')]
# Preserve the first statement if leading comments were attached to it.
if not statements or 'research_strategy_summary_v' not in rendered:
    raise RuntimeError('research_dashboard_views.sql did not render expected research views')
# Re-split after removing comment-only lines so each CREATE statement executes independently.
clean='\n'.join(line for line in rendered.splitlines() if not line.lstrip().startswith('--'))
statements=[part.strip() for part in clean.split(';') if part.strip()]
for statement in statements:
    spark.sql(statement)
print('Created/updated research views:',len(statements))

# COMMAND ----------
# MAGIC %md
# MAGIC ## 4. Validate dashboard datasets before deployment
# MAGIC Databricks dashboards should not be deployed with untested SQL. Execute every dataset query in the generated dashboard against the target catalog/schema and fail here if any query is invalid.

# COMMAND ----------
dashboard_definition=build_dashboard()
validation=[]
for dataset in dashboard_definition['datasets']:
    query=''.join(dataset['queryLines']).strip()
    try:
        spark.sql(f'USE CATALOG {identifier(CATALOG)}')
        spark.sql(f'USE SCHEMA {identifier(SCHEMA)}')
        count=spark.sql(f'SELECT COUNT(*) AS n FROM ({query}) q').first()['n']
        validation.append((dataset['name'],'OK',int(count)))
    except Exception as exc:
        validation.append((dataset['name'],'FAILED',str(exc)))
        display(spark.createDataFrame(validation,['dataset','status','rows_or_error']))
        raise RuntimeError(f"Dashboard dataset {dataset['name']!r} failed validation") from exc

display(spark.createDataFrame(validation,['dataset','status','rows_or_error']))

# COMMAND ----------
# MAGIC %md
# MAGIC ## 5. Create or update the AI/BI dashboard
# MAGIC Reuse the existing dashboard ID when exactly one dashboard with the requested name exists; otherwise create it. Publishing uses the selected SQL Warehouse and does not embed the notebook user's credentials.

# COMMAND ----------
w=WorkspaceClient()
serialized=json.dumps(dashboard_definition,separators=(',',':'))
existing=[d for d in w.lakeview.list() if (d.display_name or '').casefold()==DASHBOARD_NAME.casefold()]
if len(existing)>1:
    raise RuntimeError(f'Multiple AI/BI dashboards named {DASHBOARD_NAME!r} exist. Rename duplicates before continuing.')

payload=Dashboard(
    display_name=DASHBOARD_NAME,
    parent_path=DASHBOARD_PARENT,
    serialized_dashboard=serialized,
    warehouse_id=WAREHOUSE_ID,
)
if existing:
    DASHBOARD_ID=str(existing[0].dashboard_id)
    dashboard=w.lakeview.update(
        dashboard_id=DASHBOARD_ID,
        dashboard=payload,
        dataset_catalog=CATALOG,
        dataset_schema=SCHEMA,
    )
    action='UPDATED'
else:
    dashboard=w.lakeview.create(
        dashboard=payload,
        dataset_catalog=CATALOG,
        dataset_schema=SCHEMA,
    )
    DASHBOARD_ID=str(dashboard.dashboard_id)
    action='CREATED'

if PUBLISH:
    w.lakeview.publish(DASHBOARD_ID,embed_credentials=False,warehouse_id=WAREHOUSE_ID)

print('DASHBOARD',action)
print('dashboard_id =',DASHBOARD_ID)
print('published =',PUBLISH)
print('pages = Overview | Strategy Lab | Portfolio Lab | Risk & Monte Carlo | Models & Signals')

# COMMAND ----------
# MAGIC %md
# MAGIC ## 6. Create/update the Research App resources
# MAGIC The App receives SQL Warehouse `CAN_USE` and, only for Job IDs supplied above, Lakeflow Job `CAN_MANAGE_RUN`. The job permission is sufficient to launch/cancel runs without allowing the App to edit the Job definition.

# COMMAND ----------
if DEPLOY_APP:
    try:
        app=w.apps.get(name=APP_NAME)
        app_action='EXISTING'
    except Exception:
        w.api_client.do('POST','/api/2.0/apps',body={
            'name':APP_NAME,
            'description':'DBO_Quant Databricks-native research control and analysis app',
        })
        app=None
        last_error=None
        for _ in range(30):
            try:
                app=w.apps.get(name=APP_NAME)
                break
            except Exception as exc:
                last_error=exc
                time.sleep(2)
        if app is None:
            raise RuntimeError(f'Created App {APP_NAME!r} but it was not readable after creation') from last_error
        app_action='CREATED'

    current_resources=[]
    for resource in (app.resources or []):
        current_resources.append(resource.as_dict() if hasattr(resource,'as_dict') else resource)

    managed={'sql_warehouse',*JOB_IDS.keys()}
    resources=[r for r in current_resources if r.get('name') not in managed]
    resources.append({
        'name':'sql_warehouse',
        'description':'DBO_Quant research SQL Warehouse',
        'sql_warehouse':{'id':WAREHOUSE_ID,'permission':'CAN_USE'},
    })
    for resource_name,job_id in JOB_IDS.items():
        if job_id:
            resources.append({
                'name':resource_name,
                'description':f'DBO_Quant {resource_name.replace("_"," ")}',
                'job':{'id':job_id,'permission':'CAN_MANAGE_RUN'},
            })

    w.api_client.do('PATCH',f'/api/2.0/apps/{APP_NAME}',body={'resources':resources})
    app=w.apps.get(name=APP_NAME)
    print('Research App:',app_action,APP_NAME)
    print('Configured resources:',[r.get('name') for r in resources])

# COMMAND ----------
# MAGIC %md
# MAGIC ## 7. Grant the Research App Unity Catalog read access

# COMMAND ----------
if DEPLOY_APP:
    APP_SERVICE_PRINCIPAL=str(getattr(app,'service_principal_client_id',None) or '').strip()
    if not APP_SERVICE_PRINCIPAL:
        raise RuntimeError('Research App does not expose service_principal_client_id')

    principal=identifier(APP_SERVICE_PRINCIPAL)
    catalog_sql=identifier(CATALOG)
    schema_sql=f'{catalog_sql}.{identifier(SCHEMA)}'
    try:
        spark.sql(f'GRANT USE CATALOG ON CATALOG {catalog_sql} TO {principal}')
        spark.sql(f'GRANT USE SCHEMA ON SCHEMA {schema_sql} TO {principal}')
        spark.sql(f'GRANT SELECT ON SCHEMA {schema_sql} TO {principal}')
    except Exception as exc:
        raise RuntimeError(
            'Could not grant the Research App read access. The notebook identity must be able to manage grants on the DBO_Quant catalog/schema.'
        ) from exc
    print('App service principal:',APP_SERVICE_PRINCIPAL)
    print('Granted read access:',location.namespace)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 8. Deploy the Research App from the workspace clone
# MAGIC Snapshot `research_app/` from this same cloned workspace folder. No Git URL or independent App checkout is used.

# COMMAND ----------
if DEPLOY_APP:
    env_vars=[
        {'name':'DATABRICKS_WAREHOUSE_ID','value_from':'sql_warehouse'},
        {'name':'FINANCE_CATALOG','value':CATALOG},
        {'name':'FINANCE_SCHEMA','value':SCHEMA},
    ]
    bindings={
        'BACKTEST_JOB_ID':'backtest_job',
        'MONTE_CARLO_JOB_ID':'monte_carlo_job',
        'COMPARISON_JOB_ID':'comparison_job',
        'OPTIMIZATION_JOB_ID':'optimization_job',
    }
    for env_name,resource_name in bindings.items():
        if JOB_IDS[resource_name]:
            env_vars.append({'name':env_name,'value_from':resource_name})

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
    print('workspace source =',SOURCE_CODE_PATH)
    print('Git source = NONE')
    print('app_url =',str(app.url or ''))
    print('deployment =',deployment)
else:
    print('Research App deployment skipped; AI/BI dashboard deployment completed.')

# COMMAND ----------
# MAGIC %md
# MAGIC ## 9. Publish workflow outputs

# COMMAND ----------
try:
    dbutils.jobs.taskValues.set(key='research_dashboard_id',value=DASHBOARD_ID)
    dbutils.jobs.taskValues.set(key='research_app_url',value=str(app.url or '') if DEPLOY_APP else '')
except Exception:
    pass

print('\nDBO_QUANT DATABRICKS RESEARCH UI READY')
print('dashboard_id =',DASHBOARD_ID)
print('research_app =',APP_NAME if DEPLOY_APP else 'not deployed')
print('OpenBB = optional compatibility path')
print('CPU optimizer default = unchanged')
