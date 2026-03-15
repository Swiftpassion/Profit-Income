import streamlit as st
import random
import modules.otp2 as otp

def generate_otp():
    """Generates a random 6-digit OTP code."""
    return str(random.randint(100000, 999999))

def check_login():
    """Validates the password and triggers OTP sending."""
    password = st.session_state.get("password_input", "")
    if password == "Mos2025":
        # Generate and store OTP
        otp_code = generate_otp()
        st.session_state.current_otp = otp_code
        
        # Send OTP via email
        target_email = "stock02@swiftpassion.net"
        if otp.send_otp_email(target_email, otp_code):
            st.session_state.otp_step = True
            st.session_state.login_error = None
        else:
            st.session_state.login_error = "⚠️ ไม่สามารถส่ง OTP ได้ กรุณาลองใหม่"
    else:
        st.session_state.login_error = "⚠️ รหัสผ่านไม่ถูกต้อง กรุณาลองใหม่"
        st.session_state.logged_in = False

def verify_otp():
    """Validates the OTP entered by the user."""
    entered_otp = st.session_state.get("otp_input", "")
    if entered_otp == st.session_state.get("current_otp"):
        st.session_state.logged_in = True
        st.session_state.otp_step = False
        st.session_state.login_error = None
        # Remember login status in URL
        st.query_params["auth"] = "success"
    else:
        st.session_state.login_error = "⚠️ OTP ไม่ถูกต้อง กรุณาลองใหม่"

def require_auth():
    """Checks authentication status and renders login page if not logged in.
    Returns True if logged in, False otherwise.
    """
    # Check URL for persistent login
    if "auth" in st.query_params and st.query_params["auth"] == "success":
        st.session_state.logged_in = True
    elif 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if st.session_state.logged_in:
        return True

    # Render Login Page Style
    st.markdown("""
        <style>
            .stTextInput input { color: #ffffff !important; background-color: #1e1e1e !important; border: 1px solid #444 !important; border-radius: 8px !important; padding: 12px !important; font-size: 16px !important; }
            .stButton button { width: 100%; background: linear-gradient(90deg, #6c5ce7 0%, #a29bfe 100%) !important; color: white !important; border-radius: 8px !important; border: none !important; margin-top: 10px; }
            .login-header { font-size: 26px; font-weight: 700; text-align: center; color: white; margin-bottom: 5px; }
            .login-sub { font-size: 14px; text-align: center; color: #aaa; margin-bottom: 25px; }
            .custom-error { background-color: #ff4d4d20; border: 1px solid #ff4d4d; color: #ff4d4d; padding: 10px; border-radius: 8px; text-align: center; margin: 10px 0; }
        </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([2, 1.2, 2])

    with col2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        
        if not st.session_state.get("otp_step"):
            # Step 1: Password Input
            st.markdown('<div class="login-header">กรุณาใส่รหัสผ่าน</div>', unsafe_allow_html=True)
            st.markdown('<div class="login-sub">สำหรับเข้าดูหน้านี้</div>', unsafe_allow_html=True)
            
            st.text_input(
                "Password", 
                type="password", 
                key="password_input", 
                label_visibility="collapsed",
                placeholder="🔒 กรอกรหัสผ่าน..."
            )
            
            if st.session_state.get("login_error"):
                st.markdown(f'<div class="custom-error">{st.session_state.login_error}</div>', unsafe_allow_html=True)

            st.button("ถัดไป", on_click=check_login, use_container_width=True)
        else:
            # Step 2: OTP Input
            st.markdown('<div class="login-header">ยืนยัน OTP</div>', unsafe_allow_html=True)
            st.markdown('<div class="login-sub">รหัสผ่านถูกส่งไปที่ email ของคุณแล้ว</div>', unsafe_allow_html=True)
            
            st.text_input(
                "OTP Code", 
                key="otp_input", 
                label_visibility="collapsed",
                placeholder="🔢 กรอกรหัส OTP..."
            )
            
            if st.session_state.get("login_error"):
                st.markdown(f'<div class="custom-error">{st.session_state.login_error}</div>', unsafe_allow_html=True)

            st.button("ยืนยัน", on_click=verify_otp, use_container_width=True)
            
            if st.button("ย้อนกลับ", use_container_width=True):
                st.session_state.otp_step = False
                st.session_state.login_error = None
                st.rerun()

    return False
