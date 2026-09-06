import os
import re
from datetime import date, datetime, timezone

import pandas as pd
import requests
from bs4 import BeautifulSoup
import streamlit as st
import psycopg
from psycopg.rows import dict_row

st.set_page_config(
    page_title="B.Tech Girl Students Scholarship Portal",
    page_icon="🎓",
    layout="wide",
)

# =============================================================
# Neon PostgreSQL configuration
# =============================================================
DATABASE_URL = st.secrets.get("DATABASE_URL", os.getenv("DATABASE_URL", ""))
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", os.getenv("ADMIN_PASSWORD", ""))

if not DATABASE_URL:
    st.error("Neon is not configured. Add DATABASE_URL to Streamlit Secrets.")
    st.stop()


def get_conn():
    # Neon connection strings normally contain sslmode=require.
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


# =============================================================
# Helpers
# =============================================================
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
    # Deadline is checked in SQL as well as Python. This makes the public
    # scholarship list safe even if an admin forgets to deactivate a row.
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


def fetch_webpage(url):
    r = requests.get(
        url,
        timeout=20,
        headers={"User-Agent": "ScholarshipPortalBot/1.0 (+admin verification)"},
    )
    r.raise_for_status()
    return r.text, r.url


def extract_page_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True))


def collect_source_preview(url):
    html, final_url = fetch_webpage(url)
    text = extract_page_text(html)
    return final_url, text[:12000]


