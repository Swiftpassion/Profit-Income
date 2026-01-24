import streamlit as st
import pandas as pd
import numpy as np
import io
import gspread
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import altair as alt
import calendar
from datetime import datetime, date, timedelta

# --- GLOBAL VARIABLES ---
thai_months = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
               "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]

# --- COLOR SETTINGS ---
COLOR_SALES = "#33FFFF"
COLOR_OPS = "#3498db"  # ค่าดำเนินการ
COLOR_COM = "#FFD700"  # ค่าคอมมิชชั่น (ทอง)
COLOR_COST_PROD = "#A020F0"  # ทุนสินค้า
COLOR_ADS = "#FF6633"
COLOR_PROFIT = "#7CFC00"
COLOR_NEGATIVE = "#FF0000"

# ==========================================
# 1. CONFIG & CSS
# ==========================================
st.set_page_config(page_title="Shop Analytics Dashboard", layout="wide", page_icon="📊")

# ==========================================
# 0. LOGIN SYSTEM (REMEMBER ME VERSION)
# ==========================================
# เช็ค URL ว่าเคย Login สำเร็จหรือยัง (เพื่อให้รีเฟรชแล้วไม่ต้องกรอกใหม่)
if "auth" in st.query_params and st.query_params["auth"] == "success":
    st.session_state.logged_in = True
elif 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

def check_login():
    password = st.session_state.get("password_input", "")
    if password == "Mos2025":
        st.session_state.logged_in = True
        st.session_state.login_error = None
        # สั่งจำค่า Login ไว้บน URL Browser
        st.query_params["auth"] = "success"
    else:
        st.session_state.login_error = "⚠️ รหัสผ่านไม่ถูกต้อง กรุณาลองใหม่"

