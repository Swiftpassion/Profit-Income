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

# Custom CSS สำหรับ HTML Table และ Layout
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Kanit:wght@300;400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Kanit', sans-serif;
    }

    /* สไตล์ตาราง HTML */
    .custom-table-container {
        overflow-x: auto;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-top: 20px;
    }
    
    table.report-table {
        width: 100%;
        border-collapse: collapse;
        min-width: 1500px; /* บังคับความกว้างขั้นต่ำเพื่อให้เลื่อนได้ */
        background-color: white;
    }
    
    table.report-table th {
        background-color: #2c3e50;
        color: white;
        padding: 12px 8px;
        text-align: center;
        font-weight: 500;
        border: 1px solid #34495e;
        position: sticky;
        top: 0;
        z-index: 10;
        white-space: nowrap;
    }
    
    table.report-table td {
        padding: 10px 8px;
        border: 1px solid #ecf0f1;
        color: #2c3e50;
        font-size: 14px;
    }

    table.report-table tr:nth-child(even) {
        background-color: #f8f9fa;
    }
    
    table.report-table tr:hover {
        background-color: #e8f6f3;
        transition: 0.2s;
    }

    /* จัดแนวตัวเลข */
    .num-cell { text-align: right; }
    .text-cell { text-align: center; }
    
    /* Progress Bar ใน HTML */
    .progress-bg {
        background-color: #e0e0e0;
        border-radius: 4px;
        width: 100%;
        height: 8px;
        margin-top: 5px;
    }
    .progress-fill {
        background-color: #27ae60;
        height: 100%;
        border-radius: 4px;
    }
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
    if col_name in df.columns:
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

# --- 3. PROCESSORS (Logic เดิม) ---
# (ลดรูปเพื่อความกระชับ แต่ Logic คงเดิมตามที่คุณต้องการ)
def process_tiktok(order_files, income_files, shop_name):
    all_orders = []
    income_dfs = []
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

    for f in order_files:
        if 'xlsx' in f['name']:
            try:
                data = download_file(f['id'])
                df = pd.read_excel(data, dtype=str)
                if 'Shipped Time' in df.columns:
                    df = df.dropna(subset=['Shipped Time'])
                    df = df[df['Shipped Time'].astype(str).str.strip() != '']
                    cols = {'Order ID':'order_id', 'Order Status':'status', 'Seller SKU':'sku', 'Quantity':'quantity', 
                            'SKU Subtotal After Discount':'sales_amount', 'Created Time':'created_date', 
                            'Shipped Time':'shipped_date', 'Tracking ID':'tracking_id'}
                    df = df[[c for c in cols if c in df.columns]].rename(columns=cols)
                    df['shop_name'] = shop_name; df['platform'] = 'TIKTOK'
                    df = clean_date(df, 'created_date'); df = clean_date(df, 'shipped_date')
                    df['order_id'] = df['order_id'].apply(clean_scientific_notation)
                    all_orders.append(clean_text(df, 'sku'))
            except: pass
    
    if not all_orders: return pd.DataFrame()
    final = pd.concat(all_orders, ignore_index=True).drop_duplicates(subset=['order_id', 'sku'], keep='first')
    return pd.merge(final, income_master, on='order_id', how='left') if not income_master.empty else final

def process_shopee(order_files, income_files, shop_name):
    all_orders = []
    income_dfs = []
    for f in income_files:
        if any(x in f['name'].lower() for x in ['xls', 'csv']):
            try:
                data = download_file(f['id'])
                if 'csv' in f['name'].lower():
                    try: df = pd.read_csv(data, dtype=str, encoding='utf-8')
                    except: data.seek(0); df = pd.read_csv(data, dtype=str, encoding='cp874')
                else: df = pd.read_excel(data, sheet_name='Income', header=5, dtype=str)
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

    for f in order_files:
        if any(x in f['name'].lower() for x in ['xls', 'csv']):
            try:
                data = download_file(f['id'])
                df = pd.DataFrame()
                if 'csv' in f['name'].lower():
                    for enc in ['utf-8', 'cp874', 'utf-8-sig']:
                        try:
                            data.seek(0); temp = pd.read_csv(data, encoding=enc, dtype=str)
                            header = -1
                            if 'หมายเลขคำสั่งซื้อ' in temp.columns: header = 0
                            else:
                                for i, r in temp.head(20).iterrows():
                                    if any('หมายเลขคำสั่งซื้อ' in str(v) for v in r.values): header = i+1; break
                            if header != -1: data.seek(0); df = pd.read_csv(data, encoding=enc, dtype=str, skiprows=header); break
                        except: continue
                else: df = pd.read_excel(data, dtype=str)
                
                if df.empty: continue
                df.columns = df.columns.str.strip()
                if 'เวลาการชำระสินค้า' in df.columns:
                    df = df.dropna(subset=['เวลาการชำระสินค้า'])
                    df = df[df['เวลาการชำระสินค้า'].astype(str).str.strip() != '']
                    cols = {'หมายเลขคำสั่งซื้อ':'order_id', 'สถานะการสั่งซื้อ':'status', 'เวลาการชำระสินค้า':'shipped_date',
                            'เลขอ้างอิง SKU (SKU Reference No.)':'sku', 'จำนวน':'quantity', 'ราคาขายสุทธิ':'sales_amount',
                            '*หมายเลขติดตามพัสดุ':'tracking_id', 'วันที่ทำการสั่งซื้อ':'created_date'}
                    df = df[[c for c in cols if c in df.columns]].rename(columns=cols)
                    df['shop_name'] = shop_name; df['platform'] = 'SHOPEE'
                    df = clean_date(df, 'created_date'); df = clean_date(df, 'shipped_date')
                    df['order_id'] = df['order_id'].apply(clean_scientific_notation)
                    all_orders.append(clean_text(df, 'sku'))
            except: pass

    if not all_orders: return pd.DataFrame()
    final = pd.concat(all_orders, ignore_index=True).drop_duplicates(subset=['order_id', 'sku'], keep='first')
    return pd.merge(final, income_master, on='order_id', how='left') if not income_master.empty else final

