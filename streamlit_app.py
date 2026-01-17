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
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    drive_service = build('drive', 'v3', credentials=creds)
except Exception as e:
    st.error(f"⚠️ Connection Error: {e}")
    st.stop()

# --- HELPER FUNCTIONS ---
def list_files_in_folder(folder_id):
    try:
        query = f"'{folder_id}' in parents and trashed = false"
        results = drive_service.files().list(q=query, fields="files(id, name, mimeType)").execute()
        return results.get('files', [])
    except:
        return []

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
            return df[['sku', 'platform', 'unit_cost']]
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading Cost: {e}")
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
        if not edited_df.empty:
            try:
                records = edited_df.to_dict(orient='records')
                # หมายเหตุ: ถ้าข้อมูลเยอะมาก การลบแล้วลงใหม่ทั้งหมดอาจช้าได้ แต่ปลอดภัยสำหรับข้อมูลน้อย
                supabase.table("product_costs").delete().neq("id", 0).execute()
                supabase.table("product_costs").insert(records).execute()
                st.success("✅ บันทึกต้นทุนเรียบร้อยแล้ว!")
                st.rerun()
            except Exception as e:
                st.error(f"Error Saving: {e}")

# --- PROCESSORS ---
def process_tiktok(order_files, income_files, shop_name):
    all_orders = []
    income_master = pd.DataFrame()
    
    # Income
    income_dfs = []
    for file_info in income_files:
        if 'xlsx' in file_info['name']:
            try:
                f_data = download_file(file_info['id'])
                df = pd.read_excel(f_data, sheet_name='Order details', dtype=str)
                df = df.iloc[:, [47, 5, 3, 13, 24]]
                df.columns = ['order_id', 'settlement_amount', 'settlement_date', 'total_fees', 'affiliate']
                for col in ['total_fees', 'affiliate', 'settlement_amount']:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                df['fees'] = df['total_fees'] - df['affiliate']
                income_dfs.append(df[['order_id', 'settlement_amount', 'settlement_date', 'fees', 'affiliate']])
            except: pass
    if income_dfs:
        income_master = pd.concat(income_dfs, ignore_index=True)
        income_master['order_id'] = income_master['order_id'].apply(clean_scientific_notation)
        income_master = income_master.groupby('order_id').first().reset_index()

    # Orders
    for file_info in order_files:
        if 'xlsx' in file_info['name']:
            try:
                f_data = download_file(file_info['id'])
                df = pd.read_excel(f_data, dtype=str)
                if 'Shipped Time' in df.columns:
                    df = df.dropna(subset=['Shipped Time'])
                    cols = {'Order ID':'order_id', 'Order Status':'status', 'Seller SKU':'sku', 
                            'Quantity':'quantity', 'SKU Subtotal After Discount':'sales_amount', 
                            'Created Time':'created_date', 'Shipped Time':'shipped_date', 'Tracking ID':'tracking_id'}
                    df = df[[c for c in cols if c in df.columns]].rename(columns=cols)
                    df['shop_name'] = shop_name
                    df['platform'] = 'TIKTOK'
                    df = clean_date(df, 'created_date')
                    df = clean_date(df, 'shipped_date')
                    df['order_id'] = df['order_id'].apply(clean_scientific_notation)
                    all_orders.append(df)
            except: pass

    if not all_orders: return pd.DataFrame()
    final_df = pd.concat(all_orders, ignore_index=True)
    if not income_master.empty:
        final_df = pd.merge(final_df, income_master, on='order_id', how='left')
    return final_df

