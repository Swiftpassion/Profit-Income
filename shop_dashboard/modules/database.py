import os
import sys
from sqlalchemy import create_engine, text
import pandas as pd

# Try using streamlit secrets, otherwise fallback to local/env
try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False

# Default local connection string
DB_CONNECTION_STRING = "postgresql+psycopg2://postgres:postgres@localhost:5432/shop_dashboard"

def get_connection_string():
    """Resolves the connection string from Streamlit secrets or defaults."""
    global DB_CONNECTION_STRING
    
    # 1. Try Streamlit Secrets (App Mode)
    if HAS_STREAMLIT and hasattr(st, "secrets") and "postgres" in st.secrets:
        p = st.secrets["postgres"]
        return f"postgresql+psycopg2://{p['user']}:{p['password']}@{p['host']}:{p['port']}/{p['dbname']}"
    
    # 2. Try Loading secrets.toml manually (Script Mode)
    try:
        import toml
        # Resolve project root relative to this file (modules/database.py -> Up one level)
        current_dir = os.path.dirname(os.path.abspath(__file__)) # shop_dashboard/modules
        project_root = os.path.dirname(current_dir) # shop_dashboard
        
        secrets_path = os.path.join(project_root, ".streamlit", "secrets.toml")
        
        print(current_dir)
        print(project_root)
        print(secrets_path)

        if os.path.exists(secrets_path):
            secrets = toml.load(secrets_path)
            if "postgres" in secrets:
                p = secrets["postgres"]
                return f"postgresql+psycopg2://{p['user']}:{p['password']}@{p['host']}:{p['port']}/{p['dbname']}"
    except Exception as e:
        print(f"Warning: Could not load secrets.toml from {secrets_path}: {e}")

    # Fallback
    return DB_CONNECTION_STRING

def get_engine():
    return create_engine(get_connection_string())

