import streamlit as st
import pandas as pd
import re
import gspread
from datetime import date, datetime
from database import get_db
import services
from config import MASTER_SHEET_ID, TAB_NAME_PO, TAB_NAME_STOCK
from utils.auth_utils import get_credentials

def highlight_negative(val):
    if isinstance(val, (int, float)) and val < 0:
        return 'color: #ff4b4b; font-weight: bold;'
    return ''

import html

def clean_text_for_html(text):
    if not isinstance(text, str):
        text = str(text) if pd.notna(text) else ""
    
    # 1. ลบอักขระควบคุม (เช่น \n, \r, \t) เปลี่ยนเป็นเว้นวรรค
    text = re.sub(r'[\r\n\t]+', ' ', text)
    
    # 2. Escape HTML special characters (<, >, &, ", ')
    return html.escape(text).strip()

@st.cache_data(ttl=300)
def get_stock_from_sheet():
    try:
        db = next(get_db())
        df = services.get_products_df(db)
        return df
    except Exception as e:
        st.error(f"❌ อ่านข้อมูล Master Stock ไม่ได้: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_po_data():
    try:
        creds = get_credentials()
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(MASTER_SHEET_ID)
        ws = sh.worksheet(TAB_NAME_PO)
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
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
        df = df.rename(columns={k:v for k,v in col_map.items() if k in df.columns})

        if not df.empty:
            df['Sheet_Row_Index'] = range(2, len(df) + 2)
            for col in ['Qty_Ordered', 'Qty_Received', 'Total_Yuan', 'Yuan_Rate']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            if 'Qty_Received' not in df.columns: df['Qty_Received'] = 0
            if 'Expected_Date' not in df.columns: df['Expected_Date'] = None
                 
        return df
    except Exception as e:
        st.error(f"❌ อ่านข้อมูล PO ไม่ได้: {e}")
        return pd.DataFrame()

def get_next_auto_po():
    """ฟังก์ชันคำนวณหาเลข รอเลขสินค้าเข้าXXX ตัวถัดไป"""
    prefix = "รอเลขสินค้าเข้า"
    
    # ดึงข้อมูล PO ปัจจุบันมาเช็ค
    df = get_po_data()
    
    if df.empty:
        return f"{prefix}001"

    mask = df['PO_Number'].astype(str).str.startswith(prefix)
    existing_pos = df.loc[mask, 'PO_Number'].unique()

    if len(existing_pos) == 0:
        return f"{prefix}001"

    max_num = 0
    for po in existing_pos:
        try:
            num_part = str(po).replace(prefix, "")
            num_val = int(num_part)
            if num_val > max_num:
                max_num = num_val
        except:
            continue

    new_num = max_num + 1
    return f"{prefix}{new_num:03d}"


@st.cache_data(ttl=300)
def get_sale_from_folder():
    try:
        db = next(get_db())
        df = services.get_sales_df(db)
        return df
    except Exception as e:
        st.warning(f"⚠️ อ่านข้อมูล Sale ไม่ได้: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=60)
def get_actual_stock_from_folder():
    return pd.DataFrame()

# --- Functions: Save Data ---
def save_po_edit_split(row_index, current_row_data, new_row_data):
    try:
        creds = get_credentials()
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(MASTER_SHEET_ID)
        ws = sh.worksheet(TAB_NAME_PO)
        
        formatted_curr = []
        for item in current_row_data:
            if isinstance(item, (date, datetime)): formatted_curr.append(item.strftime("%Y-%m-%d"))
            elif item is None: formatted_curr.append("")
            else: formatted_curr.append(item)
        
        range_name = f"A{row_index}:X{row_index}" 
        ws.update(range_name, [formatted_curr])
        
        formatted_new = []
        for item in new_row_data:
            if isinstance(item, (date, datetime)): formatted_new.append(item.strftime("%Y-%m-%d"))
            elif item is None: formatted_new.append("")
            else: formatted_new.append(item)
            
        ws.append_row(formatted_new)
        
        st.cache_data.clear() 
        return True
    except Exception as e:
        st.error(f"❌ บันทึก Split ไม่สำเร็จ: {e}")
        return False

def save_po_edit_update(row_index, current_row_data):
    try:
        creds = get_credentials()
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(MASTER_SHEET_ID)
        ws = sh.worksheet(TAB_NAME_PO)
        
        formatted_curr = []
        for item in current_row_data:
            if isinstance(item, (date, datetime)): formatted_curr.append(item.strftime("%Y-%m-%d"))
            elif item is None: formatted_curr.append("")
            else: formatted_curr.append(item)
        
        range_name = f"A{row_index}:X{row_index}" 
        ws.update(range_name, [formatted_curr])
        
        st.cache_data.clear() 
        return True
    except Exception as e:
        st.error(f"❌ บันทึก Update ไม่สำเร็จ: {e}")
        return False

def save_po_batch_to_sheet(rows_data):
    try:
        creds = get_credentials()
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(MASTER_SHEET_ID)
        ws = sh.worksheet(TAB_NAME_PO)
        ws.append_rows(rows_data)
        st.cache_data.clear() 
        return True
    except Exception as e:
        st.error(f"❌ บันทึก Batch ไม่สำเร็จ: {e}")
        return False

def delete_po_row_from_sheet(row_index):
    try:
        creds = get_credentials()
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(MASTER_SHEET_ID)
        ws = sh.worksheet(TAB_NAME_PO)
        
        ws.delete_rows(int(row_index))
        
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"❌ ลบข้อมูลไม่สำเร็จ: {e}")
        return False

def update_master_limits(df_edited):
    try:
        creds = get_credentials()
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(MASTER_SHEET_ID)
        ws = sh.worksheet(TAB_NAME_STOCK)
        
        headers = ws.row_values(1)
        all_rows = ws.get_all_values()

        pid_idx = -1
        for i, h in enumerate(headers):
            if h in ['รหัสสินค้า', 'รหัส', 'ID', 'Product_ID']:
                pid_idx = i
                break
        
        if pid_idx == -1: 
            st.error("❌ ไม่พบคอลัมน์ Product_ID ใน Google Sheet")
            return

        targets = [
            ("Min_Limit", "Min_Limit", int),
            ("Note", "Note", str)
        ]

        for df_col, sheet_header, dtype in targets:
            if sheet_header not in headers:
                ws.update_cell(1, len(headers) + 1, sheet_header)
                headers = ws.row_values(1) 
                col_index = len(headers)
            else:
                col_index = headers.index(sheet_header) + 1

            data_map = {}
            for index, row in df_edited.iterrows():
                pid = str(row['Product_ID']).strip()
                raw_val = row.get(df_col, "")
                
                if dtype == int:
                    try: clean_val = int(float(str(raw_val).replace(',', '').strip()))
                    except: clean_val = 0
                else:
                    clean_val = str(raw_val) if pd.notna(raw_val) else ""
                
                data_map[pid] = clean_val

            values_to_update = []
            for row in all_rows[1:]:
                row_pid = str(row[pid_idx]).strip() if len(row) > pid_idx else ""
                final_val = "" if dtype == str else 0
                
                if row_pid in data_map:
                    final_val = data_map[row_pid]
                else:
                    if len(row) >= col_index:
                        curr_val = row[col_index-1]
                        if dtype == int:
                            try: final_val = int(float(str(curr_val).replace(",", "")))
                            except: final_val = 0
                        else:
                            final_val = str(curr_val)
                
                values_to_update.append([final_val])

            if values_to_update:
                range_name = f"{gspread.utils.rowcol_to_a1(2, col_index)}:{gspread.utils.rowcol_to_a1(len(values_to_update)+1, col_index)}"
                ws.update(range_name, values_to_update)

        st.toast("✅ บันทึกข้อมูล (จุดเตือน & หมายเหตุ) สำเร็จ!", icon="💾")
        st.cache_data.clear()
            
    except Exception as e:
        st.error(f"❌ เกิดข้อผิดพลาด: {str(e)}")
