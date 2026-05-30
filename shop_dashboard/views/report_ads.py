import streamlit as st
import pandas as pd
import calendar
from datetime import datetime, date
from modules.processing import thai_months
from modules.ui_components import render_metric_row

def show(df_daily, df_fix_cost, sku_map, sku_list, sku_type_map, category_options=None):
    st.markdown('<div class="header-bar"><div class="header-title"><i class="fas fa-bullhorn"></i> สรุปค่าโฆษณา (รายวัน)</div></div>', unsafe_allow_html=True)
    all_years = sorted(df_daily['Year'].unique(), reverse=True)
    today = datetime.now().date()
    
    # Init Session State
    if "a_d_start" not in st.session_state:
        st.session_state.a_d_start = today.replace(day=1)
        st.session_state.a_d_end = today
    if "selected_skus_a" not in st.session_state: st.session_state.selected_skus_a = []

    # SKU Options
    sku_name_lookup = df_daily.groupby('SKU_Main')['ชื่อสินค้า'].last().to_dict()
    sku_name_lookup.update(sku_map)
    all_skus_global = sku_list

    sku_options_list_global = []
    sku_map_reverse_global = {}
    for sku in all_skus_global:
        name = str(sku_name_lookup.get(sku, "")); name = "" if name in ['nan','0','0.0'] else name
        label = f"{sku} : {name}"
        sku_options_list_global.append(label)
        sku_map_reverse_global[label] = sku

    CATEGORY_OPTIONS = category_options if category_options else ["แสดงทั้งหมด"]

    def filter_skus_by_category(current_skus, selected_category):
        if selected_category == "แสดงทั้งหมด": return current_skus
        filtered = []
        for sku in current_skus:
            sku_type = sku_type_map.get(sku, 'กลุ่ม ปกติ')
            if sku_type == selected_category: filtered.append(sku)
        return filtered

    def update_a_dates():
        y = st.session_state.a_y
        m_str = st.session_state.a_m
        try:
            m_idx = thai_months.index(m_str) + 1
            days_in_m = calendar.monthrange(y, m_idx)[1]
            st.session_state.a_d_start = date(y, m_idx, 1)
            st.session_state.a_d_end = date(y, m_idx, days_in_m)
        except: pass

    def cb_clear_a(): st.session_state.selected_skus_a = []

    with st.container():
        c_y, c_m, c_s, c_e = st.columns([1, 1, 1, 1])
        with c_y: sel_year_a = st.selectbox("เลือกปี (ตั้งค่าเริ่มต้น)", all_years, key="a_y", on_change=update_a_dates)
        with c_m: sel_month_a = st.selectbox("เลือกเดือน (ตั้งค่าเริ่มต้น)", thai_months, index=today.month-1, key="a_m", on_change=update_a_dates)
        with c_s: start_date_a = st.date_input("วันที่เริ่มต้น", key="a_d_start")
        with c_e: end_date_a = st.date_input("วันที่สิ้นสุด", key="a_d_end")

        c_type, c_cat, c_sku, c_clear, c_run = st.columns([1.5, 1.5, 2.5, 0.5, 1])
        with c_type:
            filter_mode_a = st.selectbox("เงื่อนไขสินค้า (Fast Filter)",
                ["📦 แสดงรายการที่มีการเคลื่อนไหว", "📋 แสดงรายการทั้งหมด"], key="a_filter_mode")
        with c_cat:
            sel_category_a = st.selectbox("หมวดหมู่สินค้า", CATEGORY_OPTIONS, key="a_cat")
        with c_sku: 
            st.multiselect("รายการที่เลือก (Choose options):", sku_options_list_global, key="selected_skus_a")
        with c_clear:
            st.markdown("<div style='margin-top: 29px;'></div>", unsafe_allow_html=True)
            st.button("🧹", type="secondary", use_container_width=True, key="btn_clear_a", on_click=cb_clear_a)
        with c_run:
            st.markdown("<div style='margin-top: 29px;'></div>", unsafe_allow_html=True)
            st.button("🚀 ประมวลผล", type="primary", use_container_width=True, key="btn_run_a")

    mask_date_a = (df_daily['Date'] >= start_date_a) & (df_daily['Date'] <= end_date_a)
    df_base_a = df_daily[mask_date_a]

    sku_summary_a = df_base_a.groupby('SKU_Main').agg({'Ads_Amount': 'sum', 'รายละเอียดยอดที่ชำระแล้ว': 'sum'}).reset_index()
    auto_skus_a = []
    if "แสดงรายการทั้งหมด" in filter_mode_a: auto_skus_a = all_skus_global
    else: auto_skus_a = sku_summary_a[(sku_summary_a['Ads_Amount'] > 0) | (sku_summary_a['รายละเอียดยอดที่ชำระแล้ว'] > 0)]['SKU_Main'].tolist()

    selected_labels_a = st.session_state.selected_skus_a
    selected_skus_real_a = [sku_map_reverse_global[l] for l in selected_labels_a]
    
    pre_final_skus_a = sorted(selected_skus_real_a) if selected_skus_real_a else sorted(auto_skus_a)
    final_skus_a = filter_skus_by_category(pre_final_skus_a, sel_category_a)

    if not final_skus_a: 
        st.warning(f"⚠️ ไม่พบข้อมูลสินค้าตามเงื่อนไข ในช่วงวันที่ {start_date_a} ถึง {end_date_a}")
    else:
        df_view_a = df_base_a[df_base_a['SKU_Main'].isin(final_skus_a)]
        
        total_sales = df_view_a['รายละเอียดยอดที่ชำระแล้ว'].sum()
        total_ads = df_view_a['Ads_Amount'].sum()
        total_cost_prod = df_view_a['CAL_COST'].sum()
        total_ops = df_view_a['BOX_COST'].sum() + df_view_a['DELIV_COST'].sum() + df_view_a['CAL_COD_COST'].sum()
        total_com = df_view_a['CAL_COM_ADMIN'].sum() + df_view_a['CAL_COM_TELESALE'].sum()
        total_cost_all = total_cost_prod + total_ops + total_com + total_ads
        net_profit = total_sales - total_cost_all

        render_metric_row(total_sales, total_ops, total_com, total_cost_prod, total_ads, net_profit)
        
        date_list_a = pd.date_range(start_date_a, end_date_a)
        matrix_data_a = []
        
        for d in date_list_a:
            d_date = d.date()
            day_data = df_view_a[df_view_a['Date'] == d_date]
            d_total_ads = day_data['Ads_Amount'].sum()
            day_str = d.strftime("%a. %d/%m/%Y")
            row = {
                'วันที่': day_str,
                'ค่าแอดรวม': d_total_ads
            }
            for sku in final_skus_a:
                val = day_data[day_data['SKU_Main'] == sku]['Ads_Amount'].sum()
                row[sku] = val
            matrix_data_a.append(row)
            
        df_matrix_a = pd.DataFrame(matrix_data_a)
        footer_sums_a = df_view_a.groupby('SKU_Main')['Ads_Amount'].sum()
        total_period_ads = footer_sums_a.sum()
        
        def fmt_n(v): return f"{v:,.0f}" if v!=0 else "-"
        
        html = '<div class="table-wrapper"><table class="custom-table month-table"><thead><tr>'
        html += '<th class="fix-m-1" style="background-color:#2c3e50;color:white;">วันที่</th>'
        html += '<th class="fix-m-2" style="background-color:#e67e22;color:white;border-right: 2px solid #bbb !important;">ค่าแอดรวม</th>'
        for sku in final_skus_a:
            name = str(sku_name_lookup.get(sku, ""))
            html += f'<th class="th-sku">{sku}<span class="sku-header">{name}</span></th>'
        html += '</tr></thead><tbody>'
        
        for _, r in df_matrix_a.iterrows():
            html += '<tr>'
            html += f'<td class="fix-m-1">{r["วันที่"]}</td>'
            html += f'<td class="fix-m-2" style="font-weight:bold; color:#e67e22; border-right: 2px solid #bbb !important;">{fmt_n(r["ค่าแอดรวม"])}</td>'
            for sku in final_skus_a:
                val = r.get(sku, 0)
                color = "#e67e22" if val > 0 else "#ddd"
                html += f'<td style="color:{color};">{fmt_n(val)}</td>'
            html += '</tr>'
        
        html += '</tbody><tfoot>'
        bg_total = "#010538"; c_total = "#ffffff"
        html += f'<tr style="background-color: {bg_total}; font-weight: bold;">'
        html += f'<td class="fix-m-1" style="background-color: {bg_total}; color: {c_total};">รวม</td>'
        html += f'<td class="fix-m-2" style="background-color: {bg_total}; color: #FF6633; border-right: 2px solid #bbb !important;">{fmt_n(total_period_ads)}</td>'
        for sku in final_skus_a:
            val = footer_sums_a.get(sku, 0)
            html += f'<td style="background-color: {bg_total}; color: #FF6633;">{fmt_n(val)}</td>'
        html += '</tr></tfoot></table></div>'
        st.markdown(html, unsafe_allow_html=True)
