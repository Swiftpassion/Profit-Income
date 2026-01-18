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
    """
    แปลงข้อมูลเป็นวันที่ (Date Only) ตัดเวลาทิ้ง
    รองรับ: 27/12/2025 12:32:17 -> 2025-12-27
    """
    if col_name in df.columns:
        # 1. แปลงเป็น String และลบช่องว่าง
        df[col_name] = df[col_name].astype(str).str.strip()
        # 2. จัดการค่าว่าง
        df[col_name] = df[col_name].replace({'nan': None, 'None': None, '': None, 'NaT': None})
        # 3. แปลงเป็น DateTime แล้วตัดเหลือแค่ Date
        # dayfirst=True สำคัญมากสำหรับ Format ไทย (dd/mm/yyyy)
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
    return val_str.replace('.0', '') # Remove decimal if integer

def format_thai_date(d):
    if not d: return "-"
    try:
        # Check if it's already a date object or string
        if isinstance(d, str):
            d = pd.to_datetime(d).date()
        return d.strftime('%d/%m/%Y')
    except: return "-"

def get_standard_status(row):
    try: amt = float(row.get('settlement_amount', 0))
    except: amt = 0
    
    # ถ้ามีเงินเข้า ให้ถือว่าสำเร็จ (แต่ต้องระวังกรณีคืนเงินแล้วยอดเป็นลบ)
    if amt > 0: return "ออเดอร์สำเร็จ"
    
    raw_status = str(row.get('status', '')).lower()
    if any(x in raw_status for x in ['ยกเลิก', 'cancel', 'failed']): return "ยกเลิก"
    if any(x in raw_status for x in ['returned', 'return', 'ตีกลับ', 'refund']): return "ตีกลับ"
    
    # Logic เพิ่มเติมสำหรับการจัดส่งแล้วแต่เงินยังไม่เข้า
    shipped = row.get('shipped_date')
    if shipped and str(shipped) != 'NaT' and str(shipped) != 'None':
        return "รอดำเนินการ" # ส่งของแล้ว รอเงินเข้า
        
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

def find_header_row(data_io, required_keywords):
    """
    สแกน 20 บรรทัดแรก เพื่อหาว่าบรรทัดไหนคือ Header ที่แท้จริง
    โดยบรรทัดนั้นต้องมีคำคีย์เวิร์ดที่ระบุไว้อย่างน้อย 1 คำ (หรือทั้งหมดถ้าจำเป็น)
    """
    data_io.seek(0)
    try:
        # อ่าน 20 บรรทัดแรกแบบไม่ระบุ Header
        preview = pd.read_excel(data_io, header=None, nrows=20, dtype=str)
        
        best_row_idx = 0
        max_matches = 0
        
        # วนลูปเช็คทีละบรรทัด
        for i, row in preview.iterrows():
            # แปลงแถวนั้นเป็นข้อความยาวๆ ตัวพิมพ์เล็ก ตัดเว้นวรรค
            row_text = " ".join([str(x).lower().strip() for x in row.values if pd.notna(x)])
            
            # นับว่าเจอกี่คีย์เวิร์ดในบรรทัดนี้
            matches = 0
            for k in required_keywords:
                if k.lower() in row_text:
                    matches += 1
            
            # ถ้าพบคีย์เวิร์ดเยอะที่สุด ให้จำบรรทัดนี้ไว้
            if matches > max_matches:
                max_matches = matches
                best_row_idx = i
                
        # ถ้าเจอแมตช์บ้าง ให้ใช้บรรทัดนั้น, ถ้าไม่เจอเลย ใช้บรรทัดแรก (0)
        data_io.seek(0)
        return best_row_idx if max_matches > 0 else 0
        
    except Exception:
        data_io.seek(0)
        return 0

