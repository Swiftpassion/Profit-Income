import streamlit as st
import pandas as pd
import altair as alt
from modules.processing import thai_months
from modules.ui_components import render_metric_row

def show(df_daily, df_fix_cost, sku_map, sku_list, sku_type_map):
    st.markdown('<div class="pnl-container">', unsafe_allow_html=True)
    st.markdown("""
    <div class="header-gradient-pnl">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
                <h1 class="header-title-pnl">แดชบอร์ดกำไร-ขาดทุน (รายปี)</h1>
                <p class="header-sub-pnl">ภาพรวมผลประกอบการรายปี</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    c_year, c_dummy = st.columns([1, 5])
    with c_year:
        sel_year_pnl = st.selectbox("เลือกปีงบประมาณ", sorted(df_daily['Year'].unique(), reverse=True), key="pnl_year")

    df_yr = df_daily[df_daily['Year'] == sel_year_pnl].copy()

    if df_yr.empty:
        st.warning("ไม่พบข้อมูลสำหรับปีที่เลือก")
    else:
        df_m = df_yr.groupby('Month_Num').agg({
            'รายละเอียดยอดที่ชำระแล้ว': 'sum',
            'CAL_COST': 'sum', 'BOX_COST': 'sum',
            'DELIV_COST': 'sum', 'CAL_COD_COST': 'sum', 'CAL_COM_ADMIN': 'sum', 'CAL_COM_TELESALE': 'sum', 'Ads_Amount': 'sum',
            'Net_Profit': 'sum'
        }).reset_index()

        monthly_fix = []
        # Fix Cost Handling (Currently hardcoded 0 in logic or fetched?)
        # Logic in data_loader fetches df_fix_cost, but logic in app.py was hardcoded to 0 in loop
        # But wait, app.py loaded df_fix_cost but didn't seem to use it in loop line 1515.
        # "monthly_fix.append(f_cost)" where f_cost initialized to 0 inside loop?
        # Let's keep it 0 as per original effective logic, or try to use df_fix_cost if applicable.
        # Original: "f_cost = 0; monthly_fix.append(f_cost)" -> always 0.
        for m in range(1, 13):
            monthly_fix.append(0)

        df_template = pd.DataFrame({'Month_Num': range(1, 13)})
        df_merged = pd.merge(df_template, df_m, on='Month_Num', how='left').fillna(0)
        df_merged['Month_Thai'] = df_merged['Month_Num'].apply(lambda x: thai_months[x-1])
        df_merged['Fix_Cost'] = monthly_fix

        df_merged['COGS_Total'] = df_merged['CAL_COST'] + df_merged['BOX_COST']
        df_merged['Selling_Exp'] = df_merged['DELIV_COST'] + df_merged['CAL_COD_COST'] + df_merged['CAL_COM_ADMIN'] + df_merged['CAL_COM_TELESALE'] + df_merged['Ads_Amount']
        df_merged['Total_Exp'] = df_merged['COGS_Total'] + df_merged['Selling_Exp'] + df_merged['Fix_Cost']
        df_merged['Net_Profit_Final'] = df_merged['รายละเอียดยอดที่ชำระแล้ว'] - df_merged['Total_Exp']

        total_sales = df_merged['รายละเอียดยอดที่ชำระแล้ว'].sum()
        total_ads = df_merged['Ads_Amount'].sum()
        total_cost_prod = df_merged['CAL_COST'].sum()
        total_ops = df_merged['BOX_COST'].sum() + df_merged['DELIV_COST'].sum() + df_merged['CAL_COD_COST'].sum()
        total_com = df_merged['CAL_COM_ADMIN'].sum() + df_merged['CAL_COM_TELESALE'].sum()
        total_profit = df_merged['Net_Profit_Final'].sum()
        
        render_metric_row(total_sales, total_ops, total_com, total_cost_prod, total_ads, total_profit)

        def fmt(v): return f"{v:,.0f}"

        c_chart1, c_chart2 = st.columns(2)

        with c_chart1:
            st.markdown('<div class="chart-box"><div class="chart-header"><span class="pill" style="background:#3b82f6"></span> ภาพรวมยอดขาย & กำไรสุทธิ (รายปี)</div>', unsafe_allow_html=True)
            base = alt.Chart(df_merged).encode(x=alt.X('Month_Thai', sort=thai_months, title=None))
            bar1 = base.mark_bar(color='#3b82f6', opacity=0.8, cornerRadiusEnd=4).encode(
                y=alt.Y('รายละเอียดยอดที่ชำระแล้ว', title='บาท'),
                tooltip=['Month_Thai', alt.Tooltip('รายละเอียดยอดที่ชำระแล้ว', title='ยอดขาย', format=',.0f')]
            )
            line1 = base.mark_line(color='#10b981', strokeWidth=3, point=True).encode(
                y=alt.Y('Net_Profit_Final', title='กำไรสุทธิ'),
                tooltip=['Month_Thai', alt.Tooltip('Net_Profit_Final', title='กำไรสุทธิ', format=',.0f')]
            )
            st.altair_chart((bar1 + line1).interactive(), use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with c_chart2:
            st.markdown('<div class="chart-box"><div class="chart-header"><span class="pill" style="background:#f87171"></span> สัดส่วนค่าใช้จ่าย (ทั้งปี)</div>', unsafe_allow_html=True)
            exp_data = pd.DataFrame([
                {'Type': 'ต้นทุนสินค้า', 'Value': df_merged['CAL_COST'].sum()},
                {'Type': 'ค่ากล่อง', 'Value': df_merged['BOX_COST'].sum()},
                {'Type': 'ค่าส่ง', 'Value': df_merged['DELIV_COST'].sum()},
                {'Type': 'ค่า COD', 'Value': df_merged['CAL_COD_COST'].sum()},
                {'Type': 'ค่าคอม Admin', 'Value': df_merged['CAL_COM_ADMIN'].sum()},
                {'Type': 'ค่าคอม Tele', 'Value': df_merged['CAL_COM_TELESALE'].sum()},
                {'Type': 'ค่า Ads', 'Value': df_merged['Ads_Amount'].sum()}
            ])
            exp_data = exp_data[exp_data['Value'] > 0]

            if not exp_data.empty:
                donut = alt.Chart(exp_data).mark_arc(innerRadius=70).encode(
                    theta=alt.Theta("Value", stack=True),
                    color=alt.Color("Type", scale=alt.Scale(scheme='tableau10'), legend=alt.Legend(orient='right')),
                    tooltip=["Type", alt.Tooltip("Value", format=",.0f")]
                )
                st.altair_chart(donut, use_container_width=True)
            else:
                st.info("ไม่มีข้อมูลค่าใช้จ่าย")
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="chart-box"><div class="chart-header">งบกำไรขาดทุน (Profit & Loss Statement)</div>', unsafe_allow_html=True)

        t_sales = df_merged['รายละเอียดยอดที่ชำระแล้ว'].sum()
        t_prod_cost = df_merged['CAL_COST'].sum()
        t_box_cost = df_merged['BOX_COST'].sum()
        t_gross = t_sales - t_prod_cost - t_box_cost
        t_ship = df_merged['DELIV_COST'].sum()
        t_cod = df_merged['CAL_COD_COST'].sum()
        t_admin = df_merged['CAL_COM_ADMIN'].sum()
        t_tele = df_merged['CAL_COM_TELESALE'].sum()
        t_ads = df_merged['Ads_Amount'].sum()
        t_fix = df_merged['Fix_Cost'].sum()
        t_net = t_gross - t_ship - t_cod - t_admin - t_tele - t_ads - t_fix

        def row_html(label, val, is_head=False, is_neg=False, is_sub=False):
            cls = "pnl-row-head" if is_head else ("sub-item" if is_sub else "")
            val_cls = "neg" if val < 0 else ""
            return f'<tr class="{cls}"><td>{label}</td><td class="num-cell {val_cls}">{fmt(val)}</td></tr>'

        table_html = f"""
        <table class="pnl-table">
            <thead><tr><th>รายการ (Accounts)</th><th style="text-align:right">จำนวนเงิน (THB)</th></tr></thead>
            <tbody>
                {row_html("รายได้จากการขาย (Sales Revenue)", t_sales, True)}
                {row_html("หัก ต้นทุนสินค้า (Product Cost)", -t_prod_cost)}
                {row_html("หัก ค่ากล่อง (Box Cost)", -t_box_cost)}
                {row_html("กำไรขั้นต้น (Gross Profit)", t_gross, True, t_gross<0)}
                {row_html("หัก ค่าส่ง (Shipping)", -t_ship, is_sub=True)}
                {row_html("หัก ค่า COD", -t_cod, is_sub=True)}
                {row_html("หัก ค่าคอม Admin", -t_admin, is_sub=True)}
                {row_html("หัก ค่าคอม Telesale", -t_tele, is_sub=True)}
                {row_html("หัก ค่า ADS", -t_ads, is_sub=True)}
                {row_html("กำไร(ขาดทุน) สุทธิ (Net Profit)", t_net, True, t_net<0)}
            </tbody>
        </table>
        """
        st.markdown(table_html, unsafe_allow_html=True)
        st.markdown('</div></div>', unsafe_allow_html=True)
