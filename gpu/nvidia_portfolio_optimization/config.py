from __future__ import annotations

import os
from pathlib import Path


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _load_env_file(path: Path) -> None:
    """Load a simple KEY=VALUE .env file without adding another dependency.

    Existing environment variables win over values in the file.
    """
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def find_repo_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "gpu" / "nvidia_portfolio_optimization").exists() and (candidate / "src" / "quant_platform").exists():
            return candidate
    raise RuntimeError("Could not locate DBO_Quant repository root")


def load_gpu_config(repo_root: Path | None = None) -> dict:
    root = repo_root or find_repo_root()
    _load_env_file(root / ".env")

    symbols = [s.strip().upper() for s in os.getenv("DBO_SYMBOLS", "SPY,QQQ,IEF,GLD").split(",") if s.strip()]
    profile = os.getenv("DATABRICKS_PROFILE", "").strip() or None
    http_path = os.getenv("DATABRICKS_HTTP_PATH", "").strip()
    catalog = os.getenv("DBO_CATALOG", os.getenv("FINANCE_CATALOG", "")).strip()
    schema = os.getenv("DBO_SCHEMA", os.getenv("FINANCE_SCHEMA", "openbb_quant")).strip()

    if not http_path:
        raise ValueError("Set DATABRICKS_HTTP_PATH in .env or the environment")
    if not catalog or catalog.startswith("REPLACE_WITH"):
        raise ValueError("Set DBO_CATALOG (or FINANCE_CATALOG) in .env")

    return {
        "http_path": http_path,
        "catalog": catalog,
        "schema": schema or "openbb_quant",
        "profile": profile,
        "portfolio_id": os.getenv("DBO_PORTFOLIO_ID", "").strip(),
        "symbols": symbols,
        "risk_aversion": float(os.getenv("DBO_RISK_AVERSION", "1.0")),
        "confidence": float(os.getenv("DBO_CONFIDENCE", "0.95")),
        "num_scenarios": int(os.getenv("DBO_NUM_SCENARIOS", "10000")),
        "frontier_points": int(os.getenv("DBO_FRONTIER_POINTS", "25")),
        "run_rebalancing": _parse_bool(os.getenv("DBO_RUN_REBALANCING"), False),
        "transaction_cost_factor": float(os.getenv("DBO_TRANSACTION_COST_FACTOR", "0.0")),
        "look_back_window": int(os.getenv("DBO_LOOK_BACK_WINDOW", "126")),
        "look_forward_window": int(os.getenv("DBO_LOOK_FORWARD_WINDOW", "21")),
        "push_results": _parse_bool(os.getenv("DBO_PUSH_RESULTS"), True),
    }
