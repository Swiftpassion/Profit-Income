import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from supabase import create_client, Client
import io
import datetime

# --- CONFIGURATION ---
# ใส่ ID ของโฟลเดอร์แม่ "LAZADA SHOPEE TIKTOK" จาก URL ของ Google Drive ตรงนี้
PARENT_FOLDER_ID = '1DJp8gpZ8lntH88hXqYuZOwIyFv3NY4Ot' 

# ตั้งค่า Supabase Connection (ดึงจาก st.secrets)
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ตั้งค่า Google Drive Auth
# แนะนำให้เอาเนื้อหาในไฟล์ json มาใส่ใน st.secrets["gcp_service_account"]
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
creds = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"], scopes=SCOPES
)
drive_service = build('drive', 'v3', credentials=creds)

# --- HELPER FUNCTIONS ---

def list_files_in_folder(folder_id):
    """List all files and subfolders in a specific Google Drive folder."""
    query = f"'{folder_id}' in parents and trashed = false"
    results = drive_service.files().list(q=query, fields="files(id, name, mimeType)").execute()
    return results.get('files', [])

def download_file(file_id):
    """Download a file from Google Drive into memory."""
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    fh.seek(0)
    return fh

def clean_date(df, col_name):
    """Convert datetime to date only."""
    df[col_name] = pd.to_datetime(df[col_name], errors='coerce').dt.date
    return df

def clean_scientific_notation(val):
    """Ensure Order IDs are strings, not scientific notation."""
    try:
        return str(int(float(val)))
    except:
        return str(val)

# --- PROCESSOR: TIKTOK ---
def process_tiktok(order_files, income_files, shop_name):
    all_orders = []
    
    # 1. Process Income Files first to build a lookup dict
    income_dfs = []
    for file_info in income_files:
        if 'xlsx' in file_info['name']:
            f_data = download_file(file_info['id'])
            # TikTok Income: Sheet "Order details"
            df = pd.read_excel(f_data, sheet_name='Order details', dtype={'Related order ID': str})
            # Columns: AV=Related order ID, F=Total settlement amount, D=Order settled time, N=Total Fees
            # Adjust column letters to indices (0-based): AV=47, F=5, D=3, N=13
            # แต่การใช้ชื่อ Column จะแม่นยำกว่าหาก Header ตรง
            df = df[['Related order ID', 'Total settlement amount', 'Order settled time', 'Total Fees']]
            income_dfs.append(df)
    
    income_master = pd.DataFrame()
    if income_dfs:
        income_master = pd.concat(income_dfs, ignore_index=True)
        # Clean ID
        income_master['Related order ID'] = income_master['Related order ID'].apply(clean_scientific_notation)

    # 2. Process Order Files
    for file_info in order_files:
        if 'xlsx' in file_info['name']:
            f_data = download_file(file_info['id'])
            df = pd.read_excel(f_data, dtype={'Order ID': str, 'Seller SKU': str, 'Tracking ID': str})
            
            # Filter: Must have Shipped Time (Column AC)
            if 'Shipped Time' in df.columns:
                df = df.dropna(subset=['Shipped Time'])
                
                # Column Mappings based on prompt
                # A=Order ID, B=Order Status, G=Seller SKU, J=Quantity, P=SKU Subtotal After Discount, 
                # Z=Created Time, AC=Shipped Time, AJ=Tracking ID
                
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
                
                # Check exist columns
                available_cols = [c for c in cols_needed.keys() if c in df.columns]
                df = df[available_cols].rename(columns=cols_needed)
                
                # Add Shop Name
                df['shop_name'] = shop_name
                df['platform'] = 'TIKTOK'

                # Clean Dates
                df = clean_date(df, 'created_date')
                df = clean_date(df, 'shipped_date')
                
                # Clean Order ID
                df['order_id'] = df['order_id'].apply(clean_scientific_notation)
                
                # Multi-item order handling for display (Keep raw rows but we merge income by OrderID)
                all_orders.append(df)

    if not all_orders:
        return pd.DataFrame()

    final_df = pd.concat(all_orders, ignore_index=True)

    # Merge with Income
    if not income_master.empty:
        # Income is per Order, not per Item. We merge carefully.
        # TikTok Income format: AV=Related order ID
        income_master = income_master.rename(columns={
            'Related order ID': 'order_id',
            'Total settlement amount': 'settlement_amount',
            'Order settled time': 'settlement_date',
            'Total Fees': 'fees'
        })
        # Deduplicate Income Master (one row per order id)
        income_master = income_master.groupby('order_id').first().reset_index()
        
        final_df = pd.merge(final_df, income_master, on='order_id', how='left')
    
    return final_df

