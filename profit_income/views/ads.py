import streamlit as st
import pandas as pd
import datetime
import calendar
from datetime import date
from utils.db_service import fetch_ads, save_ads

def render_ads():
    thai_months = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
    today = datetime.datetime.now().date()
    
    st.header("📢 บันทึกค่าโฆษณา (ADS)")
    
    # Shop Selector
    shops_list = [
        'TIKTOK 1', 'TIKTOK 2', 'TIKTOK 3',
        'SHOPEE 1', 'SHOPEE 2', 'SHOPEE 3',
        'LAZADA 1', 'LAZADA 2', 'LAZADA 3'
    ]
    shop_selected = st.selectbox("เลือกร้านค้า", shops_list, key="ads_shop_select")

    col_filters_ads = st.columns([1, 1, 1, 1])
    with col_filters_ads[0]: 
        sel_year_ads = st.selectbox("ปี", [2024, 2025, 2026], index=1, key="ads_year")
    with col_filters_ads[1]: 
        sel_month_ads = st.selectbox("เดือน", thai_months, index=today.month-1, key="ads_month")
    
    try:
        m_idx_ads = thai_months.index(sel_month_ads) + 1
        _, days_ads = calendar.monthrange(sel_year_ads, m_idx_ads)
        d_start_ads = date(sel_year_ads, m_idx_ads, 1)
        d_end_ads = date(sel_year_ads, m_idx_ads, days_ads)
    except:
        d_start_ads = today.replace(day=1); d_end_ads = today

    with col_filters_ads[2]: d_start_ads = st.date_input("วันที่เริ่ม", d_start_ads, key="ads_d_start")
    with col_filters_ads[3]: d_end_ads = st.date_input("ถึงวันที่", d_end_ads, key="ads_d_end")

    try:
        # Fetch only for selected shop and date range
        ads_all = fetch_ads(shop_name=shop_selected, start_date=d_start_ads, end_date=d_end_ads)
        db_ads = pd.DataFrame()
        if not ads_all.empty:
            ads_all['date'] = pd.to_datetime(ads_all['date']).dt.date
            db_ads = ads_all.set_index('date')
    except: db_ads = pd.DataFrame()

    date_range_ads = pd.date_range(start=d_start_ads, end=d_end_ads)
    editor_data = []
    for d in date_range_ads:
        d_date = d.date()
        current_ads = 0.0; current_roas = 0.0
        if not db_ads.empty and d_date in db_ads.index:
            current_ads = float(db_ads.loc[d_date, 'ads_amount'])
            current_roas = float(db_ads.loc[d_date, 'roas_ads'])
        editor_data.append({'วันที่': d_date, 'ค่า ADS': current_ads, 'ROAS ADS': current_roas})

    st.markdown("---")
    col_btn, col_info = st.columns([2, 5])
    with col_btn:
        save_ads_clicked = st.button("💾 บันทึกข้อมูลค่า ADS", type="primary", use_container_width=True)
    with col_info:
        st.info(f"📅 {shop_selected} : {d_start_ads.strftime('%d/%m/%Y')} - {d_end_ads.strftime('%d/%m/%Y')}")

    st.markdown("##### 📝 กรอกข้อมูลลงในตารางด้านล่าง")
    edited_df = st.data_editor(
        pd.DataFrame(editor_data), 
        column_config={
            "วันที่": st.column_config.DateColumn(format="DD/MM/YYYY", disabled=True), 
            "ค่า ADS": st.column_config.NumberColumn(format="฿%.2f", min_value=0, step=100), 
            "ROAS ADS": st.column_config.NumberColumn(format="%.2f", min_value=0, step=0.1)
        }, 
        hide_index=True, 
        num_rows="fixed", 
        use_container_width=True, 
        height=1200, 
        key="ads_editor_tab"
    )

    if save_ads_clicked:
        upsert_data = []
        for _, row in edited_df.iterrows():
            upsert_data.append({
                "date": row['วันที่'], 
                "shop_name": shop_selected,
                "ads_amount": row['ค่า ADS'], 
                "roas_ads": row['ROAS ADS']
            })
        try:
            save_ads(pd.DataFrame(upsert_data))
            st.toast("✅ บันทึกข้อมูลเรียบร้อยแล้ว!", icon="💾")
            st.rerun()
        except Exception as e: st.error(f"เกิดข้อผิดพลาด: {e}")
