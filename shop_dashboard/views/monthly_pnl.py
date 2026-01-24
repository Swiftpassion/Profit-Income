import streamlit as st
import pandas as pd
import altair as alt
import calendar
from datetime import datetime
from modules.processing import thai_months
from modules.ui_components import render_metric_row

def show(df_daily, df_fix_cost, sku_map, sku_list, sku_type_map):
    st.markdown('<div class="pnl-container">', unsafe_allow_html=True)
    st.markdown("""
    <div class="header-gradient-pnl">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
                <h1 class="header-title-pnl">แดชบอร์ดกำไร-ขาดทุน (รายเดือน)</h1>
                <p class="header-sub-pnl">เจาะลึกรายละเอียดรายเดือน</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    c_y, c_m, c_d = st.columns([1, 1, 4])
    with c_y: sel_y_m = st.selectbox("เลือกปี", sorted(df_daily['Year'].unique(), reverse=True), key="pm_y")
    with c_m: sel_m_m = st.selectbox("เลือกเดือน", thai_months, index=datetime.now().month-1, key="pm_m")

    df_m_data = df_daily[(df_daily['Year'] == sel_y_m) & (df_daily['Month_Thai'] == sel_m_m)].copy()

    days_in_m = calendar.monthrange(sel_y_m, thai_months.index(sel_m_m)+1)[1]
    df_full_days = pd.DataFrame({'Day': range(1, days_in_m + 1)})

    fix_cost_month = 0
    fix_cost_daily = fix_cost_month / days_in_m if days_in_m > 0 else 0

    if df_m_data.empty:
        st.warning(f"ไม่พบข้อมูลการขายสำหรับเดือน {sel_m_m} {sel_y_m} (แต่จะแสดงกราฟเปล่าที่มี Fix Cost)")
        df_d_agg_raw = pd.DataFrame(columns=['Day', 'รายละเอียดยอดที่ชำระแล้ว', 'Ads_Amount', 'CAL_COST', 'BOX_COST', 'DELIV_COST', 'CAL_COD_COST', 'CAL_COM_ADMIN', 'CAL_COM_TELESALE'])
    else:
        df_d_agg_raw = df_m_data.groupby('Day').agg({
            'รายละเอียดยอดที่ชำระแล้ว': 'sum',
            'Ads_Amount': 'sum',
            'CAL_COST': 'sum', 'BOX_COST': 'sum',
            'DELIV_COST': 'sum', 'CAL_COD_COST': 'sum', 'CAL_COM_ADMIN': 'sum', 'CAL_COM_TELESALE': 'sum'
        }).reset_index()

    df_d_agg = pd.merge(df_full_days, df_d_agg_raw, on='Day', how='left').fillna(0)

    df_d_agg['Daily_Total_Exp'] = df_d_agg['CAL_COST'] + df_d_agg['BOX_COST'] + \
                                  df_d_agg['DELIV_COST'] + df_d_agg['CAL_COD_COST'] + \
                                  df_d_agg['CAL_COM_ADMIN'] + df_d_agg['CAL_COM_TELESALE'] + \
                                  df_d_agg['Ads_Amount'] + fix_cost_daily

    df_d_agg['Daily_Net_Profit'] = df_d_agg['รายละเอียดยอดที่ชำระแล้ว'] - df_d_agg['Daily_Total_Exp']

    m_sales = df_d_agg['รายละเอียดยอดที่ชำระแล้ว'].sum()
    m_ads = df_d_agg['Ads_Amount'].sum()
    m_cost_prod = df_d_agg['CAL_COST'].sum()
    m_ops = df_d_agg['BOX_COST'].sum() + df_d_agg['DELIV_COST'].sum() + df_d_agg['CAL_COD_COST'].sum()
    m_com = df_d_agg['CAL_COM_ADMIN'].sum() + df_d_agg['CAL_COM_TELESALE'].sum()
    m_net_profit = df_d_agg['Daily_Net_Profit'].sum()
    
    render_metric_row(m_sales, m_ops, m_com, m_cost_prod, m_ads, m_net_profit)

    def fmt(v): return f"{v:,.0f}"

    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="chart-box"><div class="chart-header"><span class="pill" style="background:#3b82f6"></span> แนวโน้มรายวัน (ยอดขาย vs ค่าใช้จ่าย)</div>', unsafe_allow_html=True)
        base_d = alt.Chart(df_d_agg).encode(x=alt.X('Day:O', title='วันที่'))
        bar_d = base_d.mark_bar(color='#3b82f6', opacity=0.7).encode(y=alt.Y('รายละเอียดยอดที่ชำระแล้ว', title='บาท'), tooltip=['Day', 'รายละเอียดยอดที่ชำระแล้ว'])
        line_d = base_d.mark_line(color='#ef4444').encode(y='Daily_Total_Exp', tooltip=['Day', 'Daily_Total_Exp'])
        st.altair_chart((bar_d + line_d).interactive(), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="chart-box"><div class="chart-header"><span class="pill" style="background:#f87171"></span> สัดส่วนค่าใช้จ่าย (เดือนนี้)</div>', unsafe_allow_html=True)
        m_prod = df_d_agg['CAL_COST'].sum()
        m_box = df_d_agg['BOX_COST'].sum()
        m_ship = df_d_agg['DELIV_COST'].sum()
        m_cod = df_d_agg['CAL_COD_COST'].sum()
        m_admin = df_d_agg['CAL_COM_ADMIN'].sum()
        m_tele = df_d_agg['CAL_COM_TELESALE'].sum()
        m_ads = df_d_agg['Ads_Amount'].sum()

        pie_data = pd.DataFrame([
            {'Type': 'ต้นทุนสินค้า', 'Value': m_prod},
            {'Type': 'ค่ากล่อง', 'Value': m_box},
            {'Type': 'ค่าส่ง', 'Value': m_ship},
            {'Type': 'ค่า COD', 'Value': m_cod},
            {'Type': 'ค่าคอม Admin', 'Value': m_admin},
            {'Type': 'ค่าคอม Tele', 'Value': m_tele},
            {'Type': 'ค่า Ads', 'Value': m_ads}
        ])
        pie_data = pie_data[pie_data['Value'] > 0]

        if not pie_data.empty:
            donut_m = alt.Chart(pie_data).mark_arc(innerRadius=80).encode(
                theta=alt.Theta("Value", stack=True),
                color=alt.Color("Type", scale=alt.Scale(scheme='tableau10'), legend=alt.Legend(orient='right')),
                tooltip=["Type", alt.Tooltip("Value", format=",.0f")]
            )
            st.altair_chart(donut_m, use_container_width=True)
        else:
            st.info("ไม่มีข้อมูลค่าใช้จ่าย")
        st.markdown('</div>', unsafe_allow_html=True)

    c3, c4 = st.columns(2)
    with c3:
        st.markdown('<div class="chart-box"><div class="chart-header"><span class="pill" style="background:#14b8a6"></span> กำไรสุทธิรายวัน</div>', unsafe_allow_html=True)
        chart_profit_d = alt.Chart(df_d_agg).mark_line(point=True, color='#14b8a6').encode(
            x=alt.X('Day:O', title='วันที่'),
            y=alt.Y('Daily_Net_Profit', title='บาท'),
            tooltip=['Day', alt.Tooltip('Daily_Net_Profit', format=',.0f')]
        ).properties(height=400).interactive()
        st.altair_chart(chart_profit_d, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with c4:
        st.markdown('<div class="chart-box"><div class="chart-header"><span class="pill" style="background:#6366f1"></span> สินค้าขายดีประจำเดือน (Top 12)</div>', unsafe_allow_html=True)
        
        sku_name_lookup = df_daily.groupby('SKU_Main')['ชื่อสินค้า'].last().to_dict()
        sku_name_lookup.update(sku_map)

        if not df_m_data.empty:
            top_sku_m = df_m_data.groupby('SKU_Main')['รายละเอียดยอดที่ชำระแล้ว'].sum().nlargest(12).reset_index()
            top_sku_m['Display_Name'] = top_sku_m['SKU_Main'].apply(lambda x: f"{x} : {sku_name_lookup.get(x, 'ไม่ระบุชื่อ')}")

            chart_sku_m = alt.Chart(top_sku_m).mark_bar(cornerRadiusEnd=4).encode(
                x=alt.X('รายละเอียดยอดที่ชำระแล้ว', title='ยอดขาย'),
                y=alt.Y('Display_Name', sort='-x', title='สินค้า'),
                color=alt.Color('Display_Name', legend=None, scale=alt.Scale(scheme='tableau10')),
                tooltip=['Display_Name', alt.Tooltip('รายละเอียดยอดที่ชำระแล้ว', format=',.0f')]
            ).properties(height=400)
            st.altair_chart(chart_sku_m, use_container_width=True)
        else:
            st.info("ไม่มีข้อมูลสินค้าขายดี")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="chart-box"><div class="chart-header">งบกำไรขาดทุน (Monthly Statement)</div>', unsafe_allow_html=True)

    m_sales = df_d_agg['รายละเอียดยอดที่ชำระแล้ว'].sum()
    m_prod_cost = df_d_agg['CAL_COST'].sum()
    m_box_cost = df_d_agg['BOX_COST'].sum()
    m_gross = m_sales - m_prod_cost - m_box_cost
    m_ship = df_d_agg['DELIV_COST'].sum()
    m_cod = df_d_agg['CAL_COD_COST'].sum()
    m_admin = df_d_agg['CAL_COM_ADMIN'].sum()
    m_tele = df_d_agg['CAL_COM_TELESALE'].sum()
    m_ads = df_d_agg['Ads_Amount'].sum()
    m_net = m_gross - m_ship - m_cod - m_admin - m_tele - m_ads - fix_cost_month

    def row_html(label, val, is_head=False, is_neg=False, is_sub=False):
        cls = "pnl-row-head" if is_head else ("sub-item" if is_sub else "")
        val_cls = "neg" if val < 0 else ""
        return f'<tr class="{cls}"><td>{label}</td><td class="num-cell {val_cls}">{fmt(val)}</td></tr>'

    table_html_m = f"""
    <table class="pnl-table">
        <thead><tr><th>รายการ (Accounts)</th><th style="text-align:right">จำนวนเงิน (THB)</th></tr></thead>
        <tbody>
            {row_html("รายได้จากการขาย (Sales)", m_sales, True)}
            {row_html("หัก ต้นทุนสินค้า (Product Cost)", -m_prod_cost)}
            {row_html("หัก ค่ากล่อง (Box Cost)", -m_box_cost)}
            {row_html("กำไรขั้นต้น (Gross Profit)", m_gross, True, m_gross<0)}
            {row_html("หัก ค่าส่ง (Shipping)", -m_ship, is_sub=True)}
            {row_html("หัก ค่า COD", -m_cod, is_sub=True)}
            {row_html("หัก ค่าคอม Admin", -m_admin, is_sub=True)}
            {row_html("หัก ค่าคอม Telesale", -m_tele, is_sub=True)}
            {row_html("หัก ค่า ADS", -m_ads, is_sub=True)}
            {row_html("กำไร(ขาดทุน) สุทธิ (Net Profit)", m_net, True, m_net<0)}
        </tbody>
    </table>
    """
    st.markdown(table_html_m, unsafe_allow_html=True)
    st.markdown('</div></div>', unsafe_allow_html=True)
