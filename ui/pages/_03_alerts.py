import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import json
import streamlit as st
from datetime import datetime

st.title("Alert History & Configuration")
st.caption("View detected regulatory changes and configure notification channels.")

# Alert history from state file
STATE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "seen_content_hashes.json"
)

tab_history, tab_config = st.tabs(["Alert History", "Notification Configuration"])

with tab_history:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            seen = json.load(f)
        st.metric("Documents Tracked", len(seen))
        st.info("The change detector has tracked these document IDs. New or hash-changed entries trigger alerts.")
        with st.expander("View tracked document IDs"):
            st.json(seen)
    else:
        st.warning("No alert history found. Run the scraper pipeline first.")

    # Simulated alert log (replace with real DB in production)
    st.subheader("Recent Alerts (Simulation)")
    sample_alerts = [
        {
            "timestamp": datetime.utcnow().isoformat(),
            "type": "NEW",
            "title": "NCSC Advisory: Supply Chain Security",
            "source": "NCSC",
            "jurisdiction": "UK",
        },
        {
            "timestamp": datetime.utcnow().isoformat(),
            "type": "AMENDED",
            "title": "EU Sanctions — Russia Annex IX Updated",
            "source": "EEAS",
            "jurisdiction": "EU",
        },
    ]
    for alert in sample_alerts:
        badge = "NEW" if alert["type"] == "NEW" else "AMENDED"
        color = "green" if alert["type"] == "NEW" else "orange"
        st.markdown(
            f":{color}[**{badge}**] **{alert['title']}** "
            f"— {alert['source']} | {alert['jurisdiction']} | `{alert['timestamp'][:19]}`"
        )

with tab_config:
    st.subheader("Slack Notifications")
    slack_url = st.text_input(
        "Slack Webhook URL",
        value=os.getenv("SLACK_WEBHOOK_URL", ""),
        type="password",
        help="Set SLACK_WEBHOOK_URL in your .env file",
    )
    if st.button("Test Slack Alert"):
        if slack_url:
            import requests
            try:
                r = requests.post(slack_url, json={"text": "RegScan test alert — connection OK"}, timeout=5)
                if r.ok:
                    st.success("Slack test message sent successfully.")
                else:
                    st.error(f"Slack returned {r.status_code}: {r.text}")
            except Exception as e:
                st.error(f"Failed: {e}")
        else:
            st.warning("Enter a Slack Webhook URL first.")

    st.divider()
    st.subheader("Email Notifications")
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("SMTP Host", value=os.getenv("SMTP_HOST", "smtp.gmail.com"), disabled=True)
        st.text_input("SMTP User", value=os.getenv("SMTP_USER", ""), disabled=True)
    with col2:
        st.text_input("SMTP Port", value=os.getenv("SMTP_PORT", "587"), disabled=True)
        st.text_input("Recipients", value=os.getenv("ALERT_RECIPIENTS", ""), disabled=True)
    st.info("Update email settings in your `.env` file and restart the app.")

    st.divider()
    st.subheader("Scrape Schedule")
    interval = st.number_input("Scrape interval (hours)", min_value=1, max_value=24, value=6)
    st.info(f"Set `SCRAPER_INTERVAL_HOURS={interval}` in `.env` to apply. Restart the scraper service.")
