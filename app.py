"""Sales Data Analysis System - Flask + Pandas backend.
Run:  python app.py   ->  open http://127.0.0.1:5000
Keep train.csv in the same folder as this file."""
import os, zlib
import numpy as np
import pandas as pd
from flask import Flask, jsonify, request, render_template

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(BASE, "train.csv")
STORE = os.path.join(BASE, "data", "sales_store.csv")   # created on first run
app = Flask(__name__)

# ---------------------------------------------------------------- data layer
def build_store():
    """First run: clean train.csv, add a Channel column, save to data/sales_store.csv.
    train.csv has NO online/offline column, so each ORDER is assigned a channel
    (~45% Online) using a fixed hash of its Order ID -> same result every run.
    If your own CSV already has a 'Channel' column, it is kept as is."""
    df = pd.read_csv(RAW).drop_duplicates()
    df["Order Date"] = pd.to_datetime(df["Order Date"], dayfirst=True)
    df["Ship Date"] = pd.to_datetime(df["Ship Date"], dayfirst=True)
    df["Postal Code"] = df["Postal Code"].fillna(5401).astype(int)   # missing ones are Burlington, VT
    df["Sales"] = pd.to_numeric(df["Sales"], errors="coerce")
    df = df.dropna(subset=["Sales", "Order Date"])
    if "Channel" not in df.columns:
        df["Channel"] = df["Order ID"].map(lambda o: "Online" if zlib.crc32(o.encode()) % 100 < 45 else "Offline")
    os.makedirs(os.path.dirname(STORE), exist_ok=True)
    df.to_csv(STORE, index=False, date_format="%Y-%m-%d")

def load():
    if not os.path.exists(STORE):
        build_store()
    return pd.read_csv(STORE, parse_dates=["Order Date", "Ship Date"])

DF = load()

def subset():
    ch = request.args.get("channel", "All")
    return DF if ch not in ("Online", "Offline") else DF[DF["Channel"] == ch]

COLS = {"Order ID": "order_id", "Order Date": "date", "Customer ID": "cid", "Customer Name": "customer",
        "Segment": "segment", "City": "city", "State": "state", "Region": "region",
        "Product Name": "product", "Category": "category", "Sales": "sales", "Channel": "channel"}

def to_rows(d):
    o = d[list(COLS)].rename(columns=COLS).copy()
    o["date"] = o["date"].dt.strftime("%d %b %Y")
    o["sales"] = o["sales"].round(2)
    return o.to_dict("records")

def monthly(d):
    return d.set_index("Order Date")["Sales"].resample("MS").sum()

# ------------------------------------------------------------------ dashboard
@app.get("/")
def home():
    return render_template("index.html")

@app.get("/api/summary")
def summary():
    d = subset()
    if d.empty:
        return jsonify(empty=True)
    m = monthly(d)
    reg = d.groupby("Region")["Sales"].sum().sort_values(ascending=False)
    prod = d.groupby("Product Name")["Sales"].sum().nlargest(10)
    cat = d.groupby("Category")["Sales"].sum()
    yearly = d.groupby(d["Order Date"].dt.year)["Sales"].sum()
    orders = d["Order ID"].nunique()
    v = d["Sales"]; cap = v.quantile(0.95)
    counts, edges = np.histogram(v[v <= cap], bins=20)
    insights = [
        f"Best-performing region: {reg.index[0]} (${reg.iloc[0]:,.0f}); weakest: {reg.index[-1]} (${reg.iloc[-1]:,.0f}).",
        f"Best-selling product: {prod.index[0]} (${prod.iloc[0]:,.0f}).",
        f"Highest sales month: {m.idxmax():%B %Y} (${m.max():,.0f}).",
        f"Median sale is ${v.median():,.0f} but the mean is ${v.mean():,.0f} - a few very large orders pull the average up.",
    ]
    if len(yearly) > 1:
        g = (yearly.iloc[-1] / yearly.iloc[-2] - 1) * 100
        insights.append(f"{yearly.index[-1]} sales are {g:+.1f}% versus {yearly.index[-2]}.")
    return jsonify(
        kpis=dict(total=round(v.sum(), 2), avg=round(v.mean(), 2), orders=int(orders),
                  customers=int(d["Customer ID"].nunique()), aov=round(v.sum() / orders, 2)),
        insights=insights,
        monthly=dict(labels=[x.strftime("%b %Y") for x in m.index], values=m.round(2).tolist()),
        region=dict(labels=reg.index.tolist(), values=reg.round(2).tolist()),
        category=dict(labels=cat.index.tolist(), values=cat.round(2).tolist()),
        products=dict(labels=prod.index.tolist(), values=prod.round(2).tolist()),
        hist=dict(labels=[f"${int(a)}-{int(b)}" for a, b in zip(edges[:-1], edges[1:])],
                  values=counts.tolist(), outliers=int((v > cap).sum()), cap=round(cap, 0)))

