# Databricks Serving Guide

Databricks Serving is a first-class part of the platform, but it has two distinct roles.

## Model Serving

Use Model Serving for real-time/batch inference from registered models. Examples:

- expected return forecasts
- volatility forecasts
- market regime classification
- credit/risk scoring
- NLP/news sentiment
- alternative-data models

The platform should persist predictions used in research/backtests into `model_predictions` with their original prediction timestamp so historical evaluation remains point-in-time correct.

## Feature Serving

Use Feature Serving for low-latency lookup of current/latest features such as:

- value score
- quality score
- momentum
- volatility
- latest fundamentals
- latest model features

The setup notebook creates `equity_features_latest` with a primary key and Change Data Feed. To make it servable, publish it to a Databricks Online Feature Store using `serving/feature_serving_setup.py`, then create a FeatureSpec/serving endpoint.

Historical factors remain in `factor_snapshots`; Feature Serving is not a replacement for the historical research lakehouse.

## Why Serving does not replace the minimal App

Serving endpoints are optimized contracts for model inference and feature lookup. OpenBB Workspace needs a multi-route backend providing ODP endpoints, quant result endpoints, form/job submission endpoints, and discovery metadata. The minimal Databricks App therefore stays as a thin gateway/orchestrator while delegating inference and low-latency features to Serving.

## Cost/safety

Serving endpoints and online feature resources can incur costs. The notebook therefore makes provisioning opt-in and requires explicit endpoint/model/store configuration before creation.
