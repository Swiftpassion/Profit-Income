import streamlit as st
import pandas as pd
import io
import json
import time
import calendar
import smtplib
import random
import string
import hashlib
import urllib.parse 
import re
from email.mime.text import MIMEText
from datetime import date, datetime, timedelta

from database import get_db, init_db
import services
from pages.data_manager import show_data_manager_page
from views.purchase_orders import (
    show_purchase_orders, po_batch_dialog, po_internal_batch_dialog, 
    po_multi_item_dialog, po_edit_dialog_v2, delete_confirm_dialog
)
from views.stock_report import show_stock_report

# Google Service Account Imports (Preserved for existing Logic)
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import gspread

# Initialize Database
try:
    init_db()
except:
    pass

st.set_page_config(
    page_title="JST Stock Manager",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS สำหรับปรับแต่ง Radio Button ให้หน้าตาเหมือน Tabs และตาราง
# CSS สำหรับปรับแต่ง Radio Button ให้หน้าตาเหมือน Tabs และตาราง (Improved Fix)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;500;600&display=swap');

    /* 1. FORCE GLOBAL FONT */
    * {
        font-family: 'Sarabun', sans-serif !important;
    }

    /* 2. SIDEBAR STYLING */
    [data-testid="stSidebar"] {
        background-color: #1e3c72;
    }
    
    /* Fix Sidebar Radio Buttons Layout - Make them look like cards */
    [data-testid="stSidebar"] [data-testid="stRadio"] > div {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }

    [data-testid="stSidebar"] [data-testid="stRadio"] label {
        background-color: #262730 !important;
        border: 1px solid #4a4a4a !important;
        padding: 12px 15px !important;
        border-radius: 10px !important;
        width: 100% !important; /* Force full width */
        display: flex !important;
        align-items: center !important;
        transition: all 0.3s ease !important;
        margin: 0 !important;
        color: white !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2) !important;
    }

    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
        border-color: #ff4b4b !important;
        color: #ff4b4b !important;
        transform: translateX(5px); /* Add hover effect */
    }

    /* Active State (Checking data-checked attribute) */
    [data-testid="stSidebar"] [data-testid="stRadio"] label[data-checked="true"] {
        background-color: #ff4b4b !important;
        border-color: #ff4b4b !important;
        color: white !important;
        font-weight: 600 !important;
    }
    
    /* Hide default radio circle */
    [data-testid="stSidebar"] [data-testid="stRadio"] label div[role="radio"] {
        display: none !important;
    }

    /* 3. TABLE STYLING */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
    }
    
    [data-testid="stDataFrame"] th {
        text-align: center !important;
        background-color: #1e3c72 !important;
        color: white !important;
        vertical-align: middle !important;
        min-height: 60px;
        font-size: 14px;
        border-bottom: 2px solid #ffffff !important;
    }
    
    [data-testid="stDataFrame"] th:first-child { border-top-left-radius: 8px; }
    [data-testid="stDataFrame"] th:last-child { border-top-right-radius: 8px; }
    [data-testid="stDataFrame"] td { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 150px; }

    /* 4. GENERAL UI */
    .stButton button { 
        width: 100%; 
        border-radius: 8px;
        font-family: 'Sarabun', sans-serif !important;
    }
    
    /* Hide number input arrows */
    button[data-testid="stNumberInputStepDown"], button[data-testid="stNumberInputStepUp"] { display: none !important; }
    
    /* Toast Font */
    .st-toast, [data-testid="stToast"] {
        font-family: 'Sarabun', sans-serif !important;
    }
    
    /* Headings */
    h1, h2, h3, h4, h5, h6 {
        color: #f0f2f6 !important;
        font-family: 'Sarabun', sans-serif !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. Config & Google Cloud Connection
# ==========================================
MASTER_SHEET_ID = "1SC_Dpq2aiMWsS3BGqL_Rdf7X4qpTFkPA0wPV6mqqosI"
TAB_NAME_STOCK = "MASTER"
TAB_NAME_PO = "PO_DATA"
FOLDER_ID_STOCK_ACTUAL = "1-hXu2RG2gNKMkW3ZFBFfhjQEhTacVYzk"
FOLDER_ID_DATA_SALE = "12jyMKgFHoc9-_eRZ-VN9QLsBZ31ZJP4T"

@st.cache_resource
def get_credentials():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    if "gcp_service_account" in st.secrets:
        creds_dict = json.loads(st.secrets["gcp_service_account"]) if isinstance(st.secrets["gcp_service_account"], str) else dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        return service_account.Credentials.from_service_account_info(creds_dict, scopes=scope)
    return service_account.Credentials.from_service_account_file("credentials.json", scopes=scope)

# ==========================================
# 3. ระบบ AUTHENTICATION
# ==========================================

def create_token(email):
    salt = "jst_secret_salt" 
    raw = f"{email}{salt}{date.today()}"
    return hashlib.md5(raw.encode()).hexdigest()

def send_otp_email(receiver_email, otp_code):
    try:
        sender_email = st.secrets["email"]["sender"]
        sender_password = st.secrets["email"]["password"]
    except KeyError:
        st.error("❌ ไม่พบการตั้งค่า Email ใน st.secrets")
        return False
    
    subject = "รหัสยืนยันตัวตน (OTP) - JST Hybrid System"
    body = f"รหัสเข้าใช้งานของคุณคือ: {otp_code}\n\n(รหัสนี้ใช้สำหรับการเข้าสู่ระบบครั้งนี้เท่านั้น)"

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = receiver_email

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, receiver_email, msg.as_string())
        return True
    except Exception as e:
        st.error(f"❌ ส่งอีเมลไม่สำเร็จ: {e}")
        return False

def log_login_activity(email):
    try:
        creds = get_credentials()
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(MASTER_SHEET_ID)
        try: ws = sh.worksheet("LOGIN_LOG")
        except:
            ws = sh.add_worksheet(title="LOGIN_LOG", rows="1000", cols="2")
            ws.append_row(["Timestamp", "Email"])
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ws.append_row([timestamp, email])
    except Exception as e:
        print(f"Login Log Error: {e}")

# --- Initialize Session State ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'otp_sent' not in st.session_state: st.session_state.otp_sent = False
if 'generated_otp' not in st.session_state: st.session_state.generated_otp = None
if 'user_email' not in st.session_state: st.session_state.user_email = ""
if 'current_page' not in st.session_state: st.session_state.current_page = "📅 สรุปยอดขายรายวัน"
if "target_edit_data" not in st.session_state: st.session_state.target_edit_data = {}

# --- AUTO LOGIN LOGIC ---
url_token = st.query_params.get("token", None)

if not st.session_state.logged_in and url_token:
    try:
        allowed_users = st.secrets["access"]["allowed_users"]
        for user in allowed_users:
            if create_token(user) == url_token:
                st.session_state.logged_in = True
                st.session_state.user_email = user
                st.toast(f"🔙 กลับเข้าสู่ระบบอัตโนมัติ: {user}", icon="👋")
                break
    except: pass

if st.session_state.logged_in:
    current_token = create_token(st.session_state.user_email)
    if url_token != current_token:
        st.query_params["token"] = current_token