# --- PROCESSOR: SHOPEE ---
def process_shopee(order_files, income_files, shop_name):
    all_orders = []
    
    # 1. Process Income Files (Sheet "Income", header at row 6 -> index 5)
    income_dfs = []
    for file_info in income_files:
        if 'xlsx' in file_info['name'] or 'xls' in file_info['name']:
            f_data = download_file(file_info['id'])
            # Read header at row 6 (0-based index 5)
            df = pd.read_excel(f_data, sheet_name='Income', header=5, dtype={'หมายเลขคำสั่งซื้อ': str})
            
            # Check columns: B=หมายเลขคำสั่งซื้อ, AH=จำนวนเงินทั้งหมดที่โอนแล้ว (฿), L=วันที่โอนชำระเงินสำเร็จ, M=สินค้าราคาปกติ
            # Note: Column names might vary slightly, using exact names from prompt
            req_cols = ['หมายเลขคำสั่งซื้อ', 'จำนวนเงินทั้งหมดที่โอนแล้ว (฿)', 'วันที่โอนชำระเงินสำเร็จ', 'สินค้าราคาปกติ']
            
            # Select only existing columns to avoid errors
            sel_cols = [c for c in req_cols if c in df.columns]
            df = df[sel_cols]
            
            # Rename for easier handling
            df = df.rename(columns={
                'หมายเลขคำสั่งซื้อ': 'order_id',
                'จำนวนเงินทั้งหมดที่โอนแล้ว (฿)': 'settlement_amount',
                'วันที่โอนชำระเงินสำเร็จ': 'settlement_date',
                'สินค้าราคาปกติ': 'original_price'
            })
            
            income_dfs.append(df)
            
    income_master = pd.DataFrame()
    if income_dfs:
        income_master = pd.concat(income_dfs, ignore_index=True)
        income_master['order_id'] = income_master['order_id'].apply(clean_scientific_notation)
        # Calculate Fees: M - AH
        income_master['fees'] = income_master['original_price'] - income_master['settlement_amount']
        income_master = income_master[['order_id', 'settlement_amount', 'settlement_date', 'fees']]

    # 2. Process Order Files
    for file_info in order_files:
        if 'xlsx' in file_info['name']:
            f_data = download_file(file_info['id'])
            df = pd.read_excel(f_data, dtype={'หมายเลขคำสั่งซื้อ': str, '*หมายเลขติดตามพัสดุ': str})
            
            # Filter: H = เวลาการชำระสินค้า
            if 'เวลาการชำระสินค้า' in df.columns:
                df = df.dropna(subset=['เวลาการชำระสินค้า'])
                
                cols_needed = {
                    'หมายเลขคำสั่งซื้อ': 'order_id',
                    'สถานะการสั่งซื้อ': 'status',
                    'เวลาการชำระสินค้า': 'paid_date',
                    'เลขอ้างอิง SKU (SKU Reference No.)': 'sku',
                    'จำนวน': 'quantity',
                    'ราคาขายสุทธิ': 'sales_amount', # Z
                    '*หมายเลขติดตามพัสดุ': 'tracking_id', # O
                    'วันที่ทำการสั่งซื้อ': 'created_date' # G
                }
                 # Check exist columns
                available_cols = [c for c in cols_needed.keys() if c in df.columns]
                df = df[available_cols].rename(columns=cols_needed)

                df['shop_name'] = shop_name
                df['platform'] = 'SHOPEE'
                
                df = clean_date(df, 'paid_date')
                df = clean_date(df, 'created_date')
                df['order_id'] = df['order_id'].apply(clean_scientific_notation)
                
                all_orders.append(df)

    if not all_orders:
        return pd.DataFrame()

    final_df = pd.concat(all_orders, ignore_index=True)

    # Merge Income
    if not income_master.empty:
        income_master = income_master.groupby('order_id').first().reset_index() # De-dup
        final_df = pd.merge(final_df, income_master, on='order_id', how='left')
        
    return final_df

