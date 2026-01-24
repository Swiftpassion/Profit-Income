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

    # 4. SIDEBAR & NAVIGATION
    with st.sidebar:
        st.markdown(f"**👤 ผู้ใช้งาน:** Admin")
        
        # --- DATA SOURCE SWITCHER ---
        # st.markdown("### 🔌 Data Source")
        # mode = st.radio("เลือกแหล่งข้อมูล:", ["☁️ Google Drive", "💻 Local File System"], index=0)
        
        # if mode == "☁️ Google Drive":
        #     st.session_state.data_source_mode = "MODE_DRIVE"
        # else:
        #     st.session_state.data_source_mode = "MODE_LOCAL"
        st.session_state.data_source_mode = "MODE_LOCAL"  

        if st.button("🔄 รีเฟรชข้อมูลล่าสุด", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        
        st.link_button("📊 ชีทตั้งค่าทุนสินค้า", SHEET_MASTER_URL, use_container_width=True)

        if st.button("🚪 ออกจากระบบ", use_container_width=True):
             st.session_state.logged_in = False
             st.query_params.clear()
             st.rerun()

        st.markdown("---") 

    # 5. NAVIGATION (SIDEBAR)
    with st.sidebar:
        st.markdown("### 🧭 Navigation")
        page_options = [
            "📊 REPORT_MONTH", 
            "📢 REPORT_ADS", 
            "📅 REPORT_DAILY", 
            "📈 PRODUCT GRAPH", 
            "📈 YEARLY P&L", 
            "📅 MONTHLY P&L", 
            "💰 COMMISSION", 
            "📂 FILE MANAGER",
            "🔧 MASTER_ITEM"
        ]
        
        # Add File Manager if in Local Mode
        # if st.session_state.data_source_mode == "MODE_LOCAL":
        #     page_options.insert(0, "📂 FILE MANAGER")

        selected_page = st.radio("เลือกหน้าจอ:", page_options, label_visibility="collapsed")
    
    # 6. DATA LOADING
    # Don't load data for File Manager to save resources/errors if empty
    if selected_page == "📂 FILE MANAGER":
        p_files.show()
    else:
        # Load Data
        try:
            df_daily, df_fix_cost, sku_map, sku_list, sku_type_map = process_data(st.session_state.data_source_mode)
            
            if df_daily.empty and selected_page != "🔧 MASTER_ITEM": # Master item might work partially or show error handling internally
                st.warning(f"⚠️ ไม่พบข้อมูล ({st.session_state.data_source_mode})")
                if st.session_state.data_source_mode == "MODE_LOCAL":
                     st.info("กรุณาไปที่เมนู '📂 FILE MANAGER' เพื่ออัปโหลดไฟล์")
                st.stop()

            # Routing
            if selected_page == "📊 REPORT_MONTH":
                p_month.show(df_daily, df_fix_cost, sku_map, sku_list, sku_type_map)
            elif selected_page == "📢 REPORT_ADS":
                p_ads.show(df_daily, df_fix_cost, sku_map, sku_list, sku_type_map)
            elif selected_page == "📅 REPORT_DAILY":
                p_daily.show(df_daily, df_fix_cost, sku_map, sku_list, sku_type_map)
            elif selected_page == "📈 PRODUCT GRAPH":
                p_graph.show(df_daily, df_fix_cost, sku_map, sku_list, sku_type_map)
            elif selected_page == "📈 YEARLY P&L":
                p_yearly.show(df_daily, df_fix_cost, sku_map, sku_list, sku_type_map)
            elif selected_page == "📅 MONTHLY P&L":
                p_monthly.show(df_daily, df_fix_cost, sku_map, sku_list, sku_type_map)
            elif selected_page == "💰 COMMISSION":
                p_comm.show(df_daily, df_fix_cost, sku_map, sku_list, sku_type_map)
            elif selected_page == "🔧 MASTER_ITEM":
                p_master.show(df_daily, df_fix_cost, sku_map, sku_list, sku_type_map)
        
        except Exception as e:
            st.error(f"Error Loading Data: {e}")
            # st.exception(e) # Uncomment for debugging

except Exception as e:
    st.error(f"Application Error: {e}")