def process_shopee(order_files, income_files, shop_name):
    all_orders = []
    income_master = pd.DataFrame()
    
    # Income
    income_dfs = []
    for file_info in income_files:
        if 'xls' in file_info['name']:
            try:
                f_data = download_file(file_info['id'])
                df = pd.read_excel(f_data, sheet_name='Income', header=5, dtype=str)
                renames = {'หมายเลขคำสั่งซื้อ':'order_id', 'วันที่โอนชำระเงินสำเร็จ':'settlement_date',
                           'สินค้าราคาปกติ':'original_price', 'ค่าคอมมิชชั่น':'affiliate', 'จำนวนเงินทั้งหมดที่โอนแล้ว (฿)':'settlement_amount'}
                df = df[[c for c in renames if c in df.columns]].rename(columns=renames)
                for c in ['original_price', 'settlement_amount', 'affiliate']:
                    if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
                income_dfs.append(df)
            except: pass
    if income_dfs:
        income_master = pd.concat(income_dfs, ignore_index=True)
        income_master['order_id'] = income_master['order_id'].apply(clean_scientific_notation)
        # Fees calculation logic simplification
        income_master['fees'] = 0 # Placeholder if needed
        cols = ['order_id', 'settlement_amount', 'settlement_date', 'fees', 'affiliate']
        income_master = income_master[[c for c in cols if c in income_master.columns]]

    # Orders
    for file_info in order_files:
        if 'xlsx' in file_info['name']:
            try:
                f_data = download_file(file_info['id'])
                df = pd.read_excel(f_data, dtype=str)
                if 'เวลาการชำระสินค้า' in df.columns:
                    df = df.dropna(subset=['เวลาการชำระสินค้า'])
                    cols = {'หมายเลขคำสั่งซื้อ':'order_id', 'สถานะการสั่งซื้อ':'status', 'เวลาการชำระสินค้า':'shipped_date',
                            'เลขอ้างอิง SKU (SKU Reference No.)':'sku', 'จำนวน':'quantity', 'ราคาขายสุทธิ':'sales_amount',
                            '*หมายเลขติดตามพัสดุ':'tracking_id', 'วันที่ทำการสั่งซื้อ':'created_date'}
                    df = df[[c for c in cols if c in df.columns]].rename(columns=cols)
                    df['shop_name'] = shop_name
                    df['platform'] = 'SHOPEE'
                    df = clean_date(df, 'created_date')
                    df = clean_date(df, 'shipped_date')
                    df['order_id'] = df['order_id'].apply(clean_scientific_notation)
                    all_orders.append(df)
            except: pass

    if not all_orders: return pd.DataFrame()
    final_df = pd.concat(all_orders, ignore_index=True)
    if not income_master.empty:
        income_master = income_master.groupby('order_id').first().reset_index()
        final_df = pd.merge(final_df, income_master, on='order_id', how='left')
    return final_df

def process_lazada(order_files, income_files, shop_name):
    all_orders = []
    income_master = pd.DataFrame()

    # Income
    income_dfs = []
    for file_info in income_files:
        if 'xlsx' in file_info['name']:
            try:
                f_data = download_file(file_info['id'])
                df = pd.read_excel(f_data, sheet_name='Income Overview', dtype=str)
                df = df.iloc[:, [0, 2, 3]] # Assuming generic columns if names change
                df.columns = ['order_id', 'settlement_date', 'amount']
                df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
                income_dfs.append(df)
            except: pass
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
                    cols = {'orderNumber':'order_id', 'status':'status', 'sellerSku':'sku', 'unitPrice':'sales_amount',
                            'trackingCode':'tracking_id', 'createTime':'created_date', 'deliveredDate':'shipped_date'}
                    df = df[[c for c in cols if c in df.columns]].rename(columns=cols)
                    df['quantity'] = 1
                    df['shop_name'] = shop_name
                    df['platform'] = 'LAZADA'
                    df = clean_date(df, 'created_date')
                    df = clean_date(df, 'shipped_date')
                    df['order_id'] = df['order_id'].apply(clean_scientific_notation)
                    all_orders.append(df)
            except: pass

    if not all_orders: return pd.DataFrame()
    final_df = pd.concat(all_orders, ignore_index=True)
    if not income_master.empty:
        final_df = pd.merge(final_df, income_master, on='order_id', how='left')
    return final_df

# --- MAIN APP ---
st.title("🛍️ Multi-Platform E-Commerce Dashboard")
tab1, tab2 = st.tabs(["🚀 Sync & Dashboard", "💰 ตั้งค่าต้นทุน (Master Cost)"])

