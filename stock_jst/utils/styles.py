import streamlit as st

def load_css():
    st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;500;600&display=swap');

    /* 1. FORCE GLOBAL FONT */
    * {
        font-family: 'Sarabun', sans-serif !important;
    }

    /* 2. SIDEBAR STYLING */
    [data-testid="stSidebar"] {
        background-color: #1e3c72;
    }
    
    /* Fix Sidebar Radio Buttons Layout - Make them look like cards */
    [data-testid="stSidebar"] [data-testid="stRadio"] > div {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }

    [data-testid="stSidebar"] [data-testid="stRadio"] label {
        background-color: #262730 !important;
        border: 1px solid #4a4a4a !important;
        padding: 12px 15px !important;
        border-radius: 10px !important;
        width: 100% !important; /* Force full width */
        display: flex !important;
        align-items: center !important;
        transition: all 0.3s ease !important;
        margin: 0 !important;
        color: white !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2) !important;
    }

    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
        border-color: #ff4b4b !important;
        color: #ff4b4b !important;
        transform: translateX(5px); /* Add hover effect */
    }

    /* Active State (Checking data-checked attribute) */
    [data-testid="stSidebar"] [data-testid="stRadio"] label[data-checked="true"] {
        background-color: #ff4b4b !important;
        border-color: #ff4b4b !important;
        color: white !important;
        font-weight: 600 !important;
    }
    
    /* Hide default radio circle */
    [data-testid="stSidebar"] [data-testid="stRadio"] label div[role="radio"] {
        display: none !important;
    }

    /* 3. TABLE STYLING */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
    }
    
    [data-testid="stDataFrame"] th {
        text-align: center !important;
        background-color: #1e3c72 !important;
        color: white !important;
        vertical-align: middle !important;
        min-height: 60px;
        font-size: 14px;
        border-bottom: 2px solid #ffffff !important;
    }
    
    [data-testid="stDataFrame"] th:first-child { border-top-left-radius: 8px; }
    [data-testid="stDataFrame"] th:last-child { border-top-right-radius: 8px; }
    [data-testid="stDataFrame"] td { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 150px; }

    /* 4. GENERAL UI */
    .stButton button { 
        width: 100%; 
        border-radius: 8px;
        font-family: 'Sarabun', sans-serif !important;
    }
    
    /* Hide number input arrows */
    button[data-testid="stNumberInputStepDown"], button[data-testid="stNumberInputStepUp"] { display: none !important; }
    
    /* Toast Font */
    .st-toast, [data-testid="stToast"] {
        font-family: 'Sarabun', sans-serif !important;
    }
    
    /* Headings */
    h1, h2, h3, h4, h5, h6 {
        color: #f0f2f6 !important;
        font-family: 'Sarabun', sans-serif !important;
    }
</style>
""", unsafe_allow_html=True)
