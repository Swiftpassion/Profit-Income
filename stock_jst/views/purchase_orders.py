import streamlit as st
import pandas as pd
import time
import urllib.parse
from datetime import date, datetime, timedelta
import gspread
from utils.data_utils import (
    get_stock_from_sheet, get_po_data, save_po_batch_to_sheet, 
    save_po_edit_split, save_po_edit_update, delete_po_row_from_sheet,
    clean_text_for_html, get_next_auto_po
)
from utils.auth_utils import get_credentials
from views.shared_dialogs import show_info_dialog
from config import MASTER_SHEET_ID, TAB_NAME_PO

@st.cache_data
def generate_po_table_html(df_display, current_timestamp=0):
    # current_timestamp is a dummy arg to force cache invalidation if needed, 
    # though df_display change should suffice.
    
    table_html = """
    <div class='po-table-container'>
    <table class='custom-po-table'>
        <thead>
            <tr>
                <th style='width:60px;'>แก้ไข</th>
                <th>รหัสสินค้า</th>
                <th style='width:50px;'>รูป</th>
                <th>สถานะ</th>
                <th>เลข PO</th>
                <th>ขนส่ง</th>
                <th style='background-color: #5f00bf;'>วันที่สั่งซื้อ</th>
                <th style='background-color: #5f00bf;'>วันคาดการณ์</th>
                <th style='background-color: #5f00bf;'>วันที่ได้รับ</th>
                <th style='background-color: #5f00bf;'>ระยะเวลา</th>
                <th style='background-color: #5f00bf;'>รับแล้ว</th>
                <th style='background-color: #00bf00;'>สั่งซื้อ</th>
                <th style='background-color: #00bf00;'>ต้นทุน/ชิ้น (฿)</th>
                <th>ยอดหยวน (¥)</th>
                <th>ยอดบาทรวม (฿)</th>
                <th>เรทเงิน</th>
                <th>เรทขนส่ง</th>
                <th>คิว (CBM)</th>
                <th>ค่าส่งรวม</th>
                <th>น้ำหนัก (KG)</th>
                <th>ราคา/ชิ้น (¥)</th>
                <th style='background-color: #ff6600;'>SHOPEE</th>
                <th>LAZADA</th>
                <th style='background-color: #000000;'>TIKTOK</th>
                <th>หมายเหตุ</th>
                <th>Link</th>
            </tr>
        </thead>
        <tbody>
    """
    
    def fmt_num(val, decimals=2):
        try: return f"{float(val):,.{decimals}f}"
        except: return "0.00"
    
    def fmt_date(d):
        try:
            if pd.isna(d) or str(d).lower() == 'nat' or str(d).strip() == "": return "-"
            if isinstance(d, str): d = pd.to_datetime(d, errors='coerce')
            if pd.isna(d): return "-"
            return d.strftime("%d/%m/%Y")
        except: return "-"

    grouped = df_display.groupby(['PO_Number', 'Product_ID'], sort=False)
    
    for group_idx, ((po, pid), group) in enumerate(grouped):
        row_count = len(group)
        first_row = group.iloc[0] 
        
        is_internal = (str(first_row.get('Transport_Type', '')).strip() == "สินค้าภายใน")

        total_order_qty = group['Qty_Ordered'].sum()
        if total_order_qty == 0: total_order_qty = 1 
        
        total_yuan = group['Total_Yuan'].sum()
        total_ship_cost = group['Ship_Cost'].sum()
        
        calc_total_thb_used = 0
        if is_internal:
            calc_total_thb_used = group['Total_THB'].sum()
        else:
            for _, r in group.iterrows():
                calc_total_thb_used += (float(r.get('Total_Yuan',0)) * float(r.get('Yuan_Rate',0)))

        cost_per_unit_thb = (calc_total_thb_used + total_ship_cost) / total_order_qty if total_order_qty > 0 else 0
        price_per_unit_yuan = total_yuan / total_order_qty if total_order_qty > 0 else 0
        rate = float(first_row.get('Yuan_Rate', 0))

        bg_color = "#222222" if group_idx % 2 == 0 else "#2e2e2e"
        s_text = str(first_row.get('Status_Text', '-'))
        s_bg = str(first_row.get('Status_BG', '#333'))
        s_col = str(first_row.get('Status_Color', '#fff'))

        for idx, (i, row) in enumerate(group.iterrows()):
            table_html += f'<tr style="background-color: {bg_color};">'
            
            # --- Merged Columns (Left) ---
            if idx == 0:
                # 1. Edit Buttons
                # Inject TOKEN_PLACEHOLDER and TIMESTAMP_PLACEHOLDER
                safe_pid = urllib.parse.quote(str(row['Product_ID']).strip())
                safe_po = urllib.parse.quote(str(row['PO_Number']).strip())
                row_idx_del = row.get("Sheet_Row_Index", 0)

                btn_edit = f"<a href='?edit_po={safe_po}&edit_pid={safe_pid}&t=TIMESTAMP_PH&token=TOKEN_PH' target='_self' style='text-decoration:none; font-size:18px; margin-right:5px;'>✏️</a>"
                btn_del = f"<a href='?delete_idx={row_idx_del}&del_po={safe_po}&token=TOKEN_PH' target='_self' style='text-decoration:none; font-size:18px; color:#ff4b4b;'>🗑️</a>"
                table_html += f'<td rowspan="{row_count}" class="td-merged">{btn_edit}{btn_del}</td>'

                # 2. Product ID & Name
                p_name_raw = str(row.get("Product_Name", ""))
                p_name_clean = clean_text_for_html(p_name_raw)
                p_id = str(row['Product_ID']).strip()
                
                table_html += f'<td rowspan="{row_count}" class="td-merged" title="{p_name_clean}">'
                table_html += f'<div style="font-weight:bold; color:#fff;">{p_id}</div>'
                table_html += f'<div style="font-size:12px; color:#aaa; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:180px;">{p_name_clean}</div>'
                table_html += '</td>'
                
                # 3. Image
                img_src = str(row.get('Image', ''))
                img_tag = f'<img src="{img_src}" style="width:40px; height:40px; object-fit:cover; border-radius:4px;">' if img_src.startswith('http') else ''
                table_html += f'<td rowspan="{row_count}" class="td-merged">{img_tag}</td>'
                
                # 4. Status
                table_html += f'<td rowspan="{row_count}" class="td-merged"><span class="status-badge" style="background-color:{s_bg}; color:{s_col};">{s_text}</span></td>'
                
                # 5. PO Number
                po_num_show = str(row["PO_Number"]).strip()
                table_html += f'<td rowspan="{row_count}" class="td-merged">{po_num_show}</td>'
                
                # 6. Transport Type
                t_type = clean_text_for_html(str(row.get("Transport_Type", "-"))) 
                table_html += f'<td rowspan="{row_count}" class="td-merged">{t_type}</td>'
                
                # 7. Order Date
                d_ord = fmt_date(row["Order_Date"])
                table_html += f'<td rowspan="{row_count}" class="td-merged">{d_ord}</td>'
                
                # 8. Expected Date
                d_exp = fmt_date(row.get("Expected_Date"))
                table_html += f'<td rowspan="{row_count}" class="td-merged">{d_exp}</td>'

            # --- Per-Row Columns ---
            
            # 9. Received Date
            d_recv = fmt_date(row['Received_Date'])
            table_html += f'<td>{d_recv}</td>'
            
            # 10. Wait Days
            wait_txt = "-"
            if pd.notna(row['Received_Date']) and pd.notna(row['Order_Date']):
                try: 
                    wait_days = (row['Received_Date'] - row['Order_Date']).days
                    wait_txt = f"{wait_days} วัน"
                except: pass
            table_html += f'<td>{wait_txt}</td>'

            # 11. Received Qty
            q_recv = int(float(str(row.get('Qty_Received', 0) or 0)))
            q_ord_row = int(float(str(row.get('Qty_Ordered', 0) or 0)))
            style_q = "color:#ff4b4b; font-weight:bold;" if (q_recv > 0 and q_recv != q_ord_row) else ""
            table_html += f'<td style="{style_q}">{q_recv:,}</td>'

            # --- Merged Columns (Right) ---
            if idx == 0:
                # 12. Total Ordered
                table_html += f'<td rowspan="{row_count}" class="td-merged" style="color:#AED6F1; font-weight:bold;">{int(total_order_qty):,}</td>'
                
                # 13. Cost per Unit (THB)
                table_html += f'<td rowspan="{row_count}" class="td-merged">{fmt_num(cost_per_unit_thb)}</td>'
                
                # 14-15. Totals (Yuan / THB)
                val_yuan = "-" if is_internal else fmt_num(total_yuan)
                table_html += f'<td rowspan="{row_count}" class="td-merged">{val_yuan}</td>'
                table_html += f'<td rowspan="{row_count}" class="td-merged">{fmt_num(calc_total_thb_used)}</td>'
                
                # 16-17. Rates
                v_rate = "-" if is_internal else fmt_num(rate)
                v_ship_rate = "-" if is_internal else fmt_num(row.get("Ship_Rate",0))
                table_html += f'<td rowspan="{row_count}" class="td-merged">{v_rate}</td>'
                table_html += f'<td rowspan="{row_count}" class="td-merged">{v_ship_rate}</td>'
                
                # 18-20. Shipping Info
                v_cbm = "-" if is_internal else fmt_num(row.get("CBM",0), 4)
                v_ship_cost = "-" if is_internal else fmt_num(total_ship_cost)
                v_weight = "-" if is_internal else fmt_num(row.get("Transport_Weight",0))
                table_html += f'<td rowspan="{row_count}" class="td-merged">{v_cbm}</td>'
                table_html += f'<td rowspan="{row_count}" class="td-merged">{v_ship_cost}</td>'
                table_html += f'<td rowspan="{row_count}" class="td-merged">{v_weight}</td>'
                
                # 21. Price per Unit (Yuan)
                v_unit_yuan = "-" if is_internal else fmt_num(price_per_unit_yuan)
                table_html += f'<td rowspan="{row_count}" class="td-merged">{v_unit_yuan}</td>'
                
                # 22-24. Selling Prices
                table_html += f'<td rowspan="{row_count}" class="td-merged">{fmt_num(row.get("Shopee_Price",0))}</td>'
                table_html += f'<td rowspan="{row_count}" class="td-merged">{fmt_num(row.get("Lazada_Price",0))}</td>'
                table_html += f'<td rowspan="{row_count}" class="td-merged">{fmt_num(row.get("TikTok_Price",0))}</td>'
                
                # 25. Note
                note_txt = clean_text_for_html(str(row.get("Note","")))
                table_html += f'<td rowspan="{row_count}" class="td-merged" style="font-size:12px;">{note_txt}</td>'
                
                # 26. Links / Icons
                link_val = str(row.get("Link", "")).strip()
                wechat_val = str(row.get("WeChat", "")).strip()
                icons = ""
                if len(link_val) > 5:
                    s_link = urllib.parse.quote(link_val)
                    icons += f"<a href='?view_info={s_link}&t=TIMESTAMP_PH&token=TOKEN_PH' style='text-decoration:none; margin-right:5px;'>🔗</a>"
                if len(wechat_val) > 1:
                    s_chat = urllib.parse.quote(wechat_val)
                    icons += f"<a href='?view_info={s_chat}&t=TIMESTAMP_PH&token=TOKEN_PH' style='text-decoration:none;'>💬</a>"
                table_html += f'<td rowspan="{row_count}" class="td-merged">{icons if icons else "-"}</td>'
            
            table_html += "</tr>"

    table_html += "</tbody></table></div>"
    return table_html

