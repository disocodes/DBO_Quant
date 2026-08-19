# Databricks notebook source
# MAGIC %md
# MAGIC # Platform — Connect OpenBB Workspace
# MAGIC Prerequisite: a running DBO_Quant Databricks App from `02_DEPLOY_APP.py` or `04_DEPLOY_APP_AUTOMATED.py`.
# MAGIC
# MAGIC This notebook discovers the deployed App, generates an audience-scoped OAuth token for that App, validates the OpenBB discovery/data endpoints, and prints the exact OpenBB connection values.

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Discover the Project and App
# MAGIC Resolve the canonical DBO_Quant namespace and read the deployed Databricks App URL, OAuth client ID, and App service principal directly from the workspace.

# COMMAND ----------
from pathlib import Path
import sys

repo_root = Path.cwd()
for candidate in [repo_root, *repo_root.parents]:
    if (candidate / 'src' / 'quant_platform').exists():
        repo_root = candidate
        break
sys.path.insert(0, str(repo_root / 'src'))

from quant_platform.location import discover_with_spark
from databricks.sdk import WorkspaceClient

location = discover_with_spark(spark)
CATALOG, SCHEMA = location.catalog, location.schema
print('DBO_Quant namespace:', location.namespace)

for name, default in [
    ('app_name', 'dbo-quant-api'),
    ('app_url_override', ''),
    ('show_openbb_token', 'true'),
]:
    dbutils.widgets.text(name, default)

APP_NAME = dbutils.widgets.get('app_name').strip() or 'dbo-quant-api'
APP_URL_OVERRIDE = dbutils.widgets.get('app_url_override').strip().rstrip('/')
SHOW_TOKEN = dbutils.widgets.get('show_openbb_token').strip().lower() == 'true'

w = WorkspaceClient()
app = w.apps.get(name=APP_NAME)

APP_URL = APP_URL_OVERRIDE or str(app.url or '').rstrip('/')
APP_CLIENT_ID = str(app.oauth2_app_client_id or '').strip()
APP_SERVICE_PRINCIPAL = str(getattr(app, 'service_principal_client_id', None) or '').strip()

if not APP_URL:
    raise RuntimeError(f'Databricks App {APP_NAME!r} does not have a deployed URL yet.')
if not APP_CLIENT_ID:
    raise RuntimeError(f'Databricks App {APP_NAME!r} does not expose oauth2_app_client_id.')

print('App name:', APP_NAME)
print('App URL:', APP_URL)
print('App OAuth client ID:', APP_CLIENT_ID)
print('App service principal:', APP_SERVICE_PRINCIPAL or '<not returned>')
print('Workspace host:', w.config.host)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Verify Persisted Research Data
# MAGIC Check the core DBO_Quant result tables and display their row counts before testing the App API. These Spark checks run as the notebook identity; the later API checks run through the Databricks App service principal.

# COMMAND ----------
checks = []
for table in [
    'prices_daily',
    'strategy_runs',
    'portfolio_comparison_runs',
    'monte_carlo_runs',
    'monte_carlo_sample_paths',
    'optimization_runs',
    'optimization_backtest_metrics',
    'optimization_rebalance_runs',
    'model_predictions',
]:
    try:
        count = spark.table(f'{CATALOG}.{SCHEMA}.{table}').count()
    except Exception:
        count = -1
    checks.append((table, count))

display(spark.createDataFrame(checks, ['table', 'row_count']))

# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Generate an App-Scoped OAuth Token
# MAGIC Exchange the notebook's internal token for an OAuth access token whose audience is this Databricks App. Databricks requires this audience-scoped token when a notebook calls an App API.

# COMMAND ----------
import requests
from datetime import datetime, timedelta, timezone

WORKSPACE_URL = str(w.config.host).rstrip('/')
TOKEN_URL = f'{WORKSPACE_URL}/oidc/v1/token'

notebook_token = (
    dbutils.notebook.entry_point
    .getDbutils()
    .notebook()
    .getContext()
    .apiToken()
    .get()
)

if not notebook_token:
    raise RuntimeError('Could not obtain the internal Databricks notebook token.')

token_response = requests.post(
    TOKEN_URL,
    data={
        'grant_type': 'urn:ietf:params:oauth:grant-type:token-exchange',
        'subject_token': notebook_token,
        'subject_token_type': 'urn:databricks:params:oauth:token-type:personal-access-token',
        'requested_token_type': 'urn:ietf:params:oauth:token-type:access_token',
        'scope': 'all-apis',
        'audience': APP_CLIENT_ID,
    },
    timeout=30,
)

if not token_response.ok:
    raise RuntimeError(
        f'OAuth token exchange failed ({token_response.status_code}): {token_response.text}'
    )

token_payload = token_response.json()
AUDIENCE_TOKEN = token_payload.get('access_token', '')
if not AUDIENCE_TOKEN:
    raise RuntimeError(f'Databricks token exchange returned no access_token: {token_payload}')

expires_in = int(token_payload.get('expires_in') or 0)
created_at = datetime.now(timezone.utc)
expires_at = created_at + timedelta(seconds=expires_in) if expires_in else None

print('OAuth token generated successfully.')
print('Token type:', token_payload.get('token_type', 'Bearer'))
print('Scope:', token_payload.get('scope', ''))
print('Expires in:', expires_in, 'seconds' if expires_in else '<not returned>')
if expires_at:
    print('Expires at UTC:', expires_at.isoformat())

# COMMAND ----------
# MAGIC %md
# MAGIC ## 4. Test OpenBB Discovery, Warehouse Connectivity, and Table Access
# MAGIC The SQL tests are deliberately split. `sql-health` executes only `SELECT 1/current_user()` through the App's configured warehouse; `backtests/runs` additionally requires Unity Catalog access to the DBO_Quant schema.