def process_lazada(order_files, income_files, shop_name):
    all_orders = []
    income_dfs = []
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

    for f in order_files:
        if 'xlsx' in f['name']:
            try:
                data = download_file(f['id'])
                df = pd.read_excel(data, dtype=str)
                if 'trackingCode' in df.columns:
                    df = df.dropna(subset=['trackingCode'])
                    df = df[df['trackingCode'].astype(str).str.strip() != '']
                    cols = {'orderNumber':'order_id', 'status':'status', 'sellerSku':'sku', 'unitPrice':'sales_amount',
                            'trackingCode':'tracking_id', 'createTime':'created_date', 'deliveredDate':'shipped_date'}
                    df = df[[c for c in cols if c in df.columns]].rename(columns=cols)
                    df['quantity'] = 1; df['shop_name'] = shop_name; df['platform'] = 'LAZADA'
                    df = clean_date(df, 'created_date'); df = clean_date(df, 'shipped_date')
                    df['order_id'] = df['order_id'].apply(clean_scientific_notation)
                    all_orders.append(clean_text(df, 'sku'))
            except: pass

    if not all_orders: return pd.DataFrame()
    final = pd.concat(all_orders, ignore_index=True).drop_duplicates(subset=['order_id', 'sku'], keep='first')
    return pd.merge(final, income_master, on='order_id', how='left') if not income_master.empty else final

# ==========================================
# SIDEBAR: SYNC SYSTEM (ดึงข้อมูล)
# ==========================================
with st.sidebar:
    st.header("🔄 ระบบดึงข้อมูล")
    st.caption("ดึงจาก Google Drive > Database")
    
    with st.expander("🛠️ เครื่องมือ Sync", expanded=True):
        start_sync = st.button("🚀 Sync Data (ล้างเก่าลงใหม่)", type="primary", use_container_width=True)
        debug_mode = st.checkbox("โหมดตรวจสอบ (Debug)")
        
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

                    # Date String
                    for c in ['created_date', 'shipped_date', 'settlement_date']:
                        if c in master_df.columns: master_df[c] = master_df[c].astype(str).replace({'nan': None, 'None': None})
                    
                    # Upload
                    status_box.text("☁️ อัปโหลดขึ้น Database...")
                    cols = ['order_id', 'status', 'sku', 'quantity', 'sales_amount', 'settlement_amount', 'fees', 'affiliate', 'net_profit', 'total_cost', 'unit_cost', 'settlement_date', 'created_date', 'shipped_date', 'tracking_id', 'shop_name', 'platform']
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

# สร้าง Tabs
tab_dash, tab_cost, tab_old = st.tabs(["📊 สรุปยอดขาย (Dashboard)", "💰 จัดการต้นทุน", "📂 ตารางข้อมูลเดิม"])

