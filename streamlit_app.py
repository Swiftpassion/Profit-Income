import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from supabase import create_client, Client
import io
import datetime

# --- CONFIGURATION ---
# ใส่ ID ของโฟลเดอร์แม่ "LAZADA SHOPEE TIKTOK"
PARENT_FOLDER_ID = '1DJp8gpZ8lntH88hXqYuZOwIyFv3NY4Ot' 

# Supabase & Google Auth
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
creds = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"], scopes=SCOPES
)
drive_service = build('drive', 'v3', credentials=creds)

# --- HELPER FUNCTIONS ---
def list_files_in_folder(folder_id):
    query = f"'{folder_id}' in parents and trashed = false"
    results = drive_service.files().list(q=query, fields="files(id, name, mimeType)").execute()
    return results.get('files', [])

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
    df[col_name] = pd.to_datetime(df[col_name], errors='coerce').dt.date
    return df

def clean_scientific_notation(val):
    try:
        return str(int(float(val)))
    except:
        return str(val)

# --- PROCESSOR: TIKTOK ---
def process_tiktok(order_files, income_files, shop_name):
    all_orders = []
    
    # 1. Process Income (หา Affiliate และ Fees)
    income_dfs = []
    for file_info in income_files:
        if 'xlsx' in file_info['name']:
            try:
                f_data = download_file(file_info['id'])
                df = pd.read_excel(f_data, sheet_name='Order details')
                
                # Column Index (0-based):
                # D(3)=Settled Time, F(5)=Settlement Amount, N(13)=Total Fees, Y(24)=Affiliate Commission, AV(47)=Order ID
                # ใช้ iloc เพื่อความแม่นยำ (กันชื่อคอลัมน์เพี้ยน)
                df = df.iloc[:, [47, 5, 3, 13, 24]]
                df.columns = ['order_id', 'settlement_amount', 'settlement_date', 'total_fees', 'affiliate']
                
                df['order_id'] = df['order_id'].apply(str)
                # Clean numbers
                for col in ['total_fees', 'affiliate', 'settlement_amount']:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                
                # สูตร: Real Fees = Total Fees - Affiliate
                df['fees'] = df['total_fees'] - df['affiliate']
                
                income_dfs.append(df[['order_id', 'settlement_amount', 'settlement_date', 'fees', 'affiliate']])
            except Exception as e:
                st.warning(f"TikTok Income Error {file_info['name']}: {e}")

    income_master = pd.DataFrame()
    if income_dfs:
        income_master = pd.concat(income_dfs, ignore_index=True)
        income_master['order_id'] = income_master['order_id'].apply(clean_scientific_notation)
        # Group by Order ID to deduplicate
        income_master = income_master.groupby('order_id').first().reset_index()

    # 2. Process Orders
    for file_info in order_files:
        if 'xlsx' in file_info['name']:
            f_data = download_file(file_info['id'])
            df = pd.read_excel(f_data, dtype=str)
            
            if 'Shipped Time' in df.columns:
                df = df.dropna(subset=['Shipped Time'])
                
                cols_needed = {
                    'Order ID': 'order_id',
                    'Order Status': 'status',
                    'Seller SKU': 'sku',
                    'Quantity': 'quantity',
                    'SKU Subtotal After Discount': 'sales_amount', # ยอดขาย
                    'Created Time': 'created_date',
                    'Shipped Time': 'shipped_date',
                    'Tracking ID': 'tracking_id'
                }
                
                available_cols = [c for c in cols_needed.keys() if c in df.columns]
                df = df[available_cols].rename(columns=cols_needed)
                
                df['shop_name'] = shop_name
                df['platform'] = 'TIKTOK'
                df = clean_date(df, 'created_date')
                df = clean_date(df, 'shipped_date')
                df['order_id'] = df['order_id'].apply(clean_scientific_notation)
                
                all_orders.append(df)

    if not all_orders: return pd.DataFrame()
    final_df = pd.concat(all_orders, ignore_index=True)
    if not income_master.empty:
        final_df = pd.merge(final_df, income_master, on='order_id', how='left')
    return final_df

