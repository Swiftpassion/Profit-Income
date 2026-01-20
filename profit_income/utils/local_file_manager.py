import os
import glob
import pandas as pd
import datetime

# Path to the data directory (root/data)
# script is in profit_income/utils/local_file_manager.py
# Root is profit_income/../
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, 'data')

def list_local_files(platform, category, shop_name=None):
    """
    List files in the local data directory.
    
    Args:
        platform (str): TIKTOK, SHOPEE, LAZADA
        category (str): Orders, Income
        shop_name (str, optional): Subfolder for specific shop.
        
    Returns:
        list: List of absolute file paths.
    """
    # Construct path: data/{PLATFORM}/{Category}/{ShopName}/
    path = os.path.join(DATA_DIR, platform, category)
    if shop_name:
        path = os.path.join(path, shop_name)
    
    if not os.path.exists(path):
        return []
        
    files = []
    # Look for Excel and CSV files
    extensions = ['*.xlsx', '*.xls', '*.csv']
    for ext in extensions:
        files.extend(glob.glob(os.path.join(path, ext)))
        
    return files

def get_file_info(file_path):
    """Get file size and modification time."""
    try:
        stat = os.stat(file_path)
        return {
            "name": os.path.basename(file_path),
            "size_mb": stat.st_size / (1024 * 1024),
            "modified": stat.st_mtime,
            "path": file_path
        }
    except:
        return None

def read_file(file_path):
    """
    Read a file into a pandas DataFrame.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext in ['.xlsx', '.xls']:
        return pd.read_excel(file_path)
    elif ext == '.csv':
        return pd.read_csv(file_path)
    return pd.DataFrame()

def save_uploaded_file(uploaded_file, platform, category, shop_name=None):
    """
    Save a Streamlit UploadedFile to the local directory.
    """
    # Construct path: data/{PLATFORM}/{Category}/{ShopName}/
    target_dir = os.path.join(DATA_DIR, platform, category)
    if shop_name:
        target_dir = os.path.join(target_dir, shop_name)
    
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        
    file_path = os.path.join(target_dir, uploaded_file.name)
    
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path

def delete_file(file_path):
    """
    Delete a file from the filesystem.
    """
    if os.path.exists(file_path):
        os.remove(file_path)
        return True
    return False
