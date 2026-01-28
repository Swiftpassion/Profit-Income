import streamlit as st
import os
import pandas as pd
import datetime
from utils.local_file_manager import list_local_files, save_uploaded_file, delete_file, get_file_info
from utils.db_service import save_orders, get_product_costs, get_all_shops, add_shop, delete_shop
from utils.processors import process_tiktok, process_shopee, process_lazada
from utils.common import get_standard_status

def render_file_manager():
    st.header("📂 จัดการไฟล์และซิงค์ข้อมูล")

    # --- 0. FETCH DYNAMIC SHOPS ---
    # Fetch shops from DB
    shops_df = get_all_shops()
    
    # Convert to dict structure: {'TIKTOK': ['Shop1', 'Shop2'], ...}
    shops_map = {}
    if not shops_df.empty:
        for platform, group in shops_df.groupby('platform'):
            shops_map[platform] = group['shop_name'].tolist()
    
    # Ensure all platforms exist in map even if empty
    for p in ['TIKTOK', 'SHOPEE', 'LAZADA']:
        if p not in shops_map: shops_map[p] = []

    # --- LAYOUT: 2 Columns ---
    col_left, col_right = st.columns(2, gap="large")
    
    with col_left:
        st.subheader("🛠️ การจัดการ (Management)")
        
        # --- 0.1 SHOP MANAGEMENT UI ---
        with st.expander("🏠 จัดการร้านค้า (Shop Management)", expanded=True):
            col_s1, col_s2, col_s3 = st.columns([2, 2, 1])
            with col_s1:
                new_shop_name = st.text_input("ชื่อร้านค้าใหม่", key="new_shop_name")
            with col_s2:
                new_shop_plat = st.selectbox("แพลตฟอร์ม", ["TIKTOK", "SHOPEE", "LAZADA"], key="new_shop_plat")
            with col_s3:
                st.write("")
                st.write("")
                if st.button("เพิ่ม", type="primary", use_container_width=True):
                    if new_shop_name:
                        success, msg = add_shop(new_shop_name, new_shop_plat)
                        if success:
                            st.success(f"เพิ่ม {new_shop_name} สำเร็จ")
                            st.rerun()
                        else:
                            st.error(f"Error: {msg}")
                    else:
                        st.error("ระบุชื่อร้าน")
            
            st.markdown("###### รายชื่อร้านค้า")
            if not shops_df.empty:
                # Scrollable area for shops if too many?
                # For now just list them
                for i, row in shops_df.iterrows():
                    c1, c2, c3 = st.columns([2, 2, 1])
                    with c1: st.text(row['shop_name'])
                    with c2: st.caption(row['platform'])
                    with c3:
                        if st.button("ลบ", key=f"del_shop_{i}"):
                            delete_shop(row['shop_name'], row['platform'])
                            st.rerun()
            else:
                st.info("ยังไม่มีร้านค้าในระบบ")

        # --- 0.2 SYNC TOOLS ---
        with st.expander("🔄 เครื่องมือ Sync (ดึงข้อมูลเข้า DB)", expanded=True):
            st.info("อ่านไฟล์จากเครื่อง -> ประมวลผล -> ลงฐานข้อมูล")
            
            # Helper to clean numeric
            def clean_numeric_col(df, cols):
                for c in cols:
                    if c in df.columns: 
                        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
                    else: 
                        df[c] = 0.0
                return df

            start_sync = st.button("🚀 Sync Data (ล้างเก่าลงใหม่)", type="primary", use_container_width=True)
            
            if start_sync:
                status_box = st.empty()
                status_box.info("⏳ กำลังอ่านไฟล์จากเครื่อง...")
                
                # Use Dynamic Shops Map
                # shops_map is already prepared above
                
                all_data = []
                for platform, shop_list in shops_map.items():
                    if not shop_list: continue 
                    
                    # Income files: Assume platform/Income
                    inc_files = list_local_files(platform, 'Income')
                    
                    for shop_name in shop_list:
                        status_box.text(f"กำลังโหลด: {shop_name} ({platform})...")
                        
                        # Orders: Look for specific shop subfolder
                        order_files = list_local_files(platform, 'Orders', shop_name)
                        
                        if not order_files:
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
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาดในการบันทึก: {e}")
                else:
                    status_box.warning("⚠️ ไม่พบข้อมูลไฟล์ (ตรวจสอบโฟลเดอร์ data)")
        
        st.markdown("---")



    # --- RIGHT COLUMN ---
    with col_right:

        # --- 1. CONFIGURATION (Top Level) ---
        st.subheader("⚙️ เลือกร้านค้าเพื่ออัปโหลด")
        # Platform Selector
        platform = st.selectbox("เลือกแพลตฟอร์ม", ["TIKTOK", "SHOPEE", "LAZADA"], key="fm_platform")
        
        # Shop Selector (Always visible for context)
        # Use Dynamic Map
        shop_list = shops_map.get(platform, [])
        if not shop_list:
            st.warning(f"ยังไม่มีร้านค้าใน {platform} กรุณาเพิ่มร้านค้าก่อน")
            shop_name = None
        else:
            shop_name = st.selectbox("เลือกร้านค้า (สำหรับ Orders)", shop_list, key="fm_shop_order")
        
        # --- 2. UPLOAD SECTIONS (Collapsible) ---
        
        # Initialize session state for uploaders if not exists
        if "upl_orders_key" not in st.session_state: st.session_state["upl_orders_key"] = 0
        if "upl_income_key" not in st.session_state: st.session_state["upl_income_key"] = 0

        # Orders Upload
        with st.expander(f"📦 อัปโหลดไฟล์คำสั่งซื้อ (Orders)", expanded=True):
            if shop_name:
                # Use dynamic key
                order_key = f"upl_orders_{st.session_state['upl_orders_key']}"
                uploaded_orders = st.file_uploader(
                    f"เลือกไฟล์ Order -> {shop_name}", 
                    accept_multiple_files=True,
                    type=['xlsx', 'xls', 'csv'],
                    key=order_key
                )
                if uploaded_orders:
                    if st.button("บันทึก Orders", type="primary", key="btn_save_orders"):
                        count = 0
                        for uf in uploaded_orders:
                            save_uploaded_file(uf, platform, 'Orders', shop_name)
                            count += 1
                        st.success(f"บันทึกไฟล์สำเร็จ {count} ไฟล์!")
                        
                        # Reset uploader by changing key
                        st.session_state["upl_orders_key"] += 1
                        st.rerun()
            else:
                st.info("กรุณาเลือกร้านค้าก่อน")

        # Income Upload
        with st.expander(f"💰 อัปโหลดไฟล์รายรับ (Income)", expanded=True):
            st.caption("ไฟล์ Income ใช้ร่วมกันทุกร้านค้าในแพลตฟอร์มนี้")
            
            income_key = f"upl_income_{st.session_state['upl_income_key']}"
            uploaded_income = st.file_uploader(
                f"เลือกไฟล์ Income -> {platform}", 
                accept_multiple_files=True,
                type=['xlsx', 'xls', 'csv'],
                key=income_key
            )
            if uploaded_income:
                if st.button("บันทึก Income", type="primary", key="btn_save_income"):
                    count = 0
                    for uf in uploaded_income:
                        save_uploaded_file(uf, platform, 'Income', None)
                        count += 1
                    st.success(f"บันทึกไฟล์สำเร็จ {count} ไฟล์!")
                    
                    # Reset uploader by changing key
                    st.session_state["upl_income_key"] += 1
                    st.rerun()

        st.subheader("📂 รายการไฟล์ในระบบ (File List)")
        st.info(f"รายการไฟล์สำหรับ: {platform} / {shop_name if shop_name else '-'}")

        def show_file_table(files, key_prefix, title):
            st.caption(title)
            if not files:
                st.markdown(f"*{title}: - ไม่มีไฟล์ -*")
                return

            data = []
            for f in files:
                info = get_file_info(f)
                if info:
                    data.append({
                        "Select": False,
                        "Filename": info['name'],
                        "Size (MB)": round(info['size_mb'], 2),
                        "Modified": datetime.datetime.fromtimestamp(info['modified']).strftime('%Y-%m-%d %H:%M'),
                        "path": info['path'] # Hidden
                    })
            
            if not data: return

            df = pd.DataFrame(data)
            
            # Display Data Editor
            edited_df = st.data_editor(
                df,
                column_config={
                    "Select": st.column_config.CheckboxColumn("เลือก", width="small"),
                    "Filename": st.column_config.TextColumn("ชื่อไฟล์", width="medium", disabled=True),
                    "Size (MB)": st.column_config.NumberColumn("MB", format="%.2f", disabled=True),
                    "Modified": st.column_config.TextColumn("วันที่", disabled=True),
                    "path": None 
                },
                hide_index=True,
                use_container_width=True,
                key=f"editor_{key_prefix}"
            )
            
            # Delete Button
            to_delete = edited_df[edited_df['Select'] == True]
            if not to_delete.empty:
                if st.button(f"🗑️ ลบ {len(to_delete)} ไฟล์", key=f"btn_del_{key_prefix}", type="primary"):
                    for _, row in to_delete.iterrows():
                        delete_file(row['path'])
                    st.toast("ลบไฟล์สำเร็จ!")
                    # Small delay or rerun
                    st.rerun()
            st.write("") # Spacer

        # Show Orders Table
        if shop_name:
            files_ord = list_local_files(platform, 'Orders', shop_name)
            show_file_table(files_ord, "orders", f"📦 ไฟล์ Orders: {shop_name}")
        else:
             st.caption("📦 ไฟล์ Orders: กรุณาเลือกร้านค้า")

        st.markdown("---")
        
        # Show Income Table
        files_inc = list_local_files(platform, 'Income', None)
        show_file_table(files_inc, "income", f"💰 ไฟล์ Income: {platform}")