# --- PROCESSOR: SHOPEE ---
def process_shopee(order_files, income_files, shop_name):
    all_orders = []
    
    # 1. Process Income
    income_dfs = []
    for file_info in income_files:
        if 'xls' in file_info['name']:
            try:
                f_data = download_file(file_info['id'])
                df = pd.read_excel(f_data, sheet_name='Income', header=5, dtype=str)
                
                rename_map = {
                    'หมายเลขคำสั่งซื้อ': 'order_id',
                    'วันที่โอนชำระเงินสำเร็จ': 'settlement_date',
                    'สินค้าราคาปกติ': 'original_price',
                    'ค่าคอมมิชชั่น': 'affiliate', # Col Z
                    'จำนวนเงินทั้งหมดที่โอนแล้ว (฿)': 'settlement_amount'
                }
                
                existing_cols = [c for c in rename_map.keys() if c in df.columns]
                df = df[existing_cols].rename(columns=rename_map)
                
                for col in ['original_price', 'settlement_amount', 'affiliate']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                
                # Logic: Fees = (M - AH) - Affiliate
                if 'original_price' in df.columns and 'settlement_amount' in df.columns:
                    df['raw_fees'] = df['original_price'] - df['settlement_amount']
                    aff_val = df['affiliate'] if 'affiliate' in df.columns else 0
                    df['fees'] = df['raw_fees'] - aff_val
                
                income_dfs.append(df)
            except Exception as e:
                st.warning(f"Shopee Income Error {file_info['name']}: {e}")
            
    income_master = pd.DataFrame()
    if income_dfs:
        income_master = pd.concat(income_dfs, ignore_index=True)
        income_master['order_id'] = income_master['order_id'].apply(clean_scientific_notation)
        cols_to_keep = ['order_id', 'settlement_amount', 'settlement_date', 'fees', 'affiliate']
        cols_to_keep = [c for c in cols_to_keep if c in income_master.columns]
        income_master = income_master[cols_to_keep]

    # 2. Process Orders
    for file_info in order_files:
        if 'xlsx' in file_info['name']:
            f_data = download_file(file_info['id'])
            df = pd.read_excel(f_data, dtype=str)
            
            if 'เวลาการชำระสินค้า' in df.columns:
                df = df.dropna(subset=['เวลาการชำระสินค้า'])
                
                cols_needed = {
                    'หมายเลขคำสั่งซื้อ': 'order_id',
                    'สถานะการสั่งซื้อ': 'status',
                    'เวลาการชำระสินค้า': 'shipped_date',
                    'เลขอ้างอิง SKU (SKU Reference No.)': 'sku',
                    'จำนวน': 'quantity',
                    'ราคาขายสุทธิ': 'sales_amount',
                    '*หมายเลขติดตามพัสดุ': 'tracking_id',
                    'วันที่ทำการสั่งซื้อ': 'created_date'
                }
                
                available_cols = [c for c in cols_needed.keys() if c in df.columns]
                df = df[available_cols].rename(columns=cols_needed)

                df['shop_name'] = shop_name
                df['platform'] = 'SHOPEE'
                df = clean_date(df, 'created_date')
                df = clean_date(df, 'shipped_date')
                df['order_id'] = df['order_id'].apply(clean_scientific_notation)
                
                all_orders.append(df)

    if not all_orders: return pd.DataFrame()
    final_df = pd.concat(all_orders, ignore_index=True)
    if not income_master.empty:
        income_master = income_master.groupby('order_id').first().reset_index()
        final_df = pd.merge(final_df, income_master, on='order_id', how='left')
    return final_df

