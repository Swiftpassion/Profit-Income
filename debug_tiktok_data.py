import pandas as pd
import os
import sys

# Set output file
output_file = "debug_output_income.txt"

def log(msg):
    with open(output_file, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg)

# Clear file
with open(output_file, "w", encoding="utf-8") as f:
    f.write("DEBUG LOG INCOME\n")

income_path = r"c:\Users\Thana\OneDrive\เอกสาร\GitHub\Profit-Income\data\TIKTOK\Income\การเงิน TIKTOK วันที่ 1 เดือน12 2568 - 7เดือน1  2569.xlsx"

log(f"Checking Income File: {income_path}")
try:
    # Use generic read to see columns first
    # Read only first few lines to be fast
    df_inc = pd.read_excel(income_path, dtype=str, nrows=50) 
    log(f"Income Columns (Raw): {df_inc.columns.tolist()}")
    
    # Check for header row manually if needed, but let's see raw
    # Try to find 'Order ID' in values if not in columns
    found_header = False
    for col in df_inc.columns:
        if 'Order' in col or 'หมายเลข' in col:
            log(f"Found apparent Order ID column in headers: {col}")
            sample = df_inc[col].head(10).tolist()
            log(f"Samples: {sample}")
            log(f"Repr: {[repr(x) for x in sample]}")
            found_header = True
            break
            
    if not found_header:
        log("Header not found in top row. Checking first few rows for header...")
        # Check rows for "Order ID"
        for idx, row in df_inc.iterrows():
            row_str = " ".join([str(x) for x in row.values])
            if 'Order ID' in row_str or 'Order No' in row_str:
                log(f"Found potential header at row {idx}: {row.tolist()}")
                # Assume this is header, correct header extraction would happen here
                break
                
except Exception as e:
    log(f"Error reading income file: {e}")
