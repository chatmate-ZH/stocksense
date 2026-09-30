import hashlib, sqlite3, pandas as pd, plotly.graph_objects as go, streamlit as st
from pathlib import Path
DB = Path(__file__).parent / "data" / "stocksense.db"
st.set_page_config(page_title="StockSense", page_icon="📦", layout="wide")
TEAL, CORAL, LILAC, AMBER, SLATE = "#2BB3A3", "#FF8A7A", "#8E9AF7", "#FFC857", "#4A5568"
COLORS = {"Reorder now": CORAL, "Markdown / clear": LILAC, "Watch": AMBER, "Healthy": TEAL}
st.markdown("""<style>
/* 1. Hide Streamlit Deploy button, 3-dots menu, toolbar and footer */
#MainMenu, 
[data-testid="stMainMenu"],
[data-testid="stToolbar"],
[data-testid="stToolbarActions"],
[data-testid="stStatusWidget"],
[data-testid="stDecoration"],
#stDecoration,
.stDeployButton,
[data-testid="stDeployButton"],
[data-testid="stAppDeployButton"],
footer {
    display: none !important;
    visibility: hidden !important;
}
header[data-testid="stHeader"] {
    background: transparent !important;
}

/* 2. Layout and KPI cards - single straight line alignment */
.block-container {
    padding-top: 2rem;
    max-width: 1200px;
}
.kpi {
    background: #fff;
    border-radius: 16px;
    padding: 16px 18px;
    border: 1px solid #E6ECF2;
    min-height: 94px;
    display: flex;
    flex-direction: column;
    justify-content: center;
}
.kpi b {
    font-size: clamp(1.2rem, 1.75vw, 1.55rem);
    font-weight: 700;
    line-height: 1.2;
    display: block;
    color: #2D3748;
    white-space: nowrap !important;
    overflow: hidden;
    text-overflow: ellipsis;
}
.kpi span {
    color: #718096;
    font-size: 0.85rem;
    line-height: 1.25;
    margin-top: 4px;
    display: block;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.tip {
    background: #E8F7F5;
    border-radius: 12px;
    padding: 12px 16px;
    color: #2D3748;
    margin-bottom: 12px;
}
</style>""", unsafe_allow_html=True)

@st.cache_data
def q(sql):
    if not DB.exists():
        from src.pipeline import run_all; run_all()
    with sqlite3.connect(DB) as c: return pd.read_sql(sql, c)

def login():
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown("## 📦 StockSense")
        st.caption("Know what to reorder and what to clear - NorthBay Living")
        with st.form("login"):
            u = st.text_input("Username"); p = st.text_input("Password", type="password")
            if st.form_submit_button("Log in", use_container_width=True):
                row = q("select * from users"); h = hashlib.sha256(p.encode()).hexdigest()
                m = row[(row.username == u) & (row.password_hash == h)]
                if len(m): st.session_state.user = m.display_name.iloc[0]; st.rerun()
                else: st.error("Wrong username or password. Please try again.")
        st.info("Demo login - username: admin  |  password: stocksense@123")

def kpi(col, value, label): col.markdown(f'<div class="kpi"><b>{value}</b><span>{label}</span></div>', unsafe_allow_html=True)