# --- PROCESSOR: LAZADA ---
def process_lazada(order_files, income_files, shop_name):
    all_orders = []
    
    # 1. Process Income
    income_dfs = []
    for file_info in income_files:
        if 'xlsx' in file_info['name']:
            try:
                f_data = download_file(file_info['id'])
                df = pd.read_excel(f_data, sheet_name='Income Overview', dtype=str)
                
                col_order = 'orderNumber' if 'orderNumber' in df.columns else df.columns[10]
                col_date = 'วันที่ปรับปรุงเข้ายอดของฉัน' if 'วันที่ปรับปรุงเข้ายอดของฉัน' in df.columns else df.columns[2]
                col_amount = df.columns[3] 
                
                df = df[[col_order, col_date, col_amount]]
                df.columns = ['order_id', 'settlement_date', 'amount']
                df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
                
                income_dfs.append(df)
            except Exception as e:
                st.warning(f"Lazada Income Error {file_info['name']}: {e}")

    income_master = pd.DataFrame()
    if income_dfs:
        raw_income = pd.concat(income_dfs, ignore_index=True)
        raw_income['order_id'] = raw_income['order_id'].apply(clean_scientific_notation)
        
        # Logic รวมยอดตาม Order ID
        grouped = raw_income.groupby(['order_id', 'settlement_date']).agg(
            settlement_amount=('amount', lambda x: x[x > 0].sum()),
            fees=('amount', lambda x: x[x < 0].sum())
        ).reset_index()
        
        grouped['affiliate'] = 0 # Lazada ไม่มี Affiliate
        income_master = grouped

    # 2. Process Orders
    for file_info in order_files:
        if 'xlsx' in file_info['name']:
            f_data = download_file(file_info['id'])
            df = pd.read_excel(f_data, dtype=str)
            
            if 'trackingCode' in df.columns:
                df = df.dropna(subset=['trackingCode'])
                
                cols_needed = {
                    'orderNumber': 'order_id',
                    'status': 'status',
                    'sellerSku': 'sku',
                    'unitPrice': 'sales_amount',
                    'trackingCode': 'tracking_id',
                    'createTime': 'created_date',
                    'deliveredDate': 'shipped_date'
                }
                available_cols = [c for c in cols_needed.keys() if c in df.columns]
                df = df[available_cols].rename(columns=cols_needed)
                
                df['quantity'] = 1 
                df['shop_name'] = shop_name
                df['platform'] = 'LAZADA'
                df = clean_date(df, 'created_date')
                df = clean_date(df, 'shipped_date')
                df['order_id'] = df['order_id'].apply(clean_scientific_notation)
                
                all_orders.append(df)
    
    if not all_orders: return pd.DataFrame()
    final_df = pd.concat(all_orders, ignore_index=True)
    if not income_master.empty:
        income_master = income_master.groupby('order_id').first().reset_index()
        final_df = pd.merge(final_df, income_master, on='order_id', how='left')
    return final_df

# --- MAIN APP ---
st.title("🛍️ Multi-Platform E-Commerce Dashboard")