# =============================================================
# Styling / Header
# =============================================================
st.markdown(
    """
    <style>
    .main-title {font-size: 2.3rem; font-weight: 800; margin-bottom: 0.2rem;}
    .subtitle {font-size: 1.05rem; color: #666; margin-bottom: 1.5rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="main-title">🎓 B.Tech Girl Students Scholarship Portal</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="subtitle">Scholarship name • detailed eligibility • required documents • deadline • official link</div>',
    unsafe_allow_html=True,
)

page = st.radio(
    "Go to",
    ["Scholarships", "My Application", "Admin Dashboard"],
    horizontal=True,
    label_visibility="collapsed",
)

# =============================================================
# Student: scholarships
# =============================================================
if page == "Scholarships":
    rows = get_scholarships()
    st.subheader(f"Open scholarships ({len(rows)})")

    if not rows:
        st.info("No open scholarships are currently available.")
    else:
        table = []
        for s in rows:
            d = parse_deadline(s.get("deadline"))
            table.append(
                {
                    "Scholarship Name": s["name"],
                    "Eligibility": s.get("eligibility", ""),
                    "Required Documents": s.get("documents", ""),
                    "Last Date": d.strftime("%d-%m-%Y") if d else "See official notice",
                    "Status": "OPEN" if is_open(s) else "CLOSED",
                }
            )
        st.dataframe(
            pd.DataFrame(table), use_container_width=True, hide_index=True, height=420
        )

        st.divider()
        st.subheader("Apply")
        for s in rows:
            if not is_open(s):
                continue
            d = parse_deadline(s.get("deadline"))
            with st.container(border=True):
                st.markdown(f"### {s['name']}")
                st.write(f"**Eligibility:** {s.get('eligibility', '')}")
                st.write(f"**Required documents:** {s.get('documents', '')}")
                st.write(
                    f"**Last date:** {d.strftime('%d-%m-%Y') if d else 'See official notice'}"
                )
                st.caption(
                    f"Source: {s.get('source_name') or s.get('source_url', '')} | "
                    f"Last verified: {s.get('last_verified', 'Not recorded')}"
                )
                if st.button("Apply Now →", key=f"apply_{s['id']}", type="primary"):
                    st.session_state["selected"] = s

    s = st.session_state.get("selected")
    if s and is_open(s):
        st.divider()
        st.subheader(f"Record application attempt: {s['name']}")
        with st.form("apply_form"):
            name = st.text_input("Student Name *")
            roll = st.text_input("Roll Number / Student ID *")
            branch = st.text_input("Branch *")
            mobile = st.text_input("Mobile Number *", max_chars=10)
            consent = st.checkbox(
                "I consent to recording these details for scholarship application tracking."
            )
            submit = st.form_submit_button("Save Details & Continue", type="primary")

        if submit:
            errors = []
            if not name.strip():
                errors.append("Student name is required.")
            if not roll.strip():
                errors.append("Roll number / Student ID is required.")
            if not branch.strip():
                errors.append("Branch is required.")
            if not valid_mobile(mobile):
                errors.append("Enter a valid 10-digit Indian mobile number.")
            if not consent:
                errors.append("Consent is required.")

            # Re-read from Neon immediately before saving, so a page left open
            # overnight cannot create a new application for an expired scholarship.
            current = get_scholarship(s["id"])
            if not current or not is_open(current):
                errors.append(
                    "This scholarship has closed. The application link has been disabled."
                )

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
                        "scholarship_name": current["name"],
                        "apply_url": current["apply_url"],
                    }
                    st.success("Application attempt recorded.")
                    st.link_button(
                        "Continue to official scholarship website →",
                        current["apply_url"],
                        type="primary",
                    )
                    st.session_state.pop("selected", None)
                except Exception as e:
                    st.error(f"Unable to save details: {e}")

# =============================================================
# Student: confirmation
# =============================================================
elif page == "My Application":
    st.subheader("Application Confirmation")
    data = st.session_state.get("last_application")
    if not data:
        st.info(
            "This portal records the student's attempt to start an application. "
            "It does not confirm that the external scholarship form was submitted."
        )
    else:
        st.success("Application attempt recorded.")
        st.write(f"**Student:** {data['student_name']}")
        st.write(f"**Roll Number:** {data['roll_number']}")
        st.write(f"**Branch:** {data['branch']}")
        st.write(f"**Scholarship:** {data['scholarship_name']}")
        current = get_scholarship_by_url = None
        if st.button("Refresh scholarship status"):
            st.rerun()
        # Never keep an expired external link active in the confirmation page.
        open_rows = get_scholarships()
        open_match = next(
            (x for x in open_rows if x["name"] == data["scholarship_name"]), None
        )
        if open_match:
            st.link_button(
                "Open Official Scholarship Website →",
                open_match["apply_url"],
                type="primary",
            )
        else:
            st.warning("The scholarship deadline has passed; its application link is disabled.")

# =============================================================
# Admin
# =============================================================
else:
    st.subheader("🔐 Admin Dashboard")
    password = st.text_input("Admin Password", type="password")

    if not ADMIN_PASSWORD:
        st.warning("Set ADMIN_PASSWORD in Streamlit Secrets.")
        st.stop()
    if password != ADMIN_PASSWORD:
        st.info("Enter the admin password.")
        st.stop()

    tab1, tab2, tab3 = st.tabs(["Scholarships", "Source Collector", "Applications"])

    with tab1:
        all_rows = fetch_all(
            """
            SELECT id, name, eligibility, documents, deadline, apply_url,
                   official_url, source_url, source_name, last_verified, active
            FROM scholarships
            ORDER BY deadline NULLS LAST, id
            """
        )
        df = pd.DataFrame(all_rows)
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)

        st.markdown("### Add scholarship")
        with st.form("scholarship_editor"):
            name = st.text_input("Scholarship name *")
            eligibility = st.text_area("Eligibility in detail *")
            documents = st.text_area("Required documents")
            deadline = st.date_input("Last date to apply", value=today())
            apply_url = st.text_input("Scholarship application link *")
            official_url = st.text_input("Official information page")
            source_url = st.text_input("Source webpage used for verification *")
            source_name = st.text_input("Source name")
            active = st.checkbox("Publish / make visible", value=True)
            save = st.form_submit_button("Save Scholarship")

        if save:
            if not name.strip() or not eligibility.strip() or not apply_url.strip() or not source_url.strip():
                st.error("Name, eligibility, application link and source URL are required.")
            else:
                try:
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
                            official_url.strip(),
                            source_url.strip(),
                            source_name.strip(),
                            today(),
                            active,
                        ),
                    )
                    st.success(
                        "Scholarship saved. It will stop appearing and its link will be disabled after the deadline."
                    )
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    with tab2:
        st.write(
            "Enter an official scholarship webpage. The portal fetches the page so the admin can review it."
        )
        st.warning(
            "Do not auto-publish scraped text. Eligibility and deadlines can change or be hidden in PDFs/JavaScript. Verify the official notice before publishing."
        )
        source = st.text_input("Official scholarship webpage URL")
        if st.button("Fetch webpage"):
            if not source.strip():
                st.error("Enter a webpage URL.")
            else:
                try:
                    final_url, text = collect_source_preview(source.strip())
                    st.success(f"Fetched: {final_url}")
                    st.text_area("Page text for verification", text, height=450)
                except Exception as e:
                    st.error(f"Unable to fetch page: {e}")

    with tab3:
        apps = fetch_all(
            """
            SELECT a.id, a.student_name, a.roll_number, a.branch,
                   a.mobile_number, a.scholarship_id,
                   COALESCE(s.name, 'Unknown') AS scholarship,
                   a.status, a.applied_at
            FROM scholarship_applications a
            LEFT JOIN scholarships s ON s.id = a.scholarship_id
            ORDER BY a.applied_at DESC
            """
        )
        adf = pd.DataFrame(apps)
        if adf.empty:
            st.info("No application records yet.")
        else:
            st.dataframe(adf, use_container_width=True, hide_index=True)
            csv = adf.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Download CSV",
                csv,
                "scholarship_applications.csv",
                "text/csv",
            )
