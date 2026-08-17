"""Databricks Online Feature Store + Feature Serving helpers.

Nothing in this module runs implicitly. Creating an online feature store provisions
billable infrastructure, so call prepare_online_feature_store(...) explicitly first,
then create_feature_serving(...).
"""
from __future__ import annotations

import time
from typing import Optional

from databricks.feature_engineering import FeatureLookup, FeatureEngineeringClient
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import EndpointCoreConfigInput, ServedEntityInput

FEATURE_COLUMNS = [
    "return_1m",
    "return_3m",
    "return_6m",
    "return_12m",
    "volatility_63d",
    "sma_50_ratio",
    "sma_200_ratio",
    "rsi_14",
]


def _state_text(obj) -> str:
    state = getattr(obj, "state", "")
    value = getattr(state, "value", state)
    return str(value).upper()


def prepare_online_feature_store(
    *,
    feature_table: str,
    online_store_name: str,
    online_table_name: str,
    capacity: str = "CU_2",
    publish_mode: str = "TRIGGERED",
    wait_seconds: int = 600,
):
    """Create/reuse a Databricks Online Feature Store and publish the feature table.

    The offline feature table must already have non-null primary-key columns. Change
    Data Feed is required for TRIGGERED/CONTINUOUS publishing. This helper waits for
    a newly created online store to become AVAILABLE, then publishes/synchronizes the
    table. It is intentionally opt-in because the online store is billable.
    """
    fe = FeatureEngineeringClient()
    try:
        store = fe.get_online_store(name=online_store_name)
    except Exception:
        store = fe.create_online_store(name=online_store_name, capacity=capacity)

    deadline = time.time() + max(0, int(wait_seconds))
    while "AVAILABLE" not in _state_text(store):
        if time.time() >= deadline:
            raise TimeoutError(
                f"Online feature store {online_store_name!r} is not AVAILABLE yet; "
                "rerun after provisioning completes."
            )
        time.sleep(10)
        store = fe.get_online_store(name=online_store_name)

    return fe.publish_table(
        online_store=store,
        source_table_name=feature_table,
        online_table_name=online_table_name,
        publish_mode=publish_mode,
    )


def create_feature_serving(
    *,
    feature_table: str,
    feature_spec_name: str,
    endpoint_name: str,
    feature_columns: Optional[list[str]] = None,
    workload_size: str = "Small",
    scale_to_zero: bool = True,
):
    """Create a FeatureSpec and Feature Serving endpoint after online publication."""
    fe = FeatureEngineeringClient()
    columns = feature_columns or FEATURE_COLUMNS
    try:
        fe.create_feature_spec(
            name=feature_spec_name,
            features=[
                FeatureLookup(
                    table_name=feature_table,
                    lookup_key="symbol",
                    feature_names=columns,
                )
            ],
        )
    except Exception as exc:
        if "already exists" not in str(exc).lower():
            raise

    workspace = WorkspaceClient()
    return workspace.serving_endpoints.create_and_wait(
        name=endpoint_name,
        config=EndpointCoreConfigInput(
            served_entities=[
                ServedEntityInput(
                    entity_name=feature_spec_name,
                    scale_to_zero_enabled=scale_to_zero,
                    workload_size=workload_size,
                )
            ]
        ),
    )
