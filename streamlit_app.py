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
st.set_page_config(page_title="Dashboard สรุปยอดขายครบวงจร", layout="wide", page_icon="🛍️")

# Custom CSS
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Kanit:wght@300;400;600&display=swap');
    html, body, [class*="css"] { font-family: 'Kanit', sans-serif; }
    .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #dee2e6; }
    div[data-testid="stDataFrameResizable"] { border: 1px solid #e0e0e0; border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

# Supabase & Google Auth
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    drive_service = build('drive', 'v3', credentials=creds)
    PARENT_FOLDER_ID = '1DJp8gpZ8lntH88hXqYuZOwIyFv3NY4Ot' # ID โฟลเดอร์หลักใน Drive
except Exception as e:
    st.error(f"❌ Config Error: {e}")
    st.stop()

# --- 2. HELPER FUNCTIONS (ฟังก์ชันช่วยทำงาน) ---

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
    """แปลงวันที่ให้เป็น YYYY-MM-DD ตัดเวลาทิ้ง"""
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
        try:
            return str(int(float(val)))
        except:
            return val_str
    return val_str

def get_standard_status(row):
    """แปลงสถานะให้เป็นมาตรฐาน"""
    try:
        amt = float(row.get('settlement_amount', 0))
    except:
        amt = 0
    if amt > 0: return "ออเดอร์สำเร็จ"
    
    raw_status = str(row.get('status', '')).lower()
    if any(x in raw_status for x in ['ยกเลิก', 'cancel']): return "ยกเลิก"
    if any(x in raw_status for x in ['package returned', 'return', 'ตีกลับ']): return "ตีกลับ"
    return "รอดำเนินการ"

def load_cost_data():
    """โหลดต้นทุนสินค้า"""
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

# --- 3. PROCESSORS (ตัวอ่านไฟล์แต่ละแพลตฟอร์ม - ฉบับแก้ไขแล้ว) ---

def process_tiktok(order_files, income_files, shop_name):
    all_orders = []
    # Income
    income_dfs = []
    for file_info in income_files:
        if 'xlsx' in file_info['name']:
            try:
                f_data = download_file(file_info['id'])
                df = pd.read_excel(f_data, sheet_name='Order details', dtype=str)
                df = df.iloc[:, [47, 5, 3, 13, 24]]
                df.columns = ['order_id', 'settlement_amount', 'settlement_date', 'total_fees', 'affiliate']
                df['order_id'] = df['order_id'].apply(clean_scientific_notation)
                for col in ['total_fees', 'affiliate', 'settlement_amount']:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                df['fees'] = df['total_fees'] - df['affiliate']
                income_dfs.append(df[['order_id', 'settlement_amount', 'settlement_date', 'fees', 'affiliate']])
            except: pass
    
    income_master = pd.DataFrame()
    if income_dfs:
        income_master = pd.concat(income_dfs, ignore_index=True)
        income_master = income_master.groupby('order_id').first().reset_index()

    # Orders
    for file_info in order_files:
        if 'xlsx' in file_info['name']:
            try:
                f_data = download_file(file_info['id'])
                df = pd.read_excel(f_data, dtype=str)
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
                    df = clean_text(df, 'sku')
                    all_orders.append(df)
            except: pass

    if not all_orders: return pd.DataFrame()
    final_df = pd.concat(all_orders, ignore_index=True)
    if not final_df.empty: final_df = final_df.drop_duplicates(subset=['order_id', 'sku'], keep='first')
    if not income_master.empty: final_df = pd.merge(final_df, income_master, on='order_id', how='left')
    return final_df

def process_shopee(order_files, income_files, shop_name):
    all_orders = []
    # Income
    income_dfs = []
    for file_info in income_files:
        if any(x in file_info['name'].lower() for x in ['xls', 'csv']):
            try:
                f_data = download_file(file_info['id'])
                if 'csv' in file_info['name'].lower():
                    try: df = pd.read_csv(f_data, dtype=str, encoding='utf-8')
                    except: f_data.seek(0); df = pd.read_csv(f_data, dtype=str, encoding='cp874')
                else: df = pd.read_excel(f_data, sheet_name='Income', header=5, dtype=str)
                
                df.columns = df.columns.str.strip()
                rename = {'หมายเลขคำสั่งซื้อ':'order_id', 'วันที่โอนชำระเงินสำเร็จ':'settlement_date', 
                          'สินค้าราคาปกติ':'original_price', 'ค่าคอมมิชชั่น':'affiliate', 'จำนวนเงินทั้งหมดที่โอนแล้ว (฿)':'settlement_amount'}
                df = df[[c for c in rename if c in df.columns]].rename(columns=rename)
                for c in ['original_price', 'settlement_amount', 'affiliate']: 
                    if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
                if 'original_price' in df.columns: 
                    df['fees'] = df['original_price'] - df['settlement_amount'] - df.get('affiliate',0)
                income_dfs.append(df)
            except: pass
            
    income_master = pd.DataFrame()
    if income_dfs:
        income_master = pd.concat(income_dfs, ignore_index=True)
        income_master['order_id'] = income_master['order_id'].apply(clean_scientific_notation)
        cols = [c for c in ['order_id', 'settlement_amount', 'settlement_date', 'fees', 'affiliate'] if c in income_master.columns]
        income_master = income_master[cols].drop_duplicates(subset=['order_id'])

    # Orders (แก้ปัญหาหา Header ไม่เจอ)
    for file_info in order_files:
        if any(x in file_info['name'].lower() for x in ['xls', 'csv']):
            try:
                f_data = download_file(file_info['id'])
                if 'csv' in file_info['name'].lower():
                    for enc in ['utf-8', 'cp874', 'utf-8-sig']:
                        try:
                            f_data.seek(0); temp = pd.read_csv(f_data, encoding=enc, dtype=str)
                            header_row = -1
                            if 'หมายเลขคำสั่งซื้อ' in temp.columns: header_row = 0
                            else:
                                for i, r in temp.head(20).iterrows():
                                    if any('หมายเลขคำสั่งซื้อ' in str(v) for v in r.values): header_row = i+1; break
                            if header_row != -1:
                                f_data.seek(0); df = pd.read_csv(f_data, encoding=enc, dtype=str, skiprows=header_row); break
                        except: continue
                else: df = pd.read_excel(f_data, dtype=str)

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
                    df = clean_text(df, 'sku')
                    all_orders.append(df)
            except: pass

    if not all_orders: return pd.DataFrame()
    final_df = pd.concat(all_orders, ignore_index=True)
    if not final_df.empty: final_df = final_df.drop_duplicates(subset=['order_id', 'sku'], keep='first')
    if not income_master.empty: final_df = pd.merge(final_df, income_master, on='order_id', how='left')
    return final_df

def process_lazada(order_files, income_files, shop_name):
    all_orders = []
    # Income
    income_dfs = []
    for file_info in income_files:
        if 'xlsx' in file_info['name']:
            try:
                f_data = download_file(file_info['id'])
                df = pd.read_excel(f_data, sheet_name='Income Overview', dtype=str)
                col_order = df.columns[0] if 'orderNumber' in df.columns else df.columns[10]
                col_amt = df.columns[3]
                df = df[[col_order, df.columns[2], col_amt]]
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

    # Orders
    for file_info in order_files:
        if 'xlsx' in file_info['name']:
            try:
                f_data = download_file(file_info['id'])
                df = pd.read_excel(f_data, dtype=str)
                if 'trackingCode' in df.columns:
                    df = df.dropna(subset=['trackingCode'])
                    df = df[df['trackingCode'].astype(str).str.strip() != '']
                    cols = {'orderNumber':'order_id', 'status':'status', 'sellerSku':'sku', 'unitPrice':'sales_amount',
                            'trackingCode':'tracking_id', 'createTime':'created_date', 'deliveredDate':'shipped_date'}
                    df = df[[c for c in cols if c in df.columns]].rename(columns=cols)
                    df['quantity'] = 1; df['shop_name'] = shop_name; df['platform'] = 'LAZADA'
                    df = clean_date(df, 'created_date'); df = clean_date(df, 'shipped_date')
                    df['order_id'] = df['order_id'].apply(clean_scientific_notation)
                    df = clean_text(df, 'sku')
                    all_orders.append(df)
            except: pass

    if not all_orders: return pd.DataFrame()
    final_df = pd.concat(all_orders, ignore_index=True)
    if not final_df.empty: final_df = final_df.drop_duplicates(subset=['order_id', 'sku'], keep='first')
    if not income_master.empty: final_df = pd.merge(final_df, income_master, on='order_id', how='left')
    return final_df

# --- 4. MAIN APPLICATION ---

# สร้าง Tabs หลัก
tab1, tab2, tab3 = st.tabs(["🚀 Sync ข้อมูล (หลังบ้าน)", "📊 สรุปยอดขาย & กำไร (หน้าใหม่)", "💰 ตั้งค่าต้นทุน"])

# ==========================================
# TAB 1: SYNC DATA (ระบบหลังบ้าน)
# ==========================================
with tab1:
    st.subheader("🔄 ระบบดึงข้อมูลจาก Google Drive")
    col_sync, col_debug = st.columns([2, 1])
    with col_sync:
        start_sync = st.button("🚀 เริ่มต้น Sync Data (ล้างเก่าลงใหม่)", type="primary")
    with col_debug:
        debug_mode = st.checkbox("โหมดตรวจสอบ (Debug)", value=False)

    if start_sync:
        st.info("⏳ กำลังเชื่อมต่อ Google Drive...")
        root_files = list_files_in_folder(PARENT_FOLDER_ID)
        
        if not root_files:
            st.error("❌ ไม่พบไฟล์ในโฟลเดอร์หลัก")
            st.stop()

        folder_map = {f['name']: f['id'] for f in root_files if f['mimeType'] == 'application/vnd.google-apps.folder'}
        shops = {'TIKTOK': ['TIKTOK 1', 'TIKTOK 2', 'TIKTOK 3'], 'SHOPEE': ['SHOPEE 1', 'SHOPEE 2', 'SHOPEE 3'], 'LAZADA': ['LAZADA 1', 'LAZADA 2', 'LAZADA 3']}
        inc_folders = {'TIKTOK': 'INCOME TIKTOK', 'SHOPEE': 'INCOME SHOPEE', 'LAZADA': 'INCOME LAZADA'}
        
        all_data = []
        progress_text = st.empty()

        for platform, shop_list in shops.items():
            inc_id = folder_map.get(inc_folders.get(platform), '')
            inc_files = list_files_in_folder(inc_id)
            
            for shop_name in shop_list:
                if shop_name in folder_map:
                    progress_text.text(f"กำลังประมวลผล: {shop_name}...")
                    order_files = list_files_in_folder(folder_map[shop_name])
                    
                    df_res = pd.DataFrame()
                    if platform == 'TIKTOK': df_res = process_tiktok(order_files, inc_files, shop_name)
                    elif platform == 'SHOPEE': df_res = process_shopee(order_files, inc_files, shop_name)
                    elif platform == 'LAZADA': df_res = process_lazada(order_files, inc_files, shop_name)

                    if not df_res.empty:
                        all_data.append(df_res)
                        st.success(f"✅ {shop_name}: {len(df_res)} รายการ")
                        if debug_mode: st.dataframe(df_res.head(2))

        if all_data:
            master_df = pd.concat(all_data, ignore_index=True)
            # Deduplicate
            master_df = master_df.drop_duplicates(subset=['order_id', 'sku'], keep='first')
            
            st.info("📊 กำลังคำนวณ Pro-rate และ กำไร...")
            
            # Numeric conversion
            for c in ['quantity', 'sales_amount', 'settlement_amount', 'fees', 'affiliate', 'unit_cost']:
                if c in master_df.columns: master_df[c] = pd.to_numeric(master_df[c], errors='coerce').fillna(0)
                else: master_df[c] = 0.0

            # Pro-rate Logic
            order_totals = master_df.groupby('order_id')['sales_amount'].transform('sum')
            ratio = master_df['sales_amount'] / order_totals.replace(0, 1)
            master_df['settlement_amount'] *= ratio
            master_df['fees'] *= ratio
            master_df['affiliate'] *= ratio
            
            if 'platform' in master_df.columns:
                master_df.loc[master_df['platform'] == 'LAZADA', 'affiliate'] = 0

            # Cost & Profit
            cost_df = load_cost_data()
            if not cost_df.empty:
                master_df = pd.merge(master_df, cost_df, on=['sku', 'platform'], how='left')
                if 'unit_cost_y' in master_df.columns:
                    master_df['unit_cost'] = master_df['unit_cost_y'].fillna(0)
                    master_df = master_df.drop(columns=['unit_cost_x', 'unit_cost_y'], errors='ignore')
            
            master_df['unit_cost'] = master_df['unit_cost'].fillna(0)
            master_df['total_cost'] = master_df['quantity'] * master_df['unit_cost']
            master_df['net_profit'] = master_df['settlement_amount'] - master_df['total_cost']

            # Standard Status
            master_df['status'] = master_df.apply(get_standard_status, axis=1)

            # Date Format & Clean
            for c in ['created_date', 'shipped_date', 'settlement_date']:
                if c in master_df.columns: master_df[c] = master_df[c].astype(str).replace({'nan': None, 'None': None})
            
            valid_cols = ['order_id', 'status', 'sku', 'quantity', 'sales_amount', 'settlement_amount', 'fees', 'affiliate', 
                          'net_profit', 'total_cost', 'unit_cost', 'settlement_date', 'created_date', 'shipped_date', 
                          'tracking_id', 'shop_name', 'platform']
            master_df = master_df[[c for c in valid_cols if c in master_df.columns]]

            # Upload
            st.warning("⚠️ กำลังล้างข้อมูลเก่าและลงใหม่...")
            try: supabase.table("orders").delete().neq("id", 0).execute()
            except: pass
            
            records = master_df.to_dict(orient='records')
            
            # Sanitize NaN/Inf
            clean_records = []
            for r in records:
                new_r = {}
                for k, v in r.items():
                    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)): new_r[k] = 0.0
                    else: new_r[k] = v
                clean_records.append(new_r)

            chunk_size = 500; total = 0
            bar = st.progress(0)
            for i in range(0, len(clean_records), chunk_size):
                chunk = clean_records[i:i+chunk_size]
                try:
                    supabase.table("orders").insert(chunk).execute()
                    total += len(chunk)
                except Exception as e: st.error(f"Error chunk {i}: {e}")
                bar.progress(min((i+chunk_size)/len(clean_records), 1.0))
            
            st.success(f"✅ Sync เสร็จสิ้น! ({total} รายการ)")
            st.rerun()

    # ตารางสรุปแบบเก่า (Backup)
    st.divider()
    if st.checkbox("แสดงตารางสรุปแบบเดิม (Backup)"):
        try:
            res = supabase.table("orders").select("*").execute()
            if res.data:
                st.dataframe(pd.DataFrame(res.data).head(50))
        except: pass

