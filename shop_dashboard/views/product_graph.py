import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
from modules.ui_components import render_metric_row

def show(df_daily, df_fix_cost, sku_map, sku_list, sku_type_map, category_options=None):
    st.markdown('<div class="header-bar"><div class="header-title"><i class="fas fa-chart-line"></i> กราฟแสดงแนวโน้มยอดขายรายสินค้า</div></div>', unsafe_allow_html=True)
    
    # Setup global helpers locally
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

    if "selected_skus_g" not in st.session_state: st.session_state.selected_skus_g = []
    def cb_clear_g(): st.session_state.selected_skus_g = []

    with st.container():
        c_g1, c_g2, c_g3 = st.columns([1, 1, 2])
        with c_g1: start_g = st.date_input("เริ่มวันที่", datetime.now().replace(day=1), key="g_s")
        with c_g2: end_g = st.date_input("ถึงวันที่", datetime.now(), key="g_e")
        with c_g3: filter_mode_g = st.selectbox("เงื่อนไขสินค้า (Fast Filter)",
            ["📦 แสดงรายการที่มีการเคลื่อนไหว", "💰 แสดงสินค้ากำไร", "💸 แสดงสินค้าขาดทุน", "📋 แสดงรายการทั้งหมด"], key="g_m")

        c_cat, c_sku, c_clear, c_run = st.columns([1.5, 3, 0.5, 1])
        with c_cat:
            sel_category_g = st.selectbox("หมวดหมู่สินค้า", CATEGORY_OPTIONS, key="g_cat")

        with c_sku: st.multiselect("เลือกสินค้าที่ต้องการดูกราฟ:", sku_options_list_global, key="selected_skus_g")
        with c_clear:
            st.markdown("<div style='margin-top: 29px;'></div>", unsafe_allow_html=True)
            st.button("🧹", type="secondary", use_container_width=True, key="btn_clear_g", on_click=cb_clear_g)
        with c_run:
            st.markdown("<div style='margin-top: 29px;'></div>", unsafe_allow_html=True)
            st.button("🚀 สร้างกราฟ", type="primary", use_container_width=True, key="btn_run_g")

    mask_g_date = (df_daily['Date'] >= pd.to_datetime(start_g).date()) & (df_daily['Date'] <= pd.to_datetime(end_g).date())
    df_range_g = df_daily[mask_g_date]

    sku_stats_g = df_range_g.groupby('SKU_Main').agg({'รายละเอียดยอดที่ชำระแล้ว': 'sum', 'Ads_Amount': 'sum', 'Net_Profit': 'sum'}).reset_index()
    auto_skus_g = []

    if "แสดงสินค้ากำไร" in filter_mode_g:
        auto_skus_g = sku_stats_g[sku_stats_g['Net_Profit'] > 0]['SKU_Main'].tolist()
    elif "แสดงสินค้าขาดทุน" in filter_mode_g:
        auto_skus_g = sku_stats_g[sku_stats_g['Net_Profit'] < 0]['SKU_Main'].tolist()
    elif "แสดงรายการทั้งหมด" in filter_mode_g:
        auto_skus_g = all_skus_global
    else: # แสดงรายการที่มีการเคลื่อนไหว
        auto_skus_g = sku_stats_g[(sku_stats_g['รายละเอียดยอดที่ชำระแล้ว'] > 0) | (sku_stats_g['Ads_Amount'] > 0)]['SKU_Main'].tolist()

    selected_labels_g = st.session_state.selected_skus_g
    real_selected_g = [sku_map_reverse_global[l] for l in selected_labels_g]

    pre_final_skus_g = sorted(real_selected_g) if real_selected_g else sorted(auto_skus_g)
    final_skus_g = filter_skus_by_category(pre_final_skus_g, sel_category_g)

    if not final_skus_g:
        st.info(f"👈 ไม่พบข้อมูลตามเงื่อนไข ({sel_category_g}) หรือกรุณาเลือกสินค้า")
    else:
        df_graph = df_range_g[df_range_g['SKU_Main'].isin(final_skus_g)].copy()

        if df_graph.empty:
            st.warning("⚠️ ไม่พบข้อมูลการขายของสินค้าที่เลือกในช่วงเวลานี้")
        else:
            g_sales = df_graph['รายละเอียดยอดที่ชำระแล้ว'].sum()
            g_ads = df_graph['Ads_Amount'].sum()
            g_cost_prod = df_graph['CAL_COST'].sum()
            g_ops = df_graph['BOX_COST'].sum() + df_graph['DELIV_COST'].sum() + df_graph['CAL_COD_COST'].sum()
            g_com = df_graph['CAL_COM_ADMIN'].sum() + df_graph['CAL_COM_TELESALE'].sum()
            g_net_profit = df_graph['Net_Profit'].sum()
            
            render_metric_row(g_sales, g_ops, g_com, g_cost_prod, g_ads, g_net_profit)
            
            df_chart = df_graph.groupby(['Date', 'SKU_Main']).agg({
                'รายละเอียดยอดที่ชำระแล้ว': 'sum',
                'จำนวน': 'sum'
            }).reset_index()

            df_chart['Product_Name'] = df_chart['SKU_Main'].apply(lambda x: f"{x} : {sku_name_lookup.get(x, '')}")
            df_chart['DateStr'] = df_chart['Date'].astype(str)

            st.markdown("##### 📈 แนวโน้มยอดขายรายวัน (Sales Trend)")
            chart_line = alt.Chart(df_chart).mark_line(point=True).encode(
                x=alt.X('DateStr', title='วันที่'),
                y=alt.Y('รายละเอียดยอดที่ชำระแล้ว', title='ยอดขาย (บาท)'),
                color=alt.Color('Product_Name', title='สินค้า'),
                tooltip=['DateStr', 'Product_Name', alt.Tooltip('รายละเอียดยอดที่ชำระแล้ว', format=',.0f'), 'จำนวน']
            ).interactive()
            st.altair_chart(chart_line, use_container_width=True)

            st.markdown("---")
            c_bar1, c_bar2 = st.columns(2)

            with c_bar1:
                st.markdown("##### 📊 สรุปยอดขายรวมตามช่วงเวลา (Total Sales)")
                df_bar_sum = df_chart.groupby('Product_Name')['รายละเอียดยอดที่ชำระแล้ว'].sum().reset_index()
                chart_bar = alt.Chart(df_bar_sum).mark_bar().encode(
                    x=alt.X('Product_Name', title=None, axis=alt.Axis(labels=False)),
                    y=alt.Y('รายละเอียดยอดที่ชำระแล้ว', title='ยอดขายรวม (บาท)'),
                    color=alt.Color('Product_Name', legend=None),
                    tooltip=['Product_Name', alt.Tooltip('รายละเอียดยอดที่ชำระแล้ว', format=',.0f')]
                )
                st.altair_chart(chart_bar, use_container_width=True)

            with c_bar2:
                st.markdown("##### 📦 สรุปจำนวนชิ้นที่ขายได้ (Total Units)")
                df_qty_sum = df_chart.groupby('Product_Name')['จำนวน'].sum().reset_index()
                chart_bar_qty = alt.Chart(df_qty_sum).mark_bar().encode(
                    x=alt.X('Product_Name', title=None, axis=alt.Axis(labels=False)),
                    y=alt.Y('จำนวน', title='จำนวน (ชิ้น)'),
                    color=alt.Color('Product_Name', legend=None),
                    tooltip=['Product_Name', alt.Tooltip('จำนวน', format=',.0f')]
                )
                st.altair_chart(chart_bar_qty, use_container_width=True)
