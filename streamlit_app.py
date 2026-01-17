import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from supabase import create_client, Client
import io
import datetime

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

def clean_scientific_notation(val):
    val_str = str(val)
    if 'E' in val_str or 'e' in val_str:
        try:
            return str(int(float(val)))
        except:
            return val_str
    return val_str

def load_cost_data():
    try:
        response = supabase.table("product_costs").select("sku, platform, unit_cost").execute()
        df = pd.DataFrame(response.data)
        
        if not df.empty:
            df['unit_cost'] = pd.to_numeric(df['unit_cost'], errors='coerce').fillna(0)
            df['platform'] = df['platform'].str.upper().str.strip()
            df['sku'] = df['sku'].str.strip()
            df = df.drop_duplicates(subset=['sku', 'platform'], keep='last')
            return df[['sku', 'platform', 'unit_cost']]
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading Cost from DB: {e}")
        return pd.DataFrame()

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
                
                df['order_id'] = df['order_id'].apply(str)
                for col in ['total_fees', 'affiliate', 'settlement_amount']:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                
                df['fees'] = df['total_fees'] - df['affiliate']
                income_dfs.append(df[['order_id', 'settlement_amount', 'settlement_date', 'fees', 'affiliate']])
            except Exception as e:
                st.warning(f"TikTok Income Error {file_info['name']}: {e}")

    income_master = pd.DataFrame()
    if income_dfs:
        income_master = pd.concat(income_dfs, ignore_index=True)
        income_master['order_id'] = income_master['order_id'].apply(clean_scientific_notation)
        # FIX: Use first() instead of groupby to avoid duplicates
        income_master = income_master.drop_duplicates(subset=['order_id'], keep='first')

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
                
                all_orders.append(df)

    if not all_orders: 
        return pd.DataFrame()

    final_df = pd.concat(all_orders, ignore_index=True)
    # FIX: Drop duplicates with specific columns
    final_df = final_df.drop_duplicates(subset=['order_id', 'sku', 'shop_name'])
    
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
                    'ค่าคอมมิชชั่น': 'affiliate',
                    'จำนวนเงินทั้งหมดที่โอนแล้ว (฿)': 'settlement_amount'
                }
                
                existing_cols = [c for c in rename_map.keys() if c in df.columns]
                df = df[existing_cols].rename(columns=rename_map)
                
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
        income_master = income_master.drop_duplicates(subset=['order_id'], keep='first')

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

    if not all_orders: 
        return pd.DataFrame()
    
    final_df = pd.concat(all_orders, ignore_index=True)
    # FIX: Drop duplicates with specific columns
    final_df = final_df.drop_duplicates(subset=['order_id', 'sku', 'shop_name'])

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
        
        # FIX: Use first() to avoid duplicates
        raw_income = raw_income.drop_duplicates(subset=['order_id', 'settlement_date'], keep='first')
        
        grouped = raw_income.groupby(['order_id', 'settlement_date']).agg(
            settlement_amount=('amount', lambda x: x[x > 0].sum()),
            fees=('amount', lambda x: x[x < 0].sum())
        ).reset_index()
        
        grouped['affiliate'] = 0
        income_master = grouped.drop_duplicates(subset=['order_id'], keep='first')

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
    
    if not all_orders: 
        return pd.DataFrame()
    
    final_df = pd.concat(all_orders, ignore_index=True)
    # FIX: Drop duplicates with specific columns
    final_df = final_df.drop_duplicates(subset=['order_id', 'sku', 'shop_name'])

    if not income_master.empty:
        final_df = pd.merge(final_df, income_master, on='order_id', how='left')
    
    return final_df

# --- MAIN APP ---
st.title("🛍️ Multi-Platform E-Commerce Dashboard")
tab1, tab2 = st.tabs(["🚀 Sync & Dashboard", "💰 ตั้งค่าต้นทุน (Master Cost)"])