# --- PROCESSOR: LAZADA ---
def process_lazada(order_files, income_files, shop_name):
    all_orders = []
    
    # 1. Process Income Files (Sheet "Income Overview")
    income_dfs = []
    for file_info in income_files:
        if 'xlsx' in file_info['name']:
            f_data = download_file(file_info['id'])
            try:
                # K=orderNumber, C=วันที่ปรับปรุงเข้ายอดของฉัน, D=ชื่อรายการธุรกรรม (Amount column might be adjacent, assuming logic below)
                # Note: Prompt says "Column D = ชื่อรายการธุรกรรม" used for amount calculation? 
                # Usually Lazada report has "Amount" column. Prompt implies calculating from transaction amounts.
                # Assuming standard Lazada Income report structure where there is an 'Amount' column.
                # Let's Look at prompt again: "นำ (คอลัม D = ชื่อรายการธุรกรรม)..." - This implies D is the Amount/Value or D contains Name and another col has value?
                # **Interpretation**: Assuming Column D is 'Amount' (User might have mislabeled or it's a specific report format).
                # Let's try to find a column resembling 'Amount' or 'Paid Price' + 'Shipping Fee' etc.
                # BUT, sticking to prompt: "Column D ... sum negative ... sum positive". Let's assume D *is* the value column.
                
                df = pd.read_excel(f_data, sheet_name='Income Overview', dtype={'orderNumber': str})
                
                # Identifying columns based on names/prompt
                # K = orderNumber, C = date
                # D = Transaction Amount (As per prompt logic)
                
                # Check for column names mapping
                # Assuming user means column index 3 (D) is amount
                col_d_name = df.columns[3] 
                col_k_name = 'orderNumber' if 'orderNumber' in df.columns else df.columns[10] # K is 11th
                col_c_name = 'วันที่ปรับปรุงเข้ายอดของฉัน' if 'วันที่ปรับปรุงเข้ายอดของฉัน' in df.columns else df.columns[2]
                
                df = df[[col_k_name, col_c_name, col_d_name]]
                df.columns = ['order_id', 'settlement_date', 'amount']
                
                income_dfs.append(df)
            except Exception as e:
                st.warning(f"Error reading Lazada Income file {file_info['name']}: {e}")

    income_master = pd.DataFrame()
    if income_dfs:
        raw_income = pd.concat(income_dfs, ignore_index=True)
        raw_income['order_id'] = raw_income['order_id'].apply(clean_scientific_notation)
        
        # Logic: 
        # Fees = Sum of negative amounts per order
        # Real Received = (Sum of positive amounts) - (Abs(Fees)?? or Just Sum Pos + Sum Neg?)
        # Prompt: "ยอดเงินที่ได้รับจริง = นำยอดไม่ติดลบตั้ง - ค่าธรรมเนียม(ยอดติดลบ)"
        # Note: If Fee is -10. Positive is 100.  100 - (-10) = 110 (Wrong).
        # Usually: Net = 100 + (-10) = 90.
        # User Logic Interpretation: Net = Positive - (Sum of Negatives). 
        # Since Sum of Negatives is negative (e.g., -10), Positive - (-10) = Positive + 10. This is likely not what is meant physically.
        # Most likely meaning: Net = Positive + Negative (Algebraic Sum). 
        # OR User defines Fee as ABS(Sum Negatives). Then Net = Positive - Fee.
        # Let's calculate Positive Sum and Negative Sum separately.
        
        # Convert amount to float
        raw_income['amount'] = pd.to_numeric(raw_income['amount'], errors='coerce').fillna(0)
        
        # Group logic
        grouped = raw_income.groupby(['order_id', 'settlement_date']).agg(
            pos_sum=('amount', lambda x: x[x > 0].sum()),
            neg_sum=('amount', lambda x: x[x < 0].sum())
        ).reset_index()
        
        grouped['fees'] = grouped['neg_sum'] # This will be negative
        # "ยอดเงินที่ได้รับจริง" logic from prompt: Positive - Fees. 
        # If Fees is negative (-50). Positive (100). 100 - (-50) = 150. (Unlikely).
        # I will implement: Net = Positive + Negative (Standard accounting). 
        # But to respect prompt "Positive - Fee", if Fee is treated as positive cost:
        # Let's map exactly to prompt text logic: "Fee = Sum of Negatives". "Net = Positive - Fee".
        # If I strictly follow math: 100 - (-10) = 110. 
        # I will assume "Fee" meant "Absolute value of sum of negatives".
        
        grouped['fees_val'] = grouped['neg_sum'].abs()
        grouped['settlement_amount'] = grouped['pos_sum'] - grouped['fees_val']
        
        income_master = grouped[['order_id', 'settlement_date', 'settlement_amount', 'fees']]

    # 2. Process Order Files
    for file_info in order_files:
        if 'xlsx' in file_info['name']:
            f_data = download_file(file_info['id'])
            df = pd.read_excel(f_data, dtype={'orderNumber': str, 'trackingCode': str})
            
            # Filter: Must have trackingCode (BG)
            if 'trackingCode' in df.columns:
                df = df.dropna(subset=['trackingCode'])
                
                # M=orderNumber, BN=status, F=sellerSku, Qty=1, AV=unitPrice, BG=trackingCode, I=createTime, P=deliveredDate
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
                
                df['quantity'] = 1 # Always 1 as per prompt
                df['shop_name'] = shop_name
                df['platform'] = 'LAZADA'
                
                df = clean_date(df, 'created_date')
                df = clean_date(df, 'shipped_date')
                df['order_id'] = df['order_id'].apply(clean_scientific_notation)
                
                all_orders.append(df)
    
    if not all_orders:
        return pd.DataFrame()

    final_df = pd.concat(all_orders, ignore_index=True)
    
    if not income_master.empty:
        # Lazada handles split orders sometimes, merging on Order Number is standard
        income_master = income_master.groupby('order_id').first().reset_index()
        final_df = pd.merge(final_df, income_master, on='order_id', how='left')
        
    return final_df


