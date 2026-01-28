import streamlit as st

def load_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;600&display=swap');
    
    html, body, [class*="css"], .stMarkdown, .stText, .stButton, .stSelectbox, .stTextInput, font { 
        font-family: 'Sarabun', sans-serif !important; 
    }
    
    * {
        font-family: 'Sarabun', sans-serif !important;
    }

    /* Container */
    .custom-table-wrapper {
        overflow-x: auto;
        border: 1px solid #ddd;
        border-radius: 8px;
        margin-top: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        background-color: #1c1c1c; 
    }
    
    /* Table Styling General */
    table.report-table {
        width: 100%;
        border-collapse: collapse;
        min-width: 1500px; 
        font-size: 13px;
    }
    
    /* Header */
    table.report-table th {
        background-color: #2c3e50;
        color: white;
        padding: 8px 5px;
        text-align: center;
        border: 1px solid #34495e;
        position: sticky; top: 0; z-index: 100;
        white-space: nowrap;
    }
    
    /* Cells */
    table.report-table td {
        padding: 4px 6px;
        border: 1px solid #e0e0e0;
        color: #333;
        vertical-align: middle;
        height: 35px;
    }

    table.report-table tr:nth-child(even) { background-color: #f9f9f9; }
    table.report-table tr:hover { background-color: #f0f8ff; }

    .num { text-align: right; font-family: 'Courier New', monospace; font-weight: 600; }
    .txt { text-align: center; white-space: nowrap; }
    
    /* Helper Colors */
    .text-green { color: #27ae60; }
    .text-red { color: #fa0000; font-weight: bold; }
    .font-bold { font-weight: bold; }
    
    /* Progress Bar */
    .bar-container { position: absolute; bottom: 0; left: 0; height: 4px; background-color: #27ae60; opacity: 0.7; z-index: 1; }
    .cell-content { position: relative; z-index: 2; }
    td.relative-cell { position: relative; padding-bottom: 8px; }
    </style>
""", unsafe_allow_html=True)
