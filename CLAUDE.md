# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a multi-app Python/Streamlit business analytics system for Thai e-commerce operations, tracking sales across TikTok, Shopee, and Lazada platforms. It consists of three independent Streamlit apps sharing a PostgreSQL database.

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
```

No test runner or linter is configured — run apps directly to verify behavior.

## Architecture

### Profit Income (modular — reference pattern for other apps)
```
profit_income/
├── streamlit_app.py          # Thin entry point; mounts views
├── utils/                    # Service layer
│   ├── db_service.py         # PostgreSQL read/write
│   ├── processors.py         # Platform-specific order parsing
│   ├── drive_service.py      # Google Drive API
│   └── data_helpers.py       # Excel/CSV I/O
└── views/                    # One file per tab (dashboard, details, ads, costs…)
```

### Stock JST (monolithic)
- `app.py` (~1200 lines) handles all UI and logic
- `config.py` holds DB URLs, Google Sheet IDs, and Excel column mappings
- `database.py` sets up SQLAlchemy with SQLite fallback when PostgreSQL is unavailable

### Shop Dashboard (mid-size modular)
- `modules/auth.py` — 2-step OTP authentication via email (SMTP)
- `modules/data_loader.py` — Google Drive/Sheets sync
- `views/` — one file per report page

## Key Patterns

- **Streamlit caching**: Use `@st.cache_resource` for DB connections/clients and `@st.cache_data(ttl=...)` for fetched data.
- **Secrets**: All credentials live in `.streamlit/secrets.toml` (gitignored). Never commit this file. Apps fall back to env vars or localhost defaults when secrets are absent.
- **Database**: PostgreSQL 15 via Docker (`admin:mos2025@localhost:5432`). Stock JST falls back to SQLite automatically if PostgreSQL is unreachable.
- **UI language**: All user-facing strings are in Thai. Keep new UI text in Thai.

## Configuration Files

- `.streamlit/config.toml` — headless mode, CORS/XSRF disabled, dark theme, primary color `#FF4B4B`
- `docker-compose.yml` — PostgreSQL 15 with `pgdata/` volume
- `stock_jst/config.py` — Google Sheet IDs and Excel column name mappings (edit here when upstream sheets change)

## Secrets Structure (`.streamlit/secrets.toml`)

```toml
# Profit Income
db_url = "postgresql://..."

# Shop Dashboard
[gmail]
authorized_emails = [...]
# + SMTP credentials and Google service account fields

# Stock JST
DATABASE_URL = "postgresql://..."
# + Google service account JSON fields
```

## External Integrations

- **Google Sheets/Drive** — data source for orders, inventory, and ad spend; uses a service account JSON stored in secrets
- **SMTP email** — used by `shop_dashboard` for OTP delivery to `authorized_emails` only

## Deployment

See `DEPLOYMENT.md` for the full Ubuntu 24.04 + Nginx + systemd setup. Each app runs as its own systemd service with a dedicated venv.
