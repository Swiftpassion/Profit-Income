import pandas as pd
import numpy as np
import streamlit as st
from .data_loader import load_raw_files
from .ui_components import COLOR_NEGATIVE

# --- GLOBAL VARIABLES ---
thai_months = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
               "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]

def safe_float(val):
    if pd.isna(val) or val == "" or val is None: return 0.0
    s = str(val).strip().replace(',', '').replace('฿', '').replace(' ', '')
    if s in ['-', 'nan', 'NaN', 'None']: return 0.0
    try:
        if '%' in s: return float(s.replace('%', '')) / 100
        return float(s)
    except: return 0.0

def safe_date(val):
    try: return pd.to_datetime(val).date()
    except: return None

def normalize_courier_name(courier):
    if pd.isna(courier) or courier == "":
        return "Standard Delivery - ส่งธรรมดาในประเทศ"
    
    courier = str(courier).strip()
    mapping = {
        "J&T Express": "J&T Express", "J&T": "J&T Express",
        "Flash Express": "Flash Express", "Flash": "Flash Express",
        "Kerry Express": "Kerry Express", "Kerry": "Kerry Express",
        "Thailand Post": "ThailandPost", "ThailandPost": "ThailandPost",
        "DHL Domestic": "DHL_1", "DHL": "DHL_1",
        "Shopee Express": "SPX Express", "SPX Express": "SPX Express",
        "Lazada Express": "LEX TH", "LEX": "LEX TH"
    }
    return mapping.get(courier, courier)

