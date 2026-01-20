import streamlit as st
import pandas as pd
from utils.db_service import get_product_costs, save_product_costs

def render_costs():
    st.subheader("💰 จัดการต้นทุน")
    try:
        # Use cached loader (or fresh)
        cur_data = get_product_costs()
        if cur_data.empty: cur_data = pd.DataFrame(columns=['sku', 'platform', 'unit_cost'])
        # Ensure columns exist
        for c in ['sku', 'unit_cost', 'platform']:
            if c not in cur_data.columns: cur_data[c] = None
            
        display_df = cur_data[['sku', 'unit_cost', 'platform']].copy()
        
        col_c_btn, col_c_info = st.columns([2, 5])
        with col_c_btn: save_cost_clicked = st.button("💾 บันทึกต้นทุนสินค้า", type="primary", use_container_width=True)
        with col_c_info: st.info("สามารถใส่รายการสินค้าทุกแพลตฟอร์มลงในตารางด้านล่างได้เลย")
        
        edited = st.data_editor(display_df, column_config={"sku": st.column_config.TextColumn("รหัสสินค้า (SKU)", required=True), "unit_cost": st.column_config.NumberColumn("ต้นทุน (บาท)", format="%.2f", min_value=0), "platform": st.column_config.TextColumn("แพลตฟอร์ม", disabled=True)}, hide_index=True, num_rows="dynamic", use_container_width=True, height=1000)
        
        if save_cost_clicked:
            if not edited.empty:
                edited['sku'] = edited['sku'].astype(str).str.strip().str.upper()
                save_product_costs(edited, replace=True)
                # Clear cache
                # get_product_costs.clear()
                st.cache_data.clear()
                st.success("✅ บันทึกต้นทุนสำเร็จ!")
                st.rerun()
    except Exception as e: st.error(f"Error Cost: {e}")