if st.button("🚀 Sync Data from Google Drive"):
    with st.spinner("Connecting to Google Drive..."):
        root_files = list_files_in_folder(PARENT_FOLDER_ID)
        folder_map = {f['name']: f['id'] for f in root_files if f['mimeType'] == 'application/vnd.google-apps.folder'}
        
        shops = {
            'TIKTOK': ['TIKTOK 1', 'TIKTOK 2', 'TIKTOK 3'],
            'SHOPEE': ['SHOPEE 1', 'SHOPEE 2', 'SHOPEE 3'],
            'LAZADA': ['LAZADA 1', 'LAZADA 2', 'LAZADA 3']
        }
        income_folders = {'TIKTOK': 'INCOME TIKTOK', 'SHOPEE': 'INCOME SHOPEE', 'LAZADA': 'INCOME LAZADA'}
        
        all_data = []
        for platform, shop_list in shops.items():
            st.write(f"Processing {platform}...")
            inc_files = list_files_in_folder(folder_map.get(income_folders[platform], ''))
            
            for shop_name in shop_list:
                if shop_name in folder_map:
                    order_files = list_files_in_folder(folder_map[shop_name])
                    df_res = pd.DataFrame()
                    
                    if platform == 'TIKTOK': df_res = process_tiktok(order_files, inc_files, shop_name)
                    elif platform == 'SHOPEE': df_res = process_shopee(order_files, inc_files, shop_name)
                    elif platform == 'LAZADA': df_res = process_lazada(order_files, inc_files, shop_name)
                    
                    if not df_res.empty:
                        all_data.append(df_res)
                        st.success(f"Loaded {len(df_res)} orders from {shop_name}")

        if all_data:
            master_df = pd.concat(all_data, ignore_index=True)
            # ล้างค่า NaN เป็น None (สำคัญ)
            master_df = master_df.where(pd.notnull(master_df), None)
            
            # Clean Dates for JSON
            for col in ['created_date', 'shipped_date', 'settlement_date']:
                if col in master_df.columns:
                    master_df[col] = master_df[col].apply(lambda x: str(x) if x is not None else None)
            
            st.info("Uploading to Database...")
            records = master_df.to_dict(orient='records')
            
            chunk_size = 1000
            for i in range(0, len(records), chunk_size):
                chunk = records[i:i + chunk_size]
                try:
                    supabase.table("orders").upsert(chunk).execute()
                except Exception as e:
                    st.error(f"Upload Error: {e}")
            
            st.success("✅ Data Sync Complete!")
            
            # --- ส่วนแสดงผลตาราง (UI) ภาษาไทย ---
            st.subheader("📋 รายการคำสั่งซื้อล่าสุด")
            
            # เรียงลำดับคอลัมน์และเปลี่ยนชื่อ
            ui_cols = [
                'order_id', 'status', 'sku', 'quantity', 'sales_amount',
                'settlement_amount', 'fees', 'affiliate', 'settlement_date',
                'created_date', 'shipped_date', 'tracking_id', 'shop_name', 'platform'
            ]
            
            thai_names = {
                'order_id': 'เลขคำสั่งซื้อ',
                'status': 'สถานะ',
                'sku': 'รหัสสินค้า',
                'quantity': 'จำนวน',
                'sales_amount': 'ยอดขาย',
                'settlement_amount': 'ยอดเงินที่ได้รับ',
                'fees': 'ค่าธรรมเนียม',
                'affiliate': 'แอฟฟิลิเอต',
                'settlement_date': 'วันที่ได้รับเงิน',
                'created_date': 'วันที่สร้างคำสั่งซื้อ',
                'shipped_date': 'วันที่ทำการสั่งซื้อสำเร็จ',
                'tracking_id': 'เลขพัสดุ',
                'shop_name': 'ชื่อร้าน',
                'platform': 'แพลตฟอร์ม'
            }
            
            display_df = master_df.copy()
            existing_cols = [c for c in ui_cols if c in display_df.columns]
            display_df = display_df[existing_cols].rename(columns=thai_names)
            
            st.dataframe(display_df)
            
        else:
            st.warning("No data found.")

st.divider()
st.subheader("📊 สรุปยอดขาย (Summary)")
try:
    response = supabase.table("orders").select("*").execute()
    db_df = pd.DataFrame(response.data)
    if not db_df.empty:
        # แปลงตัวเลข
        for col in ['sales_amount', 'settlement_amount', 'fees', 'affiliate']:
            if col in db_df.columns:
                db_df[col] = pd.to_numeric(db_df[col], errors='coerce').fillna(0)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("ยอดขายรวม", f"{db_df['sales_amount'].sum():,.2f}")
        c2.metric("ยอดเงินเข้าจริง", f"{db_df['settlement_amount'].sum():,.2f}")
        c3.metric("ค่าธรรมเนียมรวม", f"{db_df['fees'].sum():,.2f}")
        
        aff_sum = db_df['affiliate'].sum() if 'affiliate' in db_df.columns else 0
        c4.metric("ค่า Affiliate", f"{aff_sum:,.2f}")
        
        st.write("ยอดขายแยกตามแพลตฟอร์ม")
        st.bar_chart(db_df.groupby('platform')['sales_amount'].sum())
except:
    st.info("รอข้อมูลจากการ Sync...")