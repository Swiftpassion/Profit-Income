import smtplib
import streamlit as st
from email.message import EmailMessage

def send_otp_email(to_email, otp_code):
    """Sends an OTP email using Gmail SMTP and App Password."""
    
    # Get credentials from st.secrets under [gmail] section
    gmail_secrets = st.secrets.get("gmail", {})
    sender_email = gmail_secrets.get("google_email")
    app_password = gmail_secrets.get("google_app_password")

    if not sender_email or not app_password:
        st.error("⚠️ Error: Missing 'google_email' or 'google_app_password' in [gmail] section of secrets.toml")
        return False

    msg = EmailMessage()
    msg.set_content(f"Your Login OTP code is: {otp_code}")
    msg["Subject"] = "Your Login OTP"
    msg["From"] = sender_email
    msg["To"] = to_email

    try:
        # Use standard SMTP with TLS
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, app_password)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Error sending email: {e}")
        return False
