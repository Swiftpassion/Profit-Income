import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import select, update, insert
from models import Product, Sale, PurchaseOrder, StockLog, User
from config import COLUMN_MAPPING_PRODUCT, COLUMN_MAPPING_PO
import streamlit as st
import datetime

def clean_column_names(df):
    df.columns = df.columns.astype(str).str.strip()
    return df

def map_columns(df, mapping):
    # Find which columns from mapping exist in df
    rename_dict = {k: v for k, v in mapping.items() if k in df.columns}
    return df.rename(columns=rename_dict)

def import_master_products(file, session: Session):
    try:
        df = pd.read_excel(file)
        df = clean_column_names(df)
        df = map_columns(df, COLUMN_MAPPING_PRODUCT)
        
        required_cols = ['product_id']
        if not all(col in df.columns for col in required_cols):
            return 0, 0, f"Missing required columns: {required_cols}. Found: {df.columns.tolist()}"
            
        # Basic cleaning
        df['product_id'] = df['product_id'].astype(str).str.strip()
        if 'current_stock' in df.columns:
            df['current_stock'] = pd.to_numeric(df['current_stock'], errors='coerce').fillna(0).astype(int)
        if 'min_limit' in df.columns:
            df['min_limit'] = pd.to_numeric(df['min_limit'], errors='coerce').fillna(0).astype(int)
            
        records = df.to_dict('records')
        
        # Strategy: Upsert
        # 1. Identify existing IDs
        existing_ids = set(flat for flat in session.scalars(select(Product.id)).all())
        
        to_insert = []
        to_update = []
        
        updates_count = 0
        inserts_count = 0
        
        for row in records:
            pid = row.get('product_id')
            if not pid: continue
            
            # Prepare data dict (filter out keys that are not in model)
            # This relies on column mapping being correct for model fields
            # We must map 'product_id' -> 'id', 'product_name' -> 'name' to match Model definition
            
            data = {}
            if pid: data['id'] = pid
            if 'product_name' in row: data['name'] = row['product_name']
            if 'image_url' in row: data['image_url'] = row['image_url']
            if 'current_stock' in row: data['current_stock'] = row['current_stock']
            if 'min_limit' in row: data['min_limit'] = row['min_limit']
            if 'product_type' in row: data['product_type'] = row['product_type']
            if 'note' in row: data['note'] = row['note']
            
            # Remove keys with NaN values
            data = {k: v for k, v in data.items() if pd.notna(v)}
            
            if pid in existing_ids:
                # Update
                # Note: This is row-by-row update which is slower, but safe for generic DB.
                # For batch update, we'd need a list of dicts with bindparams.
                # Let's simple session.merge for upsert logic if list is small, or specialized batch update.
                stmt = update(Product).where(Product.id == pid).values(**data)
                session.execute(stmt)
                updates_count += 1
            else:
                to_insert.append(data)
                inserts_count += 1
                
        if to_insert:
            session.execute(insert(Product), to_insert)
            
        session.commit()
        return inserts_count, updates_count, None
        
    except Exception as e:
        session.rollback()
        return 0, 0, str(e)

def import_actual_stock(file, session: Session):
    try:
        df = pd.read_excel(file)
        df = clean_column_names(df)
        
        # Dynamic Search for Product ID column
        pid_col = next((c for c in df.columns if c in ['รหัสSKU', 'SKU', 'รหัสสินค้า', 'รหัส', 'Item No', 'Product_ID']), None)
        
        # Dynamic Search for Stock column
        stock_col = next((c for c in df.columns if 'ใช้ได้' in c), None) # Priority 1
        if not stock_col: stock_col = next((c for c in df.columns if 'คงเหลือ' in c), None) # Priority 2
        if not stock_col: stock_col = next((c for c in df.columns if 'Stock' in c or 'จำนวน' in c), None) # Priority 3
        
        if not pid_col or not stock_col:
            return 0, f"Could not identify ID or Stock columns. Found: {df.columns.tolist()}"
            
        df = df.rename(columns={pid_col: 'product_id', stock_col: 'current_stock'})
        
        updates_count = 0
        
        # Iterate and update
        # We only update existing products. We do NOT create new products from Stock file (usually).
        records = df[['product_id', 'current_stock']].to_dict('records')
        
        for row in records:
            pid = str(row['product_id']).strip()
            try:
                stock_val = int(float(row['current_stock']))
            except:
                continue
                
            # Check existence
            product = session.get(Product, pid)
            if product:
                product.current_stock = stock_val
                updates_count += 1
                
        session.commit()
        return updates_count, None
        
    except Exception as e:
        session.rollback()
        return 0, str(e)

