# Repository-native notebook design

The downloadable packaged bundle used a self-contained notebook that embedded copies of the quant engine and SQL schema so the `.ipynb` could run in isolation.

This GitHub repository deliberately removes that duplication. The Databricks source notebook imports `src/quant_platform/` and reads `sql/quant_platform_schema.sql` from the same Git folder. That makes the repository easier to maintain: a strategy-engine or schema change has one authoritative source instead of requiring synchronized edits inside a very large notebook blob.

Use `Databricks_OpenBB_Quant_Platform_Final.py` as the primary Databricks notebook. The `.ipynb` file is only a convenience launcher for it.