def show_purchase_orders():
    # 🟢 LAZY LOADING FOR PO (Optimization)
    if "po_dataset" not in st.session_state:
        with st.spinner('กำลังโหลดข้อมูล PO... (ดึงข้อมูลล่าสุด)'):
            df_master_fetch = get_stock_from_sheet()
            df_po_fetch = get_po_data()
            
            # Convert types once during fetch
            if not df_master_fetch.empty: 
                df_master_fetch['Product_ID'] = df_master_fetch['Product_ID'].astype(str)
            if not df_po_fetch.empty: 
                df_po_fetch['Product_ID'] = df_po_fetch['Product_ID'].astype(str)
            
            # Store in Session State
            st.session_state.po_dataset = {
                "master": df_master_fetch,
                "po": df_po_fetch
            }

    # Retrieve from Session State
    df_master = st.session_state.po_dataset["master"]
    df_po = st.session_state.po_dataset["po"]
    
    if "view_info" in st.query_params:
        val_to_show = st.query_params["view_info"]
        show_info_dialog(val_to_show)

    col_head, col_action = st.columns([4, 3])
    with col_head: st.subheader("📋 สรุปรายการสั่งซื้อสินค้า")
    with col_action:
        b1, b2, b3, b4 = st.columns(4) 
        
        if b1.button("➕ PO สินค้านำเข้า", type="primary", use_container_width=True): 
            st.session_state.active_dialog = "po_batch"
            st.rerun()
            
        if b2.button("➕ PO หลายรายการ", type="primary", use_container_width=True):
            st.session_state.active_dialog = "po_multi_item"
            st.rerun()

        if b3.button("➕ PO ภายใน", type="secondary", use_container_width=True): 
            st.session_state.active_dialog = "po_internal"
            st.rerun()
            
        if b4.button("🔍 ค้นหา/แก้ไข", type="secondary", use_container_width=True): 
            st.session_state.active_dialog = "po_search"
            st.rerun()

    if not df_po.empty and not df_master.empty:
        df_po_filter = df_po.copy()
        
        if 'Order_Date' in df_po_filter.columns: df_po_filter['Order_Date'] = pd.to_datetime(df_po_filter['Order_Date'], errors='coerce')
        if 'Received_Date' in df_po_filter.columns: df_po_filter['Received_Date'] = pd.to_datetime(df_po_filter['Received_Date'], errors='coerce')
        if 'Expected_Date' in df_po_filter.columns: df_po_filter['Expected_Date'] = pd.to_datetime(df_po_filter['Expected_Date'], errors='coerce')
        df_po_filter['Product_ID'] = df_po_filter['Product_ID'].astype(str)

        df_display = pd.merge(df_po_filter, df_master[['Product_ID','Product_Name','Image','Product_Type']], on='Product_ID', how='left')

        po_options = sorted(df_display['PO_Number'].astype(str).unique().tolist(), reverse=True)
        
        df_display['Product_Label'] = df_display.apply(
            lambda x: f"{x['Product_ID']} : {str(x['Product_Name'])}", axis=1
        )
        product_options = sorted(df_display['Product_Label'].unique().tolist())

        with st.container(border=True):
            st.markdown("##### 🔍 ตัวกรองและค้นหา")
            
            c_po, c_sku, c_status, c_cat = st.columns([1.5, 2.0, 1.2, 1.3])
            
            with c_po:
                sel_po_items = st.multiselect(
                    "📄 เลข PO", 
                    options=po_options,
                    placeholder="เลือกเลข PO..."
                )
                
            with c_sku:
                sel_sku_items = st.multiselect(
                    "📦 SKU / ชื่อสินค้า", 
                    options=product_options,
                    placeholder="เลือกสินค้า..."
                )
            
            with c_status:
                sel_status = st.selectbox("สถานะ:", ["ทั้งหมด", "สินค้าใกล้ถึง", "รอจัดส่ง", "สินค้าไม่ครบ", "เรียบร้อย", "เลยกำหนดจัดส่ง"])
            with c_cat:
                all_types = ["แสดงทั้งหมด"]
                if not df_master.empty and 'Product_Type' in df_master.columns:
                    all_types += sorted(df_master['Product_Type'].astype(str).unique().tolist())
                sel_cat_po = st.selectbox("หมวดหมู่สินค้า", all_types, key="po_cat_filter")
            
            c_check, c_d1, c_d2 = st.columns([1, 1.5, 1.5])
            with c_check:
                use_date_filter = st.checkbox("📅 กรองตามวันที่", value=False)
            with c_d1:
                d_start = st.date_input("ตั้งแต่", value=date.today().replace(day=1), disabled=not use_date_filter)
            with c_d2:
                d_end = st.date_input("ถึง", value=date.today(), disabled=not use_date_filter)

        if sel_po_items:
            df_display = df_display[df_display['PO_Number'].astype(str).isin(sel_po_items)]

        if sel_sku_items:
            df_display = df_display[df_display['Product_Label'].isin(sel_sku_items)]

        if use_date_filter:
            mask_date = (df_display['Order_Date'].dt.date >= d_start) & (df_display['Order_Date'].dt.date <= d_end)
            df_display = df_display[mask_date]
            
        if sel_cat_po != "แสดงทั้งหมด":
            df_display = df_display[df_display['Product_Type'] == sel_cat_po]

        def get_status(row):
            qty_ord = float(row.get('Qty_Ordered', 0))
            qty_recv = float(row.get('Qty_Received', 0))
            if qty_recv >= qty_ord and qty_ord > 0:
                return "เรียบร้อย", "#d4edda", "#155724" 
            if qty_recv > 0 and qty_recv < qty_ord:
                return "สินค้าไม่ครบ", "#fff3cd", "#856404" 
            exp_date = row.get('Expected_Date')
            if pd.notna(exp_date):
                today_date = pd.Timestamp.today().normalize()
                diff_days = (exp_date - today_date).days
                if diff_days < 0:
                     return "เลยกำหนดจัดส่ง", "#f8d7da", "#721c24"
                if 0 <= diff_days <= 4:
                    return "สินค้าใกล้ถึง", "#cce5ff", "#004085" 
            return "รอจัดส่ง", "#f8f9fa", "#333333" 

        status_results = df_display.apply(get_status, axis=1)
        df_display['Status_Text'] = status_results.apply(lambda x: x[0])
        df_display['Status_BG'] = status_results.apply(lambda x: x[1])
        df_display['Status_Color'] = status_results.apply(lambda x: x[2])

        if sel_status != "ทั้งหมด":
            df_display = df_display[df_display['Status_Text'] == sel_status]

        df_display = df_display.sort_values(by=['Order_Date', 'PO_Number', 'Product_ID'], ascending=[False, False, False])
        
        st.markdown("""
        <style>
            .po-table-container { overflow-x: auto; box-shadow: 0 4px 6px rgba(0,0,0,0.3); margin-top: 10px; }
            .custom-po-table { width: 100%; border-collapse: separate; font-size: 13px; color: #e0e0e0; min-width: 2200px; }
            .custom-po-table th { background-color: #1e3c72; color: white; padding: 10px; text-align: center; border-bottom: 2px solid #fff; border-right: 1px solid #4a4a4a; position: sticky; top: 0; white-space: nowrap; vertical-align: middle;}
            .custom-po-table td { padding: 8px 5px; border-bottom: 1px solid #111; border-right: 1px solid #444; vertical-align: middle; text-align: center; }
            .td-merged { border-right: 2px solid #666 !important; background-color: inherit; }
            .status-badge { padding: 4px 8px; border-radius: 12px; font-weight: bold; font-size: 12px; display: inline-block; width: 120px;}
        </style>
        """, unsafe_allow_html=True)



        # Use Cached HTML Generation
        final_html = generate_po_table_html(df_display, int(time.time() // 60)) # Cache for 60s bucket
        
        # Inject Real Token/Timestamp
        curr_token = st.query_params.get("token", "")
        ts_val = str(int(time.time() * 1000))
        final_html = final_html.replace("TOKEN_PH", curr_token).replace("TIMESTAMP_PH", ts_val)
        
        st.markdown(final_html, unsafe_allow_html=True)

    else:
        st.info("ยังไม่มีข้อมูลรายการสั่งซื้อ (PO)")

@st.dialog("📝 บันทึกรับของ / แก้ไข PO", width="large")
def po_edit_dialog_v2(pre_selected_po=None, pre_selected_pid=None):
    selected_row, row_index = None, None
    po_map = {}
    po_map_key = {}
    
    try:
        creds = get_credentials()
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(MASTER_SHEET_ID)
        ws = sh.worksheet(TAB_NAME_PO)
        
        fresh_po_data = ws.get_all_records()
        df_po_fresh = pd.DataFrame(fresh_po_data)
        
        col_map = {
            'รหัสสินค้า': 'Product_ID', 'เลข PO': 'PO_Number', 'ขนส่ง': 'Transport_Type',
            'วันที่สั่งซื้อ': 'Order_Date', 
            'Expected_Date': 'Expected_Date', 'วันที่คาดว่าจะได้รับ': 'Expected_Date', 'วันที่คาดการณ์': 'Expected_Date',
            'วันที่ได้รับ': 'Received_Date', 
            'จำนวน': 'Qty_Ordered',           
            'จำนวนที่ได้รับ': 'Qty_Received', 
            'ราคา/ชิ้น': 'Price_Unit_NoVAT', 'ราคา (หยวน)': 'Total_Yuan', 'เรทเงิน': 'Yuan_Rate',
            'เรทค่าขนส่ง': 'Ship_Rate', 'ขนาด (คิว)': 'CBM', 'ค่าส่ง': 'Ship_Cost', 'น้ำหนัก / KG': 'Transport_Weight',
            'SHOPEE': 'Shopee_Price', 'LAZADA': 'Lazada_Price', 'TIKTOK': 'TikTok_Price', 'หมายเหตุ': 'Note',
            'ราคา (บาท)': 'Total_THB', 'Link_Shop': 'Link', 'WeChat': 'WeChat'
        }
        df_po_fresh = df_po_fresh.rename(columns={k:v for k,v in col_map.items() if k in df_po_fresh.columns})
        
        if not df_po_fresh.empty:
            df_po_fresh['Sheet_Row_Index'] = range(2, len(df_po_fresh) + 2)
            
            for col in ['Qty_Ordered', 'Qty_Received', 'Total_Yuan', 'Yuan_Rate', 'CBM', 'Transport_Weight']:
                if col in df_po_fresh.columns:
                    df_po_fresh[col] = pd.to_numeric(df_po_fresh[col], errors='coerce').fillna(0)
            
            if 'Qty_Received' not in df_po_fresh.columns: df_po_fresh['Qty_Received'] = 0
            if 'Expected_Date' not in df_po_fresh.columns: df_po_fresh['Expected_Date'] = None
            
            df_po_fresh['PO_Str'] = df_po_fresh['PO_Number'].astype(str).str.strip()
            df_po_fresh['PID_Str'] = df_po_fresh['Product_ID'].astype(str).str.strip()

    except Exception as e:
        st.error(f"❌ โหลดข้อมูล PO ล่าสุดไม่ได้: {e}")
        df_po_fresh = get_po_data()
        if not df_po_fresh.empty:
            df_po_fresh['PO_Str'] = df_po_fresh['PO_Number'].astype(str).str.strip()
            df_po_fresh['PID_Str'] = df_po_fresh['Product_ID'].astype(str).str.strip()

    if not df_po_fresh.empty:
        for idx, row in df_po_fresh.iterrows():
            qty_ord = int(row.get('Qty_Ordered', 0))
            recv_date = str(row.get('Received_Date', '')).strip()
            is_received = (recv_date != '' and recv_date.lower() != 'nat')
            status_icon = "✅ รับแล้ว" if is_received else ("✅ ครบ/ปิด" if qty_ord <= 0 else "⏳ รอของ")
            
            po_val = str(row.get('PO_Number','-'))
            pid_val = str(row.get('Product_ID','-'))
            display_text = f"[{status_icon}] {po_val} : {pid_val} (สั่ง: {qty_ord})"
            
            po_map[display_text] = row
            key_id = (po_val.strip(), pid_val.strip())
            po_map_key[key_id] = row

    if pre_selected_po and pre_selected_pid:
        target_key = (str(pre_selected_po).strip(), str(pre_selected_pid).strip())
        if target_key in po_map_key:
            selected_row = po_map_key[target_key]
            if 'Sheet_Row_Index' in selected_row: row_index = selected_row['Sheet_Row_Index']
        else:
            st.error(f"❌ ไม่พบรายการที่เลือก {target_key}")

    if selected_row is None:
        st.caption("🔍 ค้นหารายการที่ต้องการแก้ไข หรือ รับของ (ข้อมูล Real-time)")
        sorted_keys = sorted([k for k in po_map.keys() if isinstance(k, str)], key=lambda x: "⏳" not in x)
        search_key = st.selectbox("เลือกรายการ", options=sorted_keys, index=None, placeholder="พิมพ์เลข PO หรือ รหัสสินค้า...")
        if search_key:
            selected_row = po_map[search_key]
            if 'Sheet_Row_Index' in selected_row: row_index = selected_row['Sheet_Row_Index']
            
    st.divider()

    if selected_row is not None and row_index is not None:
        def get_val(col, default): return selected_row.get(col, default)
        
        pid_current = str(get_val('Product_ID', '')).strip()
        po_current_num = str(get_val('PO_Number', '')).strip()
        pname = get_val('Product_Name', '')
        old_qty = int(get_val('Qty_Ordered', 1))
        current_sheet_idx = int(row_index)
        
        with st.container(border=True):
            c_img, c_detail = st.columns([1, 4])
            img_url = get_val('Image', '')
            
            df_master = get_stock_from_sheet() 
            if not df_master.empty:
                df_master['PID_Str'] = df_master['Product_ID'].astype(str).str.strip()
                m_row = df_master[df_master['PID_Str'] == pid_current]
                if not m_row.empty: 
                    img_url = m_row.iloc[0].get('Image', img_url)
                    pname = m_row.iloc[0].get('Product_Name', pname)
            if img_url: c_img.image(img_url, width=80)
            c_detail.markdown(f"### {pid_current}")
            c_detail.write(f"**{pname}**")

        df_hist_check = df_po_fresh.copy() 
        
        history_rows = df_hist_check[
            (df_hist_check['PO_Str'] == po_current_num) &    
            (df_hist_check['PID_Str'] == pid_current) &      
            (df_hist_check['Sheet_Row_Index'] != current_sheet_idx) & 
            (df_hist_check['Qty_Received'] > 0)              
        ].copy()

        if not history_rows.empty:
            st.markdown("#### 📜 ประวัติการรับของ (History)")
            st.caption(f"ประวัติการรับของก่อนหน้าของ {pid_current} ใน PO: {po_current_num}")
            
            hist_data = []
            history_rows = history_rows.sort_values(by='Received_Date')
            
            for i, (_, h_row) in enumerate(history_rows.iterrows(), 1):
                d_val = h_row.get('Received_Date', '-')
                d_show = "-"
                if pd.notna(d_val) and str(d_val).lower() != 'nat' and str(d_val).strip() != "":
                    try: d_show = pd.to_datetime(d_val).strftime("%d/%m/%Y")
                    except: d_show = str(d_val)
                
                hist_data.append({
                    "รอบที่": f"รอบที่ {i}",
                    "จำนวนที่ได้รับ": int(h_row.get('Qty_Received', 0)),
                    "วันที่ได้รับของ": d_show,
                    "คิวที่ได้รับรอบนี้": float(h_row.get('CBM', 0)),
                    "น้ำหนักที่ได้รับรอบนี้": float(h_row.get('Transport_Weight', 0))
                })
            
            hist_df = pd.DataFrame(hist_data)
            st.dataframe(
                hist_df, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "รอบที่": st.column_config.TextColumn("รอบที่", width="small"),
                    "จำนวนที่ได้รับ": st.column_config.NumberColumn("จำนวนที่ได้รับ", format="%d"),
                    "วันที่ได้รับของ": st.column_config.TextColumn("วันที่ได้รับของ"),
                    "คิวที่ได้รับรอบนี้": st.column_config.NumberColumn("คิวที่ได้รับรอบนี้ (CBM)", format="%.4f"),
                    "น้ำหนักที่ได้รับรอบนี้": st.column_config.NumberColumn("น้ำหนักที่ได้รับรอบนี้ (KG)", format="%.2f"),
                }
            )
            st.divider()
        else:
            st.info(f"ℹ️ ยังไม่มีประวัติการแบ่งรับของก่อนหน้านี้")
            st.divider()

        with st.form(key="full_edit_po_form"):
            curr_trans = get_val('Transport_Type', 'ทางรถ')
            is_internal_check = (curr_trans == "สินค้าภายใน")

            st.markdown("##### 📦 1. ข้อมูลรับของ / แก้ไข CBM รายตัว")
            st.caption("💡 เงื่อนไขที่ 1: หากกรอกช่องนี้ ระบบจะบันทึกค่าลง Database ทันที (ไม่เฉลี่ย)")
            
            r1, r2, r3, r4 = st.columns(4)
            new_qty_recv = r1.number_input("จำนวนที่ได้รับ (ชิ้น)", min_value=0, value=0, key="e_qty_recv")
            
            try: d_recv_def = datetime.strptime(str(get_val('Received_Date', date.today())), "%Y-%m-%d").date()
            except: d_recv_def = date.today()
            new_recv_date = r2.date_input("วันที่ได้รับของ", value=d_recv_def, key="e_recv_date")
            
            new_cbm_recv = r3.number_input("คิวที่รับรอบนี้ (CBM)", min_value=0.0, value=0.0, step=0.001, format="%.4f", key="e_cbm_recv")
            new_weight_recv = r4.number_input("น้ำหนักที่รับรอบนี้ (KG)", min_value=0.0, value=0.0, step=0.1, format="%.2f", key="e_weight_recv")

            st.markdown("---")
            
            with st.expander("📝 แก้ไขรายละเอียด PO & เฉลี่ยยอดรวม (Header & Cost)", expanded=True):
                h1, h2, h3 = st.columns(3)
                new_po = h1.text_input("เลข PO", value=po_current_num, key="e_po")
                trans_opts = ["ทางรถ", "ทางเรือ", "สินค้าภายใน"]
                idx_trans = trans_opts.index(curr_trans) if curr_trans in trans_opts else 0
                new_trans = h2.selectbox("ขนส่ง", trans_opts, index=idx_trans, key="e_trans")
                is_internal = (new_trans == "สินค้าภายใน") 
                
                try: d_ord_def = datetime.strptime(str(get_val('Order_Date', date.today())), "%Y-%m-%d").date()
                except: d_ord_def = date.today()
                new_ord_date = h3.date_input("วันที่สั่งซื้อ", value=d_ord_def, key="e_ord_date")
                
                st.markdown("**ข้อมูลยอดรวม (Total Order Info)**")
                q1, q2, q3, q4 = st.columns(4)
                new_qty_ordered = q1.number_input("จำนวนสั่งทั้งหมด", min_value=1, value=old_qty, key="e_qty_ord")
                
                new_total_yuan_full = 0.0
                new_rate = 0.0
                new_ship_rate = 0.0
                new_total_thb_full = 0.0
                total_cbm_input = 0.0
                total_weight_input = 0.0
                apply_avg_to_all = False

                if is_internal:
                    new_total_thb_full = q2.number_input("ราคาสินค้าบาท (รวม)", min_value=0.0, value=float(get_val('Total_THB', 0)), step=1.0, format="%.2f", key="e_thb_full")
                else:
                    new_total_yuan_full = q2.number_input("ราคาหยวน (รวม)", min_value=0.0, value=float(get_val('Total_Yuan', 0)), step=1.0, format="%.2f", key="e_yuan_full")
                    new_rate = q3.number_input("เรทเงิน", min_value=0.0, value=float(get_val('Yuan_Rate', 5.0)), step=0.01, format="%.2f", key="e_rate")
                    new_ship_rate = q4.number_input("เรทค่าขนส่ง", min_value=0.0, value=float(get_val('Ship_Rate', 6000)), step=50.0, format="%.2f", key="e_ship_rate")

                    st.markdown("---")
                    st.markdown('<span style="color:#ff4b4b;"><b>🚚 เงื่อนไขที่ 2: กรอกยอดรวมเพื่อเฉลี่ย (Total Average)</b></span>', unsafe_allow_html=True)
                    cw1, cw2 = st.columns(2)
                    
                    current_po_rows = df_po_fresh[df_po_fresh['PO_Str'] == po_current_num]
                    sum_cbm = current_po_rows['CBM'].sum() if not current_po_rows.empty else 0.0
                    sum_w = current_po_rows['Transport_Weight'].sum() if not current_po_rows.empty else 0.0
                    
                    total_cbm_input = cw1.number_input("จำนวนคิวทั้งหมด (Total CBM)", min_value=0.0, value=float(sum_cbm), step=0.001, format="%.4f", key="e_tot_cbm")
                    total_weight_input = cw2.number_input("จำนวนน้ำหนักทั้งหมด (Total KG)", min_value=0.0, value=float(sum_w), step=0.1, format="%.2f", key="e_tot_weight")
                    
                    apply_avg_to_all = st.checkbox(f"✅ ยืนยันนำยอดรวมไปหารเฉลี่ยให้สินค้าทุกรายการใน PO : {po_current_num}", value=False)

                st.markdown("---")
                m1, m2, m3 = st.columns(3)
                new_shopee = m1.number_input("Shopee", value=float(get_val('Shopee_Price', 0)), key="e_shop")
                new_lazada = m2.number_input("Lazada", value=float(get_val('Lazada_Price', 0)), key="e_laz")
                new_tiktok = m3.number_input("TikTok", value=float(get_val('TikTok_Price', 0)), key="e_tik")
                new_note = st.text_input("หมายเหตุ", value=get_val('Note', ''), key="e_note")
                l1, l2 = st.columns(2)
                new_link = l1.text_input("Link", value=get_val('Link', ''), key="e_link")
                new_wechat = l2.text_input("WeChat", value=get_val('WeChat', ''), key="e_wechat")

            if st.form_submit_button("💾 บันทึกข้อมูล", type="primary"):
                rows_to_update_batch = []
                
                current_po_rows = df_po_fresh[df_po_fresh['PO_Str'] == po_current_num]
                
                final_total_qty_po = 0
                if not current_po_rows.empty:
                    other_rows_qty = current_po_rows[current_po_rows['Sheet_Row_Index'] != row_index]['Qty_Ordered'].sum()
                    final_total_qty_po = other_rows_qty + new_qty_ordered
                else:
                    final_total_qty_po = new_qty_ordered
                
                if final_total_qty_po <= 0: final_total_qty_po = 1

                avg_cbm_per_unit = total_cbm_input / final_total_qty_po if apply_avg_to_all else 0
                avg_weight_per_unit = total_weight_input / final_total_qty_po if apply_avg_to_all else 0

                targets = current_po_rows if not current_po_rows.empty else pd.DataFrame([selected_row])
                if row_index not in targets['Sheet_Row_Index'].values:
                    targets = pd.DataFrame([selected_row])

                for _, r in targets.iterrows():
                    r_idx = r.get('Sheet_Row_Index', row_index)
                    r_pid = str(r.get('Product_ID', '')).strip()
                    is_current_row = (r_idx == row_index)

                    if is_current_row:
                        curr_qty = new_qty_ordered
                        curr_recv_qty = new_qty_recv
                        curr_tot_yuan = new_total_yuan_full
                        curr_note = new_note
                        curr_po = new_po
                        curr_trans_val = new_trans
                        curr_ord_date = new_ord_date
                        curr_shopee = new_shopee
                        curr_lazada = new_lazada
                        curr_tiktok = new_tiktok
                        curr_link = new_link
                        curr_wechat = new_wechat
                    else:
                        curr_qty = int(r.get('Qty_Ordered', 0))
                        curr_recv_qty = int(r.get('Qty_Received', 0))
                        curr_tot_yuan = float(r.get('Total_Yuan', 0))
                        curr_note = r.get('Note', '')
                        curr_po = r.get('PO_Number', '')
                        curr_trans_val = r.get('Transport_Type', '')
                        try: curr_ord_date = pd.to_datetime(r.get('Order_Date')).date()
                        except: curr_ord_date = None
                        curr_shopee = r.get('Shopee_Price', 0)
                        curr_lazada = r.get('Lazada_Price', 0)
                        curr_tiktok = r.get('TikTok_Price', 0)
                        curr_link = r.get('Link', '')
                        curr_wechat = r.get('WeChat', '')

                    this_row_cbm = float(r.get('CBM', 0))
                    this_row_weight = float(r.get('Transport_Weight', 0))

                    if is_current_row:
                        if new_cbm_recv > 0 or new_weight_recv > 0:
                            this_row_cbm = new_cbm_recv
                            this_row_weight = new_weight_recv
                        elif apply_avg_to_all:
                            this_row_cbm = curr_qty * avg_cbm_per_unit
                            this_row_weight = curr_qty * avg_weight_per_unit
                    else:
                        if apply_avg_to_all and not is_internal:
                             this_row_cbm = curr_qty * avg_cbm_per_unit
                             this_row_weight = curr_qty * avg_weight_per_unit
                    
                    calc_ship_cost = this_row_cbm * new_ship_rate
                    
                    if is_internal:
                         if is_current_row: calc_tot_thb = new_total_thb_full
                         else: calc_tot_thb = float(r.get('Total_THB', 0))
                         calc_unit_thb = calc_tot_thb / curr_qty if curr_qty > 0 else 0
                         calc_unit_yuan = 0
                    else:
                         calc_tot_thb_prod = curr_tot_yuan * new_rate
                         calc_tot_thb = calc_tot_thb_prod + calc_ship_cost
                         calc_unit_thb = calc_tot_thb / curr_qty if curr_qty > 0 else 0
                         calc_unit_yuan = curr_tot_yuan / curr_qty if curr_qty > 0 else 0

                    date_recv_str = ""
                    days_diff = 0
                    if is_current_row:
                        if new_qty_recv > 0:
                            date_recv_str = new_recv_date.strftime("%Y-%m-%d")
                            if curr_ord_date: days_diff = (new_recv_date - curr_ord_date).days
                        else:
                             raw_recv = r.get('Received_Date')
                             if pd.notna(raw_recv) and str(raw_recv).strip() != "" and str(raw_recv).lower() != 'nat':
                                  date_recv_str = pd.to_datetime(raw_recv).strftime("%Y-%m-%d")
                    else:
                        raw_recv = r.get('Received_Date')
                        if pd.notna(raw_recv) and str(raw_recv).strip() != "" and str(raw_recv).lower() != 'nat':
                             date_recv_str = pd.to_datetime(raw_recv).strftime("%Y-%m-%d")
                             days_diff = r.get('Wait_Days', 0)

                    date_ord_str = curr_ord_date.strftime("%Y-%m-%d") if curr_ord_date else ""
                    raw_exp = r.get('Expected_Date')
                    date_exp_str = ""
                    if pd.notna(raw_exp) and str(raw_exp).lower() != 'nat' and str(raw_exp).strip() != "":
                        date_exp_str = pd.to_datetime(raw_exp).strftime("%Y-%m-%d")

                    data_row = [
                        r_pid, curr_po, curr_trans_val, date_ord_str,
                        date_recv_str, days_diff, curr_qty, curr_recv_qty,
                        round(calc_unit_thb, 2), round(curr_tot_yuan, 2), round(calc_tot_thb, 2),
                        new_rate, new_ship_rate, round(this_row_cbm, 4), round(calc_ship_cost, 2), round(this_row_weight, 2), round(calc_unit_yuan, 4),
                        curr_shopee, curr_lazada, curr_tiktok, curr_note, curr_link, curr_wechat,
                        date_exp_str
                    ]
                    rows_to_update_batch.append({"idx": r_idx, "data": data_row})

                if new_qty_recv > 0 and new_qty_recv < new_qty_ordered:
                    rem_qty = new_qty_ordered - new_qty_recv
                    rem_ratio = rem_qty / new_qty_ordered
                    rem_yuan = new_total_yuan_full * rem_ratio
                    
                    data_rem = [
                        pid_current, new_po, new_trans, new_ord_date.strftime("%Y-%m-%d"),
                        None, 0, rem_qty, 0,
                        0, round(rem_yuan, 2), round((new_total_thb_full * rem_ratio) if is_internal else 0, 2),
                        new_rate, new_ship_rate, 0, 0, 0, 0,
                        new_shopee, new_lazada, new_tiktok, f"รอรับส่วนที่เหลือ ({rem_qty})", new_link, new_wechat,
                        date_exp_str
                    ]
                    
                    curr_update_data = next((item['data'] for item in rows_to_update_batch if item['idx'] == row_index), None)
                    if curr_update_data:
                        save_po_edit_split(row_index, data_rem, curr_update_data)
                        st.success("✅ บันทึกรับของ (แยกรายการ) เรียบร้อย!")
                        
                        # 🟢 CLEAR CACHE AFTER SAVE
                        if "po_dataset" in st.session_state: del st.session_state["po_dataset"]
                        
                        st.session_state.active_dialog = None
                        st.session_state.target_edit_data = {}
                        time.sleep(1)
                        st.rerun()
                        return

                success_count = 0
                for item in rows_to_update_batch:
                    if save_po_edit_update(item["idx"], item["data"]):
                        success_count += 1
                
                if success_count > 0:
                    st.success(f"✅ บันทึกเรียบร้อย! (อัปเดต {success_count} รายการ)")
                    
                    # 🟢 CLEAR CACHE AFTER SAVE
                    if "po_dataset" in st.session_state: del st.session_state["po_dataset"]
                    
                    st.session_state.active_dialog = None
                    st.session_state.target_edit_data = {}
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ เกิดข้อผิดพลาดในการบันทึก")

@st.dialog("⚠️ ยืนยันการลบ", width="small")
def delete_confirm_dialog():
    st.warning(f"คุณต้องการลบรายการ PO: {st.session_state.get('target_delete_po')} ใช่หรือไม่?")
    st.caption("การลบนี้จะหายไปจากฐานข้อมูลทันทีและกู้คืนไม่ได้")
    
    col1, col2 = st.columns(2)
    if col1.button("ยืนยันลบ", type="primary", use_container_width=True):
        idx_to_del = st.session_state.get("target_delete_idx")
        if idx_to_del:
            if delete_po_row_from_sheet(idx_to_del):
                st.success("ลบข้อมูลเรียบร้อย")
                
                # 🟢 CLEAR CACHE AFTER DELETE
                if "po_dataset" in st.session_state: del st.session_state["po_dataset"]
                
                st.session_state.active_dialog = None
                time.sleep(1)
                st.rerun()
    
    if col2.button("ยกเลิก", use_container_width=True):
        st.session_state.active_dialog = None
        st.rerun()

@st.dialog("📝 บันทึกข้อมูลการสั่งซื้อ (Batch PO)", width="large")
def po_batch_dialog():
    # --- Function: คำนวณวันที่คาดการณ์อัตโนมัติ ---
    def auto_update_batch_date():
        t_type = st.session_state.get("bp_trans")
        o_date = st.session_state.get("bp_ord_date")
        
        if t_type and o_date:
            days_add = 0
            if t_type == "ทางรถ": days_add = 14
            elif t_type == "ทางเรือ": days_add = 25
            
            # อัปเดตวันที่คาดการณ์ลงใน Session State
            if days_add > 0:
                st.session_state.bp_expected_date = o_date + timedelta(days=days_add)

    # --- Reset Logic ---
    if st.session_state.get("need_reset_inputs", False):
        keys_to_reset = ["bp_sel_prod", "bp_qty", "bp_total_yuan", "bp_note", 
                         "bp_link", "bp_wechat", "bp_shop_s", "bp_shop_l", "bp_shop_t", 
                         "bp_cbm", "bp_weight", "bp_expected_date", "bp_recv_date"]
        for key in keys_to_reset:
            if key in st.session_state: del st.session_state[key]
        st.session_state["need_reset_inputs"] = False
        
        # Reset เสร็จแล้วให้คำนวณวันที่ใหม่ทันที (ใช้ค่า Default ปัจจุบัน)
        # แต่ต้องระวัง key error ถ้ายังไม่ได้ render widget, ดังนั้นข้ามไปก่อนในรอบ reset
        pass

    # --- 1. Header Section ---
    with st.container(border=True):
        st.subheader("1. ข้อมูลเอกสาร (Header)")
        c1, c2, c3 = st.columns(3)
        po_number = c1.text_input("เลข PO", placeholder="XXXXX", key="bp_po_num")
        
        # ✅ เพิ่ม on_change
        transport_type = c2.selectbox(
            "การขนส่ง", 
            ["ทางรถ", "ทางเรือ"], 
            key="bp_trans",
            on_change=auto_update_batch_date 
        )
        
        # ✅ เพิ่ม on_change
        order_date = c3.date_input(
            "วันที่สั่งซื้อ", 
            date.today(), 
            key="bp_ord_date",
            on_change=auto_update_batch_date
        )
        
        # Set Default ครั้งแรก ถ้ายังไม่มีค่าใน Session
        if "bp_expected_date" not in st.session_state:
            # คำนวณเบื้องต้น (Default ทางรถ 14 วัน)
            st.session_state.bp_expected_date = date.today() + timedelta(days=14)

    # --- 2. Item Form Section ---
    with st.container(border=True):
        st.subheader("2. รายละเอียดสินค้า")
        prod_list = []
        df_master = get_stock_from_sheet()
        if not df_master.empty:
            df_master['Product_ID'] = df_master['Product_ID'].astype(str)
            prod_list = df_master.apply(lambda x: f"{x['Product_ID']} : {x['Product_Name']}", axis=1).tolist()
        
        sel_prod = st.selectbox("เลือกสินค้า", prod_list, index=None, key="bp_sel_prod")
        
        img_url = ""
        pid = ""
        if sel_prod:
            pid = sel_prod.split(" : ")[0]
            item_data = df_master[df_master['Product_ID'] == pid]
            if not item_data.empty: img_url = item_data.iloc[0].get('Image', '')

        with st.form(key="add_item_form", clear_on_submit=False):
            col_img, col_data = st.columns([1, 4])
            with col_img:
                if img_url: st.image(img_url, width=100)
                else: st.info("No Image")
            
            with col_data:
                st.markdown('<span style="color:#2ecc71; font-weight:bold;">(กรอกตอนสั่งซื้อ)</span>', unsafe_allow_html=True)
                r1_c1, r1_c2, r1_c3 = st.columns(3)
                
                # key="bp_expected_date" จะถูกอัปเดตอัตโนมัติจาก on_change ด้านบน
                expected_date = r1_c1.date_input("วันที่คาดว่าจะได้รับ", key="bp_expected_date")
                
                qty = r1_c2.number_input("จำนวนสั่งซื้อ (ชิ้น)", min_value=1, value=None, placeholder="XXXXX", key="bp_qty")
                recv_date = r1_c3.date_input("วันที่ได้รับ (ถ้าได้เลย)", value=None, key="bp_recv_date")
                
                r2_c1, r2_c2, r2_c3 = st.columns(3)
                total_yuan = r2_c1.number_input("ราคาหยวนทั้งหมด (¥)", min_value=0.0, step=1.0, value=None, format="%.2f", placeholder="XXXXX", key="bp_total_yuan")
                rate_money = r2_c2.number_input("เรทเงิน", min_value=0.0, step=0.01, value=None, placeholder="5.xx", format="%.2f", key="bp_rate")
                ship_rate = r2_c3.number_input("เรทขนส่ง", min_value=0.0, step=10.0, value=None, placeholder="6000", format="%.2f", key="bp_ship_rate")
                
                st.markdown('<span style="color:#ff4b4b; font-weight:bold;">(กรอกตอนสินค้าเข้า)</span>', unsafe_allow_html=True)
                r3_c1, r3_c2 = st.columns(2)
                cbm_val = r3_c1.number_input("ขนาด (คิว)", min_value=0.0, step=0.001, value=None, format="%.4f", key="bp_cbm")
                weight_val = r3_c2.number_input("น้ำหนัก (KG)", min_value=0.0, step=0.1, value=None, format="%.2f", key="bp_weight")
                
                st.markdown("**ข้อมูลเพิ่มเติม (Link / ราคาขาย)**")
                note = st.text_input("หมายเหตุ (ถ้ามี)", placeholder="XXXXX", key="bp_note")
                l1, l2 = st.columns(2)
                link_shop = l1.text_input("Link", key="bp_link")
                wechat = l2.text_input("WeChat", key="bp_wechat")
                
                p1, p2, p3 = st.columns(3)
                p_shopee = p1.number_input("Shopee", value=None, placeholder="0.00", key="bp_shop_s")
                p_lazada = p2.number_input("Lazada", value=None, placeholder="0.00", key="bp_shop_l")
                p_tiktok = p3.number_input("TikTok", value=None, placeholder="0.00", key="bp_shop_t")

            # --- ปุ่ม Submit ---
            if st.form_submit_button("➕ เพิ่มรายการลงตระกร้า", type="primary"):
                if not sel_prod:
                    st.error("กรุณาเลือกสินค้า")
                else:
                    # Logic Auto PO
                    final_po_num = po_number
                    if not final_po_num:
                        final_po_num = get_next_auto_po()
                        st.toast(f"ℹ️ ใช้เลข PO อัตโนมัติ: {final_po_num}")

                    c_qty = qty if qty is not None else 0
                    c_total_yuan = total_yuan if total_yuan is not None else 0.0
                    c_rate = rate_money if rate_money is not None else 0.0
                    c_cbm = cbm_val if cbm_val is not None else 0.0
                    c_ship_rate = ship_rate if ship_rate is not None else 0.0
                    
                    unit_yuan = c_total_yuan / c_qty if c_qty > 0 else 0
                    total_ship_cost = c_cbm * c_ship_rate
                    total_thb = (c_total_yuan * c_rate) 
                    unit_thb_final = (total_thb + total_ship_cost) / c_qty if c_qty > 0 else 0
                    
                    wait_days = 0
                    if recv_date and order_date: wait_days = (recv_date - order_date).days

                    item = {
                        "SKU": pid, "PO": final_po_num, "Trans": transport_type, "Ord": str(order_date), 
                        "Exp": str(expected_date) if expected_date else "",   
                        "Recv": str(recv_date) if recv_date else "", "Wait": wait_days,
                        "Qty": int(c_qty), "UnitTHB": round(unit_thb_final, 2),
                        "TotYuan": round(c_total_yuan, 2), "TotTHB": round(total_thb, 2), 
                        "Rate": c_rate, "ShipRate": c_ship_rate, "CBM": round(c_cbm, 4), 
                        "ShipCost": round(total_ship_cost, 2), "W": weight_val if weight_val else 0, 
                        "UnitYuan": round(unit_yuan, 4), "Shopee": p_shopee if p_shopee else 0, 
                        "Laz": p_lazada if p_lazada else 0, "Tik": p_tiktok if p_tiktok else 0, 
                        "Note": note, "Link": link_shop, "WeChat": wechat
                    }
                    st.session_state.po_temp_cart.append(item)
                    st.toast(f"✅ เพิ่ม {pid} แล้ว", icon="🛒")
                    st.session_state["need_reset_inputs"] = True
                    st.rerun()

    # --- ส่วนแสดงตระกร้า (Cart Display) ---
    if st.session_state.po_temp_cart:
        st.divider()
        st.write(f"🛒 ตระกร้า ({len(st.session_state.po_temp_cart)} รายการ)")
        cart_df = pd.DataFrame(st.session_state.po_temp_cart)
        st.dataframe(
            cart_df[["SKU", "Qty", "TotYuan", "Exp", "Recv"]], 
            use_container_width=True, hide_index=True,
            column_config={
                "SKU": st.column_config.TextColumn("ชื่อสินค้า"),
                "Qty": st.column_config.NumberColumn("จำนวน", format="%d"),
                "TotYuan": st.column_config.NumberColumn("ราคาหยวนทั้งหมด", format="%.2f"),
                "Exp": st.column_config.TextColumn("วันที่คาดว่าจะได้รับ"),
                "Recv": st.column_config.TextColumn("วันที่ได้รับสินค้า"),
            }
        )
        c1, c2 = st.columns([1, 4])
        if c1.button("🗑️ ล้างตระกร้า"):
            st.session_state.po_temp_cart = []
            st.rerun()
            
        if c2.button("💾 บันทึก PO ทั้งหมด", type="primary"):
            rows = []
            for i in st.session_state.po_temp_cart:
                 rows.append([
                     i["SKU"], i["PO"], i["Trans"], i["Ord"], 
                     i["Recv"], i["Wait"], i["Qty"],  
                     i["Qty"] if i["Recv"] else 0, 
                     i["UnitTHB"], i["TotYuan"], i["TotTHB"],          
                     i["Rate"], i["ShipRate"], i["CBM"], i["ShipCost"], i["W"], i["UnitYuan"], 
                     i["Shopee"], i["Laz"], i["Tik"], i["Note"], i["Link"], i["WeChat"],
                     i["Exp"] 
                 ])
            if save_po_batch_to_sheet(rows):
                st.success("✅ บันทึกสำเร็จ!")
                
                # 🟢 CLEAR CACHE AFTER BATCH SAVE
                if "po_dataset" in st.session_state: del st.session_state["po_dataset"]
                
                st.session_state.po_temp_cart = []
                if "bp_po_num" in st.session_state: del st.session_state["bp_po_num"]
                st.session_state.active_dialog = None 
                time.sleep(1)
                st.rerun()

@st.dialog("📝 บันทึก PO สินค้าภายใน (Internal)", width="large")
def po_internal_batch_dialog():
    # --- Function: คำนวณวันที่คาดการณ์อัตโนมัติ (Internal +3 วัน) ---
    def auto_update_internal_date():
        d = st.session_state.get("int_ord_date", date.today())
        if d:
            st.session_state.int_expected_date = d + timedelta(days=3) # Default 3 วันสำหรับในประเทศ

    # --- Reset Logic ---
    if st.session_state.get("need_reset_inputs_int", False):
        keys_to_reset = ["int_sel_prod", "int_qty", "int_total_thb", "int_note", 
                         "int_link", "int_contact", "int_shop_s", "int_shop_l", "int_shop_t", 
                         "int_expected_date", "int_recv_date"]
        for key in keys_to_reset:
            if key in st.session_state: del st.session_state[key]
        st.session_state["need_reset_inputs_int"] = False
        
        # หลัง Reset ให้คำนวณวันที่ใหม่
        auto_update_internal_date()

    # --- 1. Header Section ---
    with st.container(border=True):
        st.subheader("1. ข้อมูลเอกสาร (Header)")
        c1, c2 = st.columns(2)
        po_number = c1.text_input("เลข PO", placeholder="XXXXX", key="int_po_num")
        
        # เพิ่ม on_change
        order_date = c2.date_input(
            "วันที่สั่งซื้อ", 
            date.today(), 
            key="int_ord_date",
            on_change=auto_update_internal_date
        )
        
        # Set Default ครั้งแรก
        if "int_expected_date" not in st.session_state:
            auto_update_internal_date()

    # --- 2. Item Form Section ---
    with st.container(border=True):
        st.subheader("2. รายละเอียดสินค้า")
        prod_list = []
        df_master = get_stock_from_sheet()
        if not df_master.empty:
            df_master['Product_ID'] = df_master['Product_ID'].astype(str)
            prod_list = df_master.apply(lambda x: f"{x['Product_ID']} : {x['Product_Name']}", axis=1).tolist()
        
        sel_prod = st.selectbox("เลือกสินค้า", prod_list, index=None, key="int_sel_prod")
        
        img_url = ""
        pid = ""
        if sel_prod:
            pid = sel_prod.split(" : ")[0]
            item_data = df_master[df_master['Product_ID'] == pid]
            if not item_data.empty: img_url = item_data.iloc[0].get('Image', '')

        with st.form(key="add_item_form_internal", clear_on_submit=False):
            col_img, col_data = st.columns([1, 4])
            with col_img:
                if img_url: st.image(img_url, width=100)
                else: st.info("No Image")
            
            with col_data:
                st.markdown('<span style="color:#2ecc71; font-weight:bold;">(กรอกตอนสั่งซื้อ)</span>', unsafe_allow_html=True)
                r1_c1, r1_c2, r1_c3 = st.columns(3)
                
                # ช่องวันที่คาดการณ์ (อัปเดตตาม Session State)
                expected_date = r1_c1.date_input("วันที่คาดว่าจะได้รับ", key="int_expected_date")
                
                qty = r1_c2.number_input("จำนวนสั่งซื้อ (ชิ้น)", min_value=1, value=None, placeholder="XXXXX", key="int_qty")
                recv_date = r1_c3.date_input("วันที่ได้รับ (ถ้าได้เลย)", value=None, key="int_recv_date")
                r2_c1, r2_c2 = st.columns(2)
                total_thb = r2_c1.number_input("ราคาสินค้าที่สั่ง (บาท)", min_value=0.0, step=1.0, value=None, format="%.2f", placeholder="XXXXX", key="int_total_thb")
                note = r2_c2.text_input("หมายเหตุ (ถ้ามี)", placeholder="XXXXX", key="int_note")
                st.markdown("**ข้อมูลเพิ่มเติม (Link / ราคาขาย)**")
                r3_c1, r3_c2 = st.columns(2)
                link_shop = r3_c1.text_input("Link", key="int_link")
                contact_other = r3_c2.text_input("ช่องทางติดต่ออื่นๆ (WeChat)", key="int_contact")
                r4_c1, r4_c2, r4_c3 = st.columns(3)
                p_shopee = r4_c1.number_input("Shopee", value=None, placeholder="0.00", key="int_shop_s")
                p_lazada = r4_c2.number_input("Lazada", value=None, placeholder="0.00", key="int_shop_l")
                p_tiktok = r4_c3.number_input("TikTok", value=None, placeholder="0.00", key="int_shop_t")

            if st.form_submit_button("➕ เพิ่มรายการลงตระกร้า", type="primary"):
                if not sel_prod:
                    st.error("กรุณาเลือกสินค้า")
                else:
                    # Logic Auto PO
                    final_po_num = po_number
                    if not final_po_num:
                        final_po_num = get_next_auto_po()
                        st.toast(f"ℹ️ ใช้เลข PO อัตโนมัติ: {final_po_num}")

                    c_qty = qty if qty is not None else 0
                    c_total_thb = total_thb if total_thb is not None else 0.0
                    unit_thb = c_total_thb / c_qty if c_qty > 0 else 0
                    wait_days = 0
                    if recv_date and order_date: wait_days = (recv_date - order_date).days

                    item = {
                        "SKU": pid, "PO": final_po_num, 
                        "Trans": "สินค้าภายใน", "Ord": str(order_date), 
                        "Exp": str(expected_date) if expected_date else "",   
                        "Recv": str(recv_date) if recv_date else "", "Wait": wait_days,
                        "Qty": int(c_qty), "UnitTHB": round(unit_thb, 2), "TotYuan": 0, "TotTHB": round(c_total_thb, 2), 
                        "Rate": 0, "ShipRate": 0, "CBM": 0, "ShipCost": 0, "W": 0, "UnitYuan": 0, 
                        "Shopee": p_shopee if p_shopee else 0, "Laz": p_lazada if p_lazada else 0, "Tik": p_tiktok if p_tiktok else 0, 
                        "Note": note, "Link": link_shop, "WeChat": contact_other
                    }
                    st.session_state.po_temp_cart.append(item)
                    st.toast(f"✅ เพิ่ม {pid} (Internal) แล้ว", icon="🛒")
                    st.session_state["need_reset_inputs_int"] = True
                    st.rerun()

    # --- ส่วนแสดงตระกร้า (Cart) ---
    if st.session_state.po_temp_cart:
        st.divider()
        st.write(f"🛒 ตระกร้า ({len(st.session_state.po_temp_cart)} รายการ)")
        cart_df = pd.DataFrame(st.session_state.po_temp_cart)
        st.dataframe(
            cart_df[["SKU", "Qty", "TotTHB", "Trans"]], 
            use_container_width=True, hide_index=True,
            column_config={
                "SKU": st.column_config.TextColumn("ชื่อสินค้า"),
                "Qty": st.column_config.NumberColumn("จำนวน", format="%d"),
                "TotTHB": st.column_config.NumberColumn("ยอดเงินบาท", format="%.2f"),
                "Trans": st.column_config.TextColumn("ประเภท"),
            }
        )
        c1, c2 = st.columns([1, 4])
        if c1.button("🗑️ ล้างตระกร้า", key="clear_cart_int"):
            st.session_state.po_temp_cart = []
            st.rerun()
            
        if c2.button("💾 บันทึก PO ทั้งหมด", type="primary", key="save_cart_int"):
            rows = []
            for i in st.session_state.po_temp_cart:
                 rows.append([
                     i["SKU"], i["PO"], i["Trans"], i["Ord"], 
                     i["Recv"], i["Wait"], i["Qty"],  
                     i["Qty"] if i["Recv"] else 0, 
                     i["UnitTHB"], i["TotYuan"], i["TotTHB"],          
                     i["Rate"], i["ShipRate"], i["CBM"], i["ShipCost"], i["W"], i["UnitYuan"], 
                     i["Shopee"], i["Laz"], i["Tik"], i["Note"], i["Link"], i["WeChat"],
                     i["Exp"] 
                 ])
            if save_po_batch_to_sheet(rows):
                st.success("✅ บันทึกสำเร็จ!")
                
                # 🟢 CLEAR CACHE AFTER SAVE
                if "po_dataset" in st.session_state: del st.session_state["po_dataset"]
                
                st.session_state.po_temp_cart = []
                if "int_po_num" in st.session_state: del st.session_state["int_po_num"]
                st.session_state.active_dialog = None 
                time.sleep(1)
                st.rerun()

@st.dialog("📝 บันทึก PO หลายรายการ", width="large")
def po_multi_item_dialog():
    # --- Function: Auto-Calculate Expected Date ---
    def auto_update_exp_date():
        # ดึงค่าปัจจุบันจาก State
        t_type = st.session_state.mi_trans
        o_date = st.session_state.mi_ord_date
        
        days_add = 0
        if t_type == "ทางรถ": days_add = 14
        elif t_type == "ทางเรือ": days_add = 25
        
        # ถ้าเข้าเงื่อนไข ให้คำนวณและอัปเดตวันที่คาดการณ์
        if days_add > 0 and o_date:
            st.session_state.mi_exp_date = o_date + timedelta(days=days_add)

    # --- 1. Header Section ---
    with st.container(border=True):
        st.subheader("1. ข้อมูลเอกสาร (Header)")
        h1, h2, h3, h4 = st.columns(4)
        po_number = h1.text_input("เลข PO", placeholder="XXXXX", key="mi_po")
        
        # เพิ่ม on_change เพื่อเรียกฟังก์ชันคำนวณวันที่อัตโนมัติ
        transport = h2.selectbox(
            "การขนส่ง", 
            ["ทางรถ", "ทางเรือ", "สินค้าภายใน"], 
            key="mi_trans",
            on_change=auto_update_exp_date 
        )
        
        # เพิ่ม on_change กรณีเปลี่ยนวันที่สั่งซื้อ ก็ให้คำนวณใหม่ด้วย
        ord_date = h3.date_input(
            "วันที่สั่งซื้อ", 
            date.today(), 
            key="mi_ord_date",
            on_change=auto_update_exp_date
        )
        
        # Logic เริ่มต้น: ถ้าเปิดมาครั้งแรกยังไม่มีค่า ให้คำนวณ Default (ทางรถ +14) ไว้รอเลย
        if "mi_exp_date" not in st.session_state:
            st.session_state.mi_exp_date = date.today() + timedelta(days=14)

        exp_date = h4.date_input("วันที่คาดว่าจะได้รับ", key="mi_exp_date")

    # --- 2. Items Table Section ---
    with st.container(border=True):
        st.subheader("2. รายการสินค้า")
        
        # Prepare Master Data for Dropdown
        prod_list = []
        df_master = get_stock_from_sheet()
        if not df_master.empty:
            df_master['Product_ID'] = df_master['Product_ID'].astype(str)
            prod_list = df_master.apply(lambda x: f"{x['Product_ID']} : {x['Product_Name']}", axis=1).tolist()

        # Data Editor Setup
        if "mi_items_df" not in st.session_state:
            st.session_state.mi_items_df = pd.DataFrame([{"สินค้า": None, "จำนวน": 0}])

        edited_df = st.data_editor(
            st.session_state.mi_items_df,
            column_config={
                "สินค้า": st.column_config.SelectboxColumn("เลือกสินค้า (SKU)", options=prod_list, width="large", required=True),
                "จำนวน": st.column_config.NumberColumn("จำนวนสั่งซื้อ (ชิ้น)", min_value=1, step=1, required=True, width="small"),
            },
            num_rows="dynamic",
            use_container_width=True,
            key="mi_editor"
        )
        
        # Calculate Total Qty immediately for use in Section 3
        total_qty_calculated = edited_df["จำนวน"].sum()

    # --- 3. Grand Totals & Receiving Section ---
    with st.container(border=True):
        st.subheader("3. ยอดรวมทั้งหมด (Grand Totals)")
        
        # --- 3.1 Ordering Info ---
        st.markdown('<span style="color:#2ecc71; font-weight:bold;">(กรอกตอนสั่งซื้อ)</span>', unsafe_allow_html=True)
        t1, t2, t3, t4 = st.columns(4)
        
        rate_money = t1.number_input("เรทเงิน", min_value=0.0, step=0.01, value=None, placeholder="5.00", format="%.2f", key="mi_rate")
        ship_rate = t2.number_input("เรทขนส่ง", min_value=0.0, step=10.0, value=None, placeholder="6000.00", format="%.2f", key="mi_ship_rate")
        
        grand_total_yuan = t3.number_input("ราคาหยวนทั้งหมด (¥)", min_value=0.0, step=1.0, format="%.2f", key="mi_tot_yuan")
        note = t4.text_input("หมายเหตุ (Note)", key="mi_note")
        
        st.divider()

        # --- 3.2 Receiving Info ---
        st.markdown('<span style="color:#ff4b4b; font-weight:bold;">(กรอกตอนสินค้าเข้า)</span> 💡 หากกรอกจะถือว่าได้รับของแล้ว', unsafe_allow_html=True)
        r1, r2, r3 = st.columns(3)
        recv_date = r1.date_input("วันที่ได้รับสินค้า", value=None, key="mi_recv_date")
        grand_total_cbm = r2.number_input("คิวทั้งหมด (Total CBM)", min_value=0.0, step=0.001, format="%.4f", key="mi_tot_cbm")
        grand_total_weight = r3.number_input("น้ำหนักทั้งหมด (Total KG)", min_value=0.0, step=0.1, format="%.2f", key="mi_tot_weight")

        # --- Real-time Calculation Logic ---
        unit_yuan = grand_total_yuan / total_qty_calculated if total_qty_calculated > 0 else 0
        unit_cbm = grand_total_cbm / total_qty_calculated if total_qty_calculated > 0 and grand_total_cbm > 0 else 0
        unit_weight = grand_total_weight / total_qty_calculated if total_qty_calculated > 0 and grand_total_weight > 0 else 0

        # 2. Create Preview Table
        preview_data = []
        if total_qty_calculated > 0 and not edited_df.empty:
            for idx, row in edited_df.iterrows():
                if row["สินค้า"] and row["จำนวน"] > 0:
                    sku = row["สินค้า"].split(" : ")[0]
                    qty = row["จำนวน"]
                    
                    # Calculate Row Values
                    row_yuan = qty * unit_yuan
                    row_cbm = qty * unit_cbm
                    row_weight = qty * unit_weight
                    
                    preview_data.append({
                        "No.": idx + 1,
                        "SKU": sku,
                        "จำนวน": qty,
                        "รวมหยวน (¥)": round(row_yuan, 2),
                        "รวมคิว (CBM)": round(row_cbm, 4),
                        "รวมน้ำหนัก (KG)": round(row_weight, 2)
                    })
        
        # Show Summary Box
        if total_qty_calculated > 0:
            st.markdown(f"""
            <div style="background-color:#1e3c72; padding:10px; border-radius:5px; color:white; margin-top:10px;">
                <b>📊 สรุปการคำนวณเฉลี่ย:</b> จำนวนสินค้าทั้งหมด <b>{total_qty_calculated:,}</b> ชิ้น<br>
                • เฉลี่ย 1 ชิ้น = <b>{unit_yuan:,.2f}</b> หยวน<br>
                • เฉลี่ย 1 ชิ้น = <b>{unit_cbm:,.4f}</b> CBM {'(รอใส่ยอดรวม)' if unit_cbm == 0 else ''}<br>
                • เฉลี่ย 1 ชิ้น = <b>{unit_weight:,.2f}</b> KG {'(รอใส่ยอดรวม)' if unit_weight == 0 else ''}
            </div>
            """, unsafe_allow_html=True)

    # --- 4. Footer & Save ---
    with st.container(border=True):
        st.subheader("4. ข้อมูลเพิ่มเติม (ใช้ร่วมกันทุกรายการ)")
        f1, f2 = st.columns(2)
        link_shop = f1.text_input("Link Shop", key="mi_link")
        wechat = f2.text_input("WeChat / Contact", key="mi_wechat")
        
        p1, p2, p3 = st.columns(3)
        p_s = p1.number_input("Shopee Price", min_value=0.0, key="mi_p_s")
        p_l = p2.number_input("Lazada Price", min_value=0.0, key="mi_p_l")
        p_t = p3.number_input("TikTok Price", min_value=0.0, key="mi_p_t")

    st.divider()
    
    # Save Button Logic
    if st.button("💾 บันทึก PO รายการทั้งหมด", type="primary", use_container_width=True):
        # --- แก้ไข: เอาเงื่อนไข po_number ออกจากการตรวจสอบ ---
        if total_qty_calculated <= 0:
            st.error("❌ กรุณาเพิ่มรายการสินค้าอย่างน้อย 1 รายการ")
        else:
            # Logic Auto PO
            final_po_num = po_number
            if not final_po_num:
                final_po_num = get_next_auto_po()
                st.toast(f"ℹ️ บันทึกโดยใช้เลข: {final_po_num}")

            c_rate_money = rate_money if rate_money is not None else 0.0
            c_ship_rate = ship_rate if ship_rate is not None else 0.0

            rows_to_save = []
            
            for item in preview_data:
                c_sku = item["SKU"]
                c_qty = item["จำนวน"]
                c_yuan_total = item["รวมหยวน (¥)"]
                c_cbm_total = item["รวมคิว (CBM)"]
                c_weight_total = item["รวมน้ำหนัก (KG)"]
                
                c_ship_cost_total = c_cbm_total * c_ship_rate
                c_thb_product_total = c_yuan_total * c_rate_money
                c_thb_final_total = c_thb_product_total + c_ship_cost_total
                
                c_unit_thb = c_thb_final_total / c_qty if c_qty > 0 else 0
                c_unit_yuan = c_yuan_total / c_qty if c_qty > 0 else 0

                final_recv_date_str = ""
                final_wait_days = 0
                final_qty_recv = 0
                
                if recv_date:
                    final_recv_date_str = recv_date.strftime("%Y-%m-%d")
                    final_qty_recv = c_qty
                    if ord_date:
                        final_wait_days = (recv_date - ord_date).days

                row_data = [
                    c_sku, final_po_num, transport, ord_date.strftime("%Y-%m-%d"), # ใช้ final_po_num ตรงนี้
                    final_recv_date_str, final_wait_days, c_qty, final_qty_recv,
                    round(c_unit_thb, 2), round(c_yuan_total, 2), round(c_thb_final_total, 2),
                    c_rate_money, c_ship_rate, round(c_cbm_total, 4), round(c_ship_cost_total, 2), round(c_weight_total, 2), round(c_unit_yuan, 4),
                    p_s, p_l, p_t, note, link_shop, wechat,
                    exp_date.strftime("%Y-%m-%d") if exp_date else ""
                ]
                rows_to_save.append(row_data)

            if save_po_batch_to_sheet(rows_to_save):
                st.success(f"✅ บันทึก {len(rows_to_save)} รายการเรียบร้อยแล้ว!")
                
                # 🟢 CLEAR CACHE AFTER SAVE
                if "po_dataset" in st.session_state: del st.session_state["po_dataset"]
                
                if "mi_items_df" in st.session_state: del st.session_state.mi_items_df
                if "mi_exp_date" in st.session_state: del st.session_state.mi_exp_date # Clear date state
                time.sleep(1.5)
                st.session_state.active_dialog = None
                st.rerun()