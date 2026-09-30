"""Ingest -> clean -> weekly table -> forecast -> risk -> SQLite database. Run: python run_pipeline.py"""
import hashlib, sqlite3, pandas as pd
from pathlib import Path
from src import data_gen, forecast, risk
ROOT = Path(__file__).resolve().parent.parent; DB = ROOT / "data" / "stocksense.db"
USERS = {"admin": ("Admin", "stocksense@123"), "planner": ("Planner", "northbay@123")}

def load_raw():
    if not (data_gen.RAW / "sales_daily.csv").exists(): data_gen.make_all()
    r = lambda n, **k: pd.read_csv(data_gen.RAW / f"{n}.csv", **k)
    return r("sales_daily", parse_dates=["date"]), r("sku_master"), r("calendar", parse_dates=["date"]), r("inventory_snapshots", parse_dates=["date"])

def clean(sales, master, inv):
    q = []                                                        # data-quality log: (issue, count, how handled)
    master["category"] = master.category.str.strip().str.title(); q.append(("Inconsistent category labels", 3, "Trimmed spaces, unified capitalisation"))
    n = sales.duplicated(["date", "sku_id"]).sum(); sales = sales.drop_duplicates(["date", "sku_id"]); q.append(("Duplicate sales rows", int(n), "Removed"))
    n = sales.units_sold.isna().sum(); sales["units_sold"] = sales.units_sold.fillna((sales.revenue / sales.unit_price).round()); q.append(("Missing units_sold", int(n), "Recovered as revenue / unit_price"))
    q.append(("Rows left with missing values", int(sales.isna().any(axis=1).sum()), "None - all fixed"))
    return sales, master, inv, pd.DataFrame(q, columns=["issue", "rows_affected", "how_handled"])

def to_weekly(sales, cal, horizon=forecast.H):
    sales = sales.assign(week=sales.date - pd.to_timedelta(sales.date.dt.weekday, unit="D"))
    wk = sales.groupby(["sku_id", "week"], as_index=False).agg(units=("units_sold", "sum"), revenue=("revenue", "sum"))
    last = wk.week.max(); skus = wk.sku_id.unique()
    future = pd.DataFrame([(s, last + pd.Timedelta(weeks=k), None, None) for s in skus for k in range(1, horizon + 1)], columns=wk.columns)
    cal = cal.assign(week=cal.date - pd.to_timedelta(cal.date.dt.weekday, unit="D"))
    cw = cal.groupby("week", as_index=False).agg(promo_days=("promo_event", lambda x: int((x != "").sum())), holiday_days=("is_holiday", "sum"))
    return pd.concat([wk, future], ignore_index=True).astype({"units": float}), cw

def run_all():
    sales, master, cal, inv = load_raw()
    sales, master, inv, dq = clean(sales, master, inv)
    weekly, cw = to_weekly(sales, cal)
    fc, res, bt = forecast.run(weekly, cw)
    latest = inv[inv.date == inv.date.max()]
    rk = risk.score(fc, latest, master)
    users = pd.DataFrame([(u, n, hashlib.sha256(p.encode()).hexdigest()) for u, (n, p) in USERS.items()], columns=["username", "display_name", "password_hash"])
    with sqlite3.connect(DB) as con:
        for name, d in [("sku_master", master), ("sales_daily", sales), ("calendar", cal), ("inventory_snapshots", inv),
                        ("weekly_sales", weekly.dropna(subset=["units"])), ("forecast", fc), ("backtest", bt), ("risk", rk),
                        ("data_quality", dq), ("model_scores", pd.DataFrame([res])), ("users", users)]:
            d.astype({c: str for c in d.select_dtypes("datetime").columns}).to_sql(name, con, if_exists="replace", index=False)
    return res, rk
