import pandas as pd
import datetime

def clean_date(df, col_name):
    """
    แปลงข้อมูลเป็นวันที่ (Date Only) ตัดเวลาทิ้ง
    รองรับทั้ง:
    - TikTok/Thai: 27/12/2025 (DD/MM/YYYY)
    - Shopee/ISO:  2026-01-09 00:02 (YYYY-MM-DD HH:MM)
    """
    if col_name in df.columns:
        # 1. แปลงเป็น String และลบช่องว่าง
        df[col_name] = df[col_name].astype(str).str.strip()
        # 2. จัดการค่าว่าง
        df[col_name] = df[col_name].replace({'nan': None, 'None': None, '': None, 'NaT': None})
        # 3. แปลงเป็น DateTime
        try:
            df[col_name] = pd.to_datetime(df[col_name], errors='coerce', dayfirst=True, format='mixed').dt.date
        except (ValueError, TypeError):
            df[col_name] = pd.to_datetime(df[col_name], errors='coerce', dayfirst=True).dt.date
    return df

def clean_text(df, col_name):
    if col_name in df.columns:
        df[col_name] = df[col_name].astype(str).str.strip().str.upper()
    return df

def clean_scientific_notation(val):
    val_str = str(val).strip()
    if 'E' in val_str or 'e' in val_str:
        try: return str(int(float(val)))
        except: return val_str
    return val_str.replace('.0', '') 

def format_thai_date(d):
    if not d: return "-"
    try:
        if isinstance(d, str):
            d = pd.to_datetime(d).date()
        return d.strftime('%d/%m/%Y')
    except: return "-"

def get_standard_status(row):
    try: amt = float(row.get('settlement_amount', 0))
    except: amt = 0
    
    if amt > 0: return "ออเดอร์สำเร็จ"
    
    raw_status = str(row.get('status', '')).lower()
    if any(x in raw_status for x in ['ยกเลิก', 'cancel', 'failed']): return "ยกเลิก"
    if any(x in raw_status for x in ['returned', 'return', 'ตีกลับ', 'refund']): return "ตีกลับ"
    
    shipped = row.get('shipped_date')
    if shipped and str(shipped) != 'NaT' and str(shipped) != 'None':
        return "รอดำเนินการ" 
        
    return "รอดำเนินการ"