def get_col_data(df, candidates):
    """
    ค้นหาคอลัมน์แบบยืดหยุ่น (ตัดเว้นวรรค, ไม่สนตัวพิมพ์เล็กใหญ่, ไม่สน \n)
    """
    # เตรียมชื่อคอลัมน์ในไฟล์ให้เป็น format มาตรฐาน (ตัวเล็ก, ตัด space เกิน, ตัด newline)
    # ตัวอย่าง: "Seller\nSKU " -> "seller sku"
    cols_norm = [" ".join(str(c).replace('\n', ' ').split()).lower() for c in df.columns]
    
    for cand in candidates:
        # เตรียมชื่อที่ต้องการหาให้เป็น format เดียวกัน
        cand_clean = " ".join(cand.split()).lower()
        
        # เทียบหา index
        if cand_clean in cols_norm:
            idx = cols_norm.index(cand_clean)
            # คืนค่าข้อมูลคอลัมน์นั้น (ใช้ iloc เพื่อความชัวร์เรื่อง index)
            return df.iloc[:, idx]
            
    return None

# --- 3. PROCESSORS (แก้ไข process_tiktok โดยเฉพาะ) ---

def process_tiktok(order_files, income_files, shop_name):
    all_orders = []
    
    for f in order_files:
        if 'xlsx' in f['name'].lower() or 'xls' in f['name'].lower():
            try:
                data = download_file(f['id'])
                
                # 1. ค้นหา Header Row แบบเข้มข้น (ต้องเจอทั้ง Order ID และ SKU ถึงจะยอมรับ)
                # เพื่อป้องกันการไปอ่านบรรทัดที่เป็น Title หรือ Description
                header_idx = find_header_row(data, ['Order ID', 'Seller SKU', 'Quantity', 'Product Name'])
                
                # อ่านไฟล์ใหม่เริ่มจากบรรทัดที่หาเจอ
                df = pd.read_excel(data, header=header_idx, dtype=str)
                
                extracted = pd.DataFrame()
                
                # 2. เริ่มดึงข้อมูล (ใช้รายชื่อคอลัมน์จากที่คุณให้มา + ภาษาไทย)
                
                # Order ID
                oid = get_col_data(df, ['Order ID', 'หมายเลขคำสั่งซื้อ', 'Order Serial No.'])
                if oid is None: continue # ถ้าไม่มีเลข Order คือจบ ข้ามไฟล์นี้
                extracted['order_id'] = oid

                # Status
                status = get_col_data(df, ['Order Status', 'สถานะคำสั่งซื้อ', 'Status'])
                extracted['status'] = status if status is not None else 'สำเร็จ'

                # SKU (Seller SKU)
                sku = get_col_data(df, ['Seller SKU', 'รหัสสินค้าของผู้ขาย', 'SKU ID', 'SKU'])
                extracted['sku'] = sku if sku is not None else '-'

                # Product Name
                pname = get_col_data(df, ['Product Name', 'ชื่อสินค้า', 'Product'])
                extracted['product_name'] = pname if pname is not None else '-'

                # Quantity (ระวังเรื่อง Type)
                qty = get_col_data(df, ['Quantity', 'จำนวน', 'Qty'])
                extracted['quantity'] = pd.to_numeric(qty, errors='coerce').fillna(1) if qty is not None else 1

                # Sales Amount (ยอดขาย - เน้นหา SKU Subtotal After Discount ตามที่คุณระบุ)
                # ลำดับการหา: After Discount -> Order Amount -> Unit Price
                sales = get_col_data(df, ['SKU Subtotal After Discount', 'ยอดรวม SKU หลังหักส่วนลด', 'Order Amount', 'ยอดคำสั่งซื้อ', 'Unit Price'])
                extracted['sales_amount'] = pd.to_numeric(sales, errors='coerce').fillna(0) if sales is not None else 0

                # Dates
                c_date = get_col_data(df, ['Created Time', 'เวลาที่สร้าง', 'Order Creation Time'])
                extracted['created_date'] = c_date
                
                s_date = get_col_data(df, ['Shipped Time', 'เวลาจัดส่ง', 'RTS Time'])
                extracted['shipped_date'] = s_date

                # Tracking
                track = get_col_data(df, ['Tracking ID', 'หมายเลขติดตามพัสดุ', 'Tracking Number'])
                extracted['tracking_id'] = track if track is not None else '-'
                
                # ค่าอื่นๆ ที่ไม่มีในไฟล์ Order ให้เป็น 0 (ต้องรอไฟล์ Income หรือคำนวณเอา)
                extracted['settlement_amount'] = 0
                extracted['fees'] = 0
                extracted['affiliate'] = 0 # Affiliate ปกติไม่อยู่ในไฟล์ Order นี้
                
                # Metadata
                extracted['shop_name'] = shop_name
                extracted['platform'] = 'TIKTOK'

                # Cleaning
                extracted = clean_date(extracted, 'created_date')
                extracted = clean_date(extracted, 'shipped_date')
                extracted['order_id'] = extracted['order_id'].apply(clean_scientific_notation)
                extracted = clean_text(extracted, 'sku')
                
                # Check Data Validity: ถ้า Order ID เป็นค่าว่าง ให้ลบทิ้ง
                extracted = extracted[extracted['order_id'].notna() & (extracted['order_id'] != '')]

                all_orders.append(extracted)

            except Exception as e:
                st.error(f"❌ TikTok {f['name']}: {e}")
                continue

    if not all_orders: 
        return pd.DataFrame()
        
    return pd.concat(all_orders, ignore_index=True)

