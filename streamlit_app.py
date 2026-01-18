import streamlit as st
import pandas as pd
import numpy as np
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from supabase import create_client, Client
import io
import datetime
import calendar
from datetime import date
import math

# --- 1. CONFIGURATION & CSS ---
st.set_page_config(page_title="Dashboard สรุปยอดขาย", layout="wide", page_icon="🛍️")

# Custom CSS
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Kanit:wght@300;400;600&display=swap');
    
    html, body, [class*="css"] { font-family: 'Kanit', sans-serif; }

    /* Container */
    .custom-table-wrapper {
        overflow-x: auto;
        border: 1px solid #ddd;
        border-radius: 8px;
        margin-top: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        background-color: #1c1c1c; 
    }
    
    /* Table Styling General */
    table.report-table {
        width: 100%;
        border-collapse: collapse;
        min-width: 1500px; 
        font-size: 13px;
    }
    
    /* Header */
    table.report-table th {
        background-color: #2c3e50;
        color: white;
        padding: 8px 5px;
        text-align: center;
        border: 1px solid #34495e;
        position: sticky; top: 0; z-index: 100;
        white-space: nowrap;
    }
    
    /* Cells */
    table.report-table td {
        padding: 4px 6px;
        border: 1px solid #e0e0e0;
        color: #333;
        vertical-align: middle;
        height: 35px;
    }

    table.report-table tr:nth-child(even) { background-color: #f9f9f9; }
    table.report-table tr:hover { background-color: #f0f8ff; }

    .num { text-align: right; font-family: 'Courier New', monospace; font-weight: 600; }
    .txt { text-align: center; white-space: nowrap; }
    
    /* Helper Colors */
    .text-green { color: #27ae60; }
    .text-red { color: #fa0000; font-weight: bold; }
    .font-bold { font-weight: bold; }
    
    /* Progress Bar */
    .bar-container { position: absolute; bottom: 0; left: 0; height: 4px; background-color: #27ae60; opacity: 0.7; z-index: 1; }
    .cell-content { position: relative; z-index: 2; }
    td.relative-cell { position: relative; padding-bottom: 8px; }
    </style>
""", unsafe_allow_html=True)

# Supabase & Google Auth Config
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    drive_service = build('drive', 'v3', credentials=creds)
    PARENT_FOLDER_ID = '1DJp8gpZ8lntH88hXqYuZOwIyFv3NY4Ot'
except Exception as e:
    st.error(f"❌ Config Error: {e}")
    st.stop()

# --- 2. HELPER FUNCTIONS ---

def list_files_in_folder(folder_id):
    try:
        query = f"'{folder_id}' in parents and trashed = false"
        results = drive_service.files().list(q=query, fields="files(id, name, mimeType)").execute()
        return results.get('files', [])
    except: return []

def download_file(file_id):
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    fh.seek(0)
    return fh

def clean_date(df, col_name):
    """แปลงวันที่ ตัดเวลาทิ้ง และจัดการ Format ให้เป็น Date Object"""
    if col_name in df.columns:
        df[col_name] = df[col_name].astype(str).str.strip()
        df[col_name] = df[col_name].replace({'nan': None, 'None': None, '': None})
        # dayfirst=True ช่วยให้ 27/12/2025 ถูกอ่านถูกต้อง
        df[col_name] = pd.to_datetime(df[col_name], errors='coerce', dayfirst=True).dt.date
    return df

def clean_text(df, col_name):
    if col_name in df.columns:
        df[col_name] = df[col_name].astype(str).str.strip().str.upper()
    return df

def clean_scientific_notation(val):
    val_str = str(val).strip()
    if 'E' in val_str or 'e' in val_str:
        try: return str(int(float(val)))
        except: return val_str
    return val_str

def get_standard_status(row):
    try: amt = float(row.get('settlement_amount', 0))
    except: amt = 0
    if amt > 0: return "ออเดอร์สำเร็จ"
    raw_status = str(row.get('status', '')).lower()
    if any(x in raw_status for x in ['ยกเลิก', 'cancel']): return "ยกเลิก"
    if any(x in raw_status for x in ['package returned', 'return', 'ตีกลับ']): return "ตีกลับ"
    return "รอดำเนินการ"

def format_thai_date(d_obj):
    if pd.isnull(d_obj): return "-"
    if isinstance(d_obj, str):
        try: d_obj = datetime.datetime.strptime(d_obj, "%Y-%m-%d").date()
        except: return d_obj
    thai_months = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
    return f"{d_obj.day} {thai_months[d_obj.month-1]} {d_obj.year}"

def load_cost_data():
    try:
        response = supabase.table("product_costs").select("sku, platform, unit_cost").execute()
        df = pd.DataFrame(response.data)
        if not df.empty:
            df['unit_cost'] = pd.to_numeric(df['unit_cost'], errors='coerce').fillna(0)
            df['platform'] = df['platform'].str.upper().str.strip()
            df = clean_text(df, 'sku')
            return df[['sku', 'platform', 'unit_cost']]
        return pd.DataFrame()
    except: return pd.DataFrame()

# --- 3. PROCESSORS (XLSX ONLY + Clean Date + Keep Pending) ---
def process_tiktok(order_files, income_files, shop_name):
    all_orders = []
    income_dfs = []
    
    # 1. Income (XLSX Only)
    for f in income_files:
        if 'xlsx' in f['name']:
            try:
                data = download_file(f['id'])
                df = pd.read_excel(data, sheet_name='Order details', dtype=str).iloc[:, [47, 5, 3, 13, 24]]
                df.columns = ['order_id', 'settlement_amount', 'settlement_date', 'fees', 'affiliate']
                df['order_id'] = df['order_id'].apply(clean_scientific_notation)
                for c in df.columns[1:]: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
                df['fees'] = df['fees'] - df['affiliate']
                income_dfs.append(df)
            except: pass
    income_master = pd.concat(income_dfs, ignore_index=True).groupby('order_id').first().reset_index() if income_dfs else pd.DataFrame()

    # 2. Orders (XLSX Only)
    for f in order_files:
        if 'xlsx' in f['name']: # เช็คแค่ xlsx
            try:
                data = download_file(f['id'])
                df = pd.read_excel(data, dtype=str)
                
                if df.empty: continue
                df.columns = df.columns.str.strip()

                # Tiktok: Created Time (Z), Shipped Time (AC)
                if 'Order ID' in df.columns:
                    # ✅ ไม่ลบออเดอร์ด้วย Shipped Time (เพื่อให้เห็นออเดอร์ใหม่)
                    df = df.dropna(subset=['Order ID'])
                    
                    prod_col = 'Product Name' if 'Product Name' in df.columns else df.columns[7]

                    cols = {'Order ID':'order_id', 'Order Status':'status', 'Seller SKU':'sku', 'Quantity':'quantity', 
                            'SKU Subtotal After Discount':'sales_amount', 'Created Time':'created_date', 
                            'Shipped Time':'shipped_date', 'Tracking ID':'tracking_id', prod_col: 'product_name'}
                    
                    df = df[[c for c in cols if c in df.columns]].rename(columns=cols)
                    df['shop_name'] = shop_name; df['platform'] = 'TIKTOK'
                    
                    # ✅ Clean Date (ตัดเวลาทิ้ง)
                    df = clean_date(df, 'created_date')
                    df = clean_date(df, 'shipped_date')
                    
                    df['order_id'] = df['order_id'].apply(clean_scientific_notation)
                    if 'product_name' not in df.columns: df['product_name'] = "-"
                    all_orders.append(clean_text(df, 'sku'))
            except: pass
    
    if not all_orders: return pd.DataFrame()
    final = pd.concat(all_orders, ignore_index=True).drop_duplicates(subset=['order_id', 'sku'], keep='first')
    return pd.merge(final, income_master, on='order_id', how='left') if not income_master.empty else final

def process_shopee(order_files, income_files, shop_name):
    all_orders = []
    income_dfs = []
    
    # 1. Income (XLSX/XLS Only)
    for f in income_files:
        if any(x in f['name'].lower() for x in ['xls', 'xlsx']):
            try:
                data = download_file(f['id'])
                # Shopee บางทีเป็น XLS เก่า
                df = pd.read_excel(data, sheet_name='Income', header=5, dtype=str)
                df.columns = df.columns.str.strip()
                rename = {'หมายเลขคำสั่งซื้อ':'order_id', 'วันที่โอนชำระเงินสำเร็จ':'settlement_date', 'สินค้าราคาปกติ':'op', 'ค่าคอมมิชชั่น':'aff', 'จำนวนเงินทั้งหมดที่โอนแล้ว (฿)':'settlement_amount'}
                df = df[[c for c in rename if c in df.columns]].rename(columns=rename)
                for c in ['op', 'settlement_amount', 'aff']: 
                    if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
                if 'op' in df.columns: df['fees'] = df['op'] - df['settlement_amount'] - df.get('aff',0)
                income_dfs.append(df.rename(columns={'aff':'affiliate'}))
            except: pass
    income_master = pd.concat(income_dfs, ignore_index=True).drop_duplicates(subset=['order_id']) if income_dfs else pd.DataFrame()
    if not income_master.empty: income_master['order_id'] = income_master['order_id'].apply(clean_scientific_notation)

    # 2. Orders (XLSX/XLS Only)
    for f in order_files:
        if any(x in f['name'].lower() for x in ['xls', 'xlsx']):
            try:
                data = download_file(f['id'])
                df = pd.read_excel(data, dtype=str)
                
                if df.empty: continue
                df.columns = df.columns.str.strip()
                
                # Shopee: วันที่ทำการสั่งซื้อ (G), เวลาการชำระสินค้า (H)
                if 'หมายเลขคำสั่งซื้อ' in df.columns:
                    # ✅ ไม่ลบออเดอร์ด้วย เวลาชำระสินค้า
                    df = df.dropna(subset=['หมายเลขคำสั่งซื้อ'])
                    
                    cols = {'หมายเลขคำสั่งซื้อ':'order_id', 'สถานะการสั่งซื้อ':'status', 'เวลาการชำระสินค้า':'shipped_date',
                            'เลขอ้างอิง SKU (SKU Reference No.)':'sku', 'จำนวน':'quantity', 'ราคาขายสุทธิ':'sales_amount',
                            '*หมายเลขติดตามพัสดุ':'tracking_id', 'วันที่ทำการสั่งซื้อ':'created_date',
                            'ชื่อสินค้า': 'product_name'}
                    
                    df = df[[c for c in cols if c in df.columns]].rename(columns=cols)
                    df['shop_name'] = shop_name; df['platform'] = 'SHOPEE'
                    
                    # ✅ Clean Date (ตัดเวลาทิ้ง)
                    df = clean_date(df, 'created_date')
                    df = clean_date(df, 'shipped_date')
                    
                    df['order_id'] = df['order_id'].apply(clean_scientific_notation)
                    if 'product_name' not in df.columns: df['product_name'] = "-"
                    all_orders.append(clean_text(df, 'sku'))
            except: pass

    if not all_orders: return pd.DataFrame()
    final = pd.concat(all_orders, ignore_index=True).drop_duplicates(subset=['order_id', 'sku'], keep='first')
    return pd.merge(final, income_master, on='order_id', how='left') if not income_master.empty else final

def process_lazada(order_files, income_files, shop_name):
    all_orders = []
    income_dfs = []
    
    # 1. Income (XLSX Only)
    for f in income_files:
        if 'xlsx' in f['name']:
            try:
                data = download_file(f['id'])
                df = pd.read_excel(data, sheet_name='Income Overview', dtype=str)
                col_order = df.columns[0] if 'orderNumber' in df.columns else df.columns[10]
                df = df[[col_order, df.columns[2], df.columns[3]]]
                df.columns = ['order_id', 'settlement_date', 'amount']
                df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
                income_dfs.append(df)
            except: pass
    
    income_master = pd.DataFrame()
    if income_dfs:
        raw = pd.concat(income_dfs, ignore_index=True)
        raw['order_id'] = raw['order_id'].apply(clean_scientific_notation)
        income_master = raw.groupby(['order_id']).agg(
            settlement_amount=('amount', lambda x: x[x>0].sum()),
            fees=('amount', lambda x: x[x<0].sum())
        ).reset_index()
        income_master['affiliate'] = 0

    # 2. Orders (XLSX Only)
    for f in order_files:
        if 'xlsx' in f['name']:
            try:
                data = download_file(f['id'])
                df = pd.read_excel(data, dtype=str)
                if 'orderNumber' in df.columns:
                    df = df.dropna(subset=['orderNumber'])
                    
                    # Lazada: createTime (I), deliveredDate (P)
                    cols = {'orderNumber':'order_id', 'status':'status', 'sellerSku':'sku', 'unitPrice':'sales_amount',
                            'trackingCode':'tracking_id', 'createTime':'created_date', 'deliveredDate':'shipped_date',
                            'itemName': 'product_name'}
                    
                    df = df[[c for c in cols if c in df.columns]].rename(columns=cols)
                    df['quantity'] = 1; df['shop_name'] = shop_name; df['platform'] = 'LAZADA'
                    
                    # ✅ Clean Date
                    df = clean_date(df, 'created_date')
                    df = clean_date(df, 'shipped_date')
                    
                    df['order_id'] = df['order_id'].apply(clean_scientific_notation)
                    if 'product_name' not in df.columns: df['product_name'] = "-"
                    all_orders.append(clean_text(df, 'sku'))
            except: pass

    if not all_orders: return pd.DataFrame()
    final = pd.concat(all_orders, ignore_index=True).drop_duplicates(subset=['order_id', 'sku'], keep='first')
    return pd.merge(final, income_master, on='order_id', how='left') if not income_master.empty else final

# ==========================================
# SIDEBAR: SYNC SYSTEM
# ==========================================
with st.sidebar:
    st.header("🔄 ระบบดึงข้อมูล")
    st.caption("Google Drive > Database")
    
    st.link_button(
        "📂 ไปยังไดร์ฟข้อมูล", 
        "https://drive.google.com/drive/folders/1DJp8gpZ8lntH88hXqYuZOwIyFv3NY4Ot", 
        use_container_width=True
    )
    
    st.markdown("---")
    
    with st.expander("🛠️ เครื่องมือ Sync", expanded=True):
        start_sync = st.button("🚀 Sync Data (ล้างเก่าลงใหม่)", type="primary", use_container_width=True)
        
        if start_sync:
            status_box = st.empty()
            status_box.info("⏳ กำลังเชื่อมต่อ Google Drive...")
            
            root_files = list_files_in_folder(PARENT_FOLDER_ID)
            if not root_files:
                st.error("❌ ไม่พบไฟล์ในโฟลเดอร์หลัก")
            else:
                folder_map = {f['name']: f['id'] for f in root_files if f['mimeType'] == 'application/vnd.google-apps.folder'}
                shops = {'TIKTOK': ['TIKTOK 1', 'TIKTOK 2', 'TIKTOK 3'], 'SHOPEE': ['SHOPEE 1', 'SHOPEE 2', 'SHOPEE 3'], 'LAZADA': ['LAZADA 1', 'LAZADA 2', 'LAZADA 3']}
                inc_folders = {'TIKTOK': 'INCOME TIKTOK', 'SHOPEE': 'INCOME SHOPEE', 'LAZADA': 'INCOME LAZADA'}
                
                all_data = []
                for platform, shop_list in shops.items():
                    inc_id = folder_map.get(inc_folders.get(platform), '')
                    inc_files = list_files_in_folder(inc_id)
                    for shop_name in shop_list:
                        if shop_name in folder_map:
                            status_box.text(f"กำลังโหลด: {shop_name}...")
                            order_files = list_files_in_folder(folder_map[shop_name])
                            df_res = pd.DataFrame()
                            if platform == 'TIKTOK': df_res = process_tiktok(order_files, inc_files, shop_name)
                            elif platform == 'SHOPEE': df_res = process_shopee(order_files, inc_files, shop_name)
                            elif platform == 'LAZADA': df_res = process_lazada(order_files, inc_files, shop_name)
                            if not df_res.empty: all_data.append(df_res)

                if all_data:
                    status_box.text("📊 กำลังประมวลผล...")
                    master_df = pd.concat(all_data, ignore_index=True).drop_duplicates(subset=['order_id', 'sku'], keep='first')
                    
                    # Numeric Convert
                    for c in ['quantity', 'sales_amount', 'settlement_amount', 'fees', 'affiliate', 'unit_cost']:
                        if c in master_df.columns: master_df[c] = pd.to_numeric(master_df[c], errors='coerce').fillna(0)
                        else: master_df[c] = 0.0

                    # Pro-rate
                    totals = master_df.groupby('order_id')['sales_amount'].transform('sum')
                    ratio = master_df['sales_amount'] / totals.replace(0, 1)
                    master_df['settlement_amount'] *= ratio; master_df['fees'] *= ratio; master_df['affiliate'] *= ratio
                    if 'platform' in master_df.columns: master_df.loc[master_df['platform'] == 'LAZADA', 'affiliate'] = 0

                    # Cost
                    cost_df = load_cost_data()
                    if not cost_df.empty:
                        master_df = pd.merge(master_df, cost_df, on=['sku', 'platform'], how='left')
                        if 'unit_cost_y' in master_df.columns:
                            master_df['unit_cost'] = master_df['unit_cost_y'].fillna(0)
                            master_df = master_df.drop(columns=['unit_cost_x', 'unit_cost_y'], errors='ignore')
                    
                    master_df['unit_cost'] = master_df['unit_cost'].fillna(0)
                    master_df['total_cost'] = master_df['quantity'] * master_df['unit_cost']
                    master_df['net_profit'] = master_df['settlement_amount'] - master_df['total_cost']
                    master_df['status'] = master_df.apply(get_standard_status, axis=1)

                    if 'product_name' not in master_df.columns: master_df['product_name'] = "-"
                    master_df['product_name'] = master_df['product_name'].fillna("-")

                    # Date String
                    for c in ['created_date', 'shipped_date', 'settlement_date']:
                        if c in master_df.columns: master_df[c] = master_df[c].astype(str).replace({'nan': None, 'None': None})
                    
                    # Upload
                    status_box.text("☁️ อัปโหลดขึ้น Database...")
                    cols = ['order_id', 'status', 'sku', 'product_name', 'quantity', 'sales_amount', 'settlement_amount', 'fees', 'affiliate', 'net_profit', 'total_cost', 'unit_cost', 'settlement_date', 'created_date', 'shipped_date', 'tracking_id', 'shop_name', 'platform']
                    master_df = master_df[[c for c in cols if c in master_df.columns]]
                    
                    try: supabase.table("orders").delete().neq("id", 0).execute()
                    except: pass
                    
                    records = master_df.to_dict('records')
                    clean_records = []
                    for r in records:
                        new_r = {}
                        for k, v in r.items():
                            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)): new_r[k] = 0.0
                            else: new_r[k] = v
                        clean_records.append(new_r)

                    chunk_size = 500
                    for i in range(0, len(clean_records), chunk_size):
                        supabase.table("orders").insert(clean_records[i:i+chunk_size]).execute()
                    
                    status_box.success(f"✅ Sync สำเร็จ! ({len(master_df)} รายการ)")
                    st.rerun()

# ==========================================
# MAIN CONTENT
# ==========================================
thai_months = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
today = datetime.datetime.now().date()

tab_dash, tab_details, tab_ads, tab_cost, tab_old = st.tabs(["📊 สรุปยอดขาย (Dashboard)", "📦 รายละเอียดออเดอร์", "📢 บันทึกค่าโฆษณา", "💰 จัดการต้นทุน", "📂 ตารางข้อมูลเดิม"])

# --- TAB 1: DASHBOARD ---
with tab_dash:
    st.header("📊 สรุปยอดขายทุกแพลตฟอร์ม")
    col_filters = st.columns([1, 1, 1, 1])
    
    if "d_start" not in st.session_state:
        st.session_state.d_start = today.replace(day=1)
        st.session_state.d_end = today

    def update_dates():
        y = st.session_state.sel_year; m_str = st.session_state.sel_month
        try:
            m_idx = thai_months.index(m_str) + 1
            _, days = calendar.monthrange(y, m_idx)
            st.session_state.d_start = date(y, m_idx, 1)
            st.session_state.d_end = date(y, m_idx, days)
        except: pass

    with col_filters[0]: st.selectbox("ปี", [2024, 2025, 2026], index=1, key="sel_year", on_change=update_dates)
    with col_filters[1]: st.selectbox("เดือน", thai_months, index=today.month-1, key="sel_month", on_change=update_dates)
    with col_filters[2]: st.session_state.d_start = st.date_input("วันที่เริ่ม", st.session_state.d_start)
    with col_filters[3]: st.session_state.d_end = st.date_input("ถึงวันที่", st.session_state.d_end)

    cp1, cp2, cp3, cp4, cp5 = st.columns([1, 1, 1, 1, 6])
    with cp1: all_plat = st.checkbox("✅ ทั้งหมด", value=True)
    with cp2: tiktok_check = st.checkbox("✅ Tiktok", value=all_plat, disabled=all_plat)
    with cp3: shopee_check = st.checkbox("✅ Shopee", value=all_plat, disabled=all_plat)
    with cp4: lazada_check = st.checkbox("✅ Lazada", value=all_plat, disabled=all_plat)

    sel_plats = ['TIKTOK', 'SHOPEE', 'LAZADA'] if all_plat else []
    if not all_plat:
        if tiktok_check: sel_plats.append('TIKTOK')
        if shopee_check: sel_plats.append('SHOPEE')
        if lazada_check: sel_plats.append('LAZADA')

    try:
        res = supabase.table("orders").select("*").execute()
        raw_df = pd.DataFrame(res.data)
        
        ads_db = pd.DataFrame()
        try:
            ads_res = supabase.table("daily_ads").select("*").gte("date", str(st.session_state.d_start)).lte("date", str(st.session_state.d_end)).execute()
            ads_temp = pd.DataFrame(ads_res.data)
            if not ads_temp.empty:
                ads_db = ads_temp.rename(columns={'date': 'created_date', 'ads_amount': 'manual_ads', 'roas_ads': 'manual_roas'})
                ads_db['created_date'] = pd.to_datetime(ads_db['created_date']).dt.date
                ads_db['manual_ads'] = pd.to_numeric(ads_db['manual_ads'], errors='coerce').fillna(0)
                ads_db['manual_roas'] = pd.to_numeric(ads_db['manual_roas'], errors='coerce').fillna(0)
                ads_db = ads_db[['created_date', 'manual_ads', 'manual_roas']]
        except: pass

        if not raw_df.empty:
            raw_df['created_date'] = pd.to_datetime(raw_df['created_date']).dt.date
            mask = (raw_df['created_date'] >= st.session_state.d_start) & (raw_df['created_date'] <= st.session_state.d_end)
            if 'platform' in raw_df.columns: mask &= raw_df['platform'].str.upper().isin(sel_plats)
            df = raw_df.loc[mask].copy()

            for c in ['sales_amount', 'total_cost', 'fees', 'affiliate']:
                if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

            date_range = pd.date_range(start=st.session_state.d_start, end=st.session_state.d_end)
            dates_df = pd.DataFrame({'created_date': date_range.date})
            
            daily = df.groupby('created_date').agg(
                success_count=('status', lambda x: (x == 'ออเดอร์สำเร็จ').sum()),
                pending_count=('status', lambda x: (x == 'รอดำเนินการ').sum()),
                return_count=('status', lambda x: (x == 'ตีกลับ').sum()),
                cancel_count=('status', lambda x: (x == 'ยกเลิก').sum()),
                sales_sum=('sales_amount', 'sum'),
                cost_sum=('total_cost', 'sum'),
                fees_sum=('fees', 'sum'),
                affiliate_sum=('affiliate', 'sum')
            ).reset_index()
            
            step1 = pd.merge(dates_df, daily, on='created_date', how='left').fillna(0)
            
            if not ads_db.empty:
                final_df = pd.merge(step1, ads_db, on='created_date', how='left').fillna(0)
            else:
                final_df = step1.copy(); final_df['manual_ads'] = 0; final_df['manual_roas'] = 0

            calc = final_df.copy()
            calc['total_orders'] = calc['success_count'] + calc['pending_count'] + calc['return_count'] + calc['cancel_count']
            calc['กำไร'] = calc['sales_sum'] - calc['cost_sum'] - calc['fees_sum'] - calc['affiliate_sum']
            calc['ADS VAT 7%'] = calc['manual_ads'] * 0.07
            calc['ค่าแอดรวม'] = calc['manual_ads'] + calc['manual_roas'] + calc['ADS VAT 7%']
            calc['ROAS'] = calc.apply(lambda x: (x['sales_sum']/x['ค่าแอดรวม']) if x['ค่าแอดรวม'] > 0 else 0, axis=1)
            calc['ค่าดำเนินการ'] = calc['total_orders'] * 10
            calc['กำไรสุทธิ'] = calc['กำไร'] - calc['ค่าแอดรวม'] - calc['ค่าดำเนินการ']

            # HTML GENERATION (Compact)
            st.markdown("""
            <style>
                table.report-table { border-collapse: collapse; width: 100%; font-size: 13px; }
                table.report-table th { color: #ffffff !important; font-weight: bold !important; border: 1px solid #444 !important; padding: 8px; text-align: center; }
                table.report-table td { color: #ffffff !important; border: 1px solid #333; padding: 6px; vertical-align: middle; text-align: center !important; }
                table.report-table tbody tr:nth-of-type(odd) { background-color: #1c1c1c; }
                table.report-table tbody tr:nth-of-type(even) { background-color: #262626; }
                table.report-table tbody tr:hover { background-color: #333333 !important; }
                tr.total-row td { background-color: #010538 !important; color: #ffffff !important; font-weight: bold; border-top: 2px solid #555; }
                .text-red { color: #fa0000 !important; font-weight: bold; }
                .bar-container { position: absolute; bottom: 0; left: 0; height: 4px; background-color: #27ae60; opacity: 0.7; z-index: 1; }
                .cell-content { position: relative; z-index: 2; }
                td.relative-cell { position: relative; padding-bottom: 8px; }
            </style>
            """, unsafe_allow_html=True)

            h_blue = "#1e3c72"; h_cyan = "#22b8e6"; h_orange = "#e67e22"; h_green = "#27ae60"

            html_parts = []
            html_parts.append(f"""
            <div class="custom-table-wrapper">
            <table class="report-table">
                <thead>
                    <tr>
                        <th style="background-color: {h_blue}; min-width: 85px;">วันที่</th>
                        <th style="background-color: {h_blue};">จำนวนออเดอร์</th>
                        <th style="background-color: {h_blue};">ออเดอร์สำเร็จ</th>
                        <th style="background-color: {h_blue};">รอดำเนินการ</th>
                        <th style="background-color: {h_blue};">ตีกลับ</th>
                        <th style="background-color: {h_blue};">ยกเลิก</th>
                        <th style="background-color: {h_blue};">ยอดขายรวม</th>
                        <th style="background-color: {h_cyan};">ROAS</th>
                        <th style="background-color: {h_cyan};">ROAS ADS</th>
                        <th style="background-color: {h_blue};">ทุนรวม</th>
                        <th style="background-color: {h_blue};">%ทุนรวม</th>
                        <th style="background-color: {h_blue};">ค่าธรรมเนียม</th>
                        <th style="background-color: {h_blue};">%ค่าธรรมเนียม</th>
                        <th style="background-color: {h_blue};">ค่าแอฟฟิลิเอต</th>
                        <th style="background-color: {h_blue};">%ค่าแอฟฟิลิเอต</th>
                        <th style="background-color: {h_blue};">กำไร</th>
                        <th style="background-color: {h_blue};">%กำไร</th>
                        <th style="background-color: {h_orange};">ค่าADS</th>
                        <th style="background-color: {h_orange};">ADS VAT 7%</th>
                        <th style="background-color: {h_orange};">ค่าแอดรวม</th>
                        <th style="background-color: {h_blue};">%ค่าแอด</th>
                        <th style="background-color: {h_blue};">ค่าดำเนินการ</th>
                        <th style="background-color: {h_blue};">%ค่าดำเนินการ</th>
                        <th style="background-color: {h_green}; min-width: 120px;">กำไรสุทธิ</th>
                        <th style="background-color: {h_blue};">%กำไรสุทธิ</th>
                    </tr>
                </thead>
                <tbody>
            """)

            def fmt_val(val, is_percent=False):
                s_val = f"{val:,.1f}%" if is_percent else f"{val:,.2f}"
                if is_percent: s_val = f"{val:.1f}%"
                if val < 0: return f'<span class="text-red">{s_val}</span>'
                return s_val

            max_profit = calc['กำไรสุทธิ'].max()
            if max_profit <= 0: max_profit = 1

            for _, r in calc.iterrows():
                sales = r['sales_sum']
                net_profit = r['กำไรสุทธิ']
                date_str = format_thai_date(r['created_date'])

                bar_width = 0
                if net_profit > 0: bar_width = min((net_profit / max_profit) * 100, 100)
                bar_html = f'<div class="bar-container" style="width: {bar_width}%;"></div>' if bar_width > 0 else ""

                row_html = f"""
                <tr>
                    <td class="txt">{date_str}</td>
                    <td class="num">{int(r['total_orders'])}</td>
                    <td class="num">{int(r['success_count'])}</td>
                    <td class="num">{int(r['pending_count'])}</td>
                    <td class="num">{int(r['return_count'])}</td>
                    <td class="num">{int(r['cancel_count'])}</td>
                    <td class="num">{fmt_val(sales)}</td>
                    <td class="num">{fmt_val(r['ROAS'])}</td>
                    <td class="num">{fmt_val(r['manual_roas'])}</td>
                    <td class="num">{fmt_val(r['cost_sum'])}</td>
                    <td class="num">{fmt_val(safe_div(r['cost_sum'], sales), True)}</td>
                    <td class="num">{fmt_val(r['fees_sum'])}</td>
                    <td class="num">{fmt_val(safe_div(r['fees_sum'], sales), True)}</td>
                    <td class="num">{fmt_val(r['affiliate_sum'])}</td>
                    <td class="num">{fmt_val(safe_div(r['affiliate_sum'], sales), True)}</td>
                    <td class="num">{fmt_val(r['กำไร'])}</td>
                    <td class="num">{fmt_val(safe_div(r['กำไร'], sales), True)}</td>
                    <td class="num">{fmt_val(r['manual_ads'])}</td>
                    <td class="num">{fmt_val(r['ADS VAT 7%'])}</td>
                    <td class="num">{fmt_val(r['ค่าแอดรวม'])}</td>
                    <td class="num">{fmt_val(safe_div(r['ค่าแอดรวม'], sales), True)}</td>
                    <td class="num">{fmt_val(r['ค่าดำเนินการ'])}</td>
                    <td class="num">{fmt_val(safe_div(r['ค่าดำเนินการ'], sales), True)}</td>
                    <td class="num font-bold relative-cell">
                        <span class="cell-content">{fmt_val(net_profit)}</span>
                        {bar_html}
                    </td>
                    <td class="num">{fmt_val(safe_div(net_profit, sales), True)}</td>
                </tr>"""
                html_parts.append(row_html.replace('\n', ''))

            # Total Row
            sum_sales = calc['sales_sum'].sum()
            sum_cost = calc['cost_sum'].sum()
            sum_fee = calc['fees_sum'].sum()
            sum_aff = calc['affiliate_sum'].sum()
            sum_profit_gross = calc['กำไร'].sum()
            sum_ads = calc['manual_ads'].sum()
            sum_ads_vat = calc['ADS VAT 7%'].sum()
            sum_ads_total = calc['ค่าแอดรวม'].sum()
            sum_ops = calc['ค่าดำเนินการ'].sum()
            sum_net_profit = calc['กำไรสุทธิ'].sum()
            
            total_roas = (sum_sales / sum_ads_total) if sum_ads_total > 0 else 0
            avr_ROAS_ADS = calc['manual_roas'].mean() if len(calc) > 0 else 0
            
            total_html = f"""
            <tr class="total-row">
                <td class="txt">รวม</td>
                <td class="num">{int(calc['total_orders'].sum())}</td>
                <td class="num">{int(calc['success_count'].sum())}</td>
                <td class="num">{int(calc['pending_count'].sum())}</td>
                <td class="num">{int(calc['return_count'].sum())}</td>
                <td class="num">{int(calc['cancel_count'].sum())}</td>
                <td class="num">{fmt_val(sum_sales)}</td>
                <td class="num">{fmt_val(total_roas)}</td>
                <td class="num">{fmt_val(avr_ROAS_ADS)}</td>
                <td class="num">{fmt_val(sum_cost)}</td>
                <td class="num">{fmt_val(safe_div(sum_cost, sum_sales), True)}</td>
                <td class="num">{fmt_val(sum_fee)}</td>
                <td class="num">{fmt_val(safe_div(sum_fee, sum_sales), True)}</td>
                <td class="num">{fmt_val(sum_aff)}</td>
                <td class="num">{fmt_val(safe_div(sum_aff, sum_sales), True)}</td>
                <td class="num">{fmt_val(sum_profit_gross)}</td>
                <td class="num">{fmt_val(safe_div(sum_profit_gross, sum_sales), True)}</td>
                <td class="num">{fmt_val(sum_ads)}</td>
                <td class="num">{fmt_val(sum_ads_vat)}</td>
                <td class="num">{fmt_val(sum_ads_total)}</td>
                <td class="num">{fmt_val(safe_div(sum_ads_total, sum_sales), True)}</td>
                <td class="num">{fmt_val(sum_ops)}</td>
                <td class="num">{fmt_val(safe_div(sum_ops, sum_sales), True)}</td>
                <td class="num">{fmt_val(sum_net_profit)}</td>
                <td class="num">{fmt_val(safe_div(sum_net_profit, sum_sales), True)}</td>
            </tr>
            """
            html_parts.append(total_html.replace('\n', ''))

            html_parts.append("</tbody></table></div>")
            st.markdown("".join(html_parts), unsafe_allow_html=True)
            
        else: st.info("ไม่พบข้อมูลในช่วงเวลานี้")
    except Exception as e: st.error(f"Error Processing: {e}")

# --- TAB 2: DETAILED ORDER ---
with tab_details:
    st.header("📦 รายละเอียดออเดอร์แยกรายสินค้า")
    sub_plat_list = ["TIKTOK", "SHOPEE", "LAZADA"]
    selected_platform = st.radio("เลือกแพลตฟอร์ม", sub_plat_list, horizontal=True)
    st.markdown("---")
    
    col_d1, col_d2 = st.columns(2)
    with col_d1: d_start_det = st.date_input("เริ่มวันที่", st.session_state.d_start, key="det_start")
    with col_d2: d_end_det = st.date_input("ถึงวันที่", st.session_state.d_end, key="det_end")

    try:
        res = supabase.table("orders").select("*").execute()
        raw_df = pd.DataFrame(res.data)
        
        if not raw_df.empty:
            raw_df['created_date'] = pd.to_datetime(raw_df['created_date'], errors='coerce').dt.date
            mask = (raw_df['created_date'] >= d_start_det) & \
                   (raw_df['created_date'] <= d_end_det) & \
                   (raw_df['platform'] == selected_platform)
            df = raw_df.loc[mask].copy()
            
            if df.empty:
                st.info(f"ไม่พบข้อมูล {selected_platform} ในช่วงวันที่เลือก")
            else:
                for c in ['sales_amount', 'total_cost', 'fees', 'affiliate', 'settlement_amount', 'unit_cost']:
                    df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
                
                df = df.sort_values(by=['created_date', 'order_id'], ascending=[False, False])
                
                h_blue = "#1e3c72"; h_cyan = "#22b8e6"; h_green = "#27ae60"
                html = f"""
                <table style="width:100%; border-collapse: collapse; font-size: 13px; color: white;">
                    <thead>
                        <tr>
                            <th style="background-color: {h_blue}; padding: 8px; border: 1px solid #444;">วันที่ทำการสั่งซื้อ</th>
                            <th style="background-color: {h_blue}; padding: 8px; border: 1px solid #444;">เลขคำสั่งซื้อ</th>
                            <th style="background-color: {h_blue}; padding: 8px; border: 1px solid #444;">ชื่อสินค้า</th>
                            <th style="background-color: {h_blue}; padding: 8px; border: 1px solid #444;">รหัสสินค้า</th>
                            <th style="background-color: {h_blue}; padding: 8px; border: 1px solid #444;">ยอดขาย</th>
                            <th style="background-color: {h_cyan}; padding: 8px; border: 1px solid #444;">ทุน</th>
                            <th style="background-color: {h_blue}; padding: 8px; border: 1px solid #444;">%ทุน</th>
                            <th style="background-color: {h_blue}; padding: 8px; border: 1px solid #444;">ค่าธรรมเนียม</th>
                            <th style="background-color: {h_blue}; padding: 8px; border: 1px solid #444;">%ค่าธรรมเนียม</th>
                            <th style="background-color: {h_blue}; padding: 8px; border: 1px solid #444;">ค่าแอฟฟิลิเอต</th>
                            <th style="background-color: {h_blue}; padding: 8px; border: 1px solid #444;">%ค่าแอฟฟิลิเอต</th>
                            <th style="background-color: {h_blue}; padding: 8px; border: 1px solid #444;">ค่าดำเนินการ</th>
                            <th style="background-color: {h_blue}; padding: 8px; border: 1px solid #444;">%ค่าดำเนินการ</th>
                            <th style="background-color: {h_blue}; padding: 8px; border: 1px solid #444;">วันที่ได้รับเงิน</th>
                            <th style="background-color: {h_blue}; padding: 8px; border: 1px solid #444;">ยอดเงินที่ได้รับจริง</th>
                            <th style="background-color: {h_green}; padding: 8px; border: 1px solid #444;">กำไรสุทธิ</th>
                            <th style="background-color: {h_green}; padding: 8px; border: 1px solid #444;">%กำไรสุทธิ</th>
                        </tr>
                    </thead>
                    <tbody>
                """
                grouped = df.groupby('order_id', sort=False)
                row_counter = 0
                def fmt_num(val, color_neg=True):
                    s = f"{val:,.2f}"
                    if color_neg and val < 0: return f'<span class="text-red">{s}</span>'
                    return s
                def fmt_pct(num, div):
                    if div == 0: return "0.0%"
                    val = (num/div) * 100
                    return f"{val:,.1f}%"

                sum_sales = 0; sum_net_profit = 0
                for order_id, group in grouped:
                    row_counter += 1
                    bg_color = "#1c1c1c" if row_counter % 2 != 0 else "#262626"
                    hover_color = "#333333"
                    
                    order_sales = group['sales_amount'].sum()
                    order_fees = group['fees'].sum()
                    order_aff = group['affiliate'].sum()
                    order_settle = group['settlement_amount'].sum()
                    order_cost_total = group['total_cost'].sum()
                    ops_cost = 10.0
                    order_net_profit = order_sales - order_cost_total - order_fees - order_aff - ops_cost
                    sum_sales += order_sales; sum_net_profit += order_net_profit

                    created_date_str = format_thai_date(group.iloc[0]['created_date'])
                    settle_date_str = format_thai_date(group.iloc[0]['settlement_date']) if group.iloc[0]['settlement_date'] else "-"
                    num_items = len(group)
                    
                    for i, (idx, row) in enumerate(group.iterrows()):
                        html += f'<tr style="background-color: {bg_color};" onmouseover="this.style.backgroundColor=\'{hover_color}\'" onmouseout="this.style.backgroundColor=\'{bg_color}\'">'
                        if i == 0:
                            html += f'<td rowspan="{num_items}" style="border:1px solid #333; text-align:center; vertical-align:middle;">{created_date_str}</td>'
                            html += f'<td rowspan="{num_items}" style="border:1px solid #333; text-align:center; vertical-align:middle;">{order_id}</td>'
                        
                        prod_name = row.get('product_name', '-')
                        sku = row.get('sku', '-')
                        unit_cost = row.get('unit_cost', 0)
                        item_sales = row.get('sales_amount', 0)
                        pct_cost = fmt_pct(unit_cost, item_sales)
                        
                        html += f'<td style="border:1px solid #333; padding:5px;">{prod_name}</td>'
                        html += f'<td style="border:1px solid #333; text-align:center;">{sku}</td>'
                        
                        if i == 0:
                            html += f'<td rowspan="{num_items}" style="border:1px solid #333; text-align:right;">{fmt_num(order_sales)}</td>'
                        
                        html += f'<td style="border:1px solid #333; text-align:right;">{fmt_num(unit_cost)}</td>'
                        html += f'<td style="border:1px solid #333; text-align:center;">{pct_cost}</td>'
                        
                        if i == 0:
                            html += f'<td rowspan="{num_items}" style="border:1px solid #333; text-align:right;">{fmt_num(order_fees)}</td>'
                            html += f'<td rowspan="{num_items}" style="border:1px solid #333; text-align:center;">{fmt_pct(order_fees, order_sales)}</td>'
                            html += f'<td rowspan="{num_items}" style="border:1px solid #333; text-align:right;">{fmt_num(order_aff)}</td>'
                            html += f'<td rowspan="{num_items}" style="border:1px solid #333; text-align:center;">{fmt_pct(order_aff, order_sales)}</td>'
                            html += f'<td rowspan="{num_items}" style="border:1px solid #333; text-align:right;">{fmt_num(ops_cost)}</td>'
                            html += f'<td rowspan="{num_items}" style="border:1px solid #333; text-align:center;">{fmt_pct(ops_cost, order_sales)}</td>'
                            html += f'<td rowspan="{num_items}" style="border:1px solid #333; text-align:center;">{settle_date_str}</td>'
                            html += f'<td rowspan="{num_items}" style="border:1px solid #333; text-align:right;">{fmt_num(order_settle)}</td>'
                            html += f'<td rowspan="{num_items}" style="border:1px solid #333; text-align:right; font-weight:bold;">{fmt_num(order_net_profit)}</td>'
                            html += f'<td rowspan="{num_items}" style="border:1px solid #333; text-align:center;">{fmt_pct(order_net_profit, order_sales)}</td>'
                        html += "</tr>"

                html += f"""
                <tr style="background-color: #010538; font-weight: bold;">
                    <td colspan="4" style="text-align: center; padding: 10px; border-top: 2px solid #555;">รวมทั้งหมด</td>
                    <td style="text-align: right; border-top: 2px solid #555;">{fmt_num(sum_sales)}</td>
                    <td colspan="10" style="border-top: 2px solid #555;"></td>
                    <td style="text-align: right; border-top: 2px solid #555;">{fmt_num(sum_net_profit)}</td>
                    <td style="text-align: center; border-top: 2px solid #555;">{fmt_pct(sum_net_profit, sum_sales)}</td>
                </tr>
                """
                html += "</tbody></table>"
                st.markdown(f'<div class="custom-table-wrapper">{html}</div>', unsafe_allow_html=True)
    except Exception as e: st.error(f"Error Details: {e}")

with tab_ads:
    st.header("📢 บันทึกค่าโฆษณา (ADS)")
    col_filters_ads = st.columns([1, 1, 1, 1])
    with col_filters_ads[0]: 
        sel_year_ads = st.selectbox("ปี", [2024, 2025, 2026], index=1, key="ads_year")
    with col_filters_ads[1]: 
        sel_month_ads = st.selectbox("เดือน", thai_months, index=today.month-1, key="ads_month")
    
    try:
        m_idx_ads = thai_months.index(sel_month_ads) + 1
        _, days_ads = calendar.monthrange(sel_year_ads, m_idx_ads)
        d_start_ads = date(sel_year_ads, m_idx_ads, 1)
        d_end_ads = date(sel_year_ads, m_idx_ads, days_ads)
    except:
        d_start_ads = today.replace(day=1); d_end_ads = today

    with col_filters_ads[2]: d_start_ads = st.date_input("วันที่เริ่ม", d_start_ads, key="ads_d_start")
    with col_filters_ads[3]: d_end_ads = st.date_input("ถึงวันที่", d_end_ads, key="ads_d_end")

    try:
        ads_res = supabase.table("daily_ads").select("*").gte("date", str(d_start_ads)).lte("date", str(d_end_ads)).execute()
        db_ads = pd.DataFrame(ads_res.data)
        if not db_ads.empty:
            db_ads['date'] = pd.to_datetime(db_ads['date']).dt.date
            db_ads = db_ads.set_index('date')
    except: db_ads = pd.DataFrame()

    date_range_ads = pd.date_range(start=d_start_ads, end=d_end_ads)
    editor_data = []
    for d in date_range_ads:
        d_date = d.date()
        current_ads = 0.0; current_roas = 0.0
        if not db_ads.empty and d_date in db_ads.index:
            current_ads = float(db_ads.loc[d_date, 'ads_amount'])
            current_roas = float(db_ads.loc[d_date, 'roas_ads'])
        editor_data.append({'วันที่': d_date, 'ค่า ADS': current_ads, 'ROAS ADS': current_roas})

    st.markdown("---")
    col_btn, col_info = st.columns([2, 5])
    with col_btn:
        save_ads_clicked = st.button("💾 บันทึกข้อมูลค่า ADS", type="primary", use_container_width=True)
    with col_info:
        st.info(f"📅 ช่วงวันที่: {d_start_ads.strftime('%d/%m/%Y')} - {d_end_ads.strftime('%d/%m/%Y')}")

    st.markdown("##### 📝 กรอกข้อมูลลงในตารางด้านล่าง")
    edited_df = st.data_editor(pd.DataFrame(editor_data), column_config={"วันที่": st.column_config.DateColumn(format="DD/MM/YYYY", disabled=True), "ค่า ADS": st.column_config.NumberColumn(format="฿%.2f", min_value=0, step=100), "ROAS ADS": st.column_config.NumberColumn(format="%.2f", min_value=0, step=0.1)}, hide_index=True, num_rows="fixed", use_container_width=True, height=1200, key="ads_editor_tab")

    if save_ads_clicked:
        upsert_data = []
        for _, row in edited_df.iterrows():
            upsert_data.append({"date": str(row['วันที่']), "ads_amount": row['ค่า ADS'], "roas_ads": row['ROAS ADS']})
        try:
            supabase.table("daily_ads").upsert(upsert_data).execute()
            st.toast("✅ บันทึกข้อมูลเรียบร้อยแล้ว!", icon="💾")
        except Exception as e: st.error(f"เกิดข้อผิดพลาด: {e}")

with tab_cost:
    st.subheader("💰 จัดการต้นทุน")
    try:
        res = supabase.table("product_costs").select("*").execute()
        cur_data = pd.DataFrame(res.data)
        if cur_data.empty: cur_data = pd.DataFrame(columns=['sku', 'platform', 'unit_cost'])
        display_df = cur_data[['sku', 'unit_cost', 'platform']].copy()
        
        col_c_btn, col_c_info = st.columns([2, 5])
        with col_c_btn: save_cost_clicked = st.button("💾 บันทึกต้นทุนสินค้า", type="primary", use_container_width=True)
        with col_c_info: st.info("สามารถใส่รายการสินค้าทุกแพลตฟอร์มลงในตารางด้านล่างได้เลย")
        
        edited = st.data_editor(display_df, column_config={"sku": st.column_config.TextColumn("รหัสสินค้า (SKU)", required=True), "unit_cost": st.column_config.NumberColumn("ต้นทุน (บาท)", format="%.2f", min_value=0), "platform": st.column_config.TextColumn("แพลตฟอร์ม", disabled=True)}, hide_index=True, num_rows="dynamic", use_container_width=True, height=1000)
        
        if save_cost_clicked:
            if not edited.empty:
                edited['sku'] = edited['sku'].astype(str).str.strip().str.upper()
                supabase.table("product_costs").delete().neq("id", 0).execute()
                supabase.table("product_costs").insert(edited.to_dict('records')).execute()
                st.success("✅ บันทึกต้นทุนสำเร็จ!")
    except Exception as e: st.error(f"Error Cost: {e}")

with tab_old:
    st.subheader("📂 ตารางข้อมูลดิบ (Legacy)")
    try:
        res = supabase.table("orders").select("*").execute()
        if res.data:
            st.dataframe(pd.DataFrame(res.data), use_container_width=True)
        else: st.info("ไม่มีข้อมูล")
    except: pass