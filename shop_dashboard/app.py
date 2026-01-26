try:
    import streamlit as st
    import modules.auth as auth
    import modules.ui_components as ui
    from modules.processing import process_data
    from modules.data_loader import FOLDER_ID_DATA, FOLDER_ID_ADS, SHEET_MASTER_URL

    # --- PAGES ---
    import views.report_month as p_month
    import views.report_ads as p_ads
    import views.report_daily as p_daily
    import views.product_graph as p_graph
    import views.yearly_pnl as p_yearly
    import views.monthly_pnl as p_monthly
    import views.commission as p_comm
    import views.master_item as p_master
    import views.file_manager as p_files

    # 1. CONFIG
    st.set_page_config(page_title="Shop Analytics Dashboard", layout="wide", page_icon="📊")

    # 2. AUTHENTICATION
    if not auth.require_auth():
        st.stop()

    # 3. CSS & UI
    ui.load_css()
    
    # Initialize session state for page
    if "current_page" not in st.session_state:
        st.session_state.current_page = "REPORT_MONTH"

    st.session_state.data_source_mode = "MODE_LOCAL" 

    # 5. NAVIGATION (SIDEBAR)
    with st.sidebar:
        st.markdown("### 🧭 เมนูหลัก")
        
        menu_items = {
            "REPORT_MONTH": "📊 รายงานภาพรวม", 
            "REPORT_ADS": "📢 รายงานค่าโฆษณา", 
            "REPORT_DAILY": "📅 รายงานรายวัน", 
            "PRODUCT_GRAPH": "📈 กราฟสินค้า", 
            "YEARLY_PNL": "📈 งบกำไรขาดทุน (ปี)", 
            "MONTHLY_PNL": "📅 งบกำไรขาดทุน (เดือน)", 
            "COMMISSION": "💰 ค่าคอมมิชชั่น", 
            "FILE_MANAGER": "📂 จัดการไฟล์",
            "MASTER_ITEM": "🔧 ตั้งค่าสินค้า (Master)"
        }
        
        for page_id, page_label in menu_items.items():
            # Highlight current page button
            btn_type = "primary" if st.session_state.current_page == page_id else "secondary"
            if st.button(page_label, key=f"nav_{page_id}", type=btn_type, use_container_width=True):
                st.session_state.current_page = page_id
                st.rerun()
                
        selected_page = st.session_state.current_page


    # 4. SIDEBAR & NAVIGATION (Bottom)
    with st.sidebar:
        st.markdown("---") 
        st.markdown(f"**👤 ผู้ใช้งาน:** Admin")        
        # --- DATA SOURCE SWITCHER ---
        # mode = st.radio("เลือกแหล่งข้อมูล:", ["☁️ Google Drive", "💻 Local File System"], index=0)
        
        if st.button("🔄 รีเฟรชข้อมูลล่าสุด", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        
        st.link_button("📊 ชีทตั้งค่าทุนสินค้า", SHEET_MASTER_URL, use_container_width=True)

        if st.button("🚪 ออกจากระบบ", use_container_width=True):
             st.session_state.logged_in = False
             st.query_params.clear()
             st.rerun()



    # 6. DATA LOADING
    # Don't load data for File Manager to save resources/errors if empty
    if selected_page == "FILE_MANAGER":
        p_files.show()
    else:
        # Load Data
        try:
            df_daily, df_fix_cost, sku_map, sku_list, sku_type_map = process_data(st.session_state.data_source_mode)
            
            if df_daily.empty and selected_page != "MASTER_ITEM": 
                st.warning(f"⚠️ ไม่พบข้อมูล ({st.session_state.data_source_mode})")
                if st.session_state.data_source_mode == "MODE_LOCAL":
                     st.info(f"กรุณาไปที่เมนู '{menu_items['FILE_MANAGER']}' เพื่ออัปโหลดไฟล์")
                st.stop()
            
            # --- SHOP FILTER ---
            all_shops = sorted(list(df_daily['Shop'].unique()))
            if "Unknown" in all_shops: all_shops.remove("Unknown")
            
            with st.sidebar:
                st.markdown("### 🏪 รู้านค้า (Shops)")
                # Default selects all
                if "selected_shops" not in st.session_state:
                    st.session_state.selected_shops = all_shops
                
                selected_shops = st.multiselect("เลือกร้านค้า:", all_shops, default=all_shops)
                # If nothing selected, show warning or nothing?
                if not selected_shops:
                    st.warning("กรุณาเลือกร้านค้าอย่างน้อย 1 ร้าน")
                    st.stop()
            
            # Filter Data
            mask_shop = df_daily['Shop'].isin(selected_shops)
            df_daily_filtered = df_daily[mask_shop]
            
            # Pass filtered data to views
            df_daily = df_daily_filtered

            # Routing
            if selected_page == "REPORT_MONTH":
                p_month.show(df_daily, df_fix_cost, sku_map, sku_list, sku_type_map)
            elif selected_page == "REPORT_ADS":
                p_ads.show(df_daily, df_fix_cost, sku_map, sku_list, sku_type_map)
            elif selected_page == "REPORT_DAILY":
                p_daily.show(df_daily, df_fix_cost, sku_map, sku_list, sku_type_map)
            elif selected_page == "PRODUCT_GRAPH":
                p_graph.show(df_daily, df_fix_cost, sku_map, sku_list, sku_type_map)
            elif selected_page == "YEARLY_PNL":
                p_yearly.show(df_daily, df_fix_cost, sku_map, sku_list, sku_type_map)
            elif selected_page == "MONTHLY_PNL":
                p_monthly.show(df_daily, df_fix_cost, sku_map, sku_list, sku_type_map)
            elif selected_page == "COMMISSION":
                p_comm.show(df_daily, df_fix_cost, sku_map, sku_list, sku_type_map)
            elif selected_page == "MASTER_ITEM":
                p_master.show(df_daily, df_fix_cost, sku_map, sku_list, sku_type_map)
        
        except Exception as e:
            st.error(f"Error Loading Data: {e}")
            # st.exception(e) # Uncomment for debugging

except Exception as e:
    st.error(f"Application Error: {e}")
