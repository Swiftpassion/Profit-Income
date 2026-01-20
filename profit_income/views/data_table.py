import streamlit as st
from utils.db_service import fetch_orders

def render_data_table():
    st.subheader("📂 ตารางข้อมูลดิบ (Legacy)")
    try:
        # Use cached data
        res_df = fetch_orders()
        if not res_df.empty:
            st.dataframe(res_df, use_container_width=True, height=800)
        else: st.info("ไม่มีข้อมูล")
    except: pass
