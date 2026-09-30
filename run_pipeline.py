from src.pipeline import run_all
res, rk = run_all()
print(f"Baseline WAPE {res['baseline_wape']:.1%} | Model WAPE {res['model_wape']:.1%} | Winner: {res['winner']}")
print(rk.groupby('action').size().to_string()); print(f"Sales at risk Rs {rk.sales_at_risk.sum():,} | Capital locked Rs {rk.capital_locked.sum():,}")
