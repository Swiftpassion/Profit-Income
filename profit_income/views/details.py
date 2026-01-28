import streamlit as st
import pandas as pd
from utils.db_service import fetch_orders
from utils.common import format_thai_date

def render_details():
    st.header("📦 รายละเอียดออเดอร์แยกรายสินค้า")
    sub_plat_list = ["TIKTOK", "SHOPEE", "LAZADA"]
    selected_platform = st.radio("เลือกแพลตฟอร์ม", sub_plat_list, horizontal=True)
    st.markdown("---")
    
    col_d1, col_d2 = st.columns(2)
    with col_d1: d_start_det = st.date_input("เริ่มวันที่", st.session_state.d_start, key="det_start")
    with col_d2: d_end_det = st.date_input("ถึงวันที่", st.session_state.d_end, key="det_end")

    try:
        # Use cached function with DB-level filtering
        # Note: We fetch loosely based on date to ensure we get everything, 
        # but exact timestamp filtering might still be needed if created_date in DB is datetime
        raw_df = fetch_orders(platform=selected_platform, start_date=d_start_det, end_date=d_end_det)
        
        if not raw_df.empty:
            raw_df['created_date'] = pd.to_datetime(raw_df['created_date'], errors='coerce').dt.date
            # Secondary filter just in case of timezone/timestamp edge cases
            mask = (raw_df['created_date'] >= d_start_det) & (raw_df['created_date'] <= d_end_det)
            df = raw_df.loc[mask].copy()
            
            if df.empty:
                st.info(f"ไม่พบข้อมูล {selected_platform} ในช่วงวันที่เลือก")
            else:
                for c in ['sales_amount', 'total_cost', 'fees', 'affiliate', 'settlement_amount', 'unit_cost']:
                    df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
                
                # --- Filters ---
                st.markdown("##### ตัวกรองข้อมูล")
                col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
                with col_f1:
                    filter_prod_name = st.text_input("ค้นหาชื่อสินค้า", "")
                with col_f2:
                    filter_profit_range = st.slider("เลือกช่วง % กำไรสุทธิ", 0, 100, (0, 100))
                with col_f3:
                    st.write("") # Spacer
                    st.write("") 
                    filter_neg_profit = st.checkbox("แสดงเฉพาะออเดอร์ติดลบ (-)")

                # 1. Filter by Product Name (Row level first)
                if filter_prod_name:
                    df = df[df['product_name'].astype(str).str.contains(filter_prod_name, na=False)]

                # 2. Filter by Net Profit % (Need Order Level Aggregation to filter correctly)
                # We need to compute order metrics to filter by them. 
                # Strategy: Group by order_id -> calculate metric -> get list of valid order_ids -> filter original df
                
                # Calculate metrics for all orders currently in df
                ops_cost_fixed = 10.0
                grouped_metrics = df.groupby('order_id').apply(
                    lambda x: pd.Series({
                        'total_sales': x['sales_amount'].sum(),
                        'total_cost': x['total_cost'].sum(),
                        'total_fees': x['fees'].sum(),
                        'total_aff': x['affiliate'].sum()
                    })
                ).reset_index()

                grouped_metrics['net_profit'] = grouped_metrics['total_sales'] - grouped_metrics['total_cost'] - grouped_metrics['total_fees'] - grouped_metrics['total_aff'] - ops_cost_fixed
                
                # Avoid division by zero
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
                    return # Stop rendering if empty

                # --- Pagination Logic ---
                items_per_page = 50
                total_items = len(df)
                total_pages = max(1, (total_items + items_per_page - 1) // items_per_page)

                col_p1, col_p2, col_p3 = st.columns([1, 2, 4])
                with col_p1:
                    page = st.number_input("หน้า", min_value=1, max_value=total_pages, value=1, key="det_page")
                with col_p2:
                    st.empty() # Spacer
                with col_p3:
                    st.caption(f"แสดงหน้า {page}/{total_pages} (ทั้งหมด {total_items:,.0f} รายการ)")

                start_idx = (page - 1) * items_per_page
                end_idx = start_idx + items_per_page
                page_df = df.iloc[start_idx:end_idx]
                # ------------------------

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
                    ops_cost = 10.0
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
                            html += f'<td rowspan="{num_items}" style="border:1px solid #333; text-align:right;">{fmt_num(order_settle)}</td>'
                            html += f'<td rowspan="{num_items}" style="border:1px solid #333; text-align:right; font-weight:bold;">{fmt_num(order_net_profit)}</td>'
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
                st.markdown(f'<div class="custom-table-wrapper">{html}</div>', unsafe_allow_html=True)
    except Exception as e: st.error(f"Error Details: {e}")
