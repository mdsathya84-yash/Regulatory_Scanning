import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List
from scraper.models import RegulatoryDocument
import logging

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
ALERT_RECIPIENTS = os.getenv("ALERT_RECIPIENTS", "")


def _build_html(
    new_docs: List[RegulatoryDocument],
    amended_docs: List[RegulatoryDocument],
) -> str:
    rows_new = "".join(
        f"<tr><td>{d.title}</td><td>{d.source_name}</td><td>{d.jurisdiction.value}</td>"
        f"<td><a href='{d.source_url}'>View</a></td></tr>"
        for d in new_docs
    )
    rows_amended = "".join(
        f"<tr style='background:#fff3cd'><td>⚠️ {d.title}</td><td>{d.source_name}</td>"
        f"<td>{d.jurisdiction.value}</td><td><a href='{d.source_url}'>View</a></td></tr>"
        for d in amended_docs
    )

    table_style = (
        "border-collapse:collapse;width:100%;font-family:Arial,sans-serif;font-size:13px"
    )
    th_style = "background:#003366;color:white;padding:8px;text-align:left"
    td_style = "padding:7px;border-bottom:1px solid #ddd"

    return f"""
    <html><body>
    <h2 style="color:#003366">RegScan — Regulatory Update Alert</h2>
    <p>The following regulatory changes were detected during the latest scan.</p>

    {"<h3>New Regulations</h3><table style='" + table_style + "'>"
     "<tr><th style='" + th_style + "'>Title</th><th style='" + th_style + "'>Source</th>"
     "<th style='" + th_style + "'>Jurisdiction</th><th style='" + th_style + "'>Link</th></tr>"
     + rows_new + "</table>" if new_docs else ""}

    {"<h3>Amended Regulations</h3><table style='" + table_style + "'>"
     "<tr><th style='" + th_style + "'>Title</th><th style='" + th_style + "'>Source</th>"
     "<th style='" + th_style + "'>Jurisdiction</th><th style='" + th_style + "'>Link</th></tr>"
     + rows_amended + "</table>" if amended_docs else ""}

    <p style="color:#666;font-size:11px;margin-top:20px">
    Sent by RegScan &mdash; AI Regulatory Intelligence Platform
    </p>
    </body></html>
    """


def send_email_alert(
    new_docs: List[RegulatoryDocument],
    amended_docs: List[RegulatoryDocument],
    recipients: List[str] = None,
):
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.warning("[Alerting] SMTP credentials not configured — skipping email alert")
        return

    recipients = recipients or [r.strip() for r in ALERT_RECIPIENTS.split(",") if r.strip()]
    if not recipients:
        logger.warning("[Alerting] No email recipients configured")
        return

    total = len(new_docs) + len(amended_docs)
    subject = f"[RegScan] {total} Regulatory Update(s) Detected — {len(new_docs)} New, {len(amended_docs)} Amended"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = ", ".join(recipients)

    plain = (
        f"RegScan Alert\n\n"
        f"New regulations: {len(new_docs)}\n"
        f"Amended regulations: {len(amended_docs)}\n\n"
        + "\n".join(f"- {d.title} ({d.source_name})" for d in new_docs + amended_docs)
    )
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(_build_html(new_docs, amended_docs), "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, recipients, msg.as_string())
        logger.info(f"Email alert sent to {recipients}")
    except Exception as e:
        logger.error(f"Failed to send email alert: {e}")
