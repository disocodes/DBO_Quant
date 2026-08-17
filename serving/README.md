# Databricks Serving

Serving is a **first-class subsystem** of this architecture and is deliberately separate from the OpenBB Workspace gateway.

## Model Serving

Use `model_serving_setup.py` after a real model is registered in Unity Catalog. Suitable examples include expected-return models, volatility forecasts, regime classifiers, credit/risk models, or NLP/sentiment models. The thin Databricks App can expose persisted predictions to Workspace, while latency-sensitive applications can call Model Serving directly.

## Feature Serving

`feature_serving_setup.py` provides two explicit steps:

1. `prepare_online_feature_store(...)` — creates/reuses a Databricks Online Feature Store and publishes `equity_features_latest` (or another primary-keyed feature table).
2. `create_feature_serving(...)` — creates a Unity Catalog `FeatureSpec` and a Feature Serving endpoint.

Creating an online feature store provisions billable infrastructure, so the main setup notebook **does not create it automatically**. The notebook does install `databricks-feature-engineering>=0.13.0` and prepares `equity_features_latest` with a primary key and Change Data Feed so you can opt into the online-serving step deliberately.

For `TRIGGERED` or `CONTINUOUS` publication, keep Change Data Feed enabled. The source table primary key must be non-null.

Historical backtests, Monte Carlo simulations, parameter sweeps and bulk portfolio comparisons remain Databricks Jobs/SQL workloads; they should not be disguised as inference endpoints.
