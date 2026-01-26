import streamlit as st
import pandas as pd
import urllib.parse
from utils.auth_utils import create_token
from utils.data_utils import clean_text_for_html

@st.dialog("📋 รายละเอียดข้อมูล", width="small")
def show_info_dialog(text_val):
    st.info("💡 สามารถกดปุ่ม Copy มุมขวาบนของกล่องข้อความได้เลย")
    st.code(text_val, language="text") 
    
    if st.button("❌ ปิดหน้าต่าง", type="primary", use_container_width=True):
        if "view_info" in st.query_params: del st.query_params["view_info"]
        if "t" in st.query_params: del st.query_params["t"]
        if "token" not in st.query_params and st.session_state.get('logged_in'):
             st.query_params["token"] = create_token(st.session_state.user_email)
        st.rerun()

@st.dialog("📜 ประวัติการสั่งซื้อสินค้า", width="large")
def show_history_dialog(df_master, df_po, fixed_product_id=None):
    # CSS สำหรับตารางประวัติ
    st.markdown("""
    <style>
        div[data-testid="stDialog"] { width: 98vw !important; min-width: 98vw !important; max-width: 98vw !important; left: 1vw !important; margin: 0 !important; }
        div[data-testid="stDialog"] > div { width: 100% !important; max-width: 100% !important; }
        .po-table-container { overflow: auto; max-height: 75vh; margin-top: 10px; }
        .custom-po-table { width: 100%; border-collapse: separate; font-size: 12px; color: #e0e0e0; min-width: 2000px; }
        .custom-po-table th { background-color: #1e3c72; color: white; padding: 10px; text-align: center; border-bottom: 2px solid #fff; border-right: 1px solid #4a4a4a; position: sticky; top: 0; z-index: 10; white-space: nowrap; vertical-align: middle; }
        .custom-po-table td { padding: 8px 5px; border-bottom: 1px solid #111; border-right: 1px solid #444; vertical-align: middle; text-align: center; }
        .td-merged { border-right: 2px solid #666 !important; background-color: inherit; }
        .status-badge { padding: 4px 8px; border-radius: 12px; font-weight: bold; font-size: 12px; display: inline-block; width: 100px;}
    </style>
    """, unsafe_allow_html=True)
    
    selected_pid = fixed_product_id
    if not selected_pid:
        st.caption("ค้นหาและเลือกสินค้าเพื่อดูประวัติการสั่งซื้อทั้งหมด")
        if df_master.empty: return
        product_options = df_master.apply(lambda x: f"{x['Product_ID']} : {x['Product_Name']}", axis=1).tolist()
        selected_product = st.selectbox("🔍 ค้นหาสินค้า", options=product_options, index=None)
        if selected_product: selected_pid = selected_product.split(" : ")[0]
    
    if selected_pid:
        if not df_po.empty:
            df_history = df_po[df_po['Product_ID'] == selected_pid].copy()
            
            if not df_history.empty:
                df_history['Product_ID'] = df_history['Product_ID'].astype(str)
                df_history = pd.merge(df_history, df_master[['Product_ID','Product_Name','Image']], on='Product_ID', how='left')
                df_history = df_history.sort_values(by=['Order_Date', 'PO_Number'], ascending=[False, False])

                def get_status_hist(row):
                    qty_ord = float(row.get('Qty_Ordered', 0))
                    qty_recv = float(row.get('Qty_Received', 0))
                    if qty_recv >= qty_ord and qty_ord > 0: return "เรียบร้อย", "#155724", "#d4edda"
                    if qty_recv > 0: return "สินค้าไม่ครบ", "#856404", "#fff3cd"
                    return "รอจัดส่ง", "#333", "#f8f9fa"

                status_res = df_history.apply(get_status_hist, axis=1)
                df_history['Status'] = status_res.apply(lambda x: x[0])
                df_history['S_BG'] = status_res.apply(lambda x: x[1])
                df_history['S_Col'] = status_res.apply(lambda x: x[2])

                # Build HTML Table
                table_html = """
                <div class='po-table-container'>
                <table class='custom-po-table'>
                    <thead>
                        <tr>
                            <th>รหัสสินค้า</th>
                            <th style='width:50px;'>รูป</th>
                            <th>สถานะ</th>
                            <th>เลข PO</th>
                            <th>ขนส่ง</th>
                            <th>วันที่สั่งซื้อ</th>
                            <th>วันคาดการณ์</th>
                            <th>วันที่ได้รับ</th>
                            <th>สั่งซื้อ</th>
                            <th>รับแล้ว</th>
                            <th>ต้นทุน (฿)</th>
                            <th>ยอดหยวน (¥)</th>
                            <th>ยอดบาท (฿)</th>
                            <th>เรทเงิน</th>
                            <th>เรทขนส่ง</th>
                            <th>คิว (CBM)</th>
                            <th>ค่าส่ง</th>
                            <th>น้ำหนัก (KG)</th>
                            <th>ราคา/ชิ้น (¥)</th>
                            <th>Shopee</th>
                            <th>Lazada</th>
                            <th>TikTok</th>
                            <th>หมายเหตุ</th>
                        </tr>
                    </thead>
                    <tbody>
                """
                
                def fmt_num(v, d=2): 
                     try: return f"{float(v):,.{d}f}" 
                     except: return "0.00"
                
                def fmt_date(d):
                    try: return pd.to_datetime(d).strftime("%d/%m/%Y")
                    except: return "-"

                grouped = df_history.groupby('PO_Number', sort=False)

                for po, group in grouped:
                    row_count = len(group)
                    first_row = group.iloc[0]
                    
                    po_total_yuan = group['Total_Yuan'].sum()
                    po_total_ship = group['Ship_Cost'].sum()
                    po_total_qty = group['Qty_Ordered'].sum()
                    
                    calc_thb = 0
                    for _, r in group.iterrows():
                        calc_thb += (float(r.get('Total_Yuan',0)) * float(r.get('Yuan_Rate',0)))
                    
                    # Cost per unit (Approx)
                    cost_unit = (calc_thb + po_total_ship) / po_total_qty if po_total_qty > 0 else 0
                    
                    bg_col = "#222"
                    
                    for idx, (i, row) in enumerate(group.iterrows()):
                        table_html += f"<tr style='background-color:{bg_col};'>"
                        
                        # Merged Cols
                        if idx == 0:
                            p_name = clean_text_for_html(str(row.get("Product_Name","")))
                            img = str(row.get("Image",""))
                            img_tag = f"<img src='{img}' style='width:40px;'>" if img.startswith("http") else ""
                            
                            st_txt, st_bg, st_c = row['Status'], row['S_BG'], row['S_Col']
                            
                            table_html += f"<td rowspan='{row_count}' class='td-merged' title='{p_name}'>{row['Product_ID']}</td>"
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{img_tag}</td>"
                            table_html += f"<td rowspan='{row_count}' class='td-merged'><span class='status-badge' style='background:{st_c}; color:{st_bg};'>{st_txt}</span></td>"
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{row['PO_Number']}</td>"
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{row.get('Transport_Type','-')}</td>"
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{fmt_date(row['Order_Date'])}</td>"
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{fmt_date(row.get('Expected_Date'))}</td>"
                        
                        # Row Cols
                        table_html += f"<td>{fmt_date(row.get('Received_Date'))}</td>"
                        table_html += f"<td>{int(row.get('Qty_Ordered',0)):,}</td>"
                        table_html += f"<td>{int(row.get('Qty_Received',0)):,}</td>"
                        
                        if idx == 0:
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{fmt_num(cost_unit)}</td>"
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{fmt_num(po_total_yuan)}</td>"
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{fmt_num(calc_thb)}</td>"
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{fmt_num(row.get('Yuan_Rate',0))}</td>"
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{fmt_num(row.get('Ship_Rate',0))}</td>"
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{fmt_num(row.get('CBM',0), 4)}</td>"
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{fmt_num(po_total_ship)}</td>"
                            table_html += f"<td rowspan='{row_count}' class='td-merged'>{fmt_num(row.get('Transport_Weight',0))}</td>"
                            
                        # Price/Unit Yuan
                        unit_y = float(row.get('Total_Yuan',0)) / float(row.get('Qty_Ordered',1)) if row.get('Qty_Ordered',0) > 0 else 0
                        table_html += f"<td>{fmt_num(unit_y)}</td>"
                        
                        table_html += f"<td>{fmt_num(row.get('Shopee_Price',0))}</td>"
                        table_html += f"<td>{fmt_num(row.get('Lazada_Price',0))}</td>"
                        table_html += f"<td>{fmt_num(row.get('TikTok_Price',0))}</td>"
                        table_html += f"<td>{clean_text_for_html(str(row.get('Note','')))}</td>"
                        
                        table_html += "</tr>"

                table_html += "</tbody></table></div>"
                st.markdown(table_html, unsafe_allow_html=True)
            else:
                 st.info(f"ไม่พบประวัติการสั่งซื้อสำหรับ: {selected_pid}")
        else:
            st.warning("ไม่มีข้อมูล PO")
