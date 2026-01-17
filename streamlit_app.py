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

# [เพิ่มใหม่] ฟังก์ชันดึงต้นทุนจาก Supabase
def load_cost_data():
    try:
        response = supabase.table("product_costs").select("sku, platform, unit_cost").execute()
        df = pd.DataFrame(response.data)
        
        if not df.empty:
            df['unit_cost'] = pd.to_numeric(df['unit_cost'], errors='coerce').fillna(0)
            df['platform'] = df['platform'].str.upper().str.strip()
            return df[['sku', 'platform', 'unit_cost']]
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading Cost from DB: {e}")
        return pd.DataFrame()

# [ย้ายมาไว้ตรงนี้] ฟังก์ชันจัดการหน้าต้นทุน
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
                records = edited_df.to_dict(orient='records')
                # ลบข้อมูลเก่าทั้งหมดและลงใหม่ (วิธีง่ายที่สุดสำหรับข้อมูลไม่เยอะ)
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
                
                all_orders.append(df)
    
    if not all_orders: return pd.DataFrame()
    final_df = pd.concat(all_orders, ignore_index=True)
    if not income_master.empty:
        income_master = income_master.groupby('order_id').first().reset_index()
        final_df = pd.merge(final_df, income_master, on='order_id', how='left')
    return final_df

# --- MAIN APP ---
st.title("🛍️ Multi-Platform E-Commerce Dashboard")
tab1, tab2 = st.tabs(["🚀 Sync & Dashboard", "💰 ตั้งค่าต้นทุน (Master Cost)"])

