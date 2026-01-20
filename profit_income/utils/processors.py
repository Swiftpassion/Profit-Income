import pandas as pd
import streamlit as st
import os
from utils.data_helpers import find_header_row, get_col_data
from utils.common import clean_date, clean_text, clean_scientific_notation

def process_tiktok(order_files, income_files, shop_name):
    # --- Helper to load income ---
    def load_tiktok_income(inc_files):
        income_dfs = []
        for f_path in inc_files:
            filename = os.path.basename(f_path)
            if any(ext in filename.lower() for ext in ['xlsx', 'xls', 'csv']):
                try:
                    with open(f_path, 'rb') as data:
                        if 'csv' in filename.lower():
                            try:
                                data.seek(0); df = pd.read_csv(data, dtype=str)
                            except UnicodeDecodeError:
                                data.seek(0); df = pd.read_csv(data, encoding='cp874', dtype=str)
                        else:
                            header_idx = find_header_row(data, ['Order ID', 'Settlement Amount', 'Affiliate Commission'])
                            data.seek(0)
                            df = pd.read_excel(data, header=header_idx, dtype=str)
                        
                        inc = pd.DataFrame()
                        # Added Order/adjustment ID for new format
                        oid = get_col_data(df, ['Order ID', 'Order No', 'หมายเลขคำสั่งซื้อ', 'Order/adjustment ID'])
                        if oid is None: continue
                        inc['order_id'] = oid
                        
                        # Added Total settlement amount
                        settle = get_col_data(df, ['Settlement Amount', 'Payout Amount', 'ยอดเงินที่ได้รับ', 'Total settlement amount'])
                        inc['settlement_amount'] = pd.to_numeric(settle, errors='coerce').fillna(0)
                        
                        aff = get_col_data(df, ['Affiliate Commission', 'Affiliate Fee', 'ค่าคอมมิชชั่น'])
                        inc['affiliate'] = pd.to_numeric(aff, errors='coerce').fillna(0)
                        
                        fee = get_col_data(df, ['Platform Fee', 'Transaction Fee', 'ค่าธรรมเนียม', 'Total Fees'])
                        inc['fees'] = pd.to_numeric(fee, errors='coerce').fillna(0)
                        
                        # Filter out invalid rows from income too just in case
                        # inc = inc[~inc['order_id'].astype(str).str.contains('Platform', na=False)]
                        
                        inc['order_id'] = inc['order_id'].astype(str).apply(clean_scientific_notation)
                        income_dfs.append(inc)
                except Exception as e:
                    print(f"Error loading income {filename}: {e}")
                    continue
        
        if income_dfs:
            combined_inc = pd.concat(income_dfs, ignore_index=True)
            return combined_inc.groupby('order_id')[['settlement_amount', 'affiliate', 'fees']].sum().reset_index()
        return pd.DataFrame()

    # --- Load Income Data ---
    income_master = load_tiktok_income(income_files)

    # --- Read Order Files ---
    all_orders = []
    for f_path in order_files:
        filename = os.path.basename(f_path)
        if any(ext in filename.lower() for ext in ['xlsx', 'xls', 'csv']):
            try:
                with open(f_path, 'rb') as data:
                    if 'csv' in filename.lower():
                        try: data.seek(0); df = pd.read_csv(data, dtype=str)
                        except UnicodeDecodeError: data.seek(0); df = pd.read_csv(data, encoding='cp874', dtype=str)
                    else:
                        header_idx = find_header_row(data, ['Order ID', 'Seller SKU', 'Product Name'])
                        data.seek(0)
                        df = pd.read_excel(data, header=header_idx, dtype=str)
                    
                    extracted = pd.DataFrame()
                    oid = get_col_data(df, ['Order ID', 'หมายเลขคำสั่งซื้อ', 'Order Serial No.'])
                    if oid is None: continue
                    extracted['order_id'] = oid
                    extracted['status'] = get_col_data(df, ['Order Status', 'สถานะคำสั่งซื้อ'])
                    if 'status' not in extracted.columns: extracted['status'] = 'สำเร็จ'

                    sku = get_col_data(df, ['Seller SKU', 'รหัสสินค้าของผู้ขาย', 'SKU ID'])
                    extracted['sku'] = sku if sku is not None else '-'

                    qty = get_col_data(df, ['Quantity', 'จำนวน', 'Qty'])
                    extracted['quantity'] = pd.to_numeric(qty, errors='coerce').fillna(1) if qty is not None else 1

                    sales = get_col_data(df, ['SKU Subtotal After Discount', 'Order Amount', 'ยอดคำสั่งซื้อ'])
                    extracted['sales_amount'] = pd.to_numeric(sales, errors='coerce').fillna(0) if sales is not None else 0

                    extracted['created_date'] = get_col_data(df, ['Created Time', 'เวลาที่สร้าง'])
                    extracted['shipped_date'] = get_col_data(df, ['Shipped Time', 'เวลาจัดส่ง', 'RTS Time'])
                    
                    track = get_col_data(df, ['Tracking ID', 'หมายเลขติดตามพัสดุ'])
                    extracted['tracking_id'] = track if track is not None else '-'
                    
                    pname = get_col_data(df, ['Product Name', 'ชื่อสินค้า'])
                    extracted['product_name'] = pname if pname is not None else '-'

                    extracted['shop_name'] = shop_name
                    extracted['platform'] = 'TIKTOK'

                    extracted = clean_date(extracted, 'created_date')
                    extracted = clean_date(extracted, 'shipped_date')
                    
                    # Clean Order ID and filter garbage
                    extracted['order_id'] = extracted['order_id'].astype(str).apply(clean_scientific_notation)
                    extracted = extracted[~extracted['order_id'].str.contains('Platform', case=False, na=False)]
                    
                    extracted = clean_text(extracted, 'sku')
                    all_orders.append(extracted)

            except Exception as e:
                st.error(f"❌ TikTok Order {filename}: {e}")
                continue

    if not all_orders: return pd.DataFrame()
    final_orders = pd.concat(all_orders, ignore_index=True)
    
    # --- Merge with Income Data ---
    if not income_master.empty:
        final_orders['order_id'] = final_orders['order_id'].astype(str).str.strip()
        income_master['order_id'] = income_master['order_id'].astype(str).str.strip()
        merged = pd.merge(final_orders, income_master, on='order_id', how='left')
        for col in ['settlement_amount', 'affiliate', 'fees']:
            if col in merged.columns: merged[col] = merged[col].fillna(0)
        return merged
    else:
        final_orders['settlement_amount'] = 0
        final_orders['affiliate'] = 0
        final_orders['fees'] = 0
        return final_orders

