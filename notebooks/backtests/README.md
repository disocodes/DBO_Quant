# Backtest strategy notebooks

Each notebook in this folder represents one strategy research workflow. Run `notebooks/00_SETUP.py` and `notebooks/01_INGEST_DATA.py` first.

Every strategy notebook calls the same shared engine in `src/quant_platform/` and writes results to the same Unity Catalog tables. The notebook owns only the strategy logic and parameters.

## Add your own strategy

1. Copy `90_CUSTOM_STRATEGY_TEMPLATE.py`.
2. Rename the copy, for example `20_VALUE_MOMENTUM.py`.
3. Edit the strategy function and widgets.
4. Keep the function contract: `strategy(prices, params) -> target_weights_dataframe`.
5. Run all cells and keep the generated `run_id`.
6. Compare runs in `notebooks/portfolio/01_COMPARE_RUNS.py`.

Do not edit the common engine for ordinary strategy research.