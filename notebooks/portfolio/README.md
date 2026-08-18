# Portfolio notebooks

Prerequisites: run `notebooks/00_SETUP.py` once and keep market data current with `notebooks/01_INGEST_DATA.py`.

Recommended paths:

```text
Real portfolio
00_SAVE_PORTFOLIO.py
    ├─→ 02_MONTE_CARLO.py
    └─→ optional NVIDIA GPU notebook
            └─→ 03_NVIDIA_RESULTS.py

Strategy research
notebooks/backtests/*.py
    └─→ 01_COMPARE_RUNS.py
```

`portfolio_id` identifies a real saved portfolio. `run_id` identifies one strategy backtest. `optimization_run_id` identifies one NVIDIA/optimizer analysis. These IDs are intentionally separate and all persist in Unity Catalog.