def process_shopee(order_files, income_files, shop_name):
    all_orders = []
    income_dfs = []

    # --- Shopee Income ---
    for f_path in income_files:
        filename = os.path.basename(f_path)
        if any(x in filename.lower() for x in ['xls', 'xlsx']):
            try:
                with open(f_path, 'rb') as data:
                    header_idx = find_header_row(data, ['หมายเลขคำสั่งซื้อ', 'Order ID'], sheet_name='Income')
                    data.seek(0)
                    df = pd.read_excel(data, sheet_name='Income', header=header_idx, dtype=str)
                    
                    inc = pd.DataFrame()
                    inc['order_id'] = get_col_data(df, ['หมายเลขคำสั่งซื้อ', 'Order ID'])
                    inc['settlement_date'] = get_col_data(df, ['วันที่โอนชำระเงินสำเร็จ', 'Payout Completed Date'])
                    inc['settlement_amount'] = pd.to_numeric(get_col_data(df, ['จำนวนเงินทั้งหมดที่โอนแล้ว (฿)', 'Payout Amount']), errors='coerce')
                    inc['original_price'] = pd.to_numeric(get_col_data(df, ['สินค้าราคาปกติ', 'Original Price']), errors='coerce')
                    inc['affiliate'] = pd.to_numeric(get_col_data(df, ['ค่าคอมมิชชั่น', 'Commission Fee']), errors='coerce') 
                    
                    if not inc.empty and 'order_id' in inc.columns:
                        inc['fees'] = (inc['original_price'].fillna(0) - inc['settlement_amount'].fillna(0))
                        inc = clean_date(inc, 'settlement_date')
                        inc['order_id'] = inc['order_id'].apply(clean_scientific_notation)
                        income_dfs.append(inc)
            except: pass
    
    income_master = pd.concat(income_dfs, ignore_index=True).drop_duplicates(subset=['order_id']) if income_dfs else pd.DataFrame()

    # --- Shopee Orders ---
    for f_path in order_files:
        filename = os.path.basename(f_path)
        if any(x in filename.lower() for x in ['xls', 'xlsx']):
            try:
                with open(f_path, 'rb') as data:
                    header_idx = find_header_row(data, ['หมายเลขคำสั่งซื้อ', 'Order ID'])
                    data.seek(0)
                    df = pd.read_excel(data, header=header_idx, dtype=str)
                    
                    ext = pd.DataFrame()
                    oid = get_col_data(df, ['หมายเลขคำสั่งซื้อ', 'Order ID'])
                    if oid is None: continue
                    
                    ext['order_id'] = oid
                    ext['status'] = get_col_data(df, ['สถานะการสั่งซื้อ', 'Order Status'])
                    ext['sku'] = get_col_data(df, ['เลขอ้างอิง SKU (SKU Reference No.)', 'SKU Reference No.'])
                    ext['quantity'] = pd.to_numeric(get_col_data(df, ['จำนวน', 'Quantity']), errors='coerce').fillna(1)
                    ext['sales_amount'] = pd.to_numeric(get_col_data(df, ['ราคาขายสุทธิ', 'Net Price', 'ราคาต่อหน่วย']), errors='coerce').fillna(0)
                    ext['tracking_id'] = get_col_data(df, ['หมายเลขติดตามพัสดุ', 'Tracking Number*'])
                    ext['created_date'] = get_col_data(df, ['วันที่ทำการสั่งซื้อ', 'Order Creation Date'])
                    ext['shipped_date'] = get_col_data(df, ['เวลาการชำระสินค้า', 'Payment Time'])
                    ext['product_name'] = get_col_data(df, ['ชื่อสินค้า', 'Product Name'])

                    ext['shop_name'] = shop_name
                    ext['platform'] = 'SHOPEE'
                    
                    ext = clean_date(ext, 'created_date')
                    ext = clean_date(ext, 'shipped_date')
                    ext['order_id'] = ext['order_id'].apply(clean_scientific_notation)
                    ext = clean_text(ext, 'sku')
                    
                    all_orders.append(ext)
            except Exception as e:
                st.error(f"❌ Shopee {filename}: {e}")

    if not all_orders: return pd.DataFrame()
    final = pd.concat(all_orders, ignore_index=True)
    
    if not income_master.empty:
        return pd.merge(final, income_master, on='order_id', how='left')
    return final

