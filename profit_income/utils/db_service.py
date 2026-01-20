import pandas as pd
import sqlalchemy
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import text
import os

# Database Connection URL
# Using localhost because Streamlit runs on host, Postgres in Docker exposes port 5432
try:
    import streamlit as st
    if "db_url" in st.secrets:
        DB_URL = st.secrets["db_url"]
    else:
        DB_URL = os.getenv("DB_URL", "postgresql://admin:mos2025@localhost:5432/profit_income")
except:
    DB_URL = os.getenv("DB_URL", "postgresql://admin:mos2025@localhost:5432/profit_income")

def get_engine():
    """Create and return a SQLAlchemy engine."""
    return sqlalchemy.create_engine(DB_URL)

def init_db():
    """Check connection to the database."""
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True

def fetch_orders(platform=None):
    """Fetch orders from the database."""
    engine = get_engine()
    query = "SELECT * FROM orders"
    params = {}
    
    if platform:
        query += " WHERE platform = %(platform)s"
        params['platform'] = platform
        
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params=params)

def save_orders(df, replace=True):
    """
    Save orders to the database.
    If replace=True, it wipes the table first (Sync Data behavior).
    """
    engine = get_engine()
    
    # Ensure columns match schema or handle extra columns
    # We might need to map columns or drop unused ones
    # For now, assuming df has correct columns or to_sql will handle/error
    
    if replace:
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE orders"))
            
    df.to_sql('orders', engine, if_exists='append', index=False, chunksize=1000, method='multi')

def fetch_ads(shop_name=None, start_date=None, end_date=None):
    """Fetch ads metrics from the database."""
    engine = get_engine()
    query = "SELECT * FROM daily_ads_metrics WHERE 1=1"
    params = {}
    
    if shop_name:
        query += " AND shop_name = %(shop_name)s"
        params['shop_name'] = shop_name
    if start_date:
        query += " AND date >= %(start_date)s"
        params['start_date'] = start_date
    if end_date:
        query += " AND date <= %(end_date)s"
        params['end_date'] = end_date
        
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params=params)

def save_ads(df):
    """
    Upsert ads metrics to the database.
    Primary Key: (date, shop_name)
    """
    if df.empty:
        return
        
    engine = get_engine()
    metadata = sqlalchemy.MetaData()
    table = sqlalchemy.Table('daily_ads_metrics', metadata, autoload_with=engine)
    
    records = df.to_dict(orient='records')
    
    stmt = pg_insert(table).values(records)
    
    # Update all columns except PKs on conflict
    update_dict = {
        col.name: col 
        for col in stmt.excluded 
        if col.name not in ['date', 'shop_name']
    }
    
    if update_dict:
        on_conflict_stmt = stmt.on_conflict_do_update(
            index_elements=['date', 'shop_name'],
            set_=update_dict
        )
    else:
        # If no other columns (unlikely), do nothing
        on_conflict_stmt = stmt.on_conflict_do_nothing(
            index_elements=['date', 'shop_name']
        )
    
    with engine.begin() as conn:
        conn.execute(on_conflict_stmt)

def get_product_costs():
    """Fetch product costs."""
    engine = get_engine()
    return pd.read_sql("SELECT * FROM product_costs", engine)

def save_product_costs(df, replace=True):
    """
    Save product costs.
    If replace=True, wipes the table first.
    """
    engine = get_engine()
    if replace:
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE product_costs"))
            
    df.to_sql('product_costs', engine, if_exists='append', index=False, chunksize=1000, method='multi')
