import os
import re
from datetime import datetime, timezone
import pandas as pd
import streamlit as st
from supabase import create_client, Client

st.set_page_config(
    page_title="Student Scholarship Portal",
    page_icon="🎓",
    layout="wide",
)

# ---------- Configuration ----------
SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL", ""))
SUPABASE_KEY = st.secrets.get("SUPABASE_ANON_KEY", os.getenv("SUPABASE_ANON_KEY", ""))
SUPABASE_SERVICE_KEY = st.secrets.get("SUPABASE_SERVICE_KEY", os.getenv("SUPABASE_SERVICE_KEY", ""))
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", os.getenv("ADMIN_PASSWORD", ""))

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Supabase is not configured. Add SUPABASE_URL and SUPABASE_ANON_KEY in Streamlit Secrets.")
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
admin_supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY) if SUPABASE_SERVICE_KEY else None

# ---------- Styling ----------
st.markdown("""
<style>
.main-title {font-size: 2.3rem; font-weight: 800; margin-bottom: 0.2rem;}
.subtitle {font-size: 1.05rem; color: #666; margin-bottom: 1.5rem;}
.sch-card {
    padding: 1.2rem; border: 1px solid #ddd; border-radius: 14px;
    margin-bottom: 1rem; background: #fff;
}
.small-muted {color:#666; font-size:0.9rem;}
</style>
""", unsafe_allow_html=True)

# ---------- Helpers ----------
def valid_mobile(value: str) -> bool:
    value = re.sub(r"\s+", "", value)
    return bool(re.fullmatch(r"[6-9]\d{9}", value))

def get_scholarships():
    response = supabase.table("scholarships").select(
        "id,name,description,eligibility,deadline,apply_url,active"
    ).eq("active", True).order("id").execute()
    return response.data or []

def record_application(student_name, roll_number, branch, mobile, scholarship_id):
    payload = {
        "student_name": student_name.strip(),
        "roll_number": roll_number.strip(),
        "branch": branch.strip(),
        "mobile_number": mobile.strip(),
        "scholarship_id": scholarship_id,
        "status": "Clicked Apply",
        "applied_at": datetime.now(timezone.utc).isoformat(),
    }
    return supabase.table("scholarship_applications").insert(payload).execute()

def admin_client():
    return admin_supabase or supabase

# ---------- Header ----------
st.markdown('<div class="main-title">🎓 Student Scholarship Portal</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Find scholarships, register your details, and continue to the official application website.</div>',
    unsafe_allow_html=True
)

# ---------- Navigation ----------
page = st.radio(
    "Go to",
    ["Available Scholarships", "My Application", "Admin Dashboard"],
    horizontal=True,
    label_visibility="collapsed",
)

# ---------- Student pages ----------
if page == "Available Scholarships":
    scholarships = get_scholarships()

    if not scholarships:
        st.info("No scholarships are currently available.")
        st.stop()

    st.subheader(f"Available Scholarships ({len(scholarships)})")

    for s in scholarships:
        with st.container(border=True):
            st.markdown(f"### {s['name']}")
            if s.get("description"):
                st.write(s["description"])
            c1, c2 = st.columns([3, 1])
            with c1:
                if s.get("eligibility"):
                    st.markdown(f"**Eligibility:** {s['eligibility']}")
                if s.get("deadline"):
                    st.markdown(f"**Deadline:** {s['deadline']}")
            with c2:
                if st.button("Apply Now →", key=f"apply_{s['id']}", use_container_width=True):
                    st.session_state["selected_scholarship"] = s
                    st.session_state["show_form"] = True

    if st.session_state.get("show_form") and st.session_state.get("selected_scholarship"):
        s = st.session_state["selected_scholarship"]
        st.divider()
        st.subheader(f"Register before continuing: {s['name']}")

        with st.form("student_application_form"):
            name = st.text_input("Student Name *")
            roll = st.text_input("Roll Number / Student ID *")
            branch = st.text_input("Branch *", placeholder="CSE / ECE / EEE / MECH ...")
            mobile = st.text_input("Mobile Number *", max_chars=10)
            consent = st.checkbox(
                "I confirm that the above details are correct and allow the college scholarship portal to record this application attempt."
            )
            submitted = st.form_submit_button("Save Details & Continue to Official Website", type="primary")

        if submitted:
            errors = []
            if not name.strip():
                errors.append("Enter student name.")
            if not roll.strip():
                errors.append("Enter roll number / student ID.")
            if not branch.strip():
                errors.append("Enter branch.")
            if not valid_mobile(mobile):
                errors.append("Enter a valid 10-digit Indian mobile number.")
            if not consent:
                errors.append("Please provide consent.")

            if errors:
                for e in errors:
                    st.error(e)
            else:
                try:
                    record_application(name, roll, branch, mobile, int(s["id"]))
                    st.session_state["last_application"] = {
                        "student_name": name.strip(),
                        "roll_number": roll.strip(),
                        "branch": branch.strip(),
                        "mobile_number": mobile.strip(),
                        "scholarship_name": s["name"],
                        "apply_url": s["apply_url"],
                    }
                    st.success("Your details have been recorded successfully.")
                    st.link_button("Continue to Official Scholarship Website →", s["apply_url"], type="primary")
                    st.info("Complete the scholarship application on the official website. This portal records that you started the application through this page.")
                except Exception as e:
                    st.error(f"Unable to save your details. Please contact the scholarship coordinator. ({e})")

