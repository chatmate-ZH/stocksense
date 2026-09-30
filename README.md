# StockSense - Demand & Inventory Intelligence (NorthBay Living)

A simple dashboard that answers three questions for a home-products shop:
**How much will each product sell in the next 6 weeks? Which products will run out? Which ones are overstocked?**

## Data (small, everyday products)
12 products (bottle, mug, kettle, fan, cushion, bedsheet...) x ~3 years of daily sales, created by `src/data_gen.py`
(seed 42). It is intentionally messy (duplicates, missing values, inconsistent labels) and cleaned in code.
Four tables, as in the brief: `sales_daily`, `sku_master`, `calendar`, `inventory_snapshots`.

## Run it
```
pip install -r requirements.txt
python run_pipeline.py        # one command: clean -> weekly -> forecast -> risk -> data/stocksense.db
streamlit run app.py          # dashboard
```
Login: `admin` / `stocksense@123` (or `planner` / `northbay@123`). Passwords are stored hashed in the `users` table.

## How it works (explain it in 4 steps)
1. **Clean** - remove duplicate rows, recover missing units (revenue / price), fix category names. Logged in table `data_quality`.
2. **Baseline** - "sell the same as this week last year" (seasonal-naive).
3. **Model** - Gradient Boosting using past sales (6/8/12/52 weeks ago), promo days, holidays and time of year.
   All history features are at least 6 weeks old, so the model never peeks at the future (no leakage).
4. **Backtest** - rolling-origin test on the last 24 weeks (4 windows x 6 weeks). Metric: WAPE (lower = better).
   The better of model vs baseline is used automatically.

## Risk rules
- Weeks of cover = (on-hand + on-order) / forecast per week.
- **Stockout risk** rises when cover is shorter than lead time + 1 week (uses the high forecast = worst case).
- **Overstock risk** rises when cover is beyond ~8 weeks (uses the low forecast).
- Both >= 0.5 -> Watch; stockout only -> Reorder now; overstock only -> Markdown / clear; else Healthy.
- Rupees: sales at risk = missing units x list price; cash locked = units above 8 weeks of demand x unit cost.

## Database tables (`data/stocksense.db`, SQLite)
sku_master, sales_daily, calendar, inventory_snapshots, weekly_sales, forecast, backtest, risk, data_quality, model_scores, users.

## Deploy (free)
Push to GitHub -> share.streamlit.io -> New app -> pick repo, main file `app.py`. The database file is committed, so it loads instantly.

## Limitations
Simulated data; one inventory snapshot per week; forecast horizon is 6 weeks; no live client systems.

## Extra deliverables
| Folder | What |
|---|---|
| `reports/EDA_memo.md` | Data-quality & EDA memo (D2) with charts. Rebuild: `python reports/make_reports.py` |
| `reports/Executive_readout.md` | Rupee impact, actions, honest accuracy (D7) |
| `notebooks/` | `01_eda`, `02_baseline`, `03_model` - already run, outputs visible |
| `service/api.py` | FastAPI scoring service (D6) |
| `src/scoring.py` | Shared "score one product" function |

## Scoring API
```
uvicorn service.api:app --reload        # then open http://127.0.0.1:8000/docs
GET  /skus                              list products
GET  /score/K01                         6-week forecast + risk
GET  /score/K01?on_hand=2000&lead_days=7    what-if with your own stock numbers
POST /score/batch   {"sku_ids": ["K01","D04"]}
```
Bad input never crashes: unknown SKU -> 404 with a helpful message, negative/invalid numbers -> 422, unknown ids in a batch are listed under `not_found`.
Deploy on Render: New Web Service, build `pip install -r requirements.txt`, start `uvicorn service.api:app --host 0.0.0.0 --port $PORT`.
The dashboard's **Check a product** page uses the same function with number boxes.
