import streamlit as st
import pandas as pd
import calendar
from datetime import datetime, date
from modules.processing import thai_months
from modules.ui_components import render_metric_row

def show(df_daily, df_fix_cost, sku_map, sku_list, sku_type_map):
    st.markdown('<div class="header-bar"><div class="header-title"><i class="fas fa-chart-line"></i> สรุปยอดขายรายเดือน</div></div>', unsafe_allow_html=True)
    all_years = sorted(df_daily['Year'].unique(), reverse=True)
    
    today = datetime.now().date()
    
    # Init Session State for filters if not exists
    if "m_d_start" not in st.session_state:
        st.session_state.m_d_start = today.replace(day=1)
        st.session_state.m_d_end = today
    if "selected_skus" not in st.session_state: st.session_state.selected_skus = []

    # Setup SKU Global Options
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

    def update_m_dates():
        y = st.session_state.m_y
        m_str = st.session_state.m_m
        try:
            m_idx = thai_months.index(m_str) + 1
            days_in_m = calendar.monthrange(y, m_idx)[1]
            st.session_state.m_d_start = date(y, m_idx, 1)
            st.session_state.m_d_end = date(y, m_idx, days_in_m)
        except: pass

    def cb_clear_m(): st.session_state.selected_skus = []

    with st.container():
        c_y, c_m, c_s, c_e = st.columns([1, 1, 1, 1])

        with c_y: sel_year = st.selectbox("เลือกปี (ตั้งค่าเริ่มต้น)", all_years, key="m_y", on_change=update_m_dates)
        with c_m: sel_month = st.selectbox("เลือกเดือน (ตั้งค่าเริ่มต้น)", thai_months, index=today.month-1, key="m_m", on_change=update_m_dates)
        with c_s: start_date_m = st.date_input("วันที่เริ่มต้น", key="m_d_start")
        with c_e: end_date_m = st.date_input("วันที่สิ้นสุด", key="m_d_end")

        c_type, c_cat, c_sku, c_clear, c_run = st.columns([1.5, 1.5, 2.5, 0.5, 1])
        with c_type:
            filter_mode = st.selectbox("เงื่อนไขสินค้า (Fast Filter)",
                ["📦 แสดงรายการที่มีการเคลื่อนไหว", "💰 แสดงสินค้ากำไร", "💸 แสดงสินค้าขาดทุน", "📋 แสดงรายการทั้งหมด"], key="m_filter_mode")
        with c_cat:
            sel_category = st.selectbox("หมวดหมู่สินค้า", CATEGORY_OPTIONS, key="m_cat")
        with c_sku: 
            st.multiselect("รายการที่เลือก (Choose options):", sku_options_list_global, key="selected_skus")
        with c_clear:
            st.markdown("<div style='margin-top: 29px;'></div>", unsafe_allow_html=True)
            st.button("🧹", type="secondary", use_container_width=True, key="btn_clear_m", on_click=cb_clear_m)
        with c_run:
            st.markdown("<div style='margin-top: 29px;'></div>", unsafe_allow_html=True)
            st.button("🚀 ประมวลผล", type="primary", use_container_width=True, key="btn_run_m")

    mask_date = (df_daily['Date'] >= start_date_m) & (df_daily['Date'] <= end_date_m)
    df_base = df_daily[mask_date]

    sku_summary = df_base.groupby('SKU_Main').agg({'รายละเอียดยอดที่ชำระแล้ว': 'sum', 'Ads_Amount': 'sum', 'Net_Profit': 'sum'}).reset_index()
    auto_skus = []
    if "แสดงสินค้ากำไร" in filter_mode: auto_skus = sku_summary[sku_summary['Net_Profit'] > 0]['SKU_Main'].tolist()
    elif "แสดงสินค้าขาดทุน" in filter_mode: auto_skus = sku_summary[sku_summary['Net_Profit'] < 0]['SKU_Main'].tolist()
    elif "แสดงรายการทั้งหมด" in filter_mode: auto_skus = all_skus_global
    else: auto_skus = sku_summary[(sku_summary['รายละเอียดยอดที่ชำระแล้ว'] > 0) | (sku_summary['Ads_Amount'] > 0)]['SKU_Main'].tolist()

    selected_labels = st.session_state.selected_skus
    selected_skus_real = [sku_map_reverse_global[l] for l in selected_labels]
    
    pre_final_skus = sorted(selected_skus_real) if selected_skus_real else sorted(auto_skus)
    final_skus = filter_skus_by_category(pre_final_skus, sel_category)

    if not final_skus: st.warning(f"⚠️ ไม่พบข้อมูลสินค้าตามเงื่อนไข ในช่วงวันที่ {start_date_m} ถึง {end_date_m} (หมวดหมู่: {sel_category})")
    else:
        df_view = df_base[df_base['SKU_Main'].isin(final_skus)]
    
        total_sales = df_view['รายละเอียดยอดที่ชำระแล้ว'].sum()
        total_ads = df_view['Ads_Amount'].sum()
        total_cost_prod = df_view['CAL_COST'].sum()
        total_ops = df_view['BOX_COST'].sum() + df_view['DELIV_COST'].sum() + df_view['CAL_COD_COST'].sum()
        total_com = df_view['CAL_COM_ADMIN'].sum() + df_view['CAL_COM_TELESALE'].sum()
        total_cost_all = total_cost_prod + total_ops + total_com + total_ads
        net_profit = total_sales - total_cost_all

        render_metric_row(total_sales, total_ops, total_com, total_cost_prod, total_ads, net_profit)

        date_list = pd.date_range(start_date_m, end_date_m)
        matrix_data = []
    
        for d in date_list:
            d_date = d.date()
            day_data = df_view[df_view['Date'] == d_date]
            
            d_sales = day_data['รายละเอียดยอดที่ชำระแล้ว'].sum()
            d_orders = day_data['จำนวนออเดอร์'].sum()
            d_profit = day_data['Net_Profit'].sum()
            d_ads = day_data['Ads_Amount'].sum()
            
            d_pct_profit = (d_profit / d_sales * 100) if d_sales != 0 else 0
            d_pct_ads = (d_ads / d_sales * 100) if d_sales != 0 else 0

            day_str = d.strftime("%a. %d/%m/%Y")

            row = {
                'วันที่': day_str, 
                'จำนวนออเดอร์': d_orders,
                'ยอดขาย': d_sales, 
                'กำไร': d_profit,
                '%กำไร': d_pct_profit,
                'ค่าแอด': d_ads,
                '%แอด': d_pct_ads
            }
            
            for sku in final_skus:
                sku_row = day_data[day_data['SKU_Main'] == sku]
                val = sku_row['Net_Profit'].sum() if not sku_row.empty else 0
                row[sku] = val
            matrix_data.append(row)

        df_matrix = pd.DataFrame(matrix_data)
        
        footer_sums = df_view.groupby('SKU_Main').agg({'รายละเอียดยอดที่ชำระแล้ว': 'sum', 'จำนวนออเดอร์': 'sum', 'CAL_COST': 'sum', 'Other_Costs': 'sum', 'Ads_Amount': 'sum', 'Net_Profit': 'sum',
                                                        'CAL_COM_ADMIN': 'sum', 'CAL_COM_TELESALE': 'sum'})
        footer_sums = footer_sums.reindex(final_skus, fill_value=0)

        def fmt_n(v): return f"{v:,.0f}" if v!=0 else "-"
        def fmt_p(v): return f"{v:,.1f}%" if v!=0 else "-"

        html = '<div class="table-wrapper"><table class="custom-table month-table"><thead><tr>'
        html += '<th class="fix-m-1" style="background-color:#2c3e50;color:white;">วันที่</th>'
        html += '<th class="fix-m-2" style="background-color:#2c3e50;color:white;">ยอดขาย</th>'
        html += '<th class="fix-m-3" style="background-color:#2c3e50;color:white;">ออเดอร์</th>'
        html += '<th class="fix-m-4" style="background-color:#27ae60;color:white;">กำไร</th>'
        html += '<th class="fix-m-5" style="background-color:#27ae60;color:white;">%กำไร</th>'
        html += '<th class="fix-m-6" style="background-color:#e67e22;color:white;">ค่าแอด</th>'
        html += '<th class="fix-m-7" style="background-color:#e67e22;color:white;">%แอด</th>'

        for sku in final_skus:
            name = str(sku_name_lookup.get(sku, ""))
            html += f'<th class="th-sku">{sku}<span class="sku-header">{name}</span></th>'
        html += '</tr></thead><tbody>'
        
        for _, r in df_matrix.iterrows():
            color_profit = "#FF0000" if r["กำไร"] < 0 else "#27ae60"
            color_pct_profit = "#FF0000" if r["%กำไร"] < 0 else "#27ae60"
            html += f'<tr>'
            html += f'<td class="fix-m-1">{r["วันที่"]}</td>'
            html += f'<td class="fix-m-2" style="font-weight:bold;">{fmt_n(r["ยอดขาย"])}</td>'
            html += f'<td class="fix-m-3" style="font-weight:bold;color:#ddd;">{fmt_n(r["จำนวนออเดอร์"])}</td>'
            html += f'<td class="fix-m-4" style="font-weight:bold; color:{color_profit};">{fmt_n(r["กำไร"])}</td>'
            html += f'<td class="fix-m-5" style="font-weight:bold; color:{color_pct_profit};">{fmt_p(r["%กำไร"])}</td>'
            html += f'<td class="fix-m-6" style="color:#e67e22;">{fmt_n(r["ค่าแอด"])}</td>'
            html += f'<td class="fix-m-7" style="color:#e67e22;">{fmt_p(r["%แอด"])}</td>'

            for sku in final_skus:
                val = r.get(sku, 0)
                color = "#FF0000" if val < 0 else "#ddd"
                html += f'<td style="color:{color};">{fmt_n(val)}</td>'
            html += '</tr>'
        
        html += '</tbody><tfoot>'

        g_sales = total_sales; g_ads = total_ads; g_cost = total_cost_prod + total_ops + total_com; g_profit = net_profit
        g_orders = df_view['จำนวนออเดอร์'].sum()
        g_pct_profit = (g_profit / g_sales * 100) if g_sales else 0
        g_pct_ads = (g_ads / g_sales * 100) if g_sales else 0
        bg_total = "#010538"; c_total = "#ffffff"

        html += f'<tr style="background-color: {bg_total}; font-weight: bold;">'
        html += f'<td class="fix-m-1" style="background-color: {bg_total}; color: {c_total};">รวม</td>'
        html += f'<td class="fix-m-2" style="background-color: {bg_total}; color: {c_total};">{fmt_n(g_sales)}</td>'
        html += f'<td class="fix-m-3" style="background-color: {bg_total}; color: {c_total};">{fmt_n(g_orders)}</td>'
        c_prof_sum = "#7CFC00" if g_profit >= 0 else "#FF0000"
        html += f'<td class="fix-m-4" style="background-color: {bg_total}; color: {c_prof_sum};">{fmt_n(g_profit)}</td>'
        html += f'<td class="fix-m-5" style="background-color: {bg_total}; color: {c_prof_sum};">{fmt_p(g_pct_profit)}</td>'
        html += f'<td class="fix-m-6" style="background-color: {bg_total}; color: #FF6633;">{fmt_n(g_ads)}</td>'
        html += f'<td class="fix-m-7" style="background-color: {bg_total}; color: #FF6633;">{fmt_p(g_pct_ads)}</td>'

        for sku in final_skus:
            val = footer_sums.loc[sku, 'Net_Profit']
            c_sku = "#7CFC00" if val >= 0 else "#FF0000"
            html += f'<td style="background-color: {bg_total}; color: {c_sku};">{fmt_n(val)}</td>'
        html += '</tr>'
        
        def create_footer_row_new(row_cls, label, data_dict, show_pct=False, dark_bg=False):
            if "row-sales" in row_cls: bg_color = "#2c3e50"       
            elif "row-cost" in row_cls: bg_color = "#3366ff"      
            elif "row-ads" in row_cls: bg_color = "#e67e22"       
            elif "row-ops" in row_cls: bg_color = "#691e72"       
            elif "row-com" in row_cls: bg_color = "#176f98"       
            else: bg_color = "#ffffff"

            if bg_color != "#ffffff": dark_bg = True
            
            style_bg = f"background-color:{bg_color};"
            lbl_color = "#ffffff" if dark_bg else "#000000"
            grand_text_col = "#ffffff" if dark_bg else "#333333"
            
            # --- Calculate Grand Total ---
            grand_val = 0
            if label == "รวมทุนสินค้า": grand_val = total_cost_prod
            elif label == "รวมยอดขาย": grand_val = g_sales
            elif label == "รวมออเดอร์": grand_val = g_orders
            elif label == "รวมค่าแอด": grand_val = g_ads
            elif label == "รวมค่าดำเนินการ": grand_val = total_ops
            elif label == "รวมค่าคอมมิชชั่น": grand_val = total_com

            txt_val_display = fmt_n(grand_val)
            if show_pct and g_sales > 0:
                pct = (grand_val / g_sales * 100)
                txt_val_display += f' <span style="font-size:0.85em">({fmt_p(pct)})</span>'

            # --- Label + Grand Total Cells ---
            # fix-m-1: Label
            # fix-m-2: Value (Sales column position)
            # fix-m-3..7: Empty or specific mapping?
            # Note: fix-m-2 is Sales, fix-m-3 is Orders, fix-m-4 is Profit, fix-m-5 is %Profit, fix-m-6 is Ads, fix-m-7 is %Ads
            # The current design puts the grand total in fix-m-2 (Sales col).
            
            row_html = f'<tr class="{row_cls}">'
            row_html += f'<td class="fix-m-1" style="{style_bg} color: {lbl_color} !important;">{label}</td>'
            row_html += f'<td class="fix-m-2" style="{style_bg} color:{grand_text_col};">{txt_val_display}</td>'
            row_html += f'<td class="fix-m-3" style="{style_bg}"></td>'
            row_html += f'<td class="fix-m-4" style="{style_bg}"></td>'
            row_html += f'<td class="fix-m-5" style="{style_bg}"></td>'
            row_html += f'<td class="fix-m-6" style="{style_bg}"></td>'
            row_html += f'<td class="fix-m-7" style="{style_bg}"></td>'

            # --- SKU Columns ---
            for sku in final_skus:
                val = 0
                s = data_dict.loc[sku, 'รายละเอียดยอดที่ชำระแล้ว']

                if label == "รวมทุนสินค้า": 
                    val = data_dict.loc[sku, 'CAL_COST']
                elif label == "รวมยอดขาย": 
                    val = data_dict.loc[sku, 'รายละเอียดยอดที่ชำระแล้ว']
                elif label == "รวมค่าแอด": 
                    val = data_dict.loc[sku, 'Ads_Amount']
                elif label == "รวมค่าดำเนินการ":
                    val = (data_dict.loc[sku, 'Other_Costs'] - 
                            data_dict.loc[sku, 'CAL_COM_ADMIN'] - 
                            data_dict.loc[sku, 'CAL_COM_TELESALE'])
                elif label == "รวมค่าคอมมิชชั่น":
                    val = data_dict.loc[sku, 'CAL_COM_ADMIN'] + data_dict.loc[sku, 'CAL_COM_TELESALE']
                
                txt_cell = fmt_n(val)
                if show_pct and s > 0:
                    pct = (val / s * 100)
                    txt_cell = f'{fmt_n(val)} <span style="font-size:0.75em">({fmt_p(pct)})</span>'
                elif show_pct:
                    txt_cell = f'{fmt_n(val)} <span style="font-size:0.75em">(-)</span>'

                cell_text_col = "#ffffff" if dark_bg else "#333333"
                if val < 0: cell_text_col = "#FF0000" # Override for negative values if needed, but white bg usually handles it. 
                # If dark bg, keep white unless extremely important? 
                # Request didn't specify negative color behavior on footer, assume standard contrast.
                # However, logic in previous code: if val < 0: cell_text_col = "#FF0000" elif dark_bg: "#ffffff"
                if val < 0: cell_text_col = "#FF0000" # Keep red for negative
                elif dark_bg: cell_text_col = "#ffffff"

                row_html += f'<td style="{style_bg} color:{cell_text_col};">{txt_cell}</td>'
            row_html += '</tr>'
            return row_html

        html += create_footer_row_new("row-sales", "รวมยอดขาย", footer_sums, show_pct=False)
        html += create_footer_row_new("row-cost", "รวมทุนสินค้า", footer_sums, show_pct=True)
        html += create_footer_row_new("row-ads", "รวมค่าแอด", footer_sums, show_pct=True)
        html += create_footer_row_new("row-ops", "รวมค่าดำเนินการ", footer_sums, show_pct=True)
        html += create_footer_row_new("row-com", "รวมค่าคอมมิชชั่น", footer_sums, show_pct=True)
        
        html += '</tfoot></table></div>'
        st.markdown(html, unsafe_allow_html=True)