def init_db():
    """Initializes the database schema (tables and views)."""
    engine = get_engine()
    
    # 1. Create Tables
    # raw_sales: Stores raw data from sales files
    # raw_ads: Stores raw data from ads files
    # master_item: Stores master item config
    # shops: Optional, but good for dropdown management if we want to strict mode
    
    sql_tables = """
    CREATE TABLE IF NOT EXISTS shops (
        shop_name VARCHAR(255) PRIMARY KEY
    );

    CREATE TABLE IF NOT EXISTS raw_sales (
        id SERIAL PRIMARY KEY,
        shop_name VARCHAR(100),
        order_id VARCHAR(255),
        status VARCHAR(100),
        courier VARCHAR(100),
        order_time TIMESTAMP,
        sku_code VARCHAR(255),
        quantity INTEGER,
        amount_paid NUMERIC,
        creator VARCHAR(100),
        payment_method VARCHAR(100),
        product_name TEXT,
        work_type VARCHAR(100),
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE TABLE IF NOT EXISTS raw_ads (
        id SERIAL PRIMARY KEY,
        shop_name VARCHAR(100),
        date DATE,
        campaign_name TEXT,
        cost NUMERIC,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS master_item (
        sku VARCHAR(255) PRIMARY KEY,
        name TEXT,
        type VARCHAR(100),
        cost NUMERIC DEFAULT 0,
        box_cost NUMERIC DEFAULT 0,
        delivery_cost NUMERIC DEFAULT 0,
        com_admin NUMERIC DEFAULT 0,
        com_tele NUMERIC DEFAULT 0,
        
        -- Courier Percentages
        p_jnt NUMERIC DEFAULT 0,
        p_flash NUMERIC DEFAULT 0,
        p_kerry NUMERIC DEFAULT 0,
        p_thai_post NUMERIC DEFAULT 0,
        p_dhl NUMERIC DEFAULT 0,
        p_spx NUMERIC DEFAULT 0,
        p_lex NUMERIC DEFAULT 0,
        p_std NUMERIC DEFAULT 0,

        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Index for performance
    CREATE INDEX IF NOT EXISTS idx_sales_date ON raw_sales(order_time);
    CREATE INDEX IF NOT EXISTS idx_sales_sku ON raw_sales(sku_code);
    CREATE INDEX IF NOT EXISTS idx_sales_shop ON raw_sales(shop_name);
    
    CREATE INDEX IF NOT EXISTS idx_ads_date ON raw_ads(date);
    CREATE INDEX IF NOT EXISTS idx_ads_shop ON raw_ads(shop_name);
    """

    # 2. SQL Views for Logic
    # View: Cleaned Sales (Normalizes Courier names, parses dates if needed)
    # View: Processed Sales (Calculates Costs)
    
    sql_views = """
    CREATE OR REPLACE FUNCTION normalize_courier(c_name TEXT) RETURNS TEXT AS $$
    BEGIN
        IF c_name IS NULL THEN RETURN 'Standard Delivery - ส่งธรรมดาในประเทศ'; END IF;
        IF c_name ILIKE '%J&T%' THEN RETURN 'J&T Express'; END IF;
        IF c_name ILIKE '%Flash%' THEN RETURN 'Flash Express'; END IF;
        IF c_name ILIKE '%Kerry%' THEN RETURN 'Kerry Express'; END IF;
        IF c_name ILIKE '%Thailand%' AND c_name ILIKE '%Post%' THEN RETURN 'ThailandPost'; END IF;
        IF c_name ILIKE '%DHL%' THEN RETURN 'DHL_1'; END IF;
        IF c_name ILIKE '%Shopee%' OR c_name ILIKE '%SPX%' THEN RETURN 'SPX Express'; END IF;
        IF c_name ILIKE '%Lazada%' OR c_name ILIKE '%LEX%' THEN RETURN 'LEX TH'; END IF;
        RETURN c_name;
    END;
    $$ LANGUAGE plpgsql;

    CREATE OR REPLACE FUNCTION calculate_role(work_type TEXT, creator TEXT) RETURNS TEXT AS $$
    BEGIN
        IF work_type ILIKE '%admin%' OR work_type ILIKE '%แอดมิน%' OR creator ILIKE '%admin%' THEN RETURN 'Admin'; END IF;
        IF work_type ILIKE '%tele%' OR work_type ILIKE '%เทเล%' OR creator ILIKE '%tele%' THEN RETURN 'Telesale'; END IF;
        RETURN 'Unknown';
    END;
    $$ LANGUAGE plpgsql;

    CREATE OR REPLACE VIEW view_processed_sales AS
    SELECT 
        s.shop_name,
        s.order_time::DATE as date,
        s.order_id,
        s.sku_code,
        COALESCE(m.sku, s.sku_code) as sku_mapped,
        COALESCE(m.name, s.product_name) as product_name,
        COALESCE(m.type, 'กลุ่ม ปกติ') as product_type,
        s.quantity,
        s.amount_paid,
        
        -- Costs from Master
        COALESCE(m.cost, 0) as unit_cost,
        (s.quantity * COALESCE(m.cost, 0)) as total_cost_prod,
        
        COALESCE(m.box_cost, 0) as box_cost,
        COALESCE(m.delivery_cost, 0) as delivery_cost,
        
        -- Courier Cost Logic (approximate by percent if provided, logic from legacy code seems complex)
        -- Legacy Python: row['SHIP_PERCENT'] from courier name mapping
        -- We will replicate get_shipping_percent here logic
        CASE 
            WHEN normalize_courier(s.courier) = 'J&T Express' THEN m.p_jnt
            WHEN normalize_courier(s.courier) = 'Flash Express' THEN m.p_flash
            WHEN normalize_courier(s.courier) = 'Kerry Express' THEN m.p_kerry
            WHEN normalize_courier(s.courier) = 'ThailandPost' THEN m.p_thai_post
            WHEN normalize_courier(s.courier) = 'DHL_1' THEN m.p_dhl
            WHEN normalize_courier(s.courier) = 'SPX Express' THEN m.p_spx
            WHEN normalize_courier(s.courier) = 'LEX TH' THEN m.p_lex
            ELSE COALESCE(m.p_std, 0)
        END as ship_percent,
        
        -- COD Calculation
        CASE 
            WHEN (s.payment_method ILIKE '%cod%' OR s.payment_method ILIKE '%ปลายทาง%') THEN 
                (s.amount_paid * 
                    (CASE 
                        WHEN normalize_courier(s.courier) = 'J&T Express' THEN m.p_jnt
                        WHEN normalize_courier(s.courier) = 'Flash Express' THEN m.p_flash
                        WHEN normalize_courier(s.courier) = 'Kerry Express' THEN m.p_kerry
                        WHEN normalize_courier(s.courier) = 'ThailandPost' THEN m.p_thai_post
                        WHEN normalize_courier(s.courier) = 'DHL_1' THEN m.p_dhl
                        WHEN normalize_courier(s.courier) = 'SPX Express' THEN m.p_spx
                        WHEN normalize_courier(s.courier) = 'LEX TH' THEN m.p_lex
                        ELSE COALESCE(m.p_std, 0)
                    END)
                * 1.07)
            ELSE 0 
        END as cod_cost,

        -- Commissions
        CASE 
            WHEN calculate_role(s.work_type, s.creator) = 'Admin' THEN (s.amount_paid * COALESCE(m.com_admin, 0))
            ELSE 0 
        END as com_admin,
        CASE 
            WHEN calculate_role(s.work_type, s.creator) = 'Telesale' THEN (s.amount_paid * COALESCE(m.com_tele, 0))
            ELSE 0 
        END as com_tele

    FROM raw_sales s
    LEFT JOIN master_item m ON REPLACE(s.sku_code, ' ', '') = REPLACE(m.sku, ' ', '')
    WHERE s.status NOT IN ('ยกเลิก');
    """

    with engine.begin() as conn:
        conn.execute(text(sql_tables))
        conn.execute(text(sql_views))
        
    print("Database Initialized Successfully.")

