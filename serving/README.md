# Databricks Serving

Serving is an optional subsystem for low-latency model inference and online feature lookup. It is separate from the core research workflow and from the OpenBB API App.

## Model Serving

Use `model_serving_setup.py` after a real model has been registered in Unity Catalog.

Typical use cases include expected-return models, volatility forecasts, regime classifiers, credit/risk models, and sentiment/NLP models. Persist model outputs to the canonical DBO_Quant tables when they should appear in OpenBB Workspace.

## Feature Serving

`feature_serving_setup.py` contains the explicit online-feature workflow:

1. prepare or reuse an Online Feature Store;
2. publish a primary-keyed feature table such as `equity_features_latest`;
3. create a Unity Catalog `FeatureSpec`;
4. create a Feature Serving endpoint.

Online stores and serving endpoints can create billable infrastructure, so `00_SETUP.py` does not provision them automatically.

## What does not require Serving

Serving is not required for strategy backtests, portfolio comparisons, Monte Carlo simulation, portfolio optimization/rebalancing, automated strategy Jobs, or OpenBB visualization of persisted results. Those workflows use Unity Catalog/Delta as their system of record.

## Guided notebook

Use:

```text
notebooks/platform/01_SERVING.py
```

when you intentionally want to create or inspect Serving infrastructure.

## Cleanup

Serving endpoints created specifically for DBO_Quant can be supplied by name to `notebooks/99_CLEANUP.py` for explicit deletion.
