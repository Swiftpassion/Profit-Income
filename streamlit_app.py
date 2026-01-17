import streamlit as st
import pandas as pd
import numpy as np
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from supabase import create_client, Client
import io
import datetime
import math

# --- CONFIGURATION ---
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

def clean_text(df, col_name):
    """Cleans text columns by converting to string, stripping whitespace, and uppercasing."""
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

# [Function] Load Cost Data
def load_cost_data():
    try:
        response = supabase.table("product_costs").select("sku, platform, unit_cost").execute()
        df = pd.DataFrame(response.data)
        
        if not df.empty:
            df['unit_cost'] = pd.to_numeric(df['unit_cost'], errors='coerce').fillna(0)
            df['platform'] = df['platform'].str.upper().str.strip()
            df = clean_text(df, 'sku') 
            return df[['sku', 'platform', 'unit_cost']]
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading Cost from DB: {e}")
        return pd.DataFrame()

# [Function] Manage Costs Page
def manage_costs_page():
    st.subheader("💰 จัดการต้นทุนสินค้า (Master Cost)")

    try:
        response = supabase.table("product_costs").select("*").execute()
        current_data = pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"โหลดข้อมูลไม่สำเร็จ: {e}")
        current_data = pd.DataFrame()

    if current_data.empty:
        current_data = pd.DataFrame(columns=['sku', 'platform', 'unit_cost'])

    # Data Editor
    edited_df = st.data_editor(
        current_data,
        num_rows="dynamic",
        column_config={
            "unit_cost": st.column_config.NumberColumn("ต้นทุน (บาท)", min_value=0, format="%.2f"),
            "platform": st.column_config.SelectboxColumn("แพลตฟอร์ม", options=["TIKTOK", "SHOPEE", "LAZADA"], required=True),
            "sku": st.column_config.TextColumn("รหัสสินค้า (SKU)", required=True),
        },
        use_container_width=True,
        hide_index=True,
        key="cost_editor"
    )

    if st.button("💾 บันทึกการเปลี่ยนแปลงต้นทุน"):
        try:
            if not edited_df.empty:
                # Clean data before saving
                edited_df['sku'] = edited_df['sku'].astype(str).str.strip().str.upper()
                edited_df['platform'] = edited_df['platform'].astype(str).str.strip().str.upper()
                
                records = edited_df.to_dict(orient='records')
                supabase.table("product_costs").delete().neq("id", 0).execute()
                supabase.table("product_costs").insert(records).execute()
                st.success("✅ บันทึกต้นทุนเรียบร้อยแล้ว!")
                st.rerun()
            else:
                st.warning("ตารางว่างเปล่า ไม่มีการบันทึก")
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดในการบันทึก: {e}")

# --- PROCESSOR: TIKTOK ---
def process_tiktok(order_files, income_files, shop_name):
    all_orders = []
    
    # 1. Process Income
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
            except Exception as e:
                st.warning(f"TikTok Income Error {file_info['name']}: {e}")

    income_master = pd.DataFrame()
    if income_dfs:
        income_master = pd.concat(income_dfs, ignore_index=True)
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
                    'SKU Subtotal After Discount': 'sales_amount',
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
                df = clean_text(df, 'sku') 
                
                all_orders.append(df)

    if not all_orders: return pd.DataFrame()
    final_df = pd.concat(all_orders, ignore_index=True)

    if not final_df.empty:
        final_df = final_df.drop_duplicates(subset=['order_id', 'sku'], keep='first')
    
    if not income_master.empty:
        final_df = pd.merge(final_df, income_master, on='order_id', how='left')
    return final_df

