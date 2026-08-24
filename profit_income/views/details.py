import streamlit as st
import pandas as pd
import calendar
from datetime import date
from utils.db_service import fetch_orders, get_all_shops
from utils.common import format_thai_date

THAI_MONTHS = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]

def _update_det_month():
    y = st.session_state.det_sel_year
    m_str = st.session_state.det_sel_month
    try:
        m_idx = THAI_MONTHS.index(m_str) + 1
        _, days = calendar.monthrange(y, m_idx)
        st.session_state.det_start = date(y, m_idx, 1)
        st.session_state.det_end = date(y, m_idx, days)
    except Exception:
        pass

def render_details():
    st.header("📦 รายละเอียดออเดอร์แยกรายสินค้า")
    sub_plat_list = ["TIKTOK", "SHOPEE", "LAZADA"]
    selected_platform = st.radio("เลือกแพลตฟอร์ม", sub_plat_list, horizontal=True)
    st.markdown("---")

    # ตัวเลือกร้านค้าของแพลตฟอร์มที่เลือก
    try:
        shops_df = get_all_shops()
        shop_opts = sorted(shops_df.loc[shops_df['platform'] == selected_platform, 'shop_name'].dropna().unique().tolist())
    except Exception:
        shop_opts = []

    today = date.today()
    year_opts = [today.year - 2, today.year - 1, today.year]
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.selectbox("เลือกปี", year_opts, index=2, key="det_sel_year", on_change=_update_det_month)
    with col_m2:
        st.selectbox("เลือกเดือน", THAI_MONTHS, index=today.month - 1, key="det_sel_month", on_change=_update_det_month)

    # ตั้งค่าเริ่มต้นให้ session state ครั้งแรกเท่านั้น เพื่อไม่ให้ชนกับการ set ค่าผ่าน callback เลือกเดือน
    if "det_start" not in st.session_state:
        st.session_state.det_start = st.session_state.d_start
    if "det_end" not in st.session_state:
        st.session_state.det_end = st.session_state.d_end

    col_d1, col_d2, col_d3 = st.columns(3)
    with col_d1: d_start_det = st.date_input("เริ่มวันที่", key="det_start")
    with col_d2: d_end_det = st.date_input("ถึงวันที่", key="det_end")
    with col_d3: selected_shop = st.selectbox("เลือกร้านค้า", ["ทั้งหมด"] + shop_opts, key=f"det_shop_{selected_platform}")

    # --- Filters (always rendered, even when no data) ---
    st.markdown("##### ตัวกรองข้อมูล")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        filter_order_id = st.text_input("ค้นหาเลขคำสั่งซื้อ", "", key="det_order_id")
    with col_f2:
        filter_prod_name = st.text_input("ค้นหาชื่อสินค้า / รหัสสินค้า", "", key="det_prod_sku")

    col_f3, col_f4 = st.columns([3, 1])
    with col_f3:
        filter_profit_range = st.slider("เลือกช่วง % กำไรสุทธิ", 0, 100, (0, 100))
    with col_f4:
        st.write("")
        st.write("")
        filter_neg_profit = st.checkbox("แสดงเฉพาะออเดอร์ติดลบ (-)")

    col_f5, col_f6, col_f7 = st.columns(3)
    with col_f5:
        filter_has_fees = st.checkbox("แสดงเฉพาะออเดอร์ที่มีค่าธรรมเนียม (≠ 0)", key="det_has_fees")
    with col_f6:
        filter_has_affiliate = st.checkbox("แสดงเฉพาะออเดอร์ที่มีค่าแอฟฟิลิเอต (≠ 0)", key="det_has_aff")
    with col_f7:
        filter_zero_cost = st.checkbox("แสดงเฉพาะสินค้าที่ต้นทุน = 0", key="det_zero_cost")

    try:
        raw_df = fetch_orders(platform=selected_platform, start_date=d_start_det, end_date=d_end_det)

        if raw_df.empty:
            st.info(f"ไม่พบข้อมูล {selected_platform} ในช่วงวันที่เลือก")
            return

        raw_df['created_date'] = pd.to_datetime(raw_df['created_date'], errors='coerce').dt.date
        in_range = (raw_df['created_date'] >= d_start_det) & (raw_df['created_date'] <= d_end_det)
        df = raw_df.loc[in_range | raw_df['created_date'].isna()].copy()

        # Filter แยกร้าน
        if selected_shop != "ทั้งหมด" and 'shop_name' in df.columns:
            df = df[df['shop_name'] == selected_shop]

        if df.empty:
            st.info(f"ไม่พบข้อมูล {selected_platform} ในช่วงวันที่เลือก")
            return

        for c in ['sales_amount', 'total_cost', 'fees', 'affiliate', 'settlement_amount', 'unit_cost']:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        if 'has_income' not in df.columns:
            df['has_income'] = True
        df['has_income'] = df['has_income'].fillna(True).astype(bool)

        # TikTok/Lazada: กำไรสุทธิ = ยอดเงินที่ได้รับจริง (settlement) - ต้นทุน - ค่าดำเนินการ
        # Shopee ยังใช้สูตรเดิม = ยอดขาย - ต้นทุน - ค่าธรรมเนียม - ค่าแอฟฟิลิเอต - ค่าดำเนินการ
        is_settlement = selected_platform in ('TIKTOK', 'LAZADA')
        if is_settlement:
            st.caption("ℹ️ กำไรสุทธิคำนวณจาก **ยอดเงินที่ได้รับจริง (Settlement) − ต้นทุน − ค่าดำเนินการ** | ⚠️ = ยังไม่มี Income เข้ามาตรงกับออเดอร์นี้ (ยอดเงินที่ได้รับจริง/กำไรสุทธิยังไม่ควรใช้อ้างอิง)")

        # 1. Filter by Order ID
        if filter_order_id:
            df = df[df['order_id'].astype(str).str.contains(filter_order_id, na=False, case=False)]

        # 2. Filter by Product Name or SKU
        if filter_prod_name:
            name_match = df['product_name'].astype(str).str.contains(filter_prod_name, na=False, case=False)
            sku_match = df['sku'].astype(str).str.contains(filter_prod_name, na=False, case=False)
            df = df[name_match | sku_match]

        # 3. Filter by Fees / Affiliate (order-level: keep order if sum > 0)
        if filter_has_fees or filter_has_affiliate:
            order_fee_sums = df.groupby('order_id')[['fees', 'affiliate']].sum()
            fee_mask = (order_fee_sums['fees'] > 0) if filter_has_fees else pd.Series(True, index=order_fee_sums.index)
            aff_mask = (order_fee_sums['affiliate'] > 0) if filter_has_affiliate else pd.Series(True, index=order_fee_sums.index)
            valid_fee_orders = order_fee_sums.index[fee_mask & aff_mask]
            df = df[df['order_id'].isin(valid_fee_orders)]

        # 3.5 Filter by zero unit_cost (row-level: keeps only items with cost = 0)
        if filter_zero_cost:
            df = df[df['unit_cost'] == 0]

        # 4. Filter by Net Profit % (order-level aggregation)
        # ออเดอร์ที่ "ยกเลิก" ไม่คิดค่าดำเนินการ 10 บาท/ออเดอร์
        ops_cost_fixed = 10.0
        grouped_metrics = df.groupby('order_id').agg(
            total_sales=('sales_amount', 'sum'),
            total_settle=('settlement_amount', 'sum'),
            total_cost=('total_cost', 'sum'),
            total_fees=('fees', 'sum'),
            total_aff=('affiliate', 'sum'),
            is_cancelled=('status', lambda s: (s == 'ยกเลิก').all()),
        ).reset_index()

        grouped_metrics['ops_cost'] = grouped_metrics['is_cancelled'].apply(lambda c: 0.0 if c else ops_cost_fixed)
        if is_settlement:
            grouped_metrics['net_profit'] = grouped_metrics['total_settle'] - grouped_metrics['total_cost'] - grouped_metrics['ops_cost']
        else:
            grouped_metrics['net_profit'] = grouped_metrics['total_sales'] - grouped_metrics['total_cost'] - grouped_metrics['total_fees'] - grouped_metrics['total_aff'] - grouped_metrics['ops_cost']
        grouped_metrics['net_profit_pct'] = grouped_metrics.apply(
            lambda row: (row['net_profit'] / row['total_sales'] * 100) if row['total_sales'] > 0 else 0, axis=1
        )

        valid_orders_mask = pd.Series(True, index=grouped_metrics.index)
        if filter_neg_profit:
            valid_orders_mask = valid_orders_mask & (grouped_metrics['net_profit'] < 0)
        else:
            valid_orders_mask = valid_orders_mask & (grouped_metrics['net_profit_pct'] >= filter_profit_range[0]) & (grouped_metrics['net_profit_pct'] <= filter_profit_range[1])

        valid_order_ids = grouped_metrics.loc[valid_orders_mask, 'order_id']
        df = df[df['order_id'].isin(valid_order_ids)]

        df = df.sort_values(by=['created_date', 'order_id'], ascending=[False, False])

        if df.empty:
            st.warning("ไม่พบข้อมูลตามเงื่อนไขที่เลือก")
            return

        # --- Pagination (แบ่งตามเลขคำสั่งซื้อ ไม่ใช่แถวสินค้า กันออเดอร์คร่อมหน้า) ---
        items_per_page = 50
        order_seq = df['order_id'].drop_duplicates().tolist()
        total_items = len(order_seq)
        total_pages = max(1, (total_items + items_per_page - 1) // items_per_page)

        col_p1, col_p2, col_p3 = st.columns([1, 2, 4])
        with col_p1:
            page = st.number_input("หน้า", min_value=1, max_value=total_pages, value=1, key="det_page")
        with col_p2:
            st.empty()
        with col_p3:
            st.caption(f"แสดงหน้า {page}/{total_pages} (ทั้งหมด {total_items:,.0f} ออเดอร์)")

        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_orders = order_seq[start_idx:end_idx]
        page_df = df[df['order_id'].isin(page_orders)]

        h_blue = "#1e3c72"; h_cyan = "#22b8e6"; h_green = "#27ae60"
        html = f"""
        <table style="width:100%; border-collapse: collapse; font-size: 13px; color: white;">
            <thead>
                <tr>
                    <th style="background-color: {h_blue}; padding: 8px; border: 1px solid #444;">วันที่ทำการสั่งซื้อ</th>
                    <th style="background-color: {h_blue}; padding: 8px; border: 1px solid #444;">เลขคำสั่งซื้อ</th>
                    <th style="background-color: {h_blue}; padding: 8px; border: 1px solid #444;">ชื่อสินค้า</th>
                    <th style="background-color: {h_blue}; padding: 8px; border: 1px solid #444;">รหัสสินค้า</th>
                    <th style="background-color: {h_blue}; padding: 8px; border: 1px solid #444;">ยอดขาย</th>
                    <th style="background-color: {h_cyan}; padding: 8px; border: 1px solid #444;">ทุน</th>
                    <th style="background-color: {h_blue}; padding: 8px; border: 1px solid #444;">%ทุน</th>
                    <th style="background-color: {h_blue}; padding: 8px; border: 1px solid #444;">ค่าธรรมเนียม</th>
                    <th style="background-color: {h_blue}; padding: 8px; border: 1px solid #444;">%ค่าธรรมเนียม</th>
                    <th style="background-color: {h_blue}; padding: 8px; border: 1px solid #444;">ค่าแอฟฟิลิเอต</th>
                    <th style="background-color: {h_blue}; padding: 8px; border: 1px solid #444;">%ค่าแอฟฟิลิเอต</th>
                    <th style="background-color: {h_blue}; padding: 8px; border: 1px solid #444;">ค่าดำเนินการ</th>
                    <th style="background-color: {h_blue}; padding: 8px; border: 1px solid #444;">%ค่าดำเนินการ</th>
                    <th style="background-color: {h_blue}; padding: 8px; border: 1px solid #444;">วันที่ได้รับเงิน</th>
                    <th style="background-color: {h_blue}; padding: 8px; border: 1px solid #444;">ยอดเงินที่ได้รับจริง</th>
                    <th style="background-color: {h_green}; padding: 8px; border: 1px solid #444;">กำไรสุทธิ</th>
                    <th style="background-color: {h_green}; padding: 8px; border: 1px solid #444;">%กำไรสุทธิ</th>
                </tr>
            </thead>
            <tbody>
        """
        grouped = page_df.groupby('order_id', sort=False)
        row_counter = 0
        def fmt_num(val, color_neg=True):
            s = f"{val:,.2f}"
            if color_neg and val < 0: return f'<span class="text-red">{s}</span>'
            return s
        def fmt_pct(num, div):
            if div == 0: return "0.0%"
            val = (num/div) * 100
            return f"{val:,.1f}%"

        sum_sales = 0; sum_net_profit = 0
        for order_id, group in grouped:
            row_counter += 1
            bg_color = "#1c1c1c" if row_counter % 2 != 0 else "#262626"
            hover_color = "#333333"

            order_sales = group['sales_amount'].sum()
            order_fees = group['fees'].sum()
            order_aff = group['affiliate'].sum()
            order_settle = group['settlement_amount'].sum()
            order_cost_total = group['total_cost'].sum()
            order_has_income = bool(group['has_income'].all())
            # ออเดอร์ที่ "ยกเลิก" ไม่คิดค่าดำเนินการ 10 บาท/ออเดอร์
            ops_cost = 0.0 if (group['status'] == 'ยกเลิก').all() else 10.0
            if is_settlement:
                order_net_profit = order_settle - order_cost_total - ops_cost
            else:
                order_net_profit = order_sales - order_cost_total - order_fees - order_aff - ops_cost
            sum_sales += order_sales; sum_net_profit += order_net_profit

            created_date_str = format_thai_date(group.iloc[0]['created_date'])
            settle_date_str = format_thai_date(group.iloc[0]['settlement_date']) if group.iloc[0]['settlement_date'] else "-"
            num_items = len(group)

            for i, (idx, row) in enumerate(group.iterrows()):
                html += f'<tr style="background-color: {bg_color};" onmouseover="this.style.backgroundColor=\'{hover_color}\'" onmouseout="this.style.backgroundColor=\'{bg_color}\'">'
                if i == 0:
                    html += f'<td rowspan="{num_items}" style="border:1px solid #333; text-align:center; vertical-align:middle;">{created_date_str}</td>'
                    html += f'<td rowspan="{num_items}" style="border:1px solid #333; text-align:center; vertical-align:middle;">{order_id}</td>'

                prod_name = row.get('product_name', '-')
                sku = row.get('sku', '-')
                unit_cost = row.get('unit_cost', 0)
                item_sales = row.get('sales_amount', 0)
                pct_cost = fmt_pct(unit_cost, item_sales)

                html += f'<td style="border:1px solid #333; padding:5px;">{prod_name}</td>'
                html += f'<td style="border:1px solid #333; text-align:center;">{sku}</td>'

                if i == 0:
                    html += f'<td rowspan="{num_items}" style="border:1px solid #333; text-align:right;">{fmt_num(order_sales)}</td>'

                html += f'<td style="border:1px solid #333; text-align:right;">{fmt_num(unit_cost)}</td>'
                html += f'<td style="border:1px solid #333; text-align:center;">{pct_cost}</td>'

                if i == 0:
                    html += f'<td rowspan="{num_items}" style="border:1px solid #333; text-align:right;">{fmt_num(order_fees)}</td>'
                    html += f'<td rowspan="{num_items}" style="border:1px solid #333; text-align:center;">{fmt_pct(order_fees, order_sales)}</td>'
                    html += f'<td rowspan="{num_items}" style="border:1px solid #333; text-align:right;">{fmt_num(order_aff)}</td>'
                    html += f'<td rowspan="{num_items}" style="border:1px solid #333; text-align:center;">{fmt_pct(order_aff, order_sales)}</td>'
                    html += f'<td rowspan="{num_items}" style="border:1px solid #333; text-align:right;">{fmt_num(ops_cost)}</td>'
                    html += f'<td rowspan="{num_items}" style="border:1px solid #333; text-align:center;">{fmt_pct(ops_cost, order_sales)}</td>'
                    html += f'<td rowspan="{num_items}" style="border:1px solid #333; text-align:center;">{settle_date_str}</td>'
                    no_income_badge = '' if order_has_income else ' <span title="ยังไม่มี Income เข้ามาตรงกับออเดอร์นี้">⚠️</span>'
                    html += f'<td rowspan="{num_items}" style="border:1px solid #333; text-align:right;">{fmt_num(order_settle)}{no_income_badge}</td>'
                    html += f'<td rowspan="{num_items}" style="border:1px solid #333; text-align:right; font-weight:bold;">{fmt_num(order_net_profit)}{no_income_badge}</td>'
                    html += f'<td rowspan="{num_items}" style="border:1px solid #333; text-align:center;">{fmt_pct(order_net_profit, order_sales)}</td>'
                html += "</tr>"

        html += f"""
        <tr style="background-color: #010538; font-weight: bold;">
            <td colspan="4" style="text-align: center; padding: 10px; border-top: 2px solid #555;">รวมทั้งหมด</td>
            <td style="text-align: right; border-top: 2px solid #555;">{fmt_num(sum_sales)}</td>
            <td colspan="10" style="border-top: 2px solid #555;"></td>
            <td style="text-align: right; border-top: 2px solid #555;">{fmt_num(sum_net_profit)}</td>
            <td style="text-align: center; border-top: 2px solid #555;">{fmt_pct(sum_net_profit, sum_sales)}</td>
        </tr>
        """
        html += "</tbody></table>"
        st.markdown(f'<div class="custom-table-wrapper frozen-header-wrapper">{html}</div>', unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error Details: {e}")
