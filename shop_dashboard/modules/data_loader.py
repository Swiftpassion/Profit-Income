import streamlit as st
import pandas as pd
import io
import os
from pathlib import Path
import gspread
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

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

def load_raw_files(mode="MODE_DRIVE"):
    if mode == "MODE_LOCAL":
        return load_data_local()
    else:
        return load_data_drive()
