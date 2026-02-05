import streamlit as st
import pandas as pd
import io
import os
from pathlib import Path
import shutil
import gspread
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from sqlalchemy import text
from .database import get_engine, init_db

# --- CONSTANTS ---
FOLDER_ID_DATA = "1ciI_X2m8pVcsjRsPuUf5sg--6uPSPPDp"  # ไฟล์ยอดขาย JST
FOLDER_ID_ADS = "1ZE76TXNA_vNeXjhAZfLgBQQGIV0GY7w8"   # ไฟล์ค่า ADS
SHEET_MASTER_URL = "https://docs.google.com/spreadsheets/d/1Q3akHm1GKkDI2eilGfujsd9pO7aOjJvyYJNuXd98lzo/edit?gid=0#gid=0" # ชีทตั้งค่าทุน
LOCAL_DATA_DIR = Path("local_data")

# --- HELPERS ---
def get_drive_service():
    if "gcp_service_account" not in st.secrets:
        st.error("Error: ไม่พบ Secrets กรุณาตรวจสอบการตั้งค่า (required for Drive Mode)")
        return None
    creds_dict = dict(st.secrets["gcp_service_account"])
    scopes = ['https://www.googleapis.com/auth/drive.readonly', 'https://www.googleapis.com/auth/spreadsheets']
    return service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)

def load_data_drive():
    """Fetches data from Google Drive."""
    creds = get_drive_service()
    if not creds: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    service = build('drive', 'v3', credentials=creds)
    gc = gspread.authorize(creds)

    def get_files(folder_id):
        try:
            results = service.files().list(q=f"'{folder_id}' in parents and trashed=false", fields="files(id, name)").execute()
            return results.get('files', [])
        except: return []

    def read_file(file_id, filename):
        try:
            request = service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False: status, done = downloader.next_chunk()
            fh.seek(0)
            if filename.lower().endswith('.csv'): return pd.read_csv(fh, dtype={'หมายเลขคำสั่งซื้อออนไลน์': str})
            elif filename.lower().endswith(('.xlsx', '.xls')): return pd.read_excel(fh)
        except: pass
        return None

    # Load Sales Data
    files_data = get_files(FOLDER_ID_DATA)
    df_list = []
    for f in files_data:
        df = read_file(f['id'], f['name'])
        if df is not None:
            if 'หมายเลขคำสั่งซื้อออนไลน์' in df.columns:
                df['หมายเลขคำสั่งซื้อออนไลน์'] = df['หมายเลขคำสั่งซื้อออนไลน์'].astype(str).str.replace(r'\.0$', '', regex=True)
            df_list.append(df)
    df_data = pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()

    # Load Ads Data
    files_ads = get_files(FOLDER_ID_ADS)
    df_ads_list = []
    for f in files_ads:
        df = read_file(f['id'], f['name'])
        if df is not None: df_ads_list.append(df)
    df_ads_raw = pd.concat(df_ads_list, ignore_index=True) if df_ads_list else pd.DataFrame()

    # Load Master & Fix Cost
    df_master = pd.DataFrame()
    df_fix = pd.DataFrame()
    try:
        sh = gc.open_by_url(SHEET_MASTER_URL)
        df_master = pd.DataFrame(sh.worksheet("MASTER_ITEM").get_all_records())
        try: df_fix = pd.DataFrame(sh.worksheet("FIX_COST").get_all_records())
        except: 
            try: df_fix = pd.DataFrame(sh.worksheet("FIXED_COST").get_all_records())
            except: pass
    except: pass

    return df_data, df_ads_raw, df_master, df_fix

