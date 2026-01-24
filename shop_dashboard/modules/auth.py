import streamlit as st

def check_login():
    """Validates the password and updates session state."""
    password = st.session_state.get("password_input", "")
    if password == "Mos2025":
        st.session_state.logged_in = True
        st.session_state.login_error = None
        # Remember login status in URL
        st.query_params["auth"] = "success"
    else:
        st.session_state.login_error = "⚠️ รหัสผ่านไม่ถูกต้อง กรุณาลองใหม่"
        st.session_state.logged_in = False

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

    # Render Login Page
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

        st.button("เข้าสู่ระบบ", on_click=check_login, use_container_width=True)

    return False
