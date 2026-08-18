from __future__ import annotations

import os
import tomllib
from pathlib import Path


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def find_repo_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "optimization" / "portfolio_optimization").exists() and (candidate / "src" / "quant_platform").exists():
            return candidate
    raise RuntimeError("Could not locate DBO_Quant repository root")


def load_portfolio_config(repo_root: Path | None = None) -> dict:
    root = repo_root or find_repo_root()
    path = root / "optimization" / "portfolio_optimization" / "portfolio_config.toml"
    data = tomllib.loads(path.read_text())
    p = data.get("portfolio", {})
    e = data.get("execution", {})
    o = data.get("optimizer", {})
    r = data.get("rebalancing", {})
    out = data.get("output", {})
    solver = str(e.get("solver", "cpu")).strip().lower()
    if solver not in {"cpu", "gpu"}:
        raise ValueError("execution.solver must be 'cpu' or 'gpu'")
    return {
        "portfolio_id": str(p.get("portfolio_id", "")).strip(),
        "symbols": [str(x).strip().upper() for x in p.get("symbols", []) if str(x).strip()],
        "solver": solver,
        "risk_aversion": float(o.get("risk_aversion", 1.0)),
        "confidence": float(o.get("confidence", 0.95)),
        "num_scenarios": int(o.get("num_scenarios", 10000)),
        "frontier_points": int(o.get("frontier_points", 25)),
        "run_rebalancing": bool(r.get("enabled", False)),
        "transaction_cost_factor": float(r.get("transaction_cost_factor", 0.0)),
        "look_back_window": int(r.get("look_back_window", 126)),
        "look_forward_window": int(r.get("look_forward_window", 21)),
        "push_results": bool(out.get("push_results", True)),
    }


def load_external_connection(repo_root: Path | None = None, interactive: bool = True) -> dict:
    """Resolve external Databricks connection settings.

    Catalog/schema are optional overrides. If omitted, DBO_Quant discovers the
    canonical deployment created by notebooks/00_SETUP.py after authentication.
    """
    root = repo_root or find_repo_root()
    _load_env_file(root / ".env")
    profile = os.getenv("DATABRICKS_PROFILE", "").strip() or None
    host = os.getenv("DATABRICKS_HOST", "").strip() or None
    http_path = os.getenv("DATABRICKS_HTTP_PATH", "").strip()
    catalog = os.getenv("DBO_CATALOG", "").strip() or None
    schema = os.getenv("DBO_SCHEMA", "").strip() or None

    if interactive and not profile:
        if not host:
            host = input("Databricks workspace URL (https://...): ").strip()
        if not http_path:
            http_path = input("SQL Warehouse HTTP path (/sql/1.0/warehouses/...): ").strip()
    if not http_path:
        raise ValueError("A SQL Warehouse HTTP path is required for the external optimization route")

    return {
        "http_path": http_path,
        "catalog": catalog,
        "schema": schema,
        "profile": profile,
        "host": host,
        "auth_mode": "profile" if profile else "oauth",
    }


def load_external_config(repo_root: Path | None = None, interactive: bool = True) -> dict:
    cfg = load_portfolio_config(repo_root)
    cfg.update(load_external_connection(repo_root, interactive=interactive))
    return cfg