def process_shopee(order_files, income_files, shop_name):
    all_orders = []
    income_dfs = []

    # --- Shopee Income ---
    for f in income_files:
        if any(x in f['name'].lower() for x in ['xls', 'xlsx']):
            try:
                data = download_file(f['id'])
                # Shopee Income มักมี Header แถวๆบรรทัด 5-6
                header_idx = find_header_row(data, ['หมายเลขคำสั่งซื้อ', 'Order ID'])
                df = pd.read_excel(data, sheet_name='Income', header=header_idx, dtype=str)
                
                # ใช้ Smart Search ดึงข้อมูลการเงิน
                inc = pd.DataFrame()
                inc['order_id'] = get_col_data(df, ['หมายเลขคำสั่งซื้อ', 'Order ID'])
                inc['settlement_date'] = get_col_data(df, ['วันที่โอนชำระเงินสำเร็จ', 'Payout Completed Date'])
                inc['settlement_amount'] = pd.to_numeric(get_col_data(df, ['จำนวนเงินทั้งหมดที่โอนแล้ว (฿)', 'Payout Amount']), errors='coerce')
                inc['original_price'] = pd.to_numeric(get_col_data(df, ['สินค้าราคาปกติ', 'Original Price']), errors='coerce')
                inc['affiliate'] = pd.to_numeric(get_col_data(df, ['ค่าคอมมิชชั่น', 'Commission Fee']), errors='coerce') # Check real column name in file
                
                if not inc.empty and 'order_id' in inc.columns:
                    inc['fees'] = (inc['original_price'].fillna(0) - inc['settlement_amount'].fillna(0))
                    inc = clean_date(inc, 'settlement_date')
                    inc['order_id'] = inc['order_id'].apply(clean_scientific_notation)
                    income_dfs.append(inc)
            except: pass
    
    income_master = pd.concat(income_dfs, ignore_index=True).drop_duplicates(subset=['order_id']) if income_dfs else pd.DataFrame()

    # --- Shopee Orders ---
    for f in order_files:
        if any(x in f['name'].lower() for x in ['xls', 'xlsx']):
            try:
                data = download_file(f['id'])
                header_idx = find_header_row(data, ['หมายเลขคำสั่งซื้อ', 'Order ID'])
                df = pd.read_excel(data, header=header_idx, dtype=str)
                
                ext = pd.DataFrame()
                oid = get_col_data(df, ['หมายเลขคำสั่งซื้อ', 'Order ID'])
                if oid is None: continue
                
                ext['order_id'] = oid
                ext['status'] = get_col_data(df, ['สถานะการสั่งซื้อ', 'Order Status'])
                ext['sku'] = get_col_data(df, ['เลขอ้างอิง SKU (SKU Reference No.)', 'SKU Reference No.'])
                ext['quantity'] = pd.to_numeric(get_col_data(df, ['จำนวน', 'Quantity']), errors='coerce').fillna(1)
                ext['sales_amount'] = pd.to_numeric(get_col_data(df, ['ราคาขายสุทธิ', 'Net Price', 'ราคาต่อหน่วย']), errors='coerce').fillna(0)
                ext['tracking_id'] = get_col_data(df, ['หมายเลขติดตามพัสดุ', 'Tracking Number*'])
                ext['created_date'] = get_col_data(df, ['วันที่ทำการสั่งซื้อ', 'Order Creation Date'])
                ext['shipped_date'] = get_col_data(df, ['เวลาการชำระสินค้า', 'Payment Time']) # Shopee ใช้เวลาชำระแทนส่งได้ในบางกรณี
                ext['product_name'] = get_col_data(df, ['ชื่อสินค้า', 'Product Name'])

                ext['shop_name'] = shop_name
                ext['platform'] = 'SHOPEE'
                
                ext = clean_date(ext, 'created_date')
                ext = clean_date(ext, 'shipped_date')
                ext['order_id'] = ext['order_id'].apply(clean_scientific_notation)
                ext = clean_text(ext, 'sku')
                
                all_orders.append(ext)
            except Exception as e:
                st.error(f"❌ Shopee {f['name']}: {e}")

    if not all_orders: return pd.DataFrame()
    final = pd.concat(all_orders, ignore_index=True)
    
    if not income_master.empty:
        return pd.merge(final, income_master, on='order_id', how='left')
    return final