# ==========================================
# TAB 2: DASHBOARD (หน้าใหม่ตามสั่ง)
# ==========================================
with tab2:
    st.header("📊 สรุปยอดขายทุกแพลตฟอร์ม (Detailed Dashboard)")
    
    # 1. Date Filters
    thai_months = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
                   "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
    today = datetime.datetime.now().date()
    all_years = sorted([2024, 2025, 2026], reverse=True)

    def update_dates():
        y = st.session_state.sel_year
        m_str = st.session_state.sel_month
        try:
            m_idx = thai_months.index(m_str) + 1
            _, days = calendar.monthrange(y, m_idx)
            st.session_state.d_start = date(y, m_idx, 1)
            st.session_state.d_end = date(y, m_idx, days)
        except: pass

    if "d_start" not in st.session_state:
        st.session_state.d_start = today.replace(day=1)
        st.session_state.d_end = today

    with st.container():
        st.subheader("🔍 ตัวกรองช่วงเวลา")
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.selectbox("ปี", options=all_years, index=0, key="sel_year", on_change=update_dates)
        with c2: st.selectbox("เดือน", options=thai_months, index=today.month-1, key="sel_month", on_change=update_dates)
        with c3: d_start = st.date_input("วันที่เริ่ม", key="d_start")
        with c4: d_end = st.date_input("ถึงวันที่", key="d_end")

    # 2. Platform Filters
    st.write("🛍️ **เลือกแพลตฟอร์ม**")
    cp1, cp2, cp3, cp4, cp5 = st.columns([1, 1, 1, 1, 6])
    with cp1: all_plat = st.checkbox("✅ ทั้งหมด", value=True)
    with cp2: tiktok_check = st.checkbox("✅ Tiktok", value=all_plat, disabled=all_plat)
    with cp3: shopee_check = st.checkbox("✅ Shopee", value=all_plat, disabled=all_plat)
    with cp4: lazada_check = st.checkbox("✅ Lazada", value=all_plat, disabled=all_plat)

    sel_plats = []
    if all_plat: sel_plats = ['TIKTOK', 'SHOPEE', 'LAZADA']
    else:
        if tiktok_check: sel_plats.append('TIKTOK')
        if shopee_check: sel_plats.append('SHOPEE')
        if lazada_check: sel_plats.append('LAZADA')

    # 3. Data Fetching & Processing
    try:
        res = supabase.table("orders").select("*").execute()
        raw_df = pd.DataFrame(res.data)
        
        if not raw_df.empty:
            # Filter Data
            raw_df['created_date'] = pd.to_datetime(raw_df['created_date']).dt.date
            mask = (raw_df['created_date'] >= d_start) & (raw_df['created_date'] <= d_end)
            if 'platform' in raw_df.columns:
                mask &= raw_df['platform'].str.upper().isin(sel_plats)
            
            df = raw_df.loc[mask].copy()

            # Clean Numbers
            for c in ['sales_amount', 'settlement_amount', 'fees', 'affiliate', 'total_cost']:
                if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

            # Group by Date
            date_range = pd.date_range(start=d_start, end=d_end)
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

            # 4. Ads Input (Session State)
            if "ads_data" not in st.session_state: st.session_state.ads_data = {}
            
            editor_data = []
            for _, row in final_df.iterrows():
                d_str = str(row['created_date'])
                saved = st.session_state.ads_data.get(d_str, {'ads': 0.0, 'roas': 0.0})
                r_dict = row.to_dict()
                r_dict['manual_ads'] = saved['ads']
                r_dict['manual_roas'] = saved['roas']
                editor_data.append(r_dict)
            
            editor_df = pd.DataFrame(editor_data)

            # 5. Data Editor (Input)
            st.markdown("### 📝 กรอกค่า ADS (ช่องสีเหลือง)")
            edited = st.data_editor(
                editor_df,
                column_config={
                    "created_date": st.column_config.DateColumn("วันที่", format="DD MMM YYYY", disabled=True),
                    "sales_sum": st.column_config.NumberColumn("ยอดขาย", format="฿%.2f", disabled=True),
                    "manual_ads": st.column_config.NumberColumn("📢 ค่า ADS", format="฿%.2f", required=True),
                    "manual_roas": st.column_config.NumberColumn("📈 ROAS ADS", format="฿%.2f", required=True),
                },
                use_container_width=True, hide_index=True, key="main_editor",
                column_order=['created_date', 'sales_sum', 'manual_ads', 'manual_roas']
            )

            # Save Input
            for _, row in edited.iterrows():
                st.session_state.ads_data[str(row['created_date'])] = {'ads': row['manual_ads'], 'roas': row['manual_roas']}

            # 6. Final Calculation
            calc = edited.copy()
            def safe_div(a, b): return (a/b*100) if b > 0 else 0

            # Profit Calc
            calc['กำไร'] = calc['sales_sum'] - calc['cost_sum'] - calc['fees_sum'] - calc['affiliate_sum']
            
            # Ads Calc
            calc['ADS VAT 7%'] = calc['manual_ads'] * 0.07
            calc['ค่าแอดรวม'] = calc['manual_ads'] + calc['manual_roas'] + calc['ADS VAT 7%']
            calc['ROAS'] = calc.apply(lambda x: (x['sales_sum']/x['ค่าแอดรวม']) if x['ค่าแอดรวม'] > 0 else 0, axis=1)

            # Net Profit
            ops_count = calc['success_count'] + calc['pending_count'] + calc['return_count'] + calc['cancel_count']
            calc['ค่าดำเนินการ'] = ops_count * 10
            calc['กำไรสุทธิ'] = calc['กำไร'] - calc['ค่าแอดรวม'] - calc['ค่าดำเนินการ']

            # Percentages
            for c in ['cost_sum', 'fees_sum', 'affiliate_sum', 'กำไร', 'ค่าแอดรวม', 'ค่าดำเนินการ', 'กำไรสุทธิ']:
                calc[f'%{c}'] = calc.apply(lambda x: safe_div(x[c], x['sales_sum']), axis=1)

            # 7. Final Table Display
            st.markdown("### 🏁 ตารางผลลัพธ์ (คำนวณอัตโนมัติ)")
            view = calc.rename(columns={
                'created_date':'วันที่', 'success_count':'ออเดอร์สำเร็จ', 'pending_count':'รอดำเนินการ',
                'return_count':'ตีกลับ', 'cancel_count':'ยกเลิก', 'sales_sum':'ยอดขายรวม',
                'cost_sum':'ทุนรวม', '%cost_sum':'%ทุนรวม',
                'fees_sum':'ค่าธรรมเนียม', '%fees_sum':'%ค่าธรรมเนียม',
                'affiliate_sum':'ค่าแอฟฟิลิเอต', '%affiliate_sum':'%ค่าแอฟฟิลิเอต',
                '%กำไร':'%กำไร', 'manual_ads':'ค่าADS', 'manual_roas':'ROAS ADS',
                '%ค่าแอดรวม':'%ค่าแอด', '%ค่าดำเนินการ':'%ค่าดำเนินการ', '%กำไรสุทธิ':'%กำไรสุทธิ'
            })
            
            final_cols = ['วันที่', 'ออเดอร์สำเร็จ', 'รอดำเนินการ', 'ตีกลับ', 'ยกเลิก', 'ยอดขายรวม', 'ROAS',
                          'ทุนรวม', '%ทุนรวม', 'ค่าธรรมเนียม', '%ค่าธรรมเนียม', 'ค่าแอฟฟิลิเอต', '%ค่าแอฟฟิลิเอต',
                          'กำไร', '%กำไร', 'ค่าADS', 'ROAS ADS', 'ADS VAT 7%', 'ค่าแอดรวม', '%ค่าแอด',
                          'ค่าดำเนินการ', '%ค่าดำเนินการ', 'กำไรสุทธิ', '%กำไรสุทธิ']
            
            st.dataframe(
                view[final_cols],
                column_config={
                    "วันที่": st.column_config.DateColumn(format="DD/MM/YYYY"),
                    "ยอดขายรวม": st.column_config.NumberColumn(format="%.2f"),
                    "กำไรสุทธิ": st.column_config.ProgressColumn(format="฿%.2f", min_value=0, max_value=float(view['กำไรสุทธิ'].max()) if not view.empty else 100),
                    **{c: st.column_config.NumberColumn(format="%.2f") for c in final_cols if c not in ['วันที่', 'กำไรสุทธิ']},
                    **{c: st.column_config.NumberColumn(format="%.2f%%") for c in final_cols if '%' in c}
                },
                use_container_width=True, hide_index=True, height=600
            )

        else: st.info("ไม่พบข้อมูลใน Database")
    except Exception as e: st.error(f"Error Loading Dashboard: {e}")

