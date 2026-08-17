# OpenBB Workspace → Databricks App authentication

## Initial/test connection

Databricks Apps supports OAuth 2.0 Bearer authentication for external clients calling `/api/...` endpoints. This bundle intentionally places Workspace discovery and all custom routes under that prefix.

1. Ensure your user/service principal has `CAN USE` on the Databricks App.
2. Using a configured Databricks CLI profile, obtain a current OAuth token:

```bash
databricks auth login --host https://<your-workspace-host> --profile quant
databricks auth token --profile quant
```

3. In OpenBB Workspace → Data Connectors / Custom Backend, set the backend URL to:

```text
https://<your-databricks-app-url>/api
```

4. Add authentication as a request header:

```text
Key: Authorization
Value: Bearer <access_token>
```

5. Test the backend. Workspace will request `/api/widgets.json`; generated widget endpoints are normalized to backend-relative `v1/...` and `quant/...` paths, which Workspace resolves beneath the connected `/api` backend URL.

## Production/unattended connection

Databricks OAuth access tokens are short-lived. A manually pasted token is therefore suitable for testing, not as a permanent unattended credential. For production, use an OAuth-aware gateway/service that performs Databricks M2M client-credential token acquisition/refresh and exposes your organization’s approved stable authentication contract to OpenBB Workspace, or use an OpenBB Enterprise/private deployment authentication pattern that can participate in your OAuth design.

Do not use a Databricks personal access token for the App API path; current Databricks Apps documentation requires OAuth token authentication for this use case.
