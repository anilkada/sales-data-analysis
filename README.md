# 📊 Sales Data Analysis System

A web-based sales analytics dashboard built with **Flask**, **Pandas** and **NumPy** on the backend and **Chart.js** on the frontend. It loads a retail sales dataset (`train.csv`, 9,800 orders), cleans it, and lets you explore it through an interactive dashboard, forecast future sales, and find out why sales dropped in particular months.

## ✨ Features

| Tab | What it does |
|---|---|
| **Dashboard** | KPIs (total sales, orders, customers, average item price, average order value), auto-generated insights, monthly trend, region, category, top 10 products and a sales-distribution histogram |
| **Sales Records** | Searchable, paginated list of all sales (search by customer name/ID, product or order ID) |
| **Customer Details** | Search a customer and see their profile, total spend, online vs offline spend, favourite category and full purchase history |
| **Forecast** | 6-month sales forecast using *linear trend × monthly seasonality*, with an ~80% likely-range band and a back-test error (MAPE) |
| **Why Sales Dropped** | Year-over-year table plus the 5 worst months vs. the same month last year, explained by fewer orders vs. smaller baskets and the biggest region/category/segment drops |
| **Dataset** | Column-by-column description of the data (type, missing values, unique values, example) and the cleaning steps used |
| **+ Add Sale** | Record a new sale for an existing or new customer; it is saved immediately |

A global **Online / Offline / All** switch in the header filters every tab by sales channel.

## 🗂️ Project structure

```
sales-data-analysis/
├── app.py              # Flask backend + all API endpoints
├── requirements.txt    # Python dependencies
├── train.csv           # Raw dataset (9,800 rows, 18 columns)
├── templates/
│   └── index.html      # Single-page frontend (HTML + CSS + JS)
├── data/               # Created automatically on first run
│   └── sales_store.csv #   cleaned data + Channel column
├── .gitignore
└── README.md
```

## 🚀 Getting started

**Requirements:** Python 3.9+

```bash
# 1. Clone the repository
git clone https://github.com/<your-username>/sales-data-analysis.git
cd sales-data-analysis

# 2. (Optional) create a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python app.py
```

Then open **http://127.0.0.1:5000/** in your browser.

> `train.csv` must stay in the same folder as `app.py`. On the first run the app cleans it and creates `data/sales_store.csv`.

## 🧹 Data processing

1. Load `train.csv` with Pandas (9,800 rows × 18 columns).
2. Fill missing Postal Codes (all Burlington, VT) with `5401`.
3. Remove duplicate rows.
4. Convert `Order Date` / `Ship Date` from `dd/mm/yyyy` text to real dates; convert `Sales` to numeric.
5. **Add a `Channel` column (Online / Offline).** The original dataset has no such column, so each *order* is assigned a channel (~45% Online) using a fixed hash of its Order ID. This is deterministic (same result every run) and is a **simulated** attribute for demonstration. If your own CSV already has a `Channel` column, it is kept as is.
6. Save the result as `data/sales_store.csv`.

## 🔌 API endpoints

All `GET` endpoints that analyse sales accept an optional `?channel=Online|Offline|All`.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Dashboard page |
| GET | `/api/summary` | KPIs, insights and chart data |
| GET | `/api/records?page=&q=` | Paginated / searchable sales records |
| GET | `/api/customers?q=` | Top customers matching a search |
| GET | `/api/customer/<cid>` | Full profile of one customer |
| POST | `/api/add` | Add a new sale (JSON body) |
| GET | `/api/forecast?months=6` | Sales forecast with range and MAPE |
| GET | `/api/decline` | Year-over-year change and worst-month analysis |
| GET | `/api/dataset` | Dataset structure and processing steps |

## 🛠️ Tech stack

- **Backend:** Python, Flask, Pandas, NumPy
- **Frontend:** HTML, CSS, vanilla JavaScript, [Chart.js](https://www.chartjs.org/) (loaded from a CDN, so an internet connection is needed for charts)

## ⚠️ Notes & limitations

- Sales added through **+ Add Sale** are written to `data/sales_store.csv`. Delete that file to reset to the original dataset.
- The forecast needs at least 24 months of data in the selected channel.
- The app runs Flask in debug mode for local use; do not deploy it to production as is.

## 📄 License

Add a license of your choice (e.g. MIT) before publishing.


## Deploying on Render

1. Push this project folder to a GitHub repository.
2. In Render, create a **New Web Service** and connect the repository.
3. Set the runtime to **Python 3**.
4. Set the build command to `pip install -r requirements.txt`.
5. Set the start command to `gunicorn app:app --bind 0.0.0.0:$PORT`.
6. Choose an available instance plan and deploy.

Keep `train.csv` in the same directory as `app.py`. The app creates `data/sales_store.csv` automatically on startup if it does not exist. On Render's free instance, files written by the app may be lost when the service restarts or redeploys; sales entered through **Add Sale** are therefore demo data, not durable records.