def process_lazada(order_files, income_files, shop_name):
    all_orders = []
    income_dfs = []

    # --- Lazada Income ---
    for f_path in income_files:
        filename = os.path.basename(f_path)
        if any(ext in filename.lower() for ext in ['xlsx', 'xls']):
            try:
                with open(f_path, 'rb') as data:
                    header_idx = find_header_row(data, ['Order No.', 'หมายเลขคำสั่งซื้อ', 'Transaction Date', 'วันที่ทำรายการ'])
                    data.seek(0)
                    df = pd.read_excel(data, header=header_idx, dtype=str)
                    
                    inc = pd.DataFrame()
                    oid = get_col_data(df, ['Order No.', 'หมายเลขคำสั่งซื้อ', 'Order ID'])
                    if oid is None: continue 
                    inc['order_id'] = oid
                    
                    inc['settlement_date'] = get_col_data(df, ['Transaction Date', 'วันที่ทำรายการ'])
                    amt_col = get_col_data(df, ['Amount (incl. VAT)', 'Amount', 'จำนวนเงิน(รวมภาษี)'])
                    inc['settlement_amount'] = pd.to_numeric(amt_col, errors='coerce').fillna(0)
                    
                    inc['order_id'] = inc['order_id'].apply(clean_scientific_notation)
                    income_dfs.append(inc)
            except: pass

    income_master = pd.DataFrame()
    if income_dfs:
        raw_income = pd.concat(income_dfs, ignore_index=True)
        income_master = raw_income.groupby('order_id').agg(
            settlement_amount=('settlement_amount', lambda x: x[x > 0].sum()),
            fees=('settlement_amount', lambda x: abs(x[x < 0].sum())),
            settlement_date=('settlement_date', 'first')
        ).reset_index()
        income_master = clean_date(income_master, 'settlement_date')
        income_master['original_price'] = 0
        income_master['affiliate'] = 0
        
    # --- Lazada Orders ---
    for f_path in order_files:
        filename = os.path.basename(f_path)
        if any(ext in filename.lower() for ext in ['xlsx', 'xls']):
            try:
                with open(f_path, 'rb') as data:
                    header_idx = find_header_row(data, ['Order Item Id', 'orderNumber', 'หมายเลขคำสั่งซื้อ'])
                    data.seek(0)
                    df = pd.read_excel(data, header=header_idx, dtype=str)
                    
                    ext = pd.DataFrame()
                    oid = get_col_data(df, ['orderNumber', 'หมายเลขคำสั่งซื้อ', 'Order Number'])
                    if oid is None: continue
                    
                    ext['order_id'] = oid
                    ext['status'] = get_col_data(df, ['status', 'สถานะ'])
                    ext['sku'] = get_col_data(df, ['sellerSku', 'Seller SKU', 'รหัสสินค้าของร้านค้า'])
                    ext['sales_amount'] = pd.to_numeric(get_col_data(df, ['paidPrice', 'ราคาที่ชำระ', 'Paid Price']), errors='coerce').fillna(0)
                    ext['tracking_id'] = get_col_data(df, ['trackingCode', 'Tracking Code', 'รหัสติดตามพัสดุ'])
                    ext['created_date'] = get_col_data(df, ['createTime', 'Created at', 'เวลาที่สั่งซื้อ'])
                    ext['shipped_date'] = get_col_data(df, ['updateTime', 'Updated at', 'เวลาที่ปรับปรุงล่าสุด']) 
                    ext['product_name'] = get_col_data(df, ['itemName', 'Item Name', 'ชื่อสินค้า'])
                    
                    ext['quantity'] = 1 
                    ext['shop_name'] = shop_name
                    ext['platform'] = 'LAZADA'
                    
                    ext = clean_date(ext, 'created_date')
                    ext = clean_date(ext, 'shipped_date')
                    ext['order_id'] = ext['order_id'].apply(clean_scientific_notation)
                    ext = clean_text(ext, 'sku')
                    all_orders.append(ext)
            except Exception as e:
                st.error(f"❌ Lazada Order {filename}: {e}")

    if not all_orders: return pd.DataFrame()
    final_orders = pd.concat(all_orders, ignore_index=True)
    
    if not income_master.empty:
        final_orders['order_id'] = final_orders['order_id'].astype(str).str.strip()
        income_master['order_id'] = income_master['order_id'].astype(str).str.strip()
        merged = pd.merge(final_orders, income_master, on='order_id', how='left')
        for col in ['settlement_amount', 'affiliate', 'fees', 'original_price']:
            if col in merged.columns: merged[col] = merged[col].fillna(0)
        return merged
    else:
        for col in ['settlement_amount', 'affiliate', 'fees', 'original_price']:
            final_orders[col] = 0
        return final_orders
