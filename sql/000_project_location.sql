-- Canonical DBO_Quant deployment marker.
-- This table lets notebooks and external workers discover the selected
-- Unity Catalog catalog + schema through system.information_schema.
CREATE TABLE IF NOT EXISTS {{CATALOG}}.{{SCHEMA}}.dbo_quant_project_config (
  project_id STRING NOT NULL,
  catalog_name STRING NOT NULL,
  schema_name STRING NOT NULL,
  initialized_at TIMESTAMP NOT NULL,
  config_version INT NOT NULL
) USING DELTA;
