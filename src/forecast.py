"""Weekly demand forecast: seasonal-naive baseline vs gradient boosting, tested with rolling-origin backtest."""
import numpy as np, pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
H = 6   # forecast horizon (weeks). All lags are >= H, so a future week never uses unknown data (no leakage).
LAGS = ["lag6", "lag8", "lag12", "lag52", "roll4"]
FEATS = LAGS + ["promo_days", "holiday_days", "woy_sin", "woy_cos"]

def add_features(weekly):
    df = weekly.sort_values(["sku_id", "week"]).copy(); g = df.groupby("sku_id")["units"]
    for l in (6, 8, 12, 52): df[f"lag{l}"] = g.shift(l)
    df["roll4"] = pd.concat([g.shift(k) for k in (6, 7, 8, 9)], axis=1).mean(axis=1)
    w = df.week.dt.isocalendar().week.astype(int)
    df["woy_sin"], df["woy_cos"] = np.sin(2*np.pi*w/52), np.cos(2*np.pi*w/52)
    return df

def fit_predict(df, train_end, test_weeks):
    tr = df[(df.week <= train_end) & df.units.notna() & df.lag52.notna()]
    scale = tr.groupby("sku_id").units.mean()            # per-product size, from training weeks only
    def X(d):
        x = d[FEATS].copy(); s = d.sku_id.map(scale).values
        for c in LAGS: x[c] = x[c].values / s
        return x
    m = GradientBoostingRegressor(n_estimators=200, max_depth=3, learning_rate=.05, subsample=.8, random_state=42)
    m.fit(X(tr), tr.units / tr.sku_id.map(scale))
    te = df[df.week.isin(test_weeks)].copy(); te["scale"] = te.sku_id.map(scale)
    te["model"] = np.clip(m.predict(X(te)), 0, None) * te.scale; te["baseline"] = te.lag52
    return te

def wape(a, f): return float(np.abs(a - f).sum() / a.sum())
def bias(a, f): return float((f - a).sum() / a.sum())

def run(weekly, cal_week, n_origins=4):
    df = add_features(weekly.merge(cal_week, on="week", how="left")); last = weekly.dropna(subset=["units"]).week.max()
    bt = []
    for i in range(n_origins):
        origin = last - pd.Timedelta(weeks=H*(i+1))
        te = fit_predict(df, origin, [origin + pd.Timedelta(weeks=k) for k in range(1, H+1)]); te["origin"] = origin; bt.append(te)
    bt = pd.concat(bt).dropna(subset=["units", "baseline"])
    res = {"baseline_wape": wape(bt.units, bt.baseline), "model_wape": wape(bt.units, bt.model),
           "baseline_bias": bias(bt.units, bt.baseline), "model_bias": bias(bt.units, bt.model), "backtest_rows": len(bt)}
    res["winner"] = "model" if res["model_wape"] < res["baseline_wape"] else "baseline"
    err = (bt.units - bt.model) / bt.scale; q10, q90 = err.quantile(.1), err.quantile(.9)   # 80% interval from backtest errors
    fut = fit_predict(df, last, [last + pd.Timedelta(weeks=k) for k in range(1, H+1)])
    fut["forecast"] = fut[res["winner"]]; fut["low"] = np.clip(fut.forecast + q10*fut.scale, 0, None); fut["high"] = fut.forecast + q90*fut.scale
    out = fut[["sku_id", "week", "forecast", "low", "high", "baseline", "model"]].round({c: 1 for c in ["forecast","low","high","baseline","model"]})
    return out, res, bt[["sku_id", "week", "units", "model", "baseline", "origin"]].round({c: 1 for c in ["units","model","baseline"]})
