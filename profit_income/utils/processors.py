import pandas as pd
import streamlit as st
import os
from utils.data_helpers import find_header_row, get_col_data
from utils.common import clean_date, clean_text, clean_scientific_notation

def _find_sheet(data_io, preferred_names, fallback=0):
    """Return the first matching sheet name (case-insensitive), or fallback index."""
    try:
        data_io.seek(0)
        xl = pd.ExcelFile(data_io)
        sheets_lower = {s.lower(): s for s in xl.sheet_names}
        for name in preferred_names:
            if name.lower() in sheets_lower:
                data_io.seek(0)
                return sheets_lower[name.lower()]
    except Exception:
        pass
    data_io.seek(0)
    return fallback

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
                            income_sheet = _find_sheet(data, ['Order details', 'order details'])
                            header_idx = find_header_row(data, ['Order ID', 'Settlement Amount', 'Affiliate Commission', 'Order/adjustment ID'], sheet_name=income_sheet)
                            data.seek(0)
                            df = pd.read_excel(data, sheet_name=income_sheet, header=header_idx, dtype=str)

                        # Normalize column names to strip trailing whitespace
                        df.columns = df.columns.str.strip()

                        oid_col = get_col_data(df, ['Order ID', 'Order No', 'หมายเลขคำสั่งซื้อ', 'Order/adjustment ID', 'หมายเลขคำสั่งซื้อ/การปรับ'])
                        if oid_col is None: continue

                        inc = pd.DataFrame()
                        inc['order_id'] = oid_col.astype(str).apply(clean_scientific_notation)

                        # For non-Order rows (reimbursements, adjustments) use Related order ID
                        # so their settlement amount is attributed to the original order
                        type_col = get_col_data(df, ['Type', 'ประเภทธุรกรรม'])
                        related_col = get_col_data(df, ['Related order ID', 'หมายเลขคำสั่งซื้อที่เกี่ยวข้อง'])
                        if type_col is not None and related_col is not None:
                            related_clean = related_col.astype(str).apply(clean_scientific_notation)
                            is_order = type_col.str.strip().isin(['Order', 'คำสั่งซื้อ'])
                            inc['order_id'] = inc['order_id'].where(is_order, related_clean)

                        settle = get_col_data(df, ['Settlement Amount', 'Payout Amount', 'ยอดเงินที่ได้รับ', 'Total settlement amount', 'จำนวนเงินที่ชำระทั้งหมด'])
                        inc['settlement_amount'] = pd.to_numeric(settle, errors='coerce').fillna(0)

                        aff = get_col_data(df, ['Affiliate Commission', 'Affiliate Fee', 'ค่าคอมมิชชั่น', 'ค่าคอมมิชชั่นแอฟฟิลิเอต'])
                        aff_vals = pd.to_numeric(aff, errors='coerce').fillna(0)
                        # New format stores fees as negative; take abs so we store as positive cost
                        inc['affiliate'] = aff_vals.abs()

                        # Total Fees includes Affiliate Commission — subtract to get platform fees only
                        total_fee_raw = get_col_data(df, ['Total Fees', 'ค่าธรรมเนียมทั้งหมด'])
                        total_fees = pd.to_numeric(total_fee_raw, errors='coerce').fillna(0).abs()
                        inc['fees'] = total_fees - inc['affiliate']

                        inc['settlement_date'] = get_col_data(df, ['Order settled time', 'Settlement Date', 'Settled Time', 'เวลาที่ชำระคำสั่งซื้อ'])
                        inc = clean_date(inc, 'settlement_date')

                        income_dfs.append(inc)
                except Exception as e:
                    print(f"Error loading income {filename}: {e}")
                    continue

        if income_dfs:
            combined_inc = pd.concat(income_dfs, ignore_index=True)
            # Filter out rows with empty/invalid order_id before aggregation
            combined_inc = combined_inc[combined_inc['order_id'].str.strip().replace({'nan': '', 'None': ''}) != '']
            # Deduplicate same order+settlement_date across overlapping income files
            # (prevents double-counting when user uploads both English & Thai versions of same statement)
            combined_inc = combined_inc.drop_duplicates(subset=['order_id', 'settlement_date'], keep='first')
            return combined_inc.groupby('order_id').agg(
                settlement_amount=('settlement_amount', 'sum'),
                affiliate=('affiliate', 'sum'),
                fees=('fees', 'sum'),
                settlement_date=('settlement_date', 'first')
            ).reset_index()
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
                        # TikTok orders are in 'OrderSKUList' sheet
                        order_sheet = _find_sheet(data, ['OrderSKUList', 'Order SKU List', 'orders'])
                        header_idx = find_header_row(data, ['Order ID', 'Seller SKU', 'Product Name'], sheet_name=order_sheet)
                        data.seek(0)
                        df = pd.read_excel(data, sheet_name=order_sheet, header=header_idx, dtype=str)

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
                    extracted['line_no'] = extracted.groupby(['order_id', 'sku']).cumcount()
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
        # order_id not found in the Income file -> ยังไม่มี income เข้ามาตรงกับออเดอร์นี้
        merged['has_income'] = merged['settlement_amount'].notna()
        for col in ['settlement_amount', 'affiliate', 'fees']:
            if col in merged.columns: merged[col] = merged[col].fillna(0)
        return merged
    else:
        final_orders['settlement_amount'] = 0
        final_orders['affiliate'] = 0
        final_orders['fees'] = 0
        final_orders['has_income'] = False
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
                    income_sheet = _find_sheet(data, ['Income', 'income'])
                    header_idx = find_header_row(data, ['หมายเลขคำสั่งซื้อ', 'Order ID', 'จำนวนเงินทั้งหมดที่โอนแล้ว', 'Payout Amount', 'วันที่โอนชำระเงินสำเร็จ'], sheet_name=income_sheet)
                    data.seek(0)
                    df = pd.read_excel(data, sheet_name=income_sheet, header=header_idx, dtype=str)
                    df = df.dropna(how='all')

                    order_id_col = get_col_data(df, ['หมายเลขคำสั่งซื้อ', 'Order ID'])
                    if order_id_col is None:
                        continue

                    inc = pd.DataFrame()
                    inc['order_id'] = order_id_col
                    inc['settlement_date'] = get_col_data(df, ['วันที่โอนชำระเงินสำเร็จ', 'Payout Completed Date', 'วันที่ปรับปรุงเข้ายอดของฉัน'])
                    inc['settlement_amount'] = pd.to_numeric(get_col_data(df, ['จำนวนเงินทั้งหมดที่โอนแล้ว (฿)', 'จำนวนเงินทั้งหมดที่โอนแล้ว', 'Payout Amount', 'Total Payout']), errors='coerce').fillna(0)
                    inc['original_price'] = pd.to_numeric(get_col_data(df, ['สินค้าราคาปกติ', 'Original Price', 'ราคาตั้งต้น']), errors='coerce').fillna(0)
                    inc['affiliate'] = pd.to_numeric(get_col_data(df, ['ค่าคอมมิชชั่น AMS', 'ค่าคอมมิชชั่น', 'Commission Fee']), errors='coerce').fillna(0).abs()

                    # ค่าธรรมเนียมรวม = คอลัมน์ AA+AB+AC+AD+AE+AF+AG ในไฟล์ Income ของ Shopee
                    # (ค่าคอมมิชชั่น, ค่าบริการ, ค่าธรรมเนียมโครงสร้างพื้นฐานแพลตฟอร์ม, ค่าธรรมเนียมของโปรแกรมประหยัดค่าจัดส่ง,
                    #  ค่าธุรกรรมการชำระเงิน, ภาษี, ค่าธรรมเนียมเติมเงินโฆษณาจากเงิน Escrow)
                    fee_col_names = [
                        'ค่าคอมมิชชั่น',
                        'ค่าบริการ',
                        'ค่าธรรมเนียมโครงสร้างพื้นฐานแพลตฟอร์ม',
                        'ค่าธรรมเนียม ของโปรแกรมประหยัดค่าจัดส่ง',
                        'ค่าธุรกรรมการชำระเงิน',
                        'ภาษี',
                        'ค่าธรรมเนียมเติมเงินโฆษณาจากเงิน Escrow',
                    ]
                    fee_cols_found = [get_col_data(df, [name]) for name in fee_col_names]
                    fee_cols_found = [pd.to_numeric(c, errors='coerce').fillna(0).abs() for c in fee_cols_found if c is not None]

                    inc = inc.dropna(subset=['order_id'])
                    inc = inc[inc['order_id'].astype(str).str.strip() != '']
                    if not inc.empty:
                        if fee_cols_found:
                            inc['fees'] = sum(c.loc[inc.index] for c in fee_cols_found)
                        else:
                            # Fallback สำหรับไฟล์รูปแบบเก่าที่ไม่มีคอลัมน์ค่าธรรมเนียมแยกรายการ
                            inc['fees'] = (inc['original_price'].fillna(0) - inc['settlement_amount'].fillna(0) - inc['affiliate']).clip(lower=0)
                        inc = clean_date(inc, 'settlement_date')
                        inc['order_id'] = inc['order_id'].apply(clean_scientific_notation)
                        income_dfs.append(inc)
            except Exception as e:
                st.error(f"❌ Shopee Income {filename}: {e}")

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
                    ext['sales_amount'] = pd.to_numeric(get_col_data(df, ['ราคาขายสุทธิ', 'Net Price', 'ราคาต่อหน่วย', 'ราคาขาย', 'ยอดชำระเงิน', 'ราคาสินค้าที่ชำระโดยผู้ซื้อ (THB)']), errors='coerce').fillna(0)
                    ext['tracking_id'] = get_col_data(df, ['หมายเลขติดตามพัสดุ', 'Tracking Number*', '*หมายเลขติดตามพัสดุ'])
                    ext['created_date'] = get_col_data(df, ['วันที่ทำการสั่งซื้อ', 'Order Creation Date'])
                    ext['shipped_date'] = get_col_data(df, ['เวลาการชำระสินค้า', 'Payment Time'])
                    ext['product_name'] = get_col_data(df, ['ชื่อสินค้า', 'Product Name'])

                    ext['shop_name'] = shop_name
                    ext['platform'] = 'SHOPEE'

                    ext = clean_date(ext, 'created_date')
                    ext = clean_date(ext, 'shipped_date')
                    ext['order_id'] = ext['order_id'].apply(clean_scientific_notation)
                    ext = clean_text(ext, 'sku')
                    ext['line_no'] = ext.groupby(['order_id', 'sku']).cumcount()

                    all_orders.append(ext)
            except Exception as e:
                st.error(f"❌ Shopee {filename}: {e}")

    if not all_orders: return pd.DataFrame()
    final = pd.concat(all_orders, ignore_index=True)

    # Shopee ยังใช้สูตรกำไรสุทธิแบบเดิม (อิงยอดขาย) จึงไม่เช็คสถานะ income ต่อออเดอร์ในตอนนี้
    if not income_master.empty:
        merged = pd.merge(final, income_master, on='order_id', how='left')
        merged['has_income'] = True
        return merged
    final['has_income'] = True
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
                    income_sheet = _find_sheet(data, ['Income Overview', 'income overview', 'Income', 'Sheet1'])
                    header_idx = find_header_row(data, ['Order No.', 'หมายเลขคำสั่งซื้อ', 'Transaction Date', 'วันที่ทำรายการ', 'Amount', 'จำนวนเงิน(รวมภาษี)', 'จำนวนเงิน', 'Fee Name'], sheet_name=income_sheet)
                    data.seek(0)
                    df = pd.read_excel(data, sheet_name=income_sheet, header=header_idx, dtype=str)
                    df = df.dropna(how='all')

                    oid = get_col_data(df, ['Order No.', 'หมายเลขคำสั่งซื้อ', 'Order ID', 'orderNumber'])
                    if oid is None: continue

                    inc = pd.DataFrame()
                    inc['order_id'] = oid
                    inc['settlement_date'] = get_col_data(df, ['Transaction Date', 'วันที่ทำรายการ', 'วันที่สร้างคำสั่งซื้อ'])
                    amt_col = get_col_data(df, ['Amount (incl. VAT)', 'จำนวนเงิน(รวมภาษี)', 'Amount', 'จำนวนเงิน'])
                    inc['settlement_amount'] = pd.to_numeric(amt_col, errors='coerce').fillna(0)

                    inc = inc.dropna(subset=['order_id'])
                    inc = inc[inc['order_id'].astype(str).str.strip() != '']
                    if not inc.empty:
                        inc['order_id'] = inc['order_id'].apply(clean_scientific_notation)
                        income_dfs.append(inc)
            except Exception as e:
                st.error(f"❌ Lazada Income {filename}: {e}")

    income_master = pd.DataFrame()
    if income_dfs:
        raw_income = pd.concat(income_dfs, ignore_index=True)
        income_master = raw_income.groupby('order_id').agg(
            settlement_amount=('settlement_amount', 'sum'),
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
                    order_sheet = _find_sheet(data, ['sheet1', 'Sheet1', 'orders', 'Orders'])
                    header_idx = find_header_row(data, ['orderItemId', 'orderNumber', 'หมายเลขคำสั่งซื้อ', 'sellerSku'], sheet_name=order_sheet)
                    data.seek(0)
                    df = pd.read_excel(data, sheet_name=order_sheet, header=header_idx, dtype=str)

                    ext = pd.DataFrame()
                    oid = get_col_data(df, ['orderNumber', 'หมายเลขคำสั่งซื้อ', 'Order Number'])
                    if oid is None: continue

                    ext['order_id'] = oid
                    ext['status'] = get_col_data(df, ['status', 'สถานะ'])
                    ext['sku'] = get_col_data(df, ['sellerSku', 'Seller SKU', 'รหัสสินค้าของร้านค้า'])
                    ext['sales_amount'] = pd.to_numeric(get_col_data(df, ['unitPrice', 'ราคาต่อหน่วย', 'Unit Price', 'paidPrice']), errors='coerce').fillna(0)
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
                    ext['line_no'] = ext.groupby(['order_id', 'sku']).cumcount()
                    all_orders.append(ext)
            except Exception as e:
                st.error(f"❌ Lazada Order {filename}: {e}")

    if not all_orders: return pd.DataFrame()
    final_orders = pd.concat(all_orders, ignore_index=True)

    # Lazada ใช้สูตรกำไรสุทธิแบบ settlement (เหมือน TikTok): ยอดเงินที่ได้รับจริง - ต้นทุน - ค่าดำเนินการ
    if not income_master.empty:
        final_orders['order_id'] = final_orders['order_id'].astype(str).str.strip()
        income_master['order_id'] = income_master['order_id'].astype(str).str.strip()
        merged = pd.merge(final_orders, income_master, on='order_id', how='left')
        # order_id ที่ไม่พบในไฟล์ Income -> ยังไม่มี income เข้ามาตรงกับออเดอร์นี้
        merged['has_income'] = merged['settlement_amount'].notna()
        for col in ['settlement_amount', 'affiliate', 'fees', 'original_price']:
            if col in merged.columns: merged[col] = merged[col].fillna(0)
        return merged
    else:
        for col in ['settlement_amount', 'affiliate', 'fees', 'original_price']:
            final_orders[col] = 0
        final_orders['has_income'] = False
        return final_orders