if not st.session_state.logged_in:
    # ... (ส่วน CSS และ HTML เดิม ไม่ต้องแก้) ...
    # คงโค้ดส่วนแสดงผลหน้า Login ไว้เหมือนเดิมด้านล่างนี้ได้เลยครับ
    st.markdown("""
        <style>
            .stTextInput input { color: #ffffff !important; background-color: #1e1e1e !important; border: 1px solid #444 !important; border-radius: 8px !important; padding: 12px !important; font-size: 16px !important; }
            .stButton button { width: 100%; background: linear-gradient(90deg, #6c5ce7 0%, #a29bfe 100%) !important; color: white !important; border-radius: 8px !important; border: none !important; margin-top: 10px; }
            .login-header { font-size: 26px; font-weight: 700; text-align: center; color: white; margin-bottom: 5px; }
            .login-sub { font-size: 14px; text-align: center; color: #aaa; margin-bottom: 25px; }
            .custom-error { background-color: #ff4d4d20; border: 1px solid #ff4d4d; color: #ff4d4d; padding: 10px; border-radius: 8px; text-align: center; margin: 10px 0; }
        </style>
    """, unsafe_allow_html=True)

    # --- LAYOUT จัดหน้า (ปรับขนาดให้แคบลง) ---
    col1, col2, col3 = st.columns([2, 1.2, 2])

    with col2:
        st.markdown("<br><br><br>", unsafe_allow_html=True) # ดันลงมาให้อยู่กลางจอแนวตั้ง
        st.markdown('<div class="login-header">กรุณาใส่รหัสผ่าน</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-sub">สำหรับเข้าดูหน้านี้</div>', unsafe_allow_html=True)
        
        # Input Field
        st.text_input(
            "Password", 
            type="password", 
            key="password_input", 
            label_visibility="collapsed",
            placeholder="🔒 กรอกรหัสผ่าน..."
        )
        
        # แสดง Error (ถ้ามี) แบบ Custom Div
        if st.session_state.get("login_error"):
            st.markdown(f'<div class="custom-error">{st.session_state.login_error}</div>', unsafe_allow_html=True)

        # ปุ่มกด
        st.button("เข้าสู่ระบบ", on_click=check_login, use_container_width=True)

    st.stop()

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;600;700&family=Prompt:wght@300;400;500;600&display=swap');

    html, body, [class*="css"] { font-family: 'Sarabun', sans-serif; }
    
    .block-container { padding-top: 2rem !important; }

    /* --- 1. สีตัวอักษร --- */
    .val-sales { color: #33FFFF !important; font-size: 24px; font-weight: 700; }
    .sub-sales { color: #33FFFF !important; font-size: 13px; font-weight: 600; margin-top: 5px; }

    .val-ops { color: #3498db !important; font-size: 24px; font-weight: 700; }
    .sub-ops { color: #3498db !important; font-size: 13px; font-weight: 600; margin-top: 5px; }

    .val-com { color: #FFD700 !important; font-size: 24px; font-weight: 700; }
    .sub-com { color: #FFD700 !important; font-size: 13px; font-weight: 600; margin-top: 5px; }

    .val-costprod { color: #A020F0 !important; font-size: 24px; font-weight: 700; }
    .sub-costprod { color: #A020F0 !important; font-size: 13px; font-weight: 600; margin-top: 5px; }

    .val-ads { color: #FF6633 !important; font-size: 24px; font-weight: 700; }
    .sub-ads { color: #FF6633 !important; font-size: 13px; font-weight: 600; margin-top: 5px; }

    .val-profit { color: #7CFC00 !important; font-size: 24px; font-weight: 700; }
    .sub-profit { color: #7CFC00 !important; font-size: 13px; font-weight: 600; margin-top: 5px; }

    .val-neg { color: #FF0000 !important; font-size: 24px; font-weight: 700; }
    .sub-neg { color: #FF0000 !important; font-size: 13px; font-weight: 600; margin-top: 5px; }

    /* --- 2. การจัดวาง (LAYOUT FIX) --- */
    .metric-container { 
        display: grid !important; 
        grid-template-columns: repeat(6, 1fr) !important; 
        gap: 15px !important; 
        margin-bottom: 20px; 
        width: 100%;
    }
    
    .custom-card {
        background: #1c1c1c;
        border-radius: 10px; padding: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.5); 
        min-width: 0; 
        border-left: 5px solid #ddd;
        border: 1px solid #333;
    }

    .card-label { color: #aaa !important; font-size: 13px; font-weight: 600; margin-bottom: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

    .neg { color: #FF0000 !important; }
    .pos { color: #ffffff !important; }

    .border-blue { border-left-color: #33FFFF; }
    .border-ops { border-left-color: #3498db; }
    .border-com { border-left-color: #FFD700; }
    .border-costprod { border-left-color: #A020F0; }
    .border-orange { border-left-color: #FF6633; }
    .border-green { border-left-color: #7CFC00; }

    /* Inputs */
    .stTextInput input { color: #ffffff !important; caret-color: white; background-color: #262730 !important; border: 1px solid #555 !important; }
    div[data-baseweb="select"] div { color: #ffffff !important; background-color: #262730 !important; }
    div[data-baseweb="select"] span { color: #ffffff !important; }
    div[role="listbox"] li { color: #ffffff !important; background-color: #262730; }

    /* Header & Utils */
    .header-bar {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        padding: 15px 20px; border-radius: 10px;
        margin-bottom: 20px; display: flex; align-items: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .header-title { font-size: 22px; font-weight: 700; margin: 0; color: white !important; }

    /* Table Styling */
    .table-wrapper { overflow: auto; width: 100%; max-height: 800px; margin-top: 10px; background: #1c1c1c; border-radius: 8px; border: 1px solid #444; }
    .custom-table { width: 100%; min-width: 1000px; border-collapse: separate; border-spacing: 0; font-family: 'Sarabun', sans-serif; font-size: 11px; color: #ddd; }
    .custom-table th, .custom-table td { padding: 4px 6px; line-height: 1.2; text-align: center; border-bottom: 1px solid #333; border-right: 1px solid #333; white-space: nowrap; }
    .daily-table thead th, .month-table thead th { position: sticky; top: 0; z-index: 100; background-color: #1e3c72; color: white !important; font-weight: 700; border-bottom: 2px solid #555; }
    
    .custom-table tbody tr:nth-child(even) td { background-color: #262626; }
    .custom-table tbody tr:nth-child(odd) td { background-color: #1c1c1c; }
    .custom-table tbody tr:hover td { background-color: #333; }

    /* REPORT DAILY SPECIFIC */
    .custom-table.daily-table tbody tr td { 
        color: #333333 !important; 
        font-weight: 500;
    }
    .custom-table.daily-table tbody tr:nth-child(even) td { background-color: #d9d9d9 !important; }
    .custom-table.daily-table tbody tr:nth-child(odd) td { background-color: #ffffff !important; }
    .custom-table.daily-table tbody tr:hover td { background-color: #e6e6e6 !important; }
    
    .custom-table.daily-table tbody tr td.negative-value {
        color: #FF0000 !important;
        font-weight: bold !important;
    }
    
    .custom-table.daily-table tbody tr td[style*="color: #e67e22"],
    .custom-table.daily-table tbody tr td[style*="color:#e67e22"] {
        color: #e67e22 !important;
    }
    
    .custom-table.daily-table tbody tr td[style*="color: #1e3c72"],
    .custom-table.daily-table tbody tr td[style*="color:#1e3c72"] {
        color: #1e3c72 !important;
        font-weight: bold !important;
    }
    
    .custom-table.daily-table tbody tr td[style*="color: #FF0000"],
    .custom-table.daily-table tbody tr td[style*="color:#FF0000"] {
        color: #FF0000 !important;
        font-weight: bold !important;
    }
    
    .custom-table.daily-table tbody tr.footer-row td { 
        position: sticky; bottom: 0; z-index: 100; 
        background-color: #1e3c72 !important; 
        font-weight: bold; 
        color: white !important; 
        border-top: 2px solid #f1c40f; 
    }

    /* --- [FIX COMPACT SIZE] REPORT MONTH STICKY COLS --- */
    .fix-m-1 { position: sticky; left: 0px !important;   z-index: 20; width: 110px !important; min-width: 110px !important; border-right: 1px solid #444; }
    .fix-m-2 { position: sticky; left: 110px !important; z-index: 20; width: 80px !important;  min-width: 80px !important;  border-right: 1px solid #444; }
    .fix-m-3 { position: sticky; left: 190px !important; z-index: 20; width: 50px !important;  min-width: 50px !important;  border-right: 1px solid #444; }
    .fix-m-4 { position: sticky; left: 240px !important; z-index: 20; width: 70px !important;  min-width: 70px !important;  border-right: 1px solid #444; }
    .fix-m-5 { position: sticky; left: 310px !important; z-index: 20; width: 45px !important;  min-width: 45px !important;  border-right: 1px solid #444; }
    .fix-m-6 { position: sticky; left: 355px !important; z-index: 20; width: 70px !important;  min-width: 70px !important;  border-right: 1px solid #444; }
    .fix-m-7 { position: sticky; left: 425px !important; z-index: 20; width: 45px !important;  min-width: 45px !important;  border-right: 2px solid #bbb !important; }

    /* --- 1. ส่วนหัวตาราง (THEAD) แก้ z-index ให้สูงขึ้น --- */
.month-table thead th.fix-m-1, .month-table thead th.fix-m-2, 
.month-table thead th.fix-m-3, .month-table thead th.fix-m-4,
.month-table thead th.fix-m-5, .month-table thead th.fix-m-6,
.month-table thead th.fix-m-7 {
    z-index: 200 !important; /* <--- แก้จาก 30 เป็น 200 เพื่อให้อยู่บนสุดครับ */
    box-shadow: 2px 0 5px rgba(0,0,0,0.3); /* เพิ่มเงาเล็กน้อยให้ดูแยกชั้นชัดเจน */
}

/* --- 2. ส่วนเนื้อหา (TBODY) เพิ่ม z-index เล็กน้อยกันพลาด --- */
.custom-table tbody tr td.fix-m-1, .custom-table tbody tr td.fix-m-2,
.custom-table tbody tr td.fix-m-3, .custom-table tbody tr td.fix-m-4,
.custom-table tbody tr td.fix-m-5, .custom-table tbody tr td.fix-m-6,
.custom-table tbody tr td.fix-m-7 {
    background-color: #1c1c1c; 
    z-index: 50 !important; /* <--- แนะนำให้เพิ่มบรรทัดนี้ครับ */
    position: sticky;       /* <--- ย้ำคำสั่งนี้ */
}

/* --- 3. ส่วนสีพื้นหลังแถวคู่ (เหมือนเดิม) --- */
.custom-table tbody tr:nth-child(even) td.fix-m-1, .custom-table tbody tr:nth-child(even) td.fix-m-2,
.custom-table tbody tr:nth-child(even) td.fix-m-3, .custom-table tbody tr:nth-child(even) td.fix-m-4,
.custom-table tbody tr:nth-child(even) td.fix-m-5, .custom-table tbody tr:nth-child(even) td.fix-m-6,
.custom-table tbody tr:nth-child(even) td.fix-m-7 {
    background-color: #262626; 
}

    .month-table tfoot {
        position: sticky;
        bottom: 0;
        z-index: 25;
        border-top: 2px solid #fff;
    }
    .month-table tfoot td.fix-m-1, 
    .month-table tfoot td.fix-m-2, 
    .month-table tfoot td.fix-m-3, 
    .month-table tfoot td.fix-m-4, 
    .month-table tfoot td.fix-m-5, 
    .month-table tfoot td.fix-m-6, 
    .month-table tfoot td.fix-m-7 {
        z-index: 40 !important;
    }

    .th-sku { background-color: #1e3c72 !important; color: white !important; min-width: 80px; }
    .sku-header { font-size: 10px; color: #d6eaf8 !important; font-weight: normal; display: block; overflow: hidden; text-overflow: ellipsis; max-width: 100px; margin: 0 auto; text-align: center; }
    .col-small { width: 70px; min-width: 70px; max-width: 70px; font-size: 11px; color: #333333 !important; }
       .col-medium { width: 90px !important; min-width: 90px !important; max-width: 90px !important; font-size: 11px; color: #333333 !important; }
       .col-wide { width: 100px !important; min-width: 100px !important; max-width: 100px !important; font-size: 11px; color: #333333 !important; }

    .pnl-container { font-family: 'Prompt', sans-serif; color: #ffffff; }
    .header-gradient-pnl { background-image: linear-gradient(135deg, #0f172a 0%, #334155 100%); padding: 20px 25px; border-radius: 12px; color: white; margin-bottom: 25px; }
    .header-title-pnl { font-size: 24px; font-weight: 600; margin: 0; color: white !important; }
    .header-sub-pnl { font-size: 14px; color: #cbd5e1; font-weight: 300; margin-top: 5px; }
    
    .chart-box { background-color: #1c1c1c; border: 1px solid #333; border-radius: 12px; padding: 20px; margin-bottom: 20px; display: flex; flex-direction: column; }
    .chart-header { font-size: 16px; font-weight: 600; color: #ddd; margin-bottom: 15px; display: flex; align-items: center; gap: 8px; }
    .pill { width: 4px; height: 16px; border-radius: 4px; display: inline-block; }
    
    .pnl-table { width: 100%; border-collapse: collapse; font-size: 14px; font-family: 'Prompt', sans-serif; background: #1c1c1c; }
    .pnl-table th { text-align: left; padding: 12px 16px; color: #aaa; font-weight: 500; background-color: #2c2c2c; border-bottom: 1px solid #444; }
    .pnl-table td { padding: 12px 16px; border-bottom: 1px solid #333; color: #ddd; }
    .pnl-row-head td { font-weight: 600; color: #fff; background-color: #2c2c2c; }
    .num-cell { text-align: right; font-family: 'Courier New', monospace; }
    .sub-item td:first-child { padding-left: 35px; color: #aaa; font-size: 13px; }
    
    div.stButton > button { width: 100%; border-radius: 6px; height: 42px; font-weight: bold; padding: 0px 5px; background-color: #333; color: white; border: 1px solid #555; }
    div.stButton > button:hover { border-color: #00d2ff; color: #00d2ff; }
</style>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
""", unsafe_allow_html=True)

# ==========================================
# 2. SETTINGS & HELPERS
# ==========================================
FOLDER_ID_DATA = "1ciI_X2m8pVcsjRsPuUf5sg--6uPSPPDp"  # ไฟล์ยอดขาย JST
FOLDER_ID_ADS = "1ZE76TXNA_vNeXjhAZfLgBQQGIV0GY7w8"   # ไฟล์ค่า ADS
SHEET_MASTER_URL = "https://docs.google.com/spreadsheets/d/1Q3akHm1GKkDI2eilGfujsd9pO7aOjJvyYJNuXd98lzo/edit?gid=0#gid=0" # ชีทตั้งค่าทุน

def safe_float(val):
    if pd.isna(val) or val == "" or val is None: return 0.0
    s = str(val).strip().replace(',', '').replace('฿', '').replace(' ', '')
    if s in ['-', 'nan', 'NaN', 'None']: return 0.0
    try:
        if '%' in s: return float(s.replace('%', '')) / 100
        return float(s)
    except: return 0.0

def safe_date(val):
    try: return pd.to_datetime(val).date()
    except: return None

def get_val_color(val, default_hex):
    if val < 0: return COLOR_NEGATIVE
    return default_hex

# ฟังก์ชันจัดกึ่งกลางชื่อขนส่งให้ตรงกับคอลัมน์ใน Master
def normalize_courier_name(courier):
    if pd.isna(courier) or courier == "":
        return "Standard Delivery - ส่งธรรมดาในประเทศ"
    
    courier = str(courier).strip()
    mapping = {
        "J&T Express": "J&T Express", "J&T": "J&T Express",
        "Flash Express": "Flash Express", "Flash": "Flash Express",
        "Kerry Express": "Kerry Express", "Kerry": "Kerry Express",
        "Thailand Post": "ThailandPost", "ThailandPost": "ThailandPost",
        "DHL Domestic": "DHL_1", "DHL": "DHL_1",
        "Shopee Express": "SPX Express", "SPX Express": "SPX Express",
        "Lazada Express": "LEX TH", "LEX": "LEX TH"
    }
    return mapping.get(courier, courier)

# ------------------------------
# GLOBAL METRIC CARD COMPONENT (อัปเดตเป็น 6 กล่อง)
# ------------------------------
def render_metric_row(total_sales, total_ops, total_com, total_cost_prod, total_ads, total_profit):
    pct_sales = 100
    pct_ops = (total_ops / total_sales * 100) if total_sales > 0 else 0
    pct_com = (total_com / total_sales * 100) if total_sales > 0 else 0
    pct_cost_prod = (total_cost_prod / total_sales * 100) if total_sales > 0 else 0
    pct_ads = (total_ads / total_sales * 100) if total_sales > 0 else 0
    pct_profit = (total_profit / total_sales * 100) if total_sales > 0 else 0

    cls_sales_v = "val-neg" if total_sales < 0 else "val-sales"
    cls_sales_s = "sub-neg" if total_sales < 0 else "sub-sales"
    cls_ops_v = "val-neg" if total_ops < 0 else "val-ops"
    cls_ops_s = "sub-neg" if total_ops < 0 else "sub-ops"
    cls_com_v = "val-neg" if total_com < 0 else "val-com"
    cls_com_s = "sub-neg" if total_com < 0 else "sub-com"
    cls_costprod_v = "val-neg" if total_cost_prod < 0 else "val-costprod"
    cls_costprod_s = "sub-neg" if total_cost_prod < 0 else "sub-costprod"
    cls_ads_v = "val-neg" if total_ads < 0 else "val-ads"
    cls_ads_s = "sub-neg" if total_ads < 0 else "sub-ads"
    cls_prof_v = "val-neg" if total_profit < 0 else "val-profit"
    cls_prof_s = "sub-neg" if total_profit < 0 else "sub-profit"

    html = f"""
<div class="metric-container">
<div class="custom-card border-blue">
<div class="card-label">ยอดขายรวม</div>
<div class="{cls_sales_v}">{total_sales:,.0f}</div>
<div class="{cls_sales_s}">{pct_sales:.0f}%</div>
</div>
<div class="custom-card border-ops">
<div class="card-label">ค่าดำเนินการ</div>
<div class="{cls_ops_v}">{total_ops:,.0f}</div>
<div class="{cls_ops_s}">{pct_ops:.1f}%</div>
</div>
<div class="custom-card border-com">
<div class="card-label">ค่าคอมมิชชั่น</div>
<div class="{cls_com_v}">{total_com:,.0f}</div>
<div class="{cls_com_s}">{pct_com:.1f}%</div>
</div>
<div class="custom-card border-costprod">
<div class="card-label">ทุนสินค้า</div>
<div class="{cls_costprod_v}">{total_cost_prod:,.0f}</div>
<div class="{cls_costprod_s}">{pct_cost_prod:.1f}%</div>
</div>
<div class="custom-card border-orange">
<div class="card-label">ค่าโฆษณา</div>
<div class="{cls_ads_v}">{total_ads:,.0f}</div>
<div class="{cls_ads_s}">{pct_ads:.1f}%</div>
</div>
<div class="custom-card border-green">
<div class="card-label">กำไรสุทธิ</div>
<div class="{cls_prof_v}">{total_profit:,.0f}</div>
<div class="{cls_prof_s}">{pct_profit:.1f}%</div>
</div>
</div>
"""
    st.markdown(html, unsafe_allow_html=True)

@st.cache_resource
def get_drive_service():
    if "gcp_service_account" not in st.secrets:
        st.error("Error: ไม่พบ Secrets กรุณาตรวจสอบการตั้งค่า")
        st.stop()
    creds_dict = dict(st.secrets["gcp_service_account"])
    scopes = ['https://www.googleapis.com/auth/drive.readonly', 'https://www.googleapis.com/auth/spreadsheets']
    return service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)

def load_raw_files():
    creds = get_drive_service()
    service = build('drive', 'v3', credentials=creds)
    gc = gspread.authorize(creds)

    def get_files(folder_id):
        try:
            results = service.files().list(q=f"'{folder_id}' in parents and trashed=false", fields="files(id, name)").execute()
            return results.get('files', [])
        except: return []

    def read_file(file_id, filename):
        try:
            request = service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False: status, done = downloader.next_chunk()
            fh.seek(0)
            if filename.lower().endswith('.csv'): return pd.read_csv(fh, dtype={'หมายเลขคำสั่งซื้อออนไลน์': str})
            elif filename.lower().endswith(('.xlsx', '.xls')): return pd.read_excel(fh)
        except: pass
        return None

    files_data = get_files(FOLDER_ID_DATA)
    df_list = []
    for f in files_data:
        df = read_file(f['id'], f['name'])
        if df is not None:
            if 'หมายเลขคำสั่งซื้อออนไลน์' in df.columns:
                df['หมายเลขคำสั่งซื้อออนไลน์'] = df['หมายเลขคำสั่งซื้อออนไลน์'].astype(str).str.replace(r'\.0$', '', regex=True)
            df_list.append(df)
    df_data = pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()

    files_ads = get_files(FOLDER_ID_ADS)
    df_ads_list = []
    for f in files_ads:
        df = read_file(f['id'], f['name'])
        if df is not None: df_ads_list.append(df)
    df_ads_raw = pd.concat(df_ads_list, ignore_index=True) if df_ads_list else pd.DataFrame()

    df_master = pd.DataFrame()
    df_fix = pd.DataFrame()
    try:
        sh = gc.open_by_url(SHEET_MASTER_URL)
        df_master = pd.DataFrame(sh.worksheet("MASTER_ITEM").get_all_records())
        try: df_fix = pd.DataFrame(sh.worksheet("FIX_COST").get_all_records())
        except: 
            try: df_fix = pd.DataFrame(sh.worksheet("FIXED_COST").get_all_records())
            except: pass
    except: pass

    return df_data, df_ads_raw, df_master, df_fix

@st.cache_data(ttl=600)
def process_data():
    df_data, df_ads_raw, df_master, df_fix_cost = load_raw_files()

    if df_data.empty: return pd.DataFrame(), pd.DataFrame(), {}, [], {}

    # --- 1. PREPARE MASTER ITEM ---
    if not df_master.empty:
        df_master.columns = df_master.columns.astype(str).str.strip()
        
        # [แก้ไข] เพิ่มการเปลี่ยนชื่อคอลัมน์จาก 'ทุน' เป็น 'ต้นทุน' อัตโนมัติ
        if 'ทุน' in df_master.columns:
            df_master.rename(columns={'ทุน': 'ต้นทุน'}, inplace=True)
            
        if 'ชื่อสินค้า' not in df_master.columns:
            if len(df_master.columns) >= 2:
                col_b = df_master.columns[1]
                df_master.rename(columns={col_b: 'ชื่อสินค้า'}, inplace=True)
            else:
                df_master['ชื่อสินค้า'] = df_master['SKU'] if 'SKU' in df_master.columns else "Unknown"
        
        if 'Type' not in df_master.columns:
            df_master['Type'] = 'กลุ่ม ปกติ'
        df_master['Type'] = df_master['Type'].fillna('กลุ่ม ปกติ').astype(str).str.strip()

    # --- 2. PREPARE DATA ---
    cols = [c for c in ['หมายเลขคำสั่งซื้อออนไลน์', 'สถานะคำสั่งซื้อ', 
            'บริษัทขนส่ง', 'เวลาสั่งซื้อ', 'รูปแบบสินค้า', 'จำนวน', 
            'รายละเอียดยอดที่ชำระแล้ว', 'ผู้สร้างคำสั่งซื้อ', 
            'วิธีการชำระเงิน', 'ชื่อสินค้า', 'ประเภทการทำงาน'] 
            if c in df_data.columns]
    
    df = df_data[cols].copy()

    if 'สถานะคำสั่งซื้อ' in df.columns:
        df = df[~df['สถานะคำสั่งซื้อ'].isin(['ยกเลิก'])]

    df['Date'] = df['เวลาสั่งซื้อ'].apply(safe_date)
    df = df.dropna(subset=['Date'])
    
    df['SKU_Main'] = df['รูปแบบสินค้า'].astype(str).str.split('-').str[0].str.strip()

    # --- 3. MERGE WITH MASTER ITEM ---
    master_cols = ['SKU', 'ชื่อสินค้า', 'Type', 'ต้นทุน', 'ราคากล่อง', 'ค่าส่งเฉลี่ย',
                   'ค่าคอมมิชชั่น Admin', 'ค่าคอมมิชชั่น Telesale',
                   'J&T Express', 'Flash Express', 'ThailandPost', 
                   'DHL_1', 'LEX TH', 'SPX Express',
                   'Express Delivery - ส่งด่วน', 'Standard Delivery - ส่งธรรมดาในประเทศ']
    
    master_cols = [c for c in master_cols if c in df_master.columns]
    df_master_filtered = df_master[master_cols].drop_duplicates('SKU')

    df['SKU_Raw'] = df['รูปแบบสินค้า'].astype(str).str.strip()
    df['SKU_Norm'] = df['SKU_Raw'].str.replace(' ', '', regex=False)
    df['SKU_Norm_Root'] = df['SKU_Norm'].str.split('-').str[0]

    df_master_filtered['SKU_Norm'] = df_master_filtered['SKU'].astype(str).str.strip().str.replace(' ', '', regex=False)
    df_merged = pd.merge(df, df_master_filtered, on='SKU_Norm', how='left')

    if 'SKU_x' in df_merged.columns: df_merged.rename(columns={'SKU_x': 'SKU_Original'}, inplace=True)
    if 'SKU_y' in df_merged.columns: df_merged.rename(columns={'SKU_y': 'SKU_Master'}, inplace=True)
    if 'ชื่อสินค้า_y' in df_merged.columns: df_merged.rename(columns={'ชื่อสินค้า_y': 'ชื่อสินค้า_Master'}, inplace=True)
    if 'ชื่อสินค้า_x' in df_merged.columns: df_merged.rename(columns={'ชื่อสินค้า_x': 'ชื่อสินค้า'}, inplace=True)

    # Fallback Logic
    df_master_root = df_master_filtered.copy()
    df_root_lookup = pd.merge(df[['SKU_Norm_Root']], df_master_root, left_on='SKU_Norm_Root', right_on='SKU_Norm', how='left')
    
    cols_to_fill = ['ต้นทุน', 'ราคากล่อง', 'ค่าส่งเฉลี่ย', 
                    'ค่าคอมมิชชั่น Admin', 'ค่าคอมมิชชั่น Telesale', 'Type']

    for col in cols_to_fill:
        if col in df_merged.columns and col in df_root_lookup.columns:
            df_merged[col] = df_merged[col].combine_first(df_root_lookup[col])
        elif col not in df_merged.columns and col in df_root_lookup.columns:
             df_merged[col] = df_root_lookup[col]

    root_name_map = df_master_filtered.set_index('SKU_Norm')['ชื่อสินค้า'].to_dict()
    df_merged['Name_Root'] = df_merged['SKU_Norm_Root'].map(root_name_map)
    
    if 'ชื่อสินค้า_Master' in df_merged.columns:
        df_merged['ชื่อสินค้า'] = df_merged['ชื่อสินค้า_Master'].combine_first(df_merged['Name_Root']).combine_first(df_merged['ชื่อสินค้า'])
    else:
        df_merged['ชื่อสินค้า'] = df_merged['Name_Root'].combine_first(df_merged['ชื่อสินค้า'])

    # --- 4. CALCULATE COST ---
    numeric_cols = ['จำนวน', 'รายละเอียดยอดที่ชำระแล้ว', 'ต้นทุน', 'ราคากล่อง', 'ค่าส่งเฉลี่ย']
    for col in numeric_cols:
        if col in df_merged.columns:
            df_merged[col] = df_merged[col].apply(safe_float)
    
    df_merged['CAL_COST'] = df_merged['จำนวน'] * df_merged['ต้นทุน']
    df_merged['BOX_COST_PER_LINE'] = df_merged['ราคากล่อง'].fillna(0)
    df_merged['DELIV_COST_PER_LINE'] = df_merged['ค่าส่งเฉลี่ย'].fillna(0)

    def get_shipping_percent(row):
        courier = str(row.get('บริษัทขนส่ง', '')).strip()
        normalized_courier = normalize_courier_name(courier)
        if normalized_courier in row:
            return safe_float(row[normalized_courier])
        return safe_float(row.get('Standard Delivery - ส่งธรรมดาในประเทศ', 0))

    df_merged['SHIP_PERCENT'] = df_merged.apply(get_shipping_percent, axis=1)

    def calculate_cod_cost(row):
        payment = str(row.get('วิธีการชำระเงิน', '')).lower()
        is_cod = any(cod_term in payment for cod_term in ['cod', 'ปลายทาง'])
        if is_cod and row['SHIP_PERCENT'] > 0:
            return row['รายละเอียดยอดที่ชำระแล้ว'] * row['SHIP_PERCENT'] * 1.07
        return 0

    df_merged['CAL_COD_COST'] = df_merged.apply(calculate_cod_cost, axis=1)

    def calculate_role(row):
        work_type = str(row.get('ประเภทการทำงาน', '')).lower()
        creator = str(row.get('ผู้สร้างคำสั่งซื้อ', '')).lower()
        if 'admin' in work_type or 'แอดมิน' in work_type or 'admin' in creator: return 'Admin'
        if 'tele' in work_type or 'เทเล' in work_type or 'tele' in creator: return 'Telesale'
        return 'Unknown'

    df_merged['Calculated_Role'] = df_merged.apply(calculate_role, axis=1)

    com_admin = df_merged.get('ค่าคอมมิชชั่น Admin', 0).fillna(0).apply(safe_float)
    com_tele = df_merged.get('ค่าคอมมิชชั่น Telesale', 0).fillna(0).apply(safe_float)

    df_merged['CAL_COM_ADMIN'] = np.where((df_merged['Calculated_Role'] == 'Admin'), 
                                          df_merged['รายละเอียดยอดที่ชำระแล้ว'] * com_admin, 0)
    df_merged['CAL_COM_TELESALE'] = np.where((df_merged['Calculated_Role'] == 'Telesale'), 
                                             df_merged['รายละเอียดยอดที่ชำระแล้ว'] * com_tele, 0)

    df_merged['SKU_Main'] = df_merged['SKU_Norm_Root']
    df_merged['Display_Name'] = df_merged['ชื่อสินค้า']

    # --- AGGREGATE ---
    order_agg = {
        'Date': 'first',
        'SKU_Main': 'first',
        'ชื่อสินค้า': 'first',
        'จำนวน': 'sum',
        'รายละเอียดยอดที่ชำระแล้ว': 'sum',
        'CAL_COST': 'sum', 
        'BOX_COST_PER_LINE': 'max', 
        'DELIV_COST_PER_LINE': 'max',
        'CAL_COD_COST': 'sum',
        'CAL_COM_ADMIN': 'sum',
        'CAL_COM_TELESALE': 'sum',
        'Type': 'first'
    }

    df_order = df_merged.groupby('หมายเลขคำสั่งซื้อออนไลน์').agg(order_agg).reset_index()
    df_order.rename(columns={'BOX_COST_PER_LINE': 'BOX_COST', 'DELIV_COST_PER_LINE': 'DELIV_COST'}, inplace=True)

    # --- ADS ---
    df_ads_agg = pd.DataFrame(columns=['Date', 'SKU_Main', 'Ads_Amount'])
    if not df_ads_raw.empty:
        col_cost = next((c for c in ['จำนวนเงินที่ใช้จ่ายไป (THB)', 'Cost', 'Amount'] if c in df_ads_raw.columns), None)
        col_date = next((c for c in ['วัน', 'Date'] if c in df_ads_raw.columns), None)
        col_camp = next((c for c in ['ชื่อแคมเปญ', 'Campaign'] if c in df_ads_raw.columns), None)

        if col_cost and col_date and col_camp:
            df_ads_raw['Date'] = df_ads_raw[col_date].apply(safe_date)
            df_ads_raw = df_ads_raw.dropna(subset=['Date'])
            df_ads_raw[col_cost] = df_ads_raw[col_cost].apply(safe_float)
            df_ads_raw['SKU_Extracted'] = df_ads_raw[col_camp].astype(str).str.extract(r'\[(.*?)\]')
            df_ads_raw['SKU_Main'] = df_ads_raw['SKU_Extracted'].str.replace(' ', '', regex=False)
            
            df_ads_agg = df_ads_raw.groupby(['Date', 'SKU_Main'])[col_cost].sum().reset_index(name='Ads_Amount')

    # --- FINAL DAILY AGG ---
    daily_agg = {
        'ชื่อสินค้า': 'first',
        'จำนวนออเดอร์': 'count',
        'จำนวน': 'sum',
        'รายละเอียดยอดที่ชำระแล้ว': 'sum',
        'CAL_COST': 'sum',
        'BOX_COST': 'sum',
        'DELIV_COST': 'sum',
        'CAL_COD_COST': 'sum',
        'CAL_COM_ADMIN': 'sum',
        'CAL_COM_TELESALE': 'sum',
        'Type': 'first'
    }

    df_order_renamed = df_order.rename(columns={'หมายเลขคำสั่งซื้อออนไลน์': 'จำนวนออเดอร์'})
    df_daily = df_order_renamed.groupby(['Date', 'SKU_Main']).agg(daily_agg).reset_index()

    if not df_ads_agg.empty:
        df_daily = pd.merge(df_daily, df_ads_agg, on=['Date', 'SKU_Main'], how='outer')
    else: df_daily['Ads_Amount'] = 0

    df_daily = df_daily.fillna(0)
    df_daily['Other_Costs'] = df_daily['BOX_COST'] + df_daily['DELIV_COST'] + df_daily['CAL_COD_COST'] + df_daily['CAL_COM_ADMIN'] + df_daily['CAL_COM_TELESALE']
    df_daily['Total_Cost'] = df_daily['CAL_COST'] + df_daily['Other_Costs'] + df_daily['Ads_Amount']
    df_daily['Net_Profit'] = df_daily['รายละเอียดยอดที่ชำระแล้ว'] - df_daily['Total_Cost']

    df_daily['Date'] = pd.to_datetime(df_daily['Date'])
    df_daily['Year'] = df_daily['Date'].dt.year
    df_daily['Month_Num'] = df_daily['Date'].dt.month
    df_daily['Month_Thai'] = df_daily['Month_Num'].apply(lambda x: thai_months[x-1] if 1<=x<=12 else "")
    df_daily['Day'] = df_daily['Date'].dt.day
    df_daily['Date'] = df_daily['Date'].dt.date 

    # --- MAPPING ---
    sku_map = df_daily.groupby('SKU_Main')['ชื่อสินค้า'].last().to_dict()
    master_skus_set = set()
    if not df_master.empty and 'SKU' in df_master.columns:
        master_skus_set = set(df_master['SKU'].astype(str).str.strip().str.replace(' ', '', regex=False))
        if 'ชื่อสินค้า' in df_master.columns:
            temp_master = df_master.copy()
            temp_master['SKU_Norm'] = temp_master['SKU'].astype(str).str.strip().str.replace(' ', '', regex=False)
            sku_map.update(temp_master.set_index('SKU_Norm')['ชื่อสินค้า'].to_dict())
    
    daily_skus_set = set(df_daily['SKU_Main'].unique())
    sku_list = sorted(list(daily_skus_set.union(master_skus_set)))

    sku_type_map = {}
    if not df_master.empty and 'SKU' in df_master.columns and 'Type' in df_master.columns:
        temp_master = df_master.copy()
        temp_master['SKU_Norm'] = temp_master['SKU'].astype(str).str.strip().str.replace(' ', '', regex=False)
        sku_type_map = temp_master.set_index('SKU_Norm')['Type'].to_dict()
    
    if 'Type' in df_daily.columns:
        daily_type_map = df_daily.groupby('SKU_Main')['Type'].first().to_dict()
        for k, v in daily_type_map.items():
            if k not in sku_type_map:
                sku_type_map[k] = v
            elif pd.isna(sku_type_map[k]) or sku_type_map[k] == '':
                sku_type_map[k] = v

    return df_daily, df_fix_cost, sku_map, sku_list, sku_type_map
# ==========================================
# 5. FRONTEND: UI
# ==========================================
try:
    df_daily, df_fix_cost, master_map_lookup, master_sku_list, sku_type_map = process_data()

    if df_daily.empty:
        st.warning("⚠️ ไม่พบข้อมูล กรุณาตรวจสอบ Google Drive")
        st.stop()

    sku_name_lookup = df_daily.groupby('SKU_Main')['ชื่อสินค้า'].last().to_dict()
    sku_name_lookup.update(master_map_lookup)
    daily_skus = df_daily['SKU_Main'].unique().tolist()
    all_skus_global = sorted(list(set(daily_skus + master_sku_list)))

    sku_options_list_global = []
    sku_map_reverse_global = {}
    for sku in all_skus_global:
        name = str(sku_name_lookup.get(sku, "")); name = "" if name in ['nan','0','0.0'] else name
        label = f"{sku} : {name}"
        sku_options_list_global.append(label)
        sku_map_reverse_global[label] = sku

    # --- CATEGORY SETTINGS ---
    CATEGORY_OPTIONS = ["แสดงทั้งหมด", "กลุ่ม DKUB", "กลุ่ม SMASH", "กลุ่ม อาหารเสริม"]

    def filter_skus_by_category(current_skus, selected_category, type_map):
        if selected_category == "แสดงทั้งหมด":
            return current_skus
        
        filtered = []
        for sku in current_skus:
            # Default to 'กลุ่ม ปกติ' if not found
            sku_type = type_map.get(sku, 'กลุ่ม ปกติ')
            if sku_type == selected_category:
                filtered.append(sku)
        return filtered
    # -------------------------

    if 'selected_skus' not in st.session_state: st.session_state.selected_skus = []
    if 'selected_skus_d' not in st.session_state: st.session_state.selected_skus_d = []
    if 'selected_skus_g' not in st.session_state: st.session_state.selected_skus_g = []
    if 'selected_skus_a' not in st.session_state: st.session_state.selected_skus_a = []

    def cb_clear_m(): st.session_state.selected_skus = []
    def cb_clear_d(): st.session_state.selected_skus_d = []
    def cb_clear_g(): st.session_state.selected_skus_g = []
    def cb_clear_a(): st.session_state.selected_skus_a = []

    # --- [ส่วนที่เพิ่ม] ปุ่ม REFRESH (SIDEBAR) ---
    with st.sidebar:
        # 1. ส่วน User และปุ่มควบคุมระบบ
        st.markdown(f"**👤 ผู้ใช้งาน:** Admin")
        
        if st.button("🚪 ออกจากระบบ", use_container_width=True):
             st.session_state.logged_in = False
             st.query_params.clear()
             st.rerun()

        if st.button("🔄 รีเฟรชข้อมูลล่าสุด", type="primary", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        
        st.markdown("---") # เส้นขีดคั่น

        # 2. หมวดเมนูจัดการไฟล์
        st.markdown("### 📂 เมนูจัดการไฟล์")
        
        # ปุ่ม: ไฟล์ยอดขาย JST
        st.link_button(
            "📁 ไฟล์ยอดขาย JST (Drive)", 
            "https://drive.google.com/drive/folders/1ciI_X2m8pVcsjRsPuUf5sg--6uPSPPDp", 
            use_container_width=True
        )
        
        # ปุ่ม: ไฟล์ค่า ADS
        st.link_button(
            "📁 ไฟล์ค่า ADS", 
            "https://drive.google.com/drive/folders/1ZE76TXNA_vNeXjhAZfLgBQQGIV0GY7w8", 
            use_container_width=True
        )

        st.markdown("---") # เส้นขีดคั่น

        # 3. หมวดตั้งค่าระบบ
        st.markdown("### ⚙️ ตั้งค่าระบบ")
        
        # ปุ่ม: ชีทตั้งค่าทุนสินค้า / พนักงาน
        st.link_button(
            "📊 ชีทตั้งค่าทุนสินค้า / พนักงาน", 
            SHEET_MASTER_URL, 
            use_container_width=True
        )
        
        # (ลบปุ่มเพิ่ม SKU ออกแล้ว เพราะลิงก์เดียวกับข้างบน)
    # --------------------------------------------

    # ค้นหาบรรทัดนี้ในโค้ดเดิมแล้วแทนที่ด้วยบรรทัดนี้
    page_options = ["📊 REPORT_MONTH", "📢 REPORT_ADS", "📅 REPORT_DAILY", "📈 PRODUCT GRAPH", "📈 YEARLY P&L", "📅 MONTHLY P&L", "💰 COMMISSION", "🔧 MASTER_ITEM"]
    selected_page = st.radio("เลือกหน้าจอที่ต้องการแสดงผล:", page_options, horizontal=True, label_visibility="collapsed")

    # --- PAGE 1: REPORT_MONTH ---
    if selected_page == "📊 REPORT_MONTH":
        st.markdown('<div class="header-bar"><div class="header-title"><i class="fas fa-chart-line"></i> สรุปยอดขายรายเดือน</div></div>', unsafe_allow_html=True)
        all_years = sorted(df_daily['Year'].unique(), reverse=True)
        
        today = datetime.now().date()
        
        def update_m_dates():
            y = st.session_state.m_y
            m_str = st.session_state.m_m
            try:
                m_idx = thai_months.index(m_str) + 1
                days_in_m = calendar.monthrange(y, m_idx)[1]
                st.session_state.m_d_start = date(y, m_idx, 1)
                st.session_state.m_d_end = date(y, m_idx, days_in_m)
            except: pass

        with st.container():
            c_y, c_m, c_s, c_e = st.columns([1, 1, 1, 1])
            if "m_d_start" not in st.session_state:
                st.session_state.m_d_start = today.replace(day=1)
                st.session_state.m_d_end = today

            with c_y: sel_year = st.selectbox("เลือกปี (ตั้งค่าเริ่มต้น)", all_years, key="m_y", on_change=update_m_dates)
            with c_m: sel_month = st.selectbox("เลือกเดือน (ตั้งค่าเริ่มต้น)", thai_months, index=today.month-1, key="m_m", on_change=update_m_dates)
            with c_s: start_date_m = st.date_input("วันที่เริ่มต้น", key="m_d_start")
            with c_e: end_date_m = st.date_input("วันที่สิ้นสุด", key="m_d_end")

            c_type, c_cat, c_sku, c_clear, c_run = st.columns([1.5, 1.5, 2.5, 0.5, 1])
            with c_type:
                filter_mode = st.selectbox("เงื่อนไขสินค้า (Fast Filter)",
                    ["📦 แสดงรายการที่มีการเคลื่อนไหว", "💰 แสดงสินค้ากำไร", "💸 แสดงสินค้าขาดทุน", "📋 แสดงรายการทั้งหมด"])
            with c_cat:
                sel_category = st.selectbox("หมวดหมู่สินค้า", CATEGORY_OPTIONS, key="m_cat")
            with c_sku: 
                st.multiselect("รายการที่เลือก (Choose options):", sku_options_list_global, key="selected_skus")
            with c_clear:
                st.markdown("<div style='margin-top: 29px;'></div>", unsafe_allow_html=True)
                st.button("🧹", type="secondary", use_container_width=True, key="btn_clear_m", on_click=cb_clear_m)
            with c_run:
                st.markdown("<div style='margin-top: 29px;'></div>", unsafe_allow_html=True)
                st.button("🚀 ประมวลผล", type="primary", use_container_width=True, key="btn_run_m")

        mask_date = (df_daily['Date'] >= start_date_m) & (df_daily['Date'] <= end_date_m)
        df_base = df_daily[mask_date]

        sku_summary = df_base.groupby('SKU_Main').agg({'รายละเอียดยอดที่ชำระแล้ว': 'sum', 'Ads_Amount': 'sum', 'Net_Profit': 'sum'}).reset_index()
        auto_skus = []
        if "แสดงสินค้ากำไร" in filter_mode: auto_skus = sku_summary[sku_summary['Net_Profit'] > 0]['SKU_Main'].tolist()
        elif "แสดงสินค้าขาดทุน" in filter_mode: auto_skus = sku_summary[sku_summary['Net_Profit'] < 0]['SKU_Main'].tolist()
        elif "แสดงรายการทั้งหมด" in filter_mode: auto_skus = all_skus_global
        else: auto_skus = sku_summary[(sku_summary['รายละเอียดยอดที่ชำระแล้ว'] > 0) | (sku_summary['Ads_Amount'] > 0)]['SKU_Main'].tolist()

        selected_labels = st.session_state.selected_skus
        selected_skus_real = [sku_map_reverse_global[l] for l in selected_labels]
        
        pre_final_skus = sorted(selected_skus_real) if selected_skus_real else sorted(auto_skus)
        final_skus = filter_skus_by_category(pre_final_skus, sel_category, sku_type_map)

        if not final_skus: st.warning(f"⚠️ ไม่พบข้อมูลสินค้าตามเงื่อนไข ในช่วงวันที่ {start_date_m} ถึง {end_date_m} (หมวดหมู่: {sel_category})")
        else:
            df_view = df_base[df_base['SKU_Main'].isin(final_skus)]
        
            total_sales = df_view['รายละเอียดยอดที่ชำระแล้ว'].sum()
            total_ads = df_view['Ads_Amount'].sum()
            total_cost_prod = df_view['CAL_COST'].sum()
            total_ops = df_view['BOX_COST'].sum() + df_view['DELIV_COST'].sum() + df_view['CAL_COD_COST'].sum()
            total_com = df_view['CAL_COM_ADMIN'].sum() + df_view['CAL_COM_TELESALE'].sum()
            total_cost_all = total_cost_prod + total_ops + total_com + total_ads
            net_profit = total_sales - total_cost_all

            render_metric_row(total_sales, total_ops, total_com, total_cost_prod, total_ads, net_profit)

            date_list = pd.date_range(start_date_m, end_date_m)
            matrix_data = []
        
            for d in date_list:
                d_date = d.date()
                day_data = df_view[df_view['Date'] == d_date]
                
                d_sales = day_data['รายละเอียดยอดที่ชำระแล้ว'].sum()
                d_orders = day_data['จำนวนออเดอร์'].sum() # ใช้จำนวนออเดอร์แทนจำนวนชิ้น
                d_profit = day_data['Net_Profit'].sum()
                d_ads = day_data['Ads_Amount'].sum()
                
                d_pct_profit = (d_profit / d_sales * 100) if d_sales != 0 else 0
                d_pct_ads = (d_ads / d_sales * 100) if d_sales != 0 else 0

                day_str = d.strftime("%a. %d/%m/%Y")

                row = {
                    'วันที่': day_str, 
                    'จำนวนออเดอร์': d_orders,
                    'ยอดขาย': d_sales, 
                    'กำไร': d_profit,
                    '%กำไร': d_pct_profit,
                    'ค่าแอด': d_ads,
                    '%แอด': d_pct_ads
                }
                
                for sku in final_skus:
                    sku_row = day_data[day_data['SKU_Main'] == sku]
                    val = sku_row['Net_Profit'].sum() if not sku_row.empty else 0
                    row[sku] = val
                matrix_data.append(row)

            df_matrix = pd.DataFrame(matrix_data)
            
            footer_sums = df_view.groupby('SKU_Main').agg({'รายละเอียดยอดที่ชำระแล้ว': 'sum', 'จำนวนออเดอร์': 'sum', 'CAL_COST': 'sum', 'Other_Costs': 'sum', 'Ads_Amount': 'sum', 'Net_Profit': 'sum',
                                                            'CAL_COM_ADMIN': 'sum', 'CAL_COM_TELESALE': 'sum'})
            footer_sums = footer_sums.reindex(final_skus, fill_value=0)

            def fmt_n(v): return f"{v:,.0f}" if v!=0 else "-"
            def fmt_p(v): return f"{v:,.1f}%" if v!=0 else "-"

            html = '<div class="table-wrapper"><table class="custom-table month-table"><thead><tr>'
            html += '<th class="fix-m-1" style="background-color:#2c3e50;color:white;">วันที่</th>'
            html += '<th class="fix-m-2" style="background-color:#2c3e50;color:white;">ยอดขาย</th>'
            html += '<th class="fix-m-3" style="background-color:#2c3e50;color:white;">ออเดอร์</th>' # เปลี่ยนหัวข้อ
            html += '<th class="fix-m-4" style="background-color:#27ae60;color:white;">กำไร</th>'
            html += '<th class="fix-m-5" style="background-color:#27ae60;color:white;">%</th>'
            html += '<th class="fix-m-6" style="background-color:#e67e22;color:white;">ค่าแอด</th>'
            html += '<th class="fix-m-7" style="background-color:#e67e22;color:white;">%</th>'

            for sku in final_skus:
                name = str(sku_name_lookup.get(sku, ""))
                html += f'<th class="th-sku">{sku}<span class="sku-header">{name}</span></th>'
            html += '</tr></thead><tbody>'
            
            for _, r in df_matrix.iterrows():
                color_profit = "#FF0000" if r["กำไร"] < 0 else "#27ae60"
                color_pct_profit = "#FF0000" if r["%กำไร"] < 0 else "#27ae60"
                html += f'<tr>'
                html += f'<td class="fix-m-1">{r["วันที่"]}</td>'
                html += f'<td class="fix-m-2" style="font-weight:bold;">{fmt_n(r["ยอดขาย"])}</td>'
                html += f'<td class="fix-m-3" style="font-weight:bold;color:#ddd;">{fmt_n(r["จำนวนออเดอร์"])}</td>' # แสดงยอดออเดอร์
                html += f'<td class="fix-m-4" style="font-weight:bold; color:{color_profit};">{fmt_n(r["กำไร"])}</td>'
                html += f'<td class="fix-m-5" style="color:{color_pct_profit};">{fmt_p(r["%กำไร"])}</td>'
                html += f'<td class="fix-m-6" style="color:#e67e22;">{fmt_n(r["ค่าแอด"])}</td>'
                html += f'<td class="fix-m-7" style="color:#e67e22;">{fmt_p(r["%แอด"])}</td>'

                for sku in final_skus:
                    val = r.get(sku, 0)
                    color = "#FF0000" if val < 0 else "#ddd"
                    html += f'<td style="color:{color};">{fmt_n(val)}</td>'
                html += '</tr>'
            
            html += '</tbody><tfoot>'

            g_sales = total_sales; g_ads = total_ads; g_cost = total_cost_prod + total_ops + total_com; g_profit = net_profit
            g_orders = df_view['จำนวนออเดอร์'].sum() # รวมยอดออเดอร์
            g_pct_profit = (g_profit / g_sales * 100) if g_sales else 0
            g_pct_ads = (g_ads / g_sales * 100) if g_sales else 0
            bg_total = "#010538"; c_total = "#ffffff"

            html += f'<tr style="background-color: {bg_total}; font-weight: bold;">'
            html += f'<td class="fix-m-1" style="background-color: {bg_total}; color: {c_total};">รวม</td>'
            html += f'<td class="fix-m-2" style="background-color: {bg_total}; color: {c_total};">{fmt_n(g_sales)}</td>'
            html += f'<td class="fix-m-3" style="background-color: {bg_total}; color: {c_total};">{fmt_n(g_orders)}</td>'
            c_prof_sum = "#7CFC00" if g_profit >= 0 else "#FF0000"
            html += f'<td class="fix-m-4" style="background-color: {bg_total}; color: {c_prof_sum};">{fmt_n(g_profit)}</td>'
            html += f'<td class="fix-m-5" style="background-color: {bg_total}; color: {c_prof_sum};">{fmt_p(g_pct_profit)}</td>'
            html += f'<td class="fix-m-6" style="background-color: {bg_total}; color: #FF6633;">{fmt_n(g_ads)}</td>'
            html += f'<td class="fix-m-7" style="background-color: {bg_total}; color: #FF6633;">{fmt_p(g_pct_ads)}</td>'

            for sku in final_skus:
                val = footer_sums.loc[sku, 'Net_Profit']
                c_sku = "#7CFC00" if val >= 0 else "#FF0000"
                html += f'<td style="background-color: {bg_total}; color: {c_sku};">{fmt_n(val)}</td>'
            html += '</tr>'
            
            def create_footer_row_new(row_cls, label, data_dict, val_type='num', dark_bg=False):
                if "row-sales" in row_cls: bg_color = "#f9a825"       
                elif "row-cost" in row_cls: bg_color = "#3366FF"      
                elif "row-ads" in row_cls: bg_color = "#b802b8"       
                elif "row-ops" in row_cls: bg_color = "#039be5"       
                elif "row-com" in row_cls: bg_color = "#259b24"       
                elif "row-pct-ads" in row_cls: bg_color = "#b802b8"    
                elif "row-pct-cost" in row_cls: bg_color = "#A020F0"   
                elif "row-pct-ops" in row_cls: bg_color = "#1E90FF"   
                elif "row-pct-com" in row_cls: bg_color = "#5e35b1"    
                else: bg_color = "#ffffff"

                if bg_color != "#ffffff": dark_bg = True
                
                target_bold_rows = ["row-pct-ads", "row-pct-cost", "row-pct-ops", "row-pct-com"]
                is_bold = row_cls in target_bold_rows
                
                style_bg = f"background-color:{bg_color};"
                lbl_color = "#ffffff" if dark_bg else "#000000"
                
                grand_val = 0
                if label == "รวมทุนสินค้า": grand_val = total_cost_prod
                elif label == "รวมยอดขาย": grand_val = g_sales
                elif label == "รวมออเดอร์": grand_val = g_orders
                elif label == "รวมค่าแอด": grand_val = g_ads
                elif label == "รวมค่าดำเนินการ": grand_val = total_ops
                elif label == "รวมค่าคอมมิชชั่น": grand_val = total_com
                elif label == "ค่าแอด / ยอดขาย": grand_val = (g_ads/g_sales*100) if g_sales else 0
                elif label == "ทุน/ยอดขาย": grand_val = (g_cost/g_sales*100) if g_sales else 0
                elif label == "ค่าดำเนินการ/ยอดขาย": grand_val = (total_ops/g_sales*100) if g_sales else 0
                elif label == "ค่าคอมมิชชั่น/ยอดขาย": grand_val = (total_com/g_sales*100) if g_sales else 0

                txt_val = fmt_p(grand_val) if val_type=='pct' else fmt_n(grand_val)
                grand_text_col = "#333333"
                if grand_val < 0: grand_text_col = "#FF0000"
                elif dark_bg: grand_text_col = "#ffffff"

                if is_bold:
                    label_display = f"<b>{label}</b>"
                    txt_val_display = f"<b>{txt_val}</b>"
                else:
                    label_display = label
                    txt_val_display = txt_val

                row_html = f'<tr class="{row_cls}">'
                row_html += f'<td class="fix-m-1" style="{style_bg} color: {lbl_color} !important;">{label_display}</td>'
                row_html += f'<td class="fix-m-2" style="{style_bg} color:{grand_text_col};">{txt_val_display}</td>'
                row_html += f'<td class="fix-m-3" style="{style_bg} color:{grand_text_col};"></td>'
                row_html += f'<td class="fix-m-4" style="{style_bg}"></td>'
                row_html += f'<td class="fix-m-5" style="{style_bg}"></td>'
                row_html += f'<td class="fix-m-6" style="{style_bg}"></td>'
                row_html += f'<td class="fix-m-7" style="{style_bg}"></td>'

                for sku in final_skus:
                    val = 0
                    if label == "รวมทุนสินค้า": 
                        val = data_dict.loc[sku, 'CAL_COST'] # <--- แก้ตรงนี้ (ลบ + data_dict.loc[sku, 'Other_Costs'] ออก)
                    elif label == "รวมยอดขาย": 
                        val = data_dict.loc[sku, 'รายละเอียดยอดที่ชำระแล้ว']
                    elif label == "รวมค่าแอด": 
                        val = data_dict.loc[sku, 'Ads_Amount']
                    elif label == "รวมค่าดำเนินการ":
                        val = (data_dict.loc[sku, 'Other_Costs'] - 
                               data_dict.loc[sku, 'CAL_COM_ADMIN'] - 
                               data_dict.loc[sku, 'CAL_COM_TELESALE'])
                    elif label == "รวมค่าคอมมิชชั่น":
                        val = data_dict.loc[sku, 'CAL_COM_ADMIN'] + data_dict.loc[sku, 'CAL_COM_TELESALE']
                    elif label == "ค่าแอด / ยอดขาย":
                        s = data_dict.loc[sku, 'รายละเอียดยอดที่ชำระแล้ว']
                        val = (data_dict.loc[sku, 'Ads_Amount']/s*100) if s else 0
                    elif label == "ทุน/ยอดขาย":
                        s = data_dict.loc[sku, 'รายละเอียดยอดที่ชำระแล้ว']
                        cost = data_dict.loc[sku, 'CAL_COST'] + data_dict.loc[sku, 'Other_Costs']
                        val = (cost/s*100) if s else 0
                    elif label == "ค่าดำเนินการ/ยอดขาย":
                        s = data_dict.loc[sku, 'รายละเอียดยอดที่ชำระแล้ว']
                        ops = (data_dict.loc[sku, 'Other_Costs'] - 
                               data_dict.loc[sku, 'CAL_COM_ADMIN'] - 
                               data_dict.loc[sku, 'CAL_COM_TELESALE'])
                        val = (ops/s*100) if s else 0
                    elif label == "ค่าคอมมิชชั่น/ยอดขาย":
                        s = data_dict.loc[sku, 'รายละเอียดยอดที่ชำระแล้ว']
                        com = data_dict.loc[sku, 'CAL_COM_ADMIN'] + data_dict.loc[sku, 'CAL_COM_TELESALE']
                        val = (com/s*100) if s else 0

                    txt = fmt_p(val) if val_type=='pct' else fmt_n(val)
                    cell_text_col = "#333333"
                    if val < 0: cell_text_col = "#FF0000"
                    elif dark_bg: cell_text_col = "#ffffff"
                    txt_display = f"<b>{txt}</b>" if is_bold else txt
                    row_html += f'<td style="{style_bg} color:{cell_text_col};">{txt_display}</td>'
                row_html += '</tr>'
                return row_html

            html += create_footer_row_new("row-sales", "รวมยอดขาย", footer_sums, 'num')
            html += create_footer_row_new("row-cost", "รวมทุนสินค้า", footer_sums, 'num')
            html += create_footer_row_new("row-ads", "รวมค่าแอด", footer_sums, 'num')
            html += create_footer_row_new("row-ops", "รวมค่าดำเนินการ", footer_sums, 'num')
            html += create_footer_row_new("row-com", "รวมค่าคอมมิชชั่น", footer_sums, 'num')
            
            html += create_footer_row_new("row-pct-ads", "ค่าแอด / ยอดขาย", footer_sums, 'pct')
            html += create_footer_row_new("row-pct-cost", "ทุน/ยอดขาย", footer_sums, 'pct')
            html += create_footer_row_new("row-pct-ops", "ค่าดำเนินการ/ยอดขาย", footer_sums, 'pct')
            html += create_footer_row_new("row-pct-com", "ค่าคอมมิชชั่น/ยอดขาย", footer_sums, 'pct')
            
            html += '</tfoot></table></div>'
            st.markdown(html, unsafe_allow_html=True)

            
    # --- [NEW] PAGE: REPORT_ADS ---
    elif selected_page == "📢 REPORT_ADS":
        st.markdown('<div class="header-bar"><div class="header-title"><i class="fas fa-bullhorn"></i> สรุปค่าโฆษณา (รายวัน)</div></div>', unsafe_allow_html=True)
        all_years = sorted(df_daily['Year'].unique(), reverse=True)
        today = datetime.now().date()
        
        def update_a_dates():
            y = st.session_state.a_y
            m_str = st.session_state.a_m
            try:
                m_idx = thai_months.index(m_str) + 1
                days_in_m = calendar.monthrange(y, m_idx)[1]
                st.session_state.a_d_start = date(y, m_idx, 1)
                st.session_state.a_d_end = date(y, m_idx, days_in_m)
            except: pass

        with st.container():
            c_y, c_m, c_s, c_e = st.columns([1, 1, 1, 1])
            if "a_d_start" not in st.session_state:
                st.session_state.a_d_start = today.replace(day=1)
                st.session_state.a_d_end = today

            with c_y: sel_year_a = st.selectbox("เลือกปี (ตั้งค่าเริ่มต้น)", all_years, key="a_y", on_change=update_a_dates)
            with c_m: sel_month_a = st.selectbox("เลือกเดือน (ตั้งค่าเริ่มต้น)", thai_months, index=today.month-1, key="a_m", on_change=update_a_dates)
            with c_s: start_date_a = st.date_input("วันที่เริ่มต้น", key="a_d_start")
            with c_e: end_date_a = st.date_input("วันที่สิ้นสุด", key="a_d_end")

            c_type, c_cat, c_sku, c_clear, c_run = st.columns([1.5, 1.5, 2.5, 0.5, 1])
            with c_type:
                filter_mode_a = st.selectbox("เงื่อนไขสินค้า (Fast Filter)",
                    ["📦 แสดงรายการที่มีการเคลื่อนไหว", "📋 แสดงรายการทั้งหมด"], key="a_filter_mode")
            with c_cat:
                sel_category_a = st.selectbox("หมวดหมู่สินค้า", CATEGORY_OPTIONS, key="a_cat")
            with c_sku: 
                st.multiselect("รายการที่เลือก (Choose options):", sku_options_list_global, key="selected_skus_a")
            with c_clear:
                st.markdown("<div style='margin-top: 29px;'></div>", unsafe_allow_html=True)
                st.button("🧹", type="secondary", use_container_width=True, key="btn_clear_a", on_click=cb_clear_a)
            with c_run:
                st.markdown("<div style='margin-top: 29px;'></div>", unsafe_allow_html=True)
                st.button("🚀 ประมวลผล", type="primary", use_container_width=True, key="btn_run_a")

        mask_date_a = (df_daily['Date'] >= start_date_a) & (df_daily['Date'] <= end_date_a)
        df_base_a = df_daily[mask_date_a]

        sku_summary_a = df_base_a.groupby('SKU_Main').agg({'Ads_Amount': 'sum', 'รายละเอียดยอดที่ชำระแล้ว': 'sum'}).reset_index()
        auto_skus_a = []
        if "แสดงรายการทั้งหมด" in filter_mode_a: auto_skus_a = all_skus_global
        else: auto_skus_a = sku_summary_a[(sku_summary_a['Ads_Amount'] > 0) | (sku_summary_a['รายละเอียดยอดที่ชำระแล้ว'] > 0)]['SKU_Main'].tolist()

        selected_labels_a = st.session_state.selected_skus_a
        selected_skus_real_a = [sku_map_reverse_global[l] for l in selected_labels_a]
        
        pre_final_skus_a = sorted(selected_skus_real_a) if selected_skus_real_a else sorted(auto_skus_a)
        final_skus_a = filter_skus_by_category(pre_final_skus_a, sel_category_a, sku_type_map)

        if not final_skus_a: 
            st.warning(f"⚠️ ไม่พบข้อมูลสินค้าตามเงื่อนไข ในช่วงวันที่ {start_date_a} ถึง {end_date_a}")
        else:
            df_view_a = df_base_a[df_base_a['SKU_Main'].isin(final_skus_a)]
            
            total_sales = df_view_a['รายละเอียดยอดที่ชำระแล้ว'].sum()
            total_ads = df_view_a['Ads_Amount'].sum()
            total_cost_prod = df_view_a['CAL_COST'].sum()
            total_ops = df_view_a['BOX_COST'].sum() + df_view_a['DELIV_COST'].sum() + df_view_a['CAL_COD_COST'].sum()
            total_com = df_view_a['CAL_COM_ADMIN'].sum() + df_view_a['CAL_COM_TELESALE'].sum()
            total_cost_all = total_cost_prod + total_ops + total_com + total_ads
            net_profit = total_sales - total_cost_all

            render_metric_row(total_sales, total_ops, total_com, total_cost_prod, total_ads, net_profit)
            
            date_list_a = pd.date_range(start_date_a, end_date_a)
            matrix_data_a = []
            
            for d in date_list_a:
                d_date = d.date()
                day_data = df_view_a[df_view_a['Date'] == d_date]
                d_total_ads = day_data['Ads_Amount'].sum()
                day_str = d.strftime("%a. %d/%m/%Y")
                row = {
                    'วันที่': day_str,
                    'ค่าแอดรวม': d_total_ads
                }
                for sku in final_skus_a:
                    val = day_data[day_data['SKU_Main'] == sku]['Ads_Amount'].sum()
                    row[sku] = val
                matrix_data_a.append(row)
                
            df_matrix_a = pd.DataFrame(matrix_data_a)
            footer_sums_a = df_view_a.groupby('SKU_Main')['Ads_Amount'].sum()
            total_period_ads = footer_sums_a.sum()
            
            def fmt_n(v): return f"{v:,.0f}" if v!=0 else "-"
            
            html = '<div class="table-wrapper"><table class="custom-table month-table"><thead><tr>'
            html += '<th class="fix-m-1" style="background-color:#2c3e50;color:white;">วันที่</th>'
            html += '<th class="fix-m-2" style="background-color:#e67e22;color:white;border-right: 2px solid #bbb !important;">ค่าแอดรวม</th>'
            for sku in final_skus_a:
                name = str(sku_name_lookup.get(sku, ""))
                html += f'<th class="th-sku">{sku}<span class="sku-header">{name}</span></th>'
            html += '</tr></thead><tbody>'
            
            for _, r in df_matrix_a.iterrows():
                html += '<tr>'
                html += f'<td class="fix-m-1">{r["วันที่"]}</td>'
                html += f'<td class="fix-m-2" style="font-weight:bold; color:#e67e22; border-right: 2px solid #bbb !important;">{fmt_n(r["ค่าแอดรวม"])}</td>'
                for sku in final_skus_a:
                    val = r.get(sku, 0)
                    color = "#e67e22" if val > 0 else "#ddd"
                    html += f'<td style="color:{color};">{fmt_n(val)}</td>'
                html += '</tr>'
            
            html += '</tbody><tfoot>'
            bg_total = "#010538"; c_total = "#ffffff"
            html += f'<tr style="background-color: {bg_total}; font-weight: bold;">'
            html += f'<td class="fix-m-1" style="background-color: {bg_total}; color: {c_total};">รวม</td>'
            html += f'<td class="fix-m-2" style="background-color: {bg_total}; color: #FF6633; border-right: 2px solid #bbb !important;">{fmt_n(total_period_ads)}</td>'
            for sku in final_skus_a:
                val = footer_sums_a.get(sku, 0)
                html += f'<td style="background-color: {bg_total}; color: #FF6633;">{fmt_n(val)}</td>'
            html += '</tr></tfoot></table></div>'
            st.markdown(html, unsafe_allow_html=True)

    # --- PAGE 2: REPORT_DAILY ---
    elif selected_page == "📅 REPORT_DAILY":
        st.markdown('<div class="header-bar"><div class="header-title"><i class="fas fa-calendar-day"></i> สรุปการขายรายวัน (ตามช่วงเวลา)</div></div>', unsafe_allow_html=True)
        
        all_years = sorted(df_daily['Year'].unique(), reverse=True)
        today = datetime.now().date()

        def update_d_dates():
            y = st.session_state.d_y
            m_str = st.session_state.d_m
            try:
                m_idx = thai_months.index(m_str) + 1
                days_in_m = calendar.monthrange(y, m_idx)[1]
                st.session_state.d_d_start = date(y, m_idx, 1)
                st.session_state.d_d_end = date(y, m_idx, days_in_m)
            except: pass

        with st.container():
            if "d_d_start" not in st.session_state:
                st.session_state.d_d_start = today.replace(day=1)
                st.session_state.d_d_end = today

            c_y, c_m, c_s, c_e = st.columns([1, 1, 1, 1])
            with c_y: sel_year_d = st.selectbox("เลือกปี (ตั้งค่าเริ่มต้น)", all_years, key="d_y", on_change=update_d_dates)
            with c_m: sel_month_d = st.selectbox("เลือกเดือน (ตั้งค่าเริ่มต้น)", thai_months, index=today.month-1, key="d_m", on_change=update_d_dates)
            with c_s: start_d = st.date_input("วันที่เริ่มต้น", key="d_d_start")
            with c_e: end_d = st.date_input("วันที่สิ้นสุด", key="d_d_end")

            c_type, c_cat, c_sku, c_clear, c_run = st.columns([1.5, 1.5, 2.5, 0.5, 1])
            with c_type:
                filter_mode_d = st.selectbox("เงื่อนไขสินค้า (Fast Filter)", 
                    ["📦 แสดงรายการที่มีการเคลื่อนไหว", "💰 แสดงสินค้ากำไร", "💸 แสดงสินค้าขาดทุน", "📋 แสดงรายการทั้งหมด"], key="d_m_filter")
            with c_cat:
                sel_category_d = st.selectbox("หมวดหมู่สินค้า", CATEGORY_OPTIONS, key="d_cat")
            with c_sku: 
                st.multiselect("รายการที่เลือก (Choose options):", sku_options_list_global, key="selected_skus_d")
            with c_clear:
                st.markdown("<div style='margin-top: 29px;'></div>", unsafe_allow_html=True)
                st.button("🧹", type="secondary", use_container_width=True, key="btn_clear_d", on_click=cb_clear_d)
            with c_run:
                st.markdown("<div style='margin-top: 29px;'></div>", unsafe_allow_html=True)
                st.button("🚀 ประมวลผล", type="primary", use_container_width=True, key="btn_run_d")

        mask = (df_daily['Date'] >= start_d) & (df_daily['Date'] <= end_d)
        df_range = df_daily[mask]

        df_grouped = df_range.groupby(['SKU_Main']).agg({
            'ชื่อสินค้า': 'last', 
            'จำนวนออเดอร์': 'sum', 
            'จำนวน': 'sum', 
            'รายละเอียดยอดที่ชำระแล้ว': 'sum',
            'CAL_COST': 'sum', 'BOX_COST': 'sum', 'DELIV_COST': 'sum', 'CAL_COD_COST': 'sum',
            'CAL_COM_ADMIN': 'sum', 'CAL_COM_TELESALE': 'sum', 'Ads_Amount': 'sum', 'Net_Profit': 'sum'
        }).reset_index()
        df_grouped['ชื่อสินค้า'] = df_grouped['SKU_Main'].map(sku_name_lookup).fillna("ไม่ระบุชื่อ")

        auto_skus_d = []
        if "แสดงสินค้ากำไร" in filter_mode_d: auto_skus_d = df_grouped[df_grouped['Net_Profit'] > 0]['SKU_Main'].tolist()
        elif "แสดงสินค้าขาดทุน" in filter_mode_d: auto_skus_d = df_grouped[df_grouped['Net_Profit'] < 0]['SKU_Main'].tolist()
        elif "แสดงรายการทั้งหมด" in filter_mode_d: auto_skus_d = all_skus_global
        else: auto_skus_d = df_grouped[(df_grouped['รายละเอียดยอดที่ชำระแล้ว'] > 0) | (df_grouped['Ads_Amount'] > 0)]['SKU_Main'].tolist()

        selected_labels_d = st.session_state.selected_skus_d
        selected_skus_real_d = [sku_map_reverse_global[l] for l in selected_labels_d]
        
        pre_final_skus_d = sorted(selected_skus_real_d) if selected_skus_real_d else sorted(auto_skus_d)
        final_skus_d = filter_skus_by_category(pre_final_skus_d, sel_category_d, sku_type_map)

        df_final_d = df_grouped[df_grouped['SKU_Main'].isin(final_skus_d)].copy()

        if df_final_d.empty: st.warning(f"⚠️ ไม่พบข้อมูลตามเงื่อนไข ({sel_category_d}) ในช่วงเวลานี้")
        else:
            sum_sales = df_final_d['รายละเอียดยอดที่ชำระแล้ว'].sum()
            sum_ads = df_final_d['Ads_Amount'].sum()
            sum_cost_prod = df_final_d['CAL_COST'].sum()
            sum_ops = df_final_d['BOX_COST'].sum() + df_final_d['DELIV_COST'].sum() + df_final_d['CAL_COD_COST'].sum()
            sum_com = df_final_d['CAL_COM_ADMIN'].sum() + df_final_d['CAL_COM_TELESALE'].sum()
            sum_profit = df_final_d['Net_Profit'].sum()
            
            render_metric_row(sum_sales, sum_ops, sum_com, sum_cost_prod, sum_ads, sum_profit)

            df_final_d['กำไร/ขาดทุน'] = df_final_d['Net_Profit']
            df_final_d['ROAS'] = np.where(df_final_d['Ads_Amount']>0, df_final_d['รายละเอียดยอดที่ชำระแล้ว']/df_final_d['Ads_Amount'], 0)
            sls = df_final_d['รายละเอียดยอดที่ชำระแล้ว']

            val_ops_item = df_final_d['BOX_COST'] + df_final_d['DELIV_COST'] + df_final_d['CAL_COD_COST']
            df_final_d['% ค่าดำเนินการ'] = np.where(sls>0, (val_ops_item/sls)*100, 0)

            val_com_item = df_final_d['CAL_COM_ADMIN'] + df_final_d['CAL_COM_TELESALE']
            df_final_d['% ค่าคอมมิชชัน'] = np.where(sls>0, (val_com_item/sls)*100, 0)

            df_final_d['% ทุนสินค้า'] = np.where(sls>0, (df_final_d['CAL_COST']/sls)*100, 0)
            df_final_d['% Ads'] = np.where(sls>0, (df_final_d['Ads_Amount']/sls)*100, 0)
            df_final_d['% กำไร'] = np.where(sls>0, (df_final_d['Net_Profit']/sls)*100, 0)
            
            df_final_d = df_final_d.sort_values('กำไร/ขาดทุน', ascending=False)

            def fmt(val, is_percent=False):
                if val == 0 or pd.isna(val): return "-"
                text = f"{val:,.2f}%" if is_percent else f"{val:,.2f}"
                return text

            def get_cell_style(val):
                if isinstance(val, (int, float)) and val < 0:
                    return ' style="color: #FF0000 !important; font-weight: bold !important;" class="negative-value"'
                return '' 

            st.markdown("##### 📋 รายละเอียดสินค้า")
            
            cols_cfg = [
                ('SKU', 'SKU_Main', ''), 
                ('ชื่อสินค้า', 'ชื่อสินค้า', ''), 
                ('ออเดอร์', 'จำนวนออเดอร์', ''), # Changed
                ('ยอดขาย', 'รายละเอียดยอดที่ชำระแล้ว', ''), 
                ('ต้นทุน', 'CAL_COST', ''), 
                ('ค่ากล่อง', 'BOX_COST', ''), 
                ('ค่าส่ง', 'DELIV_COST', ''), 
                ('COD', 'CAL_COD_COST', ''), 
                ('Admin', 'CAL_COM_ADMIN', ''), 
                ('Tele', 'CAL_COM_TELESALE', ''), 
                ('ค่า Ads', 'Ads_Amount', ''), 
                ('กำไร', 'Net_Profit', ''), 
                ('ROAS', 'ROAS', 'col-small'), 
                ('%ค่าดำเนินการ', '% ค่าดำเนินการ', 'col-medium'), 
                ('%ค่าคอม', '% ค่าคอมมิชชัน', 'col-medium'),       
                ('%ทุน', '% ทุนสินค้า', 'col-small'), 
                ('%Ads', '% Ads', 'col-small'), 
                ('%กำไร', '% กำไร', 'col-small')
            ]

            html = '<div class="table-wrapper"><table class="custom-table daily-table"><thead><tr>'
            for title, _, cls in cols_cfg: html += f'<th class="{cls}">{title}</th>'
            html += '</tr></thead><tbody>'

            for i, (_, r) in enumerate(df_final_d.iterrows()):
                html += '<tr>'
                html += f'<td style="font-weight:bold;color:#1e3c72 !important;">{r["SKU_Main"]}</td>'
                html += f'<td style="text-align:left;font-size:11px;color:#1e3c72 !important; max-width: 100px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="{r["ชื่อสินค้า"]}">{r["ชื่อสินค้า"]}</td>'
                html += f'<td{get_cell_style(r["จำนวนออเดอร์"])}>{fmt(r["จำนวนออเดอร์"])}</td>' # Show Orders
                html += f'<td{get_cell_style(r["รายละเอียดยอดที่ชำระแล้ว"])}>{fmt(r["รายละเอียดยอดที่ชำระแล้ว"])}</td>'
                html += f'<td{get_cell_style(r["CAL_COST"])}>{fmt(r["CAL_COST"])}</td>'
                html += f'<td{get_cell_style(r["BOX_COST"])}>{fmt(r["BOX_COST"])}</td>'
                html += f'<td{get_cell_style(r["DELIV_COST"])}>{fmt(r["DELIV_COST"])}</td>'
                html += f'<td{get_cell_style(r["CAL_COD_COST"])}>{fmt(r["CAL_COD_COST"])}</td>'
                html += f'<td{get_cell_style(r["CAL_COM_ADMIN"])}>{fmt(r["CAL_COM_ADMIN"])}</td>'
                html += f'<td{get_cell_style(r["CAL_COM_TELESALE"])}>{fmt(r["CAL_COM_TELESALE"])}</td>'
                html += f'<td style="color:#e67e22 !important;">{fmt(r["Ads_Amount"])}</td>'
                html += f'<td{get_cell_style(r["Net_Profit"])}>{fmt(r["Net_Profit"])}</td>'
                html += f'<td class="col-small" style="color:#1e3c72 !important;">{fmt(r["ROAS"])}</td>'
                html += f'<td class="col-small" style="color:#1e3c72 !important;">{fmt(r["% ค่าดำเนินการ"],True)}</td>'
                html += f'<td class="col-small" style="color:#1e3c72 !important;">{fmt(r["% ค่าคอมมิชชัน"],True)}</td>'
                html += f'<td class="col-small" style="color:#1e3c72 !important;">{fmt(r["% ทุนสินค้า"],True)}</td>'
                html += f'<td class="col-small" style="color:#1e3c72 !important;">{fmt(r["% Ads"],True)}</td>'
                html += f'<td class="col-small"{get_cell_style(r["% กำไร"])}>{fmt(r["% กำไร"],True)}</td>'
                html += '</tr>'

            html += '<tr class="footer-row"><td>TOTAL</td><td></td>'
            ts = df_final_d['รายละเอียดยอดที่ชำระแล้ว'].sum(); tp = df_final_d['Net_Profit'].sum()
            ta = df_final_d['Ads_Amount'].sum(); tc = df_final_d['CAL_COST'].sum()
            t_box = df_final_d['BOX_COST'].sum()
            t_ship = df_final_d['DELIV_COST'].sum()
            t_cod = df_final_d['CAL_COD_COST'].sum()
            t_adm = df_final_d['CAL_COM_ADMIN'].sum()
            t_tel = df_final_d['CAL_COM_TELESALE'].sum()

            html += f'<td{get_cell_style(df_final_d["จำนวนออเดอร์"].sum())}>{fmt(df_final_d["จำนวนออเดอร์"].sum())}</td>' # Sum Orders
            html += f'<td{get_cell_style(ts)}>{fmt(ts)}</td>'
            html += f'<td{get_cell_style(tc)}>{fmt(tc)}</td>'
            html += f'<td{get_cell_style(t_box)}>{fmt(t_box)}</td>'
            html += f'<td{get_cell_style(t_ship)}>{fmt(t_ship)}</td>'
            html += f'<td{get_cell_style(t_cod)}>{fmt(t_cod)}</td>'
            html += f'<td{get_cell_style(t_adm)}>{fmt(t_adm)}</td>'
            html += f'<td{get_cell_style(t_tel)}>{fmt(t_tel)}</td>'
            html += f'<td{get_cell_style(ta)}>{fmt(ta)}</td>'
            html += f'<td{get_cell_style(tp)}>{fmt(tp)}</td>'

            f_roas = ts/ta if ta>0 else 0
            val_pct_ops = ((t_box + t_ship + t_cod)/ts*100) if ts>0 else 0
            val_pct_comm = ((t_adm + t_tel)/ts*100) if ts>0 else 0
            val_pct_cost = (tc/ts*100) if ts>0 else 0
            val_pct_ads = (ta/ts*100) if ts>0 else 0
            val_pct_profit = (tp/ts*100) if ts>0 else 0
            
            html += f'<td class="col-small"{get_cell_style(f_roas)}>{fmt(f_roas)}</td>'
            html += f'<td class="col-medium"{get_cell_style(val_pct_ops)}>{fmt(val_pct_ops,True)}</td>'
            html += f'<td class="col-medium"{get_cell_style(val_pct_comm)}>{fmt(val_pct_comm,True)}</td>'
            html += f'<td class="col-small"{get_cell_style(val_pct_cost)}>{fmt(val_pct_cost,True)}</td>'
            html += f'<td class="col-small"{get_cell_style(val_pct_ads)}>{fmt(val_pct_ads,True)}</td>'
            html += f'<td class="col-small"{get_cell_style(val_pct_profit)}>{fmt(val_pct_profit,True)}</td></tr></tbody></table></div>'
            st.markdown(html, unsafe_allow_html=True)

    # --- PAGE 3: PRODUCT GRAPH ---
    elif selected_page == "📈 PRODUCT GRAPH":
        st.markdown('<div class="header-bar"><div class="header-title"><i class="fas fa-chart-line"></i> กราฟแสดงแนวโน้มยอดขายรายสินค้า</div></div>', unsafe_allow_html=True)

        with st.container():
            c_g1, c_g2, c_g3 = st.columns([1, 1, 2])
            with c_g1: start_g = st.date_input("เริ่มวันที่", datetime.now().replace(day=1), key="g_s")
            with c_g2: end_g = st.date_input("ถึงวันที่", datetime.now(), key="g_e")
            with c_g3: filter_mode_g = st.selectbox("เงื่อนไขสินค้า (Fast Filter)",
                ["📦 แสดงรายการที่มีการเคลื่อนไหว", "💰 แสดงสินค้ากำไร", "💸 แสดงสินค้าขาดทุน", "📋 แสดงรายการทั้งหมด"], key="g_m")

            c_cat, c_sku, c_clear, c_run = st.columns([1.5, 3, 0.5, 1])
            with c_cat:
                sel_category_g = st.selectbox("หมวดหมู่สินค้า", CATEGORY_OPTIONS, key="g_cat")

            with c_sku: st.multiselect("เลือกสินค้าที่ต้องการดูกราฟ:", sku_options_list_global, key="selected_skus_g")
            with c_clear:
                st.markdown("<div style='margin-top: 29px;'></div>", unsafe_allow_html=True)
                st.button("🧹", type="secondary", use_container_width=True, key="btn_clear_g", on_click=cb_clear_g)
            with c_run:
                st.markdown("<div style='margin-top: 29px;'></div>", unsafe_allow_html=True)
                st.button("🚀 สร้างกราฟ", type="primary", use_container_width=True, key="btn_run_g")

        mask_g_date = (df_daily['Date'] >= pd.to_datetime(start_g).date()) & (df_daily['Date'] <= pd.to_datetime(end_g).date())
        df_range_g = df_daily[mask_g_date]

        sku_stats_g = df_range_g.groupby('SKU_Main').agg({'รายละเอียดยอดที่ชำระแล้ว': 'sum', 'Ads_Amount': 'sum', 'Net_Profit': 'sum'}).reset_index()
        auto_skus_g = []

        if "แสดงสินค้ากำไร" in filter_mode_g:
            auto_skus_g = sku_stats_g[sku_stats_g['Net_Profit'] > 0]['SKU_Main'].tolist()
        elif "แสดงสินค้าขาดทุน" in filter_mode_g:
            auto_skus_g = sku_stats_g[sku_stats_g['Net_Profit'] < 0]['SKU_Main'].tolist()
        elif "แสดงรายการทั้งหมด" in filter_mode_g:
            auto_skus_g = all_skus_global
        else: # แสดงรายการที่มีการเคลื่อนไหว
            auto_skus_g = sku_stats_g[(sku_stats_g['รายละเอียดยอดที่ชำระแล้ว'] > 0) | (sku_stats_g['Ads_Amount'] > 0)]['SKU_Main'].tolist()

        selected_labels_g = st.session_state.selected_skus_g
        real_selected_g = [sku_map_reverse_global[l] for l in selected_labels_g]

        pre_final_skus_g = sorted(real_selected_g) if real_selected_g else sorted(auto_skus_g)
        final_skus_g = filter_skus_by_category(pre_final_skus_g, sel_category_g, sku_type_map)

        if not final_skus_g:
            st.info(f"👈 ไม่พบข้อมูลตามเงื่อนไข ({sel_category_g}) หรือกรุณาเลือกสินค้า")
        else:
            df_graph = df_range_g[df_range_g['SKU_Main'].isin(final_skus_g)].copy()

            if df_graph.empty:
                st.warning("⚠️ ไม่พบข้อมูลการขายของสินค้าที่เลือกในช่วงเวลานี้")
            else:
                g_sales = df_graph['รายละเอียดยอดที่ชำระแล้ว'].sum()
                g_ads = df_graph['Ads_Amount'].sum()
                g_cost_prod = df_graph['CAL_COST'].sum()
                g_ops = df_graph['BOX_COST'].sum() + df_graph['DELIV_COST'].sum() + df_graph['CAL_COD_COST'].sum()
                g_com = df_graph['CAL_COM_ADMIN'].sum() + df_graph['CAL_COM_TELESALE'].sum()
                g_net_profit = df_graph['Net_Profit'].sum()
                
                render_metric_row(g_sales, g_ops, g_com, g_cost_prod, g_ads, g_net_profit)
                
                df_chart = df_graph.groupby(['Date', 'SKU_Main']).agg({
                    'รายละเอียดยอดที่ชำระแล้ว': 'sum',
                    'จำนวน': 'sum'
                }).reset_index()

                df_chart['Product_Name'] = df_chart['SKU_Main'].apply(lambda x: f"{x} : {sku_name_lookup.get(x, '')}")
                df_chart['DateStr'] = df_chart['Date'].astype(str)

                st.markdown("##### 📈 แนวโน้มยอดขายรายวัน (Sales Trend)")
                chart_line = alt.Chart(df_chart).mark_line(point=True).encode(
                    x=alt.X('DateStr', title='วันที่'),
                    y=alt.Y('รายละเอียดยอดที่ชำระแล้ว', title='ยอดขาย (บาท)'),
                    color=alt.Color('Product_Name', title='สินค้า'),
                    tooltip=['DateStr', 'Product_Name', alt.Tooltip('รายละเอียดยอดที่ชำระแล้ว', format=',.0f'), 'จำนวน']
                ).interactive()
                st.altair_chart(chart_line, use_container_width=True)

                st.markdown("---")
                c_bar1, c_bar2 = st.columns(2)

                with c_bar1:
                    st.markdown("##### 📊 สรุปยอดขายรวมตามช่วงเวลา (Total Sales)")
                    df_bar_sum = df_chart.groupby('Product_Name')['รายละเอียดยอดที่ชำระแล้ว'].sum().reset_index()
                    chart_bar = alt.Chart(df_bar_sum).mark_bar().encode(
                        x=alt.X('Product_Name', title=None, axis=alt.Axis(labels=False)),
                        y=alt.Y('รายละเอียดยอดที่ชำระแล้ว', title='ยอดขายรวม (บาท)'),
                        color=alt.Color('Product_Name', legend=None),
                        tooltip=['Product_Name', alt.Tooltip('รายละเอียดยอดที่ชำระแล้ว', format=',.0f')]
                    )
                    st.altair_chart(chart_bar, use_container_width=True)

                with c_bar2:
                    st.markdown("##### 📦 สรุปจำนวนชิ้นที่ขายได้ (Total Units)")
                    df_qty_sum = df_chart.groupby('Product_Name')['จำนวน'].sum().reset_index()
                    chart_bar_qty = alt.Chart(df_qty_sum).mark_bar().encode(
                        x=alt.X('Product_Name', title=None, axis=alt.Axis(labels=False)),
                        y=alt.Y('จำนวน', title='จำนวน (ชิ้น)'),
                        color=alt.Color('Product_Name', legend=None),
                        tooltip=['Product_Name', alt.Tooltip('จำนวน', format=',.0f')]
                    )
                    st.altair_chart(chart_bar_qty, use_container_width=True)

    # --- PAGE 4: YEARLY P&L ---
    elif selected_page == "📈 YEARLY P&L":
        st.markdown('<div class="pnl-container">', unsafe_allow_html=True)
        st.markdown("""
        <div class="header-gradient-pnl">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <h1 class="header-title-pnl">แดชบอร์ดกำไร-ขาดทุน (รายปี)</h1>
                    <p class="header-sub-pnl">ภาพรวมผลประกอบการรายปี</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        c_year, c_dummy = st.columns([1, 5])
        with c_year:
            sel_year_pnl = st.selectbox("เลือกปีงบประมาณ", sorted(df_daily['Year'].unique(), reverse=True), key="pnl_year")

        df_yr = df_daily[df_daily['Year'] == sel_year_pnl].copy()

        if df_yr.empty:
            st.warning("ไม่พบข้อมูลสำหรับปีที่เลือก")
        else:
            df_m = df_yr.groupby('Month_Num').agg({
                'รายละเอียดยอดที่ชำระแล้ว': 'sum',
                'CAL_COST': 'sum', 'BOX_COST': 'sum',
                'DELIV_COST': 'sum', 'CAL_COD_COST': 'sum', 'CAL_COM_ADMIN': 'sum', 'CAL_COM_TELESALE': 'sum', 'Ads_Amount': 'sum',
                'Net_Profit': 'sum'
            }).reset_index()

            monthly_fix = []
            for m in range(1, 13):
                f_cost = 0 
                monthly_fix.append(f_cost)

            df_template = pd.DataFrame({'Month_Num': range(1, 13)})
            df_merged = pd.merge(df_template, df_m, on='Month_Num', how='left').fillna(0)
            df_merged['Month_Thai'] = df_merged['Month_Num'].apply(lambda x: thai_months[x-1])
            df_merged['Fix_Cost'] = monthly_fix

            df_merged['COGS_Total'] = df_merged['CAL_COST'] + df_merged['BOX_COST']
            df_merged['Selling_Exp'] = df_merged['DELIV_COST'] + df_merged['CAL_COD_COST'] + df_merged['CAL_COM_ADMIN'] + df_merged['CAL_COM_TELESALE'] + df_merged['Ads_Amount']
            df_merged['Total_Exp'] = df_merged['COGS_Total'] + df_merged['Selling_Exp'] + df_merged['Fix_Cost']
            df_merged['Net_Profit_Final'] = df_merged['รายละเอียดยอดที่ชำระแล้ว'] - df_merged['Total_Exp']

            total_sales = df_merged['รายละเอียดยอดที่ชำระแล้ว'].sum()
            total_ads = df_merged['Ads_Amount'].sum()
            total_cost_prod = df_merged['CAL_COST'].sum()
            total_ops = df_merged['BOX_COST'].sum() + df_merged['DELIV_COST'].sum() + df_merged['CAL_COD_COST'].sum()
            total_com = df_merged['CAL_COM_ADMIN'].sum() + df_merged['CAL_COM_TELESALE'].sum()
            total_profit = df_merged['Net_Profit_Final'].sum()
            
            render_metric_row(total_sales, total_ops, total_com, total_cost_prod, total_ads, total_profit)

            pct_net_income = (total_sales / total_sales * 100) if total_sales else 0
            pct_exp = ((total_ops + total_com + total_cost_prod + total_ads) / total_sales * 100) if total_sales else 0
            net_margin = (total_profit / total_sales * 100) if total_sales else 0

            def fmt(v): return f"{v:,.0f}"
            def fmt_p(v): return f"{v:,.2f}%"

            c_chart1, c_chart2 = st.columns(2)

            with c_chart1:
                st.markdown('<div class="chart-box"><div class="chart-header"><span class="pill" style="background:#3b82f6"></span> ภาพรวมยอดขาย & กำไรสุทธิ (รายปี)</div>', unsafe_allow_html=True)
                base = alt.Chart(df_merged).encode(x=alt.X('Month_Thai', sort=thai_months, title=None))
                bar1 = base.mark_bar(color='#3b82f6', opacity=0.8, cornerRadiusEnd=4).encode(
                    y=alt.Y('รายละเอียดยอดที่ชำระแล้ว', title='บาท'),
                    tooltip=['Month_Thai', alt.Tooltip('รายละเอียดยอดที่ชำระแล้ว', title='ยอดขาย', format=',.0f')]
                )
                line1 = base.mark_line(color='#10b981', strokeWidth=3, point=True).encode(
                    y=alt.Y('Net_Profit_Final', title='กำไรสุทธิ'),
                    tooltip=['Month_Thai', alt.Tooltip('Net_Profit_Final', title='กำไรสุทธิ', format=',.0f')]
                )
                st.altair_chart((bar1 + line1).interactive(), use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

            with c_chart2:
                st.markdown('<div class="chart-box"><div class="chart-header"><span class="pill" style="background:#f87171"></span> สัดส่วนค่าใช้จ่าย (ทั้งปี)</div>', unsafe_allow_html=True)
                exp_data = pd.DataFrame([
                    {'Type': 'ต้นทุนสินค้า', 'Value': df_merged['CAL_COST'].sum()},
                    {'Type': 'ค่ากล่อง', 'Value': df_merged['BOX_COST'].sum()},
                    {'Type': 'ค่าส่ง', 'Value': df_merged['DELIV_COST'].sum()},
                    {'Type': 'ค่า COD', 'Value': df_merged['CAL_COD_COST'].sum()},
                    {'Type': 'ค่าคอม Admin', 'Value': df_merged['CAL_COM_ADMIN'].sum()},
                    {'Type': 'ค่าคอม Tele', 'Value': df_merged['CAL_COM_TELESALE'].sum()},
                    {'Type': 'ค่า Ads', 'Value': df_merged['Ads_Amount'].sum()}
                ])
                exp_data = exp_data[exp_data['Value'] > 0]

                if not exp_data.empty:
                    donut = alt.Chart(exp_data).mark_arc(innerRadius=70).encode(
                        theta=alt.Theta("Value", stack=True),
                        color=alt.Color("Type", scale=alt.Scale(scheme='tableau10'), legend=alt.Legend(orient='right')),
                        tooltip=["Type", alt.Tooltip("Value", format=",.0f")]
                    )
                    st.altair_chart(donut, use_container_width=True)
                else:
                    st.info("ไม่มีข้อมูลค่าใช้จ่าย")
                st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="chart-box"><div class="chart-header">งบกำไรขาดทุน (Profit & Loss Statement)</div>', unsafe_allow_html=True)

            t_sales = df_merged['รายละเอียดยอดที่ชำระแล้ว'].sum()
            t_prod_cost = df_merged['CAL_COST'].sum()
            t_box_cost = df_merged['BOX_COST'].sum()
            t_gross = t_sales - t_prod_cost - t_box_cost
            t_ship = df_merged['DELIV_COST'].sum()
            t_cod = df_merged['CAL_COD_COST'].sum()
            t_admin = df_merged['CAL_COM_ADMIN'].sum()
            t_tele = df_merged['CAL_COM_TELESALE'].sum()
            t_ads = df_merged['Ads_Amount'].sum()
            t_fix = df_merged['Fix_Cost'].sum()
            t_net = t_gross - t_ship - t_cod - t_admin - t_tele - t_ads - t_fix

            def row_html(label, val, is_head=False, is_neg=False, is_sub=False):
                cls = "pnl-row-head" if is_head else ("sub-item" if is_sub else "")
                val_cls = "neg" if val < 0 else ""
                return f'<tr class="{cls}"><td>{label}</td><td class="num-cell {val_cls}">{fmt(val)}</td></tr>'

            table_html = f"""
            <table class="pnl-table">
                <thead><tr><th>รายการ (Accounts)</th><th style="text-align:right">จำนวนเงิน (THB)</th></tr></thead>
                <tbody>
                    {row_html("รายได้จากการขาย (Sales Revenue)", t_sales, True)}
                    {row_html("หัก ต้นทุนสินค้า (Product Cost)", -t_prod_cost)}
                    {row_html("หัก ค่ากล่อง (Box Cost)", -t_box_cost)}
                    {row_html("กำไรขั้นต้น (Gross Profit)", t_gross, True, t_gross<0)}
                    {row_html("หัก ค่าส่ง (Shipping)", -t_ship, is_sub=True)}
                    {row_html("หัก ค่า COD", -t_cod, is_sub=True)}
                    {row_html("หัก ค่าคอม Admin", -t_admin, is_sub=True)}
                    {row_html("หัก ค่าคอม Telesale", -t_tele, is_sub=True)}
                    {row_html("หัก ค่า ADS", -t_ads, is_sub=True)}
                    {row_html("กำไร(ขาดทุน) สุทธิ (Net Profit)", t_net, True, t_net<0)}
                </tbody>
            </table>
            """
            st.markdown(table_html, unsafe_allow_html=True)
            st.markdown('</div></div>', unsafe_allow_html=True)

    # --- PAGE 5: MONTHLY P&L ---
    elif selected_page == "📅 MONTHLY P&L":
        st.markdown('<div class="pnl-container">', unsafe_allow_html=True)
        st.markdown("""
        <div class="header-gradient-pnl">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <h1 class="header-title-pnl">แดชบอร์ดกำไร-ขาดทุน (รายเดือน)</h1>
                    <p class="header-sub-pnl">เจาะลึกรายละเอียดรายเดือน</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        c_y, c_m, c_d = st.columns([1, 1, 4])
        with c_y: sel_y_m = st.selectbox("เลือกปี", sorted(df_daily['Year'].unique(), reverse=True), key="pm_y")
        with c_m: sel_m_m = st.selectbox("เลือกเดือน", thai_months, index=datetime.now().month-1, key="pm_m")

        df_m_data = df_daily[(df_daily['Year'] == sel_y_m) & (df_daily['Month_Thai'] == sel_m_m)].copy()

        days_in_m = calendar.monthrange(sel_y_m, thai_months.index(sel_m_m)+1)[1]
        df_full_days = pd.DataFrame({'Day': range(1, days_in_m + 1)})

        fix_cost_month = 0
        fix_cost_daily = fix_cost_month / days_in_m if days_in_m > 0 else 0

        if df_m_data.empty:
            st.warning(f"ไม่พบข้อมูลการขายสำหรับเดือน {sel_m_m} {sel_y_m} (แต่จะแสดงกราฟเปล่าที่มี Fix Cost)")
            df_d_agg_raw = pd.DataFrame(columns=['Day', 'รายละเอียดยอดที่ชำระแล้ว', 'Ads_Amount', 'CAL_COST', 'BOX_COST', 'DELIV_COST', 'CAL_COD_COST', 'CAL_COM_ADMIN', 'CAL_COM_TELESALE'])
        else:
            df_d_agg_raw = df_m_data.groupby('Day').agg({
                'รายละเอียดยอดที่ชำระแล้ว': 'sum',
                'Ads_Amount': 'sum',
                'CAL_COST': 'sum', 'BOX_COST': 'sum',
                'DELIV_COST': 'sum', 'CAL_COD_COST': 'sum', 'CAL_COM_ADMIN': 'sum', 'CAL_COM_TELESALE': 'sum'
            }).reset_index()

        df_d_agg = pd.merge(df_full_days, df_d_agg_raw, on='Day', how='left').fillna(0)

        df_d_agg['Daily_Total_Exp'] = df_d_agg['CAL_COST'] + df_d_agg['BOX_COST'] + \
                                      df_d_agg['DELIV_COST'] + df_d_agg['CAL_COD_COST'] + \
                                      df_d_agg['CAL_COM_ADMIN'] + df_d_agg['CAL_COM_TELESALE'] + \
                                      df_d_agg['Ads_Amount'] + fix_cost_daily

        df_d_agg['Daily_Net_Profit'] = df_d_agg['รายละเอียดยอดที่ชำระแล้ว'] - df_d_agg['Daily_Total_Exp']

        m_sales = df_d_agg['รายละเอียดยอดที่ชำระแล้ว'].sum()
        m_ads = df_d_agg['Ads_Amount'].sum()
        m_cost_prod = df_d_agg['CAL_COST'].sum()
        m_ops = df_d_agg['BOX_COST'].sum() + df_d_agg['DELIV_COST'].sum() + df_d_agg['CAL_COD_COST'].sum()
        m_com = df_d_agg['CAL_COM_ADMIN'].sum() + df_d_agg['CAL_COM_TELESALE'].sum()
        m_net_profit = df_d_agg['Daily_Net_Profit'].sum()
        
        render_metric_row(m_sales, m_ops, m_com, m_cost_prod, m_ads, m_net_profit)

        pct_net = (m_net_profit / m_sales * 100) if m_sales else 0
        pct_exp_ratio = ((m_ops + m_com + m_cost_prod + m_ads) / m_sales * 100) if m_sales else 0

        def fmt(v): return f"{v:,.0f}"
        def fmt_p(v): return f"{v:,.2f}%"

        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<div class="chart-box"><div class="chart-header"><span class="pill" style="background:#3b82f6"></span> แนวโน้มรายวัน (ยอดขาย vs ค่าใช้จ่าย)</div>', unsafe_allow_html=True)
            base_d = alt.Chart(df_d_agg).encode(x=alt.X('Day:O', title='วันที่'))
            bar_d = base_d.mark_bar(color='#3b82f6', opacity=0.7).encode(y=alt.Y('รายละเอียดยอดที่ชำระแล้ว', title='บาท'), tooltip=['Day', 'รายละเอียดยอดที่ชำระแล้ว'])
            line_d = base_d.mark_line(color='#ef4444').encode(y='Daily_Total_Exp', tooltip=['Day', 'Daily_Total_Exp'])
            st.altair_chart((bar_d + line_d).interactive(), use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with c2:
            st.markdown('<div class="chart-box"><div class="chart-header"><span class="pill" style="background:#f87171"></span> สัดส่วนค่าใช้จ่าย (เดือนนี้)</div>', unsafe_allow_html=True)
            m_prod = df_d_agg['CAL_COST'].sum()
            m_box = df_d_agg['BOX_COST'].sum()
            m_ship = df_d_agg['DELIV_COST'].sum()
            m_cod = df_d_agg['CAL_COD_COST'].sum()
            m_admin = df_d_agg['CAL_COM_ADMIN'].sum()
            m_tele = df_d_agg['CAL_COM_TELESALE'].sum()
            m_ads = df_d_agg['Ads_Amount'].sum()

            pie_data = pd.DataFrame([
                {'Type': 'ต้นทุนสินค้า', 'Value': m_prod},
                {'Type': 'ค่ากล่อง', 'Value': m_box},
                {'Type': 'ค่าส่ง', 'Value': m_ship},
                {'Type': 'ค่า COD', 'Value': m_cod},
                {'Type': 'ค่าคอม Admin', 'Value': m_admin},
                {'Type': 'ค่าคอม Tele', 'Value': m_tele},
                {'Type': 'ค่า Ads', 'Value': m_ads}
            ])
            pie_data = pie_data[pie_data['Value'] > 0]

            if not pie_data.empty:
                donut_m = alt.Chart(pie_data).mark_arc(innerRadius=80).encode(
                    theta=alt.Theta("Value", stack=True),
                    color=alt.Color("Type", scale=alt.Scale(scheme='tableau10'), legend=alt.Legend(orient='right')),
                    tooltip=["Type", alt.Tooltip("Value", format=",.0f")]
                )
                st.altair_chart(donut_m, use_container_width=True)
            else:
                st.info("ไม่มีข้อมูลค่าใช้จ่าย")
            st.markdown('</div>', unsafe_allow_html=True)

        c3, c4 = st.columns(2)
        with c3:
            st.markdown('<div class="chart-box"><div class="chart-header"><span class="pill" style="background:#14b8a6"></span> กำไรสุทธิรายวัน</div>', unsafe_allow_html=True)
            chart_profit_d = alt.Chart(df_d_agg).mark_line(point=True, color='#14b8a6').encode(
                x=alt.X('Day:O', title='วันที่'),
                y=alt.Y('Daily_Net_Profit', title='บาท'),
                tooltip=['Day', alt.Tooltip('Daily_Net_Profit', format=',.0f')]
            ).properties(height=400).interactive()
            st.altair_chart(chart_profit_d, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with c4:
            st.markdown('<div class="chart-box"><div class="chart-header"><span class="pill" style="background:#6366f1"></span> สินค้าขายดีประจำเดือน (Top 12)</div>', unsafe_allow_html=True)
            if not df_m_data.empty:
                top_sku_m = df_m_data.groupby('SKU_Main')['รายละเอียดยอดที่ชำระแล้ว'].sum().nlargest(12).reset_index()
                top_sku_m['Display_Name'] = top_sku_m['SKU_Main'].apply(lambda x: f"{x} : {sku_name_lookup.get(x, 'ไม่ระบุชื่อ')}")

                chart_sku_m = alt.Chart(top_sku_m).mark_bar(cornerRadiusEnd=4).encode(
                    x=alt.X('รายละเอียดยอดที่ชำระแล้ว', title='ยอดขาย'),
                    y=alt.Y('Display_Name', sort='-x', title='สินค้า'),
                    color=alt.Color('Display_Name', legend=None, scale=alt.Scale(scheme='tableau10')),
                    tooltip=['Display_Name', alt.Tooltip('รายละเอียดยอดที่ชำระแล้ว', format=',.0f')]
                ).properties(height=400)
                st.altair_chart(chart_sku_m, use_container_width=True)
            else:
                st.info("ไม่มีข้อมูลสินค้าขายดี")
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="chart-box"><div class="chart-header">งบกำไรขาดทุน (Monthly Statement)</div>', unsafe_allow_html=True)

        m_sales = df_d_agg['รายละเอียดยอดที่ชำระแล้ว'].sum()
        m_prod_cost = df_d_agg['CAL_COST'].sum()
        m_box_cost = df_d_agg['BOX_COST'].sum()
        m_gross = m_sales - m_prod_cost - m_box_cost
        m_ship = df_d_agg['DELIV_COST'].sum()
        m_cod = df_d_agg['CAL_COD_COST'].sum()
        m_admin = df_d_agg['CAL_COM_ADMIN'].sum()
        m_tele = df_d_agg['CAL_COM_TELESALE'].sum()
        m_ads = df_d_agg['Ads_Amount'].sum()
        m_net = m_gross - m_ship - m_cod - m_admin - m_tele - m_ads - fix_cost_month

        def row_html(label, val, is_head=False, is_neg=False, is_sub=False):
            cls = "pnl-row-head" if is_head else ("sub-item" if is_sub else "")
            val_cls = "neg" if val < 0 else ""
            return f'<tr class="{cls}"><td>{label}</td><td class="num-cell {val_cls}">{fmt(val)}</td></tr>'

        table_html_m = f"""
        <table class="pnl-table">
            <thead><tr><th>รายการ (Accounts)</th><th style="text-align:right">จำนวนเงิน (THB)</th></tr></thead>
            <tbody>
                {row_html("รายได้จากการขาย (Sales)", m_sales, True)}
                {row_html("หัก ต้นทุนสินค้า (Product Cost)", -m_prod_cost)}
                {row_html("หัก ค่ากล่อง (Box Cost)", -m_box_cost)}
                {row_html("กำไรขั้นต้น (Gross Profit)", m_gross, True, m_gross<0)}
                {row_html("หัก ค่าส่ง (Shipping)", -m_ship, is_sub=True)}
                {row_html("หัก ค่า COD", -m_cod, is_sub=True)}
                {row_html("หัก ค่าคอม Admin", -m_admin, is_sub=True)}
                {row_html("หัก ค่าคอม Telesale", -m_tele, is_sub=True)}
                {row_html("หัก ค่า ADS", -m_ads, is_sub=True)}
                {row_html("กำไร(ขาดทุน) สุทธิ (Net Profit)", m_net, True, m_net<0)}
            </tbody>
        </table>
        """
        st.markdown(table_html_m, unsafe_allow_html=True)
        st.markdown('</div></div>', unsafe_allow_html=True)

    # --- PAGE 6: COMMISSION ---
    elif selected_page == "💰 COMMISSION":
        st.markdown('<div class="header-bar"><div class="header-title"><i class="fas fa-coins"></i> สรุปค่าคอมมิชชั่น (Admin & Telesale)</div></div>', unsafe_allow_html=True)

        with st.container():
            c_c1, c_c2, c_c3 = st.columns([1, 1, 3])
            with c_c1: sel_year_c = st.selectbox("เลือกปี", sorted(df_daily['Year'].unique(), reverse=True), key="c_y")
            with c_c2: sel_month_c = st.selectbox("เลือกเดือน", thai_months, index=datetime.now().month-1, key="c_m")

        st.markdown(f"### 📅 ประจำเดือน: {sel_month_c} {sel_year_c}")

        df_comm = df_daily[(df_daily['Year'] == sel_year_c) & (df_daily['Month_Thai'] == sel_month_c)].copy()

        month_idx = thai_months.index(sel_month_c) + 1
        days_in_m = calendar.monthrange(sel_year_c, month_idx)[1]
        df_full_days = pd.DataFrame({'Day': range(1, days_in_m + 1)})

        if df_comm.empty:
            st.warning(f"⚠️ ไม่พบข้อมูลสำหรับเดือน {sel_month_c} {sel_year_c}")
            df_merged_c = df_full_days.copy()
            df_merged_c['CAL_COM_ADMIN'] = 0
            df_merged_c['CAL_COM_TELESALE'] = 0
            total_admin = 0
            total_tele = 0
            total_all = 0
        else:
            total_admin = df_comm['CAL_COM_ADMIN'].sum()
            total_tele = df_comm['CAL_COM_TELESALE'].sum()
            total_all = total_admin + total_tele

            total_sales = df_comm['รายละเอียดยอดที่ชำระแล้ว'].sum()
            total_ads = df_comm['Ads_Amount'].sum()
            total_cost_prod = df_comm['CAL_COST'].sum()
            total_ops = df_comm['BOX_COST'].sum() + df_comm['DELIV_COST'].sum() + df_comm['CAL_COD_COST'].sum()
            total_com = total_admin + total_tele
            total_cost_all = total_cost_prod + total_ops + total_com + total_ads
            net_profit = total_sales - total_cost_all
            
            render_metric_row(total_sales, total_ops, total_com, total_cost_prod, total_ads, net_profit)

            c_chart, c_table = st.columns([2, 1])

            with c_chart:
                st.markdown("##### 📈 แนวโน้มค่าคอมรายวัน (Daily Trend)")

                df_chart_c = df_comm.groupby('Day').agg({
                    'CAL_COM_ADMIN': 'sum',
                    'CAL_COM_TELESALE': 'sum'
                }).reset_index()

                df_merged_c = pd.merge(df_full_days, df_chart_c, on='Day', how='left').fillna(0)

                df_melt = df_merged_c.melt(id_vars=['Day'], value_vars=['CAL_COM_ADMIN', 'CAL_COM_TELESALE'], var_name='Role', value_name='Commission')
                df_melt['Role'] = df_melt['Role'].map({'CAL_COM_ADMIN': 'Admin', 'CAL_COM_TELESALE': 'Telesale'})

                chart_comm = alt.Chart(df_melt).mark_line(point=True).encode(
                    x=alt.X('Day:O', title='วันที่'),
                    y=alt.Y('Commission', title='ค่าคอม (บาท)'),
                    color=alt.Color('Role', scale=alt.Scale(domain=['Admin', 'Telesale'], range=['#9b59b6', '#e67e22'])),
                    tooltip=['Day', 'Role', alt.Tooltip('Commission', format=',.0f')]
                ).interactive()
                st.altair_chart(chart_comm, use_container_width=True)

            with c_table:
                st.markdown("##### 📋 สรุปตามทีม (Team Summary)")
                comm_data = [
                    {'กลุ่มพนักงาน (Team)': 'Admin', 'ค่าคอมรวม (บาท)': total_admin},
                    {'กลุ่มพนักงาน (Team)': 'Telesale', 'ค่าคอมรวม (บาท)': total_tele},
                    {'กลุ่มพนักงาน (Team)': 'รวมทั้งหมด', 'ค่าคอมรวม (บาท)': total_all}
                ]
                df_table_c = pd.DataFrame(comm_data)

                st.dataframe(
                    df_table_c.style.format({'ค่าคอมรวม (บาท)': '{:,.2f}'}),
                    use_container_width=True,
                    hide_index=True
                )

        st.markdown("---")
        st.markdown(f"### 📅 ภาพรวมทั้งปี: {sel_year_c}")

        df_template_months = pd.DataFrame({
            'Month_Num': range(1, 13),
            'Month_Thai': thai_months
        })

        df_year_comm = df_daily[df_daily['Year'] == sel_year_c].copy()

        if not df_year_comm.empty:
            df_year_agg = df_year_comm.groupby(['Month_Num']).agg({
                'CAL_COM_ADMIN': 'sum',
                'CAL_COM_TELESALE': 'sum'
            }).reset_index()
        else:
            df_year_agg = pd.DataFrame(columns=['Month_Num', 'CAL_COM_ADMIN', 'CAL_COM_TELESALE'])

        df_final_chart = pd.merge(df_template_months, df_year_agg, on='Month_Num', how='left').fillna(0)

        df_year_melt = df_final_chart.melt(id_vars=['Month_Num', 'Month_Thai'],
                                        value_vars=['CAL_COM_ADMIN', 'CAL_COM_TELESALE'],
                                        var_name='Role', value_name='Commission')
        df_year_melt['Role'] = df_year_melt['Role'].map({'CAL_COM_ADMIN': 'Admin', 'CAL_COM_TELESALE': 'Telesale'})

        chart_year = alt.Chart(df_year_melt).mark_bar().encode(
            x=alt.X('Month_Thai', sort=thai_months, title='เดือน'),
            y=alt.Y('Commission', title='ค่าคอม (บาท)'),
            color=alt.Color('Role', scale=alt.Scale(domain=['Admin', 'Telesale'], range=['#9b59b6', '#e67e22'])),
            tooltip=['Month_Thai', 'Role', alt.Tooltip('Commission', format=',.0f')]
        ).properties(height=350).interactive()

        st.altair_chart(chart_year, use_container_width=True)

    # --- PAGE 7: MASTER_ITEM (UI ปรับความสูงตารางได้) ---
    elif selected_page == "🔧 MASTER_ITEM":
        st.markdown('<div class="header-bar"><div class="header-title"><i class="fas fa-tools"></i> จัดการ Master Item (แก้ไขต้นทุน/เรทค่าใช้จ่าย)</div></div>', unsafe_allow_html=True)
        
        def get_master_worksheet():
            try:
                creds = get_drive_service()
                gc = gspread.authorize(creds)
                sh = gc.open_by_url(SHEET_MASTER_URL) 
                return sh.worksheet("MASTER_ITEM")
            except Exception as e:
                st.error(f"⚠️ ไม่สามารถเชื่อมต่อ MASTER_ITEM: {e}")
                return None

        ws = get_master_worksheet()
        
        if ws:
            try:
                data = ws.get_all_records()
                df_master_edit = pd.DataFrame(data)

                cost_col_name = 'ทุน' if 'ทุน' in df_master_edit.columns else 'ต้นทุน'

                # 1. แบ่งกลุ่มคอลัมน์
                cols_money = [cost_col_name, 'ราคากล่อง', 'ค่าส่งเฉลี่ย']
                cols_percent = [
                    'ค่าคอมมิชชั่น Admin', 'ค่าคอมมิชชั่น Telesale',
                    'J&T Express', 'Flash Express', 'ThailandPost', 
                    'LEX TH', 'SPX Express', 'Express Delivery - ส่งด่วน', 
                    'DHL_1', 'Standard Delivery - ส่งธรรมดาในประเทศ'
                ]

                target_columns_order = ['SKU', 'ชื่อสินค้า'] + cols_money + ['Type'] + cols_percent
                available_cols = [c for c in target_columns_order if c in df_master_edit.columns]
                other_cols = [c for c in df_master_edit.columns if c not in available_cols]
                
                df_editor_view = df_master_edit[available_cols + other_cols].copy()

                # --- 2. เตรียมข้อมูล ---
                for col in cols_money:
                    if col in df_editor_view.columns:
                        df_editor_view[col] = pd.to_numeric(df_editor_view[col], errors='coerce').fillna(0.0)

                for col in cols_percent:
                    if col in df_editor_view.columns:
                        df_editor_view[col] = df_editor_view[col].astype(str)

                # --- UI CONTROLS ---
                c_info, c_slider, c_btn = st.columns([2.5, 1.5, 1]) 
                
                with c_info: 
                    st.info("💡 พิมพ์ **%** ต่อท้ายได้เลย (เช่น `0.5%`)")
                
                with c_slider:
                    # [NEW] สไลด์เดอร์ปรับความสูงตาราง (Default 1200px สำหรับจอแนวตั้ง)
                    table_height = st.slider("↕️ ปรับความสูงตาราง", min_value=600, max_value=2500, value=1200, step=100)
                
                with c_btn:
                    st.markdown('<div style="margin-top: 0px;"></div>', unsafe_allow_html=True)
                    click_save = st.button("💾 บันทึกการแก้ไข", type="primary", use_container_width=True)

                # --- 3. ตั้งค่าการแสดงผล ---
                my_column_config = {
                    "SKU": st.column_config.TextColumn(disabled=False),
                    cost_col_name: st.column_config.NumberColumn(label=f"💰 {cost_col_name}", format="%.2f"),
                    "ราคากล่อง": st.column_config.NumberColumn(label="📦 ราคากล่อง", format="%.2f"),
                    "ค่าส่งเฉลี่ย": st.column_config.NumberColumn(label="🚚 ค่าส่งเฉลี่ย", format="%.2f"),
                }

                for p_col in cols_percent:
                    if p_col in df_editor_view.columns:
                        my_column_config[p_col] = st.column_config.TextColumn(
                            label=f"{p_col}",
                            width="medium" # ปรับความกว้างคอลัมน์ให้อ่านง่าย
                        )

                # แสดงตาราง
                edited_df = st.data_editor(
                    df_editor_view,
                    num_rows="dynamic", 
                    use_container_width=True,
                    height=table_height, # <--- ใช้ค่าจาก Slider ตรงนี้
                    key="master_editor_vertical_v1",
                    column_config=my_column_config
                )

                # ส่วนบันทึกข้อมูล
                if click_save:
                    try:
                        with st.spinner("⏳ กำลังบันทึกข้อมูล..."):
                            save_df = edited_df.fillna("") 
                            vals = [save_df.columns.values.tolist()] + save_df.astype(str).values.tolist()
                            ws.clear()
                            ws.update(range_name='A1', values=vals)
                            st.success("✅ บันทึกข้อมูลเรียบร้อยแล้ว!")
                            st.cache_data.clear() 
                    except Exception as e:
                        st.error(f"❌ เกิดข้อผิดพลาดขณะบันทึก: {e}")

            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาดในการโหลดข้อมูล: {e}")

except Exception as e:
    st.error(f"Application Error: {e}")