"""Simple, explainable stock-risk rules. Weeks of cover = units in stock / forecast units per week."""
import numpy as np, pandas as pd
OVERSTOCK_WEEKS = 8   # holding more than 8 weeks of demand is "too much"

def score(fc, inv, master):
    r = []
    for sku, f in fc.groupby("sku_id"):
        i = inv[inv.sku_id == sku].iloc[0]; m = master[master.sku_id == sku].iloc[0]
        lead_w = i.lead_time_days / 7; stock = i.on_hand_units + i.on_order_units
        avg, avg_hi, avg_lo = f.forecast.mean(), f.high.mean(), max(f.low.mean(), .1)
        # worst case for each risk: stockout uses the HIGH forecast, overstock uses the LOW forecast
        so = float(np.clip(1 - (stock/avg_hi) / (2*(lead_w + 1)), 0, 1))
        os_ = float(np.clip((i.on_hand_units/avg_lo) / (2*OVERSTOCK_WEEKS*1.5), 0, 1))
        hi_so, hi_os = so >= .5, os_ >= .5
        quad = "Watch" if hi_so and hi_os else "Reorder now" if hi_so else "Markdown / clear" if hi_os else "Healthy"
        short = max(0, avg_hi*(lead_w + 1) - stock); excess = max(0, i.on_hand_units - avg*OVERSTOCK_WEEKS)
        r.append(dict(sku_id=sku, product_name=m.product_name, category=m.category, on_hand=int(i.on_hand_units),
            on_order=int(i.on_order_units), lead_days=int(i.lead_time_days), weekly_forecast=round(avg, 1),
            weeks_of_cover=round(stock/avg, 1), stockout_risk=round(so, 2), overstock_risk=round(os_, 2), action=quad,
            suggested_order_qty=int(np.ceil(max(0, avg*(lead_w + 4) - stock))) if quad in ("Reorder now", "Watch") else 0,
            sales_at_risk=round(short*m.list_price), capital_locked=round(excess*m.unit_cost)))
    return pd.DataFrame(r).sort_values(["action", "sales_at_risk"], ascending=[True, False])
