import streamlit as st
import pandas as pd
import gspread
from modules.data_loader import get_drive_service, SHEET_MASTER_URL, save_master_to_db
from pathlib import Path
import shutil

LOCAL_DATA_DIR = Path("local_data")

def show(df_daily, df_fix_cost, sku_map, sku_list, sku_type_map, category_options=None):
    #st.markdown('<div class="header-bar"><div class="header-title"><i class="fas fa-tools"></i> จัดการ Master Item (แก้ไขต้นทุน/เรทค่าใช้จ่าย)</div></div>', unsafe_allow_html=True)
    

    #st.markdown("---")
    st.subheader("🔧 Master Item Management")
    
    # Create Tabs for cleaner UI
    tab_cloud, tab_local = st.tabs(["☁️ Google Sheet Sync", "📂 Upload Local File"])
    
    with tab_cloud:
        st.info("💡 เชื่อมต่อข้อมูลจาก Google Sheet โดยตรง (แนะนำ)")
        col_btn, col_blank = st.columns([1, 2])
        with col_btn:
            if st.button("🔄 อัปเดตข้อมูลจาก Google Sheet", type="primary", use_container_width=True):
                with st.spinner("Fetching data from Google Sheet..."):
                    try:
                        creds = get_drive_service()
                        if creds:
                            gc = gspread.authorize(creds)
                            try:
                                sh = gc.open_by_url(SHEET_MASTER_URL)
                                ws = sh.worksheet("MASTER_ITEM")
                                data = ws.get_all_records()
                                df_sheet = pd.DataFrame(data)
                                
                                # Save to Local File as backup
                                save_path = LOCAL_DATA_DIR / "master_item.xlsx"
                                df_sheet.to_excel(save_path, index=False)
                                
                                # Save to DB
                                save_master_to_db(df_sheet)
                                
                                st.success("✅ Sync Master Item สำเร็จ!")
                                st.rerun()
                            except gspread.exceptions.APIError as api_err:
                                st.error(f"❌ Google API Error: {api_err}")
                            except Exception as ws_err:
                                st.error(f"❌ ไม่พบ Worksheet หรือ URL ผิดพลาด: {ws_err}")
                        else:
                            st.error("⚠️ ไม่พบ Credentials ของ Google Service Account")
                    except Exception as e:
                        st.error(f"Failed to fetch: {e}")

    with tab_local:
        master_path = LOCAL_DATA_DIR / "master_item.xlsx"
        # st.info("📂 อัปโหลดไฟล์ Excel (.xlsx) เพื่อใช้เป็นฐานข้อมูล Master Item")

        if master_path.exists():
            st.success(f"✅ ไฟล์ Master Item ที่ใช้: `{master_path.name}` ")
        else:
            st.warning("⚠️ ไฟล์ Master Item ไม่พบ")

        uploaded_master = st.file_uploader("เลือกไฟล์ Master Item", type=['xlsx'], key="up_master", label_visibility="collapsed")
        if uploaded_master:
            save_path = LOCAL_DATA_DIR / "master_item.xlsx"
            with open(save_path, "wb") as buffer:
                shutil.copyfileobj(uploaded_master, buffer)
            
            # Sync to DB
            try:
                df_upload = pd.read_excel(save_path)
                save_master_to_db(df_upload)
                st.toast("✅ บันทึกไฟล์และอัปเดตฐานข้อมูลสำเร็จ!", icon="💾")
                st.rerun()
            except Exception as e:
                st.error(f"Saved file but failed to update DB: {e}")

        # --- STATUS SECTION ---
        st.markdown("---")
        
        
        c_status, c_action = st.columns([3, 1])
        # with c_status:
        #     if master_path.exists():
        #         st.success(f"✅ **Current Master File:** `{master_path.name}` (Ready)", icon="✅")
        #     else:
        #         st.warning("⚠️ **Status:** Master File Not Found", icon="⚠️")
                
        with c_action:
            if master_path.exists():
                if st.button("🗑️ Delete File", type="secondary", use_container_width=True, help="ลบไฟล์ Master Item ปัจจุบัน"):
                    try:
                        master_path.unlink()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

    # Check mode. If Local Mode, this might not work unless we have logic to edit local file or disable it.
    # if st.session_state.get("data_source_mode") == "MODE_LOCAL":
    #     st.warning("⚠️ การแก้ไข Master Item รองรับเฉพาะ Mode Drive ในขณะนี้ (หรือต้อง implement การแก้ไฟล์ Local Excel)")
    #     # Future improvement: Edit local_data/master_item.xlsx
    #     return

    def get_master_worksheet():
        try:
            creds = get_drive_service()
            if not creds: return None
            gc = gspread.authorize(creds)
            sh = gc.open_by_url(SHEET_MASTER_URL) 
            return sh.worksheet("MASTER_ITEM")
        except Exception as e:
            st.error(f"⚠️ ไม่สามารถเชื่อมต่อ MASTER_ITEM: {e}")
            return None

    ws = get_master_worksheet()
    
    if ws:
        try:
            data = ws.get_all_records()
            df_master_edit = pd.DataFrame(data)

            cost_col_name = 'ทุน' if 'ทุน' in df_master_edit.columns else 'ต้นทุน'

            # 1. แบ่งกลุ่มคอลัมน์
            cols_money = [cost_col_name, 'ราคากล่อง', 'ค่าส่งเฉลี่ย']
            cols_percent = [
                'ค่าคอมมิชชั่น Admin', 'ค่าคอมมิชชั่น Telesale',
                'J&T Express', 'Flash Express', 'ThailandPost', 
                'LEX TH', 'SPX Express', 'Express Delivery - ส่งด่วน', 
                'DHL_1', 'Standard Delivery - ส่งธรรมดาในประเทศ'
            ]

            target_columns_order = ['SKU', 'ชื่อสินค้า'] + cols_money + ['Type'] + cols_percent
            available_cols = [c for c in target_columns_order if c in df_master_edit.columns]
            other_cols = [c for c in df_master_edit.columns if c not in available_cols]
            
            df_editor_view = df_master_edit[available_cols + other_cols].copy()

            # --- 2. เตรียมข้อมูล ---
            for col in cols_money:
                if col in df_editor_view.columns:
                    df_editor_view[col] = pd.to_numeric(df_editor_view[col], errors='coerce').fillna(0.0)

            for col in cols_percent:
                if col in df_editor_view.columns:
                    df_editor_view[col] = df_editor_view[col].astype(str)

            # --- UI CONTROLS ---
            c_info, c_slider, c_btn = st.columns([2.5, 1.5, 1]) 
            
            # with c_info: 
            #     st.info("💡 พิมพ์ **%** ต่อท้ายได้เลย (เช่น `0.5%`)")
            
            # with c_slider:
            #     table_height = st.slider("↕️ ปรับความสูงตาราง", min_value=600, max_value=2500, value=1200, step=100)
            
            with c_btn:
                st.markdown('<div style="margin-top: 0px;"></div>', unsafe_allow_html=True)
                click_save = st.button("💾 บันทึกการแก้ไข", type="primary", use_container_width=True)

            # --- 3. ตั้งค่าการแสดงผล ---
            my_column_config = {
                "SKU": st.column_config.TextColumn(disabled=False),
                cost_col_name: st.column_config.NumberColumn(label=f"💰 {cost_col_name}", format="%.2f"),
                "ราคากล่อง": st.column_config.NumberColumn(label="📦 ราคากล่อง", format="%.2f"),
                "ค่าส่งเฉลี่ย": st.column_config.NumberColumn(label="🚚 ค่าส่งเฉลี่ย", format="%.2f"),
            }

            for p_col in cols_percent:
                if p_col in df_editor_view.columns:
                    my_column_config[p_col] = st.column_config.TextColumn(
                        label=f"{p_col}",
                        width="medium"
                    )

            # แสดงตาราง
            edited_df = st.data_editor(
                df_editor_view,
                num_rows="dynamic", 
                use_container_width=True,
                height=2000,
                key="master_editor_vertical_v1",
                column_config=my_column_config
            )

            # ส่วนบันทึกข้อมูล
            if click_save:
                try:
                    with st.spinner("⏳ กำลังบันทึกข้อมูล..."):
                        save_df = edited_df.fillna("") 
                        vals = [save_df.columns.values.tolist()] + save_df.astype(str).values.tolist()
                        ws.clear()
                        ws.update(range_name='A1', values=vals)
                        st.success("✅ บันทึกข้อมูลเรียบร้อยแล้ว!")
                        st.cache_data.clear() 
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ เกิดข้อผิดพลาดขณะบันทึก: {e}")

        except Exception as e:
            st.error(f"❌ เกิดข้อผิดพลาดในการโหลดข้อมูล: {e}")
