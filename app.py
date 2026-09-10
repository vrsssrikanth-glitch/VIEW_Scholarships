import os
import re
from datetime import date, datetime

import pandas as pd
import psycopg
from psycopg.rows import dict_row
import streamlit as st
import streamlit.components.v1 as components

# 1. Page Configuration
st.set_page_config(
    page_title="VIEW - Scholarship Portal",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 2. Adaptive Custom CSS (Supports Light & Dark Themes)
st.markdown(
    """
    <style>
    /* Use CSS variables to adapt automatically to light/dark theme */
    .header-container {
        background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%);
        padding: 2rem;
        border-radius: 16px;
        color: white;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .header-title {
        font-size: 2rem;
        font-weight: 800;
        margin: 0;
    }
    .header-subtitle {
        font-size: 0.95rem;
        opacity: 0.9;
        margin-top: 0.5rem;
    }
    .badge-open {
        background-color: #059669;
        color: #ffffff;
        font-weight: 600;
        font-size: 0.75rem;
        padding: 4px 12px;
        border-radius: 9999px;
        display: inline-block;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Database Setup
DATABASE_URL = st.secrets.get("DATABASE_URL", os.getenv("DATABASE_URL", ""))
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", os.getenv("ADMIN_PASSWORD", ""))

if not DATABASE_URL:
    st.error("DATABASE_URL is not configured.")
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


def is_already_applied(roll_number, scholarship_id):
    res = fetch_one(
        """
        SELECT id FROM scholarship_applications 
        WHERE roll_number = %s AND scholarship_id = %s
    """,
        (roll_number, scholarship_id),
    )
    return res is not None


# Banner Header
st.markdown(
    """
    <div class="header-container">
        <div class="header-title">🎓 Vignan's Institute of Engineering for Women</div>
        <div class="header-subtitle">Verified Scholarship Portal — Sign in once, apply seamlessly.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Top Bar Authentication Status
if "student" not in st.session_state:
    st.session_state["student"] = None

col_nav, col_user = st.columns([3, 1])

with col_user:
    if st.session_state["student"]:
        st.write(f"👤 **{st.session_state['student']['name']}**")
        if st.button("Sign Out", key="logout_btn"):
            st.session_state["student"] = None
            st.rerun()

with col_nav:
    page = st.radio(
        "Navigation",
        ["Home & Opportunities", "My Applications", "Admin Dashboard"],
        horizontal=True,
        label_visibility="collapsed",
    )

st.divider()

# PAGE 1: HOME & OPPORTUNITIES
if page == "Home & Opportunities":

    # Step 1: Student Details / Registration Form if not signed in
    if not st.session_state["student"]:
        st.subheader("🔑 Student Sign-In / Profile Setup")
        st.info(
            "Please enter your student details to view and apply for available scholarships."
        )

        with st.form("student_login_form"):
            col1, col2 = st.columns(2)
            with col1:
                s_name = st.text_input("Full Name *")
                s_branch = st.text_input("Engineering Branch *")
            with col2:
                s_roll = st.text_input("Roll Number / Student ID *")
                s_mobile = st.text_input("Mobile Number *", max_chars=10)

            login_submit = st.form_submit_button(
                "Save & Continue ➔", type="primary"
            )

        if login_submit:
            if (
                not s_name.strip()
                or not s_roll.strip()
                or not s_branch.strip()
            ):
                st.error("All mandatory fields are required.")
            elif not valid_mobile(s_mobile):
                st.error("Enter a valid 10-digit mobile number.")
            else:
                st.session_state["student"] = {
                    "name": s_name.strip(),
                    "roll": s_roll.strip().upper(),
                    "branch": s_branch.strip(),
                    "mobile": s_mobile.strip(),
                }
                st.success("Profile active!")
                st.rerun()

    # Step 2: Show Opportunities once signed in
    else:
        st.warning(
            "⚠️ **IMPORTANT NOTE:** Please wait to apply for NSP Scholarships until you get your original roll numbers."
        )

        scholarships = fetch_all(
            """
            SELECT id, name, eligibility, documents, deadline, apply_url 
            FROM scholarships 
            WHERE active = TRUE AND (deadline IS NULL OR deadline >= CURRENT_DATE)
            ORDER BY deadline NULLS LAST, id
        """
        )

        st.subheader(f"Available Opportunities ({len(scholarships)})")

        student = st.session_state["student"]

        for s in scholarships:
            already_enrolled = is_already_applied(student["roll"], s["id"])

            with st.expander(
                f"✨ **{s['name']}** - Deadline: {s['deadline'] or 'N/A'}"
            ):
                c_info, c_action = st.columns([3, 1])

                with c_info:
                    st.markdown(f"**Eligibility:** {s['eligibility']}")
                    st.markdown(f"**Required Documents:** {s['documents']}")

                with c_action:
                    if already_enrolled:
                        st.success("✅ Already Enrolled")
                        st.link_button(
                            "Open Application Portal ➔",
                            s["apply_url"],
                            use_container_width=True,
                        )
                    else:
                        if st.button(
                            "Apply Now ➔",
                            key=f"apply_{s['id']}",
                            type="primary",
                            use_container_width=True,
                        ):
                            # Auto-record application without asking for profile again
                            execute(
                                """
                                INSERT INTO scholarship_applications 
                                (student_name, roll_number, branch, mobile_number, scholarship_id, status, applied_at)
                                VALUES (%s, %s, %s, %s, %s, 'Applied', NOW())
                            """,
                                (
                                    student["name"],
                                    student["roll"],
                                    student["branch"],
                                    student["mobile"],
                                    s["id"],
                                ),
                            )
                            st.success(
                                "Enrolled successfully! Redirecting..."
                            )
                            components.html(
                                f'<script>window.open("{s["apply_url"]}", "_blank");</script>',
                                height=0,
                            )
                            st.rerun()

# PAGE 2: MY APPLICATIONS
elif page == "My Applications":
    st.subheader("📋 My Submitted Applications")

    if not st.session_state["student"]:
        st.info(
            "Please sign in on the Home page to view your active applications."
        )
    else:
        roll = st.session_state["student"]["roll"]
        user_apps = fetch_all(
            """
            SELECT s.name AS scholarship_name, s.apply_url, a.applied_at, a.status
            FROM scholarship_applications a
            JOIN scholarships s ON s.id = a.scholarship_id
            WHERE a.roll_number = %s
            ORDER BY a.applied_at DESC
        """,
            (roll,),
        )

        if not user_apps:
            st.info("You haven't applied to any scholarships yet.")
        else:
            for item in user_apps:
                with st.container():
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        st.markdown(f"### {item['scholarship_name']}")
                        st.caption(
                            f"Applied on: {item['applied_at'].strftime('%Y-%m-%d %H:%M')}"
                        )
                    with col_b:
                        st.link_button(
                            "Revisit Portal ➔",
                            item["apply_url"],
                            use_container_width=True,
                        )
                    st.divider()

# PAGE 3: ADMIN DASHBOARD
else:
    st.subheader("🔐 Admin Dashboard")
    pwd = st.text_input("Enter Admin Password", type="password")

    if pwd == ADMIN_PASSWORD and ADMIN_PASSWORD != "":
        st.success("Authenticated")
        logs = fetch_all(
            """
            SELECT a.id, a.student_name, a.roll_number, a.branch, a.mobile_number, 
                   s.name as scholarship, a.applied_at
            FROM scholarship_applications a
            LEFT JOIN scholarships s ON s.id = a.scholarship_id
            ORDER BY a.applied_at DESC
        """
        )
        if logs:
            st.dataframe(pd.DataFrame(logs), use_container_width=True)
        else:
            st.info("No applications logged yet.")
    elif pwd:
        st.error("Invalid administrator password.")
