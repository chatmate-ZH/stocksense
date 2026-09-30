"""Score one product from the database. Used by the FastAPI service and the dashboard's 'Check a product' page."""
import json, sqlite3, pandas as pd
from src import risk
from src.pipeline import DB

def _q(sql, params=()):
    with sqlite3.connect(DB) as c: return pd.read_sql(sql, c, params=params)

def score_sku(sku_id, on_hand=None, on_order=None, lead_days=None):
    m = _q("select * from sku_master where sku_id=?", (sku_id,))
    if m.empty: raise KeyError(sku_id)
    fc = _q("select * from forecast where sku_id=?", (sku_id,)).sort_values("week")
    inv = _q("select * from inventory_snapshots where sku_id=? order by date desc limit 1", (sku_id,))
    for col, v in [("on_hand_units", on_hand), ("on_order_units", on_order), ("lead_time_days", lead_days)]:
        if v is not None: inv[col] = v            # what-if: override the stock numbers
    r = json.loads(risk.score(fc, inv, m).to_json(orient="records"))[0]
    return {"sku_id": sku_id, "product_name": r["product_name"], "risk": r,
            "forecast": json.loads(fc[["week", "forecast", "low", "high"]].to_json(orient="records"))}