# --- LOGIN FORM ---
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("## 🔐 JST Hybrid System Login")
        with st.container(border=True):
            if not st.session_state.otp_sent:
                st.info("กรุณากรอกอีเมลเพื่อรับรหัส OTP")
                email_input = st.text_input("📧 อีเมล (Gmail)", placeholder="example@gmail.com")
                
                if st.button("ส่งรหัสยืนยัน (Send OTP)", type="primary"):
                    try: allowed_users = st.secrets["access"]["allowed_users"]
                    except KeyError:
                        st.error("❌ ไม่พบการตั้งค่า allowed_users")
                        st.stop()

                    if email_input.strip() in allowed_users:
                        otp = ''.join(random.choices(string.digits, k=6))
                        st.session_state.generated_otp = otp
                        st.session_state.user_email = email_input.strip()
                        
                        with st.spinner("⏳ กำลังส่งรหัสไปยังอีเมลของคุณ..."):
                            if send_otp_email(email_input.strip(), otp):
                                st.session_state.otp_sent = True
                                st.toast("✅ ส่งรหัสเรียบร้อยแล้ว! โปรดเช็คอีเมล", icon="📧")
                                st.rerun()
                    else:
                        st.error("⛔️ อีเมลนี้ไม่ได้รับอนุญาตให้เข้าใช้งาน")
            else:
                st.success(f"รหัสถูกส่งไปที่: **{st.session_state.user_email}**")
                otp_input = st.text_input("🔑 กรอกรหัส 6 หลัก", max_chars=6, type="password")
                
                c_btn1, c_btn2 = st.columns(2)
                if c_btn1.button("ยืนยันรหัส (Verify)", type="primary"):
                    if otp_input == st.session_state.generated_otp:
                        st.session_state.logged_in = True
                        log_login_activity(st.session_state.user_email)
                        token = create_token(st.session_state.user_email)
                        st.query_params["token"] = token
                        st.toast("ยินดีต้อนรับ!", icon="🎉")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ รหัสไม่ถูกต้อง กรุณาลองใหม่")
                
                if c_btn2.button("ยกเลิก / ส่งใหม่"):
                    st.session_state.otp_sent = False
                    st.session_state.generated_otp = None
                    st.rerun()
    st.stop()

# ==========================================
# 4. ฟังก์ชันจัดการข้อมูล (Data Functions)
# ==========================================

def highlight_negative(val):
    if isinstance(val, (int, float)) and val < 0:
        return 'color: #ff4b4b; font-weight: bold;'
    return ''

def clean_text_for_html(text):
    if not isinstance(text, str):
        text = str(text)
    
    # 1. ลบอักขระควบคุม (เช่น \n, \r, \t) เปลี่ยนเป็นเว้นวรรค
    text = re.sub(r'[\r\n\t]+', ' ', text)
    
    # 2. เก็บเฉพาะ: ภาษาไทย, อังกฤษ, ตัวเลข, ช่องว่าง, และเครื่องหมาย ( ) . - _ /
    # อักขระอื่นๆ ที่อาจก่อปัญหา (เช่น " ' < > & % $ #) จะถูกลบทิ้ง
    text = re.sub(r'[^\u0e00-\u0e7f a-zA-Z0-9\.\-\_\(\)\/]+', '', text)
    
    return text.strip()

