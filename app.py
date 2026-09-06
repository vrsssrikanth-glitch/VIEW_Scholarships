import os
import re
from datetime import date, datetime

import pandas as pd
import requests
from bs4 import BeautifulSoup
import streamlit as st
import psycopg
from psycopg.rows import dict_row

# 1. Page Configuration
st.set_page_config(
    page_title="B.Tech Girl Students Scholarship Portal",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 2. Custom CSS for UI Enhancement
st.markdown(
    """
    <style>
    /* Global Page Styling */
    .stApp {
        background-color: #F8FAFC;
    }
    
    /* Header Container */
    .header-container {
        background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%);
        padding: 2.5rem 2rem;
        border-radius: 16px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }
    .header-title {
        font-size: 2.5rem;
        font-weight: 800;
        margin: 0;
        letter-spacing: -0.025em;
    }
    .header-subtitle {
        font-size: 1.1rem;
        opacity: 0.9;
        margin-top: 0.5rem;
    }

    /* Metric Cards */
    .metric-card {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 1rem 1.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }

    /* Card Badge */
    .badge-open {
        background-color: #DEF7EC;
        color: #03543F;
        font-weight: 600;
        font-size: 0.8rem;
        padding: 4px 12px;
        border-radius: 9999px;
        display: inline-block;
    }

    /* Custom Form Styling */
    div[data-testid="stForm"] {
        background-color: #FFFFFF;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        padding: 1.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Database Configuration
DATABASE_URL = st.secrets.get("DATABASE_URL", os.getenv("DATABASE_URL", ""))
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", os.getenv("ADMIN_PASSWORD", ""))

if not DATABASE_URL:
    st.error("Neon is not configured. Add DATABASE_URL to Streamlit Secrets.")
    st.stop()


def get_conn():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def fetch_all(sql, params=()):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def fetch_one(sql, params=()):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()


def execute(sql, params=(), returning=False):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            result = cur.fetchone() if returning else None
        conn.commit()
        return result


def valid_mobile(v):
    return bool(re.fullmatch(r"[6-9]\d{9}", re.sub(r"\s+", "", v or "")))


def today():
    return date.today()


def parse_deadline(v):
    if not v:
        return None
    if isinstance(v, date):
        return v
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def is_open(s):
    d = parse_deadline(s.get("deadline"))
    return bool(s.get("active")) and (d is None or d >= today())


def get_scholarships(include_expired=False):
    if include_expired:
        sql = """
            SELECT id, name, description, eligibility, documents, deadline,
                   apply_url, official_url, source_url, source_name,
                   last_verified, active
            FROM scholarships
            ORDER BY deadline NULLS LAST, id
        """
        return fetch_all(sql)

    sql = """
        SELECT id, name, description, eligibility, documents, deadline,
               apply_url, official_url, source_url, source_name,
               last_verified, active
        FROM scholarships
        WHERE active = TRUE
          AND (deadline IS NULL OR deadline >= CURRENT_DATE)
        ORDER BY deadline NULLS LAST, id
    """
    return fetch_all(sql)


def get_scholarship(scholarship_id):
    return fetch_one(
        """
        SELECT id, name, description, eligibility, documents, deadline,
               apply_url, official_url, source_url, source_name,
               last_verified, active
        FROM scholarships
        WHERE id = %s
        """,
        (scholarship_id,),
    )


def record_application(student_name, roll, branch, mobile, scholarship_id):
    return execute(
        """
        INSERT INTO scholarship_applications
            (student_name, roll_number, branch, mobile_number,
             scholarship_id, status, applied_at)
        VALUES (%s, %s, %s, %s, %s, 'Clicked Apply', NOW())
        RETURNING id
        """,
        (
            student_name.strip(),
            roll.strip(),
            branch.strip(),
            mobile.strip(),
            scholarship_id,
        ),
        returning=True,
    )


# Header Banner
st.markdown(
    """
    <div class="header-container">
        <div class="header-title">🎓 B.Tech Girl Students Scholarship Portal</div>
        <div class="header-subtitle">Find verified scholarships, detailed eligibility, and direct application links in one place.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Navigation Bar
page = st.radio(
    "Navigation",
    ["Scholarships", "My Application", "Admin Dashboard"],
    horizontal=True,
    label_visibility="collapsed",
)

st.markdown("<br>", unsafe_allow_html=True)

# Page: Scholarships
if page == "Scholarships":
    rows = get_scholarships()

    col_title, col_count = st.columns([4, 1])
    with col_title:
        st.markdown("## Available Opportunities")
    with col_count:
        st.markdown(
            f"<div class='metric-card'><b>Active Programs:</b> {len(rows)}</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    if not rows:
        st.info("No open scholarships are currently available.")
    else:
        for s in rows:
            if not is_open(s):
                continue

            d = parse_deadline(s.get("deadline"))
            deadline_str = (
                d.strftime("%d %b %Y") if d else "Official Notice"
            )

            with st.container():
                with st.expander(f"✨ **{s['name']}** (Deadline: {deadline_str})", expanded=True):
                    col_info, col_action = st.columns([3, 1])

                    with col_info:
                        st.markdown(f"**Eligibility:**\n{s.get('eligibility', 'N/A')}")
                        st.markdown(f"**Required Documents:**\n{s.get('documents', 'N/A')}")
                        st.caption(
                            f"Verified Source: {s.get('source_name') or s.get('source_url', 'Official Website')} | "
                            f"Last Verified: {s.get('last_verified', 'Recently')}"
                        )

                    with col_action:
                        st.markdown(
                            f"<span class='badge-open'>OPEN</span>",
                            unsafe_allow_html=True,
                        )
                        st.markdown("<br>", unsafe_allow_html=True)

                        # Primary action to select scholarship for details & application redirect
                        if st.button("Apply Now ➔", key=f"btn_{s['id']}", use_container_width=True, type="primary"):
                            st.session_state["selected"] = s

    # Handle Student Registration before Directing to External Site
    s = st.session_state.get("selected")
    if s and is_open(s):
        st.divider()
        st.markdown(f"### Complete Details to Apply: **{s['name']}**")

        with st.form("apply_form"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Full Name *")
                branch = st.text_input("Engineering Branch *")
            with col2:
                roll = st.text_input("Roll Number / Student ID *")
                mobile = st.text_input("Mobile Number *", max_chars=10)

            consent = st.checkbox(
                "I confirm that the details provided are accurate and consent to redirection to the official application page."
            )
            submit = st.form_submit_button("Proceed to Official Portal ➔", type="primary")

        if submit:
            errors = []
            if not name.strip():
                errors.append("Student name is required.")
            if not roll.strip():
                errors.append("Roll number is required.")
            if not branch.strip():
                errors.append("Branch is required.")
            if not valid_mobile(mobile):
                errors.append("Enter a valid 10-digit Indian mobile number.")
            if not consent:
                errors.append("Consent is required.")

            current = get_scholarship(s["id"])
            if not current or not is_open(current):
                errors.append("This scholarship deadline has expired.")

            if errors:
                for err in errors:
                    st.error(err)
            else:
                try:
                    record_application(name, roll, branch, mobile, int(s["id"]))
                    st.session_state["last_application"] = {
                        "student_name": name.strip(),
                        "roll_number": roll.strip(),
                        "branch": branch.strip(),
                        "scholarship_name": current["name"],
                        "apply_url": current["apply_url"],
                    }
                    st.success("Details saved successfully! Redirecting...")
                    st.link_button(
                        "Click Here if Not Automatically Redirected ➔",
                        current["apply_url"],
                        type="primary",
                        use_container_width=True,
                    )
                    st.session_state.pop("selected", None)
                except Exception as e:
                    st.error(f"Error saving application: {e}")

# Page: My Application Confirmation
elif page == "My Application":
    st.markdown("## Application Confirmation")
    data = st.session_state.get("last_application")

    if not data:
        st.info("No recent application attempts found in this session.")
    else:
        st.success("Application attempt tracked.")
        st.markdown(
            f"""
            **Student Name:** {data['student_name']}  
            **Roll Number:** {data['roll_number']}  
            **Branch:** {data['branch']}  
            **Scholarship Program:** {data['scholarship_name']}  
            """
        )
        st.link_button(
            "Go to Official Application Portal ➔",
            data["apply_url"],
            type="primary",
        )

# Page: Admin Dashboard
else:
    st.markdown("## 🔐 Admin Dashboard")
    password = st.text_input("Admin Access Password", type="password")

    if not ADMIN_PASSWORD:
        st.warning("Set ADMIN_PASSWORD in Streamlit Secrets.")
        st.stop()
    if password != ADMIN_PASSWORD:
        st.info("Please enter the administrator password.")
        st.stop()

    tab1, tab2 = st.tabs(["Manage Scholarships", "Application Logs"])

    with tab1:
        st.markdown("### Add New Scholarship Listing")
        with st.form("add_scholarship_form"):
            name = st.text_input("Scholarship Name *")
            eligibility = st.text_area("Detailed Eligibility *")
            documents = st.text_area("Required Documents *")
            deadline = st.date_input("Deadline", value=today())
            apply_url = st.text_input("Exact Direct Application URL *")
            source_url = st.text_input("Official Announcement URL *")
            source_name = st.text_input("Source Organization Name")
            active = st.checkbox("Publish Listing Immediately", value=True)
            save = st.form_submit_button("Publish Scholarship")

        if save:
            if not name.strip() or not eligibility.strip() or not apply_url.strip():
                st.error("Please fill in all mandatory fields.")
            else:
                execute(
                    """
                    INSERT INTO scholarships
                        (name, eligibility, documents, deadline, apply_url,
                         official_url, source_url, source_name,
                         last_verified, active, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    """,
                    (
                        name.strip(),
                        eligibility.strip(),
                        documents.strip(),
                        deadline,
                        apply_url.strip(),
                        source_url.strip(),
                        source_url.strip(),
                        source_name.strip(),
                        today(),
                        active,
                    ),
                )
                st.success("Scholarship published successfully.")
                st.rerun()

    with tab2:
        apps = fetch_all(
            """
            SELECT a.id, a.student_name, a.roll_number, a.branch,
                   a.mobile_number, COALESCE(s.name, 'Unknown') AS scholarship,
                   a.applied_at
            FROM scholarship_applications a
            LEFT JOIN scholarships s ON s.id = a.scholarship_id
            ORDER BY a.applied_at DESC
            """
        )
        if apps:
            st.dataframe(pd.DataFrame(apps), use_container_width=True, hide_index=True)
        else:
            st.info("No student applications logged yet.")