# --- PROCESSOR: SHOPEE ---
def process_shopee(order_files, income_files, shop_name):
    all_orders = []
    
    # ==========================================
    # 1. Process Income Files (CSV & Excel)
    # ==========================================
    income_dfs = []
    for file_info in income_files:
        # Check for Excel (.xls, .xlsx) and CSV
        if any(ext in file_info['name'].lower() for ext in ['xls', 'csv']):
            try:
                f_data = download_file(file_info['id'])
                
                # A. Loader Logic: CSV vs Excel
                if 'csv' in file_info['name'].lower():
                    # CSVs are usually raw text without header offset
                    df = pd.read_csv(f_data, dtype=str)
                else:
                    # Excel reports usually have 5 header rows of metadata
                    df = pd.read_excel(f_data, sheet_name='Income', header=5, dtype=str)
                
                # B. Rename Columns
                rename_map = {
                    'หมายเลขคำสั่งซื้อ': 'order_id',
                    'วันที่โอนชำระเงินสำเร็จ': 'settlement_date',
                    'สินค้าราคาปกติ': 'original_price',
                    'ค่าคอมมิชชั่น': 'affiliate',
                    'จำนวนเงินทั้งหมดที่โอนแล้ว (฿)': 'settlement_amount'
                }
                
                existing_cols = [c for c in rename_map.keys() if c in df.columns]
                df = df[existing_cols].rename(columns=rename_map)
                
                # C. Calculate Fees
                for col in ['original_price', 'settlement_amount', 'affiliate']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                
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
        
        # [CRITICAL FIX] Filter columns strictly to avoid 'original_price' DB error
        cols_to_keep = ['order_id', 'settlement_amount', 'settlement_date', 'fees', 'affiliate']
        cols_to_keep = [c for c in cols_to_keep if c in income_master.columns]
        income_master = income_master[cols_to_keep] 
        
        # Deduplicate Income (One row per Order ID)
        income_master = income_master.drop_duplicates(subset=['order_id'])

    # ==========================================
    # 2. Process Order Files
    # ==========================================
    for file_info in order_files:
        # Support both .xls and .xlsx for Orders
        if any(ext in file_info['name'].lower() for ext in ['xls', 'csv']):
            try:
                f_data = download_file(file_info['id'])
                
                # Load Data
                if 'csv' in file_info['name'].lower():
                    df = pd.read_csv(f_data, dtype=str)
                else:
                    df = pd.read_excel(f_data, dtype=str)
                
                # Filter valid rows
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
                    
                    # Clean Data
                    df = clean_date(df, 'created_date')
                    df = clean_date(df, 'shipped_date')
                    df['order_id'] = df['order_id'].apply(clean_scientific_notation)
                    df = clean_text(df, 'sku') 
                    
                    all_orders.append(df)
            except Exception as e:
                st.warning(f"Shopee Order Error {file_info['name']}: {e}")

    if not all_orders: return pd.DataFrame()
    final_df = pd.concat(all_orders, ignore_index=True)
    
    # [CRITICAL FIX] Strict Deduplication for Orders (Order ID + SKU)
    if not final_df.empty:
        final_df = final_df.drop_duplicates(subset=['order_id', 'sku'], keep='first')

    # ==========================================
    # 3. Merge Income & Return
    # ==========================================
    if not income_master.empty:
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
        
        grouped = raw_income.groupby(['order_id', 'settlement_date']).agg(
            settlement_amount=('amount', lambda x: x[x > 0].sum()),
            fees=('amount', lambda x: x[x < 0].sum())
        ).reset_index()
        
        grouped['affiliate'] = 0
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
                df = clean_text(df, 'sku') 
                
                all_orders.append(df)
    
    if not all_orders: return pd.DataFrame()
    final_df = pd.concat(all_orders, ignore_index=True)
    
    if not final_df.empty:
        final_df = final_df.drop_duplicates(subset=['order_id', 'sku'], keep='first')

    if not income_master.empty:
        income_master = income_master.groupby('order_id').first().reset_index()
        final_df = pd.merge(final_df, income_master, on='order_id', how='left')
    return final_df

# --- MAIN APP ---
st.title("🛍️ Multi-Platform E-Commerce Dashboard")
tab1, tab2 = st.tabs(["🚀 Sync & Dashboard", "💰 ตั้งค่าต้นทุน (Master Cost)"])