def load_data_local():
    """Fetches data from local_data directory."""
    if not LOCAL_DATA_DIR.exists():
        LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    df_list = []
    df_ads_list = []
    
    # Simple logic: Files with 'orders' or similar in name -> Sales, 'ads' -> Ads.
    # Or just try to detect columns?
    # Better approach: The user uploads files. We might need a naming convention or separate folders.
    # For now, let's assume strict naming or just try to detect content.
    # Or strict: JST Sales files, ADS files.
    # Let's try to detect based on filename keywords 'ads', 'marketing' -> Ads, otherwise Sales?
    # Original code just grabs everything in folder A or folder B.
    # In local mode, we have one flat folder? Or subfolders?
    # Let's create subfolders in `local_data` to be safe: `local_data/sales` and `local_data/ads`.
    
    path_sales = LOCAL_DATA_DIR / "sales"
    path_ads = LOCAL_DATA_DIR / "ads"
    path_sales.mkdir(exist_ok=True)
    path_ads.mkdir(exist_ok=True)

    # Load Sales
    for file_path in path_sales.iterdir():
        if file_path.suffix.lower() in ['.csv', '.xlsx', '.xls']:
            try:
                if file_path.suffix.lower() == '.csv':
                    df = pd.read_csv(file_path, dtype={'หมายเลขคำสั่งซื้อออนไลน์': str})
                else:
                    df = pd.read_excel(file_path)
                
                if 'หมายเลขคำสั่งซื้อออนไลน์' in df.columns:
                    df['หมายเลขคำสั่งซื้อออนไลน์'] = df['หมายเลขคำสั่งซื้อออนไลน์'].astype(str).str.replace(r'\.0$', '', regex=True)
                df_list.append(df)
            except Exception as e:
                print(f"Error reading local file {file_path}: {e}")

    df_data = pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()

    # Load Ads
    for file_path in path_ads.iterdir():
        if file_path.suffix.lower() in ['.csv', '.xlsx', '.xls']:
            try:
                if file_path.suffix.lower() == '.csv':
                    df = pd.read_csv(file_path)
                else:
                    df = pd.read_excel(file_path)
                df_ads_list.append(df)
            except: pass
    
    df_ads_raw = pd.concat(df_ads_list, ignore_index=True) if df_ads_list else pd.DataFrame()

    # Master Item handling in Local Mode?
    # Option 1: Still fetch from GSheet if internet available?
    # Option 2: Require a 'master_item.xlsx' in local_data?
    # The requirement says "Dual Data Source Feature... Mode Drive vs Mode Local".
    # Usually Master Data is config. It might be better to still fetch from Sheet if possible, 
    # OR allow a local override.
    # For simplicity & robustness (offline support): Look for local master file first.
    # If not found, try GSheet.
    
    df_master = pd.DataFrame()
    df_fix = pd.DataFrame()

    # 1. Try Google Sheets first (if secrets available)
    if "gcp_service_account" in st.secrets:
        try:
             # Reuse the drive logic just for master
             _, _, df_master_web, df_fix_web = load_data_drive()
             if not df_master_web.empty: 
                 df_master = df_master_web
                 df_fix = df_fix_web
        except: pass

    # 2. Fallback to Local File if Google Sheets failed or empty
    if df_master.empty:
        master_path = LOCAL_DATA_DIR / "master_item.xlsx"
        if master_path.exists():
            try:
                df_master_local = pd.read_excel(master_path, sheet_name="MASTER_ITEM")
                try: df_fix_local = pd.read_excel(master_path, sheet_name="FIX_COST")
                except: df_fix_local = pd.DataFrame() # Create empty DF if sheet missing
                
                df_master = df_master_local
                if df_fix.empty: df_fix = df_fix_local
            except: pass

    return df_data, df_ads_raw, df_master, df_fix


