import streamlit as st
import pandas as pd
import sys
import os

# Add parent directory to path to allow importing modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import get_db
import services

st.set_page_config(page_title="Data Manager", page_icon="📂", layout="wide")

st.markdown("## 📂 จัดการข้อมูล (Data Manager)")
st.info("อัปโหลดไฟล์ Excel เพื่อนำเข้าข้อมูลสู่ระบบฐานข้อมูล")

# Tabs for different imports
tab1, tab2, tab3 = st.tabs(["📦 สินค้าหลัก (Master)", "🔢 สต็อกจริง (Actual Stock)", "🛒 ประวัติการขาย (Sales History)"])

# --- Tab 1: Master Product ---
with tab1:
    st.markdown("### 1. นำเข้าข้อมูลสินค้า (Master Product)")
    uploaded_master = st.file_uploader("เลือกไฟล์ Master Product (.xlsx)", type=['xlsx'], key="master")
    
    if uploaded_master:
        st.write("ตัวอย่างไฟล์:")
        try:
            preview = pd.read_excel(uploaded_master)
            st.dataframe(preview.head())
        except:
            st.error("อ่านไฟล์ไม่ได้")

        if st.button("🚀 Import Master Products", type="primary"):
            with st.spinner("กำลังนำเข้าข้อมูล..."):
                db = next(get_db())
                added, updated, error = services.import_master_products(uploaded_master, db)
                if error:
                    st.error(f"เกิดข้อผิดพลาด: {error}")
                else:
                    st.success(f"✅ นำเข้าสำเร็จ! เพิ่มใหม่: {added} รายการ, อัปเดต: {updated} รายการ")

# --- Tab 2: Actual Stock ---
with tab2:
    st.markdown("### 2. นำเข้ายอดสต็อกจริง (Actual Stock)")
    uploaded_stock = st.file_uploader("เลือกไฟล์ Stock (.xlsx)", type=['xlsx'], key="stock")
    
    if uploaded_stock:
        if st.button("🚀 Update Stock", type="primary"):
            with st.spinner("กำลังอัปเดตสต็อก..."):
                db = next(get_db())
                updated, error = services.import_actual_stock(uploaded_stock, db)
                if error:
                    st.error(f"เกิดข้อผิดพลาด: {error}")
                else:
                    st.success(f"✅ อัปเดตสต็อกสำเร็จ! ทั้งหมด: {updated} รายการ")

# --- Tab 3: Sales History ---
with tab3:
    st.markdown("### 3. นำเข้าประวัติการขาย (Sales History)")
    uploaded_sales = st.file_uploader("เลือกไฟล์ Sales (.xlsx)", type=['xlsx'], key="sales")
    
    if uploaded_sales:
        if st.button("🚀 Import Sales Data", type="primary"):
            with st.spinner("กำลังนำเข้าข้อมูลการขาย..."):
                db = next(get_db())
                added, error = services.import_sales_history(uploaded_sales, db)
                if error:
                    # In this case 'error' variable might contain the warning message about skipped items if not None
                    # But wait, services returns (count, msg). If execution failed, it returns (0, error_str).
                    # If execution succeeded but skipped items, it returns (count, warning_msg).
                    # So we should check if added > 0 or if it looks like a real error.
                    # Currently services logic: (0, error_str) on exception.
                    # (count, warning_msg) on success.
                    
                    # Ensure added is int
                    if isinstance(added, int):
                         st.success(f"✅ นำเข้าสำเร็จ! เพิ่มรายการขายใหม่: {added} รายการ")
                         if error: st.warning(f"⚠️ {error}")
                    else:
                         st.error(f"เกิดข้อผิดพลาด: {error}")
                else:
                    st.success(f"✅ นำเข้าสำเร็จ! เพิ่มรายการขายใหม่: {added} รายการ")
