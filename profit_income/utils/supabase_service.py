import streamlit as st
from supabase import create_client
import pandas as pd
from utils.common import clean_text

@st.cache_resource
def init_supabase():
    try:
        SUPABASE_URL = st.secrets["SUPABASE_URL"]
        SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.error(f"❌ Supabase Config Error: {e}")
        return None

@st.cache_data(ttl=3600)  # Cache 1 hour
def fetch_orders_data():
    """Fetch all orders from Supabase (Cached)"""
    client = init_supabase()
    if not client: return pd.DataFrame()
    try:
        # Use .range(0, 50000) to solve 1000 row limit
        res = client.table("orders").select("*").range(0, 50000).execute()
        return pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"Error fetching orders: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_ads_data():
    """Fetch all Ads data (Cached)"""
    client = init_supabase()
    if not client: return pd.DataFrame()
    try:
        res = client.table("daily_ads").select("*").range(0, 10000).execute()
        return pd.DataFrame(res.data)
    except: return pd.DataFrame()

@st.cache_data(ttl=3600)
def load_cost_data():
    """Fetch product costs (Cached)"""
    client = init_supabase()
    if not client: return pd.DataFrame()
    try:
        response = client.table("product_costs").select("sku, platform, unit_cost").execute()
        df = pd.DataFrame(response.data)
        if not df.empty:
            df['unit_cost'] = pd.to_numeric(df['unit_cost'], errors='coerce').fillna(0)
            df['platform'] = df['platform'].str.upper().str.strip()
            df = clean_text(df, 'sku')
            return df[['sku', 'platform', 'unit_cost']]
        return pd.DataFrame()
    except: return pd.DataFrame()