def ingest_local_data_to_db():
    """Reads all files from local_data/{shop}/... and bulk inserts to PostgreSQL."""
    engine = get_engine()
    
    # 1. Truncate Tables
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE raw_sales, raw_ads RESTART IDENTITY;"))
    
    # 2. Iterate Shops
    if not LOCAL_DATA_DIR.exists(): return
    
    # Exclude legacy folders 'sales' and 'ads' if they exist in root
    shops = [d for d in LOCAL_DATA_DIR.iterdir() if d.is_dir() and d.name not in ["sales", "ads"]]
    
    total_shops = len(shops)
    for i, shop_dir in enumerate(shops):
        shop_name = shop_dir.name
        st.write(f"🏢 Processing Shop ({i+1}/{total_shops}): **{shop_name}**")
        
        # --- SALES ---
        path_sales = shop_dir / "sales"
        if path_sales.exists():
            for f in path_sales.iterdir():
                if f.suffix.lower() in ['.csv', '.xlsx', '.xls']:
                    try:
                        if f.suffix.lower() == '.csv': df = pd.read_csv(f, dtype=str)
                        else: df = pd.read_excel(f, dtype=str)
                        
                        # Process Columns
                        # Map to DB columns: order_id, status, courier, order_time, sku_code, quantity, amount_paid...
                        # Need a mapping logic. For now, try to rename standard columns.
                        # We used to read them in process_data. Let's do partial cleaning here.
                        
                        # Standardize columns based on known headers in files
                        # Assuming the file format is consistent with what process_data expected
                        # We need to be careful with column names.
                        
                        # Let's map Thai columns to DB columns
                        # DB: order_id, status, courier, order_time, sku_code, quantity, amount_paid, creator, payment_method, product_name, work_type
                        col_map = {
                            'หมายเลขคำสั่งซื้อออนไลน์': 'order_id',
                            'สถานะคำสั่งซื้อ': 'status',
                            'บริษัทขนส่ง': 'courier',
                            'เวลาสั่งซื้อ': 'order_time',
                            'รูปแบบสินค้า': 'sku_code',
                            'จำนวน': 'quantity',
                            'รายละเอียดยอดที่ชำระแล้ว': 'amount_paid',
                            'ผู้สร้างคำสั่งซื้อ': 'creator',
                            'วิธีการชำระเงิน': 'payment_method',
                            'ชื่อสินค้า': 'product_name',
                            'ประเภทการทำงาน': 'work_type'
                        }
                        
                        df_db = df.rename(columns=col_map)
                        
                        # Keep only valid columns
                        valid_cols = list(col_map.values())
                        df_db = df_db[[c for c in df_db.columns if c in valid_cols]]
                        df_db['shop_name'] = shop_name
                        
                        # Clean numeric
                        for c in ['quantity', 'amount_paid']:
                            if c in df_db.columns:
                                df_db[c] = pd.to_numeric(df_db[c].astype(str).str.replace(',',''), errors='coerce').fillna(0)
                        
                        df_db.to_sql('raw_sales', engine, if_exists='append', index=False, chunksize=1000)
                    except Exception as e:
                        print(f"Error ingesting sale file {f}: {e}")

        # --- ADS ---
        path_ads = shop_dir / "ads"
        if path_ads.exists():
            for f in path_ads.iterdir():
                if f.suffix.lower() in ['.csv', '.xlsx', '.xls']:
                    try:
                        if f.suffix.lower() == '.csv': df = pd.read_csv(f)
                        else: df = pd.read_excel(f)
                        
                        # Map Columns
                        # Ads often have: Date, Campaign Name, Cost
                        # DB: date, campaign_name, cost
                        
                        col_cost = next((c for c in ['จำนวนเงินที่ใช้จ่ายไป (THB)', 'Cost', 'Amount'] if c in df.columns), None)
                        col_date = next((c for c in ['วัน', 'Date'] if c in df.columns), None)
                        col_camp = next((c for c in ['ชื่อแคมเปญ', 'Campaign'] if c in df.columns), None)
                        
                        if col_cost and col_date:
                            df_db = pd.DataFrame()
                            df_db['date'] = pd.to_datetime(df[col_date], errors='coerce')
                            df_db['cost'] = pd.to_numeric(df[col_cost].astype(str).str.replace(',',''), errors='coerce').fillna(0)
                            df_db['campaign_name'] = df[col_camp] if col_camp else ""
                            df_db['shop_name'] = shop_name
                            
                            df_db = df_db.dropna(subset=['date'])
                            df_db.to_sql('raw_ads', engine, if_exists='append', index=False)
                    except Exception as e:
                        print(f"Error ingesting ads file {f}: {e}")
    
    # --- MASTER ITEM ---
    # Load Master Item from local file if exists
    master_path = LOCAL_DATA_DIR / "master_item.xlsx"
    if master_path.exists():
         try:
            df_master = pd.read_excel(master_path, sheet_name="MASTER_ITEM")
            save_master_to_db(df_master, engine)
            
         except Exception as e:
             print(f"Error ingest master: {e}")

