import os
import requests
from typing import List
from scraper.models import RegulatoryDocument
import logging

logger = logging.getLogger(__name__)

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")


def send_slack_alert(
    new_docs: List[RegulatoryDocument],
    amended_docs: List[RegulatoryDocument],
):
    if not SLACK_WEBHOOK_URL:
        logger.warning("[Alerting] SLACK_WEBHOOK_URL not set — skipping Slack alert")
        return

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Regulatory Update Detected"},
        },
    ]

    if new_docs:
        doc_lines = "\n".join(
            f"* *{d.title}* [{d.source_name} | {d.jurisdiction.value}] — <{d.source_url}|view>"
            for d in new_docs[:5]
        )
        suffix = f"\n_...and {len(new_docs) - 5} more_" if len(new_docs) > 5 else ""
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{len(new_docs)} New Regulation(s):*\n{doc_lines}{suffix}",
            },
        })

    if amended_docs:
        doc_lines = "\n".join(
            f"* :warning: *{d.title}* [{d.source_name}] — AMENDED <{d.source_url}|view>"
            for d in amended_docs[:5]
        )
        suffix = f"\n_...and {len(amended_docs) - 5} more_" if len(amended_docs) > 5 else ""
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{len(amended_docs)} Amended Regulation(s):*\n{doc_lines}{suffix}",
            },
        })

    blocks.append({"type": "divider"})
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": "_Sent by RegScan — AI Regulatory Intelligence_"}],
    })

    try:
        response = requests.post(SLACK_WEBHOOK_URL, json={"blocks": blocks}, timeout=10)
        response.raise_for_status()
        logger.info("Slack alert sent successfully")
    except Exception as e:
        logger.error(f"Failed to send Slack alert: {e}")