# ------------------------------------------------- records & customer details
@app.get("/api/records")
def records():
    d = subset()
    q = request.args.get("q", "").strip().lower()
    if q:
        d = d[d["Customer Name"].str.lower().str.contains(q, regex=False) |
              d["Customer ID"].str.lower().str.contains(q, regex=False) |
              d["Product Name"].str.lower().str.contains(q, regex=False) |
              d["Order ID"].str.lower().str.contains(q, regex=False)]
    d = d.sort_values("Order Date", ascending=False)
    size, page = 15, max(1, int(request.args.get("page", 1)))
    return jsonify(total=len(d), page=page, pages=max(1, -(-len(d) // size)),
                   rows=to_rows(d.iloc[(page - 1) * size: page * size]))

@app.get("/api/customers")
def customers():
    q = request.args.get("q", "").strip().lower()
    d = DF[DF["Customer Name"].str.lower().str.contains(q, regex=False) |
           DF["Customer ID"].str.lower().str.contains(q, regex=False)] if q else DF
    g = d.groupby(["Customer ID", "Customer Name"])["Sales"].sum().nlargest(10).reset_index()
    return jsonify([dict(cid=r["Customer ID"], name=r["Customer Name"], total=round(r["Sales"], 2)) for _, r in g.iterrows()])

@app.get("/api/customer/<cid>")
def customer(cid):
    d = DF[DF["Customer ID"] == cid].sort_values("Order Date", ascending=False)
    if d.empty:
        return jsonify(error="Customer not found"), 404
    r = d.iloc[0]
    by = d.groupby("Channel")["Sales"].sum()
    return jsonify(cid=cid, name=r["Customer Name"], segment=r["Segment"], city=r["City"], state=r["State"],
                   region=r["Region"], first=d["Order Date"].min().strftime("%d %b %Y"),
                   last=d["Order Date"].max().strftime("%d %b %Y"), orders=int(d["Order ID"].nunique()),
                   total=round(d["Sales"].sum(), 2), online=round(by.get("Online", 0), 2),
                   offline=round(by.get("Offline", 0), 2),
                   fav_category=d["Category"].mode().iloc[0], purchases=to_rows(d))

@app.post("/api/add")
def add_sale():
    global DF
    f = request.get_json()
    try:
        price = float(f["sales"]); date = pd.to_datetime(f["date"])
        assert price > 0 and f["product"].strip() and f["channel"] in ("Online", "Offline")
    except Exception:
        return jsonify(error="Please fill product, a positive price, date and channel."), 400
    cid = f.get("cid", "").strip()
    old = DF[DF["Customer ID"] == cid]
    if not old.empty:                       # existing customer -> reuse stored details
        c = old.iloc[0]; name, seg, city, state, region = c["Customer Name"], c["Segment"], c["City"], c["State"], c["Region"]
    else:                                   # new customer
        name = f.get("name", "").strip()
        if not name:
            return jsonify(error="New customer needs a name."), 400
        cid = cid or "NC-" + str(100000 + len(DF["Customer ID"].unique()))
        seg, city, state, region = f["segment"], f["city"], f["state"], f["region"]
    row = {"Row ID": int(DF["Row ID"].max()) + 1, "Order ID": f"CA-{date.year}-{900000 + len(DF)}",
           "Order Date": date, "Ship Date": date, "Ship Mode": "Standard Class", "Customer ID": cid,
           "Customer Name": name, "Segment": seg, "Country": "United States", "City": city, "State": state,
           "Postal Code": 0, "Region": region, "Product ID": "NEW-" + str(len(DF)), "Category": f["category"],
           "Sub-Category": f.get("sub", "Other") or "Other", "Product Name": f["product"].strip(),
           "Sales": price, "Channel": f["channel"]}
    DF = pd.concat([DF, pd.DataFrame([row])], ignore_index=True)
    DF.to_csv(STORE, index=False, date_format="%Y-%m-%d")
    return jsonify(ok=True, cid=cid, order_id=row["Order ID"])

# ---------------------------------------------------------------- forecasting
def seasonal_trend(s, h):
    """Linear trend x month-of-year seasonal index (pure numpy). Returns forecast, in-sample fit."""
    t = np.arange(len(s)); b, a = np.polyfit(t, s.values, 1)
    trend = a + b * t
    idx = pd.Series(s.values / trend, index=s.index).groupby(s.index.month).mean()
    idx = idx / idx.mean()
    fit = trend * idx.reindex(s.index.month).values
    fdates = pd.date_range(s.index[-1] + pd.offsets.MonthBegin(1), periods=h, freq="MS")
    fc = (a + b * np.arange(len(s), len(s) + h)) * idx.reindex(fdates.month).values
    return fdates, np.maximum(fc, 0), fit

@app.get("/api/forecast")
def forecast():
    d = subset(); h = int(request.args.get("months", 6))
    s = monthly(d)
    if len(s) < 24:
        return jsonify(error="Need at least 24 months of data to forecast.")
    fd, fc, fit = seasonal_trend(s, h)
    band = 1.28 * float(np.std(s.values - fit))            # ~80% range
    _, bt, _ = seasonal_trend(s.iloc[:-12], 12)             # back-test: hide last 12 months
    actual = s.iloc[-12:].values
    mape = float(np.mean(np.abs((actual - bt) / actual)) * 100)
    last_year = s.iloc[-12:-12 + h].sum() if h <= 12 else np.nan
    return jsonify(
        hist=dict(labels=[x.strftime("%b %Y") for x in s.index], values=s.round(0).tolist()),
        fc=dict(labels=[x.strftime("%b %Y") for x in fd], values=fc.round(0).tolist(),
                lo=np.maximum(fc - band, 0).round(0).tolist(), hi=(fc + band).round(0).tolist()),
        mape=round(mape, 1), next_total=round(float(fc.sum()), 0),
        growth=None if np.isnan(last_year) else round((fc.sum() / last_year - 1) * 100, 1))

# ----------------------------------------------------- why did sales go down?
@app.get("/api/decline")
def decline():
    d = subset(); s = monthly(d)
    yoy = (s / s.shift(12) - 1).dropna()
    worst = yoy[yoy < 0].nsmallest(5)
    yearly = d.groupby(d["Order Date"].dt.year)["Sales"].sum()
    years = [dict(year=int(y), sales=round(v, 0), change=None if i == 0 else round((v / yearly.iloc[i - 1] - 1) * 100, 1))
             for i, (y, v) in enumerate(yearly.items())]
    out = []
    for m, pct in worst.items():
        p = m - pd.DateOffset(years=1)
        cur = d[d["Order Date"].dt.to_period("M") == m.to_period("M")]
        old = d[d["Order Date"].dt.to_period("M") == p.to_period("M")]
        o1, o0 = cur["Order ID"].nunique(), old["Order ID"].nunique()
        a1, a0 = cur["Sales"].sum() / max(o1, 1), old["Sales"].sum() / max(o0, 1)
        oc, ac = (o1 / o0 - 1) * 100, (a1 / a0 - 1) * 100
        why = [f"Orders: {o0} -> {o1} ({oc:+.0f}%).  Average order value: ${a0:,.0f} -> ${a1:,.0f} ({ac:+.0f}%)."]
        why.append("Main cause: FEWER ORDERS (weaker footfall / traffic or fewer customers)." if oc <= ac
                   else "Main cause: SMALLER BASKETS (customers bought cheaper items or fewer big-ticket items).")
        for col in ["Region", "Category", "Sub-Category", "Segment"]:
            delta = cur.groupby(col)["Sales"].sum().sub(old.groupby(col)["Sales"].sum(), fill_value=0).sort_values()
            if delta.iloc[0] < 0:
                why.append(f"Biggest {col.lower()} drop: {delta.index[0]} (-${-delta.iloc[0]:,.0f}).")
        out.append(dict(month=m.strftime("%B %Y"), pct=round(pct * 100, 1), sales=round(cur["Sales"].sum(), 0), why=why))
    return jsonify(years=years, months=out)

# ------------------------------------------------------- dataset structure
DESC = {"Row ID": "Serial number of the row", "Order ID": "Unique ID of an order (one order can have many items)",
        "Order Date": "Date the order was placed", "Ship Date": "Date the order was shipped",
        "Ship Mode": "Shipping method (Standard, Second, First Class, Same Day)",
        "Customer ID": "Unique customer ID", "Customer Name": "Customer's full name",
        "Segment": "Customer type: Consumer, Corporate, Home Office", "Country": "Country of the customer",
        "City": "City of the customer", "State": "State of the customer", "Postal Code": "Postal / ZIP code",
        "Region": "Sales region: East, West, Central, South", "Product ID": "Unique product ID",
        "Category": "Furniture, Office Supplies or Technology", "Sub-Category": "Finer product group (Chairs, Phones...)",
        "Product Name": "Name of the product bought", "Sales": "Sales amount (price) of the item in $",
        "Channel": "ADDED by this system: Online or Offline (train.csv has no such column)"}

@app.get("/api/dataset")
def dataset():
    raw = pd.read_csv(RAW)
    cols = [dict(name=c, type=str(raw[c].dtype), missing=int(raw[c].isna().sum()), unique=int(raw[c].nunique()),
                 example=str(raw[c].iloc[0]), desc=DESC.get(c, "")) for c in raw.columns]
    cols.append(dict(name="Channel", type="object", missing=0, unique=2, example="Online / Offline", desc=DESC["Channel"]))
    steps = [f"Loaded train.csv with pandas: {len(raw):,} rows x {raw.shape[1]} columns.",
             f"Checked missing values: {int(raw.isna().sum().sum())} found (all in Postal Code, all Burlington, VT) - filled with 5401.",
             f"Removed duplicate rows: {int(raw.duplicated().sum())} found.",
             "Converted Order Date and Ship Date from text (dd/mm/yyyy) to real dates; Sales to numeric.",
             "Added a Channel column (Online/Offline) per order, saved as data/sales_store.csv.",
             "Grouped by month / region / category / product / customer and aggregated sum, mean, count."]
    return jsonify(rows=len(raw), cols=cols, steps=steps, start=DF["Order Date"].min().strftime("%d %b %Y"),
                   end=DF["Order Date"].max().strftime("%d %b %Y"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