def overview(risk, scores):
    a, b, c, d = st.columns(4)
    kpi(a, f"Rs&nbsp;{risk.sales_at_risk.sum():,.0f}", "Sales at risk (stockouts)"); kpi(b, f"Rs&nbsp;{risk.capital_locked.sum():,.0f}", "Cash locked in overstock")
    kpi(c, int((risk.action == "Reorder now").sum()), "Products to reorder now"); kpi(d, f"{(1 - scores.model_wape.iloc[0]):.0%}", "Forecast accuracy (backtest)")
    st.write("")
    left, right = st.columns([3, 2])
    fig = go.Figure()
    for x0, y0, col in [(0, .5, "#FFF1EF"), (.5, .5, "#FFF7E0"), (0, 0, "#E8F7F5"), (.5, 0, "#EEF0FE")]:
        fig.add_shape(type="rect", x0=x0, x1=x0+.5, y0=y0, y1=y0+.5, fillcolor=col, line_width=0, layer="below")
    for act, g in risk.groupby("action"):
        fig.add_trace(go.Scatter(x=g.overstock_risk, y=g.stockout_risk, mode="markers+text", name=act, text=g.product_name, textposition="top center",
            marker=dict(size=(g.sales_at_risk + g.capital_locked).clip(lower=0)**.5 / 8 + 16, color=COLORS[act], line=dict(color="white", width=2))))
    for t, x, y in [("REORDER NOW", .02, .97), ("WATCH", .52, .97), ("HEALTHY", .02, .03), ("MARKDOWN / CLEAR", .52, .03)]:
        fig.add_annotation(x=x, y=y, text=t, showarrow=False, xanchor="left", font=dict(color="#A0AEC0", size=11))
    fig.update_layout(title="Where every product stands", xaxis=dict(title="Overstock risk  →", range=[0, 1.02]), yaxis=dict(title="Stockout risk  →", range=[0, 1.02]),
                      height=430, margin=dict(t=50, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", legend=dict(orientation="h", y=-.2))
    left.plotly_chart(fig, use_container_width=True)
    n = risk.groupby("action").size().reindex(COLORS).fillna(0).reset_index(name="products")
    pie = go.Figure(go.Pie(labels=n.action, values=n.products, hole=.55, marker=dict(colors=[COLORS[x] for x in n.action]), sort=False))
    pie.update_layout(title="Products by action", height=430, margin=dict(t=50, b=10), paper_bgcolor="rgba(0,0,0,0)"); right.plotly_chart(pie, use_container_width=True)
    st.markdown('<div class="tip">💡 <b>How to read it:</b> top-left = order more soon, bottom-right = too much stock, bottom-left = fine.</div>', unsafe_allow_html=True)

def forecast_page(risk):
    cat = st.selectbox("Category", ["All"] + sorted(risk.category.unique()))
    opts = risk if cat == "All" else risk[risk.category == cat]
    name = st.selectbox("Product", opts.product_name.sort_values()); sku = opts[opts.product_name == name].sku_id.iloc[0]
    h = q(f"select week, units from weekly_sales where sku_id='{sku}' order by week").tail(26); f = q(f"select * from forecast where sku_id='{sku}' order by week")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=list(f.week) + list(f.week[::-1]), y=list(f.high) + list(f.low[::-1]), fill="toself", fillcolor="rgba(43,179,163,.18)", line_width=0, name="Likely range (80%)"))
    fig.add_trace(go.Scatter(x=h.week, y=h.units, name="Actual sales", line=dict(color=SLATE, width=3)))
    fig.add_trace(go.Scatter(x=f.week, y=f.baseline, name="Same week last year", line=dict(color=AMBER, dash="dash")))
    fig.add_trace(go.Scatter(x=f.week, y=f.forecast, name="Forecast", line=dict(color=TEAL, width=4)))
    fig.update_layout(title=f"{name}: units sold per week", height=420, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#fff", legend=dict(orientation="h", y=-.15), yaxis_title="Units per week")
    st.plotly_chart(fig, use_container_width=True)
    r = risk[risk.sku_id == sku].iloc[0]; a, b, c = st.columns(3)
    kpi(a, r.action, "Recommended action"); kpi(b, f"{r.weeks_of_cover} weeks", "Stock will last"); kpi(c, r.suggested_order_qty, "Suggested order (units)")

def alerts(risk):
    for act, note, cols in [("Reorder now", "Order these before they run out.", ["product_name", "on_hand", "on_order", "weeks_of_cover", "suggested_order_qty", "sales_at_risk"]),
                            ("Markdown / clear", "Too much stock - run a discount to free up cash.", ["product_name", "on_hand", "weeks_of_cover", "capital_locked"]),
                            ("Watch", "Demand is unpredictable - review by hand.", ["product_name", "on_hand", "weeks_of_cover"])]:
        g = risk[risk.action == act]; st.subheader(f"{act} ({len(g)})"); st.caption(note)
        if g.empty: st.success("Nothing here right now."); continue
        st.dataframe(g[cols].rename(columns=lambda c: c.replace("_", " ").title()), use_container_width=True, hide_index=True)

def data_page(scores):
    info = {"sku_master": "Product list", "sales_daily": "Sales per product per day", "inventory_snapshots": "Stock in the warehouse", "calendar": "Dates, holidays and sale events",
            "weekly_sales": "Sales added up per week", "forecast": "Next 6 weeks prediction", "risk": "Final action for each product", "data_quality": "Problems found and fixed"}
    t = st.selectbox("Table", list(info), format_func=lambda k: f"{k}  -  {info[k]}"); d = q(f"select * from {t} limit 500")
    st.dataframe(d, use_container_width=True, hide_index=True)
    s = scores.iloc[0]; st.subheader("How accurate is the forecast?")
    st.write(f"Tested on the last 24 weeks. Average miss: **{s.model_wape:.1%}** for our model vs **{s.baseline_wape:.1%}** for 'same as last year'. Lower is better. Winner: **{s.winner}**.")

def check_page(risk):
    st.markdown('<div class="tip">Type your own stock numbers to see how the advice changes. Nothing is saved.</div>', unsafe_allow_html=True)
    from src.scoring import score_sku
    name = st.selectbox("Product", risk.product_name.sort_values()); r = risk[risk.product_name == name].iloc[0]
    a, b, c = st.columns(3)
    oh = a.number_input("Units in warehouse", 0, 100000, int(r.on_hand)); oo = b.number_input("Units already ordered", 0, 100000, int(r.on_order))
    ld = c.number_input("Days for an order to arrive", 1, 120, int(r.lead_days))
    res = score_sku(r.sku_id, oh, oo, ld); k = res["risk"]; x, y, z, w = st.columns(4)
    kpi(x, k["action"], "Recommended action"); kpi(y, f'{k["weeks_of_cover"]}&nbsp;weeks', "Stock will last"); kpi(z, k["suggested_order_qty"], "Suggested order (units)"); kpi(w, f'Rs&nbsp;{k["sales_at_risk"] + k["capital_locked"]:,.0f}', "Rupees at stake")
    st.subheader("Next 6 weeks"); st.dataframe(pd.DataFrame(res["forecast"]).rename(columns={"week": "Week starting", "forecast": "Forecast units", "low": "Low", "high": "High"}), use_container_width=True, hide_index=True)

def main():
    if "user" not in st.session_state: return login()
    risk, scores = q("select * from risk"), q("select * from model_scores")
    st.sidebar.markdown(f"### 📦 StockSense\nHello, **{st.session_state.user}**")
    page = st.sidebar.radio("Go to", ["Overview", "Forecast", "Stock alerts", "Check a product", "Data & accuracy"])
    if st.sidebar.button("Log out"): st.session_state.clear(); st.rerun()
    st.title(page)
    {"Overview": lambda: overview(risk, scores), "Forecast": lambda: forecast_page(risk), "Stock alerts": lambda: alerts(risk), "Check a product": lambda: check_page(risk), "Data & accuracy": lambda: data_page(scores)}[page]()
main()
