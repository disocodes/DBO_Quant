from __future__ import annotations

from dataclasses import dataclass

MARKER_TABLE = "dbo_quant_project_config"
PROJECT_ID = "DBO_Quant"
DEFAULT_SCHEMA = "openbb_quant"


@dataclass(frozen=True)
class ProjectLocation:
    catalog: str
    schema: str

    @property
    def namespace(self) -> str:
        return f"{self.catalog}.{self.schema}"


def _require_single(rows: list[tuple[str, str]]) -> ProjectLocation:
    unique = sorted(set(rows))
    if not unique:
        raise RuntimeError(
            "No DBO_Quant deployment marker is visible. Run notebooks/00_SETUP.py first, "
            "or specify an explicit catalog/schema override for a separate deployment."
        )
    if len(unique) > 1:
        choices = ", ".join(f"{c}.{s}" for c, s in unique)
        raise RuntimeError(
            "Multiple DBO_Quant deployments are visible: " + choices + ". "
            "Choose the intended catalog/schema explicitly."
        )
    return ProjectLocation(*unique[0])


def discover_with_spark(spark, *, catalog: str | None = None, schema: str | None = None) -> ProjectLocation:
    """Discover the canonical DBO_Quant Unity Catalog location from Databricks."""
    if catalog and schema:
        spark.table(f"`{catalog}`.`{schema}`.`{MARKER_TABLE}`").limit(1).collect()
        return ProjectLocation(catalog, schema)

    rows = spark.sql(
        f"""
        SELECT table_catalog, table_schema
        FROM system.information_schema.tables
        WHERE table_name = '{MARKER_TABLE}'
          AND table_schema <> 'information_schema'
        ORDER BY table_catalog, table_schema
        """
    ).collect()
    return _require_single([(r[0], r[1]) for r in rows])


def discover_with_sql_connection(conn, *, catalog: str | None = None, schema: str | None = None) -> ProjectLocation:
    """Discover the canonical DBO_Quant location through a Databricks SQL connection."""
    if catalog and schema:
        with conn.cursor() as cur:
            cur.execute(f"SELECT 1 FROM `{catalog}`.`{schema}`.`{MARKER_TABLE}` LIMIT 1")
            cur.fetchone()
        return ProjectLocation(catalog, schema)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT table_catalog, table_schema
            FROM system.information_schema.tables
            WHERE table_name = '{MARKER_TABLE}'
              AND table_schema <> 'information_schema'
            ORDER BY table_catalog, table_schema
            """
        )
        rows = cur.fetchall()
    return _require_single([(str(r[0]), str(r[1])) for r in rows])
