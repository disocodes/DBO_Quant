# Run this AFTER your NVIDIA efficient-frontier notebook has produced its results DataFrame.
# Replace `results_df` with the variable returned by your version of create_efficient_frontier.

from nvidia_push_adapter import DatabricksOptimizationBridge

bridge = DatabricksOptimizationBridge(
    http_path="/sql/1.0/warehouses/REPLACE_WITH_WAREHOUSE_ID",
    catalog="REPLACE_WITH_CATALOG",
    schema="openbb_quant",
)

# If the NVIDIA results dataframe includes one column per asset containing weights,
# list those asset columns explicitly. If not, omit weight_columns and push frontier
# metrics first; allocations can be pushed separately after you extract them.
ASSET_WEIGHT_COLUMNS = []  # e.g. ["AAPL", "MSFT", "NVDA", ...]

optimization_run_id = bridge.push_efficient_frontier(
    results_df,
    objective="mean_cvar",
    source_engine="NVIDIA-AI-Blueprints/portfolio-optimization",
    weight_columns=ASSET_WEIGHT_COLUMNS,
    metadata={"purpose": "external GPU efficient frontier"},
)

print("Pushed optimization_run_id:", optimization_run_id)

# If the NVIDIA notebook returns a chosen weight vector separately from the frontier:
# bridge.push_allocation(
#     optimization_run_id,
#     optimal_weights,  # pandas Series or {symbol: weight}
#     portfolio_label="max_sharpe",
#     expected_return=chosen_return,
#     volatility=chosen_volatility,
#     cvar=chosen_cvar,
# )

# Optional, when you also have a labelled covariance/correlation matrix:
# bridge.push_matrix(optimization_run_id, covariance_df, matrix_name="covariance")
