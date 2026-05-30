import streamlit as st
import sqlite3
import bcrypt
import pandas as pd
import re
from datetime import datetime

DB_NAME = "users.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    c.execute("SELECT id FROM users WHERE username = ?", ("super_admin",))
    if not c.fetchone():
        hashed = bcrypt.hashpw("SuperAdmin123!".encode(), bcrypt.gensalt()).decode()
        c.execute(
            "INSERT INTO users (username, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)",
            ("super_admin", "superadmin@system.local", hashed, "super_admin", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
    conn.close()

def analyze_password(password):
    score = 0
    suggestions = []
    if len(password) >= 8:
        score += 1
    else:
        suggestions.append("Use at least 8 characters")
    if re.search(r"[A-Z]", password):
        score += 1
    else:
        suggestions.append("Add at least one uppercase letter")
    if re.search(r"[a-z]", password):
        score += 1
    else:
        suggestions.append("Add at least one lowercase letter")
    if re.search(r"\d", password):
        score += 1
    else:
        suggestions.append("Add at least one number")
    if re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        score += 1
    else:
        suggestions.append("Add at least one special character (!@#$%^&*...)")
    if score <= 2:
        strength = "Weak"
    elif score == 3 or score == 4:
        strength = "Medium"
    else:
        strength = "Strong"
    return strength, suggestions

def register_user(username, email, password, role="user"):
    conn = get_connection()
    c = conn.cursor()
    try:
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        c.execute(
            "INSERT INTO users (username, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (username.strip(), email.strip().lower(), hashed, role, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        return True, "Account created successfully."
    except sqlite3.IntegrityError as e:
        if "username" in str(e):
            return False, "Username already exists."
        elif "email" in str(e):
            return False, "Email already registered."
        return False, "Registration failed."
    finally:
        conn.close()

def authenticate_user(username, password):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ?", (username.strip(),))
    user = c.fetchone()
    conn.close()
    if user and bcrypt.checkpw(password.encode(), user["password"].encode()):
        return dict(user)
    return None

def get_all_users():
    conn = get_connection()
    df = pd.read_sql_query("SELECT id, username, email, role, created_at FROM users ORDER BY created_at DESC", conn)
    conn.close()
    return df

def get_user_count():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
    admins = c.fetchone()[0]
    conn.close()
    return total, admins

def delete_user(username, acting_role, acting_username):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False, "User not found."
    target_role = row["role"]
    if username == acting_username:
        conn.close()
        return False, "You cannot delete your own account."
    if target_role == "super_admin":
        conn.close()
        return False, "Super Admin cannot be deleted."
    if acting_role == "admin" and target_role != "user":
        conn.close()
        return False, "Admins can only delete normal users."
    c.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    return True, f"User '{username}' has been deleted."

def promote_user(username, acting_username):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False, "User not found."
    if row["role"] != "user":
        conn.close()
        return False, "Only users with the 'user' role can be promoted to Admin."
    if username == acting_username:
        conn.close()
        return False, "You cannot modify your own account."
    c.execute("UPDATE users SET role = 'admin' WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    return True, f"'{username}' has been promoted to Admin."

def demote_admin(username, acting_username):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False, "User not found."
    if row["role"] == "super_admin":
        conn.close()
        return False, "Super Admin cannot be demoted."
    if row["role"] != "admin":
        conn.close()
        return False, "Only Admins can be demoted."
    if username == acting_username:
        conn.close()
        return False, "You cannot modify your own account."
    c.execute("UPDATE users SET role = 'user' WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    return True, f"'{username}' has been demoted to User."

def logout():
    for key in ["logged_in", "username", "role", "email"]:
        st.session_state.pop(key, None)
    st.session_state["page"] = "login"

def render_login():
    st.markdown("<h2 style='text-align:center; letter-spacing:0.04em;'>Secure Login</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#8b949e;'>Enter your credentials to access the system.</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In", use_container_width=True)
        if submitted:
            if not username or not password:
                st.error("Please fill in all fields.")
            else:
                user = authenticate_user(username, password)
                if user:
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = user["username"]
                    st.session_state["role"] = user["role"]
                    st.session_state["email"] = user["email"]
                    st.session_state["page"] = "dashboard"
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
    st.markdown("---")
    st.markdown("<p style='text-align:center; color:#8b949e;'>Don't have an account?</p>", unsafe_allow_html=True)
    if st.button("Create an Account", use_container_width=True):
        st.session_state["page"] = "register"
        st.rerun()

def render_register():
    st.markdown("<h2 style='text-align:center; letter-spacing:0.04em;'>Create Account</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#8b949e;'>Register to access the secure system.</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    with st.form("register_form"):
        username = st.text_input("Username")
        email = st.text_input("Email Address")
        password = st.text_input("Password", type="password")
        strength_placeholder = st.empty()
        confirm_password = st.text_input("Confirm Password", type="password")
        submitted = st.form_submit_button("Register", use_container_width=True)
        if password:
            strength, suggestions = analyze_password(password)
            color = {"Weak": "#e74c3c", "Medium": "#f0a500", "Strong": "#2ecc71"}.get(strength, "#aaa")
            strength_placeholder.markdown(
                f"<p style='margin:4px 0;'><b>Password Strength:</b> <span style='color:{color}; font-weight:600;'>{strength}</span></p>"
                + ("".join(f"<p style='margin:2px 0; color:#8b949e; font-size:0.85rem;'>— {s}</p>" for s in suggestions)),
                unsafe_allow_html=True
            )
        if submitted:
            if not username or not email or not password or not confirm_password:
                st.error("All fields are required.")
            elif not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
                st.error("Please enter a valid email address.")
            elif password != confirm_password:
                st.error("Passwords do not match. Please try again.")
            else:
                strength, suggestions = analyze_password(password)
                if strength == "Weak":
                    st.error("Password is too weak. Please address the following:\n" + "\n".join(f"  - {s}" for s in suggestions))
                else:
                    ok, msg = register_user(username, email, password)
                    if ok:
                        st.success(f"{msg} You may now sign in.")
                    else:
                        st.error(msg)
    st.markdown("---")
    if st.button("Back to Login", use_container_width=True):
        st.session_state["page"] = "login"
        st.rerun()

def render_user_dashboard():
    st.markdown(f"<h2>Welcome, {st.session_state['username']}</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color:#8b949e;'>Your account overview</p>", unsafe_allow_html=True)
    st.markdown("---")
    username = st.session_state["username"]
    email = st.session_state["email"]
    role = st.session_state["role"].replace("_", " ").title()
    st.markdown(f"""
    <div style='display:flex; gap:16px; margin-bottom:8px;'>
        <div style='flex:1; background:#161b22; border:1px solid #30363d; border-radius:8px; padding:16px 20px;'>
            <p style='margin:0 0 6px 0; color:#8b949e; font-size:0.82rem; font-weight:500; text-transform:uppercase; letter-spacing:0.06em;'>Username</p>
            <p style='margin:0; color:#e6edf3; font-size:1.35rem; font-weight:700; word-break:break-all;'>{username}</p>
        </div>
        <div style='flex:2; background:#161b22; border:1px solid #30363d; border-radius:8px; padding:16px 20px;'>
            <p style='margin:0 0 6px 0; color:#8b949e; font-size:0.82rem; font-weight:500; text-transform:uppercase; letter-spacing:0.06em;'>Email Address</p>
            <p style='margin:0; color:#e6edf3; font-size:1.05rem; font-weight:700; overflow-wrap:break-word; word-break:break-word; white-space:normal;'>{email}</p>
        </div>
        <div style='flex:1; background:#161b22; border:1px solid #30363d; border-radius:8px; padding:16px 20px;'>
            <p style='margin:0 0 6px 0; color:#8b949e; font-size:0.82rem; font-weight:500; text-transform:uppercase; letter-spacing:0.06em;'>Role</p>
            <p style='margin:0; color:#e6edf3; font-size:1.35rem; font-weight:700;'>{role}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")
    st.info("You are logged in as a standard user. You can only view your own account information.")
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Sign Out", use_container_width=True):
        logout()
        st.rerun()

def render_admin_dashboard():
    st.markdown("<h2>Admin Dashboard</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color:#8b949e;'>Manage system users and review account data.</p>", unsafe_allow_html=True)
    st.markdown("---")
    total, admins = get_user_count()
    col1, col2 = st.columns(2)
    col1.metric("Total Registered Users", total)
    col2.metric("Total Admins", admins)
    st.markdown("---")
    st.subheader("User Directory")
    df = get_all_users()
    search = st.text_input("Search by username or email")
    role_filter = st.selectbox("Filter by Role", ["All", "user", "admin", "super_admin"])
    if search:
        df = df[df["username"].str.contains(search, case=False) | df["email"].str.contains(search, case=False)]
    if role_filter != "All":
        df = df[df["role"] == role_filter]
    st.dataframe(df, use_container_width=True)
    st.markdown("---")
    st.subheader("Remove User")
    normal_users = get_all_users()
    normal_users = normal_users[
        (normal_users["role"] == "user") &
        (normal_users["username"] != st.session_state["username"])
    ]["username"].tolist()
    if normal_users:
        del_target = st.selectbox("Select a user to remove", normal_users)
        if st.button("Remove Selected User", use_container_width=True):
            ok, msg = delete_user(del_target, st.session_state["role"], st.session_state["username"])
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
    else:
        st.info("No removable users found.")
    st.markdown("---")
    if st.button("Sign Out", use_container_width=True):
        logout()
        st.rerun()

def render_super_admin_dashboard():
    st.markdown("<h2>Super Admin Dashboard</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color:#8b949e;'>Full system control — manage roles, users, and access privileges.</p>", unsafe_allow_html=True)
    st.markdown("---")
    total, admins = get_user_count()
    col1, col2 = st.columns(2)
    col1.metric("Total Registered Users", total)
    col2.metric("Total Admins", admins)
    st.markdown("---")
    st.subheader("User Directory")
    df = get_all_users()
    search = st.text_input("Search by username or email")
    role_filter = st.selectbox("Filter by Role", ["All", "user", "admin", "super_admin"])
    filtered = df.copy()
    if search:
        filtered = filtered[filtered["username"].str.contains(search, case=False) | filtered["email"].str.contains(search, case=False)]
    if role_filter != "All":
        filtered = filtered[filtered["role"] == role_filter]
    st.dataframe(filtered, use_container_width=True)
    st.markdown("---")
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Promote User to Admin")
        promotable = df[
            (df["role"] == "user") &
            (df["username"] != st.session_state["username"])
        ]["username"].tolist()
        if promotable:
            promo_target = st.selectbox("Select user to promote", promotable, key="promo")
            if st.button("Promote to Admin", use_container_width=True):
                ok, msg = promote_user(promo_target, st.session_state["username"])
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        else:
            st.info("No users available for promotion.")
    with col_b:
        st.subheader("Demote Admin to User")
        demotable = df[
            (df["role"] == "admin") &
            (df["username"] != st.session_state["username"])
        ]["username"].tolist()
        if demotable:
            demo_target = st.selectbox("Select admin to demote", demotable, key="demo")
            if st.button("Demote to User", use_container_width=True):
                ok, msg = demote_admin(demo_target, st.session_state["username"])
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        else:
            st.info("No admins available for demotion.")
    st.markdown("---")
    st.subheader("Remove Account")
    deletable = df[
        (df["role"].isin(["user", "admin"])) &
        (df["username"] != st.session_state["username"])
    ]["username"].tolist()
    if deletable:
        del_target = st.selectbox("Select account to remove", deletable, key="del")
        if st.button("Remove Selected Account", use_container_width=True):
            ok, msg = delete_user(del_target, st.session_state["role"], st.session_state["username"])
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
    else:
        st.info("No removable accounts found.")
    st.markdown("---")
    if st.button("Sign Out", use_container_width=True):
        logout()
        st.rerun()

def main():
    st.set_page_config(
        page_title="RBAC Secure Auth System",
        page_icon=None,
        layout="centered",
        initial_sidebar_state="collapsed"
    )
    st.markdown("""
    <style>
    body, .stApp { background-color: #0d1117; color: #c9d1d9; font-family: 'Segoe UI', system-ui, sans-serif; }
    .stTextInput > div > div > input {
        background-color: #161b22;
        color: #c9d1d9;
        border: 1px solid #30363d;
        border-radius: 6px;
    }
    .stButton > button {
        background-color: #1f6feb;
        color: white;
        border: none;
        border-radius: 6px;
        font-weight: 600;
        letter-spacing: 0.03em;
        padding: 0.5rem 1rem;
        transition: background-color 0.2s;
    }
    .stButton > button:hover { background-color: #388bfd; }
    .stSelectbox > div > div { background-color: #161b22; color: #c9d1d9; }
    .stDataFrame { background-color: #161b22; }
    .stMetric {
        background-color: #161b22;
        border-radius: 8px;
        padding: 14px 18px;
        border: 1px solid #30363d;
    }
    h1, h2, h3 { color: #e6edf3; font-weight: 700; letter-spacing: 0.02em; }
    h2 { font-size: 1.6rem; }
    h3 { font-size: 1.15rem; color: #8b949e; }
    .stForm { background-color: #161b22; padding: 24px; border-radius: 10px; border: 1px solid #30363d; }
    hr { border-color: #21262d; }
    p { color: #c9d1d9; }
    </style>
    """, unsafe_allow_html=True)

    init_db()

    if "page" not in st.session_state:
        st.session_state["page"] = "login"
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    st.markdown("<h1 style='text-align:center; font-size:1.9rem; letter-spacing:0.05em;'>RBAC Secure Authentication System</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#8b949e; font-size:0.9rem;'>Role-Based Access Control &nbsp;|&nbsp; bcrypt Encryption &nbsp;|&nbsp; SQLite</p>", unsafe_allow_html=True)
    st.markdown("---")

    if st.session_state["logged_in"]:
        role = st.session_state.get("role")
        if role == "super_admin":
            render_super_admin_dashboard()
        elif role == "admin":
            render_admin_dashboard()
        else:
            render_user_dashboard()
    else:
        if st.session_state["page"] == "register":
            render_register()
        else:
            render_login()

if __name__ == "__main__":
    main()
