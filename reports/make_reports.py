"""Builds charts + the EDA memo + the executive readout from the database. Run: python reports/make_reports.py"""
import sqlite3, pandas as pd, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from pathlib import Path
R = Path(__file__).parent; C = R / "charts"; C.mkdir(exist_ok=True)
con = sqlite3.connect(R.parent / "data" / "stocksense.db"); rd = lambda t: pd.read_sql(f"select * from {t}", con)
sales, wk, risk, dq, ms, m = rd("sales_daily"), rd("weekly_sales"), rd("risk"), rd("data_quality"), rd("model_scores").iloc[0], rd("sku_master")
sales["date"] = pd.to_datetime(sales.date); wk["week"] = pd.to_datetime(wk.week); name = dict(zip(m.sku_id, m.product_name))
TEAL, CORAL, LILAC, AMBER, SLATE = "#2BB3A3", "#FF8A7A", "#8E9AF7", "#FFC857", "#4A5568"
def save(f): plt.tight_layout(); plt.savefig(C / f, dpi=130); plt.close()
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "font.size": 10})

# 1 overall trend + seasonality
tot = wk.groupby("week").units.sum(); plt.figure(figsize=(8, 3.5)); plt.plot(tot.index, tot.values, color=TEAL, lw=2)
plt.title("All products: units sold per week"); plt.ylabel("Units per week"); save("01_total_weekly.png")
# 2 seasonal shapes
sales["month"] = sales.date.dt.month; sl = sales.groupby(["sku_id", "month"]).units_sold.mean().unstack(0); sl = sl / sl.mean()
plt.figure(figsize=(8, 3.5))
for s, c in [("K01", AMBER), ("B03", LILAC), ("D01", CORAL), ("K03", SLATE)]: plt.plot(sl.index, sl[s], color=c, lw=2.5, label=name[s])
plt.axhline(1, color="#CBD5E0", lw=1); plt.xticks(range(1, 13), list("JFMAMJJASOND")); plt.title("Sales by month (1.0 = average month)"); plt.legend(frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(.5, -.12)); save("02_seasonality.png")
# 3 top movers
last = sales[sales.date > sales.date.max() - pd.Timedelta(days=364)]; rev = last.groupby("sku_id").revenue.sum().sort_values(); top = rev.tail(6)
plt.figure(figsize=(8, 3.5)); plt.barh([name[s] for s in top.index], top.values / 1e5, color=TEAL); plt.xlabel("Revenue, last 12 months (Rs lakh)"); plt.title("Top sellers by revenue"); save("03_top_movers.png")
# 4 stock cover
rk = risk.sort_values("weeks_of_cover"); plt.figure(figsize=(8, 3.8))
plt.barh(rk.product_name, rk.weeks_of_cover, color=rk.action.map({"Reorder now": CORAL, "Markdown / clear": LILAC, "Watch": AMBER, "Healthy": TEAL}))
plt.axvline(8, color=SLATE, ls="--"); plt.text(8.3, 0, "8 weeks = too much", color=SLATE); plt.xlabel("Weeks of stock left"); plt.title("How long current stock will last"); save("04_stock_cover.png")

# numbers for the text
seas = lambda s: (sl[s].idxmax(), sl[s].max() / sl[s].min()); mo = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
pm, pr = seas("K01"); bm, br = seas("B03"); dm, dr = seas("D01")
lift = (sales[sales.promo_flag == 1].groupby("sku_id").units_sold.mean() / sales[sales.promo_flag == 0].groupby("sku_id").units_sold.mean()).mean()
wkend = sales[sales.date.dt.dayofweek >= 5].units_sold.mean() / sales[sales.date.dt.dayofweek < 5].units_sold.mean()
t3 = rev.tail(3); share = t3.sum() / rev.sum(); dead = risk[risk.action == "Markdown / clear"]; re = risk[risk.action == "Reorder now"]
SAR, LOCK = risk.sales_at_risk.sum(), risk.capital_locked.sum(); tbl = lambda d: d.to_markdown(index=False)
dqt = dq.rename(columns={"issue": "Issue", "rows_affected": "Rows", "how_handled": "How we handled it"}).to_markdown(index=False)

