"""Creates small, everyday NorthBay Living data (12 home products, ~3 years of daily sales)."""
import numpy as np, pandas as pd
from pathlib import Path
RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
LAST_DAY = pd.Timestamp("2026-09-27")   # a Sunday

# sku_id, name, category, base units/day, unit_cost, list_price, season pattern, stock cover (weeks), lead days
SKUS = [
 ("K01","Steel Water Bottle","Kitchen",9,180,399,"summer",1.5,14),
 ("K02","Coffee Mug","Kitchen",8,60,149,"winter",6,7),
 ("K03","Lunch Box","Kitchen",7,120,299,"flat",7,10),
 ("A01","Electric Kettle","Appliances",4,450,999,"winter",3,14),
 ("A02","Table Fan","Appliances",3,900,1799,"summer",26,21),
 ("D01","Cushion Cover","Decor",10,70,199,"festive",3.5,10),
 ("D02","Table Lamp","Decor",4,300,749,"festive",5,14),
 ("D03","Wall Clock","Decor",3,220,549,"flat",7,10),
 ("D04","Photo Frame","Decor",2,90,249,"flat",30,7),
 ("B01","Bedsheet Set","Bedding",5,350,899,"winter",6,14),
 ("B02","Pillow","Bedding",6,150,349,"flat",9,10),
 ("B03","Blanket","Bedding",4,400,999,"winter",4,21),
]
PROMOS = [("2024-01-22","2024-01-28","Republic Day Sale"),("2024-05-10","2024-05-19","Summer Sale"),
          ("2024-10-28","2024-11-03","Diwali Sale"),("2025-01-22","2025-01-28","Republic Day Sale"),
          ("2025-05-10","2025-05-19","Summer Sale"),("2025-10-15","2025-10-21","Diwali Sale"),
          ("2026-01-22","2026-01-28","Republic Day Sale"),("2026-05-10","2026-05-19","Summer Sale"),
          ("2026-11-02","2026-11-08","Diwali Sale")]
HOLIDAYS = ["2024-01-26","2024-03-25","2024-08-15","2024-10-02","2024-11-01","2024-12-25","2025-01-26","2025-03-14",
            "2025-08-15","2025-10-02","2025-10-20","2025-12-25","2026-01-26","2026-03-04","2026-08-15",
            "2026-10-02","2026-11-08","2026-12-25"]

def make_all(seed=42):
    rng = np.random.default_rng(seed); RAW.mkdir(parents=True, exist_ok=True)
    dates = pd.date_range("2024-01-01", LAST_DAY)
    cal = pd.DataFrame({"date": pd.date_range("2024-01-01", "2026-12-31")})
    cal["week"] = cal.date.dt.isocalendar().week.astype(int); cal["month"] = cal.date.dt.month
    cal["season"] = cal.month.map(lambda m: "Summer" if m in (3,4,5,6) else "Monsoon" if m in (7,8,9) else "Winter")
    cal["is_holiday"] = cal.date.isin(pd.to_datetime(HOLIDAYS)).astype(int); cal["promo_event"] = ""
    for s, e, n in PROMOS: cal.loc[cal.date.between(s, e), "promo_event"] = n
    promo = dict(zip(cal.date, cal.promo_event != ""))
    rows = []
    for sid, _, _, base, _, price, pat, *_ in SKUS:
        doy = dates.dayofyear.values
        f = {"summer": 1 + .5*np.sin(2*np.pi*(doy-80)/365), "winter": 1 - .5*np.sin(2*np.pi*(doy-80)/365),
             "festive": 1 + .6*np.exp(-((doy-300)/25)**2), "flat": np.ones(len(dates))}[pat]
        trend = 1 + .0003*np.arange(len(dates)); wk = np.where(dates.dayofweek >= 5, 1.15, 1.0)
        p = np.array([promo[d] for d in dates])
        units = rng.poisson(base*f*trend*wk*np.where(p, 1.4, 1.0))
        price_day = np.where(p, price*.85, price).round(0)
        rows.append(pd.DataFrame({"date": dates, "sku_id": sid, "units_sold": units.astype(float),
                                  "revenue": units*price_day, "unit_price": price_day, "promo_flag": p.astype(int)}))
    sales = pd.concat(rows, ignore_index=True)
    # deliberately messy, like a real extract
    sales.loc[rng.choice(len(sales), 30, replace=False), "units_sold"] = np.nan
    sales = pd.concat([sales, sales.sample(25, random_state=1)], ignore_index=True)
    master = pd.DataFrame([(s[0], s[1], s[2], "2023-06-01", s[4], s[5]) for s in SKUS],
        columns=["sku_id","product_name","category","launch_date","unit_cost","list_price"])
    master.loc[[1, 5, 9], "category"] = ["kitchen ", "DECOR", " bedding"]
    inv = []
    for k in range(4):   # 4 weekly snapshots, latest = 2026-09-27
        for s in SKUS:
            recent = sales[(sales.sku_id == s[0]) & (sales.date > LAST_DAY - pd.Timedelta(days=56))].units_sold.mean()*7
            total = s[7]*recent*(1 + .08*k); order = int(total*.15) if s[7] < 6 else 0
            inv.append((LAST_DAY - pd.Timedelta(weeks=k), s[0], int(total - order), order, s[8], int(recent*s[8]/7*1.3)))
    inv = pd.DataFrame(inv, columns=["date","sku_id","on_hand_units","on_order_units","lead_time_days","reorder_point"])
    for n, d in [("sales_daily", sales), ("sku_master", master), ("calendar", cal), ("inventory_snapshots", inv)]:
        d.to_csv(RAW / f"{n}.csv", index=False)