# ---------- Student tracking ----------
elif page == "My Application":
    st.subheader("Application Confirmation")
    data = st.session_state.get("last_application")
    if not data:
        st.info("Your current-session application confirmation will appear here after you click Apply Now and submit your details.")
    else:
        st.success("Application attempt recorded.")
        st.write(f"**Student:** {data['student_name']}")
        st.write(f"**Roll Number:** {data['roll_number']}")
        st.write(f"**Branch:** {data['branch']}")
        st.write(f"**Scholarship:** {data['scholarship_name']}")
        st.link_button("Open Official Scholarship Website →", data["apply_url"], type="primary")

# ---------- Admin ----------
else:
    st.subheader("🔐 Admin Dashboard")
    password = st.text_input("Admin Password", type="password")

    if not ADMIN_PASSWORD:
        st.warning("ADMIN_PASSWORD is not configured in Streamlit Secrets.")
        st.stop()

    if password != ADMIN_PASSWORD:
        st.info("Enter the admin password to view application records.")
        st.stop()

    db = admin_client()

    try:
        scholarships = db.table("scholarships").select("id,name,active").order("id").execute().data or []
        apps = db.table("scholarship_applications").select(
            "id,student_name,roll_number,branch,mobile_number,scholarship_id,status,applied_at"
        ).order("applied_at", desc=True).execute().data or []
    except Exception as e:
        st.error(f"Unable to load dashboard data: {e}")
        st.stop()

    sch_map = {s["id"]: s["name"] for s in scholarships}
    df = pd.DataFrame(apps)

    if df.empty:
        st.info("No application records yet.")
        st.stop()

    df["Scholarship"] = df["scholarship_id"].map(sch_map).fillna("Unknown")
    df["Applied At"] = pd.to_datetime(df["applied_at"], errors="coerce").dt.strftime("%d-%m-%Y %H:%M")
    df = df.rename(columns={
        "student_name": "Student Name",
        "roll_number": "Roll Number",
        "branch": "Branch",
        "mobile_number": "Mobile",
        "status": "Status",
    })

    # Filters
    f1, f2, f3 = st.columns(3)
    with f1:
        scholarship_filter = st.selectbox("Scholarship", ["All"] + sorted(df["Scholarship"].unique().tolist()))
    with f2:
        branch_filter = st.selectbox("Branch", ["All"] + sorted(df["Branch"].dropna().unique().tolist()))
    with f3:
        status_filter = st.selectbox("Status", ["All"] + sorted(df["Status"].dropna().unique().tolist()))

    filtered = df.copy()
    if scholarship_filter != "All":
        filtered = filtered[filtered["Scholarship"] == scholarship_filter]
    if branch_filter != "All":
        filtered = filtered[filtered["Branch"] == branch_filter]
    if status_filter != "All":
        filtered = filtered[filtered["Status"] == status_filter]

    a, b, c = st.columns(3)
    a.metric("Total Application Attempts", len(df))
    b.metric("Filtered Records", len(filtered))
    c.metric("Scholarships", len(scholarships))

    st.dataframe(
        filtered[["Student Name", "Roll Number", "Branch", "Mobile", "Scholarship", "Status", "Applied At"]],
        use_container_width=True,
        hide_index=True,
    )

    csv = filtered[["Student Name", "Roll Number", "Branch", "Mobile", "Scholarship", "Status", "Applied At"]].to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download CSV",
        csv,
        "scholarship_applications.csv",
        "text/csv",
    )

    st.divider()
    st.subheader("Scholarship List")
    sch_df = pd.DataFrame(scholarships)
    if not sch_df.empty:
        st.dataframe(sch_df, use_container_width=True, hide_index=True)
