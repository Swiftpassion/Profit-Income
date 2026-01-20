# Deployment Guide for Profit-Income Project

## Project Overview

This repository contains three Streamlit applications:

1. **Profit-Income (Main App)**: `profit_income/streamlit_app.py`
2. **JST Stock System**: `stock_jst/app.py`
3. **Shop Dashboard**: `shop_dashboard/app.py`

## Prerequisites

* Python 3.9+
* PostgreSQL (for Profit-Income app)

## Installation

1. **Clone the repository**.
2. **Install dependencies**:

    ```bash
    pip install -r requirements.txt
    ```

    * `pyproject.toml` is also available for modern build tools.

## Configuration

### 1. Profit-Income App

* **Database**: Uses PostgreSQL.
* **Connection**: Configured in `profit_income/utils/db_service.py`.
  * **Local**: Defaults to `postgresql://admin:mos2025@localhost:5432/profit_income`.
  * **Production**: Set `DB_URL` in environment variables or `secrets.toml`.

### 2. JST Stock System (`stock_jst`)

* **Secrets**: Configured in `stock_jst/.streamlit/secrets.toml`.
* **Contains**: GCP Service Account credentials and Email settings.

### 3. Shop Dashboard (`shop_dashboard`)

* **Secrets**: Configured in `shop_dashboard/.streamlit/secrets.toml`.
* **Contains**: GCP Service Account credentials.

## Running the Applications

### Local Development (with Docker DB)

1. **Start Database**:

    ```bash
    docker-compose up -d
    ```

2. **Run Main App**:

    ```bash
    streamlit run profit_income/streamlit_app.py
    ```

3. **Run Sub-Apps**:

    ```bash
    streamlit run stock_jst/app.py
    streamlit run shop_dashboard/app.py
    ```

### Production Deployment

* **Configuration**: Ensure `.streamlit/config.toml` is present (headless mode is enabled).
* **Secrets**:
  * **DO NOT commit** `.streamlit/secrets.toml` files to Git (they are ignored by `.gitignore`).
  * If deploying to **Streamlit Cloud**, copy the contents of your local `secrets.toml` files into the platform's Secrets management area.
* **Database**:
  * For `profit_income`, ensure the production database is accessible and set the `DB_URL` secret.

## Directory Structure Notes

* **`data/`**: Stores local upload files for Profit-Income. Ensure this directory is writable in your deployment environment.
* **`pgdata/`**: Stores database persistence for Docker.