# ==========================================
# TAB 3: COSTS (หน้าตั้งค่าต้นทุน)
# ==========================================
with tab3:
    st.subheader("💰 จัดการต้นทุนสินค้า (Master Cost)")
    try:
        res = supabase.table("product_costs").select("*").execute()
        cur_data = pd.DataFrame(res.data)
        if cur_data.empty: cur_data = pd.DataFrame(columns=['sku', 'platform', 'unit_cost'])
        
        edited = st.data_editor(
            cur_data, num_rows="dynamic", use_container_width=True, hide_index=True, key="cost_edit",
            column_config={
                "unit_cost": st.column_config.NumberColumn("ต้นทุน (บาท)", format="%.2f"),
                "platform": st.column_config.SelectboxColumn("แพลตฟอร์ม", options=["TIKTOK", "SHOPEE", "LAZADA"], required=True),
                "sku": st.column_config.TextColumn("รหัสสินค้า (SKU)", required=True),
            }
        )
        
        if st.button("💾 บันทึกต้นทุน"):
            if not edited.empty:
                edited['sku'] = edited['sku'].astype(str).str.strip().str.upper()
                edited['platform'] = edited['platform'].astype(str).str.strip().str.upper()
                supabase.table("product_costs").delete().neq("id", 0).execute()
                supabase.table("product_costs").insert(edited.to_dict('records')).execute()
                st.success("บันทึกเรียบร้อย!"); st.rerun()
    except Exception as e: st.error(f"Error Cost: {e}")