def save_master_to_db(df_master, engine=None):
    """Saves Master Item DataFrame to Database."""
    if engine is None: engine = get_engine()
    
    try:
        # Map columns
        # DB: sku, name, type, cost, box_cost, delivery_cost, com_admin, com_tele, p_...
        
        # Helper to map common names
        m_map = {
            'SKU': 'sku',
            'ชื่อสินค้า': 'name',
            'Type': 'type',
            'ทุน': 'cost', 'ต้นทุน': 'cost',
            'ราคากล่อง': 'box_cost',
            'ค่าส่งเฉลี่ย': 'delivery_cost',
            'ค่าคอมมิชชั่น Admin': 'com_admin',
            'ค่าคอมมิชชั่น Telesale': 'com_tele',
            'J&T Express': 'p_jnt',
            'Flash Express': 'p_flash',
            'Kerry Express': 'p_kerry',
            'ThailandPost': 'p_thai_post',
            'DHL_1': 'p_dhl',
            'SPX Express': 'p_spx',
            'LEX TH': 'p_lex',
            'Standard Delivery - ส่งธรรมดาในประเทศ': 'p_std'
        }
        
        df_m_db = df_master.rename(columns=m_map)
        df_m_db.columns = [c.strip() for c in df_m_db.columns]
        
        valid_m_cols = ['sku', 'name', 'type', 'cost', 'box_cost', 'delivery_cost', 
                        'com_admin', 'com_tele', 'p_jnt', 'p_flash', 'p_kerry', 
                        'p_thai_post', 'p_dhl', 'p_spx', 'p_lex', 'p_std']
        
        df_m_db = df_m_db[[c for c in df_m_db.columns if c in valid_m_cols]]
        
        # Clean numeric
        for c in df_m_db.columns:
            if c not in ['sku', 'name', 'type']:
                df_m_db[c] = pd.to_numeric(df_m_db[c].astype(str).str.replace(',','').str.replace('%',''), errors='coerce').fillna(0)
        
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE master_item;"))
        
        df_m_db.to_sql('master_item', engine, if_exists='append', index=False)
        return True
    except Exception as e:
        print(f"Error saving master to DB: {e}")
        raise e

def load_data_from_db():
    """Fetches RAW data from Database (for legacy compatibility)."""
    # Note: Ideally we switch to SQL processing, but legacy code expects DF.
    # We will query raw_sales and serve it as df_data
    engine = get_engine()
    
    # We need to reconstruct the DF structure that process_data expects
    # DB columns -> Original Thai columns
    q_sales = "SELECT * FROM raw_sales"
    df_sales = pd.read_sql(q_sales, engine)
    
    # Reverse Map
    rev_map = {
        'order_id': 'หมายเลขคำสั่งซื้อออนไลน์',
        'status': 'สถานะคำสั่งซื้อ',
        'courier': 'บริษัทขนส่ง',
        'order_time': 'เวลาสั่งซื้อ',
        'sku_code': 'รูปแบบสินค้า',
        'quantity': 'จำนวน',
        'amount_paid': 'รายละเอียดยอดที่ชำระแล้ว',
        'creator': 'ผู้สร้างคำสั่งซื้อ',
        'payment_method': 'วิธีการชำระเงิน',
        'product_name': 'ชื่อสินค้า',
        'work_type': 'ประเภทการทำงาน'
    }
    df_sales = df_sales.rename(columns=rev_map)
    # Add Shop Name needed? Legacy code doesn't use it yet, but we will need it for filtering
    # process_data() currently merges everything. 
    # We should add 'Shop' column to df_sales if we want to filter later.
    df_sales['Shop'] = df_sales['shop_name']
    
    q_ads = "SELECT * FROM raw_ads"
    df_ads = pd.read_sql(q_ads, engine)
    # Map back
    # DB: date, campaign_name, cost
    df_ads = df_ads.rename(columns={
        'date': 'Date', 'campaign_name': 'ชื่อแคมเปญ', 'cost': 'จำนวนเงินที่ใช้จ่ายไป (THB)'
    })
    
    q_master = "SELECT * FROM master_item"
    df_master = pd.read_sql(q_master, engine)
    # Map back
    m_rev_map = {
        'sku': 'SKU', 'name': 'ชื่อสินค้า', 'type': 'Type', 'cost': 'ต้นทุน',
        'box_cost': 'ราคากล่อง', 'delivery_cost': 'ค่าส่งเฉลี่ย',
        'com_admin': 'ค่าคอมมิชชั่น Admin', 'com_tele': 'ค่าคอมมิชชั่น Telesale',
        'p_jnt': 'J&T Express',
        'p_flash': 'Flash Express',
        'p_kerry': 'Kerry Express',
        'p_thai_post': 'ThailandPost',
        'p_dhl': 'DHL_1',
        'p_spx': 'SPX Express',
        'p_lex': 'LEX TH',
        'p_std': 'Standard Delivery - ส่งธรรมดาในประเทศ'
    }
    df_master = df_master.rename(columns=m_rev_map)
    
    return df_sales, df_ads, df_master, pd.DataFrame() # fix cost empty for now

def load_raw_files(mode="MODE_DRIVE"):
    # Intercept LOCAl mode to use DB
    if mode == "MODE_LOCAL":
        # Check if DB has data? Or just always load from DB
        return load_data_from_db()
    else:
        return load_data_drive()