(R / "EDA_memo.md").write_text(f"""# Data-quality & EDA memo - NorthBay Living
*Prepared for the Head of Operations. Data: 12 products, daily sales Jan 2024 - Sep 2026.*

## 1. Data quality: what we found and fixed
{dqt}

All fixes are done in code (`src/pipeline.py`), so the same steps run again next month. Nothing was fixed by hand.

## 2. What the data shows
![Weekly sales](charts/01_total_weekly.png)
![Seasonality](charts/02_seasonality.png)
![Top sellers](charts/03_top_movers.png)
![Stock cover](charts/04_stock_cover.png)

## 3. Business insights (plain language)
1. **Demand follows the seasons.** Water bottles sell about {pr:.1f}x more in their best month ({mo[pm-1]}) than their weakest. Blankets peak in {mo[bm-1]} ({br:.1f}x swing). Cushion covers jump before Diwali ({mo[dm-1]}). Ordering the same amount every month will always be wrong for these.
2. **Three products bring in most of the money.** {", ".join(name[s] for s in t3.index[::-1])} give {share:.0%} of the last 12 months' revenue among the 12 products. A stockout here hurts most.
3. **Sales events work.** On sale days a product sells about {lift:.1f}x its normal daily amount. The Diwali sale (2-8 Nov) falls inside our 6-week window, so demand is expected to rise.
4. **Weekends are busier.** Weekend days sell about {wkend:.2f}x a weekday, so stock should be in place before Friday.
5. **Dead stock exists.** {", ".join(dead.product_name)} hold more than 8 weeks of stock. Together about Rs {LOCK:,.0f} of cash sits in them.

## 4. Limits
The data is simulated and covers about 2.7 years, so a full-year pattern is seen only twice. Forecasts for a new product would need category averages.
""", encoding="utf-8")

(R / "Executive_readout.md").write_text(f"""# Executive readout - StockSense
*For: Head of Operations and Finance, NorthBay Living*

## 1. The money at stake (next 6 weeks)
| | Amount |
|---|---|
| Sales we could lose from running out of stock | **Rs {SAR:,.0f}** |
| Cash locked in stock we will not sell soon | **Rs {LOCK:,.0f}** |

## 2. What to do now
**Order now - {len(re)} products** (stock will run out before a new order can arrive)

{tbl(re[["product_name", "weeks_of_cover", "suggested_order_qty", "sales_at_risk"]].rename(columns={"product_name": "Product", "weeks_of_cover": "Weeks of stock left", "suggested_order_qty": "Order (units)", "sales_at_risk": "Sales at risk (Rs)"}))}

**Discount or promote - {len(dead)} products** (far too much stock)

{tbl(dead[["product_name", "weeks_of_cover", "capital_locked"]].rename(columns={"product_name": "Product", "weeks_of_cover": "Weeks of stock", "capital_locked": "Cash locked (Rs)"}))}

The other {len(risk) - len(re) - len(dead)} products are healthy: no action needed.

## 3. How much can you trust the forecast?
We tested the forecast on the last 24 weeks of real history it had not seen. On average it was off by **{ms.model_wape:.0%}**. The simple method "sell what we sold this week last year" was off by {ms.baseline_wape:.0%}. So the forecast is better, but it is not perfect: each product also shows a likely range (low to high), and we plan orders for the high side.

## 4. Limits to keep in mind
- Built on sample data; results should be re-checked with NorthBay's own numbers.
- Forecast covers 6 weeks and assumes stock numbers and lead times are correct.
- Sales events are known in advance; surprise events will not be predicted.

## 5. Next steps
1. Approve the reorder list above and discount the two overstocked products.
2. Refresh the tool every month with new sales (one command).
3. Review accuracy after 6 weeks and adjust.

*Tool: the StockSense dashboard (log in, open "Stock alerts").*
""", encoding="utf-8")
print("reports done")
