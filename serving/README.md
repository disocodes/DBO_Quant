# Databricks Serving

This folder contains optional helpers for Databricks Model Serving and Feature Serving.

Serving is separate from the core research workflow. Strategy backtests, portfolio comparisons, Monte Carlo, portfolio optimization, automated Jobs, and OpenBB display of persisted results do not require Serving.

## Model Serving

Use:

```text
serving/model_serving_setup.py
```

when a model registered in Unity Catalog must be exposed through a low-latency Databricks Model Serving endpoint.

Typical use cases include:

- expected-return models;
- volatility forecasts;
- regime classifiers;
- risk or credit models;
- sentiment or NLP models.

Persist model outputs to DBO_Quant tables when the results should be available to OpenBB Workspace.

## Feature Serving

Use:

```text
serving/feature_serving_setup.py
```

when online feature lookup is required.

The feature-serving workflow can:

1. prepare or reuse an Online Feature Store;
2. publish a primary-keyed feature table such as `equity_features_latest`;
3. create a Unity Catalog `FeatureSpec`;
4. create a Feature Serving endpoint.

These resources can create additional infrastructure cost and are therefore not provisioned by `notebooks/00_SETUP.py`.

## Guided notebook

Use:

```text
notebooks/platform/01_SERVING.py
```

for the Databricks-side entry point to optional serving configuration.

## Relationship to OpenBB

OpenBB Workspace reads persisted DBO_Quant results through the Databricks App.

Serving is only required when a model or online feature endpoint must be called at low latency. It is not required to display existing strategy, Monte Carlo, portfolio-optimization, or comparison results.

## Cleanup

Serving resources are deleted only when explicitly requested.

Use:

```text
notebooks/99_CLEANUP.py
```

and provide any Serving endpoint or Online Feature Store names that should be removed.