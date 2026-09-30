import nbformat as nbf
H = "import sys; sys.path.append('..')\nimport sqlite3, pandas as pd, matplotlib.pyplot as plt\ncon = sqlite3.connect('../data/stocksense.db')\nrd = lambda t: pd.read_sql(f'select * from {t}', con)"
def nb(name, cells):
    n = nbf.v4.new_notebook(); n.cells = [nbf.v4.new_markdown_cell(c[1]) if c[0] == "m" else nbf.v4.new_code_cell(c[1]) for c in cells]
    nbf.write(n, name)
nb("01_eda.ipynb", [("m", "# 01 - Data quality & EDA\nWhat is in the data, what was wrong, and what patterns exist."), ("c", H),
 ("m", "## Problems found and fixed (all fixed in code, see `src/pipeline.py`)"), ("c", "rd('data_quality')"),
 ("m", "## Sales table (one row per product per day)"), ("c", "s = rd('sales_daily'); s['date'] = pd.to_datetime(s.date); s.head()"),
 ("m", "## Sales are seasonal: units per month, per product"), ("c", "s['month'] = s.date.dt.month\ns.groupby(['month','sku_id']).units_sold.mean().unstack().plot(figsize=(9,4), title='Average daily units by month'); plt.show()"),
 ("m", "## Top sellers by revenue"), ("c", "s.groupby('sku_id').revenue.sum().sort_values().plot.barh(figsize=(7,4), color='#2BB3A3'); plt.show()"),
 ("m", "## Sale days vs normal days"), ("c", "(s[s.promo_flag==1].groupby('sku_id').units_sold.mean() / s[s.promo_flag==0].groupby('sku_id').units_sold.mean()).round(2)")])
nb("02_baseline.ipynb", [("m", "# 02 - Baseline forecast\nBaseline = *sell the same as the same week last year* (seasonal-naive). Metric = **WAPE** = total miss / total sales (lower is better). The model has to beat this."), ("c", H),
 ("c", "bt = rd('backtest'); bt['week'] = pd.to_datetime(bt.week)\nwape = lambda a, f: abs(a-f).sum() / a.sum()\nprint(f'Baseline WAPE: {wape(bt.units, bt.baseline):.1%} over {len(bt)} product-weeks (last 24 weeks)')"),
 ("m", "## Example: one product, last-year baseline vs actual"), ("c", "b = bt[bt.sku_id=='K01'].groupby('week')[['units','baseline']].mean(); b.plot(figsize=(9,3.5), color=['#4A5568','#FFC857']); plt.show()")])
nb("03_model.ipynb", [("m", "# 03 - Model, backtest and risk\nGradient Boosting on past sales (6/8/12/52 weeks ago), promo days, holidays and time of year. Every lag is at least 6 weeks old = **no data leakage**. Tested by **rolling-origin backtest**: 4 windows x 6 weeks."), ("c", H),
 ("c", "rd('model_scores').round(3)"), ("m", "Model WAPE lower than baseline WAPE means the model wins. The code picks the winner automatically."),
 ("m", "## Forecast for the next 6 weeks with 80% range"), ("c", "f = rd('forecast'); f['week'] = pd.to_datetime(f.week); x = f[f.sku_id=='K01'].set_index('week')\nax = x.forecast.plot(figsize=(8,3.5), color='#2BB3A3', lw=3); ax.fill_between(x.index, x.low, x.high, alpha=.2, color='#2BB3A3'); x.baseline.plot(ax=ax, ls='--', color='#FFC857'); plt.show()"),
 ("m", "## Risk decision for every product\nStockout risk uses the high forecast, overstock risk the low forecast. >= 0.5 is 'high'."), ("c", "rd('risk')[['product_name','weeks_of_cover','stockout_risk','overstock_risk','action','suggested_order_qty','sales_at_risk','capital_locked']]")])
