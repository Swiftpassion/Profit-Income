import streamlit as st
import pandas as pd
from utils.db_service import get_product_costs, save_product_costs

def render_costs():
    st.subheader("💰 จัดการต้นทุน")
    try:
        cur_data = get_product_costs()
        if cur_data.empty:
            cur_data = pd.DataFrame(columns=['sku', 'unit_cost'])
        for c in ['sku', 'unit_cost']:
            if c not in cur_data.columns:
                cur_data[c] = None

        display_df = cur_data[['sku', 'unit_cost']].copy()

        col_c_btn, col_c_info = st.columns([2, 5])
        with col_c_btn:
            save_cost_clicked = st.button("💾 บันทึกต้นทุนสินค้า", type="primary", use_container_width=True)
        with col_c_info:
            st.info("ต้นทุนผูกกับ SKU เท่านั้น (ใช้ร่วมกันทุกแพลตฟอร์ม)")

        edited = st.data_editor(
            display_df,
            column_config={
                "sku": st.column_config.TextColumn("รหัสสินค้า (SKU)", required=True),
                "unit_cost": st.column_config.NumberColumn("ต้นทุน (บาท)", format="%.2f", min_value=0),
            },
            hide_index=True, num_rows="dynamic", use_container_width=True, height=1000,
        )

        if save_cost_clicked and not edited.empty:
            edited = edited.dropna(subset=['sku']).copy()
            edited['sku'] = edited['sku'].astype(str).str.strip().str.upper()
            edited = edited[edited['sku'] != ''].drop_duplicates(subset=['sku'], keep='last')
            save_product_costs(edited[['sku', 'unit_cost']], replace=True)
            st.cache_data.clear()
            st.success("✅ บันทึกต้นทุนสำเร็จ!")
            st.rerun()
    except Exception as e:
        st.error(f"Error Cost: {e}")
