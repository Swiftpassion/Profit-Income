import streamlit as st
import pandas as pd
import os
from pathlib import Path
import shutil

LOCAL_DATA_DIR = Path("local_data")

def show():
    st.markdown("## 📂 File Manager (Local Mode)")
    st.info("หน้านี้สำหรับจัดการไฟล์เมื่อใช้งานโหมด **Local File System** ไฟล์จะถูกบันทึกไว้ในโฟลเดอร์ `local_data/`")

    # Create directories if not exist
    path_sales = LOCAL_DATA_DIR / "sales"
    path_ads = LOCAL_DATA_DIR / "ads"
    path_sales.mkdir(parents=True, exist_ok=True)
    path_ads.mkdir(parents=True, exist_ok=True)

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("🛒 Upload Sales Data")
        uploaded_sales = st.file_uploader("เลือกไฟล์ยอดขาย (xlsx, csv)", type=['xlsx', 'xls', 'csv'], accept_multiple_files=True, key="up_sales")
        if uploaded_sales:
            for f in uploaded_sales:
                save_path = path_sales / f.name
                with open(save_path, "wb") as buffer:
                    shutil.copyfileobj(f, buffer)
            st.success(f"บันทึกไฟล์ยอดขาย {len(uploaded_sales)} ไฟล์เรียบร้อยแล้ว")
            st.rerun()

        st.markdown("### 📄 Current Sales Files")
        files = list(path_sales.iterdir())
        if not files:
            st.write("- No files found")
        else:
            for f in files:
                c_name, c_del = st.columns([0.8, 0.2])
                c_name.write(f"📄 {f.name}")
                if c_del.button("❌", key=f"del_sales_{f.name}"):
                    try:
                        os.remove(f)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

    with c2:
        st.subheader("📢 Upload Ads Data")
        uploaded_ads = st.file_uploader("เลือกไฟล์ค่าโฆษณา (xlsx, csv)", type=['xlsx', 'xls', 'csv'], accept_multiple_files=True, key="up_ads")
        if uploaded_ads:
            for f in uploaded_ads:
                save_path = path_ads / f.name
                with open(save_path, "wb") as buffer:
                    shutil.copyfileobj(f, buffer)
            st.success(f"บันทึกไฟล์โฆษณา {len(uploaded_ads)} ไฟล์เรียบร้อยแล้ว")
            st.rerun()

        st.markdown("### 📄 Current Ads Files")
        files = list(path_ads.iterdir())
        if not files:
            st.write("- No files found")
        else:
            for f in files:
                c_name, c_del = st.columns([0.8, 0.2])
                c_name.write(f"📄 {f.name}")
                if c_del.button("❌", key=f"del_ads_{f.name}"):
                    try:
                        os.remove(f)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

    st.markdown("---")
    st.subheader("🔧 Master Item File (One file only: master_item.xlsx)")
    st.info("อัปโหลดไฟล์ `master_item.xlsx` เพื่อใช้เป็นข้อมูลต้นทุนและค่าคอมมิชชั่น")
    
    c3, c4 = st.columns([1, 1])
    
    with c3:
        uploaded_master = st.file_uploader("เลือกไฟล์ Master Item (xlsx)", type=['xlsx'], key="up_master")
        if uploaded_master:
            # Force filename to be master_item.xlsx
            save_path = LOCAL_DATA_DIR / "master_item.xlsx"
            with open(save_path, "wb") as buffer:
                shutil.copyfileobj(uploaded_master, buffer)
            st.success("บันทึกไฟล์ master_item.xlsx เรียบร้อยแล้ว")
            st.rerun()

    with c4:
        master_path = LOCAL_DATA_DIR / "master_item.xlsx"
        if master_path.exists():
            st.write(f"✅ Found: {master_path.name}")
            if st.button("❌ Delete Master Item", key="del_master"):
                try:
                    os.remove(master_path)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            st.warning("❌ Missing: master_item.xlsx")