def process_lazada(order_files, income_files, shop_name):
    all_orders = []
    income_dfs = []

    # --- Lazada Income ---
    for f in income_files:
        if 'xlsx' in f['name'].lower():
            try:
                data = download_file(f['id'])
                # Lazada Income มักอยู่ sheet 'Income Overview' หรือแผ่นแรก
                df = pd.read_excel(data, sheet_name=0, dtype=str) # Read first sheet usually
                
                # Check columns existence logic could be added here
                # Assuming standard format for Amount in col 3 is risky, try finding headers
                # Lazada income files are tricky, keep simple aggregation if complex headers
                if len(df.columns) > 3:
                     # Simple heuristics based on common format
                     # Col 0: Order No, Col 2: Date, Col 3: Amount
                     temp = df.iloc[:, [0, 2, 3]].copy()
                     temp.columns = ['order_id', 'settlement_date', 'amount']
                     temp['amount'] = pd.to_numeric(temp['amount'], errors='coerce').fillna(0)
                     income_dfs.append(temp)
            except: pass
    
    income_master = pd.DataFrame()
    if income_dfs:
        raw = pd.concat(income_dfs, ignore_index=True)
        raw['order_id'] = raw['order_id'].apply(clean_scientific_notation)
        income_master = raw.groupby(['order_id']).agg(
            settlement_amount=('amount', 'sum'),
            fees=('amount', lambda x: abs(x[x<0].sum())), # Lazada fees are negative values
            settlement_date=('settlement_date', 'first')
        ).reset_index()
        income_master['affiliate'] = 0

    # --- Lazada Orders ---
    for f in order_files:
        if 'xlsx' in f['name'].lower():
            try:
                data = download_file(f['id'])
                header_idx = find_header_row(data, ['orderNumber', 'Order Item Id', 'หมายเลขคำสั่งซื้อ'])
                df = pd.read_excel(data, header=header_idx, dtype=str)
                
                ext = pd.DataFrame()
                oid = get_col_data(df, ['orderNumber', 'หมายเลขคำสั่งซื้อ'])
                if oid is None: continue
                
                ext['order_id'] = oid
                ext['status'] = get_col_data(df, ['status', 'สถานะ'])
                ext['sku'] = get_col_data(df, ['sellerSku', 'Seller SKU'])
                ext['sales_amount'] = pd.to_numeric(get_col_data(df, ['unitPrice', 'paidPrice']), errors='coerce').fillna(0)
                ext['tracking_id'] = get_col_data(df, ['trackingCode', 'Tracking Code'])
                ext['created_date'] = get_col_data(df, ['createTime', 'Created at'])
                ext['shipped_date'] = get_col_data(df, ['deliveredDate', 'Updated at'])
                ext['product_name'] = get_col_data(df, ['itemName', 'Item Name'])
                
                ext['quantity'] = 1 # Lazada 1 row = 1 item usually
                ext['shop_name'] = shop_name
                ext['platform'] = 'LAZADA'
                
                ext = clean_date(ext, 'created_date')
                ext = clean_date(ext, 'shipped_date')
                ext['order_id'] = ext['order_id'].apply(clean_scientific_notation)
                ext = clean_text(ext, 'sku')
                
                all_orders.append(ext)
            except Exception as e:
                st.error(f"❌ Lazada {f['name']}: {e}")

    if not all_orders: return pd.DataFrame()
    final = pd.concat(all_orders, ignore_index=True)
    
    if not income_master.empty:
        return pd.merge(final, income_master, on='order_id', how='left')
    return final

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
                    # Debug: ตรวจสอบข้อมูลแต่ละแพลตฟอร์มก่อนรวม
                    st.write("🔍 ตรวจสอบข้อมูลแต่ละแพลตฟอร์มก่อนรวม:")
                    for i, df in enumerate(all_data):
                        if not df.empty:
                            platform = df['platform'].iloc[0] if 'platform' in df.columns else 'Unknown'
                            st.write(f"  - แพลตฟอร์ม {platform}: {len(df)} แถว")
                            if platform == 'TIKTOK':
                                st.write("    ตัวอย่างข้อมูล TikTok:")
                                st.write(df.head(3))
                        else:
                            st.write(f"  - ชุดที่ {i+1}: DataFrame ว่างเปล่า")
                    
                    status_box.text("📊 กำลังประมวลผล...")
                    # Combine all data. Note: We do NOT drop duplicates here yet because splitting orders by SKU is needed.
                    master_df = pd.concat(all_data, ignore_index=True)
                    
                    # Numeric Convert
                    for c in ['quantity', 'sales_amount', 'settlement_amount', 'fees', 'affiliate', 'unit_cost']:
                        if c in master_df.columns: master_df[c] = pd.to_numeric(master_df[c], errors='coerce').fillna(0)
                        else: master_df[c] = 0.0

                    # --- PRO-RATE LOGIC (CRITICAL FOR SPLIT ORDERS) ---
                    # เมื่อ Order ID เดียวมีหลาย SKU (หลายบรรทัด) แต่ Income มาเป็นก้อนเดียว
                    # เราต้องกระจายยอด Settlement, Fees, Affiliate ไปตามสัดส่วน Sales Amount ของสินค้านั้นๆ
                    # เพื่อไม่ให้ยอดพวกนี้บวกซ้ำกันจนเกินจริงเมื่อ Sum รวม
                    
                    # 1. หา Total Sales ต่อ Order
                    totals = master_df.groupby('order_id')['sales_amount'].transform('sum')
                    
                    # 2. หา Ratio (ป้องกันหารศูนย์)
                    ratio = master_df['sales_amount'] / totals.replace(0, 1)
                    
                    # 3. คูณ Ratio เข้าไปในยอดที่เป็นก้อนรวม (Settlement, Fees, Affiliate)
                    master_df['settlement_amount'] *= ratio
                    master_df['fees'] *= ratio
                    master_df['affiliate'] *= ratio
                    
                    # Cost Mapping
                    cost_df = load_cost_data()
                    if not cost_df.empty:
                        master_df = pd.merge(master_df, cost_df, on=['sku', 'platform'], how='left')
                        if 'unit_cost_y' in master_df.columns:
                            master_df['unit_cost'] = master_df['unit_cost_y'].fillna(0)
                            master_df = master_df.drop(columns=['unit_cost_x', 'unit_cost_y'], errors='ignore')
                    
                    master_df['unit_cost'] = master_df['unit_cost'].fillna(0)
                    master_df['total_cost'] = master_df['quantity'] * master_df['unit_cost']
                    
                    # Net Profit Calc (Settlement คือยอดรับสุทธิแล้ว จึงลบแค่ต้นทุน)
                    master_df['net_profit'] = master_df['settlement_amount'] - master_df['total_cost']
                    
                    master_df['status'] = master_df.apply(get_standard_status, axis=1)

                    if 'product_name' not in master_df.columns: master_df['product_name'] = "-"
                    master_df['product_name'] = master_df['product_name'].fillna("-")

                    # Date to String for DB
                    for c in ['created_date', 'shipped_date', 'settlement_date']:
                        if c in master_df.columns: 
                            master_df[c] = master_df[c].astype(str).replace({'nan': None, 'None': None, 'NaT': None})
                    
                    # Upload to Database
                    status_box.text("☁️ อัปโหลดขึ้น Database...")
                    cols = ['order_id', 'status', 'sku', 'product_name', 'quantity', 'sales_amount', 'settlement_amount', 'fees', 'affiliate', 'net_profit', 'total_cost', 'unit_cost', 'settlement_date', 'created_date', 'shipped_date', 'tracking_id', 'shop_name', 'platform']
                    master_df = master_df[[c for c in cols if c in master_df.columns]]
                    
                    # Remove Duplicates Last Check (Same Order, Same SKU) - Keep first to avoid weird duplicates
                    master_df = master_df.drop_duplicates(subset=['order_id', 'sku'], keep='first')

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

