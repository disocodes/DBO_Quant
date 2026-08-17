"""
Push outputs from NVIDIA-AI-Blueprints/portfolio-optimization into the Databricks
quant-platform Delta tables through a SQL Warehouse.

Designed for use from the user's separate GPU notebook/computer after it has
produced an efficient-frontier DataFrame.
"""
from __future__ import annotations

import json
import math
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional, Sequence

import numpy as np
import pandas as pd
from databricks import sql
from databricks.sdk.core import Config


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

KNOWN_COLUMN_ALIASES = {
    "regime": ["regime"],
    "solver": ["solver"],
    "solve_time_seconds": ["solve time", "solve_time", "solve_time_seconds", "solve time (s)"],
    "expected_return": ["return", "expected_return", "expected return"],
    "cvar": ["cvar", "CVaR", "cvar95", "cvar_95"],
    "objective_value": ["obj", "objective", "objective_value"],
    "risk_aversion": ["risk_aversion", "risk aversion"],
    "variance": ["variance"],
    "volatility": ["volatility", "vol"],
    "sharpe": ["sharpe", "sharpe_ratio", "sharpe ratio"],
}


def _clean_float(value):
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return None
    try:
        f = float(value)
        return f if math.isfinite(f) else None
    except Exception:
        return None


def _find_column(df: pd.DataFrame, aliases: Sequence[str]) -> Optional[str]:
    lower = {str(c).strip().lower(): c for c in df.columns}
    for alias in aliases:
        if alias.lower() in lower:
            return lower[alias.lower()]
    return None


