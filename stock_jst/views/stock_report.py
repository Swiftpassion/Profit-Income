import streamlit as st
import pandas as pd
from utils.data_utils import get_stock_from_sheet, get_sale_from_folder, get_po_data, get_actual_stock_from_folder, update_master_limits

def show_stock_report():
    # 🟢 LAZY LOADING FOR STOCK REPORT
    with st.spinner('กำลังโหลดข้อมูล Stock...'):
        df_master = get_stock_from_sheet()
        df_po = get_po_data()
        df_sale = get_sale_from_folder()
        df_real_stock = get_actual_stock_from_folder()

        if not df_master.empty: df_master['Product_ID'] = df_master['Product_ID'].astype(str)
        if not df_po.empty: df_po['Product_ID'] = df_po['Product_ID'].astype(str)
        if not df_sale.empty: df_sale['Product_ID'] = df_sale['Product_ID'].astype(str)

        recent_sales_map = {}
        if not df_sale.empty and 'Date_Only' in df_sale.columns:
            max_date = df_sale['Date_Only'].max()
            df_latest_sale = df_sale[df_sale['Date_Only'] == max_date]
            recent_sales_map = df_latest_sale.groupby('Product_ID')['Qty_Sold'].sum().fillna(0).astype(int).to_dict()

    st.subheader("📈 รายงาน Stock & ตั้งค่าการเตือน")
    
    if not df_master.empty and 'Product_ID' in df_master.columns:
        if not df_po.empty and 'Product_ID' in df_po.columns:
            df_po_latest = df_po.drop_duplicates(subset=['Product_ID'], keep='last')
            df_stock_report = pd.merge(df_master, df_po_latest, on='Product_ID', how='left')
        else:
            df_stock_report = df_master.copy()
            df_stock_report['PO_Number'] = ""
        
        total_sales_map = {}
        if not df_sale.empty and 'Product_ID' in df_sale.columns:
            total_sales_map = df_sale.groupby('Product_ID')['Qty_Sold'].sum().fillna(0).astype(int).to_dict()
        
        df_stock_report['Recent_Sold'] = df_stock_report['Product_ID'].map(recent_sales_map).fillna(0).astype(int)
        df_stock_report['Total_Sold_All'] = df_stock_report['Product_ID'].map(total_sales_map).fillna(0).astype(int)
        
        if 'Initial_Stock' not in df_stock_report.columns: df_stock_report['Initial_Stock'] = 0
        
        df_stock_report['Calculated_Stock'] = df_stock_report['Initial_Stock'] - df_stock_report['Recent_Sold']
        
        if not df_real_stock.empty:
            real_stock_map = df_real_stock.set_index('Product_ID')['Real_Stock'].to_dict()
            df_stock_report['Real_Stock_File'] = df_stock_report['Product_ID'].map(real_stock_map)
            
            df_stock_report['Current_Stock'] = df_stock_report.apply(
                lambda x: x['Real_Stock_File'] if pd.notna(x['Real_Stock_File']) else x['Calculated_Stock'], 
                axis=1
            )
            df_stock_report['Source'] = df_stock_report['Real_Stock_File'].apply(lambda x: "✅ ไฟล์จริง" if pd.notna(x) else "🧮 คำนวณ")
        else:
            df_stock_report['Current_Stock'] = df_stock_report['Calculated_Stock']
            df_stock_report['Source'] = "🧮 คำนวณ"

        df_stock_report['Current_Stock'] = pd.to_numeric(df_stock_report['Current_Stock'], errors='coerce').fillna(0).astype(int)

        if 'Min_Limit' not in df_stock_report.columns:
            df_stock_report['Min_Limit'] = 0
            
        df_stock_report['Min_Limit'] = pd.to_numeric(df_stock_report['Min_Limit'], errors='coerce').fillna(0).astype(int)

        def calc_status(row):
            current = row['Current_Stock']
            limit = row['Min_Limit']
            
            if current <= 0:
                return "🔴 หมดเกลี้ยง" 
            elif current <= limit: 
                return "⚠️ ของใกล้หมด"
            else:
                return "🟢 มีของ"

        df_stock_report['Status'] = df_stock_report.apply(calc_status, axis=1)

        with st.container(border=True):
            col_filter, col_search, col_reset = st.columns([2, 2, 0.5])
            with col_filter: 
                selected_status = st.multiselect("ตัวกรองสถานะ", options=["🔴 หมดเกลี้ยง", "⚠️ ของใกล้หมด", "🟢 มีของ"], default=[])
            with col_search: 
                search_text = st.text_input("🔍 ค้นหา", value="")
            with col_reset:
                if st.button("❌", use_container_width=True): st.rerun()

        edit_df = df_stock_report.copy()
        if selected_status: 
            edit_df = edit_df[edit_df['Status'].isin(selected_status)]
        if search_text: 
            edit_df = edit_df[edit_df['Product_Name'].str.contains(search_text, case=False) | edit_df['Product_ID'].str.contains(search_text, case=False)]

        final_cols = ["Product_ID", "Image", "Product_Name", "Current_Stock", "Status", "Min_Limit", "Note"]
        
        for c in final_cols:
            if c not in edit_df.columns: edit_df[c] = "" 

        # Logic: Pull Edited Data for Save
        df_for_save = edit_df.copy()
        
        if "stock_editor_key" in st.session_state:
            edits = st.session_state["stock_editor_key"].get("edited_rows", {})
            for row_idx, col_changes in edits.items():
                for col_name, new_value in col_changes.items():
                    try:
                        col_idx = df_for_save.columns.get_loc(col_name)
                        df_for_save.iloc[int(row_idx), col_idx] = new_value
                    except: pass

        col_btn1, col_btn2 = st.columns([3, 1])
        with col_btn1:
            st.info(f"📋 แสดงผลทั้งหมด **{len(edit_df)}** รายการ (แก้ไขจุดเตือนในตาราง แล้วกดบันทึก)")
        with col_btn2:
            if st.button("💾 บันทึกค่าจุดเตือน", type="primary", use_container_width=True):
                update_master_limits(df_for_save)
                st.rerun()

        st.data_editor(
            edit_df[final_cols],
            column_config={
                "Image": st.column_config.ImageColumn("รูป", width=60),
                "Product_ID": st.column_config.TextColumn("รหัส", disabled=True),
                "Product_Name": st.column_config.TextColumn("ชื่อสินค้า", disabled=True, width="medium"),
                "Current_Stock": st.column_config.NumberColumn("คงเหลือ", disabled=True),
                "Status": st.column_config.TextColumn("สถานะ", disabled=True),
                "Min_Limit": st.column_config.NumberColumn("🔔 จุดเตือน (แก้ไขได้)", min_value=0, step=1, required=True),
                "Note": st.column_config.TextColumn("📝 หมายเหตุ", required=False, width="medium"),
            },
            height=1500,  
            use_container_width=True, 
            hide_index=True, 
            key="stock_editor_key" 
        )

    else: st.warning("ไม่พบข้อมูล Master Product")
