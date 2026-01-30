
import pandas as pd
import numpy as np
import sys
import os

# Add project root to path
sys.path.append(r"c:\Users\Thana\OneDrive\เอกสาร\GitHub\Profit-Income")

# Mock Streamlit
import types
st_mock = types.ModuleType("streamlit")
st_mock.secrets = {}
st_mock.cache_data = lambda **kwargs: lambda func: func
sys.modules["streamlit"] = st_mock

from shop_dashboard.modules.data_loader import load_raw_files
from shop_dashboard.modules.processing import normalize_courier_name, safe_float

def debug_cod():
    print("Loading data...")
    try:
        df_data, df_ads, df_master, df_fix = load_raw_files("MODE_LOCAL")
        if df_data.empty:
            print("Local data empty, trying Drive...")
            df_data, df_ads, df_master, df_fix = load_raw_files("MODE_DRIVE")
    except Exception as e:
        print(f"Error loading data: {e}")
        return

    if df_data.empty:
        print("No data found!")
        return

    print(f"Data Loaded. Rows: {len(df_data)}")
    print(f"Master Loaded. Rows: {len(df_master)}")
    
    if 'วิธีการชำระเงิน' in df_data.columns:
        cod_mask = df_data['วิธีการชำระเงิน'].astype(str).str.lower().str.contains('cod|ปลายทาง', na=False, case=False)
        print(f"\nPotential COD orders found: {cod_mask.sum()}")
        
        if cod_mask.sum() > 0:
            df_test = df_data[cod_mask].head(5).copy()
            
            if 'รูปแบบสินค้า' in df_test.columns:
                df_test['SKU_Raw'] = df_test['รูปแบบสินค้า'].astype(str).str.strip()
                df_test['SKU_Norm'] = df_test['SKU_Raw'].str.replace(' ', '', regex=False)
            
            if not df_master.empty:
                df_master['SKU_Norm'] = df_master['SKU'].astype(str).str.strip().str.replace(' ', '', regex=False)
                df_merged = pd.merge(df_test, df_master, on='SKU_Norm', how='left')
            else:
                df_merged = df_test
            
            print("\n--- Simulation on COD Orders ---")
            for i, row in df_merged.iterrows():
                courier = str(row.get('บริษัทขนส่ง', '')).strip()
                norm_courier = normalize_courier_name(courier)
                
                ship_pct = 0
                if norm_courier in row:
                    val = row[norm_courier]
                    ship_pct = safe_float(val)
                
                print(f"Row {i}: Courier='{courier}' -> Norm='{norm_courier}'")
                print(f"  Merge Status: {'SKU Found' if 'SKU' in row else 'SKU Not Found in Master'}")
                print(f"  Col Found? {norm_courier in row} | Value: {row.get(norm_courier, 'MISSING')} | Pct: {ship_pct}")
                
    else:
        print("Column 'วิธีการชำระเงิน' missing!")

if __name__ == "__main__":
    debug_cod()
