import streamlit as st
import pandas as pd
import altair as alt
import calendar
from datetime import datetime
from modules.processing import thai_months
from modules.ui_components import render_metric_row

def show(df_daily, df_fix_cost, sku_map, sku_list, sku_type_map):
    st.markdown('<div class="header-bar"><div class="header-title"><i class="fas fa-coins"></i> สรุปค่าคอมมิชชั่น (Admin & Telesale)</div></div>', unsafe_allow_html=True)

    with st.container():
        c_c1, c_c2, c_c3 = st.columns([1, 1, 3])
        with c_c1: sel_year_c = st.selectbox("เลือกปี", sorted(df_daily['Year'].unique(), reverse=True), key="c_y")
        with c_c2: sel_month_c = st.selectbox("เลือกเดือน", thai_months, index=datetime.now().month-1, key="c_m")

    st.markdown(f"### 📅 ประจำเดือน: {sel_month_c} {sel_year_c}")

    df_comm = df_daily[(df_daily['Year'] == sel_year_c) & (df_daily['Month_Thai'] == sel_month_c)].copy()

    month_idx = thai_months.index(sel_month_c) + 1
    days_in_m = calendar.monthrange(sel_year_c, month_idx)[1]
    df_full_days = pd.DataFrame({'Day': range(1, days_in_m + 1)})

    if df_comm.empty:
        st.warning(f"⚠️ ไม่พบข้อมูลสำหรับเดือน {sel_month_c} {sel_year_c}")
        total_admin = 0
        total_tele = 0
        total_all = 0
    else:
        total_admin = df_comm['CAL_COM_ADMIN'].sum()
        total_tele = df_comm['CAL_COM_TELESALE'].sum()
        total_all = total_admin + total_tele

        total_sales = df_comm['รายละเอียดยอดที่ชำระแล้ว'].sum()
        total_ads = df_comm['Ads_Amount'].sum()
        total_cost_prod = df_comm['CAL_COST'].sum()
        total_ops = df_comm['BOX_COST'].sum() + df_comm['DELIV_COST'].sum() + df_comm['CAL_COD_COST'].sum()
        total_com = total_admin + total_tele
        net_profit = total_sales - (total_cost_prod + total_ops + total_com + total_ads)
        
        render_metric_row(total_sales, total_ops, total_com, total_cost_prod, total_ads, net_profit)

        c_chart, c_table = st.columns([2, 1])

        with c_chart:
            st.markdown("##### 📈 แนวโน้มค่าคอมรายวัน (Daily Trend)")

            df_chart_c = df_comm.groupby('Day').agg({
                'CAL_COM_ADMIN': 'sum',
                'CAL_COM_TELESALE': 'sum'
            }).reset_index()

            df_merged_c = pd.merge(df_full_days, df_chart_c, on='Day', how='left').fillna(0)

            df_melt = df_merged_c.melt(id_vars=['Day'], value_vars=['CAL_COM_ADMIN', 'CAL_COM_TELESALE'], var_name='Role', value_name='Commission')
            df_melt['Role'] = df_melt['Role'].map({'CAL_COM_ADMIN': 'Admin', 'CAL_COM_TELESALE': 'Telesale'})

            chart_comm = alt.Chart(df_melt).mark_line(point=True).encode(
                x=alt.X('Day:O', title='วันที่'),
                y=alt.Y('Commission', title='ค่าคอม (บาท)'),
                color=alt.Color('Role', scale=alt.Scale(domain=['Admin', 'Telesale'], range=['#9b59b6', '#e67e22'])),
                tooltip=['Day', 'Role', alt.Tooltip('Commission', format=',.0f')]
            ).interactive()
            st.altair_chart(chart_comm, use_container_width=True)

        with c_table:
            st.markdown("##### 📋 สรุปตามทีม (Team Summary)")
            comm_data = [
                {'กลุ่มพนักงาน (Team)': 'Admin', 'ค่าคอมรวม (บาท)': total_admin},
                {'กลุ่มพนักงาน (Team)': 'Telesale', 'ค่าคอมรวม (บาท)': total_tele},
                {'กลุ่มพนักงาน (Team)': 'รวมทั้งหมด', 'ค่าคอมรวม (บาท)': total_all}
            ]
            df_table_c = pd.DataFrame(comm_data)

            st.dataframe(
                df_table_c.style.format({'ค่าคอมรวม (บาท)': '{:,.2f}'}),
                use_container_width=True,
                hide_index=True
            )

    st.markdown("---")
    st.markdown(f"### 📅 ภาพรวมทั้งปี: {sel_year_c}")

    df_template_months = pd.DataFrame({
        'Month_Num': range(1, 13),
        'Month_Thai': thai_months
    })

    df_year_comm = df_daily[df_daily['Year'] == sel_year_c].copy()

    if not df_year_comm.empty:
        df_year_agg = df_year_comm.groupby(['Month_Num']).agg({
            'CAL_COM_ADMIN': 'sum',
            'CAL_COM_TELESALE': 'sum'
        }).reset_index()
    else:
        df_year_agg = pd.DataFrame(columns=['Month_Num', 'CAL_COM_ADMIN', 'CAL_COM_TELESALE'])

    df_final_chart = pd.merge(df_template_months, df_year_agg, on='Month_Num', how='left').fillna(0)

    df_year_melt = df_final_chart.melt(id_vars=['Month_Num', 'Month_Thai'],
                                    value_vars=['CAL_COM_ADMIN', 'CAL_COM_TELESALE'],
                                    var_name='Role', value_name='Commission')
    df_year_melt['Role'] = df_year_melt['Role'].map({'CAL_COM_ADMIN': 'Admin', 'CAL_COM_TELESALE': 'Telesale'})

    chart_year = alt.Chart(df_year_melt).mark_bar().encode(
        x=alt.X('Month_Thai', sort=thai_months, title='เดือน'),
        y=alt.Y('Commission', title='ค่าคอม (บาท)'),
        color=alt.Color('Role', scale=alt.Scale(domain=['Admin', 'Telesale'], range=['#9b59b6', '#e67e22'])),
        tooltip=['Month_Thai', 'Role', alt.Tooltip('Commission', format=',.0f')]
    ).properties(height=350).interactive()

    st.altair_chart(chart_year, use_container_width=True)
