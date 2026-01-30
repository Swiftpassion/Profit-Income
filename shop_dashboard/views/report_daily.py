import streamlit as st
import pandas as pd
import numpy as np
import calendar
from datetime import datetime, date
from modules.processing import thai_months
from modules.ui_components import render_metric_row

def show(df_daily, df_fix_cost, sku_map, sku_list, sku_type_map):
    st.markdown('<div class="header-bar"><div class="header-title"><i class="fas fa-calendar-day"></i> สรุปการขายรายวัน (ตามช่วงเวลา)</div></div>', unsafe_allow_html=True)
    
    all_years = sorted(df_daily['Year'].unique(), reverse=True)
    today = datetime.now().date()

    # Init Session
    if "d_d_start" not in st.session_state:
        st.session_state.d_d_start = today.replace(day=1)
        st.session_state.d_d_end = today
    if "selected_skus_d" not in st.session_state: st.session_state.selected_skus_d = []

    # SKU Setup
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

    CATEGORY_OPTIONS = ["แสดงทั้งหมด", "กลุ่ม DKUB", "กลุ่ม SMASH", "กลุ่ม อาหารเสริม"]

    def filter_skus_by_category(current_skus, selected_category):
        if selected_category == "แสดงทั้งหมด": return current_skus
        filtered = []
        for sku in current_skus:
            sku_type = sku_type_map.get(sku, 'กลุ่ม ปกติ')
            if sku_type == selected_category: filtered.append(sku)
        return filtered

    def update_d_dates():
        y = st.session_state.d_y
        m_str = st.session_state.d_m
        try:
            m_idx = thai_months.index(m_str) + 1
            days_in_m = calendar.monthrange(y, m_idx)[1]
            st.session_state.d_d_start = date(y, m_idx, 1)
            st.session_state.d_d_end = date(y, m_idx, days_in_m)
        except: pass
    
    def cb_clear_d(): st.session_state.selected_skus_d = []

    with st.container():
        c_y, c_m, c_s, c_e = st.columns([1, 1, 1, 1])
        with c_y: sel_year_d = st.selectbox("เลือกปี (ตั้งค่าเริ่มต้น)", all_years, key="d_y", on_change=update_d_dates)
        with c_m: sel_month_d = st.selectbox("เลือกเดือน (ตั้งค่าเริ่มต้น)", thai_months, index=today.month-1, key="d_m", on_change=update_d_dates)
        with c_s: start_d = st.date_input("วันที่เริ่มต้น", key="d_d_start")
        with c_e: end_d = st.date_input("วันที่สิ้นสุด", key="d_d_end")

        c_type, c_cat, c_sku, c_clear, c_run = st.columns([1.5, 1.5, 2.5, 0.5, 1])
        with c_type:
            filter_mode_d = st.selectbox("เงื่อนไขสินค้า (Fast Filter)", 
                ["📦 แสดงรายการที่มีการเคลื่อนไหว", "💰 แสดงสินค้ากำไร", "💸 แสดงสินค้าขาดทุน", "📋 แสดงรายการทั้งหมด"], key="d_m_filter")
        with c_cat:
            sel_category_d = st.selectbox("หมวดหมู่สินค้า", CATEGORY_OPTIONS, key="d_cat")
        with c_sku: 
            st.multiselect("รายการที่เลือก (Choose options):", sku_options_list_global, key="selected_skus_d")
        with c_clear:
            st.markdown("<div style='margin-top: 29px;'></div>", unsafe_allow_html=True)
            st.button("🧹", type="secondary", use_container_width=True, key="btn_clear_d", on_click=cb_clear_d)
        with c_run:
            st.markdown("<div style='margin-top: 29px;'></div>", unsafe_allow_html=True)
            st.button("🚀 ประมวลผล", type="primary", use_container_width=True, key="btn_run_d")

    mask = (df_daily['Date'] >= start_d) & (df_daily['Date'] <= end_d)
    df_range = df_daily[mask]

    df_grouped = df_range.groupby(['SKU_Main']).agg({
        'ชื่อสินค้า': 'last', 
        'จำนวนออเดอร์': 'sum', 
        'จำนวน': 'sum', 
        'รายละเอียดยอดที่ชำระแล้ว': 'sum',
        'CAL_COST': 'sum', 'BOX_COST': 'sum', 'DELIV_COST': 'sum', 'CAL_COD_COST': 'sum',
        'CAL_COM_ADMIN': 'sum', 'CAL_COM_TELESALE': 'sum', 'Ads_Amount': 'sum', 'Net_Profit': 'sum'
    }).reset_index()
    df_grouped['ชื่อสินค้า'] = df_grouped['SKU_Main'].map(sku_name_lookup).fillna("ไม่ระบุชื่อ")

    auto_skus_d = []
    if "แสดงสินค้ากำไร" in filter_mode_d: auto_skus_d = df_grouped[df_grouped['Net_Profit'] > 0]['SKU_Main'].tolist()
    elif "แสดงสินค้าขาดทุน" in filter_mode_d: auto_skus_d = df_grouped[df_grouped['Net_Profit'] < 0]['SKU_Main'].tolist()
    elif "แสดงรายการทั้งหมด" in filter_mode_d: auto_skus_d = all_skus_global
    else: auto_skus_d = df_grouped[(df_grouped['รายละเอียดยอดที่ชำระแล้ว'] > 0) | (df_grouped['Ads_Amount'] > 0)]['SKU_Main'].tolist()

    selected_labels_d = st.session_state.selected_skus_d
    selected_skus_real_d = [sku_map_reverse_global[l] for l in selected_labels_d]
    
    pre_final_skus_d = sorted(selected_skus_real_d) if selected_skus_real_d else sorted(auto_skus_d)
    final_skus_d = filter_skus_by_category(pre_final_skus_d, sel_category_d)

    df_final_d = df_grouped[df_grouped['SKU_Main'].isin(final_skus_d)].copy()

    if df_final_d.empty: st.warning(f"⚠️ ไม่พบข้อมูลตามเงื่อนไข ({sel_category_d}) ในช่วงเวลานี้")
    else:
        sum_sales = df_final_d['รายละเอียดยอดที่ชำระแล้ว'].sum()
        sum_ads = df_final_d['Ads_Amount'].sum()
        sum_cost_prod = df_final_d['CAL_COST'].sum()
        sum_ops = df_final_d['BOX_COST'].sum() + df_final_d['DELIV_COST'].sum() + df_final_d['CAL_COD_COST'].sum()
        sum_com = df_final_d['CAL_COM_ADMIN'].sum() + df_final_d['CAL_COM_TELESALE'].sum()
        sum_profit = df_final_d['Net_Profit'].sum()
        
        render_metric_row(sum_sales, sum_ops, sum_com, sum_cost_prod, sum_ads, sum_profit)

        df_final_d['กำไร/ขาดทุน'] = df_final_d['Net_Profit']
        df_final_d['ROAS'] = np.where(df_final_d['Ads_Amount']>0, df_final_d['รายละเอียดยอดที่ชำระแล้ว']/df_final_d['Ads_Amount'], 0)
        sls = df_final_d['รายละเอียดยอดที่ชำระแล้ว']

        val_ops_item = df_final_d['BOX_COST'] + df_final_d['DELIV_COST'] + df_final_d['CAL_COD_COST']
        df_final_d['% ค่าดำเนินการ'] = np.where(sls>0, (val_ops_item/sls*100), 0)

        val_com_item = df_final_d['CAL_COM_ADMIN'] + df_final_d['CAL_COM_TELESALE']
        df_final_d['% ค่าคอมมิชชัน'] = np.where(sls>0, (val_com_item/sls*100), 0)

        df_final_d['% ทุนสินค้า'] = np.where(sls>0, (df_final_d['CAL_COST']/sls*100), 0)
        df_final_d['% Ads'] = np.where(sls>0, (df_final_d['Ads_Amount']/sls*100), 0)
        df_final_d['% กำไร'] = np.where(sls>0, (df_final_d['Net_Profit']/sls*100), 0)
        
        df_final_d = df_final_d.sort_values('กำไร/ขาดทุน', ascending=False)

        def fmt(val, is_percent=False):
            if val == 0 or pd.isna(val): return "-"
            text = f"{val:,.2f}%" if is_percent else f"{val:,.2f}"
            return text

        def get_cell_style(val):
            if isinstance(val, (int, float)) and val < 0:
                return ' style="color: #FF0000 !important; font-weight: bold !important;" class="negative-value"'
            return '' 

        st.markdown("##### 📋 รายละเอียดสินค้า")
        
        cols_cfg = [
            ('SKU', 'SKU_Main', ''), 
            ('ชื่อสินค้า', 'ชื่อสินค้า', ''), 
            ('ออเดอร์', 'จำนวนออเดอร์', ''), 
            ('ยอดขาย', 'รายละเอียดยอดที่ชำระแล้ว', ''), 
            ('ต้นทุน', 'CAL_COST', ''), 
            ('ค่ากล่อง', 'BOX_COST', ''), 
            ('ค่าส่ง', 'DELIV_COST', ''), 
            ('COD', 'CAL_COD_COST','col-small'), 
            ('Admin', 'CAL_COM_ADMIN', ''), 
            ('Tele', 'CAL_COM_TELESALE', ''), 
            ('ค่า Ads', 'Ads_Amount', ''), 
            ('กำไร', 'Net_Profit', ''), 
            ('ROAS', 'ROAS', 'col-small'), 
            ('%ค่าดำเนินการ', '% ค่าดำเนินการ', 'col-medium'), 
            ('%ค่าคอม', '% ค่าคอมมิชชัน', 'col-medium'),       
            ('%ทุน', '% ทุนสินค้า', 'col-small'), 
            ('%Ads', '% Ads', 'col-small'), 
            ('%กำไร', '% กำไร', 'col-small')
        ]

        html = '<div class="table-wrapper"><table class="custom-table daily-table"><thead><tr>'
        for title, _, cls in cols_cfg: html += f'<th class="{cls}">{title}</th>'
        html += '</tr></thead><tbody>'

        for i, (_, r) in enumerate(df_final_d.iterrows()):
            html += '<tr>'
            html += f'<td style="font-weight:bold;color:#1e3c72 !important;">{r["SKU_Main"]}</td>'
            html += f'<td style="text-align:left;font-size:11px;color:#1e3c72 !important; max-width: 100px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="{r["ชื่อสินค้า"]}">{r["ชื่อสินค้า"]}</td>'
            html += f'<td{get_cell_style(r["จำนวนออเดอร์"])}>{fmt(r["จำนวนออเดอร์"])}</td>'
            html += f'<td{get_cell_style(r["รายละเอียดยอดที่ชำระแล้ว"])}>{fmt(r["รายละเอียดยอดที่ชำระแล้ว"])}</td>'
            html += f'<td{get_cell_style(r["CAL_COST"])}>{fmt(r["CAL_COST"])}</td>'
            html += f'<td{get_cell_style(r["BOX_COST"])}>{fmt(r["BOX_COST"])}</td>'
            html += f'<td{get_cell_style(r["DELIV_COST"])}>{fmt(r["DELIV_COST"])}</td>'
            html += f'<td{get_cell_style(r["CAL_COD_COST"])}>{fmt(r["CAL_COD_COST"])}</td>'
            html += f'<td{get_cell_style(r["CAL_COM_ADMIN"])}>{fmt(r["CAL_COM_ADMIN"])}</td>'
            html += f'<td{get_cell_style(r["CAL_COM_TELESALE"])}>{fmt(r["CAL_COM_TELESALE"])}</td>'
            html += f'<td style="color:#e67e22 !important;">{fmt(r["Ads_Amount"])}</td>'
            html += f'<td{get_cell_style(r["Net_Profit"])}>{fmt(r["Net_Profit"])}</td>'
            html += f'<td class="col-small" style="color:#1e3c72 !important;">{fmt(r["ROAS"])}</td>'
            html += f'<td class="col-small" style="color:#1e3c72 !important;">{fmt(r["% ค่าดำเนินการ"],True)}</td>'
            html += f'<td class="col-small" style="color:#1e3c72 !important;">{fmt(r["% ค่าคอมมิชชัน"],True)}</td>'
            html += f'<td class="col-small" style="color:#1e3c72 !important;">{fmt(r["% ทุนสินค้า"],True)}</td>'
            html += f'<td class="col-small" style="color:#1e3c72 !important;">{fmt(r["% Ads"],True)}</td>'
            html += f'<td class="col-small"{get_cell_style(r["% กำไร"])}>{fmt(r["% กำไร"],True)}</td>'
            html += '</tr>'

        html += '<tr class="footer-row"><td>TOTAL</td><td></td>'
        ts = df_final_d['รายละเอียดยอดที่ชำระแล้ว'].sum(); tp = df_final_d['Net_Profit'].sum()
        ta = df_final_d['Ads_Amount'].sum(); tc = df_final_d['CAL_COST'].sum()
        t_box = df_final_d['BOX_COST'].sum()
        t_ship = df_final_d['DELIV_COST'].sum()
        t_cod = df_final_d['CAL_COD_COST'].sum()
        t_adm = df_final_d['CAL_COM_ADMIN'].sum()
        t_tel = df_final_d['CAL_COM_TELESALE'].sum()

        html += f'<td{get_cell_style(df_final_d["จำนวนออเดอร์"].sum())}>{fmt(df_final_d["จำนวนออเดอร์"].sum())}</td>'
        html += f'<td{get_cell_style(ts)}>{fmt(ts)}</td>'
        html += f'<td{get_cell_style(tc)}>{fmt(tc)}</td>'
        html += f'<td{get_cell_style(t_box)}>{fmt(t_box)}</td>'
        html += f'<td{get_cell_style(t_ship)}>{fmt(t_ship)}</td>'
        html += f'<td{get_cell_style(t_cod)}>{fmt(t_cod)}</td>'
        html += f'<td{get_cell_style(t_adm)}>{fmt(t_adm)}</td>'
        html += f'<td{get_cell_style(t_tel)}>{fmt(t_tel)}</td>'
        html += f'<td{get_cell_style(ta)}>{fmt(ta)}</td>'
        html += f'<td{get_cell_style(tp)}>{fmt(tp)}</td>'

        f_roas = ts/ta if ta>0 else 0
        val_pct_ops = ((t_box + t_ship + t_cod)/ts*100) if ts>0 else 0
        val_pct_comm = ((t_adm + t_tel)/ts*100) if ts>0 else 0
        val_pct_cost = (tc/ts*100) if ts>0 else 0
        val_pct_ads = (ta/ts*100) if ts>0 else 0
        val_pct_profit = (tp/ts*100) if ts>0 else 0
        
        html += f'<td class="col-small"{get_cell_style(f_roas)}>{fmt(f_roas)}</td>'
        html += f'<td class="col-medium"{get_cell_style(val_pct_ops)}>{fmt(val_pct_ops,True)}</td>'
        html += f'<td class="col-medium"{get_cell_style(val_pct_comm)}>{fmt(val_pct_comm,True)}</td>'
        html += f'<td class="col-small"{get_cell_style(val_pct_cost)}>{fmt(val_pct_cost,True)}</td>'
        html += f'<td class="col-small"{get_cell_style(val_pct_ads)}>{fmt(val_pct_ads,True)}</td>'
        html += f'<td class="col-small"{get_cell_style(val_pct_profit)}>{fmt(val_pct_profit,True)}</td></tr></tbody></table></div>'
        st.markdown(html, unsafe_allow_html=True)
