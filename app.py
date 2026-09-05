
import os
import re
from datetime import date, datetime, timezone
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup
import streamlit as st
from supabase import create_client, Client

st.set_page_config(page_title="B.Tech Girl Students Scholarship Portal",
                   page_icon="🎓", layout="wide")

SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL", ""))
SUPABASE_KEY = st.secrets.get("SUPABASE_ANON_KEY", os.getenv("SUPABASE_ANON_KEY", ""))
SUPABASE_SERVICE_KEY = st.secrets.get("SUPABASE_SERVICE_KEY", os.getenv("SUPABASE_SERVICE_KEY", ""))
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", os.getenv("ADMIN_PASSWORD", ""))

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Supabase is not configured. Add SUPABASE_URL and SUPABASE_ANON_KEY.")
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
admin_supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY) if SUPABASE_SERVICE_KEY else None

def admin_client():
    return admin_supabase or supabase

def valid_mobile(v):
    return bool(re.fullmatch(r"[6-9]\d{9}", re.sub(r"\s+", "", v or "")))

def today():
    return date.today()

def parse_deadline(v):
    if not v:
        return None
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    except Exception:
        return None

def is_open(s):
    d = parse_deadline(s.get("deadline"))
    return bool(s.get("active")) and (d is None or d >= today())

def get_scholarships(include_expired=False):
    q = supabase.table("scholarships").select(
        "id,name,description,eligibility,documents,deadline,apply_url,"
        "official_url,source_url,source_name,last_verified,active"
    )
    if not include_expired:
        q = q.eq("active", True)
    rows = q.order("deadline").execute().data or []
    return [x for x in rows if include_expired or is_open(x)]

def record_application(student_name, roll, branch, mobile, scholarship_id):
    return supabase.table("scholarship_applications").insert({
        "student_name": student_name.strip(),
        "roll_number": roll.strip(),
        "branch": branch.strip(),
        "mobile_number": mobile.strip(),
        "scholarship_id": scholarship_id,
        "status": "Clicked Apply",
        "applied_at": datetime.now(timezone.utc).isoformat()
    }).execute()

def fetch_webpage(url):
    r = requests.get(url, timeout=20, headers={
        "User-Agent": "ScholarshipPortalBot/1.0 (+admin verification)"
    })
    r.raise_for_status()
    return r.text, r.url

def extract_page_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True))

def collect_source_preview(url):
    """Fetches a source page for administrator review.
    It intentionally does NOT auto-publish extracted eligibility/deadlines."""
    html, final_url = fetch_webpage(url)
    text = extract_page_text(html)
    return final_url, text[:12000]

def save_scholarship(row):
    db = admin_client()
    payload = {
        "name": row["name"].strip(),
        "description": row.get("description", ""),
        "eligibility": row["eligibility"].strip(),
        "documents": row.get("documents", ""),
        "deadline": row.get("deadline") or None,
        "apply_url": row["apply_url"].strip(),
        "official_url": row.get("official_url", "").strip(),
        "source_url": row["source_url"].strip(),
        "source_name": row.get("source_name", "").strip(),
        "last_verified": row.get("last_verified") or str(today()),
        "active": True
    }
    return db.table("scholarships").upsert(payload, on_conflict="id").execute()

st.markdown("## 🎓 B.Tech Girl Students Scholarship Portal")
st.caption("Scholarship name • detailed eligibility • required documents • deadline • official link")

page = st.radio("Go to", ["Scholarships", "My Application", "Admin Dashboard"],
                horizontal=True, label_visibility="collapsed")

