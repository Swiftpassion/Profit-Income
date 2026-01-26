import streamlit as st
import json
import hashlib
import random
import string
import smtplib
from datetime import date, datetime
from email.mime.text import MIMEText
from google.oauth2 import service_account
import gspread
from config import MASTER_SHEET_ID

@st.cache_resource
def get_credentials():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    if "gcp_service_account" in st.secrets:
        creds_dict = json.loads(st.secrets["gcp_service_account"]) if isinstance(st.secrets["gcp_service_account"], str) else dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        return service_account.Credentials.from_service_account_info(creds_dict, scopes=scope)
    return service_account.Credentials.from_service_account_file("credentials.json", scopes=scope)

def create_token(email):
    salt = "jst_secret_salt" 
    raw = f"{email}{salt}{date.today()}"
    return hashlib.md5(raw.encode()).hexdigest()

def send_otp_email(receiver_email, otp_code):
    try:
        sender_email = st.secrets["email"]["sender"]
        sender_password = st.secrets["email"]["password"]
    except KeyError:
        st.error("❌ ไม่พบการตั้งค่า Email ใน st.secrets")
        return False
    
    subject = "รหัสยืนยันตัวตน (OTP) - JST Hybrid System"
    body = f"รหัสเข้าใช้งานของคุณคือ: {otp_code}\n\n(รหัสนี้ใช้สำหรับการเข้าสู่ระบบครั้งนี้เท่านั้น)"

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = receiver_email

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, receiver_email, msg.as_string())
        return True
    except Exception as e:
        st.error(f"❌ ส่งอีเมลไม่สำเร็จ: {e}")
        return False

def log_login_activity(email):
    try:
        creds = get_credentials()
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(MASTER_SHEET_ID)
        try: ws = sh.worksheet("LOGIN_LOG")
        except:
            ws = sh.add_worksheet(title="LOGIN_LOG", rows="1000", cols="2")
            ws.append_row(["Timestamp", "Email"])
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ws.append_row([timestamp, email])
    except Exception as e:
        print(f"Login Log Error: {e}")