# --- TAB 1: DASHBOARD (HTML Table) ---
with tab_dash:
    st.header("📊 สรุปยอดขายทุกแพลตฟอร์ม")
    
    # 1. Filters
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

    # Data Processing
    try:
        # A. ดึงข้อมูลออเดอร์
        res = supabase.table("orders").select("*").execute()
        raw_df = pd.DataFrame(res.data)
        
        # B. ดึงข้อมูลค่าโฆษณา
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

        # C. ประมวลผลและรวมตาราง
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
                final_df = step1.copy()
                final_df['manual_ads'] = 0
                final_df['manual_roas'] = 0

            # D. คำนวณ
            calc = final_df.copy()
            calc['total_orders'] = calc['success_count'] + calc['pending_count'] + calc['return_count'] + calc['cancel_count']
            
            # กำไรขั้นต้น = ยอดขาย - ทุน - ค่าธรรมเนียม - ค่าคอม
            calc['กำไร'] = calc['sales_sum'] - calc['cost_sum'] - calc['fees_sum'] - calc['affiliate_sum']
            calc['ADS VAT 7%'] = calc['manual_ads'] * 0.07
            calc['ค่าแอดรวม'] = calc['manual_ads'] + calc['manual_roas'] + calc['ADS VAT 7%']
            
            def safe_div(a, b): return (a/b*100) if b > 0 else 0
            
            calc['ROAS'] = calc.apply(lambda x: (x['sales_sum']/x['ค่าแอดรวม']) if x['ค่าแอดรวม'] > 0 else 0, axis=1)
            calc['ค่าดำเนินการ'] = calc['total_orders'] * 10
            calc['กำไรสุทธิ'] = calc['กำไร'] - calc['ค่าแอดรวม'] - calc['ค่าดำเนินการ']

            # HTML GENERATION
            # ... (ส่วนแสดงผล HTML เหมือนเดิม แต่ข้อมูลจะถูกต้องขึ้นจาก Logic ด้านบน)
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
                if net_profit > 0: 
                    bar_width = min((net_profit / max_profit) * 100, 100)
                
                bar_html = ""
                if bar_width > 0:
                    bar_html = f'<div class="bar-container" style="width: {bar_width}%;"></div>'

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

            # --- TOTAL ROW ---
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

# ... (Tab ADS, Cost, Old ยังคงเหมือนเดิม) ...
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