# COMMAND ----------
AUTH_HEADERS = {
    'Authorization': f'Bearer {AUDIENCE_TOKEN}',
    'Accept': 'application/json',
}

TESTS = [
    ('OpenBB widget discovery', f'{APP_URL}/api/widgets.json'),
    ('DBO_Quant health', f'{APP_URL}/api/quant/health'),
    ('SQL warehouse connectivity', f'{APP_URL}/api/quant/sql-health'),
    ('SQL-backed strategy runs', f'{APP_URL}/api/quant/backtests/runs?limit=1'),
]

results = []
for test_name, url in TESTS:
    try:
        response = requests.get(url, headers=AUTH_HEADERS, timeout=90)
        body_preview = response.text[:500].replace('\n', ' ')
        results.append((test_name, response.status_code, url, body_preview))
    except Exception as exc:
        results.append((test_name, -1, url, str(exc)))

display(spark.createDataFrame(results, ['test', 'http_status', 'url', 'response_preview']))

result_by_name = {row[0]: row for row in results}
widget_status = result_by_name['OpenBB widget discovery'][1]
health_status = result_by_name['DBO_Quant health'][1]
sql_status = result_by_name['SQL warehouse connectivity'][1]
strategy_status = result_by_name['SQL-backed strategy runs'][1]

if widget_status == 200 and health_status == 200:
    print('App authentication and OpenBB discovery are healthy.')

if sql_status != 200:
    print(
        'SQL warehouse connectivity is not healthy. Because this probe does not read a DBO_Quant table, '
        'check the App sql_warehouse resource/CAN_USE permission, warehouse availability or cold-start behaviour, '
        'and the App SQL connector credentials before investigating table grants.'
    )
elif strategy_status != 200:
    print(
        'The App can execute SQL on the warehouse but cannot complete the strategy_runs table query. '
        'Check that the App service principal has USE CATALOG, USE SCHEMA, and SELECT on the DBO_Quant namespace, '
        'and confirm that strategy_runs exists in the catalog/schema printed above.'
    )
else:
    print('OpenBB discovery, SQL warehouse connectivity, and DBO_Quant table access all returned HTTP 200.')

# COMMAND ----------
# MAGIC %md
# MAGIC ## 5. Validate Form Widgets in the Discovery Payload
# MAGIC Confirm that the three run widgets contain generated `type=form` parameters while the build-only top-level `form_endpoint` directive is not exposed to Workspace.

# COMMAND ----------
try:
    widgets_response = requests.get(f'{APP_URL}/api/widgets.json', headers=AUTH_HEADERS, timeout=30)
    widgets_response.raise_for_status()
    widgets = widgets_response.json()
    expected_names = {'Strategy Runs', 'Portfolio Comparison Runs', 'Monte Carlo Runs'}
    form_checks = []
    for widget_id, definition in widgets.items():
        if definition.get('name') not in expected_names:
            continue
        form_params = [p for p in definition.get('params', []) if isinstance(p, dict) and p.get('type') == 'form']
        form_checks.append((
            definition.get('name'),
            widget_id,
            'form_endpoint' in definition,
            len(form_params),
            form_params[0].get('endpoint') if form_params else None,
        ))
    display(spark.createDataFrame(
        form_checks,
        ['widget_name', 'widget_id', 'has_invalid_top_level_form_endpoint', 'form_param_count', 'form_submit_endpoint'],
    ))
    if len(form_checks) == 3 and all((not row[2]) and row[3] >= 1 and row[4] for row in form_checks):
        print('Form widget discovery payload is Workspace-compatible.')
    else:
        print('Form widget discovery still needs inspection; review the table above before reconnecting Workspace.')
except Exception as exc:
    print('Could not validate form widget metadata:', exc)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 6. Print the Exact OpenBB Workspace Connection Values
# MAGIC Use these values in OpenBB Workspace → Custom Backend. The token is short-lived; rerun this notebook when a fresh test token is required.

# COMMAND ----------
BACKEND_URL = f'{APP_URL}/api'
DISCOVERY_URL = f'{APP_URL}/api/widgets.json'

print('OPENBB WORKSPACE BACKEND')
print('Backend URL:', BACKEND_URL)
print('Discovery URL:', DISCOVERY_URL)
print('Authentication location: Header')
print('Authentication key: Authorization')

if SHOW_TOKEN:
    print('\nSENSITIVE — copy this exact value into the OpenBB Authorization header:')
    print(f'Bearer {AUDIENCE_TOKEN}')
else:
    print('\nToken display is disabled. Set notebook widget show_openbb_token=true and rerun to reveal it.')

# COMMAND ----------
# MAGIC %md
# MAGIC ## 7. Configure OpenBB Workspace
# MAGIC In OpenBB Workspace:
# MAGIC
# MAGIC 1. Add or edit the **Custom Backend**.
# MAGIC 2. Use the `Backend URL` printed above.
# MAGIC 3. Add authentication at **Header**.
# MAGIC 4. Set the key to **Authorization**.
# MAGIC 5. Paste the complete value printed above, including the `Bearer ` prefix.
# MAGIC 6. Save the backend and refresh the widget catalogue after the latest App deployment is RUNNING.
# MAGIC
# MAGIC The generated token is intended for connection testing and expires. Do not commit or store it in source control.

# COMMAND ----------
# MAGIC %md
# MAGIC ## 8. Complete the Platform Connection
# MAGIC Confirm the connection workflow and identify the normal research and cleanup paths.

# COMMAND ----------
print('DBO_QUANT OPENBB CONNECTION CHECK COMPLETE')
print('Normal research continues in notebooks/backtests/, notebooks/portfolio/, and notebooks/workflows/.')
print('Final teardown, when required: notebooks/99_CLEANUP.py')
