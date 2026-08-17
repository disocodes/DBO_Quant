"""Helpers to deploy an existing Unity Catalog model through Databricks Model Serving."""
from __future__ import annotations

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import EndpointCoreConfigInput, ServedEntityInput


def create_model_serving_endpoint(
    endpoint_name: str,
    uc_model_name: str,
    model_version: str,
    *,
    workload_size: str = "Small",
    scale_to_zero: bool = True,
    workload_type: str | None = None,
):
    """Create a Databricks Serving endpoint for a model already registered in Unity Catalog."""
    w = WorkspaceClient()
    entity_kwargs = dict(
        name=f"{endpoint_name}-entity",
        entity_name=uc_model_name,
        entity_version=str(model_version),
        workload_size=workload_size,
        scale_to_zero_enabled=scale_to_zero,
    )
    if workload_type:
        entity_kwargs["workload_type"] = workload_type
    return w.serving_endpoints.create_and_wait(
        name=endpoint_name,
        config=EndpointCoreConfigInput(
            served_entities=[ServedEntityInput(**entity_kwargs)]
        ),
    )


if __name__ == "__main__":
    print("Import create_model_serving_endpoint(...) from a Databricks notebook after registering your model in Unity Catalog.")
