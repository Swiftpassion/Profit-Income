import os
import streamlit as st

# Database Configuration
DB_USER = "admin"
DB_PASS = "mos2025"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "stock_jst"

# Try PostgreSQL first, fallback to SQLite
# Prefer connection string from Streamlit secrets if available, otherwise build it
if "DATABASE_URL" in st.secrets:
    DATABASE_URL = st.secrets["DATABASE_URL"]
else:
    # Local PostgreSQL
    DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Fallback SQLite path
SQLITE_DB_PATH = "stock_jst.db"
SQLITE_URL = f"sqlite:///{SQLITE_DB_PATH}"

# Google Sheet Config
MASTER_SHEET_ID = "1SC_Dpq2aiMWsS3BGqL_Rdf7X4qpTFkPA0wPV6mqqosI"
TAB_NAME_STOCK = "MASTER"
TAB_NAME_PO = "PO_DATA"
FOLDER_ID_STOCK_ACTUAL = "1-hXu2RG2gNKMkW3ZFBFfhjQEhTacVYzk"
FOLDER_ID_DATA_SALE = "12jyMKgFHoc9-_eRZ-VN9QLsBZ31ZJP4T"

# Excel Column Mappings
COLUMN_MAPPING_PRODUCT = {
    'รหัสสินค้า': 'product_id', 'รหัส': 'product_id', 'ID': 'product_id', 'รหัสSKU': 'product_id',
    'ชื่อสินค้า': 'product_name', 'ชื่อ': 'product_name', 'Name': 'product_name',
    'รูป': 'image_url', 'รูปภาพ': 'image_url', 'Link รูป': 'image_url', 'รูปภาพ SKU': 'image_url',
    'Stock': 'current_stock', 'จำนวน': 'current_stock', 'สต็อก': 'current_stock', 'คงเหลือ': 'current_stock',
    'สินค้าคงคลัง': 'current_stock', 'จํานวนที่ใช้ได้': 'current_stock',
    'Min_Limit': 'min_limit', 'Min': 'min_limit', 'จุดเตือน': 'min_limit',
    'สต็อกความปลอดภัยน้อยสุด': 'min_limit', 'จำนวนน้อยสุดในการเติมสินค้า (MIN)': 'min_limit',
    'Type': 'product_type', 'หมวดหมู่': 'product_type', 'Category': 'product_type', 'กลุ่ม': 'product_type',
    'หมายเหตุ': 'note', 'Note': 'note', 'Remark': 'note', 'Remarks': 'note'
}

COLUMN_MAPPING_PO = {
    'รหัสสินค้า': 'product_id', 'เลข PO': 'po_number', 'ขนส่ง': 'transport_type',
    'วันที่สั่งซื้อ': 'order_date',
    'Expected_Date': 'expected_date', 'วันที่คาดว่าจะได้รับ': 'expected_date', 'วันที่คาดการณ์': 'expected_date',
    'วันที่ได้รับ': 'received_date',
    'จำนวน': 'qty_ordered',
    'จำนวนที่ได้รับ': 'qty_received',
    'ราคา/ชิ้น': 'price_unit_novat', 'ราคา (หยวน)': 'total_yuan', 'เรทเงิน': 'yuan_rate',
    'เรทค่าขนส่ง': 'ship_rate', 'ขนาด (คิว)': 'cbm', 'ค่าส่ง': 'ship_cost', 'น้ำหนัก / KG': 'transport_weight',
    'SHOPEE': 'shopee_price', 'LAZADA': 'lazada_price', 'TIKTOK': 'tiktok_price', 'หมายเหตุ': 'note',
    'ราคา (บาท)': 'total_thb', 'Link_Shop': 'link', 'WeChat': 'wechat'
}