# --- TAB 1: DASHBOARD (HTML Table) ---
with tab_dash:
    st.header("📊 สรุปยอดขายทุกแพลตฟอร์ม")
    
    # 1. Filters
    col_filters = st.columns([1, 1, 1, 1])
    
    thai_months = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
    today = datetime.datetime.now().date()
    
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

    # 2. Platform Selector
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

    # 3. Process Data
    try:
        res = supabase.table("orders").select("*").execute()
        raw_df = pd.DataFrame(res.data)
        
        if not raw_df.empty:
            raw_df['created_date'] = pd.to_datetime(raw_df['created_date']).dt.date
            mask = (raw_df['created_date'] >= st.session_state.d_start) & (raw_df['created_date'] <= st.session_state.d_end)
            if 'platform' in raw_df.columns: mask &= raw_df['platform'].str.upper().isin(sel_plats)
            df = raw_df.loc[mask].copy()

            for c in ['sales_amount', 'total_cost', 'fees', 'affiliate']:
                if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

            # Group
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
            
            final_df = pd.merge(dates_df, daily, on='created_date', how='left').fillna(0)

            # Ads Input (Small Editor)
            if "ads_data" not in st.session_state: st.session_state.ads_data = {}
            
            editor_data = []
            for _, row in final_df.iterrows():
                d_str = str(row['created_date'])
                saved = st.session_state.ads_data.get(d_str, {'ads': 0.0, 'roas': 0.0})
                editor_data.append({'วันที่': row['created_date'], 'ค่า ADS': saved['ads'], 'ROAS ADS': saved['roas']})
            
            st.markdown("##### 📝 กรอกค่าโฆษณา (Ads)")
            edited_ads = st.data_editor(
                pd.DataFrame(editor_data),
                column_config={
                    "วันที่": st.column_config.DateColumn(format="DD/MM/YYYY", disabled=True),
                    "ค่า ADS": st.column_config.NumberColumn(format="฿%.2f", min_value=0, required=True),
                    "ROAS ADS": st.column_config.NumberColumn(format="฿%.2f", min_value=0, required=True)
                },
                hide_index=True, num_rows="fixed", height=200, use_container_width=True
            )

            # Update Session State
            for _, row in edited_ads.iterrows():
                st.session_state.ads_data[str(row['วันที่'])] = {'ads': row['ค่า ADS'], 'roas': row['ROAS ADS']}

            # Calculate Final
            calc = final_df.copy()
            # Map ads back
            calc['manual_ads'] = calc['created_date'].astype(str).map(lambda x: st.session_state.ads_data.get(x, {}).get('ads', 0))
            calc['manual_roas'] = calc['created_date'].astype(str).map(lambda x: st.session_state.ads_data.get(x, {}).get('roas', 0))

            calc['กำไร'] = calc['sales_sum'] - calc['cost_sum'] - calc['fees_sum'] - calc['affiliate_sum']
            calc['ADS VAT 7%'] = calc['manual_ads'] * 0.07
            calc['ค่าแอดรวม'] = calc['manual_ads'] + calc['manual_roas'] + calc['ADS VAT 7%']
            
            def safe_div(a, b): return (a/b*100) if b > 0 else 0
            
            calc['ROAS'] = calc.apply(lambda x: (x['sales_sum']/x['ค่าแอดรวม']) if x['ค่าแอดรวม'] > 0 else 0, axis=1)
            calc['ค่าดำเนินการ'] = (calc['success_count'] + calc['pending_count'] + calc['return_count'] + calc['cancel_count']) * 10
            calc['กำไรสุทธิ'] = calc['กำไร'] - calc['ค่าแอดรวม'] - calc['ค่าดำเนินการ']

            # Generate HTML Table
            html = """
            <div class="custom-table-container">
            <table class="report-table">
                <thead>
                    <tr>
                        <th style="min-width: 100px;">วันที่</th>
                        <th>สำเร็จ</th><th>รอ</th><th>ตีกลับ</th><th>ยกเลิก</th>
                        <th style="background-color: #2980b9;">ยอดขายรวม</th>
                        <th style="background-color: #2980b9;">ROAS</th>
                        <th>ทุนรวม</th><th>%ทุน</th>
                        <th>ค่าธรรมเนียม</th><th>%ธรรมเนียม</th>
                        <th>Affiliate</th><th>%Aff</th>
                        <th style="background-color: #27ae60;">กำไร</th><th>%กำไร</th>
                        <th style="background-color: #d35400;">ค่า ADS</th>
                        <th style="background-color: #d35400;">ROAS ADS</th>
                        <th style="background-color: #d35400;">VAT 7%</th>
                        <th style="background-color: #c0392b;">ค่าแอดรวม</th><th>%แอด</th>
                        <th>ค่าดำเนินการ</th><th>%ดำเนิน</th>
                        <th style="background-color: #16a085; min-width: 150px;">กำไรสุทธิ</th><th>%สุทธิ</th>
                    </tr>
                </thead>
                <tbody>
            """

            for _, r in calc.iterrows():
                sales = r['sales_sum']
                net_profit = r['กำไรสุทธิ']
                
                # Progress bar logic
                max_profit = calc['กำไรสุทธิ'].max() if calc['กำไรสุทธิ'].max() > 0 else 100
                bar_width = min(max(0, (net_profit / max_profit) * 100), 100)
                
                html += f"""
                <tr>
                    <td class="text-cell">{r['created_date'].strftime('%d %b %Y')}</td>
                    <td class="num-cell">{int(r['success_count'])}</td>
                    <td class="num-cell">{int(r['pending_count'])}</td>
                    <td class="num-cell">{int(r['return_count'])}</td>
                    <td class="num-cell">{int(r['cancel_count'])}</td>
                    <td class="num-cell" style="font-weight:bold;">{sales:,.2f}</td>
                    <td class="num-cell">{r['ROAS']:,.2f}</td>
                    <td class="num-cell">{r['cost_sum']:,.2f}</td>
                    <td class="num-cell">{safe_div(r['cost_sum'], sales):.1f}%</td>
                    <td class="num-cell">{r['fees_sum']:,.2f}</td>
                    <td class="num-cell">{safe_div(r['fees_sum'], sales):.1f}%</td>
                    <td class="num-cell">{r['affiliate_sum']:,.2f}</td>
                    <td class="num-cell">{safe_div(r['affiliate_sum'], sales):.1f}%</td>
                    <td class="num-cell" style="color: green; font-weight:bold;">{r['กำไร']:,.2f}</td>
                    <td class="num-cell">{safe_div(r['กำไร'], sales):.1f}%</td>
                    <td class="num-cell">{r['manual_ads']:,.2f}</td>
                    <td class="num-cell">{r['manual_roas']:,.2f}</td>
                    <td class="num-cell">{r['ADS VAT 7%']:,.2f}</td>
                    <td class="num-cell" style="color: #c0392b;">{r['ค่าแอดรวม']:,.2f}</td>
                    <td class="num-cell">{safe_div(r['ค่าแอดรวม'], sales):.1f}%</td>
                    <td class="num-cell">{r['ค่าดำเนินการ']:,.0f}</td>
                    <td class="num-cell">{safe_div(r['ค่าดำเนินการ'], sales):.1f}%</td>
                    <td class="num-cell" style="font-weight:bold; color: #16a085;">
                        {net_profit:,.2f}
                        <div class="progress-bg"><div class="progress-fill" style="width: {bar_width}%;"></div></div>
                    </td>
                    <td class="num-cell">{safe_div(net_profit, sales):.1f}%</td>
                </tr>
                """
            
            html += "</tbody></table></div>"
            st.markdown(html, unsafe_allow_html=True)

        else: st.info("ไม่พบข้อมูล")
    except Exception as e: st.error(f"Error: {e}")