with tab1:
    if st.button("🚀 Sync Data from Google Drive"):
        st.write("🔄 **Start Debugging Process...**") # Debug 1
        
        with st.spinner("Connecting to Google Drive..."):
            # 1. เช็คไฟล์ในโฟลเดอร์หลัก
            root_files = list_files_in_folder(PARENT_FOLDER_ID)
            st.write(f"📂 พบไฟล์/โฟลเดอร์ใน Drive ทั้งหมด: {len(root_files)} รายการ") # Debug 2
            
            if len(root_files) == 0:
                st.error("❌ ไม่พบไฟล์ในโฟลเดอร์หลักเลย เช็ค PARENT_FOLDER_ID หรือสิทธิ์การเข้าถึง")
                st.stop()

            folder_map = {f['name']: f['id'] for f in root_files if f['mimeType'] == 'application/vnd.google-apps.folder'}
            st.write(f"📂 พบโฟลเดอร์ย่อย: {list(folder_map.keys())}") # Debug 3
            
            shops = {
                'TIKTOK': ['TIKTOK 1', 'TIKTOK 2', 'TIKTOK 3'],
                'SHOPEE': ['SHOPEE 1', 'SHOPEE 2', 'SHOPEE 3'],
                'LAZADA': ['LAZADA 1', 'LAZADA 2', 'LAZADA 3']
            }
            income_folders = {'TIKTOK': 'INCOME TIKTOK', 'SHOPEE': 'INCOME SHOPEE', 'LAZADA': 'INCOME LAZADA'}
            
            all_data = []
            
            # 2. เริ่มวนลูปอ่านข้อมูล
            for platform, shop_list in shops.items():
                # st.write(f"กำลังตรวจสอบ Platform: {platform}...") 
                inc_folder_name = income_folders.get(platform)
                inc_files = list_files_in_folder(folder_map.get(inc_folder_name, ''))
                
                for shop_name in shop_list:
                    if shop_name in folder_map:
                        order_files = list_files_in_folder(folder_map[shop_name])
                        
                        # st.write(f"  - ร้าน {shop_name}: พบไฟล์ออเดอร์ {len(order_files)} ไฟล์")
                        
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
                        else:
                            # ถ้าไฟล์มีแต่ดึงไม่ได้ อาจจะเตือนนิดหน่อย
                            if len(order_files) > 0:
                                st.warning(f"  ⚠️ {shop_name}: มีไฟล์แต่ดึงข้อมูลไม่ได้ (เช็ค format ไฟล์)")

            # 3. รวมข้อมูล
            if all_data:
                master_df = pd.concat(all_data, ignore_index=True)
                st.info(f"📊 รวมข้อมูลดิบทั้งหมดได้: {len(master_df)} แถว -> กำลังคำนวณกำไร...") # Debug 4
                
                # --- ส่วนคำนวณ ---
                cost_df = load_cost_data()
                if not cost_df.empty:
                    master_df = pd.merge(master_df, cost_df, on=['sku', 'platform'], how='left')
                else:
                    st.warning("⚠️ ไม่พบข้อมูลต้นทุน (Master Cost) กำไรจะเป็น 0")
                    master_df['unit_cost'] = 0

                # Fill NaNs & Calculate
                for col in ['quantity', 'unit_cost', 'settlement_amount']:
                    if col in master_df.columns:
                        master_df[col] = pd.to_numeric(master_df[col], errors='coerce').fillna(0)
                
                master_df['total_cost'] = master_df.get('quantity', 0) * master_df.get('unit_cost', 0)
                master_df['net_profit'] = master_df.get('settlement_amount', 0) - master_df.get('total_cost', 0)

                # เตรียม Upload
                master_df = master_df.where(pd.notnull(master_df), None)
                for col in ['created_date', 'shipped_date', 'settlement_date']:
                    if col in master_df.columns:
                        master_df[col] = master_df[col].astype(str)

                # 4. Upload ขึ้น Supabase
                st.info("☁️ กำลังอัปโหลดขึ้น Database...")
                records = master_df.to_dict(orient='records')
                
                chunk_size = 500
                total_uploaded = 0
                error_count = 0
                
                progress_bar = st.progress(0)
                
                for i in range(0, len(records), chunk_size):
                    chunk = records[i:i + chunk_size]
                    try:
                        supabase.table("orders").upsert(chunk).execute()
                        total_uploaded += len(chunk)
                    except Exception as e:
                        error_count += 1
                        st.error(f"❌ Upload Error (Chunk {i}): {e}")
                    
                    progress_bar.progress(min((i + chunk_size) / len(records), 1.0))
                
                if error_count == 0:
                    st.success(f"✅ Sync เสร็จสมบูรณ์! อัปโหลดแล้ว {total_uploaded} รายการ")
                    st.rerun()
                else:
                    st.error("⚠️ Sync เสร็จสิ้นแต่มีบางรายการล้มเหลว ลองเช็ค Error ด้านบน")
            else:
                st.error("❌ ไม่พบข้อมูลออเดอร์ที่ใช้ได้เลย (all_data ว่างเปล่า)")
                st.info("คำแนะนำ: ลองเปิดไฟล์ Excel ใน Drive ดูว่ามีข้อมูลไหม หรือชื่อ Sheet ตรงกับโค้ดไหม")

    # [แก้ไข] ย่อหน้าเข้ามา 1 Step (4 เคาะ) เพื่อให้อยู่ใน with tab1:
    st.divider()
    st.subheader("📊 สรุปยอดขาย (Summary)")
    
    try:
        # ดึงข้อมูลจาก Supabase
        response = supabase.table("orders").select("*").execute()
        db_df = pd.DataFrame(response.data)
        
        # --- [ส่วน Debug: แสดงให้เห็นว่าดึงอะไรมาได้บ้าง] ---
        with st.expander("🔍 คลิกเพื่อดูข้อมูลดิบ (Debug Info)"):
            st.write(f"จำนวนแถวที่ดึงได้: {len(db_df)}")
            if not db_df.empty:
                st.write("รายชื่อคอลัมน์ที่มี:", list(db_df.columns))
                st.write("ตัวอย่างข้อมูล 3 แถวแรก:", db_df.head(3))
            else:
                st.warning("⚠️ ตารางว่างเปล่า ไม่มีข้อมูล")
        # ------------------------------------------------
        
        if not db_df.empty:
            # 1. แปลงตัวเลข (ใช้ errors='coerce' เพื่อกัน Error ถ้าข้อมูลไม่ใช่ตัวเลข)
            numeric_cols = {}
            target_cols = ['sales_amount', 'settlement_amount', 'fees', 'affiliate', 'total_cost', 'net_profit']
            
            for col in target_cols:
                # เช็คก่อนว่ามีคอลัมน์นี้ไหม ถ้ามีค่อยแปลง
                if col in db_df.columns:
                    db_df[col] = pd.to_numeric(db_df[col], errors='coerce').fillna(0)
                    numeric_cols[col] = db_df[col]
                else:
                    # ถ้าไม่มี ให้ถือว่าเป็น 0 ไปก่อน (โปรแกรมจะไม่พัง)
                    numeric_cols[col] = pd.Series([0] * len(db_df))

            # 2. แสดงการ์ดตัวเลขสรุป (ใช้ค่าที่เตรียมไว้ใน numeric_cols)
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("ยอดขายรวม", f"{numeric_cols['sales_amount'].sum():,.2f}")
            c2.metric("ยอดเงินเข้าจริง", f"{numeric_cols['settlement_amount'].sum():,.2f}")
            c3.metric("ต้นทุนสินค้า", f"{numeric_cols['total_cost'].sum():,.2f}")
            c4.metric("กำไรสุทธิ", f"{numeric_cols['net_profit'].sum():,.2f}")
            c5.metric("ค่า Affiliate", f"{numeric_cols['affiliate'].sum():,.2f}")
            
            # 3. แสดงกราฟ
            st.write("📈 **ยอดขายแยกตามแพลตฟอร์ม**")
            if 'platform' in db_df.columns and 'sales_amount' in db_df.columns:
                st.bar_chart(db_df.groupby('platform')['sales_amount'].sum())
            else:
                st.info("ไม่พบข้อมูล Platform หรือ ยอดขาย สำหรับสร้างกราฟ")

            # 4. แสดงตารางข้อมูลละเอียด
            st.write("📄 **รายการคำสั่งซื้อทั้งหมด**")
            
            # เลือกเฉพาะคอลัมน์ที่มีอยู่จริง เพื่อป้องกัน Error
            desired_cols = [
                'order_id', 'platform', 'shop_name', 'sku', 
                'sales_amount', 'settlement_amount', 'total_cost', 'net_profit', 'status'
            ]
            final_cols = [c for c in desired_cols if c in db_df.columns]
            
            st.dataframe(
                db_df[final_cols], 
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("ℹ️ ยังไม่มีข้อมูลในระบบ กดปุ่ม Sync ด้านบนเพื่อดึงข้อมูล")
            
    except Exception as e:
        st.error(f"❌ เกิดข้อผิดพลาดในการโหลดข้อมูล: {e}")
        st.info("💡 ข้อแนะนำ: ลองเช็คว่าชื่อตารางใน Supabase ตรงกับ 'orders' หรือไม่")

# ส่วน Tab 2 ต้องถอยกลับมาชิดซ้ายสุด (Level 0) ถูกแล้ว
with tab2:
    manage_costs_page()