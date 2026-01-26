import streamlit as st
import pandas as pd
import datetime
import calendar
from datetime import date
from utils.db_service import fetch_orders, fetch_ads
from utils.common import format_thai_date

def render_dashboard():
    thai_months = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
    today = datetime.datetime.now().date()
    
    st.header("📊 สรุปยอดขายทุกแพลตฟอร์ม")
    col_filters = st.columns([1, 1, 1, 1])
    
    if "d_start" not in st.session_state:
        st.session_state.d_start = today.replace(day=1)
        st.session_state.d_end = today

    def update_dates():
        y = st.session_state.sel_year; m_str = st.session_state.sel_month
        try:
            m_idx = thai_months.index(m_str) + 1
            _, days = calendar.monthrange(y, m_idx)
            st.session_state.d_start = date(y, m_idx, 1)
            st.session_state.d_end = date(y, m_idx, days)
        except: pass

    with col_filters[0]: st.selectbox("ปี", [2024, 2025, 2026], index=1, key="sel_year", on_change=update_dates)
    with col_filters[1]: st.selectbox("เดือน", thai_months, index=today.month-1, key="sel_month", on_change=update_dates)
    with col_filters[2]: st.session_state.d_start = st.date_input("วันที่เริ่ม", st.session_state.d_start)
    with col_filters[3]: st.session_state.d_end = st.date_input("ถึงวันที่", st.session_state.d_end)

    cp1, cp2, cp3, cp4, cp5 = st.columns([1, 1, 1, 1, 6])
    with cp1: all_plat = st.checkbox("✅ ทั้งหมด", value=True)
    with cp2: tiktok_check = st.checkbox("✅ Tiktok", value=all_plat, disabled=all_plat)
    with cp3: shopee_check = st.checkbox("✅ Shopee", value=all_plat, disabled=all_plat)
    with cp4: lazada_check = st.checkbox("✅ Lazada", value=all_plat, disabled=all_plat)

    sel_plats = ['TIKTOK', 'SHOPEE', 'LAZADA'] if all_plat else []
    if not all_plat:
        if tiktok_check: sel_plats.append('TIKTOK')
        if shopee_check: sel_plats.append('SHOPEE')
        if lazada_check: sel_plats.append('LAZADA')

    # Data Processing with Cache
    try:
        # A. ดึงข้อมูลออเดอร์ (Cached)
        raw_df = fetch_orders()
        
        # B. ดึงข้อมูลค่าโฆษณา (Cached)
        ads_all = fetch_ads()
        ads_db = pd.DataFrame()

        # --- SHOP SELECTION ---
        all_shops = set()
        if not raw_df.empty and 'shop_name' in raw_df.columns:
            all_shops.update(raw_df['shop_name'].dropna().unique())
        if not ads_all.empty and 'shop_name' in ads_all.columns:
            all_shops.update(ads_all['shop_name'].dropna().unique())
        
        sorted_shops = sorted(list(all_shops))

        st.markdown("##### 🏪 เลือกร้านค้า (Shop Name)")
        
        # Container for Select All button and Multiselect
        col_shop_sel, col_shop_btn = st.columns([5, 1])
        
        # Logic for Select All
        if 'selected_shops' not in st.session_state:
            st.session_state.selected_shops = sorted_shops

        def select_all_shops():
            st.session_state.selected_shops = sorted_shops
        
        with col_shop_btn:
             if st.button("✅ เลือกทั้งหมด", on_click=select_all_shops, use_container_width=True):
                 pass

        with col_shop_sel:
            selected_shops = st.multiselect(
                "Filter Shop", 
                sorted_shops, 
                default=st.session_state.selected_shops,
                key="shop_multiselect",
                label_visibility="collapsed"
            )
            # Sync session state if user manually changes multiselect
            if selected_shops != st.session_state.selected_shops:
                 st.session_state.selected_shops = selected_shops

        
        if not ads_all.empty:
            # Filter ads data in memory (faster than DB query)
            ads_all['date'] = pd.to_datetime(ads_all['date']).dt.date
            
            # --- FILTER ADS BY SHOP ---
            mask_ads = (ads_all['date'] >= st.session_state.d_start) & (ads_all['date'] <= st.session_state.d_end)
            if 'shop_name' in ads_all.columns and selected_shops:
                mask_ads &= ads_all['shop_name'].isin(selected_shops)
                
            ads_temp = ads_all[mask_ads].copy()
            
            if not ads_temp.empty:
                # Group by date if multiple shops selected to sum up ads
                ads_grouped = ads_temp.groupby('date')[['ads_amount', 'roas_ads']].sum().reset_index()
                
                ads_db = ads_grouped.rename(columns={'date': 'created_date', 'ads_amount': 'manual_ads', 'roas_ads': 'manual_roas'})
                ads_db['manual_ads'] = pd.to_numeric(ads_db['manual_ads'], errors='coerce').fillna(0)
                ads_db['manual_roas'] = pd.to_numeric(ads_db['manual_roas'], errors='coerce').fillna(0)
                ads_db = ads_db[['created_date', 'manual_ads', 'manual_roas']]

        # C. ประมวลผล
        if not raw_df.empty:
            raw_df['created_date'] = pd.to_datetime(raw_df['created_date']).dt.date
            mask = (raw_df['created_date'] >= st.session_state.d_start) & (raw_df['created_date'] <= st.session_state.d_end)
            if 'platform' in raw_df.columns: mask &= raw_df['platform'].str.upper().isin(sel_plats)
            
            # --- FILTER ORDERS BY SHOP ---
            if 'shop_name' in raw_df.columns and selected_shops:
                 mask &= raw_df['shop_name'].isin(selected_shops)

            df = raw_df.loc[mask].copy()

            for c in ['sales_amount', 'total_cost', 'fees', 'affiliate']:
                if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

            date_range = pd.date_range(start=st.session_state.d_start, end=st.session_state.d_end)
            dates_df = pd.DataFrame({'created_date': date_range.date})
            
            daily = df.groupby('created_date').agg(
                success_count=('status', lambda x: (x == 'ออเดอร์สำเร็จ').sum()),
                pending_count=('status', lambda x: (x == 'รอดำเนินการ').sum()),
                return_count=('status', lambda x: (x == 'ตีกลับ').sum()),
                cancel_count=('status', lambda x: (x == 'ยกเลิก').sum()),
                sales_sum=('sales_amount', 'sum'),
                cost_sum=('total_cost', 'sum'),
                fees_sum=('fees', 'sum'),
                affiliate_sum=('affiliate', 'sum')
            ).reset_index()
            
            step1 = pd.merge(dates_df, daily, on='created_date', how='left').fillna(0)
            
            if not ads_db.empty:
                final_df = pd.merge(step1, ads_db, on='created_date', how='left').fillna(0)
            else:
                final_df = step1.copy()
                final_df['manual_ads'] = 0
                final_df['manual_roas'] = 0

            # D. คำนวณ
            calc = final_df.copy()
            calc['total_orders'] = calc['success_count'] + calc['pending_count'] + calc['return_count'] + calc['cancel_count']
            calc['กำไร'] = calc['sales_sum'] - calc['cost_sum'] - calc['fees_sum'] - calc['affiliate_sum']
            calc['ADS VAT 7%'] = calc['manual_ads'] * 0.07
            calc['ค่าแอดรวม'] = calc['manual_ads'] + calc['manual_roas'] + calc['ADS VAT 7%']
            
            def safe_div(a, b): return (a/b*100) if b > 0 else 0
            
            calc['ROAS'] = calc.apply(lambda x: (x['sales_sum']/x['ค่าแอดรวม']) if x['ค่าแอดรวม'] > 0 else 0, axis=1)
            calc['ค่าดำเนินการ'] = calc['total_orders'] * 10
            calc['กำไรสุทธิ'] = calc['กำไร'] - calc['ค่าแอดรวม'] - calc['ค่าดำเนินการ']

            # ... HTML Table Code ...
            st.markdown("""
            <style>
                table.report-table { border-collapse: collapse; width: 100%; font-size: 13px; }
                table.report-table th { color: #ffffff !important; font-weight: bold !important; border: 1px solid #444 !important; padding: 8px; text-align: center; }
                table.report-table td { color: #ffffff !important; border: 1px solid #333; padding: 6px; vertical-align: middle; text-align: center !important; }
                table.report-table tbody tr:nth-of-type(odd) { background-color: #1c1c1c; }
                table.report-table tbody tr:nth-of-type(even) { background-color: #262626; }
                table.report-table tbody tr:hover { background-color: #333333 !important; }
                tr.total-row td { background-color: #010538 !important; color: #ffffff !important; font-weight: bold; border-top: 2px solid #555; }
                .text-red { color: #fa0000 !important; font-weight: bold; }
                .bar-container { position: absolute; bottom: 0; left: 0; height: 4px; background-color: #27ae60; opacity: 0.7; z-index: 1; }
                .cell-content { position: relative; z-index: 2; }
                td.relative-cell { position: relative; padding-bottom: 8px; }
            </style>
            """, unsafe_allow_html=True)

            h_blue = "#1e3c72"; h_cyan = "#22b8e6"; h_orange = "#e67e22"; h_green = "#27ae60"

            html_parts = []
            html_parts.append(f"""
            <div class="custom-table-wrapper">
            <table class="report-table">
                <thead>
                    <tr>
                        <th style="background-color: {h_blue}; min-width: 85px;">วันที่</th>
                        <th style="background-color: {h_blue};">จำนวนออเดอร์</th>
                        <th style="background-color: {h_blue};">ออเดอร์สำเร็จ</th>
                        <th style="background-color: {h_blue};">รอดำเนินการ</th>
                        <th style="background-color: {h_blue};">ตีกลับ</th>
                        <th style="background-color: {h_blue};">ยกเลิก</th>
                        <th style="background-color: {h_blue};">ยอดขายรวม</th>
                        <th style="background-color: {h_cyan};">ROAS</th>
                        <th style="background-color: {h_cyan};">ROAS ADS</th>
                        <th style="background-color: {h_blue};">ทุนรวม</th>
                        <th style="background-color: {h_blue};">%ทุนรวม</th>
                        <th style="background-color: {h_blue};">ค่าธรรมเนียม</th>
                        <th style="background-color: {h_blue};">%ค่าธรรมเนียม</th>
                        <th style="background-color: {h_blue};">ค่าแอฟฟิลิเอต</th>
                        <th style="background-color: {h_blue};">%ค่าแอฟฟิลิเอต</th>
                        <th style="background-color: {h_blue};">กำไร</th>
                        <th style="background-color: {h_blue};">%กำไร</th>
                        <th style="background-color: {h_orange};">ค่าADS</th>
                        <th style="background-color: {h_orange};">ADS VAT 7%</th>
                        <th style="background-color: {h_orange};">ค่าแอดรวม</th>
                        <th style="background-color: {h_blue};">%ค่าแอด</th>
                        <th style="background-color: {h_blue};">ค่าดำเนินการ</th>
                        <th style="background-color: {h_blue};">%ค่าดำเนินการ</th>
                        <th style="background-color: {h_green}; min-width: 120px;">กำไรสุทธิ</th>
                        <th style="background-color: {h_blue};">%กำไรสุทธิ</th>
                    </tr>
                </thead>
                <tbody>
            """)

            def fmt_val(val, is_percent=False):
                s_val = f"{val:,.1f}%" if is_percent else f"{val:,.2f}"
                if is_percent: s_val = f"{val:.1f}%"
                if val < 0: return f'<span class="text-red">{s_val}</span>'
                return s_val

            max_profit = calc['กำไรสุทธิ'].max()
            if max_profit <= 0: max_profit = 1

            for _, r in calc.iterrows():
                sales = r['sales_sum']
                net_profit = r['กำไรสุทธิ']
                date_str = format_thai_date(r['created_date'])

                bar_width = 0
                if net_profit > 0: 
                    bar_width = min((net_profit / max_profit) * 100, 100)
                
                bar_html = ""
                if bar_width > 0:
                    bar_html = f'<div class="bar-container" style="width: {bar_width}%;"></div>'

                row_html = f"""
                <tr>
                    <td class="txt">{date_str}</td>
                    <td class="num">{int(r['total_orders'])}</td>
                    <td class="num">{int(r['success_count'])}</td>
                    <td class="num">{int(r['pending_count'])}</td>
                    <td class="num">{int(r['return_count'])}</td>
                    <td class="num">{int(r['cancel_count'])}</td>
                    <td class="num">{fmt_val(sales)}</td>
                    <td class="num">{fmt_val(r['ROAS'])}</td>
                    <td class="num">{fmt_val(r['manual_roas'])}</td>
                    <td class="num">{fmt_val(r['cost_sum'])}</td>
                    <td class="num">{fmt_val(safe_div(r['cost_sum'], sales), True)}</td>
                    <td class="num">{fmt_val(r['fees_sum'])}</td>
                    <td class="num">{fmt_val(safe_div(r['fees_sum'], sales), True)}</td>
                    <td class="num">{fmt_val(r['affiliate_sum'])}</td>
                    <td class="num">{fmt_val(safe_div(r['affiliate_sum'], sales), True)}</td>
                    <td class="num">{fmt_val(r['กำไร'])}</td>
                    <td class="num">{fmt_val(safe_div(r['กำไร'], sales), True)}</td>
                    <td class="num">{fmt_val(r['manual_ads'])}</td>
                    <td class="num">{fmt_val(r['ADS VAT 7%'])}</td>
                    <td class="num">{fmt_val(r['ค่าแอดรวม'])}</td>
                    <td class="num">{fmt_val(safe_div(r['ค่าแอดรวม'], sales), True)}</td>
                    <td class="num">{fmt_val(r['ค่าดำเนินการ'])}</td>
                    <td class="num">{fmt_val(safe_div(r['ค่าดำเนินการ'], sales), True)}</td>
                    <td class="num font-bold relative-cell">
                        <span class="cell-content">{fmt_val(net_profit)}</span>
                        {bar_html}
                    </td>
                    <td class="num">{fmt_val(safe_div(net_profit, sales), True)}</td>
                </tr>"""
                html_parts.append(row_html.replace('\n', ''))

            # --- TOTAL ROW ---
            sum_sales = calc['sales_sum'].sum()
            sum_cost = calc['cost_sum'].sum()
            sum_fee = calc['fees_sum'].sum()
            sum_aff = calc['affiliate_sum'].sum()
            sum_profit_gross = calc['กำไร'].sum()
            sum_ads = calc['manual_ads'].sum()
            sum_ads_vat = calc['ADS VAT 7%'].sum()
            sum_ads_total = calc['ค่าแอดรวม'].sum()
            sum_ops = calc['ค่าดำเนินการ'].sum()
            sum_net_profit = calc['กำไรสุทธิ'].sum()
            
            total_roas = (sum_sales / sum_ads_total) if sum_ads_total > 0 else 0
            avr_ROAS_ADS = calc['manual_roas'].mean() if len(calc) > 0 else 0
            
            total_html = f"""
            <tr class="total-row">
                <td class="txt">รวม</td>
                <td class="num">{int(calc['total_orders'].sum())}</td>
                <td class="num">{int(calc['success_count'].sum())}</td>
                <td class="num">{int(calc['pending_count'].sum())}</td>
                <td class="num">{int(calc['return_count'].sum())}</td>
                <td class="num">{int(calc['cancel_count'].sum())}</td>
                <td class="num">{fmt_val(sum_sales)}</td>
                <td class="num">{fmt_val(total_roas)}</td>
                <td class="num">{fmt_val(avr_ROAS_ADS)}</td>
                <td class="num">{fmt_val(sum_cost)}</td>
                <td class="num">{fmt_val(safe_div(sum_cost, sum_sales), True)}</td>
                <td class="num">{fmt_val(sum_fee)}</td>
                <td class="num">{fmt_val(safe_div(sum_fee, sum_sales), True)}</td>
                <td class="num">{fmt_val(sum_aff)}</td>
                <td class="num">{fmt_val(safe_div(sum_aff, sum_sales), True)}</td>
                <td class="num">{fmt_val(sum_profit_gross)}</td>
                <td class="num">{fmt_val(safe_div(sum_profit_gross, sum_sales), True)}</td>
                <td class="num">{fmt_val(sum_ads)}</td>
                <td class="num">{fmt_val(sum_ads_vat)}</td>
                <td class="num">{fmt_val(sum_ads_total)}</td>
                <td class="num">{fmt_val(safe_div(sum_ads_total, sum_sales), True)}</td>
                <td class="num">{fmt_val(sum_ops)}</td>
                <td class="num">{fmt_val(safe_div(sum_ops, sum_sales), True)}</td>
                <td class="num">{fmt_val(sum_net_profit)}</td>
                <td class="num">{fmt_val(safe_div(sum_net_profit, sum_sales), True)}</td>
            </tr>
            """
            html_parts.append(total_html.replace('\n', ''))

            html_parts.append("</tbody></table></div>")
            st.markdown("".join(html_parts), unsafe_allow_html=True)
            
        else: st.info("ไม่พบข้อมูลในช่วงเวลานี้")
    except Exception as e: st.error(f"Error Processing: {e}")
