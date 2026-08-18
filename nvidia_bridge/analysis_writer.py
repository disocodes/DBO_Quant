from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import uuid
from typing import Any

import numpy as np
import pandas as pd

from .nvidia_push_adapter import DatabricksOptimizationBridge


def _finite(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except Exception:
        return None


class NvidiaAnalysisWriter:
    """Persist NVIDIA portfolio-optimization backtest and rebalancing outputs."""

    def __init__(self, bridge: DatabricksOptimizationBridge):
        self.bridge = bridge

    def push_backtest_metrics(self, optimization_run_id: str, backtest_results: pd.DataFrame) -> int:
        if backtest_results is None or backtest_results.empty:
            return 0
        rows = []
        frame = backtest_results.copy()
        if frame.index.name or not isinstance(frame.index, pd.RangeIndex):
            frame = frame.reset_index()
        for idx, row in frame.iterrows():
            portfolio_name = str(
                row.get("portfolio_name", row.get("portfolio", row.get("name", f"portfolio_{idx}")))
            )
            for col, value in row.items():
                if col in {"portfolio_name", "portfolio", "name"}:
                    continue
                numeric = _finite(value)
                rows.append([
                    optimization_run_id,
                    portfolio_name,
                    str(col),
                    numeric,
                    "" if numeric is not None else str(value),
                ])
        if not rows:
            return 0
        with self.bridge._connect() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    f"""INSERT INTO {self.bridge._table('optimization_backtest_metrics')}
                    (optimization_run_id, portfolio_name, metric_name, metric_value, metric_text)
                    VALUES (?, ?, ?, ?, ?)""",
                    rows,
                )
        return len(rows)

    def push_rebalancing(
        self,
        *,
        optimization_run_id: str | None,
        results_dataframe: pd.DataFrame,
        re_optimize_dates: list,
        cumulative_portfolio_value: pd.Series | pd.DataFrame,
        portfolio_id: str | None = None,
        transaction_cost_factor: float = 0.0,
        look_back_window: int = 126,
        look_forward_window: int = 21,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        rebalance_run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with self.bridge._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""INSERT INTO {self.bridge._table('optimization_rebalance_runs')}
                    (rebalance_run_id, optimization_run_id, portfolio_id, source_engine,
                     transaction_cost_factor, look_back_window, look_forward_window, created_at, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    [
                        rebalance_run_id,
                        optimization_run_id,
                        portfolio_id,
                        "NVIDIA-AI-Blueprints/portfolio-optimization",
                        float(transaction_cost_factor),
                        int(look_back_window),
                        int(look_forward_window),
                        now,
                        json.dumps(metadata or {}, default=str),
                    ],
                )

                event_rows = []
                df = results_dataframe.copy() if results_dataframe is not None else pd.DataFrame()
                dates = list(re_optimize_dates or [])
                for i in range(max(len(df), len(dates))):
                    payload = {}
                    if i < len(df):
                        payload = {str(k): v for k, v in df.iloc[i].to_dict().items()}
                    event_date = None
                    if i < len(dates):
                        try:
                            event_date = pd.Timestamp(dates[i]).date()
                        except Exception:
                            event_date = None
                    event_rows.append([
                        rebalance_run_id,
                        i,
                        event_date,
                        json.dumps(payload, default=str),
                    ])
                if event_rows:
                    cur.executemany(
                        f"""INSERT INTO {self.bridge._table('optimization_rebalance_events')}
                        (rebalance_run_id, event_index, event_date, event_json)
                        VALUES (?, ?, ?, ?)""",
                        event_rows,
                    )

                if isinstance(cumulative_portfolio_value, pd.DataFrame):
                    if cumulative_portfolio_value.shape[1] == 0:
                        series = pd.Series(dtype=float)
                    else:
                        series = cumulative_portfolio_value.iloc[:, 0]
                else:
                    series = pd.Series(cumulative_portfolio_value)
                daily_rows = []
                for dt, value in series.dropna().items():
                    numeric = _finite(value)
                    if numeric is None:
                        continue
                    try:
                        date_value = pd.Timestamp(dt).date()
                    except Exception:
                        continue
                    daily_rows.append([rebalance_run_id, date_value, numeric])
                if daily_rows:
                    cur.executemany(
                        f"""INSERT INTO {self.bridge._table('optimization_rebalance_daily')}
                        (rebalance_run_id, date, portfolio_value)
                        VALUES (?, ?, ?)""",
                        daily_rows,
                    )
        return rebalance_run_id
