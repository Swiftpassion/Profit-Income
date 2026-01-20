import streamlit as st
from utils.styles import load_css
from utils.db_service import init_db
from views.sidebar import render_sidebar
from views.dashboard import render_dashboard
from views.details import render_details
from views.ads import render_ads
from views.costs import render_costs
from views.data_table import render_data_table

# --- 1. CONFIGURATION & CSS ---
st.set_page_config(page_title="Dashboard สรุปยอดขาย", layout="wide", page_icon="🛍️")
load_css()

# --- 2. INITIALIZATION CHECK ---
if not init_db():
    st.error("ไม่สามารถเชื่อมต่อฐานข้อมูลได้ กรุณาตรวจสอบ Docker")
    st.stop()

# --- 3. SIDEBAR ---
render_sidebar()

# --- 4. MAIN CONTENT ---
tab_dash, tab_details, tab_ads, tab_cost, tab_old = st.tabs([
    "📊 สรุปยอดขาย (Dashboard)", 
    "📦 รายละเอียดออเดอร์", 
    "📢 บันทึกค่าโฆษณา", 
    "💰 จัดการต้นทุน", 
    "📂 ตารางข้อมูลเดิม"
])

with tab_dash:
    render_dashboard()

with tab_details:
    render_details()

with tab_ads:
    render_ads()

with tab_cost:
    render_costs()

with tab_old:
    render_data_table()