def import_sales_history(file, session: Session):
    try:
        df = pd.read_excel(file)
        df = clean_column_names(df)
        
        # Mapping
        col_map = {'รหัสสินค้า':'product_id', 'จำนวน':'quantity', 'ร้านค้า':'shop', 'เวลาสั่งซื้อ':'order_time'}
        df = df.rename(columns={k:v for k,v in col_map.items() if k in df.columns})
        
        if 'product_id' not in df.columns or 'quantity' not in df.columns:
             return 0, "Missing product_id or quantity columns."

        df['product_id'] = df['product_id'].astype(str).str.strip()
        df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0).astype(int)
        
        if 'order_time' in df.columns:
            df['order_time'] = pd.to_datetime(df['order_time'], errors='coerce')
            df['date_only'] = df['order_time'].dt.date
        
        # Append strategy: Avoid duplicates if same product, shop, order_time, qty exist?
        # Doing a rigorous check for every row is expensive.
        # User requirement: "Apppend new sales records (avoid duplicates if possible based on Order ID/Date)"
        # Since we assume historical data load or monthly load, maybe just insert all?
        # Let's try to check existence of a "signature" for de-dup.
        
        inserted_count = 0
        to_insert = []
        
        # Pre-fetch potential duplicates? Too hard without index on time.
        # Just iterate.
        
        # 1. Fetch valid Product IDs to prevent ForeignKeyViolation
        valid_pids = set(session.scalars(select(Product.id)).all())
        
        skipped_count = 0
        
        for index, row in df.iterrows():
            if not row['product_id']: continue
            
            # Check foreign key constraint
            if row['product_id'] not in valid_pids:
                skipped_count += 1
                continue
            
            # Simple check: If we have order_time, check if a sale exists for this product at this time from this shop
            exists = False
            if pd.notna(row.get('order_time')):
                stmt = select(Sale).where(
                    Sale.product_id == row['product_id'],
                    Sale.order_time == row['order_time'],
                    Sale.shop == row.get('shop')
                )
                if session.execute(stmt).first():
                    exists = True
            
            if not exists:
                sale = {
                    "product_id": row['product_id'],
                    "quantity": row['quantity'],
                    "shop": row.get('shop'),
                    "order_time": row.get('order_time') if pd.notna(row.get('order_time')) else None,
                    "date_only": row.get('date_only') if pd.notna(row.get('date_only')) else None
                }
                to_insert.append(sale)
                inserted_count += 1

        if to_insert:
            session.execute(insert(Sale), to_insert)
            
        session.commit()
        session.commit()
        
        msg = None
        if skipped_count > 0:
            msg = f"Skipped {skipped_count} items (Product ID not found in Master)."
            
        return inserted_count, msg
        
    except Exception as e:
        session.rollback()
        return 0, str(e)

def get_products_df(session: Session):
    stmt = select(Product)
    products = session.scalars(stmt).all()
    if not products:
        return pd.DataFrame()
    
    # Convert manually to avoid detaching issues or use pandas read_sql
    data = []
    for p in products:
        data.append({
            'Product_ID': p.id,
            'Product_Name': p.name,
            'Image': p.image_url,
            'Initial_Stock': p.current_stock, # Mapping back for app compatibility
            'Min_Limit': p.min_limit,
            'Product_Type': p.product_type,
            'Note': p.note
        })
    return pd.DataFrame(data)

def get_sales_df(session: Session):
    # Use direct SQL read for speed if needed, or ORM
    # The app expects columns: 'Product_ID', 'Qty_Sold', 'Shop', 'Order_Time', 'Date_Only'
    stmt = select(Sale)
    sales = session.scalars(stmt).all()
    
    data = []
    for s in sales:
        data.append({
            'Product_ID': s.product_id,
            'Qty_Sold': s.quantity,
            'Shop': s.shop,
            'Order_Time': s.order_time,
            'Date_Only': s.date_only
        })
    df = pd.DataFrame(data)
    if not df.empty and 'Order_Time' in df.columns:
         df['Order_Time'] = pd.to_datetime(df['Order_Time'])
    return df