@st.cache_data(ttl=600)
def process_data(mode="MODE_DRIVE"):
    df_data, df_ads_raw, df_master, df_fix_cost = load_raw_files(mode)

    if df_data.empty: return pd.DataFrame(), pd.DataFrame(), {}, [], {}

    # --- 1. PREPARE MASTER ITEM ---
    if not df_master.empty:
        df_master.columns = df_master.columns.astype(str).str.strip()
        
        if 'ทุน' in df_master.columns:
            df_master.rename(columns={'ทุน': 'ต้นทุน'}, inplace=True)
            
        if 'ชื่อสินค้า' not in df_master.columns:
            if len(df_master.columns) >= 2:
                col_b = df_master.columns[1]
                df_master.rename(columns={col_b: 'ชื่อสินค้า'}, inplace=True)
            else:
                df_master['ชื่อสินค้า'] = df_master['SKU'] if 'SKU' in df_master.columns else "Unknown"
        
        if 'Type' not in df_master.columns:
            df_master['Type'] = 'กลุ่ม ปกติ'
        df_master['Type'] = df_master['Type'].fillna('กลุ่ม ปกติ').astype(str).str.strip()

    # --- 2. PREPARE DATA ---
    cols = [c for c in ['หมายเลขคำสั่งซื้อออนไลน์', 'สถานะคำสั่งซื้อ', 
            'บริษัทขนส่ง', 'เวลาสั่งซื้อ', 'รูปแบบสินค้า', 'จำนวน', 
            'รายละเอียดยอดที่ชำระแล้ว', 'ผู้สร้างคำสั่งซื้อ', 
            'วิธีการชำระเงิน', 'ชื่อสินค้า', 'ประเภทการทำงาน'] 
            if c in df_data.columns]
    
    df = df_data[cols].copy()

    if 'สถานะคำสั่งซื้อ' in df.columns:
        df = df[~df['สถานะคำสั่งซื้อ'].isin(['ยกเลิก'])]

    df['Date'] = df['เวลาสั่งซื้อ'].apply(safe_date)
    df = df.dropna(subset=['Date'])
    
    df['SKU_Main'] = df['รูปแบบสินค้า'].astype(str).str.split('-').str[0].str.strip()

    # --- 3. MERGE WITH MASTER ITEM ---
    master_cols = ['SKU', 'ชื่อสินค้า', 'Type', 'ต้นทุน', 'ราคากล่อง', 'ค่าส่งเฉลี่ย',
                   'ค่าคอมมิชชั่น Admin', 'ค่าคอมมิชชั่น Telesale',
                   'J&T Express', 'Flash Express', 'ThailandPost', 
                   'DHL_1', 'LEX TH', 'SPX Express',
                   'Express Delivery - ส่งด่วน', 'Standard Delivery - ส่งธรรมดาในประเทศ']
    
    master_cols = [c for c in master_cols if c in df_master.columns]
    df_master_filtered = df_master[master_cols].drop_duplicates('SKU')

    df['SKU_Raw'] = df['รูปแบบสินค้า'].astype(str).str.strip()
    df['SKU_Norm'] = df['SKU_Raw'].str.replace(' ', '', regex=False)
    df['SKU_Norm_Root'] = df['SKU_Norm'].str.split('-').str[0]

    if not df_master_filtered.empty:
        df_master_filtered['SKU_Norm'] = df_master_filtered['SKU'].astype(str).str.strip().str.replace(' ', '', regex=False)
        df_merged = pd.merge(df, df_master_filtered, on='SKU_Norm', how='left')
    else:
        df_merged = df.copy()
        for col in ['ต้นทุน', 'ราคากล่อง', 'ค่าส่งเฉลี่ย', 'ค่าคอมมิชชั่น Admin', 'ค่าคอมมิชชั่น Telesale', 'Type']:
            df_merged[col] = 0

    if 'SKU_x' in df_merged.columns: df_merged.rename(columns={'SKU_x': 'SKU_Original'}, inplace=True)
    if 'SKU_y' in df_merged.columns: df_merged.rename(columns={'SKU_y': 'SKU_Master'}, inplace=True)
    if 'ชื่อสินค้า_y' in df_merged.columns: df_merged.rename(columns={'ชื่อสินค้า_y': 'ชื่อสินค้า_Master'}, inplace=True)
    if 'ชื่อสินค้า_x' in df_merged.columns: df_merged.rename(columns={'ชื่อสินค้า_x': 'ชื่อสินค้า'}, inplace=True)

    # Fallback Logic
    if not df_master_filtered.empty:
        df_master_root = df_master_filtered.copy()
        df_root_lookup = pd.merge(df[['SKU_Norm_Root']], df_master_root, left_on='SKU_Norm_Root', right_on='SKU_Norm', how='left')
        
        cols_to_fill = ['ต้นทุน', 'ราคากล่อง', 'ค่าส่งเฉลี่ย', 
                        'ค่าคอมมิชชั่น Admin', 'ค่าคอมมิชชั่น Telesale', 'Type']

        for col in cols_to_fill:
            if col in df_merged.columns and col in df_root_lookup.columns:
                df_merged[col] = df_merged[col].combine_first(df_root_lookup[col])
            elif col not in df_merged.columns and col in df_root_lookup.columns:
                df_merged[col] = df_root_lookup[col]

        root_name_map = df_master_filtered.set_index('SKU_Norm')['ชื่อสินค้า'].to_dict()
        df_merged['Name_Root'] = df_merged['SKU_Norm_Root'].map(root_name_map)
        
        if 'ชื่อสินค้า_Master' in df_merged.columns:
            df_merged['ชื่อสินค้า'] = df_merged['ชื่อสินค้า_Master'].combine_first(df_merged['Name_Root']).combine_first(df_merged['ชื่อสินค้า'])
        else:
            df_merged['ชื่อสินค้า'] = df_merged['Name_Root'].combine_first(df_merged['ชื่อสินค้า'])
    else:
        df_merged['Name_Root'] = df_merged['SKU_Norm_Root'] # Just use SKU as name if master missing

    # --- 4. CALCULATE COST ---
    numeric_cols = ['จำนวน', 'รายละเอียดยอดที่ชำระแล้ว', 'ต้นทุน', 'ราคากล่อง', 'ค่าส่งเฉลี่ย']
    for col in numeric_cols:
        if col in df_merged.columns:
            df_merged[col] = df_merged[col].apply(safe_float)
    
    df_merged['CAL_COST'] = df_merged['จำนวน'] * df_merged['ต้นทุน']
    df_merged['BOX_COST_PER_LINE'] = df_merged['ราคากล่อง'].fillna(0)
    df_merged['DELIV_COST_PER_LINE'] = df_merged['ค่าส่งเฉลี่ย'].fillna(0)

    def get_shipping_percent(row):
        courier = str(row.get('บริษัทขนส่ง', '')).strip()
        normalized_courier = normalize_courier_name(courier)
        if normalized_courier in row:
            return safe_float(row[normalized_courier])
        return safe_float(row.get('Standard Delivery - ส่งธรรมดาในประเทศ', 0))

    df_merged['SHIP_PERCENT'] = df_merged.apply(get_shipping_percent, axis=1)

    def calculate_cod_cost(row):
        payment = str(row.get('วิธีการชำระเงิน', '')).lower()
        is_cod = any(cod_term in payment for cod_term in ['cod', 'ปลายทาง'])
        if is_cod and row['SHIP_PERCENT'] > 0:
            return row['รายละเอียดยอดที่ชำระแล้ว'] * row['SHIP_PERCENT'] * 1.07
        return 0

    df_merged['CAL_COD_COST'] = df_merged.apply(calculate_cod_cost, axis=1)

    def calculate_role(row):
        work_type = str(row.get('ประเภทการทำงาน', '')).lower()
        creator = str(row.get('ผู้สร้างคำสั่งซื้อ', '')).lower()
        if 'admin' in work_type or 'แอดมิน' in work_type or 'admin' in creator: return 'Admin'
        if 'tele' in work_type or 'เทเล' in work_type or 'tele' in creator: return 'Telesale'
        return 'Unknown'

    df_merged['Calculated_Role'] = df_merged.apply(calculate_role, axis=1)

    com_admin = df_merged.get('ค่าคอมมิชชั่น Admin', 0).fillna(0).apply(safe_float)
    com_tele = df_merged.get('ค่าคอมมิชชั่น Telesale', 0).fillna(0).apply(safe_float)

    df_merged['CAL_COM_ADMIN'] = np.where((df_merged['Calculated_Role'] == 'Admin'), 
                                          df_merged['รายละเอียดยอดที่ชำระแล้ว'] * com_admin, 0)
    df_merged['CAL_COM_TELESALE'] = np.where((df_merged['Calculated_Role'] == 'Telesale'), 
                                             df_merged['รายละเอียดยอดที่ชำระแล้ว'] * com_tele, 0)

    df_merged['SKU_Main'] = df_merged['SKU_Norm_Root']
    df_merged['Display_Name'] = df_merged['ชื่อสินค้า']

    # --- AGGREGATE ---
    order_agg = {
        'Date': 'first',
        'SKU_Main': 'first',
        'ชื่อสินค้า': 'first',
        'จำนวน': 'sum',
        'รายละเอียดยอดที่ชำระแล้ว': 'sum',
        'CAL_COST': 'sum', 
        'BOX_COST_PER_LINE': 'max', 
        'DELIV_COST_PER_LINE': 'max',
        'CAL_COD_COST': 'sum',
        'CAL_COM_ADMIN': 'sum',
        'CAL_COM_TELESALE': 'sum',
        'Type': 'first'
    }

    df_order = df_merged.groupby('หมายเลขคำสั่งซื้อออนไลน์').agg(order_agg).reset_index()
    df_order.rename(columns={'BOX_COST_PER_LINE': 'BOX_COST', 'DELIV_COST_PER_LINE': 'DELIV_COST'}, inplace=True)

    # --- ADS ---
    df_ads_agg = pd.DataFrame(columns=['Date', 'SKU_Main', 'Ads_Amount'])
    if not df_ads_raw.empty:
        col_cost = next((c for c in ['จำนวนเงินที่ใช้จ่ายไป (THB)', 'Cost', 'Amount'] if c in df_ads_raw.columns), None)
        col_date = next((c for c in ['วัน', 'Date'] if c in df_ads_raw.columns), None)
        col_camp = next((c for c in ['ชื่อแคมเปญ', 'Campaign'] if c in df_ads_raw.columns), None)

        if col_cost and col_date and col_camp:
            df_ads_raw['Date'] = df_ads_raw[col_date].apply(safe_date)
            df_ads_raw = df_ads_raw.dropna(subset=['Date'])
            df_ads_raw[col_cost] = df_ads_raw[col_cost].apply(safe_float)
            df_ads_raw['SKU_Extracted'] = df_ads_raw[col_camp].astype(str).str.extract(r'\[(.*?)\]')
            df_ads_raw['SKU_Main'] = df_ads_raw['SKU_Extracted'].str.replace(' ', '', regex=False)
            
            df_ads_agg = df_ads_raw.groupby(['Date', 'SKU_Main'])[col_cost].sum().reset_index(name='Ads_Amount')

    # --- FINAL DAILY AGG ---
    daily_agg = {
        'ชื่อสินค้า': 'first',
        'จำนวนออเดอร์': 'count',
        'จำนวน': 'sum',
        'รายละเอียดยอดที่ชำระแล้ว': 'sum',
        'CAL_COST': 'sum',
        'BOX_COST': 'sum',
        'DELIV_COST': 'sum',
        'CAL_COD_COST': 'sum',
        'CAL_COM_ADMIN': 'sum',
        'CAL_COM_TELESALE': 'sum',
        'Type': 'first'
    }

    df_order_renamed = df_order.rename(columns={'หมายเลขคำสั่งซื้อออนไลน์': 'จำนวนออเดอร์'})
    df_daily = df_order_renamed.groupby(['Date', 'SKU_Main']).agg(daily_agg).reset_index()

    if not df_ads_agg.empty:
        df_daily = pd.merge(df_daily, df_ads_agg, on=['Date', 'SKU_Main'], how='outer')
    else: df_daily['Ads_Amount'] = 0

    df_daily = df_daily.fillna(0)
    df_daily['Other_Costs'] = df_daily['BOX_COST'] + df_daily['DELIV_COST'] + df_daily['CAL_COD_COST'] + df_daily['CAL_COM_ADMIN'] + df_daily['CAL_COM_TELESALE']
    df_daily['Total_Cost'] = df_daily['CAL_COST'] + df_daily['Other_Costs'] + df_daily['Ads_Amount']
    df_daily['Net_Profit'] = df_daily['รายละเอียดยอดที่ชำระแล้ว'] - df_daily['Total_Cost']

    df_daily['Date'] = pd.to_datetime(df_daily['Date'])
    df_daily['Year'] = df_daily['Date'].dt.year
    df_daily['Month_Num'] = df_daily['Date'].dt.month
    df_daily['Month_Thai'] = df_daily['Month_Num'].apply(lambda x: thai_months[x-1] if 1<=x<=12 else "")
    df_daily['Day'] = df_daily['Date'].dt.day
    df_daily['Date'] = df_daily['Date'].dt.date 

    # --- MAPPING ---
    sku_map = df_daily.groupby('SKU_Main')['ชื่อสินค้า'].last().to_dict()
    master_skus_set = set()
    if not df_master.empty and 'SKU' in df_master.columns:
        master_skus_set = set(df_master['SKU'].astype(str).str.strip().str.replace(' ', '', regex=False))
        if 'ชื่อสินค้า' in df_master.columns:
            temp_master = df_master.copy()
            temp_master['SKU_Norm'] = temp_master['SKU'].astype(str).str.strip().str.replace(' ', '', regex=False)
            sku_map.update(temp_master.set_index('SKU_Norm')['ชื่อสินค้า'].to_dict())
    
    daily_skus_set = set(df_daily['SKU_Main'].unique())
    sku_list = sorted(list(daily_skus_set.union(master_skus_set)))

    sku_type_map = {}
    if not df_master.empty and 'SKU' in df_master.columns and 'Type' in df_master.columns:
        temp_master = df_master.copy()
        temp_master['SKU_Norm'] = temp_master['SKU'].astype(str).str.strip().str.replace(' ', '', regex=False)
        sku_type_map = temp_master.set_index('SKU_Norm')['Type'].to_dict()
    
    if 'Type' in df_daily.columns:
        daily_type_map = df_daily.groupby('SKU_Main')['Type'].first().to_dict()
        for k, v in daily_type_map.items():
            if k not in sku_type_map:
                sku_type_map[k] = v
            elif pd.isna(sku_type_map[k]) or sku_type_map[k] == '':
                sku_type_map[k] = v

    return df_daily, df_fix_cost, sku_map, sku_list, sku_type_map
