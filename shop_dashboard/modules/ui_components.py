import streamlit as st

# --- COLOR SETTINGS ---
COLOR_SALES = "#33FFFF"
COLOR_OPS = "#3498db"  # ค่าดำเนินการ
COLOR_COM = "#FFD700"  # ค่าคอมมิชชั่น (ทอง)
COLOR_COST_PROD = "#A020F0"  # ทุนสินค้า
COLOR_ADS = "#FF6633"
COLOR_PROFIT = "#7CFC00"
COLOR_NEGATIVE = "#FF0000"

def load_css():
    st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;600;700&family=Prompt:wght@300;400;500;600&display=swap');

    html, body, [class*="css"] { font-family: 'Sarabun', sans-serif; }
    
    .block-container { padding-top: 2rem !important; }

    /* --- 1. สีตัวอักษร --- */
    .val-sales { color: #33FFFF !important; font-size: 24px; font-weight: 700; }
    .sub-sales { color: #33FFFF !important; font-size: 13px; font-weight: 600; margin-top: 5px; }

    .val-ops { color: #3498db !important; font-size: 24px; font-weight: 700; }
    .sub-ops { color: #3498db !important; font-size: 13px; font-weight: 600; margin-top: 5px; }

    .val-com { color: #FFD700 !important; font-size: 24px; font-weight: 700; }
    .sub-com { color: #FFD700 !important; font-size: 13px; font-weight: 600; margin-top: 5px; }

    .val-costprod { color: #A020F0 !important; font-size: 24px; font-weight: 700; }
    .sub-costprod { color: #A020F0 !important; font-size: 13px; font-weight: 600; margin-top: 5px; }

    .val-ads { color: #FF6633 !important; font-size: 24px; font-weight: 700; }
    .sub-ads { color: #FF6633 !important; font-size: 13px; font-weight: 600; margin-top: 5px; }

    .val-profit { color: #7CFC00 !important; font-size: 24px; font-weight: 700; }
    .sub-profit { color: #7CFC00 !important; font-size: 13px; font-weight: 600; margin-top: 5px; }

    .val-neg { color: #FF0000 !important; font-size: 24px; font-weight: 700; }
    .sub-neg { color: #FF0000 !important; font-size: 13px; font-weight: 600; margin-top: 5px; }

    /* --- 2. การจัดวาง (LAYOUT FIX) --- */
    .metric-container { 
        display: grid !important; 
        grid-template-columns: repeat(6, 1fr) !important; 
        gap: 15px !important; 
        margin-bottom: 20px; 
        width: 100%;
    }
    
    .custom-card {
        background: #1c1c1c;
        border-radius: 10px; padding: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.5); 
        min-width: 0; 
        border-left: 5px solid #ddd;
        border: 1px solid #333;
    }

    .card-label { color: #aaa !important; font-size: 13px; font-weight: 600; margin-bottom: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

    .neg { color: #FF0000 !important; }
    .pos { color: #ffffff !important; }

    .border-blue { border-left-color: #33FFFF; }
    .border-ops { border-left-color: #3498db; }
    .border-com { border-left-color: #FFD700; }
    .border-costprod { border-left-color: #A020F0; }
    .border-orange { border-left-color: #FF6633; }
    .border-green { border-left-color: #7CFC00; }

    /* Inputs */
    .stTextInput input { color: #ffffff !important; caret-color: white; background-color: #262730 !important; border: 1px solid #555 !important; }
    div[data-baseweb="select"] div { color: #ffffff !important; background-color: #262730 !important; }
    div[data-baseweb="select"] span { color: #ffffff !important; }
    div[role="listbox"] li { color: #ffffff !important; background-color: #262730; }

    /* Header & Utils */
    .header-bar {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        padding: 15px 20px; border-radius: 10px;
        margin-bottom: 20px; display: flex; align-items: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .header-title { font-size: 22px; font-weight: 700; margin: 0; color: white !important; }

    /* Table Styling */
    .table-wrapper { overflow: auto; width: 100%; max-height: 800px; margin-top: 10px; background: #1c1c1c; border-radius: 8px; border: 1px solid #444; }
    .custom-table { width: 100%; min-width: 1000px; border-collapse: separate; border-spacing: 0; font-family: 'Sarabun', sans-serif; font-size: 11px; color: #ddd; }
    .custom-table th, .custom-table td { padding: 4px 6px; line-height: 1.2; text-align: center; border-bottom: 1px solid #333; border-right: 1px solid #333; white-space: nowrap; }
    .daily-table thead th, .month-table thead th { position: sticky; top: 0; z-index: 100; background-color: #1e3c72; color: white !important; font-weight: 700; border-bottom: 2px solid #555; }
    
    .custom-table tbody tr:nth-child(even) td { background-color: #262626; }
    .custom-table tbody tr:nth-child(odd) td { background-color: #1c1c1c; }
    .custom-table tbody tr:hover td { background-color: #333; }

    /* REPORT DAILY SPECIFIC */
    .custom-table.daily-table tbody tr td { 
        color: #333333 !important; 
        font-weight: 500;
    }
    .custom-table.daily-table tbody tr:nth-child(even) td { background-color: #d9d9d9 !important; }
    .custom-table.daily-table tbody tr:nth-child(odd) td { background-color: #ffffff !important; }
    .custom-table.daily-table tbody tr:hover td { background-color: #e6e6e6 !important; }
    
    .custom-table.daily-table tbody tr td.negative-value {
        color: #FF0000 !important;
        font-weight: bold !important;
    }
    
    .custom-table.daily-table tbody tr td[style*="color: #e67e22"],
    .custom-table.daily-table tbody tr td[style*="color:#e67e22"] {
        color: #e67e22 !important;
    }
    
    .custom-table.daily-table tbody tr td[style*="color: #1e3c72"],
    .custom-table.daily-table tbody tr td[style*="color:#1e3c72"] {
        color: #1e3c72 !important;
        font-weight: bold !important;
    }
    
    .custom-table.daily-table tbody tr td[style*="color: #FF0000"],
    .custom-table.daily-table tbody tr td[style*="color:#FF0000"] {
        color: #FF0000 !important;
        font-weight: bold !important;
    }
    
    .custom-table.daily-table tbody tr.footer-row td { 
        position: sticky; bottom: 0; z-index: 100; 
        background-color: #1e3c72 !important; 
        font-weight: bold; 
        color: white !important; 
        border-top: 2px solid #f1c40f; 
    }

    /* --- [FIX COMPACT SIZE] REPORT MONTH STICKY COLS --- */
    .fix-m-1 { position: sticky; left: 0px !important;   z-index: 20; width: 110px !important; min-width: 110px !important; border-right: 1px solid #444; }
    .fix-m-2 { position: sticky; left: 110px !important; z-index: 20; width: 80px !important;  min-width: 80px !important;  border-right: 1px solid #444; }
    .fix-m-3 { position: sticky; left: 190px !important; z-index: 20; width: 50px !important;  min-width: 50px !important;  border-right: 1px solid #444; }
    .fix-m-4 { position: sticky; left: 240px !important; z-index: 20; width: 115px !important;  min-width: 115px !important;  border-right: 1px solid #444; }
    .fix-m-5 { position: sticky; left: 310px !important; z-index: 20; width: 0px !important;  min-width: 0px !important;  display: none !important; }
    .fix-m-6 { position: sticky; left: 355px !important; z-index: 20; width: 115px !important;  min-width: 115px !important;  border-right: 1px solid #444; }
    .fix-m-7 { position: sticky; left: 425px !important; z-index: 20; width: 0px !important;  min-width: 0px !important;  display: none !important; }

    /* --- 1. ส่วนหัวตาราง (THEAD) แก้ z-index ให้สูงขึ้น --- */
.month-table thead th.fix-m-1, .month-table thead th.fix-m-2, 
.month-table thead th.fix-m-3, .month-table thead th.fix-m-4,
.month-table thead th.fix-m-5, .month-table thead th.fix-m-6,
.month-table thead th.fix-m-7 {
    z-index: 200 !important; /* <--- แก้จาก 30 เป็น 200 เพื่อให้อยู่บนสุดครับ */
    box-shadow: 2px 0 5px rgba(0,0,0,0.3); /* เพิ่มเงาเล็กน้อยให้ดูแยกชั้นชัดเจน */
}

/* --- 2. ส่วนเนื้อหา (TBODY) เพิ่ม z-index เล็กน้อยกันพลาด --- */
.custom-table tbody tr td.fix-m-1, .custom-table tbody tr td.fix-m-2,
.custom-table tbody tr td.fix-m-3, .custom-table tbody tr td.fix-m-4,
.custom-table tbody tr td.fix-m-5, .custom-table tbody tr td.fix-m-6,
.custom-table tbody tr td.fix-m-7 {
    background-color: #1c1c1c; 
    z-index: 50 !important; /* <--- แนะนำให้เพิ่มบรรทัดนี้ครับ */
    position: sticky;       /* <--- ย้ำคำสั่งนี้ */
}

/* --- 3. ส่วนสีพื้นหลังแถวคู่ (เหมือนเดิม) --- */
.custom-table tbody tr:nth-child(even) td.fix-m-1, .custom-table tbody tr:nth-child(even) td.fix-m-2,
.custom-table tbody tr:nth-child(even) td.fix-m-3, .custom-table tbody tr:nth-child(even) td.fix-m-4,
.custom-table tbody tr:nth-child(even) td.fix-m-5, .custom-table tbody tr:nth-child(even) td.fix-m-6,
.custom-table tbody tr:nth-child(even) td.fix-m-7 {
    background-color: #262626; 
}

    .month-table tfoot {
        position: sticky;
        bottom: 0;
        z-index: 25;
        border-top: 2px solid #fff;
    }
    .month-table tfoot td.fix-m-1, 
    .month-table tfoot td.fix-m-2, 
    .month-table tfoot td.fix-m-3, 
    .month-table tfoot td.fix-m-4, 
    .month-table tfoot td.fix-m-5, 
    .month-table tfoot td.fix-m-6, 
    .month-table tfoot td.fix-m-7 {
        z-index: 40 !important;
    }

    .th-sku { background-color: #1e3c72 !important; color: white !important; min-width: 80px; }
    .sku-header { font-size: 10px; color: #d6eaf8 !important; font-weight: normal; display: block; overflow: hidden; text-overflow: ellipsis; max-width: 100px; margin: 0 auto; text-align: center; }
    .col-small { width: 70px; min-width: 70px; max-width: 70px; font-size: 11px; color: #333333 !important; }
       .col-medium { width: 90px !important; min-width: 90px !important; max-width: 90px !important; font-size: 11px; color: #333333 !important; }
       .col-wide { width: 100px !important; min-width: 100px !important; max-width: 100px !important; font-size: 11px; color: #333333 !important; }

    .pnl-container { font-family: 'Prompt', sans-serif; color: #ffffff; }
    .header-gradient-pnl { background-image: linear-gradient(135deg, #0f172a 0%, #334155 100%); padding: 20px 25px; border-radius: 12px; color: white; margin-bottom: 25px; }
    .header-title-pnl { font-size: 24px; font-weight: 600; margin: 0; color: white !important; }
    .header-sub-pnl { font-size: 14px; color: #cbd5e1; font-weight: 300; margin-top: 5px; }
    
    .chart-box { background-color: #1c1c1c; border: 1px solid #333; border-radius: 12px; padding: 20px; margin-bottom: 20px; display: flex; flex-direction: column; }
    .chart-header { font-size: 16px; font-weight: 600; color: #ddd; margin-bottom: 15px; display: flex; align-items: center; gap: 8px; }
    .pill { width: 4px; height: 16px; border-radius: 4px; display: inline-block; }
    
    .pnl-table { width: 100%; border-collapse: collapse; font-size: 14px; font-family: 'Prompt', sans-serif; background: #1c1c1c; }
    .pnl-table th { text-align: left; padding: 12px 16px; color: #aaa; font-weight: 500; background-color: #2c2c2c; border-bottom: 1px solid #444; }
    .pnl-table td { padding: 12px 16px; border-bottom: 1px solid #333; color: #ddd; }
    .pnl-row-head td { font-weight: 600; color: #fff; background-color: #2c2c2c; }
    .num-cell { text-align: right; font-family: 'Courier New', monospace; }
    .sub-item td:first-child { padding-left: 35px; color: #aaa; font-size: 13px; }
    
    div.stButton > button { width: 100%; border-radius: 6px; height: 42px; font-weight: bold; padding: 0px 5px; background-color: #333; color: white; border: 1px solid #555; }
    div.stButton > button:hover { border-color: #00d2ff; color: #00d2ff; }
</style>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
""", unsafe_allow_html=True)

def render_metric_row(total_sales, total_ops, total_com, total_cost_prod, total_ads, total_profit):
    """Renders the top summary metrics row."""
    pct_sales = 100
    pct_ops = (total_ops / total_sales * 100) if total_sales > 0 else 0
    pct_com = (total_com / total_sales * 100) if total_sales > 0 else 0
    pct_cost_prod = (total_cost_prod / total_sales * 100) if total_sales > 0 else 0
    pct_ads = (total_ads / total_sales * 100) if total_sales > 0 else 0
    pct_profit = (total_profit / total_sales * 100) if total_sales > 0 else 0

    cls_sales_v = "val-neg" if total_sales < 0 else "val-sales"
    cls_sales_s = "sub-neg" if total_sales < 0 else "sub-sales"
    cls_ops_v = "val-neg" if total_ops < 0 else "val-ops"
    cls_ops_s = "sub-neg" if total_ops < 0 else "sub-ops"
    cls_com_v = "val-neg" if total_com < 0 else "val-com"
    cls_com_s = "sub-neg" if total_com < 0 else "sub-com"
    cls_costprod_v = "val-neg" if total_cost_prod < 0 else "val-costprod"
    cls_costprod_s = "sub-neg" if total_cost_prod < 0 else "sub-costprod"
    cls_ads_v = "val-neg" if total_ads < 0 else "val-ads"
    cls_ads_s = "sub-neg" if total_ads < 0 else "sub-ads"
    cls_prof_v = "val-neg" if total_profit < 0 else "val-profit"
    cls_prof_s = "sub-neg" if total_profit < 0 else "sub-profit"

    html = f"""
<div class="metric-container">
<div class="custom-card border-blue">
<div class="card-label">ยอดขายรวม</div>
<div class="{cls_sales_v}">{total_sales:,.0f}</div>
<div class="{cls_sales_s}">{pct_sales:.0f}%</div>
</div>
<div class="custom-card border-ops">
<div class="card-label">ค่าดำเนินการ</div>
<div class="{cls_ops_v}">{total_ops:,.0f}</div>
<div class="{cls_ops_s}">{pct_ops:.1f}%</div>
</div>
<div class="custom-card border-com">
<div class="card-label">ค่าคอมมิชชั่น</div>
<div class="{cls_com_v}">{total_com:,.0f}</div>
<div class="{cls_com_s}">{pct_com:.1f}%</div>
</div>
<div class="custom-card border-costprod">
<div class="card-label">ทุนสินค้า</div>
<div class="{cls_costprod_v}">{total_cost_prod:,.0f}</div>
<div class="{cls_costprod_s}">{pct_cost_prod:.1f}%</div>
</div>
<div class="custom-card border-orange">
<div class="card-label">ค่าโฆษณา</div>
<div class="{cls_ads_v}">{total_ads:,.0f}</div>
<div class="{cls_ads_s}">{pct_ads:.1f}%</div>
</div>
<div class="custom-card border-green">
<div class="card-label">กำไรสุทธิ</div>
<div class="{cls_prof_v}">{total_profit:,.0f}</div>
<div class="{cls_prof_s}">{pct_profit:.1f}%</div>
</div>
</div>
"""
    st.markdown(html, unsafe_allow_html=True)