# --- MAIN APP LOGIC ---

st.title("🛍️ Multi-Platform E-Commerce Dashboard")

if st.button("🚀 Sync Data from Google Drive"):
    with st.spinner("Connecting to Google Drive..."):
        # 1. Map Folders
        root_files = list_files_in_folder(PARENT_FOLDER_ID)
        
        # Identify Shop Folders and Income Folders
        shops = {
            'TIKTOK': ['TIKTOK 1', 'TIKTOK 2', 'TIKTOK 3'],
            'SHOPEE': ['SHOPEE 1', 'SHOPEE 2', 'SHOPEE 3'],
            'LAZADA': ['LAZADA 1', 'LAZADA 2', 'LAZADA 3']
        }
        income_folders = {
            'TIKTOK': 'INCOME TIKTOK',
            'SHOPEE': 'INCOME SHOPEE',
            'LAZADA': 'INCOME LAZADA'
        }
        
        # Map folder names to IDs
        folder_map = {f['name']: f['id'] for f in root_files if f['mimeType'] == 'application/vnd.google-apps.folder'}
        
        all_data = []
        
        # Iterate Platforms
        for platform, shop_list in shops.items():
            st.write(f"Processing {platform}...")
            
            # Get Income Files for this platform
            inc_folder_name = income_folders[platform]
            inc_files = []
            if inc_folder_name in folder_map:
                inc_files = list_files_in_folder(folder_map[inc_folder_name])
            
            for shop_name in shop_list:
                if shop_name in folder_map:
                    order_files = list_files_in_folder(folder_map[shop_name])
                    
                    df_res = pd.DataFrame()
                    if platform == 'TIKTOK':
                        df_res = process_tiktok(order_files, inc_files, shop_name)
                    elif platform == 'SHOPEE':
                        df_res = process_shopee(order_files, inc_files, shop_name)
                    elif platform == 'LAZADA':
                        df_res = process_lazada(order_files, inc_files, shop_name)
                    
                    if not df_res.empty:
                        all_data.append(df_res)
                        st.success(f"Loaded {len(df_res)} orders from {shop_name}")
        
        if all_data:
            master_df = pd.concat(all_data, ignore_index=True)
            
            # Convert Date objects to strings for Supabase/JSON
            date_cols = ['created_date', 'shipped_date', 'paid_date', 'settlement_date']
            for col in date_cols:
                if col in master_df.columns:
                    master_df[col] = master_df[col].astype(str).replace('NaT', None)
            
            # Upsert to Supabase
            st.info("Uploading to Database...")
            records = master_df.to_dict(orient='records')
            
            # Chunking upload (Supabase sometimes limits payload size)
            chunk_size = 1000
            for i in range(0, len(records), chunk_size):
                chunk = records[i:i + chunk_size]
                try:
                    # 'upsert' works if you have a Primary Key set on 'order_id' + 'sku' (composite) or just 'order_id'
                    # Make sure your Supabase table has a Primary Key!
                    supabase.table("orders").upsert(chunk).execute()
                except Exception as e:
                    st.error(f"Error uploading chunk {i}: {e}")
            
            st.success("✅ Data Sync Complete!")
            st.dataframe(master_df)
        else:
            st.warning("No data found or processed.")

# --- DASHBOARD VIEW ---
st.divider()
st.subheader("📊 Summary View")

# Fetch data from Supabase for viewing (Live Data)
try:
    response = supabase.table("orders").select("*").execute()
    db_df = pd.DataFrame(response.data)
    
    if not db_df.empty:
        st.write("Total Orders in DB:", len(db_df))
        
        # Simple Metrics
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Sales", f"{db_df['sales_amount'].sum():,.2f}")
        col2.metric("Total Settlement", f"{db_df['settlement_amount'].sum():,.2f}")
        col3.metric("Total Fees", f"{db_df['fees'].sum():,.2f}")
        
        # Pivot by Platform
        st.write("Sales by Platform")
        pivot = db_df.groupby('platform')[['sales_amount', 'settlement_amount']].sum()
        st.bar_chart(pivot)
        
        with st.expander("View Raw Data"):
            st.dataframe(db_df)
            
except Exception as e:
    st.error("Could not fetch data from database yet.")