# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a multi-app Python/Streamlit business analytics system for Thai e-commerce operations, tracking sales across TikTok, Shopee, and Lazada platforms. It consists of three independent Streamlit apps sharing one PostgreSQL server (each app connects with its own config — see Database Connections below).

The `onpermise` branch (current) migrates data ingestion from Google Drive to local Excel files on disk. Google Drive/Sheets code paths still exist but local-file mode is the default.

## Apps and Entry Points

| App | Entry Point | Default Port | Purpose |
|-----|-------------|--------------|---------|
| Profit Income | `profit_income/streamlit_app.py` | 8501 | Sales/revenue dashboard |
| Stock JST | `stock_jst/app.py` | 8502 | Inventory management |
| Shop Dashboard | `shop_dashboard/app.py` | 8503 | Analytics & monthly reports |

## Common Commands

```bash
# Setup
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Start PostgreSQL
docker-compose up -d

# Run each app (separate terminals)
streamlit run profit_income/streamlit_app.py
streamlit run stock_jst/app.py
streamlit run shop_dashboard/app.py

# Initialize Shop Dashboard DB schema (outside Streamlit)
python shop_dashboard/scripts/init_db_script.py
```

No test runner or linter is configured — run apps directly to verify behavior.

## Data Flow (important)

Each app ingests platform export Excel files from a local directory, parses them, and upserts into PostgreSQL. Reports then read from the DB.

- **Profit Income** reads from `data/{PLATFORM}/{Orders|Income}/{ShopName}/` at the repo root (PLATFORM = TIKTOK/SHOPEE/LAZADA). `utils/local_file_manager.py` manages the folder tree; the "จัดการไฟล์ & Sync" tab uploads files and triggers ingestion. `utils/processors.py` holds the platform-specific column parsing — edit here when a platform changes its export format. Business rules live in the processors too (e.g., cancelled orders get zeroed financials and are excluded from the 10-baht/order ค่าดำเนินการ fee).
- **Shop Dashboard** reads from `shop_dashboard/local_data/{sales,ads}/` plus `local_data/master_item.xlsx`. `app.py` hardcodes `data_source_mode = "MODE_LOCAL"`; the Drive loaders in `modules/data_loader.py` (folder IDs, master sheet URL at the top of that file) remain, and the Master Item Google Sheet is still synced to DB on the refresh button.
- **Stock JST** syncs from Google Sheets (IDs in `stock_jst/config.py`).

## Architecture

### Profit Income (modular — reference pattern for other apps)
```
profit_income/
├── streamlit_app.py          # Thin entry point; mounts tabs
├── utils/                    # Service layer
│   ├── db_service.py         # PostgreSQL read/write (upserts via pg_insert)
│   ├── processors.py         # Platform-specific order/income parsing
│   ├── local_file_manager.py # data/ folder tree management
│   ├── drive_service.py      # Google Drive API (legacy path)
│   └── data_helpers.py       # Excel/CSV I/O
└── views/                    # One file per tab (dashboard, details, ads, costs, file_manager…)
```

### Shop Dashboard (mid-size modular)
- `modules/auth.py` + `modules/otp2.py` — 2-step OTP authentication via email (SMTP, `[gmail]` secrets)
- `modules/data_loader.py` — local-file and Drive/Sheets loading, DB ingestion
- `modules/database.py` — engine/DDL; resolves connection from `st.secrets["postgres"]`, or parses `.streamlit/secrets.toml` directly when run as a plain script
- `modules/processing.py` — report calculations
- `views/` — one file per report page (report_month, report_ads, report_daily, yearly_pnl, monthly_pnl, commission, master_item, file_manager…)

### Stock JST (partially refactored monolith)
- `app.py` (~1200 lines) still holds most UI and logic; extraction into `views/` (daily_sales, purchase_orders, stock_report) and `models.py`/`services.py` has started — continue that direction for new code
- `config.py` holds DB URLs, Google Sheet IDs, and Excel column mappings (edit here when upstream sheets change)
- `database.py` falls back to SQLite (`stock_jst.db`) automatically when PostgreSQL is unreachable

## Database Connections (differ per app)

Docker Compose runs PostgreSQL 15 (`admin:mos2025@localhost:5432`, db `profit_income`, volume `pgdata/`, init SQL in `admin_scripts/`).

| App | Secrets key | Fallback |
|-----|-------------|----------|
| Profit Income | `db_url` (string) | env `DB_URL`, then `postgresql://admin:mos2025@localhost:5432/profit_income` |
| Shop Dashboard | `[postgres]` table (`user`/`password`/`host`/`port`/`dbname`) | `postgres:postgres@localhost:5432/shop_dashboard` |
| Stock JST | `DATABASE_URL` (string) | localhost default, then SQLite |

## Key Patterns

- **Streamlit caching**: `@st.cache_resource` for DB connections/clients, `@st.cache_data(ttl=...)` for fetched data. The refresh buttons call `st.cache_data.clear()`.
- **Secrets**: All credentials live in each app's `.streamlit/secrets.toml` (gitignored). Never commit this file. Apps fall back to env vars or localhost defaults when secrets are absent.
- **UI language**: All user-facing strings are in Thai. Keep new UI text in Thai. Data files use Thai Buddhist-era years (e.g., 2569 = 2026) in filenames and sometimes in cell values — processors handle the conversion.

## Configuration Files

- `.streamlit/config.toml` — headless mode, CORS/XSRF disabled, dark theme, primary color `#FF4B4B`
- `docker-compose.yml` — PostgreSQL 15 container
- `stock_jst/config.py` — Google Sheet IDs and Excel column name mappings

## External Integrations

- **Google Sheets/Drive** — legacy data source for orders/ad spend; still used for Stock JST inventory and the Shop Dashboard Master Item sheet; uses a service account JSON stored in secrets
- **SMTP email** — used by `shop_dashboard` for OTP delivery to `[gmail].authorized_emails` only

## Deployment

See `DEPLOYMENT.md` for the full Ubuntu 24.04 + Nginx + systemd setup: apps served at `/profit`, `/stock`, `/shop` behind Nginx, each as its own systemd service with a dedicated venv.