with tab1:
    st.write("Debug: เริ่มต้น Tab 1") # DEBUG

    if st.button("🚀 Sync Data from Google Drive"):
        with st.spinner("กำลังเชื่อมต่อ..."):
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
                inc_files = list_files_in_folder(folder_map.get(income_folders.get(platform), ''))
                
                for shop_name in shop_list:
                    if shop_name in folder_map:
                        files = list_files_in_folder(folder_map[shop_name])
                        if platform == 'TIKTOK': res = process_tiktok(files, inc_files, shop_name)
                        elif platform == 'SHOPEE': res = process_shopee(files, inc_files, shop_name)
                        elif platform == 'LAZADA': res = process_lazada(files, inc_files, shop_name)
                        else: res = pd.DataFrame()
                        
                        if not res.empty:
                            all_data.append(res)
                            st.write(f"✅ {shop_name}: {len(res)} orders")

            if all_data:
                master_df = pd.concat(all_data, ignore_index=True)
                
                # Calculation
                st.info("กำลังคำนวณกำไร...")
                cost_df = load_cost_data()
                if not cost_df.empty:
                    master_df = pd.merge(master_df, cost_df, on=['sku', 'platform'], how='left')
                else:
                    master_df['unit_cost'] = 0

                # Fill NaNs
                for c in ['quantity', 'unit_cost', 'settlement_amount']:
                    if c in master_df.columns: master_df[c] = pd.to_numeric(master_df[c], errors='coerce').fillna(0)
                
                master_df['total_cost'] = master_df.get('quantity', 0) * master_df.get('unit_cost', 0)
                master_df['net_profit'] = master_df.get('settlement_amount', 0) - master_df['total_cost']
                
                # Upload
                master_df = master_df.where(pd.notnull(master_df), None)
                for c in ['created_date', 'shipped_date', 'settlement_date']:
                    if c in master_df.columns: master_df[c] = master_df[c].astype(str)

                st.info("กำลังอัปโหลดขึ้น Database...")
                records = master_df.to_dict(orient='records')
                chunk_size = 500
                for i in range(0, len(records), chunk_size):
                    chunk = records[i:i+chunk_size]
                    try:
                        # ตรวจสอบว่าคอลัมน์ตรงกับ DB ไหม ถ้าไม่ตรง Supabase อาจปฏิเสธ
                        supabase.table("orders").upsert(chunk).execute()
                    except Exception as e:
                        st.error(f"❌ Upload Error (Chunk {i}): {e}")
                
                st.success("✅ Sync เสร็จสิ้น!")
                st.rerun()
            else:
                st.warning("ไม่พบข้อมูลออเดอร์ใน Drive")

    # --- ส่วนแสดงผลสรุป (อยู่นอกปุ่ม Sync) ---
    st.divider()
    st.subheader("📊 สรุปยอดขาย (Summary)")
    st.write("Debug: กำลังโหลดข้อมูลสรุป...") # DEBUG

    try:
        response = supabase.table("orders").select("*").execute()
        db_df = pd.DataFrame(response.data)
        
        st.write(f"Debug: พบข้อมูลใน Database จำนวน {len(db_df)} แถว") # DEBUG

        if not db_df.empty:
            # Metrics
            cols = ['sales_amount', 'settlement_amount', 'total_cost', 'net_profit', 'affiliate']
            for c in cols:
                if c in db_df.columns: db_df[c] = pd.to_numeric(db_df[c], errors='coerce').fillna(0)

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("ยอดขาย", f"{db_df.get('sales_amount', pd.Series([0])).sum():,.2f}")
            c2.metric("เงินเข้าจริง", f"{db_df.get('settlement_amount', pd.Series([0])).sum():,.2f}")
            c3.metric("ต้นทุน", f"{db_df.get('total_cost', pd.Series([0])).sum():,.2f}")
            c4.metric("กำไร", f"{db_df.get('net_profit', pd.Series([0])).sum():,.2f}")
            c5.metric("Affiliate", f"{db_df.get('affiliate', pd.Series([0])).sum():,.2f}")

            # Chart
            if 'platform' in db_df.columns:
                st.bar_chart(db_df.groupby('platform')['sales_amount'].sum())

            # Table
            st.write("📄 **รายการออเดอร์**")
            show_cols = ['order_id', 'platform', 'sku', 'sales_amount', 'net_profit']
            st.dataframe(db_df[[c for c in show_cols if c in db_df.columns]], use_container_width=True)
        else:
            st.info("ℹ️ ยังไม่มีข้อมูลใน Database (ตารางว่างเปล่า)")
    
    except Exception as e:
        st.error(f"❌ โหลดข้อมูลผิดพลาด: {e}")

with tab2:
    manage_costs_page()