@dataclass
class DatabricksOptimizationBridge:
    http_path: str
    catalog: str
    schema: str = "openbb_quant"
    profile: Optional[str] = None

    def _config(self) -> Config:
        return Config(profile=self.profile) if self.profile else Config()

    def _connect(self):
        cfg = self._config()
        hostname = cfg.host.replace("https://", "").replace("http://", "").rstrip("/")
        return sql.connect(
            server_hostname=hostname,
            http_path=self.http_path,
            credentials_provider=lambda: cfg.authenticate,
            _use_arrow_native_complex_types=False,
        )

    def _table(self, name: str) -> str:
        for identifier in (self.catalog, self.schema, name):
            if not _IDENTIFIER.match(identifier):
                raise ValueError(f"Unsafe Databricks identifier: {identifier!r}")
        return f"`{self.catalog}`.`{self.schema}`.`{name}`"

    def push_efficient_frontier(
        self,
        results_df: pd.DataFrame,
        *,
        objective: str = "mean_cvar",
        source_engine: str = "NVIDIA portfolio-optimization",
        source_notebook: str = "notebooks/efficient_frontier.ipynb",
        portfolio_id: Optional[str] = None,
        weight_columns: Optional[Iterable[str]] = None,
        metadata: Optional[dict] = None,
        portfolio_labels: Optional[dict[int, str]] = None,
    ) -> str:
        """
        Persist NVIDIA efficient-frontier results.

        NVIDIA's notebook result columns can evolve. This adapter maps common
        metric names and lets you explicitly supply asset weight columns. If no
        weight_columns are supplied, only frontier metrics are pushed.
        """
        if results_df is None or len(results_df) == 0:
            raise ValueError("results_df is empty")
        df = results_df.reset_index(drop=True).copy()
        run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        colmap = {canonical: _find_column(df, aliases) for canonical, aliases in KNOWN_COLUMN_ALIASES.items()}
        weights = list(weight_columns or [])
        missing_weights = [c for c in weights if c not in df.columns]
        if missing_weights:
            raise ValueError(f"weight_columns not found in results_df: {missing_weights}")
        labels = portfolio_labels or {}

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""INSERT INTO {self._table('optimization_runs')}
                    (optimization_run_id, portfolio_id, objective, source_engine, source_notebook,
                     status, created_at, completed_at, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    [run_id, portfolio_id, objective, source_engine, source_notebook,
                     "COMPLETED", now, now, json.dumps(metadata or {}, default=str)],
                )

                frontier_rows = []
                allocation_rows = []
                for point_id, row in df.iterrows():
                    def val(key):
                        col = colmap.get(key)
                        return row[col] if col is not None else None

                    meta_extra = {
                        str(c): row[c]
                        for c in df.columns
                        if c not in weights and c not in {x for x in colmap.values() if x is not None}
                    }
                    frontier_rows.append([
                        run_id,
                        int(point_id),
                        None if val("regime") is None else str(val("regime")),
                        None if val("solver") is None else str(val("solver")),
                        _clean_float(val("solve_time_seconds")),
                        _clean_float(val("expected_return")),
                        _clean_float(val("cvar")),
                        _clean_float(val("objective_value")),
                        _clean_float(val("risk_aversion")),
                        _clean_float(val("variance")),
                        _clean_float(val("volatility")),
                        _clean_float(val("sharpe")),
                        json.dumps(meta_extra, default=str),
                    ])
                    label = labels.get(int(point_id), f"frontier_{int(point_id):04d}")
                    for symbol in weights:
                        weight = _clean_float(row[symbol])
                        if weight is None:
                            continue
                        allocation_rows.append([
                            run_id, label, int(point_id), str(symbol), weight,
                            _clean_float(val("expected_return")),
                            _clean_float(val("volatility")),
                            _clean_float(val("cvar")),
                            _clean_float(val("sharpe")),
                            json.dumps({"source": source_engine}),
                        ])

                cur.executemany(
                    f"""INSERT INTO {self._table('efficient_frontier')}
                    (optimization_run_id, point_id, regime, solver, solve_time_seconds,
                     expected_return, cvar, objective_value, risk_aversion, variance,
                     volatility, sharpe, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    frontier_rows,
                )
                if allocation_rows:
                    cur.executemany(
                        f"""INSERT INTO {self._table('optimal_allocations')}
                        (optimization_run_id, portfolio_label, point_id, symbol, weight,
                         expected_return, volatility, cvar, sharpe, metadata_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        allocation_rows,
                    )
                cur.execute(
                    f"""INSERT INTO {self._table('external_ingestion_log')}
                    (ingestion_id, source_system, object_type, object_id, status, row_count, metadata_json, ingested_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    [str(uuid.uuid4()), source_engine, "efficient_frontier", run_id, "COMPLETED",
                     int(len(frontier_rows) + len(allocation_rows)), json.dumps(metadata or {}, default=str), now],
                )
        return run_id

    def push_allocation(
        self,
        optimization_run_id: str,
        weights: pd.Series | dict[str, float],
        *,
        portfolio_label: str = "selected_portfolio",
        point_id: Optional[int] = None,
        expected_return: Optional[float] = None,
        volatility: Optional[float] = None,
        cvar: Optional[float] = None,
        sharpe: Optional[float] = None,
        metadata: Optional[dict] = None,
    ) -> int:
        """Persist a chosen optimizer allocation even when weights are separate from the frontier DataFrame."""
        w = pd.Series(weights, dtype=float).dropna()
        if w.empty:
            raise ValueError("weights is empty")
        rows = [
            [
                optimization_run_id,
                portfolio_label,
                point_id,
                str(symbol),
                float(weight),
                _clean_float(expected_return),
                _clean_float(volatility),
                _clean_float(cvar),
                _clean_float(sharpe),
                json.dumps(metadata or {}, default=str),
            ]
            for symbol, weight in w.items()
            if math.isfinite(float(weight))
        ]
        if not rows:
            raise ValueError("weights contains no finite values")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    f"""INSERT INTO {self._table('optimal_allocations')}
                    (optimization_run_id, portfolio_label, point_id, symbol, weight,
                     expected_return, volatility, cvar, sharpe, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    rows,
                )
        return len(rows)

    def push_matrix(
        self,
        optimization_run_id: str,
        matrix: pd.DataFrame,
        matrix_name: str = "covariance",
    ) -> int:
        """Persist a covariance/correlation/other labelled matrix."""
        if matrix.index.empty or matrix.columns.empty:
            return 0
        rows = []
        for r in matrix.index:
            for c in matrix.columns:
                value = _clean_float(matrix.loc[r, c])
                if value is not None:
                    rows.append([optimization_run_id, matrix_name, str(r), str(c), value])
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    f"""INSERT INTO {self._table('optimization_matrix_entries')}
                    (optimization_run_id, matrix_name, row_symbol, column_symbol, value)
                    VALUES (?, ?, ?, ?, ?)""",
                    rows,
                )
        return len(rows)
