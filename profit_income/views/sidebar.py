import streamlit as st
import pandas as pd
from utils.local_file_manager import list_local_files, read_file
from utils.db_service import save_orders, get_product_costs, fetch_orders
from utils.processors import process_tiktok, process_shopee, process_lazada
from utils.common import get_standard_status
from views.file_manager import render_file_manager

def render_sidebar():
    # Helper to clean numeric
    def clean_numeric_col(df, cols):
        for c in cols:
            if c in df.columns: 
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
            else: 
                df[c] = 0.0
        return df

    with st.sidebar:
        st.header("🔄 ระบบดึงข้อมูล")
        st.caption("Local File > PostgreSQL")
        
        st.markdown("---")
        
        with st.expander("🛠️ เครื่องมือ Sync", expanded=True):
            start_sync = st.button("🚀 Sync Data (ล้างเก่าลงใหม่)", type="primary", use_container_width=True)
            
            if start_sync:
                status_box = st.empty()
                status_box.info("⏳ กำลังอ่านไฟล์จากเครื่อง...")
                
                # Shops Structure
                shops = {
                    'TIKTOK': ['TIKTOK 1', 'TIKTOK 2', 'TIKTOK 3'], 
                    'SHOPEE': ['SHOPEE 1', 'SHOPEE 2', 'SHOPEE 3'], 
                    'LAZADA': ['LAZADA 1', 'LAZADA 2', 'LAZADA 3']
                }
                
                all_data = []
                for platform, shop_list in shops.items():
                    # Income files: Assume platform/Income (not per shop, or all in one folder)
                    # We pass all Income files for the platform to the processor, which merges by Order ID.
                    inc_files = list_local_files(platform, 'Income')
                    
                    for shop_name in shop_list:
                        status_box.text(f"กำลังโหลด: {shop_name} ({platform})...")
                        
                        # Orders: Look for specific shop subfolder
                        order_files = list_local_files(platform, 'Orders', shop_name)
                        
                        if not order_files:
                            # Optional: Warn user if folder missing or empty
                            # But keep it clean
                            pass
                            
                        df_res = pd.DataFrame()
                        if platform == 'TIKTOK': 
                            df_res = process_tiktok(order_files, inc_files, shop_name)
                        elif platform == 'SHOPEE': 
                            df_res = process_shopee(order_files, inc_files, shop_name)
                        elif platform == 'LAZADA': 
                            df_res = process_lazada(order_files, inc_files, shop_name)
                            
                        if not df_res.empty: 
                            all_data.append(df_res)

                if all_data:
                    status_box.text("📊 กำลังประมวลผล...")
                    master_df = pd.concat(all_data, ignore_index=True)
                    
                    # Numeric Convert
                    master_df = clean_numeric_col(master_df, ['quantity', 'sales_amount', 'settlement_amount', 'fees', 'affiliate', 'unit_cost'])

                    # --- PRO-RATE LOGIC ---
                    totals = master_df.groupby('order_id')['sales_amount'].transform('sum')
                    ratio = master_df['sales_amount'] / totals.replace(0, 1)
                    master_df['settlement_amount'] *= ratio
                    master_df['fees'] *= ratio
                    master_df['affiliate'] *= ratio
                    
                    # Cost Mapping
                    # Use db_service.get_product_costs instead of load_cost_data
                    cost_df = get_product_costs()
                    if not cost_df.empty:
                        master_df = pd.merge(master_df, cost_df, on=['sku', 'platform'], how='left')
                        if 'unit_cost_y' in master_df.columns:
                            master_df['unit_cost'] = master_df['unit_cost_y'].fillna(0)
                            master_df = master_df.drop(columns=['unit_cost_x', 'unit_cost_y'], errors='ignore')
                    
                    master_df['unit_cost'] = master_df['unit_cost'].fillna(0)
                    master_df['total_cost'] = master_df['quantity'] * master_df['unit_cost']
                    master_df['net_profit'] = master_df['settlement_amount'] - master_df['total_cost']
                    master_df['status'] = master_df.apply(get_standard_status, axis=1)

                    if 'product_name' not in master_df.columns: master_df['product_name'] = "-"
                    master_df['product_name'] = master_df['product_name'].fillna("-")

                    # Date to String for DB
                    for c in ['created_date', 'shipped_date', 'settlement_date']:
                        if c in master_df.columns: 
                            master_df[c] = master_df[c].astype(str).replace({'nan': None, 'None': None, 'NaT': None})
                    
                    # Upload to Database
                    status_box.text("☁️ บันทึกลงฐานข้อมูล...")
                    cols = ['order_id', 'status', 'sku', 'product_name', 'quantity', 'sales_amount', 'settlement_amount', 'fees', 'affiliate', 'net_profit', 'total_cost', 'unit_cost', 'settlement_date', 'created_date', 'shipped_date', 'tracking_id', 'shop_name', 'platform']
                    master_df = master_df[[c for c in cols if c in master_df.columns]]
                    master_df = master_df.drop_duplicates(subset=['order_id', 'sku'], keep='first')

                    try:
                        save_orders(master_df, replace=True) 
                        status_box.success(f"✅ Sync สำเร็จ! ({len(master_df)} รายการ)")
                        
                        # Clear cache if any
                        # fetch_orders.clear() # If we used cache decoration
                        st.cache_data.clear()
                        
                        st.rerun()
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาดในการบันทึก: {e}")
                else:
                    status_box.warning("⚠️ ไม่พบข้อมูลไฟล์ (ตรวจสอบโฟลเดอร์ data)")

        st.markdown("---")
        
        with st.expander("📂 จัดการไฟล์ (File Manager)", expanded=False):
            render_file_manager()

