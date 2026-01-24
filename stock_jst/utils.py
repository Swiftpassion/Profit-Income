import re
import pandas as pd

def clean_text_for_html(text):
    """
    Remove standard HTML tags and special characters.
    """
    if pd.isna(text): return ""
    text = str(text)
    clean = re.sub('<.*?>', '', text)
    return clean

def highlight_negative(val):
    """
    Color negative values red.
    """
    try:
        val = float(val)
    except:
        return ''
    color = 'red' if val < 0 else 'black'
    return f'color: {color}'

def format_currency_thb(val):
    try:
        return f"฿{float(val):,.2f}"
    except:
        return val

def format_number(val):
    try:
        return f"{int(val):,}"
    except:
        return val
