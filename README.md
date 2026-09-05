
# Scholarship Portal V2

This version is based on the user's uploaded Streamlit app and changes the scholarship catalogue to include:

- Scholarship name
- Detailed eligibility
- Required documents
- Last date
- Application link
- Official/source webpage
- Last verified date
- Automatic closing of expired scholarships
- Admin source-page fetcher for verification
- Existing student application tracking

## IMPORTANT: "directly gather from webpages"

A production scholarship portal should not blindly scrape and publish eligibility/deadlines. Many official portals use JavaScript, PDFs, CAPTCHAs, or change notices. This implementation therefore provides a safe source collector:

1. Admin enters the official webpage.
2. Portal fetches and displays the page text.
3. Admin verifies the exact eligibility, documents and deadline.
4. Admin publishes the verified record to Supabase.
5. Students see only open records.

For full automatic ingestion, add a scheduled backend worker that fetches approved source URLs and uses an extraction model/rules to create a "pending_review" record. Never let an unverified extraction overwrite a published deadline.

## Supabase setup

1. Create a Supabase project.
2. Open SQL Editor.
3. Run `schema.sql`.
4. Optionally run `cron_disable_expired.sql` if pg_cron is available.
5. In Streamlit Cloud secrets set:

SUPABASE_URL = "https://YOURPROJECT.supabase.co"
SUPABASE_ANON_KEY = "your-anon-key"
SUPABASE_SERVICE_KEY = "your-service-role-key"
ADMIN_PASSWORD = "strong-admin-password"

Never expose SUPABASE_SERVICE_KEY to the browser.

## Run locally

pip install -r requirements.txt
streamlit run app.py

## Deadline behavior

The student page checks `deadline >= today's date` before showing a scholarship.
The application form checks the deadline AGAIN immediately before recording the application.
Therefore an expired link is not offered even if the page was left open overnight.

The optional pg_cron job additionally sets `active=false` after expiry.

## Suggested production architecture

official webpages/PDFs
        ↓
source collector
        ↓
raw source snapshot
        ↓
extractor
        ↓
pending_review
        ↓
admin verification
        ↓
published scholarships
        ↓
student portal

This is much safer than automatically publishing arbitrary scraped content.
