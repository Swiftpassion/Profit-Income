import streamlit as st
import os
import pandas as pd
import datetime
from utils.local_file_manager import list_local_files, save_uploaded_file, delete_file, get_file_info

def render_file_manager():
    # --- 1. CONFIGURATION (Top Level) ---
    # Platform Selector
    platform = st.selectbox("เลือกแพลตฟอร์ม", ["TIKTOK", "SHOPEE", "LAZADA"], key="fm_platform")
    
    # Shop Selector (Always visible for context)
    shops_map = {
        'TIKTOK': ['TIKTOK 1', 'TIKTOK 2', 'TIKTOK 3'], 
        'SHOPEE': ['SHOPEE 1', 'SHOPEE 2', 'SHOPEE 3'], 
        'LAZADA': ['LAZADA 1', 'LAZADA 2', 'LAZADA 3']
    }
    shop_list = shops_map.get(platform, [])
    shop_name = st.selectbox("เลือกร้านค้า (สำหรับ Orders)", shop_list, key="fm_shop_order")
    
    st.markdown("---")

    # --- 2. UPLOAD SECTIONS (Collapsible) ---
    
    # Initialize session state for uploaders if not exists
    if "upl_orders_key" not in st.session_state: st.session_state["upl_orders_key"] = 0
    if "upl_income_key" not in st.session_state: st.session_state["upl_income_key"] = 0

    # Orders Upload
    with st.expander(f"📦 อัปโหลดไฟล์คำสั่งซื้อ (Orders)", expanded=False):
        # Use dynamic key
        order_key = f"upl_orders_{st.session_state['upl_orders_key']}"
        uploaded_orders = st.file_uploader(
            f"เลือกไฟล์ Order (.xlsx, .csv) -> {shop_name}", 
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

    # Income Upload
    with st.expander(f"💰 อัปโหลดไฟล์รายรับ (Income)", expanded=False):
        st.caption("ไฟล์ Income ใช้ร่วมกันทุกร้านค้าในแพลตฟอร์มนี้")
        
        income_key = f"upl_income_{st.session_state['upl_income_key']}"
        uploaded_income = st.file_uploader(
            f"เลือกไฟล์ Income (.xlsx, .csv) -> {platform}", 
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

    st.markdown("---")

    # --- 3. FILE LISTS (Visible Tables) ---
    
    def show_file_table(files, key_prefix, title):
        st.caption(title)
        if not files:
            st.info("- ไม่มีไฟล์ -")
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
            if st.button(f"ลบ {len(to_delete)} ไฟล์ ({key_prefix})", key=f"btn_del_{key_prefix}", type="primary"):
                for _, row in to_delete.iterrows():
                    delete_file(row['path'])
                st.toast("ลบไฟล์สำเร็จ!")
                # Small delay or rerun
                st.rerun()
        st.write("") # Spacer

    # Show Orders Table
    files_ord = list_local_files(platform, 'Orders', shop_name)
    show_file_table(files_ord, "orders", f"📑 ไฟล์ Orders: {shop_name}")

    # Show Income Table
    files_inc = list_local_files(platform, 'Income', None)
    show_file_table(files_inc, "income", f"📑 ไฟล์ Income: {platform}")
