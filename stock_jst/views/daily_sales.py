import streamlit as st
import pandas as pd
import calendar
import urllib.parse
from datetime import date
from utils.data_utils import get_stock_from_sheet, get_sale_from_folder, get_po_data, get_actual_stock_from_folder, clean_text_for_html
from views.shared_dialogs import show_history_dialog

def show_daily_sales():
    thai_months = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", 
                   "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
    today = date.today()
    all_years = [today.year - i for i in range(3)]

    # 🟢 LAZY LOADING
    with st.spinner('กำลังโหลดข้อมูลยอดขาย...'):
        df_master = get_stock_from_sheet()
        df_sale = get_sale_from_folder()

        if not df_master.empty: df_master['Product_ID'] = df_master['Product_ID'].astype(str)
        if not df_sale.empty: df_sale['Product_ID'] = df_sale['Product_ID'].astype(str)
        
        recent_sales_map = {}
        if not df_sale.empty and 'Date_Only' in df_sale.columns:
            max_date = df_sale['Date_Only'].max()
            df_latest_sale = df_sale[df_sale['Date_Only'] == max_date]
            recent_sales_map = df_latest_sale.groupby('Product_ID')['Qty_Sold'].sum().fillna(0).astype(int).to_dict()

        # Load PO only if strictly needed (History Dialog)
        if "history_pid" in st.query_params or st.session_state.active_dialog == "history":
             df_po = get_po_data()
             if not df_po.empty: df_po['Product_ID'] = df_po['Product_ID'].astype(str)
        else:
             df_po = pd.DataFrame()

    st.subheader("📅 สรุปยอดขายรายวัน")
    
    if "history_pid" in st.query_params:
        hist_pid = st.query_params["history_pid"]
        del st.query_params["history_pid"] 
        show_history_dialog(df_master, df_po, fixed_product_id=hist_pid)

    def update_m_dates():
        y = st.session_state.m_y
        m_index = thai_months.index(st.session_state.m_m) + 1
        _, last_day = calendar.monthrange(y, m_index)
        st.session_state.m_d_start = date(y, m_index, 1)
        st.session_state.m_d_end = date(y, m_index, last_day)

    if "m_d_start" not in st.session_state: st.session_state.m_d_start = date(today.year, today.month, 1)
    if "m_d_end" not in st.session_state:
        _, last_day = calendar.monthrange(today.year, today.month)
        st.session_state.m_d_end = date(today.year, today.month, last_day)

    with st.container(border=True):
        st.markdown("##### 🔍 ตัวกรองข้อมูล")
        c_y, c_m, c_s, c_e = st.columns([1, 1.5, 1.5, 1.5])
        with c_y: st.selectbox("ปี", all_years, key="m_y", on_change=update_m_dates)
        with c_m: st.selectbox("เดือน", thai_months, index=today.month-1, key="m_m", on_change=update_m_dates)
        with c_s: st.date_input("วันที่เริ่มต้น", key="m_d_start")
        with c_e: st.date_input("วันที่สิ้นสุด", key="m_d_end")
        
        st.divider()
        
        col_sec_check, col_sec_date = st.columns([2, 2])
        with col_sec_check:
            st.write("") 
            use_focus_date = st.checkbox("🔎 กรองเฉพาะสินค้าที่มียอดขายในวันที่...โปรดติก ✅ และเลือกวันที่", key="use_focus_date")
        focus_date = None
        if use_focus_date:
            with col_sec_date: focus_date = st.date_input("ระบุวันที่ขาย (Focus Date):", value=today, key="filter_focus_date")
        
        st.divider()

        col_cat, col_move, col_sku = st.columns([1.5, 1.5, 3])
        
        category_options = ["แสดงทั้งหมด"]
        if not df_master.empty and 'Product_Type' in df_master.columns:
            unique_types = sorted(df_master['Product_Type'].astype(str).unique().tolist())
            category_options += unique_types
            
        sku_options = []
        if not df_master.empty:
            sku_options = df_master.apply(lambda x: f"{x['Product_ID']} : {x['Product_Name']}", axis=1).tolist()
            
        with col_cat: 
            selected_category = st.selectbox("หมวดหมู่สินค้า", category_options, key="filter_category")
            
        with col_move:
            movement_filter = st.selectbox(
                "การเคลื่อนไหว", 
                ["ทั้งหมด", "สินค้าที่มีการเคลื่อนไหว", 'สินค้าที่ "ไม่มี" การเคลื่อนไหว'],
                key="filter_movement"
            )

        with col_sku: 
            selected_skus = st.multiselect("รายการที่เลือก (Choose options):", sku_options, key="filter_skus")

    start_date = st.session_state.m_d_start
    end_date = st.session_state.m_d_end
    
    if start_date and end_date:
        if start_date > end_date: st.error("⚠️ วันที่เริ่มต้นต้องมาก่อนวันที่สิ้นสุด")
        else:
            if not df_sale.empty and 'Date_Only' in df_sale.columns:
                mask_range = (df_sale['Date_Only'] >= start_date) & (df_sale['Date_Only'] <= end_date)
                df_sale_range = df_sale.loc[mask_range].copy()
                
                df_pivot = pd.DataFrame()
                if not df_sale_range.empty:
                    thai_abbr = ["", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
                    df_sale_range['Day_Col'] = df_sale_range['Order_Time'].apply(lambda x: f"{x.day} {thai_abbr[x.month]}")
                    df_sale_range['Day_Sort'] = df_sale_range['Order_Time'].dt.strftime('%Y%m%d')
                    
                    pivot_data = df_sale_range.groupby(['Product_ID', 'Day_Col', 'Day_Sort'])['Qty_Sold'].sum().reset_index()
                    df_pivot = pivot_data.pivot(index='Product_ID', columns='Day_Col', values='Qty_Sold').fillna(0).astype(int)
                    
                    if use_focus_date and focus_date:
                        products_sold_on_focus = df_sale[(df_sale['Date_Only'] == focus_date) & (df_sale['Qty_Sold'] > 0)]['Product_ID'].unique()
                        df_pivot = df_pivot[df_pivot.index.isin(products_sold_on_focus)]

                if not df_pivot.empty:
                    df_pivot = df_pivot.reset_index()
                    final_report = pd.merge(df_master, df_pivot, on='Product_ID', how='left')
                else: 
                    final_report = df_master.copy()
                
                day_cols = [c for c in final_report.columns if c not in df_master.columns]
                day_cols = [c for c in day_cols if isinstance(c, str) and "🔴" not in c and "หมด" not in c]

                final_report[day_cols] = final_report[day_cols].fillna(0).astype(int)
                
                if selected_category != "แสดงทั้งหมด": final_report = final_report[final_report['Product_Type'] == selected_category]
                if selected_skus:
                    selected_ids = [item.split(" : ")[0] for item in selected_skus]
                    final_report = final_report[final_report['Product_ID'].isin(selected_ids)]
                if use_focus_date and focus_date and not df_pivot.empty:
                     final_report = final_report[final_report['Product_ID'].isin(df_pivot['Product_ID'])]
                elif use_focus_date and focus_date and df_pivot.empty:
                     final_report = pd.DataFrame()

                if final_report.empty: st.warning(f"⚠️ ไม่พบข้อมูลสินค้า")
                else:
                    final_report['Total_Sales_Range'] = final_report[day_cols].sum(axis=1).astype(int)
                    
                    if movement_filter == "สินค้าที่มีการเคลื่อนไหว":
                        final_report = final_report[final_report['Total_Sales_Range'] > 0]
                    elif movement_filter == 'สินค้าที่ "ไม่มี" การเคลื่อนไหว':
                        final_report = final_report[final_report['Total_Sales_Range'] == 0]
                    
                    df_real_stock = get_actual_stock_from_folder()
                    
                    if not df_real_stock.empty:
                        real_stock_map = df_real_stock.set_index('Product_ID')['Real_Stock'].to_dict()
                        final_report['Real_Stock_File'] = final_report['Product_ID'].map(real_stock_map)
                        stock_map = df_master.set_index('Product_ID')['Initial_Stock'].to_dict()
                        
                        final_report['Current_Stock'] = final_report.apply(
                            lambda x: x['Real_Stock_File'] if pd.notna(x['Real_Stock_File']) else (stock_map.get(x['Product_ID'], 0) - recent_sales_map.get(x['Product_ID'], 0)), 
                            axis=1
                        )
                    else:
                        stock_map = df_master.set_index('Product_ID')['Initial_Stock'].to_dict()
                        final_report['Current_Stock'] = final_report['Product_ID'].apply(lambda x: stock_map.get(x, 0) - recent_sales_map.get(x, 0))

                    final_report['Current_Stock'] = pd.to_numeric(final_report['Current_Stock'], errors='coerce').fillna(0).astype(int)

                    if 'Min_Limit' not in final_report.columns: final_report['Min_Limit'] = 0
                    final_report['Min_Limit'] = pd.to_numeric(final_report['Min_Limit'], errors='coerce').fillna(0).astype(int)

                    def calc_sales_status(row):
                        curr = row['Current_Stock']
                        limit = row['Min_Limit']
                        if curr <= 0: return "🔴 หมด"
                        elif curr <= limit: return "⚠️ ใกล้หมด"
                        else: return "🟢 ปกติ"

                    final_report['Status'] = final_report.apply(calc_sales_status, axis=1)
                    
                    if not df_sale_range.empty:
                         pivot_data_temp = df_sale_range.groupby(['Product_ID', 'Day_Col', 'Day_Sort'])['Qty_Sold'].sum().reset_index()
                         sorted_day_cols = sorted(day_cols, key=lambda x: pivot_data_temp[pivot_data_temp['Day_Col'] == x]['Day_Sort'].values[0] if x in pivot_data_temp['Day_Col'].values else 0)
                    else: sorted_day_cols = sorted(day_cols)

                    fixed_cols = ['Product_ID', 'Image', 'Product_Name', 'Product_Type', 'Current_Stock', 'Total_Sales_Range', 'Status']
                    available_fixed = [c for c in fixed_cols if c in final_report.columns]
                    final_df = final_report[available_fixed + sorted_day_cols]
                    
                    st.divider()
                    
                    st.markdown("""
                    <style>
                        .daily-sales-table-wrapper { 
                            overflow-x: auto; 
                            width: 100%; 
                            margin-top: 5px; 
                            background: #1c1c1c; 
                            border-radius: 8px; 
                            border: 1px solid #444; 
                            margin-bottom: 20px;
                        }
                        .daily-sales-table { 
                            width: 100%; 
                            min-width: 1200px; 
                            border-collapse: separate; 
                            border-spacing: 0; 
                            font-size: 11px; 
                            color: #ddd; 
                        }
                        .daily-sales-table th, .daily-sales-table td { padding: 4px 6px; line-height: 1.2; text-align: center; border-bottom: 1px solid #333; border-right: 1px solid #333; white-space: nowrap; vertical-align: middle; }
                        .daily-sales-table thead th { position: sticky; top: 0; z-index: 100; background-color: #1e3c72 !important; color: white !important; font-weight: 700; border-bottom: 2px solid #ffffff !important; min-height: 40px; }
                        .daily-sales-table tbody tr:nth-child(even) td { background-color: #262626 !important; }
                        .daily-sales-table tbody tr:nth-child(odd) td { background-color: #1c1c1c !important; }
                        .daily-sales-table tbody tr:hover td { background-color: #333 !important; }
                        .negative-value { color: #FF0000 !important; font-weight: bold !important; }
                        
                        .col-history { width: 40px !important; min-width: 40px !important; }
                        .col-small { width: 80px !important; min-width: 80px !important; }
                        .col-medium { width: 100px !important; min-width: 100px !important; }
                        .col-image { width: 50px !important; min-width: 50px !important; }
                        .col-name { width: 250px !important; min-width: 200px !important; text-align: left !important; }
                        a.history-link { text-decoration: none; color: white; font-size: 16px; cursor: pointer; }
                        a.history-link:hover { transform: scale(1.2); }
                    </style>
                    """, unsafe_allow_html=True)
                    
                    st.markdown(f"**📊 แสดงผลทั้งหมด:** {len(final_df):,} รายการ")
                    curr_token = st.query_params.get("token", "")

                    chunk_size = 100  
                    
                    for start_idx in range(0, len(final_df), chunk_size):
                        end_idx = start_idx + chunk_size
                        df_chunk = final_df.iloc[start_idx:end_idx]
                        
                        html_parts = []
                        html_parts.append('<div class="daily-sales-table-wrapper"><table class="daily-sales-table">')
                        
                        html_parts.append('<thead><tr>')
                        html_parts.append('<th class="col-history">ประวัติ</th>')
                        html_parts.append('<th class="col-small">รหัส</th>')
                        html_parts.append('<th class="col-image">รูป</th>')
                        html_parts.append('<th class="col-name">ชื่อสินค้า</th>')
                        html_parts.append('<th class="col-small">คงเหลือ</th>')
                        html_parts.append('<th class="col-medium">ยอดรวม</th>')
                        html_parts.append('<th class="col-medium">สถานะ</th>')
                        for day_col in sorted_day_cols: 
                            html_parts.append(f'<th class="col-small">{day_col}</th>')
                        html_parts.append('</tr></thead>')
                        
                        html_parts.append('<tbody>')
                        for idx, row in df_chunk.iterrows():
                            current_stock_class = "negative-value" if row['Current_Stock'] < 0 else ""
                            safe_pid = urllib.parse.quote(str(row['Product_ID']).strip())
                            h_link = f"?history_pid={safe_pid}&token={curr_token}"
                            
                            raw_name = str(row.get("Product_Name", ""))
                            clean_name = clean_text_for_html(raw_name)
                            if len(clean_name) > 50: clean_name = clean_name[:47] + "..."

                            html_parts.append('<tr>')
                            html_parts.append(f'<td class="col-history"><a class="history-link" href="{h_link}" target="_self">📜</a></td>')
                            html_parts.append(f'<td class="col-small">{row["Product_ID"]}</td>')
                            
                            if pd.notna(row.get('Image')) and str(row['Image']).startswith('http'):
                                html_parts.append(f'<td class="col-image"><img src="{row["Image"]}" style="width: 40px; height: 40px; object-fit: cover; border-radius: 4px;"></td>')
                            else: 
                                html_parts.append('<td class="col-image"></td>')
                            
                            html_parts.append(f'<td class="col-name">{clean_name}</td>')
                            html_parts.append(f'<td class="col-small {current_stock_class}">{row["Current_Stock"]}</td>')
                            html_parts.append(f'<td class="col-medium">{row["Total_Sales_Range"]}</td>')
                            html_parts.append(f'<td class="col-medium">{row["Status"]}</td>')
                            
                            for day_col in sorted_day_cols:
                                day_value = row.get(day_col, 0)
                                day_class = "negative-value" if isinstance(day_value, (int, float)) and day_value < 0 else ""
                                val_show = int(day_value) if isinstance(day_value, (int, float)) else day_value
                                html_parts.append(f'<td class="col-small {day_class}">{val_show}</td>')
                            
                            html_parts.append('</tr>')
                        
                        html_parts.append('</tbody></table></div>')
                        
                        st.markdown("".join(html_parts), unsafe_allow_html=True)
            else: st.error("⚠️ ไม่พบข้อมูลการขายในช่วงเวลานี้")