if page == "Scholarships":
    rows = get_scholarships()
    st.subheader(f"Open scholarships ({len(rows)})")

    if not rows:
        st.info("No open scholarships are currently available.")
    else:
        # Table-style display requested by the user.
        table = []
        for s in rows:
            d = parse_deadline(s.get("deadline"))
            table.append({
                "Scholarship Name": s["name"],
                "Eligibility": s.get("eligibility", ""),
                "Required Documents": s.get("documents", ""),
                "Last Date": d.strftime("%d-%m-%Y") if d else "See official notice",
                "Status": "OPEN" if is_open(s) else "CLOSED"
            })
        st.dataframe(pd.DataFrame(table), use_container_width=True,
                     hide_index=True, height=420)

        st.divider()
        st.subheader("Apply")
        for s in rows:
            d = parse_deadline(s.get("deadline"))
            if not is_open(s):
                continue

            with st.container(border=True):
                st.markdown(f"### {s['name']}")
                st.write(f"**Eligibility:** {s.get('eligibility','')}")
                st.write(f"**Required documents:** {s.get('documents','')}")
                st.write(f"**Last date:** {d.strftime('%d-%m-%Y') if d else 'See official notice'}")
                st.caption(
                    f"Source: {s.get('source_name') or s.get('source_url','')} | "
                    f"Last verified: {s.get('last_verified','Not recorded')}"
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
            if not name.strip(): errors.append("Student name is required.")
            if not roll.strip(): errors.append("Roll number / Student ID is required.")
            if not branch.strip(): errors.append("Branch is required.")
            if not valid_mobile(mobile): errors.append("Enter a valid 10-digit Indian mobile number.")
            if not consent: errors.append("Consent is required.")

            # Deadline is checked again at the moment of submission.
            current = next((x for x in get_scholarships() if x["id"] == s["id"]), None)
            if not current or not is_open(current):
                errors.append("This scholarship has closed. The application link has been disabled.")

            if errors:
                for e in errors: st.error(e)
            else:
                try:
                    record_application(name, roll, branch, mobile, int(s["id"]))
                    st.success("Application attempt recorded.")
                    st.link_button("Continue to official scholarship website →",
                                   current["apply_url"], type="primary")
                    st.session_state.pop("selected", None)
                except Exception as e:
                    st.error(f"Unable to save details: {e}")

elif page == "My Application":
    st.subheader("Application Confirmation")
    st.info("This portal records the student's attempt to start an application. It does not confirm that the external scholarship form was submitted.")

else:
    st.subheader("🔐 Admin Dashboard")
    password = st.text_input("Admin Password", type="password")
    if not ADMIN_PASSWORD:
        st.warning("Set ADMIN_PASSWORD in Streamlit Secrets.")
        st.stop()
    if password != ADMIN_PASSWORD:
        st.info("Enter the admin password.")
        st.stop()

    db = admin_client()
    tab1, tab2, tab3 = st.tabs(["Scholarships", "Source Collector", "Applications"])

    with tab1:
        all_rows = db.table("scholarships").select(
            "id,name,eligibility,documents,deadline,apply_url,official_url,source_url,source_name,last_verified,active"
        ).order("deadline").execute().data or []

        df = pd.DataFrame(all_rows)
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)

        st.markdown("### Add / update scholarship")
        with st.form("scholarship_editor"):
            name = st.text_input("Scholarship name *")
            eligibility = st.text_area("Eligibility in detail *")
            documents = st.text_area("Required documents")
            deadline = st.date_input("Last date to apply", value=today())
            apply_url = st.text_input("Scholarship application link *")
            official_url = st.text_input("Official information page")
            source_url = st.text_input("Source webpage used for verification *")
            source_name = st.text_input("Source name")
            save = st.form_submit_button("Publish / Update")

        if save:
            if not name or not eligibility or not apply_url or not source_url:
                st.error("Name, eligibility, application link and source URL are required.")
            else:
                try:
                    db.table("scholarships").insert({
                        "name": name.strip(),
                        "eligibility": eligibility.strip(),
                        "documents": documents.strip(),
                        "deadline": deadline.isoformat(),
                        "apply_url": apply_url.strip(),
                        "official_url": official_url.strip(),
                        "source_url": source_url.strip(),
                        "source_name": source_name.strip(),
                        "last_verified": today().isoformat(),
                        "active": True
                    }).execute()
                    st.success("Scholarship published. It will automatically stop being displayed after the deadline.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    with tab2:
        st.write("Enter an official scholarship webpage. The portal fetches the page so the admin can review it.")
        st.warning("Do not auto-publish scraped text. Scholarship eligibility and deadlines can change or be hidden in PDFs/JavaScript. Verify the official notice before publishing.")
        source = st.text_input("Official scholarship webpage URL")
        if st.button("Fetch webpage"):
            try:
                final_url, text = collect_source_preview(source)
                st.success(f"Fetched: {final_url}")
                st.text_area("Page text for verification", text, height=450)
            except Exception as e:
                st.error(f"Unable to fetch page: {e}")

    with tab3:
        apps = db.table("scholarship_applications").select("*").order("applied_at", desc=True).execute().data or []
        st.dataframe(pd.DataFrame(apps), use_container_width=True, hide_index=True)
