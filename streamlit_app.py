import streamlit as st
import pandas as pd
import numpy as np
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from supabase import create_client, Client
import io
import datetime
import calendar
from datetime import date

# --- 1. CONFIGURATION & CSS ---
st.set_page_config(page_title="Dashboard สรุปยอดขาย", layout="wide", page_icon="📊")

# Custom CSS ให้ตารางสวยงาม
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Kanit:wght@300;400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Kanit', sans-serif;
    }
    
    .stMetric {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* ปรับแต่ง Header ของตาราง */
    div[data-testid="stDataFrameResizable"] {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
    }
    </style>
""", unsafe_allow_html=True)

# Supabase Setup
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except:
    st.error("ไม่พบการตั้งค่า Supabase ใน st.secrets")
    st.stop()

# --- 2. HELPER FUNCTIONS ---

def get_standard_status(row):
    """ฟังก์ชันแปลงสถานะมาตรฐาน"""
    try:
        amt = float(row.get('settlement_amount', 0))
    except:
        amt = 0
    if amt > 0: return "ออเดอร์สำเร็จ"
    
    raw_status = str(row.get('status', '')).lower()
    if any(x in raw_status for x in ['ยกเลิก', 'cancel']): return "ยกเลิก"
    if any(x in raw_status for x in ['package returned', 'return', 'ตีกลับ']): return "ตีกลับ"
    return "รอดำเนินการ"

def fetch_data(start_date, end_date):
    """ดึงข้อมูลจาก Supabase ตามช่วงวันที่"""
    try:
        # ดึงข้อมูลโดยแปลง created_date เป็น Date เพื่อเทียบ
        response = supabase.table("orders").select("*").execute()
        df = pd.DataFrame(response.data)
        
        if not df.empty:
            # Clean Date
            df['created_date'] = pd.to_datetime(df['created_date'], errors='coerce').dt.date
            
            # Filter Date Range
            mask = (df['created_date'] >= start_date) & (df['created_date'] <= end_date)
            df = df.loc[mask]
            
            # Clean Numbers
            cols_num = ['sales_amount', 'settlement_amount', 'fees', 'affiliate', 'total_cost']
            for c in cols_num:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
            
            # Standard Status
            df['std_status'] = df.apply(get_standard_status, axis=1)
            
        return df
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return pd.DataFrame()

# --- 3. UI ส่วนตัวกรอง (ตามที่คุณขอมา) ---

st.title("📊 หน้าสรุปยอดขายทุกแพลตฟอร์ม")
st.markdown("---")

# Logic วันที่ (ของคุณ)
thai_months = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
                "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
today = datetime.datetime.now().date()
all_years = sorted([2024, 2025, 2026], reverse=True)

def update_dates():
    y = st.session_state.sel_year
    m_str = st.session_state.sel_month
    try:
        m_idx = thai_months.index(m_str) + 1
        _, days_in_m = calendar.monthrange(y, m_idx)
        st.session_state.d_start = date(y, m_idx, 1)
        st.session_state.d_end = date(y, m_idx, days_in_m)
    except:
        pass

if "d_start" not in st.session_state:
    st.session_state.d_start = today.replace(day=1)
    st.session_state.d_end = today

with st.container():
    st.subheader("🔍 ตัวกรองช่วงเวลา")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.selectbox("ปี", options=all_years, index=0, key="sel_year", on_change=update_dates)
    with c2:
        st.selectbox("เดือน", options=thai_months, index=today.month-1, key="sel_month", on_change=update_dates)
    with c3:
        d_start = st.date_input("วันที่เริ่ม", key="d_start")
    with c4:
        d_end = st.date_input("ถึงวันที่", key="d_end")

st.markdown("")
st.subheader("🛍️ เลือกแพลตฟอร์ม")

# Checkbox แพลตฟอร์ม
cp1, cp2, cp3, cp4, cp5 = st.columns([1, 1, 1, 1, 6])
with cp1:
    all_plat = st.checkbox("✅ ทั้งหมด", value=True)
with cp2:
    tiktok_check = st.checkbox("✅ Tiktok", value=all_plat, disabled=all_plat)
with cp3:
    shopee_check = st.checkbox("✅ Shopee", value=all_plat, disabled=all_plat)
with cp4:
    lazada_check = st.checkbox("✅ Lazada", value=all_plat, disabled=all_plat)

# Logic เลือก Platform
selected_platforms = []
if all_plat:
    selected_platforms = ['TIKTOK', 'SHOPEE', 'LAZADA']
else:
    if tiktok_check: selected_platforms.append('TIKTOK')
    if shopee_check: selected_platforms.append('SHOPEE')
    if lazada_check: selected_platforms.append('LAZADA')

# --- 4. การคำนวณข้อมูล (CORE LOGIC) ---

# โหลดข้อมูลดิบ
raw_df = fetch_data(d_start, d_end)

if not raw_df.empty:
    # กรอง Platform
    if 'platform' in raw_df.columns:
        # ทำให้เป็นตัวใหญ่เพื่อเทียบ
        raw_df['platform'] = raw_df['platform'].str.upper().str.strip()
        raw_df = raw_df[raw_df['platform'].isin(selected_platforms)]

    # สร้าง DataFrame วันที่ครบถ้วน (เผื่อวันไหนขายไม่ได้ ก็ต้องโชว์บรรทัดนั้น)
    date_range = pd.date_range(start=d_start, end=d_end)
    summary_df = pd.DataFrame({'created_date': date_range.date})

    # Group by Date: Metrics พื้นฐาน
    daily_stats = raw_df.groupby('created_date').agg(
        total_orders=('order_id', 'count'),
        success_count=('std_status', lambda x: (x == 'ออเดอร์สำเร็จ').sum()),
        pending_count=('std_status', lambda x: (x == 'รอดำเนินการ').sum()),
        return_count=('std_status', lambda x: (x == 'ตีกลับ').sum()),
        cancel_count=('std_status', lambda x: (x == 'ยกเลิก').sum()),
        sales_sum=('sales_amount', 'sum'),
        cost_sum=('total_cost', 'sum'),
        fees_sum=('fees', 'sum'),
        affiliate_sum=('affiliate_sum', 'sum') if 'affiliate_sum' in raw_df.columns else ('affiliate', 'sum')
    ).reset_index()

    # Merge กับตารางวันที่หลัก (Left Join)
    final_df = pd.merge(summary_df, daily_stats, on='created_date', how='left').fillna(0)

    # --- 5. ระบบกรอกค่า ADS (Using Session State to remember inputs) ---
    
    # Key สำหรับเก็บค่า Ads (ถ้ายังไม่มีให้สร้าง)
    if "ads_data" not in st.session_state:
        st.session_state.ads_data = {} # {date_str: {'ads_cost': 0, 'roas_ads': 0}}

    # เตรียมข้อมูลสำหรับแสดงใน Data Editor
    editor_data = []
    for index, row in final_df.iterrows():
        d_str = str(row['created_date'])
        
        # ดึงค่า Ads เดิมที่เคยกรอกไว้ (ถ้ามี)
        saved_ads = st.session_state.ads_data.get(d_str, {'ads_cost': 0.0, 'roas_ads': 0.0})
        
        row_dict = row.to_dict()
        row_dict['manual_ads_cost'] = saved_ads['ads_cost']
        row_dict['manual_roas_ads'] = saved_ads['roas_ads']
        editor_data.append(row_dict)
    
    editor_df = pd.DataFrame(editor_data)

    # --- 6. แสดงตารางและการคำนวณ (Display & Calculate) ---
    
    st.markdown("### 📝 ตารางสรุปยอดขายและกำไร (แก้ไขค่า Ads ได้ในช่องสีเหลือง)")
    
    # Config คอลัมน์สำหรับ Data Editor
    column_config = {
        "created_date": st.column_config.DateColumn("วันที่", format="DD MMM YYYY", width="medium", disabled=True),
        
        # Status
        "success_count": st.column_config.NumberColumn("✅ สำเร็จ", format="%d", width="small", disabled=True),
        "pending_count": st.column_config.NumberColumn("⏳ รอ", format="%d", width="small", disabled=True),
        "return_count": st.column_config.NumberColumn("↩️ ตีกลับ", format="%d", width="small", disabled=True),
        "cancel_count": st.column_config.NumberColumn("❌ ยกเลิก", format="%d", width="small", disabled=True),
        
        # Financials
        "sales_sum": st.column_config.NumberColumn("💰 ยอดขายรวม", format="฿%.2f", disabled=True),
        "cost_sum": st.column_config.NumberColumn("📦 ทุนรวม", format="฿%.2f", disabled=True),
        "fees_sum": st.column_config.NumberColumn("🧾 ค่าธรรมเนียม", format="฿%.2f", disabled=True),
        "affiliate_sum": st.column_config.NumberColumn("🤝 ค่า Aff", format="฿%.2f", disabled=True),
        
        # Manual Inputs (Editable)
        "manual_ads_cost": st.column_config.NumberColumn("📢 ค่า ADS (กรอกเอง)", format="฿%.2f", min_value=0, required=True),
        "manual_roas_ads": st.column_config.NumberColumn("📈 ROAS ADS (กรอกเอง)", format="฿%.2f", min_value=0, required=True),
    }

    # แสดง Data Editor (เฉพาะคอลัมน์ Input และข้อมูลดิบก่อนคำนวณปลายทาง)
    # เราจะแสดงผลลัพธ์การคำนวณในตารางแยก หรือ คำนวณแล้วโชว์เลย (ต้องระวัง re-run loop)
    # วิธีที่ดีที่สุด: ให้ user กรอก Ads ในตารางนี้ แล้วเราเอาผลไปคำนวณโชว์อีกตาราง หรือ Merge กัน
    
    # เพื่อความสวยงาม "Fix HTML" เราจะใช้เทคนิค:
    # 1. ให้ User กรอก Ads ในตารางเล็ก หรือตารางรวม
    # 2. นำค่าที่กรอกมาคำนวณ Metrics ทั้งหมด
    # 3. แสดงผลตารางใหญ่แบบ Read-only (สวยๆ)
    
    # แต่ User อยากเห็นภาพรวมในที่เดียว ดังนั้นใช้ Data Editor ตัวเดียวแล้วคำนวณสด
    
    # 1. รับค่าแก้ไข
    edited_data = st.data_editor(
        editor_df[[
            'created_date', 'success_count', 'pending_count', 'return_count', 'cancel_count',
            'sales_sum', 'cost_sum', 'fees_sum', 'affiliate_sum', 
            'manual_ads_cost', 'manual_roas_ads'
        ]],
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        key="main_editor"
    )
    
    # 2. บันทึกค่าที่แก้ลง Session State
    for index, row in edited_data.iterrows():
        d_str = str(row['created_date'])
        st.session_state.ads_data[d_str] = {
            'ads_cost': row['manual_ads_cost'],
            'roas_ads': row['manual_roas_ads']
        }

    # 3. คำนวณสูตรทั้งหมด (Final Calculation)
    calc_df = edited_data.copy()
    
    # ป้องกันการหารด้วย 0
    def safe_div(a, b):
        return (a / b * 100) if b > 0 else 0

    # --- กลุ่ม 1: ต้นทุนและกำไรขั้นต้น ---
    calc_df['%ทุนรวม'] = calc_df.apply(lambda x: safe_div(x['cost_sum'], x['sales_sum']), axis=1)
    calc_df['%ค่าธรรมเนียม'] = calc_df.apply(lambda x: safe_div(x['fees_sum'], x['sales_sum']), axis=1)
    calc_df['%ค่าแอฟฟิลิเอต'] = calc_df.apply(lambda x: safe_div(x['affiliate_sum'], x['sales_sum']), axis=1)
    
    calc_df['กำไร'] = calc_df['sales_sum'] - calc_df['cost_sum'] - calc_df['fees_sum'] - calc_df['affiliate_sum']
    calc_df['%กำไร'] = calc_df.apply(lambda x: safe_div(x['กำไร'], x['sales_sum']), axis=1)

    # --- กลุ่ม 2: โฆษณา (ADS) ---
    calc_df['ADS VAT 7%'] = calc_df['manual_ads_cost'] * 0.07
    calc_df['ค่าแอดรวม'] = calc_df['manual_ads_cost'] + calc_df['manual_roas_ads'] + calc_df['ADS VAT 7%']
    
    # ROAS (Platform) & ROAS รวม
    # หมายเหตุ: User ขอ "ROAS" เฉยๆ = ยอดขาย / ค่าแอดรวม
    calc_df['ROAS'] = calc_df.apply(lambda x: (x['sales_sum'] / x['ค่าแอดรวม']) if x['ค่าแอดรวม'] > 0 else 0, axis=1)
    calc_df['%ค่าแอด'] = calc_df.apply(lambda x: safe_div(x['ค่าแอดรวม'], x['sales_sum']), axis=1)

    # --- กลุ่ม 3: ดำเนินการและสุทธิ ---
    # ค่าดำเนินการ = (สำเร็จ+รอ+ตีกลับ+ยกเลิก) * 10
    total_ops_count = calc_df['success_count'] + calc_df['pending_count'] + calc_df['return_count'] + calc_df['cancel_count']
    calc_df['ค่าดำเนินการ'] = total_ops_count * 10
    calc_df['%ค่าดำเนินการ'] = calc_df.apply(lambda x: safe_div(x['ค่าดำเนินการ'], x['sales_sum']), axis=1)

    calc_df['กำไรสุทธิ'] = calc_df['กำไร'] - calc_df['ค่าแอดรวม'] - calc_df['ค่าดำเนินการ']
    calc_df['%กำไรสุทธิ'] = calc_df.apply(lambda x: safe_div(x['กำไรสุทธิ'], x['sales_sum']), axis=1)

    # --- 4. แสดงตารางผลลัพธ์สมบูรณ์ (Beautiful HTML Table View) ---
    st.markdown("### 🏁 ผลลัพธ์การคำนวณละเอียด")
    
    # เลือกคอลัมน์ตามลำดับที่ขอ
    final_view = calc_df[[
        'created_date', 
        'success_count', 'pending_count', 'return_count', 'cancel_count',
        'sales_sum', 'ROAS', 
        'cost_sum', '%ทุนรวม',
        'fees_sum', '%ค่าธรรมเนียม',
        'affiliate_sum', '%ค่าแอฟฟิลิเอต',
        'กำไร', '%กำไร',
        'manual_ads_cost', 'manual_roas_ads', 'ADS VAT 7%', 'ค่าแอดรวม', '%ค่าแอด',
        'ค่าดำเนินการ', '%ค่าดำเนินการ',
        'กำไรสุทธิ', '%กำไรสุทธิ'
    ]].copy()

    # เปลี่ยนชื่อคอลัมน์ให้ตรงเป๊ะ
    rename_cols = {
        'created_date': 'วันที่',
        'success_count': 'สำเร็จ', 'pending_count': 'รอ', 'return_count': 'ตีกลับ', 'cancel_count': 'ยกเลิก',
        'sales_sum': 'ยอดขายรวม',
        'cost_sum': 'ทุนรวม',
        'fees_sum': 'ค่าธรรมเนียม',
        'affiliate_sum': 'ค่าแอฟฟิลิเอต',
        'manual_ads_cost': 'ค่าADS', 'manual_roas_ads': 'ROAS ADS'
    }
    final_view = final_view.rename(columns=rename_cols)

    # แสดงผลด้วย Dataframe แบบกำหนด Format (สวยงาม)
    st.dataframe(
        final_view,
        column_config={
            "วันที่": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "ยอดขายรวม": st.column_config.NumberColumn(format="%.2f"),
            "ROAS": st.column_config.NumberColumn(format="%.2f"),
            "ทุนรวม": st.column_config.NumberColumn(format="%.2f"),
            "%ทุนรวม": st.column_config.NumberColumn(format="%.2f%%"),
            "ค่าธรรมเนียม": st.column_config.NumberColumn(format="%.2f"),
            "%ค่าธรรมเนียม": st.column_config.NumberColumn(format="%.2f%%"),
            "ค่าแอฟฟิลิเอต": st.column_config.NumberColumn(format="%.2f"),
            "%ค่าแอฟฟิลิเอต": st.column_config.NumberColumn(format="%.2f%%"),
            "กำไร": st.column_config.NumberColumn(format="%.2f"),
            "%กำไร": st.column_config.NumberColumn(format="%.2f%%"),
            "ค่าADS": st.column_config.NumberColumn(format="%.2f"),
            "ROAS ADS": st.column_config.NumberColumn(format="%.2f"),
            "ADS VAT 7%": st.column_config.NumberColumn(format="%.2f"),
            "ค่าแอดรวม": st.column_config.NumberColumn(format="%.2f"),
            "%ค่าแอด": st.column_config.NumberColumn(format="%.2f%%"),
            "ค่าดำเนินการ": st.column_config.NumberColumn(format="%.2f"),
            "%ค่าดำเนินการ": st.column_config.NumberColumn(format="%.2f%%"),
            "กำไรสุทธิ": st.column_config.ProgressColumn(
                format="฿%.2f",
                min_value=float(final_view['กำไรสุทธิ'].min()) if not final_view.empty else 0,
                max_value=float(final_view['กำไรสุทธิ'].max()) if not final_view.empty else 100,
            ),
            "%กำไรสุทธิ": st.column_config.NumberColumn(format="%.2f%%")
        },
        use_container_width=True,
        hide_index=True,
        height=600
    )

else:
    st.info("ไม่พบข้อมูลในช่วงเวลานี้")