@st.cache_data(ttl=300)
def get_stock_from_sheet():
    try:
        db = next(get_db())
        df = services.get_products_df(db)
        return df
    except Exception as e:
        st.error(f"❌ อ่านข้อมูล Master Stock ไม่ได้: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_po_data():
    try:
        creds = get_credentials()
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(MASTER_SHEET_ID)
        ws = sh.worksheet(TAB_NAME_PO)
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        col_map = {
            'รหัสสินค้า': 'Product_ID', 'เลข PO': 'PO_Number', 'ขนส่ง': 'Transport_Type',
            'วันที่สั่งซื้อ': 'Order_Date', 
            'Expected_Date': 'Expected_Date', 'วันที่คาดว่าจะได้รับ': 'Expected_Date', 'วันที่คาดการณ์': 'Expected_Date',
            'วันที่ได้รับ': 'Received_Date', 
            'จำนวน': 'Qty_Ordered',          
            'จำนวนที่ได้รับ': 'Qty_Received', 
            'ราคา/ชิ้น': 'Price_Unit_NoVAT', 'ราคา (หยวน)': 'Total_Yuan', 'เรทเงิน': 'Yuan_Rate',
            'เรทค่าขนส่ง': 'Ship_Rate', 'ขนาด (คิว)': 'CBM', 'ค่าส่ง': 'Ship_Cost', 'น้ำหนัก / KG': 'Transport_Weight',
            'SHOPEE': 'Shopee_Price', 'LAZADA': 'Lazada_Price', 'TIKTOK': 'TikTok_Price', 'หมายเหตุ': 'Note',
            'ราคา (บาท)': 'Total_THB', 'Link_Shop': 'Link', 'WeChat': 'WeChat'
        }
        df = df.rename(columns={k:v for k,v in col_map.items() if k in df.columns})

        if not df.empty:
            df['Sheet_Row_Index'] = range(2, len(df) + 2)
            for col in ['Qty_Ordered', 'Qty_Received', 'Total_Yuan', 'Yuan_Rate']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            if 'Qty_Received' not in df.columns: df['Qty_Received'] = 0
            if 'Expected_Date' not in df.columns: df['Expected_Date'] = None
                 
        return df
    except Exception as e:
        st.error(f"❌ อ่านข้อมูล PO ไม่ได้: {e}")
        return pd.DataFrame()
def get_next_auto_po():
    """ฟังก์ชันคำนวณหาเลข รอเลขสินค้าเข้าXXX ตัวถัดไป"""
    prefix = "รอเลขสินค้าเข้า"
    
    # ดึงข้อมูล PO ปัจจุบันมาเช็ค
    df = get_po_data()
    
    if df.empty:
        return f"{prefix}001"

    # กรองเฉพาะ PO ที่ขึ้นต้นด้วย prefix นี้
    # แปลงเป็น string ก่อนเผื่อมีข้อมูลขยะ
    mask = df['PO_Number'].astype(str).str.startswith(prefix)
    existing_pos = df.loc[mask, 'PO_Number'].unique()

    if len(existing_pos) == 0:
        return f"{prefix}001"

    max_num = 0
    for po in existing_pos:
        try:
            # ตัด prefix ออกแล้วแปลงเป็นตัวเลข
            num_part = str(po).replace(prefix, "")
            num_val = int(num_part)
            if num_val > max_num:
                max_num = num_val
        except:
            continue

    new_num = max_num + 1
    return f"{prefix}{new_num:03d}"


@st.cache_data(ttl=300)
def get_sale_from_folder():
    try:
        db = next(get_db())
        df = services.get_sales_df(db)
        return df
    except Exception as e:
        st.warning(f"⚠️ อ่านข้อมูล Sale ไม่ได้: {e}")
        return pd.DataFrame()
@st.cache_data(ttl=60)
def get_actual_stock_from_folder():
    # Since we are using a database now, the 'Actual Stock' is integrated into the Product.current_stock.
    # The 'get_stock_from_sheet' returns this as 'Initial_Stock'.
    # We return empty here to allow the App to calculate (Initial_Stock - Sales), 
    # where Initial_Stock is the latest DB update (from Master or Stock import).
    return pd.DataFrame()

# --- Functions: Save Data ---
def save_po_edit_split(row_index, current_row_data, new_row_data):
    try:
        creds = get_credentials()
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(MASTER_SHEET_ID)
        ws = sh.worksheet(TAB_NAME_PO)
        
        formatted_curr = []
        for item in current_row_data:
            if isinstance(item, (date, datetime)): formatted_curr.append(item.strftime("%Y-%m-%d"))
            elif item is None: formatted_curr.append("")
            else: formatted_curr.append(item)
        
        range_name = f"A{row_index}:X{row_index}" 
        ws.update(range_name, [formatted_curr])
        
        formatted_new = []
        for item in new_row_data:
            if isinstance(item, (date, datetime)): formatted_new.append(item.strftime("%Y-%m-%d"))
            elif item is None: formatted_new.append("")
            else: formatted_new.append(item)
            
        ws.append_row(formatted_new)
        
        st.cache_data.clear() 
        return True
    except Exception as e:
        st.error(f"❌ บันทึก Split ไม่สำเร็จ: {e}")
        return False

def save_po_edit_update(row_index, current_row_data):
    try:
        creds = get_credentials()
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(MASTER_SHEET_ID)
        ws = sh.worksheet(TAB_NAME_PO)
        
        formatted_curr = []
        for item in current_row_data:
            if isinstance(item, (date, datetime)): formatted_curr.append(item.strftime("%Y-%m-%d"))
            elif item is None: formatted_curr.append("")
            else: formatted_curr.append(item)
        
        range_name = f"A{row_index}:X{row_index}" 
        ws.update(range_name, [formatted_curr])
        
        st.cache_data.clear() 
        return True
    except Exception as e:
        st.error(f"❌ บันทึก Update ไม่สำเร็จ: {e}")
        return False

def save_po_batch_to_sheet(rows_data):
    try:
        creds = get_credentials()
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(MASTER_SHEET_ID)
        ws = sh.worksheet(TAB_NAME_PO)
        ws.append_rows(rows_data)
        st.cache_data.clear() 
        return True
    except Exception as e:
        st.error(f"❌ บันทึก Batch ไม่สำเร็จ: {e}")
        return False
def delete_po_row_from_sheet(row_index):
    try:
        creds = get_credentials()
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(MASTER_SHEET_ID)
        ws = sh.worksheet(TAB_NAME_PO)
        
        # ลบแถวตาม Index (Google Sheet เริ่มนับแถว 1, ข้อมูลเริ่มแถว 2)
        ws.delete_rows(int(row_index))
        
        st.cache_data.clear() # ล้าง Cache เพื่อให้ข้อมูลอัปเดตทันที
        return True
    except Exception as e:
        st.error(f"❌ ลบข้อมูลไม่สำเร็จ: {e}")
        return False


def update_master_limits(df_edited):
    try:
        creds = get_credentials()
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(MASTER_SHEET_ID)
        ws = sh.worksheet(TAB_NAME_STOCK)
        
        headers = ws.row_values(1)
        all_rows = ws.get_all_values()

        # หา Index รหัสสินค้า (Product_ID)
        pid_idx = -1
        for i, h in enumerate(headers):
            if h in ['รหัสสินค้า', 'รหัส', 'ID', 'Product_ID']:
                pid_idx = i
                break
        
        if pid_idx == -1: 
            st.error("❌ ไม่พบคอลัมน์ Product_ID ใน Google Sheet")
            return

        # กำหนดคอลัมน์ที่จะอัปเดต: (ชื่อใน DF, ชื่อใน Sheet, ประเภทข้อมูล)
        targets = [
            ("Min_Limit", "Min_Limit", int),
            ("Note", "Note", str)
        ]

        for df_col, sheet_header, dtype in targets:
            # 1. ตรวจสอบ/สร้าง Header ใน Sheet ถ้ายังไม่มี
            if sheet_header not in headers:
                ws.update_cell(1, len(headers) + 1, sheet_header)
                headers = ws.row_values(1) # โหลด Header ใหม่
                col_index = len(headers)
            else:
                col_index = headers.index(sheet_header) + 1

            # 2. เตรียมข้อมูลจากหน้าเว็บ (df_edited) ใส่ Dictionary
            data_map = {}
            for index, row in df_edited.iterrows():
                pid = str(row['Product_ID']).strip()
                raw_val = row.get(df_col, "")
                
                if dtype == int:
                    try: clean_val = int(float(str(raw_val).replace(',', '').strip()))
                    except: clean_val = 0
                else:
                    clean_val = str(raw_val) if pd.notna(raw_val) else ""
                
                data_map[pid] = clean_val

            # 3. เตรียมข้อมูลสำหรับ Update (เทียบกับแถวเดิมใน Sheet)
            values_to_update = []
            for row in all_rows[1:]: # ข้าม Header
                row_pid = str(row[pid_idx]).strip() if len(row) > pid_idx else ""
                final_val = "" if dtype == str else 0
                
                # ถ้าเป็นสินค้าที่ถูกแก้ในหน้าเว็บ -> ใช้ค่าใหม่
                if row_pid in data_map:
                    final_val = data_map[row_pid]
                else:
                    # ถ้าไม่ได้แก้ (เช่น ติด Filter อยู่) -> ให้คงค่าเดิมใน Sheet ไว้
                    if len(row) >= col_index:
                        curr_val = row[col_index-1]
                        if dtype == int:
                            try: final_val = int(float(str(curr_val).replace(",", "")))
                            except: final_val = 0
                        else:
                            final_val = str(curr_val)
                
                values_to_update.append([final_val])

            # 4. บันทึกลง Sheet (Batch Update)
            if values_to_update:
                range_name = f"{gspread.utils.rowcol_to_a1(2, col_index)}:{gspread.utils.rowcol_to_a1(len(values_to_update)+1, col_index)}"
                ws.update(range_name, values_to_update)

        st.toast("✅ บันทึกข้อมูล (จุดเตือน & หมายเหตุ) สำเร็จ!", icon="💾")
        st.cache_data.clear()
        time.sleep(1)
            
    except Exception as e:
        st.error(f"❌ เกิดข้อผิดพลาด: {str(e)}")

# ==========================================
# 5. Main App & Data Loading
# ==========================================



st.title("📊 JST Hybrid Management System")

# --- 2. Sidebar ---
with st.sidebar:
    # Navigation Menu
    menu = ["📅 สรุปยอดขายรายวัน", "📈 รายงาน Stock", "📦 รายการสั่งซื้อ (PO)", "📂 จัดการข้อมูล (Upload)"]
    
    # Ensure current_page is valid
    if "current_page" not in st.session_state or st.session_state.current_page not in menu:
        st.session_state.current_page = menu[0]
        
    st.markdown("### เมนูหลัก")
    for page_name in menu:
        # Show active button as 'primary', others as 'secondary'
        btn_type = "primary" if st.session_state.current_page == page_name else "secondary"
        if st.button(page_name, key=f"nav_{page_name}", type=btn_type, use_container_width=True):
            st.session_state.current_page = page_name
            st.rerun()
    
    # st.divider()
    # st.subheader("📂 ไฟล์ในเครื่อง (Local Files)")
    # # Show files in local_data folder
    # import os
    # local_dir = "local_data"
    # if not os.path.exists(local_dir):
    #     os.makedirs(local_dir)
        
    # files = os.listdir(local_dir)
    # if files:
    #     for f in files:
    #         st.text(f"📄 {f}")
    # else:
    #     st.caption("ว่างเปล่า (Empty)")
        
    st.divider()
    st.subheader("⚙️ ตั้งค่าระบบ")
    st.link_button("🔗 เพิ่ม SKU / Master", "https://docs.google.com/spreadsheets/d/1SC_Dpq2aiMWsS3BGqL_Rdf7X4qpTFkPA0wPV6mqqosI/edit?gid=0#gid=0", type="secondary", use_container_width=True)

    if st.button("🔄 รีเฟรชข้อมูลล่าสุด", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.sidebar.markdown(f"👤 **ผู้ใช้งาน:** {st.session_state.user_email}")

# Update Session State based on Radio Choice (Redundant if using variable above, but keeping for safety)
# st.session_state.current_page = choice  <-- Removed as we are now using key='current_page'

# --- 3. Session State (Dialogs) ---
if "active_dialog" not in st.session_state: st.session_state.active_dialog = None 
if "selected_product_history" not in st.session_state: st.session_state.selected_product_history = None
if 'po_temp_cart' not in st.session_state: st.session_state.po_temp_cart = []

# Initialize DataFrames
df_master = pd.DataFrame()
df_po = pd.DataFrame()
df_sale = pd.DataFrame()
df_real_stock = pd.DataFrame()

# Global variables (initialized empty, populated in pages if needed)
recent_sales_map = {}
latest_date_str = "ไม่พบข้อมูล"

# ==========================================
# DIALOGS
# ==========================================

@st.dialog("📋 รายละเอียดข้อมูล", width="small")
def show_info_dialog(text_val):
    st.info("💡 สามารถกดปุ่ม Copy มุมขวาบนของกล่องข้อความได้เลย")
    st.code(text_val, language="text") 
    
    if st.button("❌ ปิดหน้าต่าง", type="primary", use_container_width=True):
        if "view_info" in st.query_params: del st.query_params["view_info"]
        if "t" in st.query_params: del st.query_params["t"]
        if "token" not in st.query_params and st.session_state.logged_in:
             st.query_params["token"] = create_token(st.session_state.user_email)
        st.rerun()

@st.dialog("📜 ประวัติการสั่งซื้อสินค้า", width="large")
def show_history_dialog(fixed_product_id=None):
    # CSS สำหรับตารางประวัติ
    st.markdown("""
    <style>
        div[data-testid="stDialog"] { width: 98vw !important; min-width: 98vw !important; max-width: 98vw !important; left: 1vw !important; margin: 0 !important; }
        div[data-testid="stDialog"] > div { width: 100% !important; max-width: 100% !important; }
        .po-table-container { overflow: auto; max-height: 75vh; margin-top: 10px; }
        .custom-po-table { width: 100%; border-collapse: separate; font-size: 12px; color: #e0e0e0; min-width: 2000px; }
        .custom-po-table th { background-color: #1e3c72; color: white; padding: 10px; text-align: center; border-bottom: 2px solid #fff; border-right: 1px solid #4a4a4a; position: sticky; top: 0; z-index: 10; white-space: nowrap; vertical-align: middle; }
        .custom-po-table td { padding: 8px 5px; border-bottom: 1px solid #111; border-right: 1px solid #444; vertical-align: middle; text-align: center; }
        .td-merged { border-right: 2px solid #666 !important; background-color: inherit; }
        .status-badge { padding: 4px 8px; border-radius: 12px; font-weight: bold; font-size: 12px; display: inline-block; width: 100px;}
    </style>
    """, unsafe_allow_html=True)
    
    selected_pid = fixed_product_id
    if not selected_pid:
        st.caption("ค้นหาและเลือกสินค้าเพื่อดูประวัติการสั่งซื้อทั้งหมด")
        if df_master.empty: return
        product_options = df_master.apply(lambda x: f"{x['Product_ID']} : {x['Product_Name']}", axis=1).tolist()
        selected_product = st.selectbox("🔍 ค้นหาสินค้า", options=product_options, index=None)
        if selected_product: selected_pid = selected_product.split(" : ")[0]
    
    if selected_pid:
        if not df_po.empty:
            df_history = df_po[df_po['Product_ID'] == selected_pid].copy()
            
            if not df_history.empty:
                df_history['Product_ID'] = df_history['Product_ID'].astype(str)
                df_master_t = df_master.copy()
                df_master_t['Product_ID'] = df_master_t['Product_ID'].astype(str)
                cols_to_use = ['Product_ID', 'Product_Name', 'Image', 'Product_Type']
                valid_cols = [c for c in cols_to_use if c in df_master_t.columns]
                df_final = pd.merge(df_history, df_master_t[valid_cols], on='Product_ID', how='left')
                
                for col in ['Order_Date', 'Received_Date', 'Expected_Date']:
                    if col in df_final.columns:
                        df_final[col] = pd.to_datetime(df_final[col], errors='coerce')

                # ฟังก์ชันเช็คสถานะ
                def get_status_hist(row):
                    qty_ord = float(row.get('Qty_Ordered', 0))
                    qty_recv = float(row.get('Qty_Received', 0))
                    if qty_recv >= qty_ord and qty_ord > 0: return "เรียบร้อย", "#d4edda", "#155724"
                    if qty_recv > 0 and qty_recv < qty_ord: return "สินค้าไม่ครบ", "#fff3cd", "#856404"
                    exp_date = row.get('Expected_Date')
                    if pd.notna(exp_date):
                        today_date = pd.Timestamp.today().normalize()
                        diff_days = (exp_date - today_date).days
                        if 0 <= diff_days <= 4: return "สินค้าใกล้ถึง", "#cce5ff", "#004085"
                    return "รอจัดส่ง", "#f8f9fa", "#333333"

                status_results = df_final.apply(get_status_hist, axis=1)
                df_final['Status_Text'] = status_results.apply(lambda x: x[0])
                df_final['Status_BG'] = status_results.apply(lambda x: x[1])
                df_final['Status_Color'] = status_results.apply(lambda x: x[2])
                df_final = df_final.sort_values(by=['Order_Date', 'PO_Number', 'Received_Date'], ascending=[False, False, True])

                # Helper functions
                def fmt_num(val, decimals=2):
                    try: return f"{float(val):,.{decimals}f}"
                    except: return "0.00"
                def fmt_date(d):
                    if pd.isna(d) or str(d) == 'NaT': return "-"
                    return d.strftime("%d/%m/%Y")
                grouped = df_final.groupby(['PO_Number', 'Product_ID'], sort=False)
                table_html = "<div class='po-table-container'><table class='custom-po-table'><thead><tr><th>รหัสสินค้า</th><th>รูปสินค้า</th><th>สถานะ</th><th>เลข PO</th><th>ประเภทการนำเข้า</th><th style='background-color: #5f00bf;'>วันที่สั่งซื้อ</th><th style='background-color: #5f00bf;'>วันคาดการณ์</th><th style='background-color: #5f00bf;'>วันที่ได้รับ</th><th style='background-color: #5f00bf;'>ระยะเวลา</th><th style='background-color: #5f00bf;'>จำนวนที่ได้รับ</th><th style='background-color: #00bf00;'>จำนวนสั่งซื้อ</th><th style='background-color: #00bf00;'>ต้นทุน/ชิ้น (฿)</th><th>ยอดเงินหยวน (¥)</th><th>ยอดเงินบาทที่ใช้ (฿)</th><th>เรทเงิน</th><th>เรทค่าขนส่ง</th><th>ขนาด (คิว)</th><th>ค่าส่ง</th><th>น้ำหนัก / KG</th><th>ราคา / ชิ้น (หยวน)</th><th style='background-color: #ff6600;'>SHOPEE</th><th>LAZADA</th><th style='background-color: #000000;'>TIKTOK</th><th>หมายเหตุ</th><th>ร้านค้า</th></tr></thead><tbody>"

                for group_idx, ((po, pid), group) in enumerate(grouped):
                    row_count = len(group)
                    first_row = group.iloc[0] 
                    is_internal = (str(first_row.get('Transport_Type', '')).strip() == "สินค้าภายใน")

                    total_order_qty = group['Qty_Ordered'].sum()
                    if total_order_qty == 0: total_order_qty = 1 
                    total_yuan = group['Total_Yuan'].sum()
                    total_ship_cost = group['Ship_Cost'].sum()
                    calc_total_thb_used = 0
                    if is_internal:
                        calc_total_thb_used = group['Total_THB'].sum()
                    else:
                        for _, r in group.iterrows():
                            calc_total_thb_used += (float(r.get('Total_Yuan',0)) * float(r.get('Yuan_Rate',0)))

                    cost_per_unit_thb = (calc_total_thb_used + total_ship_cost) / total_order_qty if total_order_qty > 0 else 0
                    price_per_unit_yuan = total_yuan / total_order_qty if total_order_qty > 0 else 0
                    rate = float(first_row.get('Yuan_Rate', 0))

                    bg_color = "#222222" if group_idx % 2 == 0 else "#2e2e2e"
                    s_text = first_row['Status_Text']
                    s_bg = first_row['Status_BG']
                    s_col = first_row['Status_Color']

                    for idx, (i, row) in enumerate(group.iterrows()):
                        table_html += f"<tr style='background-color: {bg_color};'>"
                        if idx == 0:
                            curr_token = st.query_params.get("token", "")
                            ts = int(time.time() * 1000)
                            full_pname = str(row.get("Product_Name", "")).replace('"', '&quot;').replace('\n', ' ')
                            table_html += f"<td rowspan='{row_count}' class='td-merged' title='{full_pname}'>"
                            table_html += f"<b>{row['Product_ID']}</b><br>"
                            table_html += f"<div style='white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 200px; margin: 0 auto; font-size: 12px;'>{full_pname}</div></td>"
                            img_src = row.get('Image', '')
                            img_html = f"<img src='{img_src}' width='50' height='50'>" if str(img_src).startswith('http') else ""
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{img_html}</td>"
                            table_html += f"<td rowspan='{row_count}' class='td-merged'><span class='status-badge' style='background-color:{s_bg}; color:{s_col};'>{s_text}</span></td>"
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{row['PO_Number']}</td>"
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{row.get('Transport_Type', '-')}</td>"
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{fmt_date(row['Order_Date'])}</td>"
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{fmt_date(row.get('Expected_Date'))}</td>"
                        recv_d = fmt_date(row['Received_Date'])
                        table_html += f"<td>{recv_d}</td>"
                        wait_val = "-"

                        if pd.notna(row['Received_Date']) and pd.notna(row['Order_Date']):
                            wait_val = f"{(row['Received_Date'] - row['Order_Date']).days} วัน"
                        table_html += f"<td>{wait_val}</td>"
                        qty_recv = int(row.get('Qty_Received', 0))
                        q_style = "color: #ff4b4b; font-weight:bold;" if (qty_recv > 0 and qty_recv != int(row.get('Qty_Ordered', 0))) else "font-weight:bold;"
                        table_html += f"<td style='{q_style}'>{qty_recv:,}</td>"
                        if idx == 0:
                            table_html += f"<td rowspan='{row_count}' class='td-merged' style='color:#AED6F1; font-weight:bold;'>{int(total_order_qty):,}</td>"
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{fmt_num(cost_per_unit_thb)}</td>"
                            val_yuan = "-" if is_internal else fmt_num(total_yuan)
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{val_yuan}</td>"
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{fmt_num(calc_total_thb_used)}</td>"
                            val_rate = "-" if is_internal else fmt_num(rate)
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{val_rate}</td>"
                            val_ship_rate = "-" if is_internal else fmt_num(row.get('Ship_Rate',0))
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{val_ship_rate}</td>"
                            val_cbm = "-" if is_internal else fmt_num(row.get('CBM',0), 4)
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{val_cbm}</td>"
                            val_ship_cost = "-" if is_internal else fmt_num(total_ship_cost)
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{val_ship_cost}</td>"
                            val_weight = "-" if is_internal else fmt_num(row.get('Transport_Weight',0))
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{val_weight}</td>"
                            val_unit_yuan = "-" if is_internal else fmt_num(price_per_unit_yuan)
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{val_unit_yuan}</td>"
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{fmt_num(row.get('Shopee_Price',0))}</td>"
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{fmt_num(row.get('Lazada_Price',0))}</td>"
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{fmt_num(row.get('TikTok_Price',0))}</td>"
                            clean_note = str(row.get("Note","")).replace('\n', ' ')
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{clean_note}</td>"
                            link_val = str(row.get("Link", "")).strip()
                            wechat_val = str(row.get("WeChat", "")).strip()
                            icons_html = ""
                            import urllib.parse
                            
                            if link_val and link_val.lower() not in ['nan', 'none', '']:
                                safe_link = urllib.parse.quote(link_val)
                                icons_html += f"<a href='?view_info={safe_link}&t={int(time.time()*1000)}_{idx}&token={curr_token}' target='_self' style='text-decoration:none; font-size:16px; margin-right:5px; color:#007bff;'>🔗</a>"

                            if wechat_val and wechat_val.lower() not in ['nan', 'none', '']:
                                safe_wechat = urllib.parse.quote(wechat_val)
                                icons_html += f"<a href='?view_info={safe_wechat}&t={int(time.time()*1000)}_{idx}&token={curr_token}' target='_self' style='text-decoration:none; font-size:16px; color:#25D366;'>💬</a>"
                            
                            final_icons = icons_html if icons_html else "-"
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{final_icons}</td>"

                        table_html += "</tr>"
                table_html += "</tbody></table></div>"
                st.markdown(table_html, unsafe_allow_html=True)
            else: 
                st.warning("❌ ไม่พบประวัติการสั่งซื้อสำหรับสินค้านี้")
        else: 
            st.warning("❌ ยังไม่มีข้อมูล PO ในระบบ")



# --- FIX: ย้ายการเช็ค Edit Params มาไว้ตรงนี้ (ก่อนสร้าง Menu Navigation) ---
# เพื่อให้เมื่อ Reload หน้าแล้ว ระบบจะดักจับได้ทันทีและบังคับเข้าหน้า PO
if "edit_po" in st.query_params and "edit_pid" in st.query_params:
    p_po = st.query_params["edit_po"]
    p_pid = st.query_params["edit_pid"]
    
    # ลบ params ออกเพื่อไม่ให้วนลูป
    if "edit_po" in st.query_params: del st.query_params["edit_po"]
    if "edit_pid" in st.query_params: del st.query_params["edit_pid"]
    
    # บันทึกข้อมูลเป้าหมาย และบังคับเปลี่ยนหน้า
    st.session_state.target_edit_data = {"po": p_po, "pid": p_pid}
    st.session_state.active_dialog = "po_edit_direct"
    st.session_state.current_page = "📦 รายการสั่งซื้อ (PO)" 
    st.rerun()
if "delete_idx" in st.query_params:
    d_idx = st.query_params["delete_idx"]
    d_po = st.query_params.get("del_po", "Unknown")
    
    # เก็บค่าเข้า Session เพื่อส่งให้ Dialog
    st.session_state.target_delete_idx = d_idx
    st.session_state.target_delete_po = d_po
    
    # ล้าง Query Params เพื่อไม่ให้รีเฟรชแล้วลบซ้ำ
    del st.query_params["delete_idx"]
    if "del_po" in st.query_params: del st.query_params["del_po"]
    
    # เปิด Dialog ยืนยัน
    st.session_state.active_dialog = "delete_confirm"
    st.session_state.current_page = "📦 รายการสั่งซื้อ (PO)"
    st.rerun()
# -------------------------------------------

# Removed duplicate navigation radio from here since it is now in the sidebar.
# selected_page = st.radio(...)

st.divider()

# --- Global Variables for All Pages ---
thai_months = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", 
               "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
today = date.today()
all_years = [today.year - i for i in range(3)]

# --- Page 1: Daily Sales Summary ---
if st.session_state.current_page == "📅 สรุปยอดขายรายวัน":
    # 🟢 LAZY LOADING FOR DAILY SALES
    with st.spinner('กำลังโหลดข้อมูลยอดขาย...'):
        df_master = get_stock_from_sheet()
        df_sale = get_sale_from_folder()

        if not df_master.empty: df_master['Product_ID'] = df_master['Product_ID'].astype(str)
        if not df_sale.empty: df_sale['Product_ID'] = df_sale['Product_ID'].astype(str)
        
        # Calculate Recent Sales Map
        if not df_sale.empty and 'Date_Only' in df_sale.columns:
            max_date = df_sale['Date_Only'].max()
            latest_date_str = max_date.strftime("%d/%m/%Y")
            df_latest_sale = df_sale[df_sale['Date_Only'] == max_date]
            recent_sales_map = df_latest_sale.groupby('Product_ID')['Qty_Sold'].sum().fillna(0).astype(int).to_dict()

        # Load PO only if strictly needed (History Dialog)
        if "history_pid" in st.query_params or st.session_state.active_dialog == "history":
             df_po = get_po_data()
             if not df_po.empty: df_po['Product_ID'] = df_po['Product_ID'].astype(str)

    st.subheader("📅 สรุปยอดขายรายวัน")
    
    # ตรวจสอบว่ามีการกดดูประวัติจากหน้าอื่นหรือไม่
    if "history_pid" in st.query_params:
        hist_pid = st.query_params["history_pid"]
        del st.query_params["history_pid"] 
        show_history_dialog(fixed_product_id=hist_pid)

    # ฟังก์ชันอัปเดตวันที่เมื่อเปลี่ยนเดือน/ปี
    def update_m_dates():
        y = st.session_state.m_y
        m_index = thai_months.index(st.session_state.m_m) + 1
        _, last_day = calendar.monthrange(y, m_index)
        st.session_state.m_d_start = date(y, m_index, 1)
        st.session_state.m_d_end = date(y, m_index, last_day)

    # ตั้งค่า Default Date
    if "m_d_start" not in st.session_state: st.session_state.m_d_start = date(today.year, today.month, 1)
    if "m_d_end" not in st.session_state:
        _, last_day = calendar.monthrange(today.year, today.month)
        st.session_state.m_d_end = date(today.year, today.month, last_day)

    # --- ส่วน UI Filter (ตัวกรอง) ---
    with st.container(border=True):
        st.markdown("##### 🔍 ตัวกรองข้อมูล")
        c_y, c_m, c_s, c_e = st.columns([1, 1.5, 1.5, 1.5])
        with c_y: st.selectbox("ปี", all_years, key="m_y", on_change=update_m_dates)
        with c_m: st.selectbox("เดือน", thai_months, index=today.month-1, key="m_m", on_change=update_m_dates)
        with c_s: st.date_input("วันที่เริ่มต้น", key="m_d_start")
        with c_e: st.date_input("วันที่สิ้นสุด", key="m_d_end")
        
        #st.divider()
        
        # --- ส่วน Focus Date ---
        col_sec_check, col_sec_date = st.columns([2, 2])
        with col_sec_check:
            st.write("") 
            use_focus_date = st.checkbox("🔎 กรองเฉพาะสินค้าที่มียอดขายในวันที่...โปรดเลือก ✅ และเลือกวันที่", key="use_focus_date")
        focus_date = None
        if use_focus_date:
            with col_sec_date: focus_date = st.date_input("ระบุวันที่ขาย (Focus Date):", value=today, key="filter_focus_date")
        
        #st.divider()

        # --- ส่วน Category / Movement / SKU ---
        col_cat, col_move, col_sku = st.columns([1.5, 1.5, 3])
        
        category_options = ["แสดงทั้งหมด"]
        if not df_master.empty and 'Product_Type' in df_master.columns:
            unique_types = sorted(df_master['Product_Type'].astype(str).unique().tolist())
            category_options += unique_types
            
        sku_options = []
        if not df_master.empty:
            sku_options = df_master.apply(lambda x: f"{x['Product_ID']} : {x['Product_Name']}", axis=1).tolist()
            
        with col_cat: 
            selected_category = st.selectbox("หมวดหมู่สินค้า", category_options, key="filter_category")
            
        with col_move:
            movement_filter = st.selectbox(
                "การเคลื่อนไหว", 
                ["ทั้งหมด", "สินค้าที่มีการเคลื่อนไหว", 'สินค้าที่ "ไม่มี" การเคลื่อนไหว'],
                key="filter_movement"
            )

        with col_sku: 
            selected_skus = st.multiselect("รายการที่เลือก (Choose options):", sku_options, key="filter_skus")

    # --- เริ่มประมวลผลข้อมูล ---
    start_date = st.session_state.m_d_start
    end_date = st.session_state.m_d_end
    
    if start_date and end_date:
        if start_date > end_date: st.error("⚠️ วันที่เริ่มต้นต้องมาก่อนวันที่สิ้นสุด")
        else:
            # 1. กรองข้อมูลการขายตามวันที่
            if not df_sale.empty and 'Date_Only' in df_sale.columns:
                mask_range = (df_sale['Date_Only'] >= start_date) & (df_sale['Date_Only'] <= end_date)
                df_sale_range = df_sale.loc[mask_range].copy()
                
                df_pivot = pd.DataFrame()
                if not df_sale_range.empty:
                    thai_abbr = ["", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
                    df_sale_range['Day_Col'] = df_sale_range['Order_Time'].apply(lambda x: f"{x.day} {thai_abbr[x.month]}")
                    df_sale_range['Day_Sort'] = df_sale_range['Order_Time'].dt.strftime('%Y%m%d')
                    
                    # Pivot Table: แปลงแถวเป็นคอลัมน์วันที่
                    pivot_data = df_sale_range.groupby(['Product_ID', 'Day_Col', 'Day_Sort'])['Qty_Sold'].sum().reset_index()
                    df_pivot = pivot_data.pivot(index='Product_ID', columns='Day_Col', values='Qty_Sold').fillna(0).astype(int)
                    
                    # กรอง Focus Date
                    if use_focus_date and focus_date:
                        products_sold_on_focus = df_sale[(df_sale['Date_Only'] == focus_date) & (df_sale['Qty_Sold'] > 0)]['Product_ID'].unique()
                        df_pivot = df_pivot[df_pivot.index.isin(products_sold_on_focus)]

                # Merge กับ Master
                if not df_pivot.empty:
                    df_pivot = df_pivot.reset_index()
                    final_report = pd.merge(df_master, df_pivot, on='Product_ID', how='left')
                else: 
                    final_report = df_master.copy()
                
                # หาคอลัมน์วันที่ทั้งหมด
                day_cols = [c for c in final_report.columns if c not in df_master.columns]
                day_cols = [c for c in day_cols if isinstance(c, str) and "🔴" not in c and "หมด" not in c]

                final_report[day_cols] = final_report[day_cols].fillna(0).astype(int)
                
                # Apply Filters
                if selected_category != "แสดงทั้งหมด": final_report = final_report[final_report['Product_Type'] == selected_category]
                if selected_skus:
                    selected_ids = [item.split(" : ")[0] for item in selected_skus]
                    final_report = final_report[final_report['Product_ID'].isin(selected_ids)]
                if use_focus_date and focus_date and not df_pivot.empty:
                     final_report = final_report[final_report['Product_ID'].isin(df_pivot['Product_ID'])]
                elif use_focus_date and focus_date and df_pivot.empty:
                     final_report = pd.DataFrame()

                if final_report.empty: st.warning(f"⚠️ ไม่พบข้อมูลสินค้า")
                else:
                    final_report['Total_Sales_Range'] = final_report[day_cols].sum(axis=1).astype(int)
                    
                    # Logic: กรองสินค้าตามการเคลื่อนไหว
                    if movement_filter == "สินค้าที่มีการเคลื่อนไหว":
                        final_report = final_report[final_report['Total_Sales_Range'] > 0]
                    elif movement_filter == 'สินค้าที่ "ไม่มี" การเคลื่อนไหว':
                        final_report = final_report[final_report['Total_Sales_Range'] == 0]
                    
                    # 2. คำนวณ Current Stock (Real vs Calculated)
                    df_real_stock = get_actual_stock_from_folder()
                    
                    if not df_real_stock.empty:
                        real_stock_map = df_real_stock.set_index('Product_ID')['Real_Stock'].to_dict()
                        final_report['Real_Stock_File'] = final_report['Product_ID'].map(real_stock_map)
                        stock_map = df_master.set_index('Product_ID')['Initial_Stock'].to_dict()
                        
                        final_report['Current_Stock'] = final_report.apply(
                            lambda x: x['Real_Stock_File'] if pd.notna(x['Real_Stock_File']) else (stock_map.get(x['Product_ID'], 0) - recent_sales_map.get(x['Product_ID'], 0)), 
                            axis=1
                        )
                    else:
                        stock_map = df_master.set_index('Product_ID')['Initial_Stock'].to_dict()
                        final_report['Current_Stock'] = final_report['Product_ID'].apply(lambda x: stock_map.get(x, 0) - recent_sales_map.get(x, 0))

                    final_report['Current_Stock'] = pd.to_numeric(final_report['Current_Stock'], errors='coerce').fillna(0).astype(int)

                    # 3. คำนวณสถานะ (Status)
                    if 'Min_Limit' not in final_report.columns: final_report['Min_Limit'] = 0
                    final_report['Min_Limit'] = pd.to_numeric(final_report['Min_Limit'], errors='coerce').fillna(0).astype(int)

                    def calc_sales_status(row):
                        curr = row['Current_Stock']
                        limit = row['Min_Limit']
                        if curr <= 0: return "🔴 หมด"
                        elif curr <= limit: return "⚠️ ใกล้หมด"
                        else: return "🟢 ปกติ"

                    final_report['Status'] = final_report.apply(calc_sales_status, axis=1)
                    
                    # เรียงลำดับคอลัมน์วันที่
                    if not df_sale_range.empty:
                         pivot_data_temp = df_sale_range.groupby(['Product_ID', 'Day_Col', 'Day_Sort'])['Qty_Sold'].sum().reset_index()
                         sorted_day_cols = sorted(day_cols, key=lambda x: pivot_data_temp[pivot_data_temp['Day_Col'] == x]['Day_Sort'].values[0] if x in pivot_data_temp['Day_Col'].values else 0)
                    else: sorted_day_cols = sorted(day_cols)

                    fixed_cols = ['Product_ID', 'Image', 'Product_Name', 'Product_Type', 'Current_Stock', 'Total_Sales_Range', 'Status']
                    available_fixed = [c for c in fixed_cols if c in final_report.columns]
                    final_df = final_report[available_fixed + sorted_day_cols]
                    
                    st.divider()
                    
                    # =========================================================
                    # 🖌️ CSS Style (กำหนด CSS ครั้งเดียวตรงนี้)
                    # =========================================================
                    st.markdown("""
                    <style>
                        .daily-sales-table-wrapper { 
                            overflow-x: auto; 
                            width: 100%; 
                            margin-top: 5px; 
                            background: #1c1c1c; 
                            border-radius: 8px; 
                            border: 1px solid #444; 
                            margin-bottom: 20px;
                        }
                        .daily-sales-table { 
                            width: 100%; 
                            min-width: 1200px; 
                            border-collapse: separate; 
                            border-spacing: 0; 
                            font-family: 'Sarabun', sans-serif; 
                            font-size: 11px; 
                            color: #ddd; 
                        }
                        .daily-sales-table th, .daily-sales-table td { padding: 4px 6px; line-height: 1.2; text-align: center; border-bottom: 1px solid #333; border-right: 1px solid #333; white-space: nowrap; vertical-align: middle; }
                        .daily-sales-table thead th { position: sticky; top: 0; z-index: 100; background-color: #1e3c72 !important; color: white !important; font-weight: 700; border-bottom: 2px solid #ffffff !important; min-height: 40px; }
                        .daily-sales-table tbody tr:nth-child(even) td { background-color: #262626 !important; }
                        .daily-sales-table tbody tr:nth-child(odd) td { background-color: #1c1c1c !important; }
                        .daily-sales-table tbody tr:hover td { background-color: #333 !important; }
                        .negative-value { color: #FF0000 !important; font-weight: bold !important; }
                        
                        .col-history { width: 40px !important; min-width: 40px !important; }
                        .col-small { width: 80px !important; min-width: 80px !important; }
                        .col-medium { width: 100px !important; min-width: 100px !important; }
                        .col-image { width: 50px !important; min-width: 50px !important; }
                        .col-name { width: 250px !important; min-width: 200px !important; text-align: left !important; }
                        a.history-link { text-decoration: none; color: white; font-size: 16px; cursor: pointer; }
                        a.history-link:hover { transform: scale(1.2); }
                    </style>
                    """, unsafe_allow_html=True)
                    
                    st.markdown(f"**📊 แสดงผลทั้งหมด:** {len(final_df):,} รายการ")
                    curr_token = st.query_params.get("token", "")

                    # =========================================================
                    # 🚀 เทคนิค Batch Rendering: ทยอยวาดทีละ 100 รายการ
                    # ช่วยให้ Scroll ดูได้หมดในหน้าเดียว และแก้ปัญหาตัวอักษรเพี้ยน
                    # =========================================================
                    chunk_size = 100  
                    
                    for start_idx in range(0, len(final_df), chunk_size):
                        end_idx = start_idx + chunk_size
                        df_chunk = final_df.iloc[start_idx:end_idx]
                        
                        html_parts = []
                        html_parts.append('<div class="daily-sales-table-wrapper"><table class="daily-sales-table">')
                        
                        # สร้าง Header ทุกครั้งเพื่อให้แต่ละก้อนมีหัวตาราง
                        html_parts.append('<thead><tr>')
                        html_parts.append('<th class="col-history">ประวัติ</th>')
                        html_parts.append('<th class="col-small">รหัส</th>')
                        html_parts.append('<th class="col-image">รูป</th>')
                        html_parts.append('<th class="col-name">ชื่อสินค้า</th>')
                        html_parts.append('<th class="col-small">คงเหลือ</th>')
                        html_parts.append('<th class="col-medium">ยอดรวม</th>')
                        html_parts.append('<th class="col-medium">สถานะ</th>')
                        for day_col in sorted_day_cols: 
                            html_parts.append(f'<th class="col-small">{day_col}</th>')
                        html_parts.append('</tr></thead>')
                        
                        html_parts.append('<tbody>')
                        for idx, row in df_chunk.iterrows():
                            current_stock_class = "negative-value" if row['Current_Stock'] < 0 else ""
                            safe_pid = urllib.parse.quote(str(row['Product_ID']).strip())
                            h_link = f"?history_pid={safe_pid}&token={curr_token}"
                            
                            raw_name = str(row.get("Product_Name", ""))
                            clean_name = clean_text_for_html(raw_name)
                            if len(clean_name) > 50: clean_name = clean_name[:47] + "..."

                            html_parts.append('<tr>')
                            html_parts.append(f'<td class="col-history"><a class="history-link" href="{h_link}" target="_self">📜</a></td>')
                            html_parts.append(f'<td class="col-small">{row["Product_ID"]}</td>')
                            
                            if pd.notna(row.get('Image')) and str(row['Image']).startswith('http'):
                                html_parts.append(f'<td class="col-image"><img src="{row["Image"]}" style="width: 40px; height: 40px; object-fit: cover; border-radius: 4px;"></td>')
                            else: 
                                html_parts.append('<td class="col-image"></td>')
                            
                            html_parts.append(f'<td class="col-name">{clean_name}</td>')
                            html_parts.append(f'<td class="col-small {current_stock_class}">{row["Current_Stock"]}</td>')
                            html_parts.append(f'<td class="col-medium">{row["Total_Sales_Range"]}</td>')
                            html_parts.append(f'<td class="col-medium">{row["Status"]}</td>')
                            
                            for day_col in sorted_day_cols:
                                day_value = row.get(day_col, 0)
                                day_class = "negative-value" if isinstance(day_value, (int, float)) and day_value < 0 else ""
                                val_show = int(day_value) if isinstance(day_value, (int, float)) else day_value
                                html_parts.append(f'<td class="col-small {day_class}">{val_show}</td>')
                            
                            html_parts.append('</tr>')
                        
                        html_parts.append('</tbody></table></div>')
                        
                        # แสดงผลทันทีทีละก้อน (Chunk)
                        st.markdown("".join(html_parts), unsafe_allow_html=True)
            else: st.error("⚠️ ไม่พบข้อมูลการขายในช่วงเวลานี้")

# --- Page 2: Purchase Orders ---
elif st.session_state.current_page == "📦 รายการสั่งซื้อ (PO)":
    show_purchase_orders()

# --- Page 3: Stock ---
elif st.session_state.current_page == "📈 รายงาน Stock":
    show_stock_report()

# --- Page 4: Data Manager ---
elif st.session_state.current_page == "📂 จัดการข้อมูล (Upload)":
    show_data_manager_page()

# 🔥 FIX: Preload data if a dialog is active (dialogs need df_master, df_po to work)
if st.session_state.active_dialog:
    if df_master.empty or df_po.empty:
        with st.spinner('📦 Loading data for dialog...'):
            if df_master.empty:
                df_master = get_stock_from_sheet()
                if not df_master.empty: 
                    df_master['Product_ID'] = df_master['Product_ID'].astype(str)
            
            if df_po.empty:
                df_po = get_po_data()
                if not df_po.empty: 
                    df_po['Product_ID'] = df_po['Product_ID'].astype(str)

if st.session_state.active_dialog == "po_batch": 
    po_batch_dialog()
elif st.session_state.active_dialog == "po_internal": 
    po_internal_batch_dialog()
elif st.session_state.active_dialog == "po_search": 
    po_edit_dialog_v2()
elif st.session_state.active_dialog == "po_edit_direct":
    data = st.session_state.get("target_edit_data", {})
    po_edit_dialog_v2(pre_selected_po=data.get("po"), pre_selected_pid=data.get("pid"))
elif st.session_state.active_dialog == "history": 
    show_history_dialog(fixed_product_id=st.session_state.get("selected_product_history"))
elif st.session_state.active_dialog == "po_multi_item": 
    po_multi_item_dialog()
elif st.session_state.active_dialog == "delete_confirm": 
    delete_confirm_dialog()