with tab1:
    col_sync, col_debug = st.columns([2, 1])
    with col_sync:
        start_sync = st.button("🚀 Sync Data from Google Drive")
    with col_debug:
        debug_mode = st.checkbox("🐞 Enable Debug Mode (Show raw data)")

    if start_sync:
        st.write("🔄 **Starting Sync Process...**")
        
        with st.spinner("Connecting to Google Drive..."):
            root_files = list_files_in_folder(PARENT_FOLDER_ID)
            
            if len(root_files) == 0:
                st.error("❌ ไม่พบไฟล์ในโฟลเดอร์หลักเลย เช็ค PARENT_FOLDER_ID หรือสิทธิ์การเข้าถึง")
                st.stop()

            folder_map = {f['name']: f['id'] for f in root_files if f['mimeType'] == 'application/vnd.google-apps.folder'}
            
            shops = {
                'TIKTOK': ['TIKTOK 1', 'TIKTOK 2', 'TIKTOK 3'],
                'SHOPEE': ['SHOPEE 1', 'SHOPEE 2', 'SHOPEE 3'],
                'LAZADA': ['LAZADA 1', 'LAZADA 2', 'LAZADA 3']
            }
            income_folders = {'TIKTOK': 'INCOME TIKTOK', 'SHOPEE': 'INCOME SHOPEE', 'LAZADA': 'INCOME LAZADA'}
            
            all_data = []
            
            # --- 1. Loop อ่านข้อมูล ---
            for platform, shop_list in shops.items():
                inc_folder_name = income_folders.get(platform)
                inc_files = list_files_in_folder(folder_map.get(inc_folder_name, ''))
                
                for shop_name in shop_list:
                    if shop_name in folder_map:
                        order_files = list_files_in_folder(folder_map[shop_name])
                        
                        df_res = pd.DataFrame()
                        try:
                            if platform == 'TIKTOK': df_res = process_tiktok(order_files, inc_files, shop_name)
                            elif platform == 'SHOPEE': df_res = process_shopee(order_files, inc_files, shop_name)
                            elif platform == 'LAZADA': df_res = process_lazada(order_files, inc_files, shop_name)
                        except Exception as e:
                            st.error(f"  ❌ Error processing {shop_name}: {e}")

                        if not df_res.empty:
                            all_data.append(df_res)
                            st.success(f"  ✅ {shop_name}: {len(df_res)} รายการ")
                            
                            if debug_mode:
                                st.caption(f"🐞 Debug {shop_name}: Sample Data")
                                st.dataframe(df_res.head(3), use_container_width=True)

            # --- 2. รวมและคำนวณ ---
            if all_data:
                master_df = pd.concat(all_data, ignore_index=True)
                
                # Deduplication
                before_dedup = len(master_df)
                master_df = master_df.drop_duplicates(subset=['order_id', 'sku'], keep='first')
                after_dedup = len(master_df)
                
                if before_dedup > after_dedup:
                    st.warning(f"🧹 Removed {before_dedup - after_dedup} duplicated rows.")

                st.info(f"📊 ข้อมูลสุทธิ: {len(master_df)} แถว -> กำลังประมวลผล...")

                # แปลงตัวเลข
                cols_num = ['quantity', 'sales_amount', 'settlement_amount', 'fees', 'affiliate', 'unit_cost']
                for col in cols_num:
                    if col in master_df.columns:
                        master_df[col] = pd.to_numeric(master_df[col], errors='coerce').fillna(0)
                    else:
                        master_df[col] = 0.0

                # -------------------------------------------------------------
                # [Logic Pro-rate]
                # -------------------------------------------------------------
                order_totals = master_df.groupby('order_id')['sales_amount'].transform('sum')
                ratio = master_df['sales_amount'] / order_totals.replace(0, 1)
                
                master_df['settlement_amount'] = master_df['settlement_amount'] * ratio
                master_df['fees'] = master_df['fees'] * ratio
                master_df['affiliate'] = master_df['affiliate'] * ratio
                
                if 'platform' in master_df.columns:
                    master_df.loc[master_df['platform'] == 'LAZADA', 'affiliate'] = 0

                # --- 3. ดึงต้นทุน & คำนวณกำไร ---
                cost_df = load_cost_data()
                if not cost_df.empty:
                    master_df = pd.merge(master_df, cost_df, on=['sku', 'platform'], how='left')
                    if 'unit_cost_y' in master_df.columns:
                        master_df['unit_cost'] = master_df['unit_cost_y'].fillna(0)
                        master_df = master_df.drop(columns=['unit_cost_x', 'unit_cost_y'], errors='ignore')
                else:
                    master_df['unit_cost'] = 0

                master_df['unit_cost'] = master_df['unit_cost'].fillna(0)
                master_df['total_cost'] = master_df['quantity'] * master_df['unit_cost']
                master_df['net_profit'] = master_df['settlement_amount'] - master_df['total_cost']

                # Format Date
                for col in ['created_date', 'shipped_date', 'settlement_date']:
                    if col in master_df.columns:
                        master_df[col] = master_df[col].astype(str).replace({'nan': None, 'None': None})

                # --- [IMPORTANT FIX] FILTER ONLY DB COLUMNS ---
                # This explicitly selects only columns that exist in the DB Schema
                # to prevent errors like "Could not find 'original_price' column"
                valid_db_columns = [
                    'order_id', 'status', 'sku', 'quantity', 'sales_amount', 
                    'settlement_amount', 'fees', 'affiliate', 'net_profit', 
                    'total_cost', 'unit_cost', 'settlement_date', 
                    'created_date', 'shipped_date', 'tracking_id', 
                    'shop_name', 'platform'
                ]
                
                # Keep only allowed columns
                final_upload_cols = [c for c in valid_db_columns if c in master_df.columns]
                master_df = master_df[final_upload_cols]

                # --- 4. UPLOAD ---
                st.warning("⚠️ กำลังล้างข้อมูลเก่าทั้งหมดใน Database และลงข้อมูลใหม่...")
                
                try:
                    supabase.table("orders").delete().neq("id", 0).execute()
                except Exception as e:
                    st.error(f"ลบข้อมูลเก่าไม่สำเร็จ: {e}")

                st.info("☁️ กำลังอัปโหลดข้อมูลใหม่...")
                records = master_df.to_dict(orient='records')
                
                chunk_size = 500
                total_uploaded = 0
                error_count = 0
                progress_bar = st.progress(0)
                
                for i in range(0, len(records), chunk_size):
                    chunk = records[i:i + chunk_size]
                    
                    # Sanitize chunk (NaN/Infinity fix)
                    clean_chunk = []
                    for row in chunk:
                        clean_row = {}
                        for k, v in row.items():
                            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                                clean_row[k] = 0.0
                            else:
                                clean_row[k] = v
                        clean_chunk.append(clean_row)

                    try:
                        supabase.table("orders").insert(clean_chunk).execute()
                        total_uploaded += len(clean_chunk)
                    except Exception as e:
                        error_count += 1
                        st.error(f"❌ Upload Error (Chunk {i}): {e}")
                    
                    progress_bar.progress(min((i + chunk_size) / len(records), 1.0))
                
                if error_count == 0:
                    st.success(f"✅ Sync เสร็จสมบูรณ์! ({total_uploaded} รายการ)")
                    st.rerun()
                else:
                    st.error("⚠️ มีบางรายการล้มเหลว")
            else:
                st.error("❌ ไม่พบข้อมูลออเดอร์ที่ใช้ได้เลย")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    st.divider()
    st.subheader("📊 สรุปยอดขาย (Summary)")
    
    try:
        response = supabase.table("orders").select("*").execute()
        db_df = pd.DataFrame(response.data)
        
        if not db_df.empty:
            target_cols = ['sales_amount', 'settlement_amount', 'fees', 'affiliate', 'total_cost', 'net_profit', 'quantity']
            
            numeric_vals = {}
            for col in target_cols:
                if col in db_df.columns:
                    db_df[col] = pd.to_numeric(db_df[col], errors='coerce').fillna(0)
                    numeric_vals[col] = db_df[col].sum()
                else:
                    numeric_vals[col] = 0

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("ยอดขายรวม", f"{numeric_vals['sales_amount']:,.2f}")
            c2.metric("ยอดเงินที่ได้รับ", f"{numeric_vals['settlement_amount']:,.2f}")
            c3.metric("ต้นทุนรวม", f"{numeric_vals['total_cost']:,.2f}")
            c4.metric("กำไรสุทธิ", f"{numeric_vals['net_profit']:,.2f}")
            c5.metric("ค่า Affiliate", f"{numeric_vals['affiliate']:,.2f}")

            st.write("📄 **รายการคำสั่งซื้อทั้งหมด**")
            
            col_order = [
                'order_id', 'status', 'sku', 'quantity', 'sales_amount', 
                'settlement_amount', 'net_profit', 'total_cost', 'fees', 'affiliate', 
                'settlement_date', 'created_date', 'shipped_date', 
                'tracking_id', 'shop_name', 'platform'
            ]
            
            rename_map = {
                'order_id': 'เลขคำสั่งซื้อ', 'status': 'สถานะ', 'sku': 'รหัสสินค้า',
                'quantity': 'จำนวน', 'sales_amount': 'ยอดขาย', 'settlement_amount': 'ยอดเงินที่ได้รับ',
                'net_profit': 'กำไร', 'total_cost': 'ต้นทุน', 'fees': 'ค่าธรรมเนียม',
                'affiliate': 'แอฟฟิลิเอต', 'settlement_date': 'วันที่ได้รับเงิน',
                'created_date': 'วันที่สร้างคำสั่งซื้อ', 'shipped_date': 'วันที่ทำการสั่งซื้อสำเร็จ',
                'tracking_id': 'เลขพัสดุ', 'shop_name': 'ชื่อร้าน', 'platform': 'แพลตฟอร์ม'
            }

            final_cols = [c for c in col_order if c in db_df.columns]
            display_df = db_df[final_cols].rename(columns=rename_map)
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            st.info("ℹ️ ยังไม่มีข้อมูลในระบบ กดปุ่ม Sync ด้านบนเพื่อดึงข้อมูล")
            
    except Exception as e:
        st.error(f"❌ เกิดข้อผิดพลาดในการโหลดข้อมูล: {e}")

with tab2:
    manage_costs_page()