with tab1:
    if st.button("🚀 Sync Data from Google Drive"):
        st.write("🔄 **Start Debugging Process...**")
        
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
                            st.success(f"  ✅ {shop_name}: ดึงข้อมูลได้ {len(df_res)} รายการ")
            
            # --- 2. รวมและคำนวณ ---
            if all_data:
                master_df = pd.concat(all_data, ignore_index=True)
                # FIX: Final deduplication across all platforms
                master_df = master_df.drop_duplicates(subset=['order_id', 'sku', 'shop_name', 'platform'])
                
                st.info(f"📊 ข้อมูลดิบ: {len(master_df)} แถว -> กำลังประมวลผล...")
                
                # Debug: Show duplicates if any
                duplicate_count = master_df.duplicated(subset=['order_id', 'sku', 'shop_name', 'platform']).sum()
                if duplicate_count > 0:
                    st.warning(f"⚠️ พบข้อมูลซ้ำซ้อน {duplicate_count} แถวหลังจากการล้างซ้ำครั้งแรก")

                # แปลงตัวเลข
                cols_num = ['quantity', 'sales_amount', 'settlement_amount', 'fees', 'affiliate']
                for col in cols_num:
                    if col in master_df.columns:
                        master_df[col] = pd.to_numeric(master_df[col], errors='coerce').fillna(0)
                    else:
                        master_df[col] = 0.0

                # หายอดขายรวมของทั้งออเดอร์
                order_totals = master_df.groupby('order_id')['sales_amount'].transform('sum')
                
                # คำนวณสัดส่วน (Ratio) และเฉลี่ยยอดเงิน
                ratio = master_df['sales_amount'] / order_totals.replace(0, 1)
                
                # เฉลี่ยยอดเงินเข้าตามสัดส่วน
                for col in ['settlement_amount', 'fees', 'affiliate']:
                    if col in master_df.columns:
                        master_df[col] = master_df[col] * ratio

                # บังคับ Lazada Affiliate เป็น 0
                if 'platform' in master_df.columns:
                    master_df.loc[master_df['platform'] == 'LAZADA', 'affiliate'] = 0

                # --- 3. ดึงต้นทุน & คำนวณกำไร ---
                cost_df = load_cost_data()
                if not cost_df.empty:
                    # FIX: Merge properly
                    master_df = pd.merge(
                        master_df, 
                        cost_df, 
                        on=['sku', 'platform'], 
                        how='left'
                    )
                    # Handle duplicate column names
                    if 'unit_cost_x' in master_df.columns and 'unit_cost_y' in master_df.columns:
                        master_df['unit_cost'] = master_df['unit_cost_y'].fillna(0)
                        master_df = master_df.drop(columns=['unit_cost_x', 'unit_cost_y'], errors='ignore')
                else:
                    master_df['unit_cost'] = 0

                master_df['unit_cost'] = master_df['unit_cost'].fillna(0)
                master_df['total_cost'] = master_df['quantity'] * master_df['unit_cost']
                master_df['net_profit'] = master_df['settlement_amount'] - master_df['total_cost']

                # Final cleanup
                master_df = master_df.replace([float('inf'), float('-inf')], 0)
                
                # Format ข้อมูล
                for col in ['created_date', 'shipped_date', 'settlement_date']:
                    if col in master_df.columns:
                        master_df[col] = master_df[col].astype(str).replace({'nan': None, 'None': None})

                # Final deduplication check before upload
                final_duplicates = master_df.duplicated(subset=['order_id', 'sku', 'shop_name', 'platform']).sum()
                if final_duplicates > 0:
                    st.warning(f"⚠️ ยังพบข้อมูลซ้ำ {final_duplicates} แถว จะลบออกก่อนอัปโหลด")
                    master_df = master_df.drop_duplicates(subset=['order_id', 'sku', 'shop_name', 'platform'])
                
                st.info(f"📤 พร้อมอัปโหลด {len(master_df)} แถวที่ไม่ซ้ำกัน")

                # --- 4. UPLOAD ---
                st.warning("⚠️ กำลังล้างข้อมูลเก่าและอัปโหลดข้อมูลใหม่...")
                
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
                    try:
                        supabase.table("orders").insert(chunk).execute()
                        total_uploaded += len(chunk)
                    except Exception as e:
                        error_count += 1
                        st.error(f"❌ Upload Error (Chunk {i}): {e}")
                    
                    progress_bar.progress(min((i + chunk_size) / len(records), 1.0))
                
                if error_count == 0:
                    st.success(f"✅ Sync เสร็จสมบูรณ์! ({total_uploaded} รายการ)")
                    st.rerun()
                else:
                    st.error(f"⚠️ มี {error_count} chunk ที่ล้มเหลว")
            else:
                st.error("❌ ไม่พบข้อมูลออเดอร์ที่ใช้ได้เลย")

    # ส่วนแสดงผลสรุป
    st.divider()
    st.subheader("📊 สรุปยอดขาย (Summary)")
    
    try:
        response = supabase.table("orders").select("*").execute()
        db_df = pd.DataFrame(response.data)
        
        if not db_df.empty:
            st.metric("จำนวนรายการทั้งหมด", f"{len(db_df)}")
            
            # Display table
            col_order = [
                'order_id', 'status', 'sku', 'quantity', 'sales_amount',
                'settlement_amount', 'net_profit', 'total_cost', 'fees',
                'affiliate', 'settlement_date', 'created_date', 'shipped_date',
                'tracking_id', 'shop_name', 'platform'
            ]
            
            rename_map = {
                'order_id': 'เลขคำสั่งซื้อ',
                'status': 'สถานะ',
                'sku': 'รหัสสินค้า',
                'quantity': 'จำนวน',
                'sales_amount': 'ยอดขาย',
                'settlement_amount': 'ยอดเงินที่ได้รับ',
                'net_profit': 'กำไร',
                'total_cost': 'ต้นทุน',
                'fees': 'ค่าธรรมเนียม',
                'affiliate': 'แอฟฟิลิเอต',
                'settlement_date': 'วันที่ได้รับเงิน',
                'created_date': 'วันที่สร้างคำสั่งซื้อ',
                'shipped_date': 'วันที่ทำการสั่งซื้อสำเร็จ',
                'tracking_id': 'เลขพัสดุ',
                'shop_name': 'ชื่อร้าน',
                'platform': 'แพลตฟอร์ม'
            }

            final_cols = [c for c in col_order if c in db_df.columns]
            display_df = db_df[final_cols].rename(columns=rename_map)
            
            st.dataframe(
                display_df, 
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("ℹ️ ยังไม่มีข้อมูลในระบบ กดปุ่ม Sync ด้านบนเพื่อดึงข้อมูล")
            
    except Exception as e:
        st.error(f"❌ เกิดข้อผิดพลาดในการโหลดข้อมูล: {e}")

with tab2:
    manage_costs_page()