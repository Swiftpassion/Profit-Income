
import streamlit as st
import pandas as pd
import os
from pathlib import Path
import shutil
from modules.data_loader import ingest_local_data_to_db, LOCAL_DATA_DIR
from modules.database import init_db

def show():
    if "uploader_key" not in st.session_state: st.session_state.uploader_key = 0
    st.markdown("## 📂 File Manager (Local Mode & Database)")
    st.info("หน้านี้สำหรับจัดการไฟล์และนำเข้าข้อมูลสู่ฐานข้อมูล (PostgreSQL)")

    # --- 0. DB INIT (Rescue Button) ---
    with st.expander("⚙️ Database Settings (Click if first time)", expanded=False):
        if st.button("🛠️ Initialize Database Schema"):
            try:
                init_db()
                st.success("Database Initialized Successfully!")
            except Exception as e:
                st.error(f"Error: {e}")

    st.markdown("---")

    # --- 1. SHOP MANAGEMENT ---
    st.subheader("1. จัดการร้านค้า (Shop Management)")
    
    if not LOCAL_DATA_DIR.exists():
        LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # List existing shops based on folders
    existing_shops = [d.name for d in LOCAL_DATA_DIR.iterdir() if d.is_dir() and d.name not in ["sales", "ads"]] # Exclude legacy folders if any
    
    c_shop_sel, c_shop_add = st.columns([2, 1])
    
    with c_shop_add:
        new_shop_name = st.text_input("สร้างร้านค้าใหม่ (ชื่อร้าน)", placeholder="Tiktok1").strip()
        if st.button("➕ เพิ่มร้านค้า") and new_shop_name:
            if new_shop_name in existing_shops:
                 st.error("มีร้านค้านี้อยู่แล้ว")
            else:
                 (LOCAL_DATA_DIR / new_shop_name / "sales").mkdir(parents=True, exist_ok=True)
                 (LOCAL_DATA_DIR / new_shop_name / "ads").mkdir(parents=True, exist_ok=True)
                 st.success(f"สร้างร้าน {new_shop_name} เรียบร้อย")
                 st.rerun()

    with c_shop_sel:
        selected_shop = st.selectbox("เลือกร้านค้าที่ต้องการจัดการไฟล์:", ["-- เลือกร้านค้า --"] + existing_shops)

    st.markdown("---")

    # --- 2. FILE UPLOAD (Per Shop) ---
    if selected_shop and selected_shop != "-- เลือกร้านค้า --":
        st.subheader(f"2. อัปโหลดไฟล์สำหรับ: {selected_shop}")
        
        current_shop_dir = LOCAL_DATA_DIR / selected_shop
        path_sales = current_shop_dir / "sales"
        path_ads = current_shop_dir / "ads"
        
        c1, c2 = st.columns(2)

        with c1:
            st.markdown(f"**🛒 Sales Data ({selected_shop})**")
            uploaded_sales = st.file_uploader(f"ไฟล์ยอดขาย {selected_shop}", type=['xlsx', 'xls', 'csv'], accept_multiple_files=True, key=f"up_sales_{selected_shop}_{st.session_state.uploader_key}")
            if uploaded_sales:
                for f in uploaded_sales:
                    save_path = path_sales / f.name
                    with open(save_path, "wb") as buffer:
                        shutil.copyfileobj(f, buffer)
                st.success(f"บันทึกไฟล์ยอดขาย {len(uploaded_sales)} ไฟล์")
                st.session_state.uploader_key += 1
                st.rerun()

            # List Files
            files = list(path_sales.iterdir())
            if files:
                st.markdown(f"*{len(files)} files found*")
                for f in files:
                    col_n, col_d = st.columns([0.8, 0.2])
                    col_n.text(f.name)
                    if col_d.button("🗑️", key=f"del_s_{selected_shop}_{f.name}"):
                        os.remove(f)
                        st.rerun()
            else: st.info("ยังไม่มีไฟล์ยอดขาย")

        with c2:
            st.markdown(f"**📢 Ads Data ({selected_shop})**")
            uploaded_ads = st.file_uploader(f"ไฟล์โฆษณา {selected_shop}", type=['xlsx', 'xls', 'csv'], accept_multiple_files=True, key=f"up_ads_{selected_shop}_{st.session_state.uploader_key}")
            if uploaded_ads:
                for f in uploaded_ads:
                    save_path = path_ads / f.name
                    with open(save_path, "wb") as buffer:
                        shutil.copyfileobj(f, buffer)
                st.success(f"บันทึกไฟล์โฆษณา {len(uploaded_ads)} ไฟล์")
                st.session_state.uploader_key += 1
                st.rerun()

            files = list(path_ads.iterdir())
            if files:
                st.markdown(f"*{len(files)} files found*")
                for f in files:
                    col_n, col_d = st.columns([0.8, 0.2])
                    col_n.text(f.name)
                    if col_d.button("🗑️", key=f"del_a_{selected_shop}_{f.name}"):
                        os.remove(f)
                        st.rerun()
            else: st.info("ยังไม่มีไฟล์โฆษณา")
            
        # Delete Shop Button
        st.markdown("---")
        if st.button(f"🗑️ ลบร้านค้า {selected_shop}", type="primary"):
            shutil.rmtree(current_shop_dir)
            st.warning(f"ลบร้านค้า {selected_shop} แล้ว")
            st.rerun()

    st.markdown("---")
    
    # --- 3. MASTER ITEM ---
    st.subheader("3. ไฟล์ตั้งค่าสินค้า (Master Item & Costs)")
    st.info("ไฟล์ Master Item (master_item.xlsx) ใช้ร่วมกันทุกร้านค้า")
    c3, c4 = st.columns([1, 1])
    with c3:
        uploaded_master = st.file_uploader("เลือกไฟล์ Master Item (xlsx)", type=['xlsx'], key="up_master")
        if uploaded_master:
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
                os.remove(master_path)
                st.rerun()
        else:
            st.warning("❌ Missing: master_item.xlsx")

    st.markdown("---")

    # --- 4. ACTION ---
    st.subheader("4. ประมวลผลและบันทึกลงฐานข้อมูล (Fetch Data)")
    c_fetch, _ = st.columns([1, 2])
    with c_fetch:
        if st.button("🚀 Fetch Data to Database", type="primary", use_container_width=True):
            status = st.status("⏳ กำลังประมวลผลข้อมูล...", expanded=True)
            with status:
                st.write("🔄 กำลังเตรียมฐานข้อมูล...")
                try:
                    ingest_local_data_to_db()
                    st.write("✅ บันทึกข้อมูลเรียบร้อย")
                    status.update(label="✅ เสร็จสิ้น!", state="complete", expanded=False)
                    
                    st.session_state.fetch_success_msg = "✅ นำเข้าข้อมูลสำเร็จ! ข้อมูลถูกบันทึกลงฐานข้อมูลแล้ว"
                    st.rerun()
                except Exception as e:
                    status.update(label="❌ เกิดข้อผิดพลาด", state="error", expanded=True)
                    st.error(f"Error: {e}")
    
    # Show success message if exists (and clear it)
    if "fetch_success_msg" in st.session_state:
        st.success(st.session_state.fetch_success_msg)
        del st.session_state.fetch_success_msg