# --- TAB 2: MASTER COST ---
with tab_cost:
    st.subheader("💰 จัดการต้นทุน (แก้ไขเฉพาะ SKU และ ราคา)")
    try:
        res = supabase.table("product_costs").select("*").execute()
        cur_data = pd.DataFrame(res.data)
        if cur_data.empty: cur_data = pd.DataFrame(columns=['sku', 'platform', 'unit_cost'])
        
        # Show only SKU and Unit Cost for editing, Platform read-only/hidden logic
        # User requested: Show only SKU and Unit Cost
        # But we need Platform to save correctly. I will show Platform as disabled.
        
        edited = st.data_editor(
            cur_data,
            column_config={
                "sku": st.column_config.TextColumn("รหัสสินค้า (SKU)", required=True),
                "unit_cost": st.column_config.NumberColumn("ต้นทุน (บาท)", format="%.2f", min_value=0),
                "platform": st.column_config.TextColumn("แพลตฟอร์ม", disabled=True), # Read-only
                "id": st.column_config.Column(hidden=True),
                "created_at": st.column_config.Column(hidden=True)
            },
            hide_index=True,
            num_rows="dynamic",
            use_container_width=True
        )
        
        if st.button("💾 บันทึกต้นทุนสินค้า"):
            if not edited.empty:
                # Clean
                edited['sku'] = edited['sku'].astype(str).str.strip().str.upper()
                # Save
                data_to_save = edited.to_dict('records')
                # Delete old (truncate logic or upsert) - simpler to delete all except id 0 then insert
                # But here we should be careful. Let's delete all and insert.
                supabase.table("product_costs").delete().neq("id", 0).execute()
                supabase.table("product_costs").insert(data_to_save).execute()
                st.success("บันทึกสำเร็จ!")
                st.rerun()
    except Exception as e: st.error(f"Error Cost: {e}")

# --- TAB 3: OLD TABLE ---
with tab_old:
    st.subheader("📂 ตารางข้อมูลดิบ (Legacy)")
    try:
        res = supabase.table("orders").select("*").execute()
        if res.data:
            old_df = pd.DataFrame(res.data)
            # Display FULL SCREEN height
            st.dataframe(old_df, height=2500, use_container_width=True)
        else:
            st.info("ไม่มีข้อมูล")
    except: pass